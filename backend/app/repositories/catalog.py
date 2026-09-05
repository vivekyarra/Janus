from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import Product
from app.domain.models import CatalogProductInput
from app.services.audit_service import write_audit


DEMO_PRODUCTS = [
    {"id": "prod_a", "merchant_id": "merchant_demo", "name": "Sony Voyager NC", "price_paise": 1849900, "currency": "INR", "category": "headphones", "condition": "new", "active": True, "attributes": {"noise_cancelling": True, "weight_g": 254, "foldable": True, "travel_case": True, "color": "black", "branding": "minimal", "collection": "travel"}},
    {"id": "prod_b", "merchant_id": "merchant_demo", "name": "Sony Studio Pro", "price_paise": 2149900, "currency": "INR", "category": "headphones", "condition": "new", "active": True, "attributes": {"noise_cancelling": True, "color": "black"}},
    {"id": "prod_c", "merchant_id": "merchant_demo", "name": "Bose Home Max", "price_paise": 1799900, "currency": "INR", "category": "headphones", "condition": "new", "active": True, "attributes": {"noise_cancelling": True, "weight_g": 410, "foldable": False, "collection": "home"}},
    {"id": "prod_d", "merchant_id": "merchant_demo", "name": "Aurum Party XL", "price_paise": 699900, "currency": "INR", "category": "headphones", "condition": "new", "active": True, "attributes": {"color": "metallic gold", "branding": "oversized", "collection": "party", "flashy": True}},
    {"id": "prod_e", "merchant_id": "merchant_demo", "name": "Aster Essential", "price_paise": 749900, "currency": "INR", "category": "headphones", "condition": "new", "active": True, "attributes": {"noise_cancelling": True}},
]


def seed_catalog(db: Session) -> int:
    report = import_catalog(db, [CatalogProductInput.model_validate(values) for values in DEMO_PRODUCTS], source="explicit_demo_reset")
    return report.total


@dataclass(frozen=True)
class CatalogImportReport:
    created: int
    updated: int
    unchanged: int

    @property
    def total(self) -> int:
        return self.created + self.updated + self.unchanged


class CatalogOwnershipConflict(ValueError):
    pass


def import_catalog(db: Session, records: list[CatalogProductInput], *, source: str) -> CatalogImportReport:
    """Atomically upsert merchant-authoritative facts after all input is validated."""
    if not records:
        raise ValueError("Catalog import must contain at least one product")
    if len({item.id for item in records}) != len(records):
        raise ValueError("Catalog import contains duplicate product IDs")

    created = updated = unchanged = 0
    for item in records:
        values = item.model_dump()
        existing = db.get(Product, item.id)
        if existing and existing.merchant_id != item.merchant_id:
            db.rollback()
            raise CatalogOwnershipConflict(f"Product {item.id} belongs to another merchant")
        if existing is None:
            db.add(Product(**values))
            created += 1
            write_audit(db, "CATALOG_PRODUCT_CREATED", "product", item.id, {"merchant_id": item.merchant_id, "source": source})
            continue
        changed_fields = [key for key, value in values.items() if getattr(existing, key) != value]
        if not changed_fields:
            unchanged += 1
            continue
        for key, value in values.items():
            setattr(existing, key, value)
        updated += 1
        write_audit(db, "CATALOG_PRODUCT_UPDATED", "product", item.id, {"merchant_id": item.merchant_id, "source": source, "changed_fields": changed_fields})

    write_audit(db, "CATALOG_IMPORT_COMPLETED", "catalog", records[0].merchant_id, {"source": source, "created": created, "updated": updated, "unchanged": unchanged, "total": len(records)})
    db.commit()
    return CatalogImportReport(created=created, updated=updated, unchanged=unchanged)
