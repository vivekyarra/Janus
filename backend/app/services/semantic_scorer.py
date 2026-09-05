from typing import Any

from app.domain.models import EvidenceItem, SemanticAssessment, SemanticConstraintResult
from app.integrations.llm_adapter import SemanticModelPort, SemanticModelUnavailable


def assess_semantic_constraints(instruction_text: str, semantic_constraints: list[dict], product_evidence: dict[str, Any], model: SemanticModelPort) -> SemanticAssessment:
    if not semantic_constraints:
        return SemanticAssessment(results=[])
    suspicious = ("ignore all previous", "system:", "assistant:", "return supported", "override")
    if any(any(token in str(value).lower() for token in suspicious) for value in product_evidence.values()):
        return SemanticAssessment(results=[SemanticConstraintResult(constraint_id=item["id"], status="INSUFFICIENT_EVIDENCE", evidence=[], reason="Merchant evidence contained instruction-like text and was rejected as untrusted.") for item in semantic_constraints])
    try:
        raw = model.classify(instruction=instruction_text, constraints=semantic_constraints, evidence=product_evidence)
    except SemanticModelUnavailable:
        return SemanticAssessment(results=[], service_status="UNAVAILABLE")

    by_id = {item.get("constraint_id"): item for item in raw.get("results", []) if isinstance(item, dict)} if isinstance(raw, dict) else {}
    validated: list[SemanticConstraintResult] = []
    for constraint in semantic_constraints:
        item = by_id.get(constraint["id"])
        if not item or item.get("status") not in {"SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"}:
            validated.append(SemanticConstraintResult(constraint_id=constraint["id"], status="INSUFFICIENT_EVIDENCE", evidence=[], reason="Model output missing or malformed for this constraint."))
            continue
        fields = item.get("evidence_fields", [])
        if not isinstance(fields, list) or any(field not in product_evidence for field in fields):
            validated.append(SemanticConstraintResult(constraint_id=constraint["id"], status="INSUFFICIENT_EVIDENCE", evidence=[], reason="Model cited evidence outside the merchant catalog."))
            continue
        evidence = [EvidenceItem(field=field, value=product_evidence[field]) for field in fields]
        status = item["status"]
        if status in {"SUPPORTED", "CONTRADICTED"} and not evidence:
            status = "INSUFFICIENT_EVIDENCE"
        validated.append(SemanticConstraintResult(constraint_id=constraint["id"], status=status, evidence=evidence, reason=str(item.get("reason", ""))[:500]))
    return SemanticAssessment(results=validated)
