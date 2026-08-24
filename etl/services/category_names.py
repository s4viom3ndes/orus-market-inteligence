"""Cache de nomes de categorias ML.

Mantem state/category_names.json no R2 com {cat_id: {name, path}}.
Populado incrementalmente pelos jobs de coleta.
"""
import json
import logging
from src.config import USE_REMOTE_STORAGE

log = logging.getLogger(__name__)

CACHE_KEY = "state/category_names.json"


def load() -> dict:
    if not USE_REMOTE_STORAGE:
        return {}
    from storage.r2 import download_bytes
    raw = download_bytes(CACHE_KEY)
    return json.loads(raw) if raw else {}


def save(mapping: dict) -> None:
    if not USE_REMOTE_STORAGE:
        return
    from storage.r2 import upload_bytes
    payload = json.dumps(mapping, indent=2, ensure_ascii=False).encode("utf-8")
    upload_bytes(payload, CACHE_KEY, content_type="application/json")


def ensure(cat_ids: list[str], client) -> dict:
    """Garante que todos cat_ids estao no cache. Faz fetch pros ausentes."""
    mapping = load()
    added = 0
    for cid in cat_ids:
        if cid in mapping:
            continue
        try:
            cat = client.get(f"/categories/{cid}")
            mapping[cid] = {
                "name": cat.get("name") or cid,
                "path": " > ".join(c["name"] for c in cat.get("path_from_root") or []),
            }
            added += 1
        except Exception as e:
            log.warning("nao consegui nome de %s: %s", cid, e)
    if added:
        log.info("cache de categorias: %s nomes novos, total %s", added, len(mapping))
        save(mapping)
    return mapping


def name_of(cat_id: str, mapping: dict) -> str:
    entry = mapping.get(cat_id)
    return entry.get("name") if entry else cat_id
