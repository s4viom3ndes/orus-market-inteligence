import json
import logging
import time
from pathlib import Path
import yaml
import polars as pl
from src.config import ETL_ROOT, R2_BUCKET, USE_REMOTE_STORAGE

log = logging.getLogger(__name__)

MOCK_CONFIG = ETL_ROOT / "config" / "mock_client.yaml"
STATE_KEY = "state/buy_box_state.json"
LOCAL_STATE = ETL_ROOT / "state_buy_box.json"


def load_mock_client() -> dict:
    return yaml.safe_load(MOCK_CONFIG.read_text(encoding="utf-8"))


def load_latest_snapshot() -> pl.DataFrame:
    """Retorna o parquet mais recente de market_offers (do R2 ou local)."""
    if USE_REMOTE_STORAGE:
        from storage.r2 import get_client
        r = get_client().list_objects_v2(Bucket=R2_BUCKET, Prefix="market_offers/")
        objs = sorted(r.get("Contents", []), key=lambda x: x["LastModified"], reverse=True)
        if not objs:
            raise RuntimeError("nenhum snapshot no R2")
        key = objs[0]["Key"]
        log.info("lendo snapshot: r2://%s/%s", R2_BUCKET, key)
        obj = get_client().get_object(Bucket=R2_BUCKET, Key=key)
        import io
        return pl.read_parquet(io.BytesIO(obj["Body"].read()))

    import glob
    files = sorted(glob.glob(str(ETL_ROOT.parent / "data" / "market_offers" / "**" / "*.parquet"), recursive=True))
    if not files:
        raise RuntimeError("nenhum snapshot local")
    log.info("lendo snapshot local: %s", files[-1])
    return pl.read_parquet(files[-1])


def _load_state() -> dict:
    if USE_REMOTE_STORAGE:
        from storage.r2 import download_bytes
        raw = download_bytes(STATE_KEY)
        if raw:
            return json.loads(raw)
    if LOCAL_STATE.exists():
        return json.loads(LOCAL_STATE.read_text())
    return {}


def _save_state(state: dict) -> None:
    payload = json.dumps(state, indent=2, ensure_ascii=False).encode("utf-8")
    LOCAL_STATE.write_bytes(payload)
    if USE_REMOTE_STORAGE:
        from storage.r2 import upload_bytes
        upload_bytes(payload, STATE_KEY, content_type="application/json")


def evaluate_sku(sku_cfg: dict, snapshot: pl.DataFrame) -> dict:
    """Avalia status de 1 SKU mockado contra o snapshot."""
    pid = sku_cfg["catalog_product_id"]
    offers = snapshot.filter(pl.col("catalog_product_id") == pid).sort("rank")

    result = {
        "sku": sku_cfg["sku"],
        "catalog_product_id": pid,
        "category_id": sku_cfg["category_id"],
        "current_price": sku_cfg["current_price"],
        "min_price": sku_cfg["min_price"],
        "target_position": sku_cfg["target_position"],
        "product_name": None,
        "n_competitors": offers.height,
        "winner_price": None,
        "winner_seller_id": None,
        "winner_shipping": None,
        "our_position_if_priced_now": None,
        "gap_to_winner": None,
        "recommendation": None,
        "status": "no_data",
    }

    if offers.is_empty():
        return result

    first = offers.row(0, named=True)
    result["product_name"] = first["product_name"]
    result["winner_price"] = float(first["price"])
    result["winner_seller_id"] = int(first["seller_id"])
    result["winner_shipping"] = first.get("shipping_logistic_type")

    prices = offers["price"].to_list()
    my_price = float(sku_cfg["current_price"])
    our_pos = sum(1 for p in prices if p < my_price)
    result["our_position_if_priced_now"] = our_pos
    result["gap_to_winner"] = round(my_price - result["winner_price"], 2)

    target = sku_cfg["target_position"]
    min_p = float(sku_cfg["min_price"])

    if our_pos <= target:
        result["status"] = "winning"
        result["recommendation"] = "manter preco"
    else:
        needed_price = round(result["winner_price"] - 0.01, 2)
        if needed_price >= min_p:
            result["status"] = "losing_recoverable"
            result["recommendation"] = f"baixar preco pra R$ {needed_price:.2f} (winner esta R$ {result['winner_price']:.2f})"
        else:
            result["status"] = "losing_locked"
            result["recommendation"] = f"buy box exige R$ {needed_price:.2f}, mas min_price=R$ {min_p:.2f} - reavaliar margem ou aceitar 2º"

    return result


def run() -> dict:
    cfg = load_mock_client()
    snap = load_latest_snapshot()
    log.info("snapshot com %s linhas, avaliando %s SKUs", snap.height, len(cfg["skus"]))

    results = [evaluate_sku(s, snap) for s in cfg["skus"]]
    prev = _load_state()
    changes = []

    for r in results:
        p = prev.get(r["sku"], {})
        if r["status"] != p.get("status") or r["winner_seller_id"] != p.get("winner_seller_id"):
            changes.append({
                "sku": r["sku"],
                "before": {"status": p.get("status"), "winner": p.get("winner_seller_id")},
                "after": {"status": r["status"], "winner": r["winner_seller_id"]},
            })

    new_state = {r["sku"]: {
        "status": r["status"],
        "winner_seller_id": r["winner_seller_id"],
        "winner_price": r["winner_price"],
        "last_checked": int(time.time()),
    } for r in results}
    _save_state(new_state)

    return {
        "seller": cfg["seller"],
        "results": results,
        "changes": changes,
        "checked_at": int(time.time()),
    }
