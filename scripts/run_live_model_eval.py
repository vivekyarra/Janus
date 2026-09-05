from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings
from app.integrations.llm_adapter import GeminiAdapter, VercelAIGatewayAdapter


def run_live_model_evaluation(
    model_name: str = "gemini",
    output_file: str = "evals/live_model_outputs.json"
) -> dict:
    """Run 200 semantic cases through live model and capture raw outputs."""
    settings = get_settings()
    
    # Initialize the appropriate model
    if model_name == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not configured")
        adapter = GeminiAdapter(settings)
        model_id = settings.gemini_model
    elif model_name == "vercel":
        if not settings.ai_gateway_api_key and not settings.vercel_oidc_token and not settings.llm_api_key:
            raise ValueError("Vercel AI Gateway credentials not configured")
        adapter = VercelAIGatewayAdapter(settings)
        model_id = settings.llm_model
    else:
        raise ValueError(f"Unsupported model: {model_name}")
    
    # Load test cases
    cases = json.loads((ROOT / "evals" / "semantic_cases.json").read_text(encoding="utf-8"))
    
    results = []
    errors = []
    start_time = time.time()
    
    print(f"Running {len(cases)} cases through {model_name} ({model_id})...")
    print("=" * 70)
    
    for i, case in enumerate(cases, 1):
        case_start = time.time()
        timestamp = datetime.now(timezone.utc).isoformat()
        
        try:
            # Call the actual model
            output = adapter.classify(
                instruction=case["instruction"],
                constraints=[case["constraint"]],
                evidence=case["evidence"]
            )
            
            latency_ms = (time.time() - case_start) * 1000
            
            result = {
                "case_index": i,
                "case_name": case["name"],
                "timestamp": timestamp,
                "model_name": model_name,
                "model_id": model_id,
                "latency_ms": round(latency_ms, 2),
                "instruction": case["instruction"],
                "constraint": case["constraint"],
                "evidence": case["evidence"],
                "raw_model_output": output,
                "expected_decision": case["expected"]
            }
            results.append(result)
            
            if i % 20 == 0:
                print(f"Processed {i}/{len(cases)} cases...")
                
        except Exception as e:
            error = {
                "case_index": i,
                "case_name": case["name"],
                "timestamp": timestamp,
                "model_name": model_name,
                "model_id": model_id,
                "error": str(e),
                "error_type": type(e).__name__
            }
            errors.append(error)
            print(f"ERROR on case {i} ({case['name']}): {e}")
    
    total_time = time.time() - start_time
    
    # Save results
    output_data = {
        "evaluation_metadata": {
            "model_name": model_name,
            "model_id": model_id,
            "total_cases": len(cases),
            "successful_evaluations": len(results),
            "failed_evaluations": len(errors),
            "total_time_seconds": round(total_time, 2),
            "average_latency_ms": round(sum(r["latency_ms"] for r in results) / max(1, len(results)), 2) if results else 0,
            "evaluation_start": datetime.fromtimestamp(start_time, timezone.utc).isoformat(),
            "evaluation_end": datetime.now(timezone.utc).isoformat()
        },
        "results": results,
        "errors": errors
    }
    
    output_path = ROOT / output_file
    output_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
    
    print("=" * 70)
    print(f"Evaluation complete!")
    print(f"  Successful: {len(results)}/{len(cases)}")
    print(f"  Failed: {len(errors)}/{len(cases)}")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Avg latency: {output_data['evaluation_metadata']['average_latency_ms']:.2f}ms")
    print(f"  Results saved to: {output_path}")
    
    return output_data


def generate_confusion_matrix_from_live_outputs(output_file: str = "evals/live_model_outputs.json") -> dict:
    """Generate confusion matrix and metrics from live model outputs."""
    data = json.loads((ROOT / output_file).read_text(encoding="utf-8"))
    
    if not data["results"]:
        print("No results to analyze")
        return {}
    
    # Import decision engine components
    from app.services.decision_engine import decide
    from app.services.hard_gate import evaluate_hard_constraints
    from app.services.semantic_scorer import assess_semantic_constraints
    from app.db.models import Mandate, Product
    from datetime import timedelta
    from scripts.run_eval import FixtureModel, mandate_for, product_for
    
    # Create baseline mandate and product for hard gate
    mandate = mandate_for({})
    product = product_for({})
    hard_pass = evaluate_hard_constraints(mandate, product, 1, "live-eval", datetime.now(timezone.utc))
    
    # Metrics
    tp = fp = tn = fn = 0
    decisions_by_expected = {}
    
    for result in data["results"]:
        # Convert raw model output to assessment
        assessment = assess_semantic_constraints(
            result["instruction"],
            [result["constraint"]],
            result["evidence"],
            FixtureModel(result["raw_model_output"]),
            confidence_threshold=0.85
        )
        
        decision = decide(hard_pass, assessment)
        actual = decision.decision.value
        expected = result["expected_decision"]
        
        # Track decisions
        if expected not in decisions_by_expected:
            decisions_by_expected[expected] = {}
        if actual not in decisions_by_expected[expected]:
            decisions_by_expected[expected][actual] = 0
        decisions_by_expected[expected][actual] += 1
        
        # Confusion matrix
        if expected == "ALLOW" and actual == "ALLOW":
            tp += 1
        elif expected != "ALLOW" and actual == "ALLOW":
            fp += 1
        elif expected != "ALLOW" and actual == "STEP_UP":
            tn += 1
        elif expected == "ALLOW" and actual == "STEP_UP":
            fn += 1
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    false_allow_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    correct_escalation_rate = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    
    metrics = {
        "confusion_matrix": {
            "true_positives_allow": tp,
            "false_positives_unsafe_allow": fp,
            "true_negatives_correct_stepup": tn,
            "false_negatives_over_escalation": fn
        },
        "metrics": {
            "autonomous_precision": round(precision, 4),
            "autonomous_recall": round(recall, 4),
            "false_autonomous_allow_rate": round(false_allow_rate, 4),
            "correct_escalation_rate": round(correct_escalation_rate, 4)
        },
        "decisions_by_expected": decisions_by_expected
    }
    
    # Save metrics
    metrics_file = ROOT / "evals/live_model_metrics.json"
    metrics_file.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    
    print("=" * 70)
    print("CONFUSION MATRIX & METRICS FROM LIVE MODEL OUTPUTS")
    print("=" * 70)
    print(f"True Positives (Correct ALLOW):       {tp}")
    print(f"False Positives (Unsafe ALLOW):       {fp}")
    print(f"True Negatives (Correct STEP_UP):     {tn}")
    print(f"False Negatives (Over-escalation):    {fn}")
    print()
    print(f"Autonomous Precision:                 {precision:.1%}")
    print(f"Autonomous Recall:                    {recall:.1%}")
    print(f"False Autonomous Allow Rate:          {false_allow_rate:.1%} (TARGET: 0.0%)")
    print(f"Correct Escalation Rate:              {correct_escalation_rate:.1%}")
    print(f"Metrics saved to: {metrics_file}")
    
    return metrics


def generate_threshold_metrics(output_file: str = "evals/live_model_outputs.json") -> dict:
    """Generate metrics across different confidence thresholds."""
    data = json.loads((ROOT / output_file).read_text(encoding="utf-8"))
    
    if not data["results"]:
        print("No results to analyze")
        return {}
    
    from app.services.decision_engine import decide
    from app.services.hard_gate import evaluate_hard_constraints
    from app.services.semantic_scorer import assess_semantic_constraints
    from scripts.run_eval import FixtureModel, mandate_for, product_for
    from datetime import datetime, timezone
    
    mandate = mandate_for({})
    product = product_for({})
    hard_pass = evaluate_hard_constraints(mandate, product, 1, "threshold-eval", datetime.now(timezone.utc))
    
    threshold_results = {}
    
    for threshold in [0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]:
        tp = fp = tn = fn = 0
        
        for result in data["results"]:
            assessment = assess_semantic_constraints(
                result["instruction"],
                [result["constraint"]],
                result["evidence"],
                FixtureModel(result["raw_model_output"]),
                confidence_threshold=threshold
            )
            
            decision = decide(hard_pass, assessment)
            actual = decision.decision.value
            expected = result["expected_decision"]
            
            if expected == "ALLOW" and actual == "ALLOW":
                tp += 1
            elif expected != "ALLOW" and actual == "ALLOW":
                fp += 1
            elif expected != "ALLOW" and actual == "STEP_UP":
                tn += 1
            elif expected == "ALLOW" and actual == "STEP_UP":
                fn += 1
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        false_allow_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        
        threshold_results[f"threshold_{threshold:.2f}"] = {
            "threshold": threshold,
            "true_positives_allow": tp,
            "false_positives_unsafe_allow": fp,
            "true_negatives_correct_stepup": tn,
            "false_negatives_over_escalation": fn,
            "autonomous_precision": round(precision, 4),
            "autonomous_recall": round(recall, 4),
            "false_autonomous_allow_rate": round(false_allow_rate, 4)
        }
    
    # Save threshold metrics
    threshold_file = ROOT / "evals/threshold_metrics.json"
    threshold_file.write_text(json.dumps(threshold_results, indent=2, ensure_ascii=False), encoding="utf-8")
    
    print("=" * 70)
    print("THRESHOLD ANALYSIS")
    print("=" * 70)
    for thresh_key, metrics in threshold_results.items():
        print(f"{thresh_key}: Precision={metrics['autonomous_precision']:.1%}, "
              f"Recall={metrics['autonomous_recall']:.1%}, "
              f"False Allow Rate={metrics['false_autonomous_allow_rate']:.1%}")
    
    print(f"Threshold metrics saved to: {threshold_file}")
    
    return threshold_results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run live model evaluation on semantic cases")
    parser.add_argument("--model", choices=["gemini", "vercel"], default="gemini", help="Model to use")
    parser.add_argument("--output", default="evals/live_model_outputs.json", help="Output file")
    parser.add_argument("--analyze-only", action="store_true", help="Only analyze existing outputs")
    parser.add_argument("--threshold-analysis", action="store_true", help="Generate threshold metrics")
    
    args = parser.parse_args()
    
    if args.analyze_only:
        generate_confusion_matrix_from_live_outputs(args.output)
        if args.threshold_analysis:
            generate_threshold_metrics(args.output)
    else:
        run_live_model_evaluation(args.model, args.output)
        generate_confusion_matrix_from_live_outputs(args.output)
        if args.threshold_analysis:
            generate_threshold_metrics(args.output)