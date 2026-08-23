import argparse
import json
import logging
import time
from pathlib import Path
from src.config import PROJECT_ROOT, WATCHLIST_SELLERS, WATCHLIST_CATEGORIES, USE_REMOTE_STORAGE
from services.ml_client import MLClient
from services.search import iter_highlights, get_product, iter_product_items, normalize_offer
from services.enrichment import get_visits_for, get_reviews_summary, get_questions_count
from storage.parquet_writer import write_snapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
)
log = logging.getLogger("collect_market")

DATA_DIR = PROJECT_ROOT / "data"
LEAVES_LOCAL = PROJECT_ROOT / "state_leaves.json"
LEAVES_KEY = "state/leaves.json"


def load_leaf_categories() -> list[str]:
    """Carrega lista de folhas. Tenta R2, depois local, depois fallback."""
    if USE_REMOTE_STORAGE:
        from storage.r2 import download_bytes
        raw = download_bytes(LEAVES_KEY)
        if raw:
            data = json.loads(raw)
            leaves = [l["id"] for l in data.get("leaves", [])]
            log.info("carreguei %s folhas do R2", len(leaves))
            return leaves

    if LEAVES_LOCAL.exists():
        data = json.loads(LEAVES_LOCAL.read_text(encoding="utf-8"))
        leaves = [l["id"] for l in data.get("leaves", [])]
        log.info("carreguei %s folhas do arquivo local", len(leaves))
        return leaves

    log.warning("nenhum arquivo de folhas encontrado, usando WATCHLIST_CATEGORIES do config")
    return WATCHLIST_CATEGORIES


def run(categories: list[str], dataset: str, enrich: bool = True, max_per_cat: int | None = None) -> None:
    watch = set(WATCHLIST_SELLERS)
    log.info("coleta: %s categorias | watchlist=%s | enrich=%s", len(categories), watch, enrich)
    captured_at = int(time.time())

    rows = []
    watched_hits = 0
    client = MLClient()

    try:
        for ci, cat_id in enumerate(categories, 1):
            try:
                product_ids = list(iter_highlights(cat_id, client=client))
            except Exception as e:
                log.warning("[%s/%s cat=%s] highlights falhou: %s", ci, len(categories), cat_id, e)
                continue

            if max_per_cat:
                product_ids = product_ids[:max_per_cat]

            if not product_ids:
                continue

            log.info("[%s/%s] cat=%s -> %s produtos", ci, len(categories), cat_id, len(product_ids))

            cat_offers: list[tuple[dict, dict]] = []
            for pid in product_ids:
                try:
                    product = get_product(pid, client)
                    offers = list(iter_product_items(pid, client))
                except Exception as e:
                    log.debug("falha em %s: %s", pid, e)
                    continue
                for offer in offers:
                    cat_offers.append((product, offer))

            visits_map = {}
            if enrich and cat_offers:
                winner_item_ids = [o["item_id"] for _, o in cat_offers
                                   if o.get("_rank") == 0 and o.get("item_id")]
                visits_map = get_visits_for(winner_item_ids, client)

            reviews_cache: dict[str, dict] = {}
            questions_cache: dict[str, int | None] = {}

            for product, offer in cat_offers:
                iid = offer.get("item_id")
                pid_key = product.get("id")

                reviews = None
                questions = None
                if enrich and pid_key:
                    if pid_key not in reviews_cache:
                        reviews_cache[pid_key] = get_reviews_summary(iid, client)
                        questions_cache[pid_key] = get_questions_count(iid, client)
                    reviews = reviews_cache[pid_key]
                    questions = questions_cache[pid_key]

                row = normalize_offer(
                    product, offer, captured_at,
                    watchlist_sellers=watch, category_id=cat_id,
                    visits_30d=visits_map.get(iid),
                    reviews_count=(reviews or {}).get("count"),
                    reviews_avg=(reviews or {}).get("avg_rating"),
                    questions_count=questions,
                )
                rows.append(row)
                if row["is_watched_seller"]:
                    watched_hits += 1
    finally:
        client.close()

    log.info("coleta concluida: %s linhas | %s da watchlist", len(rows), watched_hits)

    if rows:
        out = write_snapshot(rows, dataset=dataset, base_dir=DATA_DIR)
        log.info("arquivo: %s", out)


def main():
    p = argparse.ArgumentParser(description="Coleta bestsellers do ML + ofertas + enrichment consumidor")
    p.add_argument("--categories", nargs="+", help="IDs de categorias (default: folhas descobertas)")
    p.add_argument("--dataset", default="market_offers")
    p.add_argument("--no-enrich", action="store_true", help="pula visits/reviews/questions")
    p.add_argument("--max-per-cat", type=int, help="limita N produtos por categoria")
    args = p.parse_args()

    cats = args.categories or load_leaf_categories()
    run(categories=cats, dataset=args.dataset, enrich=not args.no_enrich, max_per_cat=args.max_per_cat)


if __name__ == "__main__":
    main()
