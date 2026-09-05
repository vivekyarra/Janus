from starlette.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.repositories.catalog import seed_catalog


def test_merchant_metrics_endpoint(db):
    seed_catalog(db)
    app.dependency_overrides[get_db] = lambda: db

    with TestClient(app) as client:
        res = client.get("/api/v1/products/metrics?merchant_id=merchant_demo")
        assert res.status_code == 200
        data = res.json()
        assert data["merchant_id"] == "merchant_demo"
        assert data["catalog_sku_count"] == 6
        assert data["machine_readability_score"] == 100.0
        assert data["p95_authorization_latency_ms"] is None or data["p95_authorization_latency_ms"] < 100.0
        assert "autonomous_gmv_paise" in data
        assert "conversion_rate_pct" in data
