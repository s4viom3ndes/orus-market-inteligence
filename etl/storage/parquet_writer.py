import logging
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import polars as pl
from src.config import USE_REMOTE_STORAGE

TZ_SP = ZoneInfo("America/Sao_Paulo")

log = logging.getLogger(__name__)


def write_snapshot(rows: list[dict], dataset: str, base_dir: Path) -> str:
    """Escreve um snapshot Parquet. Se USE_REMOTE_STORAGE, envia pro R2; senao grava local.
    Retorna a URI (path local ou r2://...) do arquivo."""
    if not rows:
        raise ValueError("nada pra escrever")

    df = pl.from_dicts(rows, infer_schema_length=None)
    today = datetime.now(TZ_SP).date().isoformat()
    ts = int(time.time())
    filename = f"snapshot-{ts}.parquet"

    tmp_dir = base_dir / dataset / f"date={today}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    local_path = tmp_dir / filename
    df.write_parquet(local_path, compression="zstd")

    try:
        from services.data_health import compute_and_save
        compute_and_save(df, dataset)
    except Exception as e:
        log.warning("data_health falhou (nao bloqueia write): %s", e)

    if USE_REMOTE_STORAGE:
        from storage.r2 import upload_file
        key = f"{dataset}/date={today}/{filename}"
        uri = upload_file(local_path, key)
        log.info("snapshot enviado: %s (%s linhas)", uri, len(df))
        return uri

    log.info("snapshot local: %s (%s linhas)", local_path, len(df))
    return str(local_path)
