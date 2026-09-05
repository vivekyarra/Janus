# MANDATE FIREWALL *(Working Title — Might Change Later)*

## Final Project Specification — Razorpay AI Buildathon

> **Track:** 01 — AI Growth & Agentic Commerce  
> **Project status:** Finalized for build  
> **Primary objective:** Make a merchant safely transactable by an autonomous AI buyer while ensuring that no Razorpay money action can exceed the human principal's delegated authority.  
> **Design philosophy:** Minimal surface area, maximum correctness. AI is used only where semantics require judgment. All irreversible money gates remain deterministic.

---

# 0. Executive Summary

An AI buyer should not be trusted merely because it says, “the user asked me to buy this.”

The merchant needs an independent authorization boundary.

**MANDATE FIREWALL** is that boundary.

A human issues a signed purchase mandate containing:

1. **Hard constraints** — exact limits that can be deterministically verified:
   - maximum amount;
   - merchant;
   - category;
   - currency;
   - quantity;
   - expiry;
   - execution count;
   - revocation state.

2. **Semantic intent** — fuzzy human requirements that cannot be proved exactly:
   - “not flashy”;
   - “good for an interview”;
   - “comfortable for travel”;
   - “premium but not extravagant”.

When an AI buyer proposes a checkout:

- hard limits are checked deterministically;
- semantic intent is assessed separately using merchant-controlled evidence;
- hard failure = **BLOCK**;
- semantic uncertainty = **STEP_UP** to the human;
- both clear = **ALLOW**;
- only an allowed transaction is permitted to create a Razorpay test-mode order;
- every decision is written to a structured audit log;
- a revoked mandate cannot authorize a subsequent execution.

The project is intentionally narrow.

It is not an agent platform, recommendation system, checkout redesign, fraud engine, payment orchestrator, or general-purpose policy framework.

Its sole job is:

> **Decide whether an AI-generated checkout is within the human's delegated authority before Razorpay is allowed to execute it.**

---

# 1. Buildathon Positioning

## 1.1 Track

**Track 01 — AI Growth & Agentic Commerce**

The product should be positioned as **commerce enablement**, not primarily as fraud prevention.

The value proposition:

> Merchants can safely accept autonomous AI-buyer transactions instead of forcing every AI-assisted purchase back into a human checkout.

The core business metric is:

```text
Safe Autonomous Completion Rate
```

The core safety metric is:

```text
Unauthorized Execution Rate
```

Target safety outcome:

```text
Unauthorized Execution Rate = 0
```

---

# 2. Final One-Sentence Pitch

> **A merchant-side authorization gateway that deterministically enforces a human's signed hard purchase limits, separately assesses whether an AI-generated checkout is semantically consistent with the human's delegated intent, and allows Razorpay execution only when both paths clear; violations block, ambiguity escalates to the human, and revocation stops subsequent execution.**

---

# 3. Core Product Thesis

There are two fundamentally different authorization problems.

They must never be represented as if they have the same certainty.

## 3.1 Hard Authority — VERIFIED

Hard authority is exact.

Examples:

```text
amount <= ₹20,000
merchant = merchant_demo_01
category = headphones
currency = INR
quantity <= 1
expires_at > now
mandate_status = ACTIVE
execution_count < max_executions
```

These are handled entirely by deterministic code.

Output:

```text
PASS
FAIL
```

No model call.

No semantic guess.

No confidence score.

No LLM is allowed to override these results.

---

## 3.2 Semantic Intent — ASSESSED

Semantic intent is fuzzy.

Examples:

```text
"nothing flashy"
"appropriate for an interview"
"travel friendly"
"premium but not extravagant"
"comfortable"
"minimal design"
```

These are not “verified.”

They are assessed using merchant-controlled evidence.

Output:

```text
SUPPORTED
CONTRADICTED
INSUFFICIENT_EVIDENCE
```

Important rule:

```text
INSUFFICIENT_EVIDENCE != PASS
```

Ambiguity must result in human step-up.

---

# 4. Design Principles

The team must preserve these principles even if implementation details change.

## 4.1 AI proposes interpretation; AI does not control money

AI may:

- parse human natural language;
- extract semantic criteria;
- assess fuzzy product compatibility;
- produce human-readable explanations.

AI may not:

- override a hard amount limit;
- ignore expiry;
- ignore merchant restrictions;
- bypass revocation;
- bypass execution count;
- directly call Razorpay without the deterministic gate.

---

## 4.2 Human authority must be inspectable

Before signing, the human must be shown the normalized mandate.

Example:

```text
Maximum spend      ₹20,000
Merchant           Demo Electronics
Category           Headphones
Quantity           1
Expiry             2 hours
Condition          New only

Semantic intent:
- Sony preferred
- Suitable for travel
```

The final object that the human authorizes is what later governs execution.

---

## 4.3 Merchant-controlled evidence wins over agent claims

Never trust product facts from the AI buyer when the merchant already owns canonical data.

Bad:

```json
{
  "category": "headphones",
  "condition": "new"
}
```

if supplied only by the agent.

Preferred:

```text
agent proposes product_id
      ↓
merchant catalog resolves product_id
      ↓
canonical category / condition / price / attributes
```

---

## 4.4 Unknown must remain unknown

If evidence is missing:

```text
"ethically sourced"
```

and the merchant catalog contains no sourcing information:

```text
INSUFFICIENT_EVIDENCE
→ STEP_UP
```

Never infer favorable compliance from missing data.

---

## 4.5 Fail closed before money movement

If the gate cannot establish authorization because of:

- signature failure;
- database failure;
- revocation lookup failure;
- malformed mandate;
- missing required hard constraint;
- unknown execution state;

then:

```text
DO NOT CALL RAZORPAY
```

---

## 4.6 Minimal architecture

Use as few components as possible.

Avoid:

- Kafka;
- microservices;
- blockchain;
- vector databases unless truly necessary;
- multi-agent frameworks;
- orchestration frameworks for simple flows;
- unnecessary distributed systems.

A single well-structured backend is preferred.

---

# 5. System Actors

## 5.1 Human Principal

The actual user delegating authority.

Responsibilities:

- provides natural-language instruction;
- reviews compiled mandate;
- signs/approves mandate;
- may revoke mandate;
- handles step-up decisions.

---

## 5.2 AI Buyer

A simulated or real AI agent proposing a checkout.

Responsibilities:

- submits a checkout proposal;
- supplies intended product selection;
- never decides its own authorization.

For the hackathon, the buyer agent may be a lightweight simulator.

Do not waste build time creating a complex autonomous buyer.

---

## 5.3 Merchant

Owns:

- product catalog;
- product attributes;
- merchant ID;
- prices;
- checkout creation;
- Razorpay integration;
- firewall.

---

## 5.4 Mandate Firewall

The core system.

Responsibilities:

- parse and validate mandate;
- verify signature;
- check expiry;
- check revocation;
- enforce hard constraints;
- resolve merchant-owned product facts;
- run semantic assessment;
- produce final decision;
- gate Razorpay order creation;
- write structured audit events.

---

## 5.5 Razorpay

Used in test mode.

The firewall must be positioned directly before the Razorpay order/payment creation path.

No order should be created if authorization fails.

---

# 6. End-to-End User Flow

```text
HUMAN
  |
  | "Buy noise-cancelling headphones under ₹20k.
  |  Sony preferred. Nothing refurbished.
  |  Delivery within 3 days."
  v
INTENT COMPILER
  |
  | proposes hard + semantic constraints
  v
HUMAN REVIEW
  |
  | approve/sign
  v
SIGNED MANDATE
  |
  | mandate_id
  v
AI BUYER
  |
  | proposes product + checkout
  v
FIREWALL
  |
  +---- HARD GATE
  |
  +---- SEMANTIC ASSESSMENT
  |
  v
DECISION
  |
  +---- ALLOW ----> RAZORPAY TEST ORDER
  |
  +---- BLOCK ----> ₹0 moved
  |
  +---- STEP_UP --> HUMAN
                     |
                     +--- APPROVE ONCE --> RAZORPAY
                     |
                     +--- REJECT -------> BLOCK
  |
  v
AUDIT LOG
```

---

# 7. Mandate Issuance

## 7.1 Input

Human instruction:

```text
Buy noise-cancelling headphones under ₹20,000.
Sony preferred.
Nothing refurbished.
Delivery within 3 days.
```

---

## 7.2 Intent Compiler Output

The compiler returns a structured proposal.

Example:

```json
{
  "hard_constraints": {
    "currency": "INR",
    "max_amount_paise": 2000000,
    "allowed_merchant_ids": ["merchant_demo_01"],
    "allowed_categories": ["headphones"],
    "max_quantity": 1,
    "condition": "new"
  },
  "semantic_constraints": [
    {
      "id": "sem_01",
      "claim": "Sony preferred",
      "policy": "step_up_if_contradicted"
    },
    {
      "id": "sem_02",
      "claim": "suitable for travel",
      "policy": "step_up_if_unknown"
    }
  ]
}
```

---

## 7.3 Human Review

The UI must show the normalized mandate before approval.

The human may:

```text
APPROVE
EDIT
CANCEL
```

No mandate becomes active until approved.

---

# 8. Final Mandate Schema

Recommended schema:

```json
{
  "mandate_id": "mnd_01JXYZ",
  "principal_id": "usr_demo_001",

  "issued_at": "2026-09-05T10:00:00Z",
  "expires_at": "2026-09-05T12:00:00Z",

  "instruction_text": "Buy noise-cancelling headphones under ₹20,000. Sony preferred. Nothing refurbished. Delivery within 3 days.",

  "hard_constraints": {
    "currency": "INR",
    "max_amount_paise": 2000000,
    "allowed_merchant_ids": ["merchant_demo_01"],
    "allowed_categories": ["headphones"],
    "max_quantity": 1,
    "condition": "new"
  },

  "semantic_constraints": [
    {
      "id": "sem_01",
      "claim": "Sony preferred",
      "policy": "step_up_if_contradicted"
    },
    {
      "id": "sem_02",
      "claim": "suitable for travel",
      "policy": "step_up_if_unknown"
    }
  ],

  "execution_policy": {
    "single_use": true,
    "max_executions": 1
  },

  "version": 1,
  "status": "ACTIVE",
  "signature_alg": "ES256",
  "signature": "..."
}
```

---

# 9. Database Model

Use PostgreSQL.

SQLite is acceptable for a local prototype, but PostgreSQL is preferred for the final demo because row locking and concurrent state transitions matter.

## 9.1 `mandates`

```sql
CREATE TABLE mandates (
    mandate_id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL,

    instruction_text TEXT NOT NULL,

    hard_constraints JSONB NOT NULL,
    semantic_constraints JSONB NOT NULL,
    execution_policy JSONB NOT NULL,

    issued_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,

    status TEXT NOT NULL CHECK (
        status IN ('ACTIVE', 'REVOKED', 'EXPIRED', 'CONSUMED')
    ),

    version INTEGER NOT NULL DEFAULT 1,
    execution_count INTEGER NOT NULL DEFAULT 0,

    signature_alg TEXT NOT NULL,
    signature TEXT NOT NULL,

    revoked_at TIMESTAMPTZ NULL,
    consumed_at TIMESTAMPTZ NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 9.2 `products`

```sql
CREATE TABLE products (
    product_id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    canonical_category TEXT NOT NULL,
    currency TEXT NOT NULL,
    amount_paise BIGINT NOT NULL,
    condition TEXT NOT NULL,
    attributes JSONB NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);
```

Example attributes:

```json
{
  "brand": "Sony",
  "noise_cancelling": true,
  "weight_grams": 254,
  "foldable": true,
  "battery_hours": 30,
  "travel_case": true,
  "color": "black",
  "style_tags": ["minimal", "professional"]
}
```

---

## 9.3 `checkout_proposals`

```sql
CREATE TABLE checkout_proposals (
    proposal_id TEXT PRIMARY KEY,
    mandate_id TEXT NOT NULL REFERENCES mandates(mandate_id),
    product_id TEXT NOT NULL REFERENCES products(product_id),

    quantity INTEGER NOT NULL,
    merchant_id TEXT NOT NULL,

    expected_amount_paise BIGINT NOT NULL,
    currency TEXT NOT NULL,

    idempotency_key TEXT NOT NULL UNIQUE,

    status TEXT NOT NULL CHECK (
        status IN (
            'PENDING',
            'ALLOWED',
            'BLOCKED',
            'STEP_UP',
            'EXECUTING',
            'EXECUTED',
            'FAILED'
        )
    ),

    razorpay_order_id TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 9.4 `audit_events`

```sql
CREATE TABLE audit_events (
    audit_id BIGSERIAL PRIMARY KEY,

    mandate_id TEXT NOT NULL,
    proposal_id TEXT NULL,

    event_type TEXT NOT NULL,
    decision TEXT NULL,

    payload JSONB NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 9.5 `step_up_requests`

```sql
CREATE TABLE step_up_requests (
    step_up_id TEXT PRIMARY KEY,
    mandate_id TEXT NOT NULL,
    proposal_id TEXT NOT NULL,

    reason TEXT NOT NULL,
    semantic_result JSONB NOT NULL,

    status TEXT NOT NULL CHECK (
        status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED')
    ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ NULL
);
```

---

# 10. Signing Strategy

## 10.1 Preferred

Use WebAuthn/passkey for user approval.

Flow:

```text
canonical mandate
      ↓
hash
      ↓
WebAuthn challenge
      ↓
human confirms using passkey
      ↓
signed authorization
```

---

## 10.2 Hackathon fallback

If WebAuthn causes implementation risk:

Use ECDSA over a demo user keypair.

Still preserve:

- deterministic canonicalization;
- signature verification;
- clear statement that production identity binding would use passkeys/WebAuthn.

Do not pretend a locally generated test key proves real-world identity.

---

# 11. Canonicalization

Never sign arbitrary JSON stringification.

The canonical bytes must be deterministic.

Recommended approach:

1. exclude mutable server fields:
   - status;
   - execution_count;
   - revoked_at;
   - consumed_at;
2. sort object keys;
3. serialize without whitespace variation;
4. UTF-8 encode;
5. SHA-256 hash;
6. sign hash.

Pseudo-code:

```python
def canonical_payload(mandate):
    signed_fields = {
        "mandate_id": mandate["mandate_id"],
        "principal_id": mandate["principal_id"],
        "instruction_text": mandate["instruction_text"],
        "hard_constraints": mandate["hard_constraints"],
        "semantic_constraints": mandate["semantic_constraints"],
        "execution_policy": mandate["execution_policy"],
        "issued_at": mandate["issued_at"],
        "expires_at": mandate["expires_at"],
        "version": mandate["version"]
    }
    return canonical_json(signed_fields)

digest = sha256(canonical_payload(mandate))
signature = sign(private_key, digest)
```

---

# 12. Hard Gate

This is the most important component.

Build this before the semantic scorer.

## 12.1 Required Checks

Recommended order:

```text
1. mandate_exists
2. signature_valid
3. mandate_status_active
4. not_expired
5. version_current
6. idempotency_unused
7. merchant_allowed
8. currency_allowed
9. category_allowed
10. condition_allowed
11. quantity_within_limit
12. amount_within_limit
13. execution_count_available
```

---

## 12.2 Hard Check Contract

Each check emits:

```json
{
  "name": "amount_within_limit",
  "passed": true,
  "expected": {
    "operator": "<=",
    "value": 2000000
  },
  "actual": 1849900,
  "source": "merchant_checkout"
}
```

---

## 12.3 Hard Gate Result

```json
{
  "status": "PASS",
  "checks": [
    {
      "name": "signature_valid",
      "passed": true
    },
    {
      "name": "amount_within_limit",
      "passed": true
    }
  ]
}
```

or:

```json
{
  "status": "FAIL",
  "reason_code": "AMOUNT_LIMIT_EXCEEDED",
  "checks": [...]
}
```

---

# 13. Semantic Assessment

Build this only after the deterministic pipeline is working.

## 13.1 Purpose

Assess soft human intent using merchant-controlled evidence.

This component must never override a hard gate failure.

---

## 13.2 Input Contract

```json
{
  "instruction_text": "Buy noise-cancelling headphones under ₹20,000. Sony preferred. Nothing refurbished. Delivery within 3 days.",
  "semantic_constraint": {
    "id": "sem_02",
    "claim": "suitable for travel",
    "policy": "step_up_if_unknown"
  },
  "product_evidence": {
    "name": "Sony Demo NC-1000",
    "brand": "Sony",
    "weight_grams": 254,
    "foldable": true,
    "noise_cancelling": true,
    "battery_hours": 30,
    "travel_case": true
  }
}
```

---

## 13.3 Output Contract

```json
{
  "constraint_id": "sem_02",
  "status": "SUPPORTED",
  "evidence": [
    {
      "field": "foldable",
      "value": true
    },
    {
      "field": "weight_grams",
      "value": 254
    },
    {
      "field": "travel_case",
      "value": true
    }
  ],
  "reason": "Available product attributes support portability for travel."
}
```

Allowed statuses:

```text
SUPPORTED
CONTRADICTED
INSUFFICIENT_EVIDENCE
```

---

## 13.4 Semantic Decision Rules

Recommended:

```text
all semantic constraints SUPPORTED
→ semantic path PASS

any required semantic constraint CONTRADICTED
→ STEP_UP

any required semantic constraint INSUFFICIENT_EVIDENCE
→ STEP_UP
```

For the buildathon, prefer STEP_UP over semantic auto-block.

Why:

- it demonstrates graceful uncertainty;
- it reduces false-negative commerce loss;
- it keeps humans in control of ambiguous decisions.

---

# 14. Final Decision Engine

Exact decision table:

| Hard Gate | Semantic Path | Result |
|---|---|---|
| FAIL | not run / irrelevant | BLOCK |
| PASS | SUPPORTED | ALLOW |
| PASS | CONTRADICTED | STEP_UP |
| PASS | INSUFFICIENT_EVIDENCE | STEP_UP |
| ERROR | any | BLOCK |
| PASS | semantic service unavailable | STEP_UP or BLOCK based on configured fail policy |

Recommended demo policy:

```text
semantic service unavailable
→ STEP_UP
```

Do not silently allow.

---

# 15. Step-Up Flow

A step-up is not a failure of the system.

It is a designed outcome.

Example UI:

```text
HUMAN CONFIRMATION REQUIRED

Mandate:
Buy formal interview shoes under ₹8,000.
Nothing flashy.

Proposed:
Gold metallic party-style loafer
₹6,999

Hard checks:
✓ amount
✓ merchant
✓ category
✓ expiry

Semantic assessment:
! "nothing flashy" → CONTRADICTED

Evidence:
- color: metallic gold
- collection: party
- finish: reflective

[ APPROVE ONCE ]
[ REJECT ]
```

---

## 15.1 Approve Once

Do not mutate the original mandate.

Create a one-time approval record bound to:

```text
proposal_id
mandate_id
product_id
amount
```

Then execute only that proposal.

---

## 15.2 Reject

Set:

```text
proposal.status = BLOCKED
step_up.status = REJECTED
```

No Razorpay order.

---

# 16. Revocation

Revocation is a core demo feature.

## 16.1 API

```text
POST /mandates/{mandate_id}/revoke
```

Result:

```json
{
  "mandate_id": "mnd_01JXYZ",
  "status": "REVOKED",
  "revoked_at": "..."
}
```

---

## 16.2 Gate Rule

Every execution attempt must re-check mandate state immediately before reserving execution.

A signed credential remaining mathematically valid does not mean it remains authorized.

Authorization is:

```text
signature valid
AND
status == ACTIVE
AND
not expired
AND
execution policy available
```

---

# 17. Revocation Race Semantics

Do not claim “instant revocation” without defining concurrency behavior.

Use a database transaction.

Recommended execution reservation:

```sql
BEGIN;

SELECT *
FROM mandates
WHERE mandate_id = $1
FOR UPDATE;

-- Verify status, expiry, version, execution count

-- If valid:
UPDATE mandates
SET execution_count = execution_count + 1
WHERE mandate_id = $1;

UPDATE checkout_proposals
SET status = 'EXECUTING'
WHERE proposal_id = $2;

COMMIT;
```

Revocation:

```sql
BEGIN;

SELECT *
FROM mandates
WHERE mandate_id = $1
FOR UPDATE;

UPDATE mandates
SET status = 'REVOKED',
    revoked_at = NOW(),
    version = version + 1
WHERE mandate_id = $1;

COMMIT;
```

This produces a deterministic ordering.

Whichever transaction acquires the row lock first wins.

Document this clearly.

---

# 18. Idempotency

Every checkout proposal must have an idempotency key.

Example:

```text
sha256(
    mandate_id +
    product_id +
    quantity +
    amount +
    agent_request_id
)
```

The database must enforce uniqueness.

Repeated requests:

```text
same idempotency key
→ return original decision
→ never create another Razorpay order
```

Required adversarial test:

```text
send same allowed request 20 times
```

Expected:

```text
1 execution
19 duplicate responses
0 duplicate Razorpay orders
```

---

# 19. Razorpay Integration

Use Razorpay test mode.

## 19.1 Gate Placement

Correct:

```text
checkout proposal
    ↓
Mandate Firewall
    ↓
ALLOW
    ↓
Razorpay order creation
```

Incorrect:

```text
Razorpay order created
    ↓
firewall checks afterward
```

---

## 19.2 Razorpay Order Creation

Backend adapter:

```python
def create_razorpay_order(amount_paise, currency, receipt):
    return razorpay_client.order.create({
        "amount": amount_paise,
        "currency": currency,
        "receipt": receipt
    })
```

This function must only be reachable from the execution service after an ALLOW or approved STEP_UP.

---

## 19.3 Execution Guard

Pseudo-code:

```python
def execute_proposal(proposal_id):
    decision = evaluate_proposal(proposal_id)

    if decision.type != "ALLOW":
        raise AuthorizationDenied()

    reservation = reserve_execution_atomically(proposal_id)

    if not reservation.ok:
        raise AuthorizationDenied()

    order = create_razorpay_order(
        amount_paise=reservation.amount_paise,
        currency=reservation.currency,
        receipt=reservation.proposal_id
    )

    persist_order(order)
    return order
```

---

# 20. Audit Trail

The audit trail is a product feature, not debug logging.

Every meaningful state transition should write one structured event.

## 20.1 Event Types

Minimum:

```text
MANDATE_CREATED
MANDATE_SIGNED
MANDATE_REVOKED
PROPOSAL_RECEIVED
HARD_GATE_PASSED
HARD_GATE_FAILED
SEMANTIC_ASSESSMENT_COMPLETED
STEP_UP_REQUESTED
STEP_UP_APPROVED
STEP_UP_REJECTED
EXECUTION_RESERVED
RAZORPAY_ORDER_CREATED
EXECUTION_BLOCKED
DUPLICATE_REQUEST_REJECTED
```

---

## 20.2 Audit Event Shape

```json
{
  "audit_id": 1042,
  "mandate_id": "mnd_01JXYZ",
  "proposal_id": "prp_01JABC",

  "event_type": "HARD_GATE_FAILED",
  "decision": "BLOCK",

  "payload": {
    "reason_code": "AMOUNT_LIMIT_EXCEEDED",
    "checks": [
      {
        "name": "amount_within_limit",
        "passed": false,
        "expected": "<= 2000000",
        "actual": 2149900
      }
    ]
  },

  "created_at": "2026-09-05T10:31:54.123Z"
}
```

---

# 21. API Specification

Use FastAPI.

Base:

```text
/api/v1
```

## 21.1 Create Draft Mandate

```http
POST /api/v1/mandates/compile
```

Request:

```json
{
  "principal_id": "usr_demo_001",
  "instruction_text": "Buy noise-cancelling headphones under ₹20,000...",
  "merchant_id": "merchant_demo_01"
}
```

Response:

```json
{
  "draft_id": "draft_01",
  "hard_constraints": {...},
  "semantic_constraints": [...]
}
```

---

## 21.2 Approve / Sign Mandate

```http
POST /api/v1/mandates
```

Request contains:

```json
{
  "draft_id": "draft_01",
  "approved_constraints": {...},
  "authorization_assertion": {...}
}
```

Response:

```json
{
  "mandate_id": "mnd_01JXYZ",
  "status": "ACTIVE"
}
```

---

## 21.3 Fetch Mandate

```http
GET /api/v1/mandates/{mandate_id}
```

---

## 21.4 Revoke Mandate

```http
POST /api/v1/mandates/{mandate_id}/revoke
```

---

## 21.5 Submit Checkout Proposal

```http
POST /api/v1/proposals
```

Request:

```json
{
  "mandate_id": "mnd_01JXYZ",
  "product_id": "prod_sony_001",
  "quantity": 1,
  "agent_request_id": "agent_req_001"
}
```

Backend derives:

- price;
- category;
- condition;
- merchant;
- product attributes;

from merchant-owned data.

Response:

```json
{
  "proposal_id": "prp_01",
  "decision": "ALLOW",
  "hard_gate": {...},
  "semantic_result": {...}
}
```

---

## 21.6 Execute Proposal

```http
POST /api/v1/proposals/{proposal_id}/execute
```

Only succeeds if authorized.

---

## 21.7 Resolve Step-Up

Approve:

```http
POST /api/v1/step-ups/{step_up_id}/approve
```

Reject:

```http
POST /api/v1/step-ups/{step_up_id}/reject
```

---

## 21.8 Audit

```http
GET /api/v1/audit?mandate_id=...
```

---

# 22. Backend Module Structure

Recommended:

```text
backend/
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── mandates.py
│   │   ├── proposals.py
│   │   ├── stepups.py
│   │   └── audit.py
│   │
│   ├── domain/
│   │   ├── mandate.py
│   │   ├── proposal.py
│   │   ├── decision.py
│   │   └── audit_event.py
│   │
│   ├── services/
│   │   ├── intent_compiler.py
│   │   ├── signature_service.py
│   │   ├── hard_gate.py
│   │   ├── semantic_scorer.py
│   │   ├── decision_engine.py
│   │   ├── revocation_service.py
│   │   ├── execution_service.py
│   │   ├── stepup_service.py
│   │   └── audit_service.py
│   │
│   ├── integrations/
│   │   ├── razorpay_adapter.py
│   │   └── llm_adapter.py
│   │
│   ├── repositories/
│   │   ├── mandate_repository.py
│   │   ├── product_repository.py
│   │   ├── proposal_repository.py
│   │   └── audit_repository.py
│   │
│   ├── models/
│   │   └── db.py
│   │
│   └── config.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── adversarial/
│   └── fixtures/
│
├── requirements.txt
└── README.md
```

---

# 23. Frontend Structure

Recommended:

```text
frontend/
├── src/
│   ├── pages/
│   │   ├── IssueMandate.tsx
│   │   ├── MandateDetail.tsx
│   │   ├── AgentCheckout.tsx
│   │   ├── StepUp.tsx
│   │   └── AuditTrail.tsx
│   │
│   ├── components/
│   │   ├── ConstraintList.tsx
│   │   ├── DecisionBadge.tsx
│   │   ├── HardCheckTable.tsx
│   │   ├── SemanticEvidence.tsx
│   │   └── AuditTimeline.tsx
│   │
│   └── api/
│       └── client.ts
```

Use React/Next.js/Vite depending on team familiarity.

Do not over-invest in frontend architecture.

---

# 24. Recommended Tech Stack

## Backend

```text
Python 3.11+
FastAPI
Pydantic
SQLAlchemy
PostgreSQL
```

## AI

Any reliable structured-output model.

Requirements:

- JSON schema output;
- low temperature;
- deterministic prompt versioning where possible.

## Crypto

Preferred:

```text
WebAuthn/passkeys
```

Fallback:

```text
ECDSA / ES256
```

## Payments

```text
Razorpay Test Mode API
```

## Frontend

```text
React + TypeScript
```

---

# 25. AI Prompt Contract — Intent Compiler

System objective:

```text
Convert the human instruction into:
1. deterministic hard constraints only when explicitly supported;
2. semantic constraints for fuzzy requirements;
3. never invent authority;
4. ambiguous numerical authority must be returned as unresolved.
```

Expected output schema:

```json
{
  "hard_constraints": {},
  "semantic_constraints": [],
  "unresolved": []
}
```

Example rule:

Human:

```text
"Don't spend too much."
```

Do NOT produce:

```text
max_amount = ₹5000
```

Produce:

```json
{
  "unresolved": [
    {
      "field": "max_amount",
      "reason": "No explicit numerical spending limit was provided."
    }
  ]
}
```

The UI must require human clarification before the mandate can be signed.

---

# 26. AI Prompt Contract — Semantic Scorer

The scorer is evidence-grounded.

Rules:

```text
- Assess only the supplied semantic claim.
- Use only merchant-supplied product evidence.
- Do not infer missing attributes.
- Return SUPPORTED, CONTRADICTED, or INSUFFICIENT_EVIDENCE.
- Cite exact fields used as evidence.
- If evidence is insufficient, return INSUFFICIENT_EVIDENCE.
- Never authorize payment.
```

---

# 27. Decision Codes

Use stable machine-readable codes.

## Hard Failure Codes

```text
MANDATE_NOT_FOUND
SIGNATURE_INVALID
MANDATE_REVOKED
MANDATE_EXPIRED
MANDATE_CONSUMED
MANDATE_VERSION_STALE
MERCHANT_NOT_ALLOWED
CURRENCY_NOT_ALLOWED
CATEGORY_NOT_ALLOWED
CONDITION_NOT_ALLOWED
QUANTITY_EXCEEDED
AMOUNT_LIMIT_EXCEEDED
EXECUTION_LIMIT_EXCEEDED
DUPLICATE_REQUEST
PRODUCT_NOT_FOUND
PRODUCT_INACTIVE
```

## Semantic Codes

```text
SEMANTIC_SUPPORTED
SEMANTIC_CONTRADICTED
SEMANTIC_INSUFFICIENT_EVIDENCE
SEMANTIC_SERVICE_UNAVAILABLE
```

---

# 28. State Machines

## 28.1 Mandate

```text
DRAFT
  ↓
ACTIVE
  ├──→ REVOKED
  ├──→ EXPIRED
  └──→ CONSUMED
```

`CONSUMED` applies when:

```text
single_use = true
AND
successful execution reserved/completed
```

---

## 28.2 Proposal

```text
PENDING
   |
   +--> BLOCKED
   |
   +--> STEP_UP
   |       |
   |       +--> BLOCKED
   |       |
   |       +--> ALLOWED
   |
   +--> ALLOWED
           |
           v
       EXECUTING
           |
           +--> EXECUTED
           |
           +--> FAILED
```

---

# 29. Failure Policy

Every failure needs an explicit behavior.

| Failure | Required behavior |
|---|---|
| invalid signature | BLOCK |
| revoked mandate | BLOCK |
| expired mandate | BLOCK |
| hard limit violation | BLOCK |
| semantic contradiction | STEP_UP |
| missing semantic evidence | STEP_UP |
| semantic model timeout | STEP_UP |
| DB unavailable | BLOCK |
| Razorpay unavailable | preserve authorization state, do not create duplicate execution |
| duplicate request | return previous result |
| malformed product | BLOCK |
| stale mandate version | BLOCK |
| step-up expires | BLOCK |

---

# 30. Razorpay Failure Handling

If Razorpay order creation fails:

```text
authorization != payment success
```

Do not consume the mandate incorrectly unless the execution semantics explicitly say so.

Recommended:

```text
execution reservation
→ Razorpay call
→ if API failed before order creation:
      release reservation if safe
      keep audit
→ if order created:
      persist Razorpay order ID
```

For the hackathon, document the exact behavior.

Never retry blindly if you are uncertain whether an order was already created.

Use the proposal ID as the receipt/idempotency anchor where supported.

---

# 31. Test Strategy

Tests are part of the product signal.

The team must ship:

```text
unit tests
integration tests
adversarial tests
demo fixtures
```

---

# 32. Required Unit Tests

## Signature

```text
valid signature passes
modified amount breaks signature
modified category breaks signature
modified expiry breaks signature
wrong public key fails
```

## Hard Gate

```text
exact amount limit passes
amount limit + 1 paise fails
wrong merchant fails
wrong category fails
wrong currency fails
expired mandate fails
revoked mandate fails
quantity overflow fails
single-use consumed mandate fails
```

## Idempotency

```text
same request repeated returns same result
```

---

# 33. Required Integration Tests

1. Valid mandate → valid proposal → Razorpay order created.
2. Hard violation → Razorpay adapter never called.
3. Semantic contradiction → step-up created.
4. Step-up approved → Razorpay order created.
5. Step-up rejected → no Razorpay order.
6. Mandate revoked → valid-looking proposal blocked.
7. Duplicate allowed request → only one execution.
8. Semantic model unavailable → step-up.
9. Stale mandate version → block.
10. Product inactive → block.

---

# 34. Adversarial Test Matrix

Minimum recommended cases:

| # | Attack / Edge Case | Expected |
|---:|---|---|
| 1 | amount exactly at limit | allow |
| 2 | amount + ₹0.01 | block |
| 3 | wrong merchant | block |
| 4 | wrong category | block |
| 5 | modified signed mandate | block |
| 6 | expired mandate | block |
| 7 | revoked mandate | block |
| 8 | duplicate request x20 | one execution |
| 9 | stale mandate version | block |
| 10 | fake agent category | merchant catalog overrides |
| 11 | missing product evidence | step-up |
| 12 | semantic contradiction | step-up |
| 13 | valid semantic evidence | allow |
| 14 | prompt injection in product description | must not alter system policy |
| 15 | model returns malformed JSON | step-up |
| 16 | semantic service timeout | step-up |
| 17 | DB error | block |
| 18 | Razorpay API error | no duplicate order |
| 19 | revoke immediately before execute | deterministic lock ordering |
| 20 | execute immediately before revoke | execution ordering documented |

---

# 35. Evaluation Metrics

Do not fabricate values.

Run the test harness and report actual numbers.

## Core Metrics

```text
Hard-policy decision accuracy
Unauthorized execution count
Unauthorized execution rate
Safe autonomous completion rate
Step-up rate
Step-up approval rate
Duplicate execution count
Semantic false-allow count
Semantic over-escalation rate
P95 gate latency
```

Important metric:

```text
Semantic False-Allow Count
```

This should be zero in the evaluation set if possible.

A false escalation is preferable to an unauthorized automatic execution.

---

# 36. Demo Dataset

Create a small merchant catalog with deliberate edge cases.

Recommended category:

```text
headphones
```

Products:

### Product A — clearly valid

```text
Sony
₹18,499
new
noise cancelling
254g
foldable
travel case
black
```

### Product B — hard violation

```text
Sony
₹21,499
new
noise cancelling
```

### Product C — semantically questionable

```text
Bose
₹17,999
new
large/heavy
not foldable
```

### Product D — semantic contradiction

```text
Demo Brand
₹6,999
metallic gold
party collection
oversized branding
```

### Product E — missing evidence

```text
Demo Brand
₹7,499
category correct
attributes incomplete
```

---

# 37. Required Demo Beats

The pitch should show only the strongest cases.

## Demo Beat 1 — Valid Autonomous Execution

Human mandate:

```text
Buy noise-cancelling headphones under ₹20k.
Sony preferred.
Nothing refurbished.
Good for travel.
```

Agent proposes Product A.

Result:

```text
HARD GATE        PASS
SEMANTIC         SUPPORTED
FINAL            ALLOW
RAZORPAY ORDER   CREATED
```

This proves end-to-end commerce.

---

## Demo Beat 2 — Hard Violation

Agent proposes Product B.

```text
Mandate max      ₹20,000
Proposed         ₹21,499

HARD GATE        FAIL
FINAL            BLOCK
RAZORPAY         NOT CALLED
```

Audit line shows exact reason.

---

## Demo Beat 3 — Semantic Step-Up

Use an instruction containing a soft requirement.

Example:

```text
"Nothing flashy."
```

Proposed product:

```text
metallic gold
party collection
oversized branding
```

Result:

```text
HARD GATE        PASS
SEMANTIC         CONTRADICTED
FINAL            STEP_UP
```

Human:

```text
REJECT
```

No payment.

This is the key AI demo.

---

## Demo Beat 4 — Mid-Session Revocation

Mandate initially:

```text
ACTIVE
```

AI agent has an otherwise valid proposal.

Human clicks:

```text
REVOKE
```

Next execution attempt:

```text
MANDATE_REVOKED
FINAL            BLOCK
RAZORPAY         NOT CALLED
```

Audit shows revocation timestamp and blocked attempt.

---

# 38. UI Pages

Keep UI operational and information-dense.

## Page 1 — Issue Mandate

Show:

```text
Human instruction input
Compiled hard constraints
Compiled semantic constraints
Unresolved fields
Approve / Edit / Cancel
```

---

## Page 2 — Mandate Detail

Show:

```text
mandate ID
status
expiry
hard constraints
semantic constraints
signature status
execution count
revoke button
```

---

## Page 3 — Agent Checkout Simulator

Select:

```text
mandate
product
quantity
```

Button:

```text
PROPOSE CHECKOUT
```

Then show:

```text
hard decision
semantic decision
final decision
```

If ALLOW:

```text
EXECUTE THROUGH RAZORPAY
```

---

## Page 4 — Step-Up

Show:

```text
original instruction
proposed product
hard checks
semantic evidence
reason
approve once
reject
```

---

## Page 5 — Audit Trail

Chronological:

```text
10:02:01 MANDATE_SIGNED
10:03:11 PROPOSAL_RECEIVED
10:03:11 HARD_GATE_PASSED
10:03:12 SEMANTIC_ASSESSMENT_COMPLETED
10:03:12 STEP_UP_REQUESTED
10:03:19 STEP_UP_REJECTED
```

Each row expandable.

---

# 39. Frontend Visual Style

Avoid generic AI aesthetics.

Do not make the product look like a chatbot.

Recommended visual style:

```text
dark operational console
high information density
clean typography
clear PASS / BLOCK / STEP-UP states
timeline / event audit
minimal animation
```

Focus on:

```text
authorization
state
evidence
decision
money impact
```

---

# 40. Repo Structure

Recommended final repository:

```text
mandate-firewall/
├── README.md
├── PROJECT_SPEC.md
├── .env.example
├── docker-compose.yml
│
├── backend/
│   ├── app/
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   └── package.json
│
├── scripts/
│   ├── seed_catalog.py
│   ├── run_eval.py
│   └── demo_reset.py
│
├── evals/
│   ├── hard_cases.json
│   ├── semantic_cases.json
│   └── adversarial_cases.json
│
├── docs/
│   ├── architecture.md
│   ├── threat-model.md
│   ├── demo-script.md
│   └── api.md
│
└── screenshots/
```

---

# 41. `.env.example`

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mandate_firewall

RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=

LLM_API_KEY=
LLM_MODEL=

APP_ENV=development
BASE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000

SIGNING_MODE=demo_ecdsa
```

Never commit real secrets.

---

# 42. Implementation Order

Do not reorder unless there is a blocking technical reason.

## Phase 1 — Data + Hard Spine

1. Create database models.
2. Seed merchant and products.
3. Implement mandate schema.
4. Implement deterministic canonicalization.
5. Implement signing / signature verification.
6. Implement hard gate.
7. Implement structured audit writes.
8. Unit test all hard checks.

Acceptance:

```text
valid proposal → PASS
hard violation → BLOCK
audit generated
```

---

## Phase 2 — Razorpay End-to-End

9. Add Razorpay test-mode adapter.
10. Add execution endpoint.
11. Ensure Razorpay function cannot be called after BLOCK.
12. Implement idempotency.
13. Test duplicate requests.

Acceptance:

```text
valid request creates exactly one Razorpay order
invalid request creates zero Razorpay orders
```

---

## Phase 3 — Revocation

14. Add revoke endpoint.
15. Add row locking/version state.
16. Re-check mandate before execution reservation.
17. Add revocation audit events.
18. Test revoke/execute ordering.

Acceptance:

```text
revoked mandate cannot execute
```

---

## Phase 4 — Semantic AI

19. Implement intent compiler.
20. Add human mandate review screen.
21. Implement semantic scorer.
22. Enforce evidence-only reasoning.
23. Add SUPPORTED / CONTRADICTED / INSUFFICIENT_EVIDENCE outputs.
24. Add semantic audit events.

Acceptance:

```text
semantic uncertainty never auto-executes
```

---

## Phase 5 — Step-Up

25. Add step-up records.
26. Add approve-once flow.
27. Add reject flow.
28. Bind approval to a single proposal.
29. Test replay after approval.

Acceptance:

```text
step-up approval executes only intended proposal
```

---

## Phase 6 — Evaluation + Demo

30. Build adversarial fixture set.
31. Build evaluation script.
32. Record metrics.
33. Build audit UI.
34. Build final demo script.
35. Add architecture diagram.
36. Clean README.
37. Run full demo repeatedly from reset state.

---

# 43. Definition of Done

The project is submission-ready only if all are true:

## Core

- [ ] Human can issue a mandate.
- [ ] Human sees normalized authority before approval.
- [ ] Mandate is signed.
- [ ] Signature is verified server-side.
- [ ] Hard constraints are deterministic.
- [ ] Merchant catalog is authoritative for product facts.
- [ ] Valid proposal can create a Razorpay test-mode order.
- [ ] Hard-invalid proposal cannot call Razorpay.
- [ ] Semantic uncertainty creates step-up.
- [ ] Human can approve once or reject.
- [ ] Mandate can be revoked.
- [ ] Revoked mandate cannot subsequently authorize execution.
- [ ] Duplicate execution is prevented.
- [ ] Audit trail records every major decision.

## Quality

- [ ] No secrets committed.
- [ ] README includes setup commands.
- [ ] `.env.example` included.
- [ ] Seed script included.
- [ ] Demo reset script included.
- [ ] Test suite passes.
- [ ] Evaluation report contains real measured numbers.
- [ ] All failure cases have explicit behavior.
- [ ] No UI-only mocked decisions presented as real backend behavior.

---

# 44. Threat Model

## Threat: Agent modifies mandate

Defense:

```text
signature verification
```

---

## Threat: Agent exceeds amount

Defense:

```text
deterministic amount check
```

---

## Threat: Agent lies about product category

Defense:

```text
merchant-controlled catalog lookup
```

---

## Threat: Agent replays request

Defense:

```text
idempotency key
execution count
single-use mandate state
```

---

## Threat: Human revokes while agent continues

Defense:

```text
online mandate state
row-lock ordering
version check
```

---

## Threat: Prompt injection in product description

Defense:

- product text treated as untrusted data;
- system prompt explicitly forbids following embedded instructions;
- semantic model output cannot authorize hard constraints;
- deterministic gate is isolated.

---

## Threat: Semantic model hallucinates

Defense:

```text
evidence-only output
INSUFFICIENT_EVIDENCE
human step-up
```

---

## Threat: Semantic model unavailable

Defense:

```text
STEP_UP
```

Never auto-allow.

---

## Threat: Backend error

Defense:

```text
fail closed before payment
```

---

# 45. What Must Not Be Added Before Submission

Do not add the following unless the core project is fully complete and tested:

```text
dynamic pricing
recommendation engine
agent negotiation
MCP server
ACP support
AP2 protocol gateway
x402
UPI delegation
fraud model
multi-agent orchestration
graph database
blockchain
RL
voice agent
campaign agent
merchant analytics suite
```

These create scope without increasing the central proof.

---

# 46. Optional Extensions — Only If Core Is Finished

These are post-core stretch goals.

## 46.1 AP2-style Adapter

Accept a standards-inspired mandate format and convert it into the internal mandate schema.

Do not claim full AP2 compliance unless actually implemented.

---

## 46.2 Passkey Authorization

Upgrade demo ECDSA signing to WebAuthn.

---

## 46.3 Semantic Policy Calibration

Run a labeled evaluation set and tune thresholds / decision mapping.

---

## 46.4 Multi-Merchant Policy

Allow a principal to authorize a set of merchants.

---

## 46.5 Limited Reusable Mandates

Example:

```text
up to 3 purchases
total spend <= ₹50,000
expires in 24h
```

Requires careful accounting.

Do not build before single-use is rock solid.

---

# 47. Five-Minute Pitch Script

## 0:00–0:30 — Problem

Say:

> AI agents can already find products and initiate purchases. But the merchant still has a trust problem: the agent itself cannot be the sole party claiming that it followed the human's instructions. Before money moves, the merchant needs an independent authorization boundary.

---

## 0:30–1:00 — Architecture

Show:

```text
Human mandate
      ↓
AI buyer proposal
      ↓
Hard deterministic gate
+
Semantic intent assessment
      ↓
ALLOW / BLOCK / STEP-UP
      ↓
Razorpay
```

Say:

> Hard authority is verified exactly. Semantic intent is assessed, never pretended to be exact. Unknown goes back to the human.

---

## 1:00–1:45 — Valid Purchase

Issue mandate.

Run valid proposal.

Show:

```text
PASS
SUPPORTED
ALLOW
Razorpay order created
```

---

## 1:45–2:30 — Hard Failure

Run over-budget proposal.

Show:

```text
AMOUNT_LIMIT_EXCEEDED
BLOCK
Razorpay not called
```

---

## 2:30–3:30 — Semantic Failure

Run semantically wrong product.

Show:

```text
hard checks PASS

semantic:
CONTRADICTED

STEP_UP
```

Human rejects.

Show:

```text
₹0 moved
```

---

## 3:30–4:15 — Revocation

Activate valid mandate.

Revoke it.

Agent attempts again.

Show:

```text
MANDATE_REVOKED
BLOCK
```

---

## 4:15–5:00 — Metrics + Engineering Judgment

Show:

```text
hard-policy cases
semantic cases
unauthorized executions
duplicate executions
step-up rate
safe completion rate
```

Close with:

> We deliberately did not let AI decide exact monetary authority. AI is used only for the semantic layer where deterministic rules are insufficient. Everything irreversible stays behind deterministic policy, revocation state, and audit.

---

# 48. Submission Text — What It Solves

Recommended concise answer:

> Autonomous AI buyers can select products and initiate commerce, but merchants cannot safely trust the buyer agent's own claim that it stayed within the human's intent. Our gateway turns human delegation into an enforceable merchant-side boundary: exact limits are checked deterministically, fuzzy intent is assessed separately using merchant product evidence, uncertainty escalates to the human, and only authorized proposals can reach Razorpay test-mode execution.

---

# 49. Submission Text — What Broke and How We Got Out

Do not invent this before development.

During implementation, keep a real engineering log.

Good examples if they actually happen:

```text
- revocation race produced inconsistent execution state;
- duplicate request created multiple orders;
- semantic scorer overconfidently passed missing evidence;
- signature canonicalization broke because JSON serialization was unstable;
- model output malformed schema;
- Razorpay timeout created uncertain order state.
```

Document:

```text
what happened
why it happened
what invariant was violated
how architecture changed
how test was added
```

This section matters.

---

# 50. Internal Success Scorecard

The team should evaluate itself before submission.

| Dimension | Target |
|---|---:|
| Problem taste | 19/20 |
| Track fit | 15/15 |
| AI judgment | 19/20 |
| Technical depth | 18+/20 |
| Build reliability | 18+/20 |
| Demo strength | 10/10 |
| Novelty | 8+/10 |

The project should feel:

```text
narrow
correct
trustworthy
operational
difficult to fake
easy to understand
```

Not:

```text
large
feature-rich
chatbot-heavy
framework-heavy
mock-driven
```

---

# 51. Engineering Invariants

These must always hold.

## Invariant 1

```text
hard_gate == FAIL
→ Razorpay never called
```

## Invariant 2

```text
mandate.status != ACTIVE
→ execution impossible
```

## Invariant 3

```text
semantic == INSUFFICIENT_EVIDENCE
→ no autonomous execution
```

## Invariant 4

```text
duplicate proposal
→ at most one Razorpay order
```

## Invariant 5

```text
agent-provided product facts
→ never override merchant catalog facts
```

## Invariant 6

```text
LLM output
→ never overrides deterministic money constraints
```

## Invariant 7

```text
every final decision
→ corresponding audit event
```

---

# 52. Minimal Pseudocode — Main Evaluation

```python
def evaluate_checkout(mandate_id: str, product_id: str, quantity: int, agent_request_id: str):
    mandate = mandate_repo.get(mandate_id)
    product = product_repo.get(product_id)

    hard_result = hard_gate.evaluate(
        mandate=mandate,
        product=product,
        quantity=quantity,
        agent_request_id=agent_request_id,
    )

    audit.write_hard_result(hard_result)

    if hard_result.status == "FAIL":
        return Decision.block(
            reason=hard_result.reason_code,
            hard_checks=hard_result.checks,
        )

    semantic_result = semantic_scorer.evaluate(
        instruction_text=mandate.instruction_text,
        semantic_constraints=mandate.semantic_constraints,
        product_evidence=product.attributes,
    )

    audit.write_semantic_result(semantic_result)

    if semantic_result.has_unknown or semantic_result.has_contradiction:
        stepup = stepup_service.create(
            mandate=mandate,
            product=product,
            semantic_result=semantic_result,
        )

        return Decision.step_up(
            step_up_id=stepup.step_up_id,
            semantic_result=semantic_result,
        )

    return Decision.allow(
        hard_checks=hard_result.checks,
        semantic_result=semantic_result,
    )
```

---

# 53. Minimal Pseudocode — Execution

```python
def execute_authorized_proposal(proposal_id: str):
    with db.transaction():
        proposal = proposal_repo.get_for_update(proposal_id)
        mandate = mandate_repo.get_for_update(proposal.mandate_id)

        assert proposal.status == "ALLOWED"
        assert mandate.status == "ACTIVE"
        assert mandate.expires_at > now()
        assert mandate.execution_count < mandate.max_executions

        proposal.status = "EXECUTING"
        mandate.execution_count += 1

        if mandate.single_use:
            mandate.status = "CONSUMED"

        audit.write("EXECUTION_RESERVED", ...)

    try:
        order = razorpay_adapter.create_order(
            amount=proposal.expected_amount_paise,
            currency=proposal.currency,
            receipt=proposal.proposal_id,
        )
    except Exception as exc:
        execution_recovery.handle_create_order_failure(proposal_id, exc)
        raise

    proposal_repo.attach_razorpay_order(proposal_id, order["id"])
    audit.write("RAZORPAY_ORDER_CREATED", ...)

    return order
```

Production semantics around consumption vs payment completion can be refined, but for the hackathon they must be explicit and consistent.

---

# 54. Demo Reset

Create:

```text
scripts/demo_reset.py
```

It should:

- delete demo mandates;
- delete proposals;
- delete audit events;
- reset product catalog;
- recreate known demo users;
- optionally recreate demo key material.

The team must be able to restore the exact demo state in one command.

Example:

```bash
python scripts/demo_reset.py
```

---

# 55. Local Run Commands

Recommended developer experience:

```bash
docker compose up -d postgres

cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

cd frontend
npm install
npm run dev
```

Seed:

```bash
python scripts/seed_catalog.py
```

Evaluation:

```bash
python scripts/run_eval.py
```

Tests:

```bash
pytest -q
```

---

# 56. Final Product Identity

Working title:

# **MANDATE FIREWALL**

**This name may change later.**

The project definition must remain stable even if the final name changes.

Do not rename the architecture or central primitive during development.

The core remains:

```text
SIGNED HUMAN AUTHORITY
        ↓
DETERMINISTIC HARD GATE
        +
SEMANTIC INTENT ASSESSMENT
        ↓
ALLOW / BLOCK / STEP-UP
        ↓
RAZORPAY
```

---

# 57. Final Build Rule

If the team has to choose between:

```text
one more feature
```

and:

```text
one more invariant tested correctly
```

choose the invariant.

If the team has to choose between:

```text
a prettier AI demo
```

and:

```text
real Razorpay execution behind the gate
```

choose real execution.

If the team has to choose between:

```text
AI guessing
```

and:

```text
human step-up
```

choose step-up.

The project wins by being **small, correct, measurable, and trustworthy**.

---

# 58. Final Summary

The final submission should demonstrate one complete loop:

```text
Human delegates
→ authority is signed
→ AI buyer proposes
→ merchant independently checks exact limits
→ merchant separately assesses semantic intent
→ uncertainty returns to the human
→ only authorized proposals reach Razorpay
→ revocation stops future execution
→ every decision is auditable
```

That is the entire product.

Nothing outside this loop is required for the first submission.
