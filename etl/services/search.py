import logging
import time
from typing import Iterator
from services.ml_client import MLClient

log = logging.getLogger(__name__)

THROTTLE_SEC = 0.15


# Tipos de destaque que conseguimos resolver em ofertas.
#   PRODUCT      -> catalogo do ML; /products/{id} e /products/{id}/items funcionam
#   USER_PRODUCT -> pagina de produto do proprio vendedor (anuncio proprio).
#                   /products/MLBU.../items FUNCIONA, mas /products/MLBU... da 403.
#   ITEM         -> anuncio solto; /items/{id} e restrito (403), fica de fora.
#
# Ignorar USER_PRODUCT custava caro: na varredura de 12/09/2026 foram 759 entradas
# descartadas em 2.669 produtos resolvidos (28%), e em varias categorias o bestseller
# de posicao #1 e um USER_PRODUCT. Sellers que fogem do catalogo por diferenciacao
# vivem exatamente ai - eram invisiveis pro dataset inteiro.
RESOLVIVEIS = ("PRODUCT", "USER_PRODUCT")


def iter_highlights(category_id: str, site: str = "MLB", client: MLClient | None = None,
                    types: tuple[str, ...] = RESOLVIVEIS) -> Iterator[dict]:
    """Destaques (bestsellers) de uma categoria, como {"id": ..., "type": ...}."""
    owns = client is None
    if owns:
        client = MLClient()
    try:
        data = client.get(f"/highlights/{site}/category/{category_id}")
        for c in data.get("content") or []:
            if c.get("type") in types:
                yield {"id": c["id"], "type": c["type"]}
    finally:
        if owns:
            client.close()


def get_product_safe(product_id: str, product_type: str, client: MLClient) -> dict:
    """Metadados do produto, tolerando USER_PRODUCT.

    /products/{id} responde 403 para MLBU..., entao para anuncio proprio devolvemos
    um esqueleto com o id. Os campos de catalogo (nome, marca, dominio) ficam nulos -
    a oferta em si vem completa por /products/{id}/items.
    """
    if product_type == "USER_PRODUCT":
        return {"id": product_id}
    return get_product(product_id, client)


def get_product(product_id: str, client: MLClient) -> dict:
    return client.get(f"/products/{product_id}")


def iter_product_items(product_id: str, client: MLClient) -> Iterator[dict]:
    """Itera todas as ofertas (vendedores) por um produto de catalogo."""
    offset = 0
    while True:
        data = client.get(f"/products/{product_id}/items", limit=100, offset=offset)
        results = data.get("results", [])
        if not results:
            break
        for i, offer in enumerate(results):
            offer["_rank"] = offset + i
            yield offer
        total = (data.get("paging") or {}).get("total", 0)
        offset += len(results)
        if offset >= total:
            break
        time.sleep(THROTTLE_SEC)


def normalize_offer(
    product: dict,
    offer: dict,
    captured_at: int,
    watchlist_sellers: set[int] | None = None,
    category_id: str | None = None,
    visits_30d: int | None = None,
    reviews_count: int | None = None,
    reviews_avg: float | None = None,
    questions_count: int | None = None,
    seller_info: dict | None = None,
    product_type: str = "PRODUCT",
) -> dict:
    shipping = offer.get("shipping") or {}
    addr = offer.get("seller_address") or {}
    watch = watchlist_sellers or set()
    sinfo = seller_info or {}
    return {
        "captured_at": captured_at,
        "category_id": category_id,
        "catalog_product_id": product.get("id"),
        # PRODUCT = disputa buy box de catalogo; USER_PRODUCT = anuncio proprio, em
        # geral sem concorrente na pagina. Misturar os dois distorce qualquer
        # estatistica de buy box, entao a distincao precisa chegar ao parquet.
        "product_type": product_type,
        "product_name": product.get("name"),
        "domain_id": product.get("domain_id"),
        "family_name": product.get("family_name"),
        "brand": _attr(product, "BRAND"),
        "model": _attr(product, "MODEL"),
        "line": _attr(product, "LINE"),

        "rank": offer.get("_rank"),
        "is_buy_box_winner": offer.get("_rank") == 0,

        "item_id": offer.get("item_id"),
        "seller_id": offer.get("seller_id"),
        "is_watched_seller": offer.get("seller_id") in watch,
        "official_store_id": offer.get("official_store_id"),
        "price": offer.get("price"),
        "original_price": offer.get("original_price"),
        "currency_id": offer.get("currency_id"),
        "condition": offer.get("condition"),
        "listing_type_id": offer.get("listing_type_id"),
        "tier": offer.get("tier"),
        "warranty": offer.get("warranty"),
        "tags": ",".join(offer.get("tags") or []),

        "shipping_free": shipping.get("free_shipping"),
        "shipping_mode": shipping.get("mode"),
        "shipping_logistic_type": shipping.get("logistic_type"),
        "shipping_cost": shipping.get("cost"),

        "state": (addr.get("state") or {}).get("name"),
        "city": (addr.get("city") or {}).get("name"),

        "visits_30d": visits_30d,
        "reviews_count": reviews_count,
        "reviews_avg_rating": reviews_avg,
        "questions_count": questions_count,

        "seller_nickname": sinfo.get("nickname"),
        "seller_reputation_level": sinfo.get("reputation_level"),
        "seller_power_status": sinfo.get("power_status"),
        "seller_tx_total": sinfo.get("tx_total"),
        "seller_ratings_negative": sinfo.get("ratings_negative"),
    }


def _attr(product: dict, attr_id: str) -> str | None:
    for a in product.get("attributes") or []:
        if a.get("id") == attr_id:
            return a.get("value_name")
    return None
