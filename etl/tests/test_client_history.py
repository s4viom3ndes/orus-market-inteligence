"""Testes de build_client_snapshot (REAL) e build_mock_snapshot (MOCK)."""
from unittest.mock import patch
import polars as pl
import pytest

from services.client_history import build_client_snapshot, build_mock_snapshot


def _make_snapshot(rows):
    return pl.DataFrame(rows)


@pytest.fixture
def snap_com_cliente():
    """Cliente (seller=42) tem 2 ofertas: perde 1 e ganha 1 buy box."""
    return _make_snapshot([
        # produto A: cliente ganha
        {"catalog_product_id": "MLB-A", "product_name": "Prod A", "category_id": "MLB1",
         "captured_at": 1000, "item_id": "I1", "seller_id": 42, "price": 99.0,
         "rank": 0, "is_buy_box_winner": True, "shipping_logistic_type": "fulfillment"},
        {"catalog_product_id": "MLB-A", "product_name": "Prod A", "category_id": "MLB1",
         "captured_at": 1000, "item_id": "I2", "seller_id": 999, "price": 105.0,
         "rank": 1, "is_buy_box_winner": False, "shipping_logistic_type": "cross_docking"},
        # produto B: cliente perde para outro
        {"catalog_product_id": "MLB-B", "product_name": "Prod B", "category_id": "MLB2",
         "captured_at": 1000, "item_id": "I3", "seller_id": 888, "price": 50.0,
         "rank": 0, "is_buy_box_winner": True, "shipping_logistic_type": "drop_off"},
        {"catalog_product_id": "MLB-B", "product_name": "Prod B", "category_id": "MLB2",
         "captured_at": 1000, "item_id": "I4", "seller_id": 42, "price": 60.0,
         "rank": 1, "is_buy_box_winner": False, "shipping_logistic_type": "fulfillment"},
    ])


def test_extrai_apenas_linhas_do_cliente(snap_com_cliente):
    with patch("services.client_history.WATCHLIST_SELLERS", [42]):
        r = build_client_snapshot(snap_com_cliente, "2026-08-27")
    assert r.height == 2
    assert set(r["catalog_product_id"].to_list()) == {"MLB-A", "MLB-B"}
    assert all(s == "real" for s in r["source"].to_list())


def test_enrichment_com_winner_e_gap(snap_com_cliente):
    with patch("services.client_history.WATCHLIST_SELLERS", [42]):
        r = build_client_snapshot(snap_com_cliente, "2026-08-27")

    prod_a = r.filter(pl.col("catalog_product_id") == "MLB-A").row(0, named=True)
    assert prod_a["winner_price"] == 99.0
    assert prod_a["winner_seller_id"] == 42
    assert prod_a["gap_to_winner"] == 0.0
    assert prod_a["is_buy_box_winner"] is True
    assert prod_a["n_competitors"] == 2

    prod_b = r.filter(pl.col("catalog_product_id") == "MLB-B").row(0, named=True)
    assert prod_b["winner_price"] == 50.0
    assert prod_b["winner_seller_id"] == 888
    assert prod_b["gap_to_winner"] == 10.0
    assert prod_b["is_buy_box_winner"] is False


def test_captured_date_e_setado(snap_com_cliente):
    with patch("services.client_history.WATCHLIST_SELLERS", [42]):
        r = build_client_snapshot(snap_com_cliente, "2026-08-27")
    assert all(d == "2026-08-27" for d in r["captured_date"].to_list())


def test_snapshot_vazio_retorna_vazio():
    empty = pl.DataFrame()
    r = build_client_snapshot(empty, "2026-08-27")
    assert r.is_empty()


def test_cliente_sem_ofertas_retorna_vazio(snap_com_cliente):
    with patch("services.client_history.WATCHLIST_SELLERS", [12345]):
        r = build_client_snapshot(snap_com_cliente, "2026-08-27")
    assert r.is_empty()


def test_watchlist_vazia_retorna_vazio(snap_com_cliente):
    with patch("services.client_history.WATCHLIST_SELLERS", []):
        r = build_client_snapshot(snap_com_cliente, "2026-08-27")
    assert r.is_empty()


# ---- build_mock_snapshot ----

def test_mock_snapshot_calcula_posicao_e_gap(snap_com_cliente):
    """Mock SKU com current_price=95 → ganharia buy box no produto A (winner=99)."""
    mock_cfg = {"skus": [
        {"sku": "SKU-A", "catalog_product_id": "MLB-A", "category_id": "MLB1",
         "current_price": 95.0, "target_position": 0},
    ]}
    r = build_mock_snapshot(snap_com_cliente, mock_cfg, "2026-08-27")
    assert r.height == 1
    row = r.row(0, named=True)
    assert row["source"] == "mock"
    assert row["sku"] == "SKU-A"
    assert row["winner_price"] == 99.0
    assert row["our_position"] == 0
    assert row["is_buy_box_winner"] is True
    assert row["gap_to_winner"] == -4.0
    assert row["status"] == "winning"


def test_mock_snapshot_losing_status(snap_com_cliente):
    """Mock SKU com current_price=110 no produto B (winner=50) → perde."""
    mock_cfg = {"skus": [
        {"sku": "SKU-B", "catalog_product_id": "MLB-B", "category_id": "MLB2",
         "current_price": 110.0, "target_position": 0},
    ]}
    r = build_mock_snapshot(snap_com_cliente, mock_cfg, "2026-08-27")
    row = r.row(0, named=True)
    assert row["is_buy_box_winner"] is False
    assert row["status"] == "losing"
    assert row["gap_to_winner"] == 60.0
    assert row["our_position"] == 2  # atras dos 2 competidores


def test_mock_snapshot_pula_sku_sem_ofertas():
    """Se catalog_product_id nao tem ofertas, pula (nao quebra)."""
    empty_snap = pl.DataFrame(schema={
        "catalog_product_id": pl.String, "product_name": pl.String,
        "price": pl.Float64, "rank": pl.Int64, "seller_id": pl.Int64,
        "is_buy_box_winner": pl.Boolean, "shipping_logistic_type": pl.String,
    })
    mock_cfg = {"skus": [
        {"sku": "X", "catalog_product_id": "MLB-X", "category_id": "C",
         "current_price": 50.0, "target_position": 0}
    ]}
    r = build_mock_snapshot(empty_snap, mock_cfg, "2026-08-27")
    assert r.is_empty()


def test_mock_snapshot_sem_skus_no_config(snap_com_cliente):
    r = build_mock_snapshot(snap_com_cliente, {"skus": []}, "2026-08-27")
    assert r.is_empty()
