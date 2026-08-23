import argparse
import io
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import polars as pl

from src.config import PROJECT_ROOT, R2_BUCKET, USE_REMOTE_STORAGE
from services.ml_client import MLClient
from services.buy_box_monitor import load_mock_client, load_latest_snapshot, _fetch_offers_live
from services.repricer import suggest
from services.job_status import track
from storage.parquet_writer import write_snapshot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s | %(message)s")
log = logging.getLogger("run_repricer")

TZ_SP = ZoneInfo("America/Sao_Paulo")
DATA_DIR = PROJECT_ROOT / "data"


def run() -> dict:
    cfg = load_mock_client()
    snapshot = load_latest_snapshot()
    seller_has_full = bool(cfg.get("seller", {}).get("has_full", False))
    defaults = cfg.get("defaults", {}) or {}

    log.info("repricer: %s SKUs, seller_has_full=%s, defaults=%s",
             len(cfg["skus"]), seller_has_full, defaults)

    rows = []
    changes = 0
    client = MLClient()
    try:
        for sku_cfg in cfg["skus"]:
            pid = sku_cfg["catalog_product_id"]
            offers = snapshot.filter(pl.col("catalog_product_id") == pid).sort("rank")
            if offers.is_empty():
                offers = _fetch_offers_live(pid, sku_cfg["category_id"], client).sort("rank")

            sug = suggest(sku_cfg, offers, seller_has_full, defaults)
            sug["at"] = int(time.time())
            rows.append(sug)
            log.info("  [%s] %s | %s", sug["sku"], sug["status"], sug["reason"])
            if sug["status"] == "suggest_change":
                changes += 1
    finally:
        client.close()

    if rows:
        out = write_snapshot(rows, dataset="reprice_suggestions", base_dir=DATA_DIR)
        log.info("sugestoes salvas: %s", out)

    return {
        "skus_avaliados": len(rows),
        "changes_sugeridas": changes,
        "output": out if rows else None,
    }


def main():
    p = argparse.ArgumentParser(description="Motor de repricer - gera sugestoes por SKU")
    p.parse_args()
    with track("repricer") as job:
        job["counts"] = run()


if __name__ == "__main__":
    main()
