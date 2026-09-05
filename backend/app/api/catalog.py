from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Product
from app.db.session import get_db
from app.domain.models import ProductRead
from app.api.schemas import CatalogImportRequest, CatalogImportResponse
from app.repositories.catalog import CatalogOwnershipConflict, import_catalog
from app.services.auth_service import Actor, require_human_actor, require_proposal_actor


router = APIRouter(prefix="/api/v1/products", tags=["catalog"])


@router.get("", response_model=list[ProductRead])
def list_products(
    merchant_id: str | None = Query(default=None, min_length=3, max_length=80),
    db: Session = Depends(get_db),
    _: Actor = Depends(require_proposal_actor),
):
    query = select(Product)
    if merchant_id:
        query = query.where(Product.merchant_id == merchant_id)
    return list(db.scalars(query.order_by(Product.id)))


@router.post("/import", response_model=CatalogImportResponse)
def import_products(
    request: CatalogImportRequest,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_human_actor),
):
    if any(product.merchant_id != request.merchant_id for product in request.products):
        raise HTTPException(422, detail={"reason_code": "CATALOG_MERCHANT_MISMATCH"})
    try:
        report = import_catalog(db, request.products, source=f"authenticated_api:{actor.subject}")
    except CatalogOwnershipConflict as exc:
        raise HTTPException(409, detail={"reason_code": "CATALOG_OWNERSHIP_CONFLICT", "message": str(exc)}) from exc
    return CatalogImportResponse(merchant_id=request.merchant_id, total=report.total, created=report.created, updated=report.updated, unchanged=report.unchanged)
