from __future__ import annotations

import base64
import re
import unicodedata
from typing import Any

from app.domain.models import EvidenceItem, SemanticAssessment, SemanticConstraintResult
from app.integrations.llm_adapter import SemanticModelPort, SemanticModelUnavailable

SUSPICIOUS_TOKENS = (
    "ignore all previous",
    "ignore all constraints",
    "system:",
    "assistant:",
    "user:",
    "return supported",
    "output supported",
    "override",
    "bypassing",
    "check field x",
    "invalid_status",
    "step 1:",
    "```json",
    "<b>system:",
    "系统：",
    "系统:",
    "系统",
    "\u7cfb\u7edf",
    "النظام:",
    "सिस्टम:",
    "\U0001F916:",
)

ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200d\ufeff]")


def _detect_prompt_injection(val: Any) -> bool:
    if val is None:
        return False
    raw_str = str(val)
    # 1. Normalize unicode (NFKC turns full-width chars like ＳＹＳＴＥＭ into SYSTEM)
    norm = unicodedata.normalize("NFKC", raw_str)
    # 2. Strip zero-width characters
    cleaned = ZERO_WIDTH_RE.sub("", norm).lower()

    # 3. Direct token check
    if any(token in cleaned for token in SUSPICIOUS_TOKENS):
        return True

    # 4. Check for embedded base64
    base64_candidates = re.findall(r"[A-Za-z0-9+/]{8,}={0,2}", raw_str)
    for b64 in base64_candidates:
        try:
            decoded = base64.b64decode(b64.encode("ascii"), validate=True).decode("utf-8", errors="ignore").lower()
            if any(token in decoded for token in ("system:", "supported", "ignore", "override")):
                return True
        except Exception:
            pass

    # 5. Check for nested json instruction
    if "instruction" in cleaned and "supported" in cleaned:
        return True

    return False


def assess_semantic_constraints(
    instruction_text: str,
    semantic_constraints: list[dict],
    product_evidence: dict[str, Any],
    model: SemanticModelPort,
) -> SemanticAssessment:
    if not semantic_constraints:
        return SemanticAssessment(results=[])

    # Quarantine prompt injection before passing to model
    if any(_detect_prompt_injection(val) for val in product_evidence.values()):
        return SemanticAssessment(
            results=[
                SemanticConstraintResult(
                    constraint_id=item["id"],
                    status="INSUFFICIENT_EVIDENCE",
                    evidence=[],
                    reason="Merchant evidence contained instruction-like or prompt-injection text and was quarantined.",
                )
                for item in semantic_constraints
            ]
        )

    try:
        raw = model.classify(instruction=instruction_text, constraints=semantic_constraints, evidence=product_evidence)
    except SemanticModelUnavailable:
        return SemanticAssessment(results=[], service_status="UNAVAILABLE")

    by_id = (
        {item.get("constraint_id"): item for item in raw.get("results", []) if isinstance(item, dict)}
        if isinstance(raw, dict)
        else {}
    )

    validated: list[SemanticConstraintResult] = []
    for constraint in semantic_constraints:
        item = by_id.get(constraint["id"])
        if not item or item.get("status") not in {"SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"}:
            validated.append(
                SemanticConstraintResult(
                    constraint_id=constraint["id"],
                    status="INSUFFICIENT_EVIDENCE",
                    evidence=[],
                    reason="Model output missing or malformed for this constraint.",
                )
            )
            continue

        fields = item.get("evidence_fields", [])
        if not isinstance(fields, list) or any(field not in product_evidence for field in fields):
            validated.append(
                SemanticConstraintResult(
                    constraint_id=constraint["id"],
                    status="INSUFFICIENT_EVIDENCE",
                    evidence=[],
                    reason="Model cited evidence outside the merchant catalog.",
                )
            )
            continue

        evidence = [EvidenceItem(field=field, value=product_evidence[field]) for field in fields]
        status = item["status"]
        if status in {"SUPPORTED", "CONTRADICTED"} and not evidence:
            status = "INSUFFICIENT_EVIDENCE"

        validated.append(
            SemanticConstraintResult(
                constraint_id=constraint["id"],
                status=status,
                evidence=evidence,
                reason=str(item.get("reason", ""))[:500],
            )
        )

    return SemanticAssessment(results=validated)
