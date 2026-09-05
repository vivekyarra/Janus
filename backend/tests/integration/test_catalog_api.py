from fastapi.testclient import TestClient

from app.db.models import Product
from app.db.session import get_db
from app.main import app


def test_authenticated_catalog_import_contract_and_filtering(db) -> None:
    app.dependency_overrides[get_db] = lambda: db
    payload = {"merchant_id": "northstar_audio", "products": [{"id": "sku-transit", "merchant_id": "northstar_audio", "name": "Transit ANC", "price_paise": 1849900, "currency": "INR", "category": "headphones", "condition": "new", "active": True, "attributes": {"travel_case": True}}]}
    try:
        with TestClient(app) as client:
            imported = client.post("/api/v1/products/import", json=payload)
            assert imported.status_code == 200
            assert imported.json() == {"merchant_id": "northstar_audio", "created": 1, "updated": 0, "unchanged": 0, "total": 1}
            assert client.get("/api/v1/products", params={"merchant_id": "other"}).json() == []
            catalog = client.get("/api/v1/products", params={"merchant_id": "northstar_audio"}).json()
            assert catalog[0]["price_paise"] == 1849900
            assert db.get(Product, "sku-transit").attributes == {"travel_case": True}
    finally:
        app.dependency_overrides.clear()


def test_catalog_import_rejects_merchant_mismatch(db) -> None:
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/products/import", json={"merchant_id": "northstar_audio", "products": [{"id": "sku-bad", "merchant_id": "another_store", "name": "Bad", "price_paise": 100, "currency": "INR", "category": "test", "attributes": {}}]})
            assert response.status_code == 422
            assert response.json()["detail"]["reason_code"] == "CATALOG_MERCHANT_MISMATCH"
    finally:
        app.dependency_overrides.clear()
