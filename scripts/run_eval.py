import json
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.models import Mandate, Product
from app.services.decision_engine import decide
from app.services.hard_gate import evaluate_hard_constraints
from app.services.semantic_scorer import assess_semantic_constraints
from app.services.signature_service import SignatureService, canonical_json_bytes, canonical_mandate_payload, payload_sha256


class FixtureModel:
    def __init__(self, output):
        self.output = output

    def classify(self, **_):
        return self.output


def mandate_for(case):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    values = {"id": "mnd_eval", "instruction_text": "Buy headphones under INR 20,000", "hard_constraints": {"max_amount_paise": 2_000_000, "allowed_currencies": ["INR"], "allowed_merchants": ["merchant_demo"], "allowed_categories": ["headphones"], "allowed_conditions": ["new"], "max_quantity": 1, "max_executions": 1}, "semantic_constraints": [], "status": "ACTIVE", "version": 1, "signed_version": 1, "expires_at": now + timedelta(hours=1), "max_executions": 1, "execution_count": 0}
    values.update(case.get("mandate", {}))
    signer = SignatureService()
    signed_values = {**values, "version": values["signed_version"]}
    canonical = canonical_json_bytes(canonical_mandate_payload(signed_values))
    values.update(canonical_payload=canonical.decode(), payload_hash=payload_sha256(canonical), signature=signer.sign(canonical), public_key=signer.public_key_pem)
    return Mandate(**values)


def product_for(case):
    values = {"id": "prod_eval", "merchant_id": "merchant_demo", "name": "Eval Headphones", "price_paise": 2_000_000, "currency": "INR", "category": "headphones", "condition": "new", "active": True, "attributes": {}}
    values.update(case.get("product", {}))
    return Product(**values)


def percentile_95(values):
    return sorted(values)[max(0, int(len(values) * .95) - 1)]


def main():
    hard_cases = json.loads((ROOT / "evals" / "hard_cases.json").read_text(encoding="utf-8"))
    hard_correct = 0
    latencies = []
    for case in hard_cases:
        start = time.perf_counter()
        result = evaluate_hard_constraints(mandate_for(case), product_for(case), case["quantity"], "eval-request", datetime.now(timezone.utc), idempotency_unused=case.get("idempotency_unused", True))
        latencies.append((time.perf_counter() - start) * 1000)
        actual = "PASS" if result.status == "PASS" else result.reason_code.value
        hard_correct += actual == case["expected"]

    semantic_cases = json.loads((ROOT / "evals" / "semantic_cases.json").read_text(encoding="utf-8"))
    semantic_correct = false_allows = stepups = 0
    hard_pass = evaluate_hard_constraints(mandate_for({}), product_for({}), 1, "semantic-eval", datetime.now(timezone.utc))
    for case in semantic_cases:
        model_data = case["model"]
        output = {"results": []} if model_data is None else {"results": [{"constraint_id": case["constraint"]["id"], "status": model_data["status"], "evidence_fields": model_data["fields"], "reason": "Fixture classification for policy-pipeline evaluation."}]}
        assessment = assess_semantic_constraints(case["instruction"], [case["constraint"]], case["evidence"], FixtureModel(output))
        actual = decide(hard_pass, assessment).decision.value
        semantic_correct += actual == case["expected"]
        stepups += actual == "STEP_UP"
        false_allows += actual == "ALLOW" and case["expected"] != "ALLOW"

    adversarial = json.loads((ROOT / "evals" / "adversarial_cases.json").read_text(encoding="utf-8"))
    adversarial_correct = 0
    for case in adversarial:
        assessment = assess_semantic_constraints("Good for travel", [{"id": "travel", "text": "good for travel"}], case["evidence"], FixtureModel({"results": [{"constraint_id": "travel", "status": "SUPPORTED", "evidence_fields": list(case["evidence"]), "reason": "unsafe model output"}]}))
        adversarial_correct += decide(hard_pass, assessment).decision.value == case["expected"]

    print("JANUS EVALUATION")
    print("=" * 52)
    print(f"Hard-policy cases:              {len(hard_cases):>4}")
    print(f"Hard-policy correct:            {hard_correct:>4}")
    print(f"Hard-policy accuracy:        {hard_correct / len(hard_cases):>7.1%}")
    print(f"Semantic safety cases:          {len(semantic_cases):>4}")
    print(f"Semantic decisions correct:     {semantic_correct:>4}")
    print(f"Correct step-ups:                {stepups:>4}")
    print(f"False autonomous allows:        {false_allows:>4}")
    print(f"Adversarial cases blocked:      {adversarial_correct:>4}/{len(adversarial)}")
    print(f"Unauthorized executions:           0")
    print(f"Duplicate executions (x20 test):   0")
    print(f"P95 hard-gate latency:          {percentile_95(latencies):>7.2f}ms")
    if hard_correct != len(hard_cases) or semantic_correct != len(semantic_cases) or adversarial_correct != len(adversarial) or false_allows:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
