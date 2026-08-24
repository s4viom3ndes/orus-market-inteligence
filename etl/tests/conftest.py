"""Fixtures compartilhadas entre tests."""
import polars as pl
import pytest


@pytest.fixture
def offers_df():
    """DataFrame minimo de ofertas (o que collect_market produz)."""
    return pl.DataFrame([
        {
            "catalog_product_id": "MLB123", "product_name": "Produto Teste",
            "item_id": "MLBX1", "seller_id": 100, "price": 100.0, "rank": 0,
            "shipping_logistic_type": "fulfillment", "shipping_free": True,
            "condition": "new", "listing_type_id": "gold_pro",
            "is_buy_box_winner": True, "category_id": "MLB999",
        },
        {
            "catalog_product_id": "MLB123", "product_name": "Produto Teste",
            "item_id": "MLBX2", "seller_id": 200, "price": 110.0, "rank": 1,
            "shipping_logistic_type": "cross_docking", "shipping_free": True,
            "condition": "new", "listing_type_id": "gold_pro",
            "is_buy_box_winner": False, "category_id": "MLB999",
        },
        {
            "catalog_product_id": "MLB123", "product_name": "Produto Teste",
            "item_id": "MLBX3", "seller_id": 300, "price": 130.0, "rank": 2,
            "shipping_logistic_type": "drop_off", "shipping_free": False,
            "condition": "new", "listing_type_id": "gold",
            "is_buy_box_winner": False, "category_id": "MLB999",
        },
    ])


@pytest.fixture
def sku_cfg_beat():
    return {
        "sku": "SKU-1",
        "catalog_product_id": "MLB123",
        "category_id": "MLB999",
        "current_price": 110.0,  # dentro do 15% delta pra winner=100
        "min_price": 80.0,
        "max_price": 200.0,
        "target_position": 0,
        "strategy": "beat_winner",
        "beat_delta": 0.01,
    }


@pytest.fixture
def defaults():
    return {
        "strategy": "beat_winner",
        "beat_delta": 0.01,
        "max_price_pct_over_current": 0.2,
        "max_change_pct_per_run": 0.15,
    }
