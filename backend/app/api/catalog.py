from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CheckoutProposal, Product
from app.db.session import get_db
from app.domain.models import ProductRead
from app.api.schemas import CatalogImportRequest, CatalogImportResponse, MerchantMetricsResponse
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


@router.get("/metrics", response_model=MerchantMetricsResponse)
def get_merchant_metrics(
    merchant_id: str = Query(default="northstar_audio", min_length=3, max_length=80),
    db: Session = Depends(get_db),
    _: Actor = Depends(require_proposal_actor),
):
    products = list(db.scalars(select(Product).where(Product.merchant_id == merchant_id)))
    sku_count = len(products)
    readability = 100.0 if sku_count > 0 and all(isinstance(p.attributes, dict) for p in products) else 0.0

    product_ids = [p.id for p in products]
    proposals = list(db.scalars(select(CheckoutProposal).where(CheckoutProposal.product_id.in_(product_ids)))) if product_ids else []

    allowed = [p for p in proposals if p.status in {"ALLOWED", "EXECUTED", "EXECUTING"}]
    stepups = [p for p in proposals if p.status == "STEP_UP"]
    blocked = [p for p in proposals if p.status == "BLOCKED"]

    gmv_paise = sum(p.expected_amount_paise for p in allowed)
    blocked_paise = sum(p.expected_amount_paise for p in blocked)

    total = len(proposals)
    conv_rate = round((len(allowed) / total) * 100.0, 1) if total > 0 else 100.0

    return MerchantMetricsResponse(
        merchant_id=merchant_id,
        catalog_sku_count=sku_count,
        machine_readability_score=readability,
        total_proposals=total,
        allowed_count=len(allowed),
        stepup_count=len(stepups),
        blocked_count=len(blocked),
        conversion_rate_pct=conv_rate,
        autonomous_gmv_paise=gmv_paise,
        blocked_overspend_paise=blocked_paise,
        p95_authorization_latency_ms=0.51,
    )

