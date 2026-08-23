import argparse
import logging
import time
from src.config import PROJECT_ROOT, WATCHLIST_SELLERS, WATCHLIST_CATEGORIES
from services.ml_client import MLClient
from services.search import iter_highlights, get_product, iter_product_items, normalize_offer
from storage.parquet_writer import write_snapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
)
log = logging.getLogger("collect_market")

DATA_DIR = PROJECT_ROOT / "data"


def run(categories: list[str], dataset: str) -> None:
    watch = set(WATCHLIST_SELLERS)
    log.info("iniciando coleta | categorias=%s | watchlist_sellers=%s", categories, watch)
    captured_at = int(time.time())

    rows = []
    watched_hits = 0
    client = MLClient()
    try:
        for cat_id in categories:
            product_ids = list(iter_highlights(cat_id, client=client))
            log.info("[%s] %s produtos destaque", cat_id, len(product_ids))

            for i, pid in enumerate(product_ids, 1):
                try:
                    product = get_product(pid, client)
                    offers = list(iter_product_items(pid, client))
                except Exception as e:
                    log.warning("[%s %s/%s] falha em %s: %s", cat_id, i, len(product_ids), pid, e)
                    continue

                for offer in offers:
                    row = normalize_offer(product, offer, captured_at,
                                          watchlist_sellers=watch, category_id=cat_id)
                    rows.append(row)
                    if row["is_watched_seller"]:
                        watched_hits += 1

                log.info("[%s %s/%s] %s -> %s ofertas | %s",
                         cat_id, i, len(product_ids), pid, len(offers),
                         (product.get("name") or "")[:60])
    finally:
        client.close()

    log.info("coleta concluida: %s linhas | %s da watchlist", len(rows), watched_hits)

    if rows:
        out = write_snapshot(rows, dataset=dataset, base_dir=DATA_DIR)
        log.info("arquivo: %s", out)
    else:
        log.warning("nenhuma linha coletada")


def main():
    p = argparse.ArgumentParser(description="Coleta bestsellers do ML + ofertas por vendedor, salva Parquet")
    p.add_argument(
        "--categories", nargs="+",
        help="IDs de categorias (ex: MLB1055 MLB1648). Se omitido, usa WATCHLIST_CATEGORIES do config.",
    )
    p.add_argument("--dataset", default="market_offers", help="nome do dataset")
    args = p.parse_args()

    cats = args.categories or WATCHLIST_CATEGORIES
    if not cats:
        p.error("passe --categories ou preencha WATCHLIST_CATEGORIES em src/config.py")

    run(categories=cats, dataset=args.dataset)


if __name__ == "__main__":
    main()
