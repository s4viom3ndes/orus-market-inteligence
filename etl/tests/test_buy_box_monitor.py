"""Testes de evaluate_sku (pura, sem live fetch)."""
import polars as pl
import pytest
from services.buy_box_monitor import evaluate_sku


@pytest.fixture
def snapshot():
    return pl.DataFrame([
        {"catalog_product_id": "MLB123", "product_name": "P", "seller_id": 1,
         "price": 100.0, "rank": 0, "shipping_logistic_type": "fulfillment"},
        {"catalog_product_id": "MLB123", "product_name": "P", "seller_id": 2,
         "price": 110.0, "rank": 1, "shipping_logistic_type": "drop_off"},
        {"catalog_product_id": "MLB123", "product_name": "P", "seller_id": 3,
         "price": 150.0, "rank": 2, "shipping_logistic_type": "drop_off"},
    ])


def test_status_winning_quando_meu_preco_abaixo_do_winner(snapshot):
    sku = {"sku": "S1", "catalog_product_id": "MLB123", "category_id": "MLB999",
           "current_price": 95.0, "min_price": 50.0, "target_position": 0}
    r = evaluate_sku(sku, snapshot)
    assert r["status"] == "winning"
    assert r["winner_price"] == 100.0


def test_status_losing_recoverable_se_min_permite(snapshot):
    sku = {"sku": "S1", "catalog_product_id": "MLB123", "category_id": "MLB999",
           "current_price": 120.0, "min_price": 50.0, "target_position": 0}
    r = evaluate_sku(sku, snapshot)
    assert r["status"] == "losing_recoverable"
    assert "baixar preco" in r["recommendation"].lower()


def test_status_losing_locked_se_min_acima_do_winner(snapshot):
    sku = {"sku": "S1", "catalog_product_id": "MLB123", "category_id": "MLB999",
           "current_price": 120.0, "min_price": 105.0, "target_position": 0}
    r = evaluate_sku(sku, snapshot)
    assert r["status"] == "losing_locked"


def test_status_no_data_sem_ofertas():
    empty = pl.DataFrame({"catalog_product_id": [], "price": [], "rank": [],
                          "shipping_logistic_type": []},
                         schema={"catalog_product_id": pl.String, "price": pl.Float64,
                                 "rank": pl.Int64, "shipping_logistic_type": pl.String})
    sku = {"sku": "S1", "catalog_product_id": "MLB123", "category_id": "MLB999",
           "current_price": 100.0, "min_price": 50.0, "target_position": 0}
    r = evaluate_sku(sku, empty)
    assert r["status"] == "no_data"


def test_gap_calculado_corretamente(snapshot):
    sku = {"sku": "S1", "catalog_product_id": "MLB123", "category_id": "MLB999",
           "current_price": 120.0, "min_price": 50.0, "target_position": 0}
    r = evaluate_sku(sku, snapshot)
    assert r["gap_to_winner"] == 20.0
