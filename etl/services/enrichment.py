import logging
import time
from services.ml_client import MLClient

log = logging.getLogger(__name__)

THROTTLE_SEC = 0.05


def get_visits(item_id: str, client: MLClient) -> int | None:
    """ML /visits/items aceita apenas 1 id por chamada (mudanca recente)."""
    try:
        data = client.get("/visits/items", ids=item_id)
        if isinstance(data, dict):
            v = data.get(item_id)
            if isinstance(v, int):
                return v
    except Exception as e:
        log.debug("visits falhou %s: %s", item_id, e)
    return None


def get_visits_for(item_ids: list[str], client: MLClient) -> dict[str, int]:
    results: dict[str, int] = {}
    for iid in item_ids:
        v = get_visits(iid, client)
        if v is not None:
            results[iid] = v
        time.sleep(THROTTLE_SEC)
    return results


def get_reviews_summary(item_id: str, client: MLClient) -> dict:
    try:
        data = client.get(f"/reviews/item/{item_id}", limit=1)
        total = (data.get("paging") or {}).get("total", 0)
        rating = data.get("rating_average")
        return {"count": total, "avg_rating": rating}
    except Exception as e:
        log.debug("reviews falhou %s: %s", item_id, e)
        return {"count": None, "avg_rating": None}


def get_questions_count(item_id: str, client: MLClient) -> int | None:
    try:
        data = client.get("/questions/search", item_id=item_id, limit=1)
        return data.get("total", 0)
    except Exception as e:
        log.debug("questions falhou %s: %s", item_id, e)
        return None


def get_seller_info(seller_id: int, client: MLClient) -> dict:
    """Reputacao publica do seller: /users/{id}. Sempre retorna dict (chaves None se falhar)."""
    empty = {
        "nickname": None,
        "reputation_level": None,
        "power_status": None,
        "tx_total": None,
        "ratings_negative": None,
    }
    try:
        data = client.get(f"/users/{seller_id}")
    except Exception as e:
        log.debug("seller %s falhou: %s", seller_id, e)
        return empty
    rep = data.get("seller_reputation") or {}
    tx = rep.get("transactions") or {}
    ratings = tx.get("ratings") or {}
    return {
        "nickname": data.get("nickname"),
        "reputation_level": rep.get("level_id"),
        "power_status": rep.get("power_seller_status"),
        "tx_total": tx.get("total"),
        "ratings_negative": ratings.get("negative"),
    }


def get_sellers_for(seller_ids: list[int], client: MLClient) -> dict[int, dict]:
    """Cache de reputacao por seller_id (dedup ja feita pelo caller)."""
    results: dict[int, dict] = {}
    for sid in seller_ids:
        results[sid] = get_seller_info(sid, client)
        time.sleep(THROTTLE_SEC)
    return results
