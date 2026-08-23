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
