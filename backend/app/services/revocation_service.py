from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Mandate
from app.services.audit_service import write_audit


def revoke_mandate(db: Session, mandate_id: str) -> Mandate | None:
    mandate = db.scalar(select(Mandate).where(Mandate.id == mandate_id).with_for_update())
    if mandate is None:
        return None
    if mandate.status == "ACTIVE":
        mandate.status = "REVOKED"
        mandate.revoked_at = datetime.now(timezone.utc)
        mandate.version += 1
        write_audit(db, "MANDATE_REVOKED", "mandate", mandate.id, {"revoked_at": mandate.revoked_at.isoformat(), "version": mandate.version})
        db.commit()
        db.refresh(mandate)
    return mandate
