# JANUS API Documentation

Base URL: `/api/v1`. Interactive OpenAPI documentation is published at `/docs`.

## Endpoint Summary

| Method | Path | Purpose |
|---|---|---|
| POST | `/mandates/compile` | Compiles raw natural-language delegation into hard and semantic constraints |
| POST | `/mandates` | Creates and cryptographically signs an active mandate (ECDSA P-256) |
| GET | `/mandates/{id}` | Retrieves signed mandate envelope and current lifecycle status |
| POST | `/mandates/{id}/revoke` | Instantly revokes an active mandate (human kill-switch) |
| GET | `/products` | Retrieves authoritative merchant catalog SKUs (tenant isolated) |
| POST | `/products/import` | Merchant catalog batch ingestion with schema validation |
| GET | `/products/metrics` | Real merchant telemetry: GMV, overspend prevention, P50/P95 latencies |
| POST | `/proposals` | Evaluates buyer checkout proposal through hard gate and semantic path |
| POST | `/proposals/autonomous-shop` | Six-stage autonomous buyer cycle: scan, evaluate all SKUs, rank, authorize |
| POST | `/proposals/{id}/execute` | Re-verifies constraints, reserves execution slot, creates Razorpay test order |
| POST | `/proposals/{id}/verify-payment` | Verifies server-side Razorpay HMAC signature and provider payment facts |
| GET | `/step-ups/{id}` | Retrieves escalated proposal facts and conflicting semantic evidence |
| POST | `/step-ups/{id}/approve` | Grants single-use human override for this exact proposal |
| POST | `/step-ups/{id}/reject` | Rejects proposal permanently with zero money moved |
| GET | `/audit` | Retrieves structured, immutable audit log events |

---

## Key Payloads & Lifecycles

### 1. Proposal Input (Merchant Authority Principle)

Agents never supply prices, currencies, or conditions. They submit only what they intend to buy:

```json
{
  "mandate_id": "mnd_8f3a9e2...",
  "mandate_version": 1,
  "product_id": "prod_a",
  "quantity": 1,
  "agent_request_id": "agent-session-001"
}
```

The gateway resolves pricing, currency, merchant ID, category, condition, and attributes exclusively from the merchant's authoritative catalog.

### 2. Six-Stage Autonomous Shopping Cycle

`POST /api/v1/proposals/autonomous-shop`

1. **Mandate Ingestion:** Extracts signed spending ceiling, currency, category, and semantic criteria.
2. **Catalog Scan:** Discovers machine-readable SKUs from merchant catalog (strict tenant isolation).
3. **Deterministic Hard Filtering:** Eliminates SKUs that violate amount, currency, category, or condition.
4. **LLM Semantic Evaluation:** Evaluates and scores EVERY remaining eligible candidate against fuzzy intent.
5. **Gateway Authorization:** Dispatches optimal candidate through formal decision engine.
6. **Razorpay Execution:** Secures atomic reservation and creates test-mode order (or step-up).

### 3. Server-Side Payment Verification

`POST /api/v1/proposals/{id}/verify-payment`

```json
{
  "razorpay_order_id": "order_TYLalcYGCbqDbY",
  "razorpay_payment_id": "pay_TYLbm3K8sPqX",
  "razorpay_signature": "e5b8d2..."
}
```

Validates:
1. `hmac_sha256(order_id + "|" + payment_id, secret) == signature`
2. Fetches payment from Razorpay API and confirms `order_id`, `amount`, `currency`, and `status == "captured"`.
3. Transitions proposal status to `PAID`.
4. Records `RAZORPAY_PAYMENT_VERIFIED` audit event.
