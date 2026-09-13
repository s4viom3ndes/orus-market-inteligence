"""Dia a dia: pega snapshot mais recente, extrai desempenho do cliente
(REAL via WATCHLIST_SELLERS + MOCK via mock_client.yaml), grava em
buy_box_history/date=YYYY-MM-DD/. Alimenta time-series na dashboard."""
import argparse
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import polars as pl
from src.config import PROJECT_ROOT
from services.buy_box_monitor import load_latest_snapshot, load_mock_client
from services.client_history import build_client_snapshot, build_mock_snapshot
from services.job_status import track
from storage.parquet_writer import write_snapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
)
log = logging.getLogger("track_client_history")

TZ_SP = ZoneInfo("America/Sao_Paulo")
DATA_DIR = PROJECT_ROOT / "data"


def run() -> dict:
    snap = load_latest_snapshot()
    date_str = datetime.now(TZ_SP).strftime("%Y-%m-%d")

    parts: list[pl.DataFrame] = []

    real = build_client_snapshot(snap, date_str)
    if not real.is_empty():
        log.info("REAL: %s ofertas do cliente no snapshot", real.height)
        parts.append(real)
    else:
        log.info("REAL: cliente nao aparece no snapshot (OAuth nao feito)")

    try:
        mock_cfg = load_mock_client()
        mock = build_mock_snapshot(snap, mock_cfg, date_str)
        if not mock.is_empty():
            log.info("MOCK: %s SKUs avaliados via mock_client.yaml", mock.height)
            parts.append(mock)
    except Exception as e:
        log.warning("MOCK falhou: %s", e)

    if not parts:
        log.warning("nenhuma linha para gravar (nem real nem mock)")
        return {"rows": 0, "winning_buy_box": 0, "unique_products": 0}

    hist = pl.concat(parts, how="diagonal_relaxed")
    winning = int(hist.filter(pl.col("is_buy_box_winner")).height)
    unique = int(hist.select("catalog_product_id").n_unique())

    log.info(
        "total: %s linhas | %s ganhando buy box | %s produtos unicos",
        hist.height, winning, unique,
    )

    rows = hist.to_dicts()
    out = write_snapshot(rows, dataset="buy_box_history", base_dir=DATA_DIR)
    log.info("gravado: %s", out)

    return {
        "rows": hist.height,
        "winning_buy_box": winning,
        "unique_products": unique,
        "output": out,
    }


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    with track("track_client_history") as job:
        job["counts"] = run()


if __name__ == "__main__":
    main()
