from datetime import datetime, timezone

import pytest

from app.domain.models import ReasonCode
from app.services.decision_engine import decide
from app.services.hard_gate import evaluate_hard_constraints
from app.services.semantic_scorer import assess_semantic_constraints
from tests.unit.test_hard_gate import make_mandate, make_product


class ScriptedModel:
    def __init__(self, result):
        self.result = result

    def classify(self, **_):
        return self.result


def hard_pass():
    return evaluate_hard_constraints(make_mandate(), make_product(), 1, "req", datetime.now(timezone.utc))


def test_high_confidence_supported_allows() -> None:
    model = ScriptedModel({
        "results": [
            {
                "constraint_id": "travel",
                "status": "SUPPORTED",
                "confidence": 0.94,
                "evidence_fields": ["foldable", "travel_case"],
                "reason": "Product folds flat and includes a rugged hardshell travel case.",
            }
        ]
    })
    evidence = {"foldable": True, "travel_case": True, "weight_g": 240}
    assessment = assess_semantic_constraints(
        "Good for travel",
        [{"id": "travel", "text": "good for travel"}],
        evidence,
        model,
    )
    assert assessment.results[0].status == "SUPPORTED"
    assert assessment.results[0].confidence == 0.94
    assert assessment.results[0].abstain is False
    assert "catalog.attributes.foldable=True" in assessment.results[0].citation
    decision = decide(hard_pass(), assessment)
    assert decision.decision == "ALLOW"


def test_low_confidence_supported_abstains_to_stepup() -> None:
    # Model returns SUPPORTED, but epistemic confidence is only 0.65 (< 0.85 threshold)
    model = ScriptedModel({
        "results": [
            {
                "constraint_id": "office",
                "status": "SUPPORTED",
                "confidence": 0.65,
                "evidence_fields": ["mic_quality"],
                "reason": "Microphone is decent but background noise reduction is unverified.",
            }
        ]
    })
    evidence = {"mic_quality": "standard"}
    assessment = assess_semantic_constraints(
        "Suitable for executive office calls",
        [{"id": "office", "text": "suitable for office"}],
        evidence,
        model,
        confidence_threshold=0.85,
    )
    # Calibrated abstention mechanism converts this to INSUFFICIENT_EVIDENCE
    assert assessment.results[0].status == "INSUFFICIENT_EVIDENCE"
    assert assessment.results[0].abstain is True
    assert "below autonomous safety threshold" in assessment.results[0].reason
    decision = decide(hard_pass(), assessment)
    # Fails closed to human review (STEP_UP), preventing unsafe autonomous charge!
    assert decision.decision == "STEP_UP"
    assert decision.reason_code == ReasonCode.SEMANTIC_INSUFFICIENT_EVIDENCE


def test_hallucinated_evidence_key_fails_closed() -> None:
    # Model cites an attribute key that does NOT exist in the merchant catalog
    model = ScriptedModel({
        "results": [
            {
                "constraint_id": "travel",
                "status": "SUPPORTED",
                "confidence": 0.99,
                "evidence_fields": ["hallucinated_airline_approved_token"],
                "reason": "Model hallucination.",
            }
        ]
    })
    evidence = {"foldable": True}
    assessment = assess_semantic_constraints(
        "Good for travel",
        [{"id": "travel", "text": "good for travel"}],
        evidence,
        model,
    )
    assert assessment.results[0].status == "INSUFFICIENT_EVIDENCE"
    assert assessment.results[0].abstain is True
    assert "Model cited evidence outside the merchant catalog" in assessment.results[0].reason
    decision = decide(hard_pass(), assessment)
    assert decision.decision == "STEP_UP"


def test_evidence_citations_formatting() -> None:
    model = ScriptedModel({
        "results": [
            {
                "constraint_id": "not_flashy",
                "status": "CONTRADICTED",
                "confidence": 0.98,
                "evidence_fields": ["color", "branding"],
                "reason": "Metallic gold color with oversized branding contradicts minimalist requirement.",
            }
        ]
    })
    evidence = {"color": "metallic_gold", "branding": "oversized"}
    assessment = assess_semantic_constraints(
        "Nothing flashy",
        [{"id": "not_flashy", "text": "nothing flashy"}],
        evidence,
        model,
    )
    res = assessment.results[0]
    assert res.status == "CONTRADICTED"
    assert "catalog.attributes.color='metallic_gold'" in res.citation
    assert "catalog.attributes.branding='oversized'" in res.citation
    assert len(res.evidence) == 2
    assert res.evidence[0].field == "color"
    assert res.evidence[0].citation == "catalog.attributes.color='metallic_gold'"
