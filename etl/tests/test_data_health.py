"""Testes de compute de data_health."""
import polars as pl
from services.data_health import compute


def test_status_green_com_dados_ok():
    df = pl.DataFrame({
        "catalog_product_id": ["a"] * 600,
        "seller_id": list(range(600)),
        "price": [10.0] * 600,
    })
    h = compute(df, "market_offers")
    assert h["status"] == "green"
    assert h["row_count"] == 600
    assert h["warnings"] == []


def test_status_yellow_row_count_abaixo_do_esperado():
    df = pl.DataFrame({
        "catalog_product_id": ["a"] * 300,  # < 500 mas > 250
        "seller_id": list(range(300)),
        "price": [10.0] * 300,
    })
    h = compute(df, "market_offers")
    assert h["status"] == "yellow"
    assert any("row_count" in w for w in h["warnings"])


def test_status_red_row_count_muito_baixo():
    df = pl.DataFrame({
        "catalog_product_id": ["a"] * 100,  # < 250 (metade do min 500)
        "seller_id": list(range(100)),
        "price": [10.0] * 100,
    })
    h = compute(df, "market_offers")
    assert h["status"] == "red"


def test_status_red_com_coluna_critica_nula():
    """catalog_product_id > 10% null vira red."""
    df = pl.DataFrame({
        "catalog_product_id": [None] * 400 + ["x"] * 200,
        "seller_id": list(range(600)),
        "price": [10.0] * 600,
    })
    h = compute(df, "market_offers")
    assert h["status"] == "red"
    assert any("catalog_product_id" in w for w in h["warnings"])


def test_null_rates_calculados():
    df = pl.DataFrame({
        "col_a": [1, 2, 3, 4, None],
        "col_b": [1, 2, 3, 4, 5],
    })
    h = compute(df, "custom")
    assert h["null_rates"]["col_a"] == 0.2
    assert h["null_rates"]["col_b"] == 0.0


def test_numeric_stats_para_colunas_numericas():
    df = pl.DataFrame({"price": [10.0, 20.0, 30.0]})
    h = compute(df, "custom")
    assert h["numeric_stats"]["price"]["min"] == 10.0
    assert h["numeric_stats"]["price"]["max"] == 30.0
    assert h["numeric_stats"]["price"]["median"] == 20.0
    assert h["numeric_stats"]["price"]["mean"] == 20.0
