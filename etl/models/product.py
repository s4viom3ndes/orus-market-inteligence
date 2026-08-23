from typing import List, Optional, Dict

class Product:
    def __init__(self, seller_id:str, sku:str, title:str, price:float, available_quantity:int, condition:str, listing_type_id:str, category_id:str, currency_id:str, status:str, metadata:Optional[Dict]=None):
        self.seller_id = seller_id
        self.sku = sku
        self.title = title
        self.price = price
        self.available_quantity = available_quantity
        self.condition = condition
        self.listing_type_id = listing_type_id
        self.category_id = category_id
        self.currency_id = currency_id
        self.status = status
        self.metadata = metadata or {}

    def to_dict(self) -> Dict:
        return {
            "seller_id": self.seller_id,
            "sku": self.sku,
            "title": self.title,
            "price": self.price,
            "available_quantity": self.available_quantity,
            "condition": self.condition,
            "listing_type_id": self.listing_type_id,
            "category_id": self.category_id,
            "currency_id": self.currency_id,
            "status": self.status,
            "metadata": self.metadata
        }


class Category:
    def __init__(self, category_id: str, name: str, parent_id: Optional[str] = None):
        self.category_id = category_id
        self.name = name
        self.parent_id = parent_id

    def to_dict(self) -> Dict:
        return {
            "category_id": self.category_id,
            "name": self.name,
            "parent_id": self.parent_id
        }


class Exposure:
    def __init__(self, exposure_id: str, name: str, home_page: str, priority_in_search: Optional[int] = None):
        self.exposure_id = exposure_id
        self.name = name
        self.home_page = home_page
        self.priority_in_search = priority_in_search


    def to_dict(self) -> Dict:
        return {
            "exposure_id": self.exposure_id,
            "name": self.name,
            "home_page": self.home_page,
            "priority_in_search": self.priority_in_search
        }