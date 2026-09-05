# Evaluation Results

Measured locally on 2026-09-05 with Python 3.11.6 across 81 systematic authorization & semantic boundary test cases.

```text
Hard-policy boundary cases:       35
Hard-policy correct:              35
Hard-policy accuracy:         100.0%

Semantic safety cases:            31
Semantic decisions correct:       31
Correct step-ups:                 21
False autonomous allows:           0
Safety precision:             100.0%

Adversarial injection cases:      15 / 15 blocked (100%)
Unauthorized executions:           0
Duplicate executions (x20 test):   0
P95 hard-gate latency:          0.50ms
```

Portable checkpoint: `50 passed, 3 skipped`. The skipped-by-default tests require PostgreSQL; all unit and integration tests pass without failure.

The semantic benchmark measures fine-grained attribute citations, travel constraints, office/professional settings, durability, comfort padding, acoustic profiles, and anti-hallucination guardrails (e.g. models citing non-existent merchant facts immediately fail safe to `STEP_UP`). Adversarial cases rigorously verify prompt injection defense, override keyword quarantine, markdown delimiter smuggling, and role spoofing attempts.

## Live Razorpay test-mode proof

Verified on 2026-09-05 through the production execution boundary, using runtime-only test credentials:

```text
Mandate signature:                 valid
Hard gate:                         PASS
Final decision:                    ALLOW
Razorpay order:                    order_TYLalcYGCbqDbY
Provider status:                   created
Amount:                            1849900 paise
Currency:                          INR
Receipt:                           prp_718442a40ccb4e8890802190e2d1d1e9
Same execution repeated:           20 times
Unique Razorpay order IDs:         1
Blocked proposal receipts found:   0
```

The order was independently fetched from Razorpay after creation. The recent provider window contained exactly that JANUS receipt; the amount-limit, semantic step-up/rejection, and revoked-mandate receipts were absent. No credential value is stored in the repository.
