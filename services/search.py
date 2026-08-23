import logging
import time
from typing import Iterator
from services.ml_client import MLClient

log = logging.getLogger(__name__)

THROTTLE_SEC = 0.15


def iter_highlights(category_id: str, site: str = "MLB", client: MLClient | None = None) -> Iterator[str]:
    """Retorna IDs de produtos destaque (bestsellers) de uma categoria."""
    owns = client is None
    if owns:
        client = MLClient()
    try:
        data = client.get(f"/highlights/{site}/category/{category_id}")
        for c in data.get("content") or []:
            if c.get("type") == "PRODUCT":
                yield c["id"]
    finally:
        if owns:
            client.close()


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
) -> dict:
    shipping = offer.get("shipping") or {}
    addr = offer.get("seller_address") or {}
    watch = watchlist_sellers or set()
    return {
        "captured_at": captured_at,
        "category_id": category_id,
        "catalog_product_id": product.get("id"),
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
    }


def _attr(product: dict, attr_id: str) -> str | None:
    for a in product.get("attributes") or []:
        if a.get("id") == attr_id:
            return a.get("value_name")
    return None
