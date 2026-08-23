from typing import Optional
from pydantic import BaseModel


class MyListing(BaseModel):
    """Anuncio proprio do seller que o Orus monitora."""
    item_id: str
    ml_user_id: int
    sku: Optional[str] = None
    title: str
    catalog_product_id: Optional[str] = None
    price: float
    currency_id: str = "BRL"
    status: str
    listing_type_id: Optional[str] = None
    condition: Optional[str] = None
    permalink: Optional[str] = None

    min_price: Optional[float] = None
    max_price: Optional[float] = None
    target_margin: Optional[float] = None


class OfferSnapshot(BaseModel):
    """Uma oferta de um vendedor concorrendo em um catalog product."""
    captured_at: int
    catalog_product_id: str
    item_id: str
    seller_id: int
    price: float
    currency_id: str
    condition: str
    listing_type_id: Optional[str]
    shipping_free: bool
    shipping_logistic_type: Optional[str]
    rank: int
    is_buy_box_winner: bool


class BuyBoxEvent(BaseModel):
    """Mudanca de estado do buy box detectada."""
    captured_at: int
    catalog_product_id: str
    my_item_id: str
    event: str
    my_price: float
    winner_price: float
    winner_seller_id: int
