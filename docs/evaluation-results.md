# Evaluation Results

Last verified locally: 2026-09-05.

## Deterministic authorization harness

`python scripts/run_eval.py` completed successfully with the following measured output:

```text
Hard-policy cases:              100 / 100 correct (100.0%)
Hard-gate latency:              P50 0.34 ms, P95 0.61 ms

Labeled semantic fixtures:      200 / 200 policy outcomes matched
False autonomous allows:          0
Required step-ups:              127

Counterfactual pairs:            25 / 25 decision flips correct
Prompt-injection attempts:       50 / 50 quarantined
End-to-end buyer scenarios:      25 / 25 correct
Replay test:                      1 execution, 19 duplicates blocked
Unauthorized orders:              0
```

The semantic section of this command uses deliberately labeled fixture outputs to verify JANUS policy mapping. It is not a measurement of an external model.

## Automated test suite

`python -m pytest backend/tests -q` completed with **72 passed, 6 skipped**. Four skipped tests require `JANUS_POSTGRES_TEST_URL`; two additionally require `REQUIRE_REAL_RAZORPAY=true`. They were not represented as passing.

`npm run build --prefix frontend` completed successfully.

## Live-model benchmark status

The live Gemini benchmark completed **200 / 200** cases with `gemini-3.1-flash-lite`. At the current 0.85 self-reported-confidence abstention threshold it exposed **5 unsafe autonomous allows** (3.94% of non-allow cases). At an exploratory conservative **0.95** threshold, the same corpus measured **0 unsafe autonomous allows**, **56 correct autonomous allows**, **127 correct step-ups**, and **17 over-escalations** (76.7% autonomous recall). This is a model-and-corpus-specific safety result, not a claim of calibration or universal model performance. A production threshold change needs a deliberate configuration change and regression review; JANUS must not claim zero live-model unsafe allows at its current setting.

To produce a report with a valid configured credential:

```powershell
$env:GEMINI_API_KEY = '...'
$env:GEMINI_MODEL = 'gemini-3.1-flash-lite'
.\\.venv\\Scripts\\python scripts\\run_live_model_eval.py --model gemini --output evals\\live_gemini_outputs.json
```

The command exits non-zero and refuses analysis if any case is missing or failed. The completed raw output, metrics, and threshold artifacts are versioned under `evals/`.

## Scope of the evidence

These results demonstrate deterministic authorization, fail-closed semantic routing, injected-product-text quarantine, replay resistance, and one provenance-bound live model evaluation. They do not establish production readiness or full AP2/ACP/x402 conformance.
