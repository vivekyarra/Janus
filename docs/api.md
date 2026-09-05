# JANUS API

Base: `/api/v1`. FastAPI publishes `/docs` and `/openapi.json`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/mandates/compile` | Compile explicit authority; ambiguity stays unresolved |
| POST | `/mandates` | Human-reviewed signing |
| GET | `/mandates/{id}` | Signed authority and live state |
| POST | `/mandates/{id}/revoke` | Lock and revoke |
| GET | `/products` | Merchant catalog |
| POST | `/proposals` | Hard gate, semantic path, final decision |
| POST | `/proposals/{id}/execute` | Re-check, reserve, create test order |
| GET | `/step-ups/{id}` | Bound escalation evidence |
| POST | `/step-ups/{id}/approve` | Approve this proposal once |
| POST | `/step-ups/{id}/reject` | Reject with zero payment |
| GET | `/audit` | Structured event list |

Narrow proposal input:

```json
{"mandate_id":"mnd_...","mandate_version":1,"product_id":"prod_a","quantity":1,"agent_request_id":"buyer-session-001"}
```

The backend derives price, currency, merchant, category, condition, and attributes. A hard failure includes each executed check, exact expected/actual values, authoritative source, stable reason code, and `razorpay_called: false`.

