from datetime import datetime, timezone

import pytest

from app.domain.models import DecisionType
from app.services.decision_engine import decide
from app.services.hard_gate import evaluate_hard_constraints
from app.services.semantic_scorer import assess_semantic_constraints
from tests.unit.test_hard_gate import make_mandate, make_product


class ScriptedClassifier:
    """Simulates calibrated LLM classifier that evaluates exact merchant attributes."""

    def classify(self, *, instruction: str, constraints: list[dict], evidence: dict) -> dict:
        results = []
        for c in constraints:
            cid = c["id"]
            if cid == "not_flashy":
                color = evidence.get("color")
                branding = evidence.get("branding")
                if color == "metallic_gold" or branding == "oversized":
                    results.append({
                        "constraint_id": cid,
                        "status": "CONTRADICTED",
                        "confidence": 0.98,
                        "evidence_fields": [k for k in ["color", "branding"] if k in evidence],
                        "citation": f"catalog.attributes.color={color} contradicts 'not flashy'",
                        "reason": f"Color {color} is flashy.",
                    })
                else:
                    results.append({
                        "constraint_id": cid,
                        "status": "SUPPORTED",
                        "confidence": 0.96,
                        "evidence_fields": [k for k in ["color", "branding"] if k in evidence],
                        "citation": f"catalog.attributes.color={color} supports 'not flashy'",
                        "reason": f"Color {color} is understated.",
                    })
            elif cid == "waterproof":
                wp = evidence.get("waterproof", False)
                if wp:
                    results.append({
                        "constraint_id": cid,
                        "status": "SUPPORTED",
                        "confidence": 0.99,
                        "evidence_fields": ["waterproof"],
                        "citation": "catalog.attributes.waterproof=True",
                        "reason": "Explicitly waterproof.",
                    })
                else:
                    results.append({
                        "constraint_id": cid,
                        "status": "CONTRADICTED",
                        "confidence": 0.95,
                        "evidence_fields": ["waterproof"],
                        "citation": "catalog.attributes.waterproof=False",
                        "reason": "Not waterproof.",
                    })
        return {"results": results}


def hard_pass():
    return evaluate_hard_constraints(make_mandate(), make_product(), 1, "req", datetime.now(timezone.utc))


def test_counterfactual_color_attribute_flip() -> None:
    classifier = ScriptedClassifier()
    constraints = [{"id": "not_flashy", "text": "nothing flashy"}]

    # Variant A: Flashy (metallic gold)
    evidence_flashy = {"color": "metallic_gold", "branding": "minimal", "weight_g": 220}
    res_a = assess_semantic_constraints("Nothing flashy", constraints, evidence_flashy, classifier)
    dec_a = decide(hard_pass(), res_a)
    assert res_a.results[0].status == "CONTRADICTED"
    assert dec_a.decision == DecisionType.STEP_UP

    # Variant B (Counterfactual): Identical product, toggle ONLY color: metallic_gold -> matte_black
    evidence_matte = {"color": "matte_black", "branding": "minimal", "weight_g": 220}
    res_b = assess_semantic_constraints("Nothing flashy", constraints, evidence_matte, classifier)
    dec_b = decide(hard_pass(), res_b)
    # The decision flips deterministically from STEP_UP to ALLOW!
    assert res_b.results[0].status == "SUPPORTED"
    assert dec_b.decision == DecisionType.ALLOW


def test_counterfactual_waterproof_attribute_flip() -> None:
    classifier = ScriptedClassifier()
    constraints = [{"id": "waterproof", "text": "must be waterproof for outdoor running"}]

    # Non-waterproof SKU
    sku_non_wp = {"waterproof": False, "ip_rating": "none", "fit": "sport"}
    res_non = assess_semantic_constraints("Running gear", constraints, sku_non_wp, classifier)
    assert decide(hard_pass(), res_non).decision == DecisionType.STEP_UP

    # Counterfactual: toggle ONLY waterproof: False -> True
    sku_wp = {"waterproof": True, "ip_rating": "IPX7", "fit": "sport"}
    res_wp = assess_semantic_constraints("Running gear", constraints, sku_wp, classifier)
    assert decide(hard_pass(), res_wp).decision == DecisionType.ALLOW
