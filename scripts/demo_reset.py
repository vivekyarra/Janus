import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings
from app.db.models import AuditEvent, CheckoutProposal, Mandate, Product, StepUpRequest
from app.db.session import Base, SessionLocal, engine
from app.repositories.catalog import seed_catalog


def main():
    settings = get_settings()
    if settings.app_env not in {"development", "test", "demo"}:
        raise SystemExit("Refusing demo reset outside development/test/demo APP_ENV.")
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for model in (StepUpRequest, CheckoutProposal, AuditEvent, Mandate, Product):
            db.query(model).delete()
        db.commit()
        count = seed_catalog(db)
    print(f"JANUS demo reset complete: {count} products, 0 mandates, 0 proposals, 0 audit events.")


if __name__ == "__main__":
    main()
