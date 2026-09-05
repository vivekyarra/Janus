from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import CheckoutProposal, Mandate, Product
from app.db.session import get_db
from app.services.protocol_interop import (
    export_acp_checkout,
    export_ap2_mandate,
    import_ap2_mandate,
    verify_x402_handshake,
)

router = APIRouter(prefix="/api/v1/interop", tags=["protocol_interop"])


class AP2ImportRequest(BaseModel):
    envelope: dict[str, Any]


class AP2ImportResponse(BaseModel):
    status: str
    mandate_payload: dict[str, Any]


@router.get("/ap2/{mandate_id}")
def get_ap2_envelope(mandate_id: str, db: Session = Depends(get_db)):
    """Export JANUS signed mandate as an AP2 (Agent Payments Protocol) Delegation Envelope."""
    mandate = db.get(Mandate, mandate_id)
    if not mandate:
        raise HTTPException(status_code=404, detail={"reason_code": "MANDATE_NOT_FOUND"})
    return export_ap2_mandate(mandate)


@router.post("/ap2/import", response_model=AP2ImportResponse)
def import_ap2_envelope(req: AP2ImportRequest):
    """Import an external AP2 Delegation Envelope into JANUS mandate input."""
    try:
        payload = import_ap2_mandate(req.envelope)
        return AP2ImportResponse(status="IMPORTED", mandate_payload=payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"reason_code": "AP2_PARSE_ERROR", "message": str(exc)})


@router.get("/acp/{proposal_id}")
def get_acp_checkout(proposal_id: str, db: Session = Depends(get_db)):
    """Export JANUS proposal and settlement state as an ACP (Agentic Commerce Protocol) Checkout Intent."""
    proposal = db.get(CheckoutProposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail={"reason_code": "PROPOSAL_NOT_FOUND"})
    mandate = db.get(Mandate, proposal.mandate_id)
    product = db.get(Product, proposal.product_id)
    if not mandate or not product:
        raise HTTPException(status_code=404, detail={"reason_code": "AUTHORIZATION_STATE_UNAVAILABLE"})
    return export_acp_checkout(proposal, mandate, product)


@router.post("/x402/verify")
def verify_x402(authorization: str | None = Header(default=None)):
    """Verify HTTP 402 payment header handshake for machine-to-machine checkout.
    
    NOTE: Returns 501 Not Implemented as x402 is out of scope for current build.
    """
    result = verify_x402_handshake(authorization)
    if result["http_code"] != 200:
        return JSONResponse(status_code=result["http_code"], content=result)
    return result
