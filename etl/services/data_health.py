"""Data observability - health por dataset.

Computa metricas de saude sobre um DataFrame:
  - volume, unicidade, completude, distribuicao numerica
  - status green/yellow/red baseado em thresholds

Persiste em R2 (state/data_health/<dataset>_latest.json + history).
"""
import json
import logging
import time
from typing import Any
import polars as pl
from src.config import USE_REMOTE_STORAGE

log = logging.getLogger(__name__)

DEFAULT_MIN_ROWS = {
    "market_offers": 500,
    "trends": 20,
    "reprice_suggestions": 1,
}

CRITICAL_NULL_COLS = {
    "market_offers": ["catalog_product_id", "seller_id", "price"],
    "trends": ["keyword"],
    "reprice_suggestions": ["sku", "status"],
}


def compute(df: pl.DataFrame, dataset: str) -> dict:
    """Snapshot de saude do parquet."""
    now = int(time.time())
    n = df.height
    warnings: list[str] = []

    null_rates: dict[str, float] = {}
    for col in df.columns:
        try:
            nulls = df[col].null_count()
            null_rates[col] = round(nulls / n, 4) if n else 0.0
        except Exception:
            null_rates[col] = -1.0

    unique_counts: dict[str, int] = {}
    numeric_stats: dict[str, dict[str, float]] = {}
    for col in df.columns:
        dtype = df.schema[col]
        if dtype in (pl.Int64, pl.Int32, pl.Float64, pl.Float32):
            try:
                s = df[col].drop_nulls()
                if s.len() > 0:
                    numeric_stats[col] = {
                        "min": float(s.min()),
                        "max": float(s.max()),
                        "median": float(s.median()),
                        "mean": round(float(s.mean()), 4),
                    }
            except Exception:
                pass
        if dtype == pl.String or dtype == pl.Int64:
            try:
                unique_counts[col] = df[col].n_unique()
            except Exception:
                pass

    status = "green"
    min_rows = DEFAULT_MIN_ROWS.get(dataset, 1)
    if n < min_rows * 0.5:
        status = "red"
        warnings.append(f"row_count {n} muito baixo (esperado >= {min_rows})")
    elif n < min_rows:
        status = "yellow"
        warnings.append(f"row_count {n} abaixo do esperado ({min_rows})")

    for col in CRITICAL_NULL_COLS.get(dataset, []):
        if col in null_rates and null_rates[col] > 0.1:
            status = "red"
            warnings.append(f"coluna critica '{col}' com {null_rates[col]*100:.1f}% de nulos")

    return {
        "dataset": dataset,
        "computed_at": now,
        "computed_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "status": status,
        "warnings": warnings,
        "row_count": n,
        "column_count": df.width,
        "null_rates": null_rates,
        "unique_counts": unique_counts,
        "numeric_stats": numeric_stats,
    }


def save(health: dict) -> None:
    if not USE_REMOTE_STORAGE:
        return
    from storage.r2 import upload_bytes
    payload = json.dumps(health, indent=2, ensure_ascii=False, default=str).encode("utf-8")
    dataset = health["dataset"]
    try:
        upload_bytes(payload, f"state/data_health/{dataset}_latest.json", content_type="application/json")
        upload_bytes(payload, f"state/data_health/history/{dataset}_{health['computed_at']}.json",
                     content_type="application/json")
    except Exception as e:
        log.warning("nao consegui salvar data_health: %s", e)


def compute_and_save(df: pl.DataFrame, dataset: str) -> dict:
    h = compute(df, dataset)
    save(h)
    log.info("data_health[%s]: status=%s rows=%s warnings=%s",
             dataset, h["status"], h["row_count"], len(h["warnings"]))
    return h


def load_latest(dataset: str) -> dict | None:
    if not USE_REMOTE_STORAGE:
        return None
    from storage.r2 import download_bytes
    raw = download_bytes(f"state/data_health/{dataset}_latest.json")
    return json.loads(raw) if raw else None
