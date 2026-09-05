import pytest
from pydantic import ValidationError

from app.db.models import AuditEvent, Product
from app.domain.models import CatalogProductInput
from app.repositories.catalog import CatalogOwnershipConflict, import_catalog


def product(**changes) -> CatalogProductInput:
    values = {
        "id": "sku-transit-anc",
        "merchant_id": "northstar_audio",
        "name": "Transit ANC",
        "price_paise": 1_849_900,
        "currency": "INR",
        "category": "headphones",
        "condition": "new",
        "active": True,
        "attributes": {"color": "black", "branding": "minimal"},
    }
    values.update(changes)
    return CatalogProductInput.model_validate(values)


def test_catalog_import_is_atomic_idempotent_and_audited(db) -> None:
    first = import_catalog(db, [product()], source="test_fixture")
    second = import_catalog(db, [product()], source="test_fixture")
    assert (first.created, first.updated, first.unchanged) == (1, 0, 0)
    assert (second.created, second.updated, second.unchanged) == (0, 0, 1)
    assert db.get(Product, "sku-transit-anc").price_paise == 1_849_900
    assert db.query(AuditEvent).filter(AuditEvent.event_type == "CATALOG_IMPORT_COMPLETED").count() == 2


def test_catalog_import_updates_authoritative_price(db) -> None:
    import_catalog(db, [product()], source="first")
    result = import_catalog(db, [product(price_paise=1_899_900)], source="second")
    assert result.updated == 1
    assert db.get(Product, "sku-transit-anc").price_paise == 1_899_900


def test_catalog_import_rejects_cross_merchant_takeover(db) -> None:
    import_catalog(db, [product()], source="first")
    with pytest.raises(CatalogOwnershipConflict):
        import_catalog(db, [product(merchant_id="attacker_store")], source="attack")
    assert db.get(Product, "sku-transit-anc").merchant_id == "northstar_audio"


def test_catalog_schema_rejects_floating_money_and_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        product(price_paise=18499.50, buyer_claimed_category="travel")
