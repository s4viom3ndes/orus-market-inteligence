"""Testes de normalize_offer."""
from services.search import normalize_offer


def test_normalize_offer_campos_basicos():
    product = {
        "id": "MLB123", "name": "Produto X", "domain_id": "MLB-FOO",
        "family_name": "Fam", "attributes": [
            {"id": "BRAND", "value_name": "Marca X"},
            {"id": "MODEL", "value_name": "Modelo Y"},
        ],
    }
    offer = {
        "_rank": 0, "item_id": "MLBA1", "seller_id": 500, "price": 99.9,
        "currency_id": "BRL", "condition": "new", "listing_type_id": "gold_pro",
        "shipping": {"free_shipping": True, "mode": "me2", "logistic_type": "fulfillment", "cost": 0},
        "seller_address": {"state": {"name": "SP"}, "city": {"name": "Sao Paulo"}},
        "tags": ["kvs_primary", "immediate_payment"], "warranty": "12 meses",
    }
    row = normalize_offer(product, offer, captured_at=1000)
    assert row["catalog_product_id"] == "MLB123"
    assert row["product_name"] == "Produto X"
    assert row["item_id"] == "MLBA1"
    assert row["seller_id"] == 500
    assert row["price"] == 99.9
    assert row["is_buy_box_winner"] is True
    assert row["rank"] == 0
    assert row["brand"] == "Marca X"
    assert row["model"] == "Modelo Y"
    assert row["shipping_free"] is True
    assert row["shipping_logistic_type"] == "fulfillment"
    assert row["state"] == "SP"
    assert row["tags"] == "kvs_primary,immediate_payment"


def test_normalize_offer_watchlist_seller_flag():
    product = {"id": "MLB1", "name": "P", "domain_id": None,
               "family_name": None, "attributes": []}
    offer = {"_rank": 1, "item_id": "A", "seller_id": 999, "price": 10,
             "currency_id": "BRL", "condition": "new", "listing_type_id": "gold",
             "shipping": {}, "seller_address": {}, "tags": []}
    row = normalize_offer(product, offer, 1, watchlist_sellers={999})
    assert row["is_watched_seller"] is True

    row2 = normalize_offer(product, offer, 1, watchlist_sellers={888})
    assert row2["is_watched_seller"] is False


def test_normalize_offer_enrichment_pass_through():
    product = {"id": "MLB1", "name": "P", "domain_id": None,
               "family_name": None, "attributes": []}
    offer = {"_rank": 0, "item_id": "A", "seller_id": 1, "price": 1,
             "currency_id": "BRL", "condition": "new", "listing_type_id": "gold",
             "shipping": {}, "seller_address": {}, "tags": []}
    row = normalize_offer(product, offer, 1,
                          visits_30d=1000, reviews_count=50,
                          reviews_avg=4.5, questions_count=3)
    assert row["visits_30d"] == 1000
    assert row["reviews_count"] == 50
    assert row["reviews_avg_rating"] == 4.5
    assert row["questions_count"] == 3
