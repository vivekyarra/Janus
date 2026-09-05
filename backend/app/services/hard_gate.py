from datetime import datetime, timezone

from app.db.models import Mandate, Product
from app.domain.models import HardCheck, HardConstraints, HardGateResult, ReasonCode
from app.services.signature_service import SignatureService, canonical_json_bytes, canonical_mandate_payload


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def evaluate_hard_constraints(
    mandate: Mandate,
    product: Product,
    quantity: int,
    agent_request_id: str,
    now: datetime,
    *,
    idempotency_unused: bool = True,
) -> HardGateResult:
    constraints = HardConstraints.model_validate(mandate.hard_constraints)
    checks: list[HardCheck] = []

    def check(name: str, passed: bool, expected, actual, source: str, reason: ReasonCode) -> HardGateResult | None:
        checks.append(HardCheck(name=name, passed=passed, expected=expected, actual=actual, source=source))
        return None if passed else HardGateResult(status="FAIL", reason_code=reason, checks=checks)

    signed_bytes = canonical_json_bytes(canonical_mandate_payload(mandate))
    failure = check("signature_valid", SignatureService.verify(signed_bytes, mandate.signature, mandate.public_key), "valid ES256 signature", "valid" if SignatureService.verify(signed_bytes, mandate.signature, mandate.public_key) else "invalid", "signed_mandate", ReasonCode.SIGNATURE_INVALID)
    if failure: return failure
    status_reason = ReasonCode.MANDATE_REVOKED if mandate.status == "REVOKED" else ReasonCode.MANDATE_CONSUMED
    failure = check("mandate_active", mandate.status == "ACTIVE", "ACTIVE", mandate.status, "server_state", status_reason)
    if failure: return failure
    failure = check("mandate_not_expired", _aware(mandate.expires_at) > _aware(now), {"operator": ">", "value": _aware(now).isoformat()}, _aware(mandate.expires_at).isoformat(), "signed_mandate", ReasonCode.MANDATE_EXPIRED)
    if failure: return failure
    failure = check("mandate_version_current", mandate.version == mandate.signed_version, mandate.signed_version, mandate.version, "server_state", ReasonCode.MANDATE_VERSION_STALE)
    if failure: return failure
    failure = check("idempotency_unused", idempotency_unused, "unused agent_request_id", agent_request_id, "server_state", ReasonCode.DUPLICATE_REQUEST)
    if failure: return failure
    failure = check("merchant_allowed", product.merchant_id in constraints.allowed_merchants, constraints.allowed_merchants, product.merchant_id, "merchant_catalog", ReasonCode.MERCHANT_NOT_ALLOWED)
    if failure: return failure
    failure = check("currency_allowed", product.currency in constraints.allowed_currencies, constraints.allowed_currencies, product.currency, "merchant_catalog", ReasonCode.CURRENCY_NOT_ALLOWED)
    if failure: return failure
    failure = check("category_allowed", product.category in constraints.allowed_categories, constraints.allowed_categories, product.category, "merchant_catalog", ReasonCode.CATEGORY_NOT_ALLOWED)
    if failure: return failure
    failure = check("condition_allowed", product.condition in constraints.allowed_conditions, constraints.allowed_conditions, product.condition, "merchant_catalog", ReasonCode.CONDITION_NOT_ALLOWED)
    if failure: return failure
    failure = check("quantity_within_limit", 0 < quantity <= constraints.max_quantity, {"operator": "<=", "value": constraints.max_quantity}, quantity, "request", ReasonCode.QUANTITY_EXCEEDED)
    if failure: return failure
    total = product.price_paise * quantity
    failure = check("amount_within_limit", total <= constraints.max_amount_paise, {"operator": "<=", "value": constraints.max_amount_paise}, total, "merchant_catalog", ReasonCode.AMOUNT_LIMIT_EXCEEDED)
    if failure: return failure
    failure = check("execution_count_available", mandate.execution_count < mandate.max_executions, {"operator": "<", "value": mandate.max_executions}, mandate.execution_count, "server_state", ReasonCode.EXECUTION_LIMIT_EXCEEDED)
    if failure: return failure
    return HardGateResult(status="PASS", checks=checks)

