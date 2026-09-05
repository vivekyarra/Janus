from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import AuditRead
from app.db.models import AuditEvent
from app.db.session import get_db


router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("", response_model=list[AuditRead])
def list_audit(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return list(db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)))

