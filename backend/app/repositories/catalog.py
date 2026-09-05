from sqlalchemy.orm import Session

from app.db.models import Product


DEMO_PRODUCTS = [
    {"id": "prod_a", "merchant_id": "merchant_demo", "name": "Sony Voyager NC", "price_paise": 1849900, "currency": "INR", "category": "headphones", "condition": "new", "active": True, "attributes": {"noise_cancelling": True, "weight_g": 254, "foldable": True, "travel_case": True, "color": "black", "branding": "minimal", "collection": "travel"}},
    {"id": "prod_b", "merchant_id": "merchant_demo", "name": "Sony Studio Pro", "price_paise": 2149900, "currency": "INR", "category": "headphones", "condition": "new", "active": True, "attributes": {"noise_cancelling": True, "color": "black"}},
    {"id": "prod_c", "merchant_id": "merchant_demo", "name": "Bose Home Max", "price_paise": 1799900, "currency": "INR", "category": "headphones", "condition": "new", "active": True, "attributes": {"noise_cancelling": True, "weight_g": 410, "foldable": False, "collection": "home"}},
    {"id": "prod_d", "merchant_id": "merchant_demo", "name": "Aurum Party XL", "price_paise": 699900, "currency": "INR", "category": "headphones", "condition": "new", "active": True, "attributes": {"color": "metallic gold", "branding": "oversized", "collection": "party", "flashy": True}},
    {"id": "prod_e", "merchant_id": "merchant_demo", "name": "Demo Essential", "price_paise": 749900, "currency": "INR", "category": "headphones", "condition": "new", "active": True, "attributes": {"noise_cancelling": True}},
]


def seed_catalog(db: Session) -> int:
    for values in DEMO_PRODUCTS:
        existing = db.get(Product, values["id"])
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
        else:
            db.add(Product(**values))
    db.commit()
    return len(DEMO_PRODUCTS)
