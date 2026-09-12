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


def test_normalize_offer_seller_info_pass_through():
    product = {"id": "MLB1", "name": "P", "domain_id": None,
               "family_name": None, "attributes": []}
    offer = {"_rank": 0, "item_id": "A", "seller_id": 42, "price": 1,
             "currency_id": "BRL", "condition": "new", "listing_type_id": "gold",
             "shipping": {}, "seller_address": {}, "tags": []}
    sinfo = {
        "nickname": "MEGA_STORE", "reputation_level": "5_green",
        "power_status": "platinum", "tx_total": 12500, "ratings_negative": 0.01,
    }
    row = normalize_offer(product, offer, 1, seller_info=sinfo)
    assert row["seller_nickname"] == "MEGA_STORE"
    assert row["seller_reputation_level"] == "5_green"
    assert row["seller_power_status"] == "platinum"
    assert row["seller_tx_total"] == 12500
    assert row["seller_ratings_negative"] == 0.01


def test_normalize_offer_sem_seller_info_deixa_nulls():
    product = {"id": "MLB1", "name": "P", "domain_id": None,
               "family_name": None, "attributes": []}
    offer = {"_rank": 0, "item_id": "A", "seller_id": 1, "price": 1,
             "currency_id": "BRL", "condition": "new", "listing_type_id": "gold",
             "shipping": {}, "seller_address": {}, "tags": []}
    row = normalize_offer(product, offer, 1)
    assert row["seller_nickname"] is None
    assert row["seller_reputation_level"] is None
    assert row["seller_power_status"] is None
    assert row["seller_tx_total"] is None
    assert row["seller_ratings_negative"] is None


# --- destaques: PRODUCT e USER_PRODUCT ---

class _FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.gets = []

    def get(self, path, **kw):
        self.gets.append(path)
        return self.payload

    def close(self):
        pass


_DESTAQUES = {"content": [
    {"id": "MLBU111", "position": 1, "type": "USER_PRODUCT"},
    {"id": "MLB222", "position": 2, "type": "PRODUCT"},
    {"id": "MLB333", "position": 3, "type": "ITEM"},
]}


def test_iter_highlights_inclui_anuncio_proprio():
    """Regressao: so PRODUCT descartava 28% dos bestsellers, incluindo posicao #1."""
    from services.search import iter_highlights
    r = list(iter_highlights("MLB1", client=_FakeClient(_DESTAQUES)))
    assert [x["id"] for x in r] == ["MLBU111", "MLB222"]
    assert r[0]["type"] == "USER_PRODUCT"


def test_iter_highlights_exclui_item():
    """ITEM fica de fora porque /items/{id} responde 403."""
    from services.search import iter_highlights
    r = list(iter_highlights("MLB1", client=_FakeClient(_DESTAQUES)))
    assert "MLB333" not in [x["id"] for x in r]


def test_iter_highlights_aceita_filtro_de_tipo():
    from services.search import iter_highlights
    r = list(iter_highlights("MLB1", client=_FakeClient(_DESTAQUES), types=("PRODUCT",)))
    assert [x["id"] for x in r] == ["MLB222"]


def test_get_product_safe_nao_chama_api_para_anuncio_proprio():
    """/products/MLBU... responde 403 - nem tentar."""
    from services.search import get_product_safe
    c = _FakeClient({"id": "nao deveria ser usado"})
    assert get_product_safe("MLBU111", "USER_PRODUCT", c) == {"id": "MLBU111"}
    assert c.gets == []


def test_get_product_safe_busca_catalogo_normalmente():
    from services.search import get_product_safe
    c = _FakeClient({"id": "MLB222", "name": "Produto"})
    assert get_product_safe("MLB222", "PRODUCT", c)["name"] == "Produto"
    assert c.gets == ["/products/MLB222"]


def test_normalize_offer_marca_o_tipo_de_produto():
    """Sem essa coluna, anuncio proprio (sem concorrencia) distorce a estatistica
    de buy box quando misturado com catalogo."""
    product = {"id": "MLBU111"}
    offer = {"_rank": 0, "item_id": "MLBX", "seller_id": 1, "price": 78.9}
    row = normalize_offer(product, offer, 1, product_type="USER_PRODUCT")
    assert row["product_type"] == "USER_PRODUCT"
    assert row["is_buy_box_winner"] is True
    assert normalize_offer(product, offer, 1)["product_type"] == "PRODUCT"
