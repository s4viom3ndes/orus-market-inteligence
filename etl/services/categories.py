import logging
import time
from typing import Iterator
from services.ml_client import MLClient

log = logging.getLogger(__name__)

THROTTLE_SEC = 0.05


def get_category(client: MLClient, cat_id: str) -> dict:
    return client.get(f"/categories/{cat_id}")


def walk(root_id: str, client: MLClient, max_depth: int, depth: int = 0) -> Iterator[dict]:
    """Yield categories a cada nivel. Se max_depth atingido ou for folha, para de descer.
    Retorna nodos 'consideraveis' como folhas efetivas (para efeito de coleta).
    """
    if depth > max_depth:
        return
    try:
        cat = get_category(client, root_id)
    except Exception as e:
        log.warning("falha em %s: %s", root_id, e)
        return

    children = cat.get("children_categories") or []
    node = {
        "id": cat["id"],
        "name": cat["name"],
        "depth": depth,
        "total_items": cat.get("total_items_in_this_category"),
        "path": " > ".join(c["name"] for c in cat.get("path_from_root", [])),
    }

    # se atingiu profundidade max OU eh folha real: yield e para
    if depth == max_depth or not children:
        yield node
        return

    time.sleep(THROTTLE_SEC)
    for ch in children:
        yield from walk(ch["id"], client, max_depth, depth + 1)


def discover(roots: list[str], max_depth: int = 2) -> list[dict]:
    """Descobre categorias a partir de raizes, limitando profundidade.
    max_depth=2 significa: raiz -> filhos -> netos, para nesse nivel.
    """
    client = MLClient()
    try:
        result = []
        for root in roots:
            t0 = time.time()
            count_before = len(result)
            for cat in walk(root, client, max_depth):
                result.append(cat)
            log.info("raiz %s: %s categorias (depth<=%s) em %.1fs",
                     root, len(result) - count_before, max_depth, time.time() - t0)
        return result
    finally:
        client.close()
