"""Extrai o desempenho dos SKUs do cliente no snapshot de mercado.

Duas fontes possiveis:
- REAL: linhas onde seller_id ∈ WATCHLIST_SELLERS (quando cliente autoriza via OAuth)
- MOCK: SKUs configurados em mock_client.yaml (demo / pre-onboarding)

Produz 1 linha por SKU por dia com winner, gap, posicao — pra plotar time-series
na dashboard.
"""
import time
import polars as pl
from src.config import WATCHLIST_SELLERS


COMMON_SCHEMA = [
    "captured_date", "captured_at", "source",
    "sku", "catalog_product_id", "product_name", "category_id",
    "current_price", "our_position", "is_buy_box_winner",
    "winner_price", "winner_seller_id", "winner_shipping",
    "n_competitors", "gap_to_winner", "status",
]


def build_client_snapshot(snap: pl.DataFrame, captured_date: str) -> pl.DataFrame:
    """Extrai linhas onde o cliente esta como seller (fonte REAL, precisa OAuth)."""
    watch = set(WATCHLIST_SELLERS)
    if snap.is_empty() or not watch:
        return pl.DataFrame()

    ours = snap.filter(pl.col("seller_id").is_in(watch))
    if ours.is_empty():
        return pl.DataFrame()

    winners = (
        snap.filter(pl.col("rank") == 0)
        .select(
            pl.col("catalog_product_id"),
            pl.col("price").alias("winner_price"),
            pl.col("seller_id").alias("winner_seller_id"),
            pl.col("shipping_logistic_type").alias("winner_shipping"),
        )
    )

    counts = snap.group_by("catalog_product_id").len().rename({"len": "n_competitors"})

    return (
        ours.join(winners, on="catalog_product_id", how="left")
        .join(counts, on="catalog_product_id", how="left")
        .with_columns(
            [
                pl.lit(captured_date).alias("captured_date"),
                pl.lit("real").alias("source"),
                pl.col("item_id").alias("sku"),
                pl.col("price").alias("current_price"),
                pl.col("rank").alias("our_position"),
                (pl.col("price") - pl.col("winner_price")).round(2).alias("gap_to_winner"),
                pl.when(pl.col("is_buy_box_winner"))
                .then(pl.lit("winning"))
                .otherwise(pl.lit("losing"))
                .alias("status"),
            ]
        )
        .select(COMMON_SCHEMA)
    )


def build_mock_snapshot(snap: pl.DataFrame, mock_cfg: dict, captured_date: str) -> pl.DataFrame:
    """Extrai desempenho de SKUs do mock_client.yaml no snapshot.

    Pra cada SKU do mock, olha o catalog_product_id no snapshot e calcula
    posicao/gap SE o cliente estivesse listado com `current_price`. Isso permite
    demonstrar time-series real (winner e concorrentes vem do snapshot; a
    posicao do cliente e uma projecao do preco configurado).
    """
    if snap.is_empty() or not mock_cfg.get("skus"):
        return pl.DataFrame()

    ts = int(time.time())
    rows: list[dict] = []

    for sku in mock_cfg["skus"]:
        pid = sku["catalog_product_id"]
        offers = snap.filter(pl.col("catalog_product_id") == pid).sort("rank")
        if offers.is_empty():
            continue

        first = offers.row(0, named=True)
        prices = offers["price"].to_list()
        my_price = float(sku["current_price"])
        our_pos = sum(1 for p in prices if p < my_price)
        gap = round(my_price - float(first["price"]), 2)
        is_winner = our_pos <= int(sku.get("target_position", 0))

        rows.append({
            "captured_date": captured_date,
            "captured_at": ts,
            "source": "mock",
            "sku": sku["sku"],
            "catalog_product_id": pid,
            "product_name": first["product_name"],
            "category_id": sku.get("category_id"),
            "current_price": my_price,
            "our_position": our_pos,
            "is_buy_box_winner": is_winner,
            "winner_price": float(first["price"]),
            "winner_seller_id": int(first["seller_id"]),
            "winner_shipping": first.get("shipping_logistic_type"),
            "n_competitors": offers.height,
            "gap_to_winner": gap,
            "status": "winning" if is_winner else "losing",
        })

    if not rows:
        return pl.DataFrame()
    return pl.from_dicts(rows, infer_schema_length=None).select(COMMON_SCHEMA)
