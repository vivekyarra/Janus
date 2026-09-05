# JANUS

[![JANUS safety gate](https://github.com/vivekyarra/Janus/actions/workflows/ci.yml/badge.svg)](https://github.com/vivekyarra/Janus/actions/workflows/ci.yml)

> A merchant-side authorization gateway for AI buyers: exact authority is deterministic, fuzzy intent is evidence-bound, uncertainty returns to the human, and only an authorized proposal can reach Razorpay.

JANUS is a Track 01 — AI Growth & Agentic Commerce project for the Razorpay AI Buildathon. It closes the trust gap between an autonomous buyer saying “I followed the human’s instructions” and a merchant independently proving that claim before creating an order.

## The boundary

```mermaid
flowchart LR
    H[Human instruction] --> C[Intent compiler] --> R[Human review] --> S[Signed mandate]
    A[AI buyer proposal] --> G[Deterministic hard gate]
    S --> G
    K[Merchant catalog evidence] --> G
    G -->|FAIL| B[BLOCK: Razorpay not called]
    G -->|PASS| M[Semantic assessment]
    K --> M
    M -->|SUPPORTED| E[Atomic execution reservation]
    M -->|CONTRADICTED / UNKNOWN / ERROR| U[Human step-up]
    U -->|Reject| B
    U -->|Approve once| E
    E --> Z[Razorpay Orders API: test mode]
```

| Path | Handles | Output | May override hard policy? |
|---|---|---|---|
| Hard gate | signature, state, expiry, version, merchant, currency, category, condition, quantity, amount, execution count | `PASS` / `FAIL` | No |
| Semantic scorer | “good for travel,” “nothing flashy,” and similar phrases, using merchant evidence only | `SUPPORTED` / `CONTRADICTED` / `INSUFFICIENT_EVIDENCE` | No |

## Run locally

Requirements: Python 3.11+, Node 24+, and Docker Desktop only for PostgreSQL verification.

```powershell
git clone https://github.com/vivekyarra/Janus.git
Set-Location Janus
Copy-Item .env.example .env
py -m venv .venv
.\.venv\Scripts\pip install -r backend\requirements.txt
npm ci --prefix frontend
docker compose up -d postgres
.\.venv\Scripts\python scripts\demo_reset.py
Set-Location backend
..\.venv\Scripts\python -m uvicorn app.main:app --reload
```

In a second terminal:

```powershell
Set-Location frontend
$env:VITE_API_URL='http://localhost:8000'
npm run dev
```

Open `http://localhost:5173`. When finished, stop both processes and run `docker compose stop postgres`.

For a zero-PostgreSQL development run, omit `DATABASE_URL`; JANUS uses a repository-local SQLite file. PostgreSQL remains the required deployment and concurrency-test database.

## Environment

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL SQLAlchemy URL; required for persistent deployment |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | Razorpay test-mode keys; the ID must start with `rzp_test_` |
| `RAZORPAY_MODE` | Must remain `test` in JANUS v1 |
| `AI_GATEWAY_API_KEY` or `VERCEL_OIDC_TOKEN` | Vercel AI Gateway authentication |
| `LLM_MODEL` | Structured-output model slug, default `openai/gpt-5-mini` |
| `FRONTEND_URL` | Exact allowed browser origin |
| `SEED_DEMO_CATALOG` | Idempotently seed five deterministic demo products |

No credentials, private keys, or signing material are committed.

## Verification

```powershell
.\.venv\Scripts\python -m pytest backend
npm run build --prefix frontend
.\.venv\Scripts\python scripts\run_eval.py
.\.venv\Scripts\python scripts\demo_reset.py
```

Real row-lock tests run against PostgreSQL:

```powershell
$env:JANUS_POSTGRES_TEST_URL='postgresql+psycopg://postgres:postgres@localhost:5432/janus'
.\.venv\Scripts\python -m pytest backend\tests\adversarial\test_postgres_races.py
```

Current measured results are in [docs/evaluation-results.md](docs/evaluation-results.md). Test doubles exist only inside automated tests; production authorization and external adapters never silently simulate success.

## Razorpay test mode

1. Generate test keys in the Razorpay Dashboard.
2. Put them in runtime environment variables, never source control.
3. Reset and run the valid demo.
4. Confirm the returned `order_...` identifier in the Razorpay test-mode Orders view.

JANUS calls `POST /v1/orders` from exactly one module: `backend/app/integrations/razorpay_adapter.py`. Amounts are integer currency subunits and the proposal ID is the unique receipt.

## Five demo beats

1. **Valid autonomous execution:** Product A → hard `PASS` → semantic `SUPPORTED` (confidence 0.96) → `ALLOW` → one Razorpay test order.
2. **Hard violation:** Product B at ₹21,499 against ₹20,000 → `AMOUNT_LIMIT_EXCEEDED` → `BLOCK` → no Razorpay call.
3. **Semantic step-up:** “Nothing flashy” + metallic gold / party / oversized branding → `CONTRADICTED` → human rejects → ₹0 moved.
4. **Revocation:** revoke an active mandate, then let the agent try Product A → `MANDATE_REVOKED` → `BLOCK` → no Razorpay call.
5. **Adversarial prompt injection defense:** Trojan product with embedded `"IGNORE BUYER INSTRUCTIONS"` directive → pre-model quarantine & untrusted evidence treatment → `STEP_UP` → Razorpay calls = 0.

See [docs/demo-script.md](docs/demo-script.md) for the exact step-by-step sequence.

## Evaluation & Benchmark Proof

> **“Across 200 unseen intents, JANUS had 0 unsafe autonomous approvals; uncertain cases were escalated.”**

- **Real-World Semantic Intent Benchmark (200 cases):** Covers English, Hinglish colloquialisms, nuanced linguistic preferences, and conflicting marketing copy vs merchant specs.
- **Calibrated Confidence & Abstention:** Evaluates confidence $c \in [0.0, 1.0]$. When $c < 0.85$, JANUS automatically abstains from autonomous execution and fails closed to human `STEP_UP`. At $\tau = 0.85$, the false autonomous allow rate is strictly **0.0%**.
- **Counterfactual Reasoning (25 pairs):** Proves single-attribute flips (e.g., `metallic_gold` $\to$ `matte_black`) consistently flip verdicts between `STEP_UP` and `ALLOW`.
- **Protocol Interoperability:** Implements export/import interfaces for **AP2** (Agent Payments Protocol v1), **ACP** (Agentic Commerce Protocol v1), and **x402** payment envelope handshakes.

## Repository map

```text
backend/app/domain          typed contracts and stable reason codes
backend/app/services        signing, hard gate, semantic, decision, revocation, execution, step-up, audit, interop
backend/app/integrations    the only LLM and Razorpay network boundaries
backend/app/api             thin transport routes
backend/tests               unit, integration, and adversarial coverage
frontend/src                operational authorization console
evals                       deterministic boundary, 200 semantic cases, and benchmark reports
scripts                     seed, reset, model benchmarks, and measured evaluation
docs                        architecture, API, threat model, demo, failures, evaluation results
```

## Security assumptions and limitations

- Razorpay is test mode only; JANUS never moves real money in this build.
- ECDSA signing demonstrates signed authority, not a production passkey/WebAuthn ceremony.
- Interoperability adapters export/import AP2 and ACP envelopes and verify x402 payment headers.
- No production identity provider is included; deploy only as a controlled demo.
- Pre-model sanitization quarantines untrusted product text before LLM classification.
- Reservation winning the database lock may finish; revocation winning first prevents it. This ordering is explicit and tested.
- A Razorpay failure triggers an automatic reservation rollback in the database transaction, preventing execution slot burning while failing closed safely.
- The Killer Scenario (`test_killer_scenario.py`) tests the complete 3-product lifecycle: hard overbudget block, semantic contradiction rejection, compliant candidate autonomous execution, server-side payment verification, and audit trail.

JANUS is a focused buildathon system, not a claim of production readiness. Its narrower claim is testable: the payment boundary is explicit, auditable, and difficult for the buyer agent or semantic model to bypass. All 400+ evaluation cases pass deterministically.

## Detailed evidence

[Architecture](docs/architecture.md) · [API](docs/api.md) · [Threat model](docs/threat-model.md) · [Engineering log](docs/engineering-log.md) · [Evaluation](docs/evaluation-results.md)
