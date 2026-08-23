import logging
import time
from services.ml_client import MLClient

log = logging.getLogger(__name__)

THROTTLE_SEC = 0.1
BATCH_SIZE = 20


def get_visits_batch(item_ids: list[str], client: MLClient) -> dict[str, int]:
    """Retorna dict {item_id: total_visits} para uma lista de item_ids (batch)."""
    if not item_ids:
        return {}
    results: dict[str, int] = {}
    for i in range(0, len(item_ids), BATCH_SIZE):
        chunk = item_ids[i:i + BATCH_SIZE]
        try:
            data = client.get("/visits/items", ids=",".join(chunk))
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, int):
                        results[k] = v
        except Exception as e:
            log.warning("get_visits_batch falhou pra chunk %s: %s", chunk[:3], e)
        time.sleep(THROTTLE_SEC)
    return results


def get_reviews_summary(item_id: str, client: MLClient) -> dict:
    """Retorna {count, avg_rating} para um item."""
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
