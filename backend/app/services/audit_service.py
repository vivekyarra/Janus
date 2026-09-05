from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditEvent


def write_audit(db: Session, event_type: str, entity_type: str, entity_id: str, payload: dict[str, Any]) -> AuditEvent:
    event = AuditEvent(event_type=event_type, entity_type=entity_type, entity_id=entity_id, payload=payload)
    db.add(event)
    db.flush()
    return event

