from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import CatalogImportRequest, CatalogImportResponse, MerchantMetricsResponse
from app.db.models import AuditEvent, CheckoutProposal, Product
from app.db.session import get_db
from app.domain.models import ProductRead
from app.repositories.catalog import CatalogOwnershipConflict, import_catalog
from app.services.auth_service import Actor, require_human_actor, require_proposal_actor

router = APIRouter(prefix="/api/v1/products", tags=["catalog"])


@router.get("", response_model=list[ProductRead])
def list_products(
    merchant_id: str | None = Query(default=None, min_length=3, max_length=80),
    db: Session = Depends(get_db),
    _: Actor = Depends(require_proposal_actor),
) -> list[Product]:
    query = select(Product)
    if merchant_id:
        query = query.where(Product.merchant_id == merchant_id)
    return list(db.scalars(query.order_by(Product.id)))


@router.post("/import", response_model=CatalogImportResponse)
def import_products(
    request: CatalogImportRequest,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_human_actor),
) -> CatalogImportResponse:
    if any(product.merchant_id != request.merchant_id for product in request.products):
        raise HTTPException(422, detail={"reason_code": "CATALOG_MERCHANT_MISMATCH"})
    try:
        report = import_catalog(db, request.products, source=f"authenticated_api:{actor.subject}")
    except CatalogOwnershipConflict as exc:
        raise HTTPException(409, detail={"reason_code": "CATALOG_OWNERSHIP_CONFLICT", "message": str(exc)}) from exc
    return CatalogImportResponse(
        merchant_id=request.merchant_id,
        total=report.total,
        created=report.created,
        updated=report.updated,
        unchanged=report.unchanged,
    )


@router.get("/metrics", response_model=MerchantMetricsResponse)
def get_merchant_metrics(
    merchant_id: str = Query(default="northstar_audio", min_length=3, max_length=80),
    db: Session = Depends(get_db),
    _: Actor = Depends(require_proposal_actor),
) -> MerchantMetricsResponse:
    products = list(db.scalars(select(Product).where(Product.merchant_id == merchant_id)))
    sku_count = len(products)
    active_skus = len([p for p in products if p.active])

    # Machine-readability: percentage of products with structured non-empty attributes
    if sku_count > 0:
        readable_count = sum(
            1
            for p in products
            if p.name and p.price_paise > 0 and p.currency and p.category and isinstance(p.attributes, dict)
        )
        readability: float | None = round((readable_count / sku_count) * 100.0, 1)
    else:
        readability = None

    product_ids = [p.id for p in products]
    proposals = (
        list(db.scalars(select(CheckoutProposal).where(CheckoutProposal.product_id.in_(product_ids))))
        if product_ids
        else []
    )
    total = len(proposals)

    allowed = [p for p in proposals if p.status in {"ALLOWED", "ORDER_CREATED", "EXECUTED", "PAID"}]
    stepups = [p for p in proposals if p.status == "STEP_UP"]
    blocked = [p for p in proposals if p.status == "BLOCKED"]

    # Autonomous GMV: ONLY count verified payments (PAID status or VERIFIED payment_status)
    paid_proposals = [p for p in proposals if p.status == "PAID" or p.payment_status == "VERIFIED"]
    gmv_paise = sum(p.expected_amount_paise for p in paid_proposals)

    # Blocked overspend: ONLY count proposals blocked due to AMOUNT_LIMIT_EXCEEDED
    amount_blocked = [
        p for p in blocked if (p.decision or {}).get("reason_code") == "AMOUNT_LIMIT_EXCEEDED"
    ]
    blocked_paise = sum(p.expected_amount_paise for p in amount_blocked)

    # Rates: None when total == 0 (no fake 100%)
    if total > 0:
        conv_rate: float | None = round((len(paid_proposals) / total) * 100.0, 1)
        auth_rate: float | None = round((len(allowed) / total) * 100.0, 1)
        stepup_rate: float | None = round((len(stepups) / total) * 100.0, 1)
        semantic_rejections = [
            p
            for p in blocked
            if (p.decision or {}).get("reason_code") in {"SEMANTIC_CONTRADICTED", "SEMANTIC_INSUFFICIENT_EVIDENCE"}
        ]
        semantic_rej_rate: float | None = round((len(semantic_rejections) / total) * 100.0, 1)
        ordered = [p for p in proposals if p.razorpay_order_id is not None]
        pay_rate: float | None = round((len(paid_proposals) / len(ordered)) * 100.0, 1) if ordered else None
    else:
        conv_rate = None
        auth_rate = None
        stepup_rate = None
        semantic_rej_rate = None
        pay_rate = None

    # Calculate real authorization latencies (P50 and P95) from audit event timestamps
    latencies: list[float] = []
    duplicate_prevention_count = 0
    if proposals:
        prop_ids = [p.id for p in proposals]
        events = list(
            db.scalars(
                select(AuditEvent)
                .where(AuditEvent.entity_type == "proposal", AuditEvent.entity_id.in_(prop_ids))
                .order_by(AuditEvent.created_at)
            )
        )
        by_prop: dict[str, dict[str, datetime]] = {}
        for ev in events:
            if ev.event_type == "DUPLICATE_REQUEST_REJECTED":
                duplicate_prevention_count += 1
            if ev.entity_id not in by_prop:
                by_prop[ev.entity_id] = {}
            if ev.event_type in ("PROPOSAL_RECEIVED", "FINAL_DECISION", "HARD_GATE_FAILED"):
                by_prop[ev.entity_id][ev.event_type] = ev.created_at

        for p_id, times in by_prop.items():
            start_t = times.get("PROPOSAL_RECEIVED")
            end_t = times.get("FINAL_DECISION") or times.get("HARD_GATE_FAILED")
            if start_t and end_t:
                delta = max(0.01, (end_t - start_t).total_seconds() * 1000.0)
                latencies.append(delta)

    if latencies:
        sorted_lat = sorted(latencies)
        p50_idx = int(len(sorted_lat) * 0.50)
        p95_idx = max(0, min(len(sorted_lat) - 1, int(len(sorted_lat) * 0.95)))
        p50_latency: float | None = round(sorted_lat[p50_idx], 2)
        p95_latency: float | None = round(sorted_lat[p95_idx], 2)
    else:
        p50_latency = None
        p95_latency = None

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
        p95_authorization_latency_ms=p95_latency,
        p50_authorization_latency_ms=p50_latency,
        authorization_success_rate_pct=auth_rate,
        step_up_rate_pct=stepup_rate,
        semantic_rejection_rate_pct=semantic_rej_rate,
        payment_success_rate_pct=pay_rate,
        duplicate_prevention_count=duplicate_prevention_count,
        # Frontend aliases:
        total_skus=sku_count,
        active_skus=active_skus,
        machine_readable_pct=readability,
        prevented_overspend_paise=blocked_paise,
        executed_proposals=len(paid_proposals),
        blocked_proposals=len(blocked),
    )
