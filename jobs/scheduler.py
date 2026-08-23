import argparse
import logging
import time
import schedule

from src.config import WATCHLIST_CATEGORIES
from jobs.collect_market import run as collect_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
)
log = logging.getLogger("scheduler")


def tick(dataset: str):
    try:
        log.info("--- tick: iniciando coleta agendada ---")
        collect_run(categories=WATCHLIST_CATEGORIES, dataset=dataset)
        log.info("--- tick concluido ---")
    except Exception as e:
        log.exception("falha no tick: %s", e)


def main():
    p = argparse.ArgumentParser(description="Agendador que roda collect_market periodicamente")
    p.add_argument("--every-minutes", type=int, default=60,
                   help="intervalo entre coletas em minutos (default 60)")
    p.add_argument("--dataset", default="market_offers", help="nome do dataset")
    p.add_argument("--run-now", action="store_true",
                   help="roda uma vez imediatamente antes de comecar o loop")
    args = p.parse_args()

    if not WATCHLIST_CATEGORIES:
        log.error("WATCHLIST_CATEGORIES vazio em src/config.py. Nada a coletar.")
        return

    log.info("scheduler iniciado | intervalo=%s min | categorias=%s",
             args.every_minutes, WATCHLIST_CATEGORIES)

    if args.run_now:
        tick(args.dataset)

    schedule.every(args.every_minutes).minutes.do(tick, dataset=args.dataset)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
