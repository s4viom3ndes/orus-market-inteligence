import argparse
import logging
import time
from src.config import PROJECT_ROOT
from services.ml_client import MLClient
from services.job_status import track
from storage.parquet_writer import write_snapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
)
log = logging.getLogger("collect_trends")

DATA_DIR = PROJECT_ROOT / "data"


def run(site: str, categories: list[str], dataset: str) -> dict:
    captured_at = int(time.time())
    client = MLClient()
    rows = []
    try:
        # trends do site (Brasil todo)
        try:
            for i, t in enumerate(client.get(f"/trends/{site}") or []):
                rows.append({
                    "captured_at": captured_at,
                    "site": site,
                    "scope": "site",
                    "category_id": None,
                    "rank": i,
                    "keyword": t.get("keyword"),
                    "url": t.get("url"),
                })
        except Exception as e:
            log.warning("trends site falhou: %s", e)

        # trends por categoria
        for cat_id in categories:
            try:
                for i, t in enumerate(client.get(f"/trends/{site}/category/{cat_id}") or []):
                    rows.append({
                        "captured_at": captured_at,
                        "site": site,
                        "scope": "category",
                        "category_id": cat_id,
                        "rank": i,
                        "keyword": t.get("keyword"),
                        "url": t.get("url"),
                    })
            except Exception as e:
                log.warning("trends cat=%s falhou: %s", cat_id, e)
    finally:
        client.close()

    log.info("trends coletadas: %s linhas", len(rows))
    counts = {"rows": len(rows)}
    if rows:
        out = write_snapshot(rows, dataset=dataset, base_dir=DATA_DIR)
        log.info("arquivo: %s", out)
        counts["output"] = out
    return counts


DEFAULT_ROOT_CATS = ["MLB1574", "MLB5726"]


def main():
    p = argparse.ArgumentParser(description="Coleta trending searches do ML por site e categoria")
    p.add_argument("--site", default="MLB")
    p.add_argument("--categories", nargs="+", default=DEFAULT_ROOT_CATS)
    p.add_argument("--dataset", default="trends")
    args = p.parse_args()

    with track("collect_trends") as job:
        job["counts"] = run(site=args.site, categories=args.categories, dataset=args.dataset)


if __name__ == "__main__":
    main()
