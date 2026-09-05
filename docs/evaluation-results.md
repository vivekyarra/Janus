# Evaluation Results

Measured locally on 2026-09-05 with Python 3.11.6. These are synthetic safety-pipeline cases, not population-level model accuracy claims.

```text
Hard-policy cases:                12
Hard-policy correct:              12
Hard-policy accuracy:         100.0%
Semantic safety cases:             8
Semantic decisions correct:        8
Correct step-ups:                   6
False autonomous allows:           0
Adversarial cases blocked:         3/3
Unauthorized executions:           0
Duplicate executions (x20 test):   0
P95 hard-gate latency:           3.47ms
```

Portable checkpoint: `35 passed, 3 skipped`. The skipped-by-default tests require PostgreSQL; with `JANUS_POSTGRES_TEST_URL` set, all three passed in the same build session: reservation-first, revocation-first, and two simultaneous executions producing one order.

The semantic set measures post-model safety: schema handling, evidence validation, decision mapping, injection quarantine, and escalation. Live model results require AI Gateway credentials and must be reported separately.

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
