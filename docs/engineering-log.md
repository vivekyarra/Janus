# JANUS Engineering Log

This log records failures encountered during the real build. It is intentionally factual; entries are added only after a failure is reproduced and understood.

## 2026-09-05 — Bootstrap verification failed

- **Symptom:** The frontend production build rejected the side-effect CSS import, and PostgreSQL Compose could not connect to Docker Desktop's Linux engine.
- **Root cause:** The Vite client type declaration was missing from the fresh TypeScript app. Docker Desktop was installed but its engine was not running.
- **Invariant affected:** Reproducible clean-start verification; no payment invariant was reached.
- **Fix:** Added `vite-env.d.ts`; start and health-check Docker Desktop before PostgreSQL verification.
- **Regression check:** `npm run build`, `docker compose ps`, backend `/health`, and `pytest` are part of the Phase 0 gate.

## 2026-09-05 — Catalog reseed violated a non-null column

- **Symptom:** Running the deterministic seed function twice attempted to write `NULL` into `products.active`.
- **Root cause:** Seed fixtures were transient SQLAlchemy objects. Python-side column defaults had not executed before their values were copied during the upsert.
- **Invariant affected:** Demo reset repeatability; authorization data could not be restored reliably.
- **Fix:** Store seed fixtures as complete plain records with every authoritative field explicit.
- **Test added:** `test_seed_catalog_is_deterministic` runs the seed twice and asserts the catalog remains exactly five products.

## 2026-09-05 — Persisted timestamp broke signature verification

- **Symptom:** A mandate signed and saved through the API immediately failed the hard gate during the x20 replay test.
- **Root cause:** SQLite round-tripped the UTC expiry without timezone metadata. Canonicalization treated that naïve value as machine-local time, changing the signed bytes.
- **Invariant affected:** Signature validity and therefore deterministic authorization availability.
- **Fix:** Canonicalization now treats naïve database timestamps as UTC and always emits second-precision `Z` timestamps.
- **Test added:** The end-to-end API replay test creates a signed mandate, evaluates it after persistence, repeats the proposal 20 times, and repeats execution 20 times.

## 2026-09-05 — Local console could not reach the API

- **Symptom:** The rendered control room loaded correctly but displayed `Failed to fetch`; catalog and audit counts stayed at zero.
- **Root cause:** CORS permitted `localhost:5173` only while the verification browser used the equivalent `127.0.0.1:5173` loopback origin.
- **Invariant affected:** End-to-end demo availability; no authorization decision was reached.
- **Fix:** The development allowlist now includes both forms of the configured loopback origin without broad wildcard CORS.
- **Regression check:** Rendered browser flow must load five catalog products and create a signed mandate through the API.

## 2026-09-05 — Demo catalog depended on process working directory

- **Symptom:** After CORS was fixed, the browser reached the API but still showed zero products although `demo_reset.py` had seeded five.
- **Root cause:** The relative SQLite URL created one database from the repository root and another from `backend/`.
- **Invariant affected:** Merchant catalog authority and repeatable clean demo state.
- **Fix:** Resolve the development SQLite path from the application file location, and idempotently seed the known catalog on startup when enabled.
- **Regression check:** A backend started from `backend/` and scripts started from the repository root must resolve the same five products.

## 2026-09-05 — Revocation changed the bytes used for verification

- **Symptom:** The planned post-revocation attempt would fail as `SIGNATURE_INVALID` instead of the more accurate `MANDATE_REVOKED`.
- **Root cause:** Revocation correctly increments the online runtime version, but verification reconstructed signed bytes from that mutable value rather than the immutable `signed_version`.
- **Invariant affected:** Revocation still blocked execution, but the audit reason and signed-payload contract were wrong.
- **Fix:** Persist current and signed versions separately; canonical verification uses `signed_version`, then the ordered hard gate checks current status and version.
- **Test updated:** Stale-version and revoked-mandate cases now preserve valid signed bytes and reach their exact reason codes.

## 2026-09-05 — Container build sent local dependency trees

- **Symptom:** The first Docker build prepared a 76 MB context before application layers ran.
- **Root cause:** The fresh repository had no `.dockerignore`, so the local virtual environment and frontend dependencies entered the build context.
- **Invariant affected:** Reproducible, resource-conscious packaging; authorization behavior was unaffected.
- **Fix:** Cancelled the build and added a narrow `.dockerignore` for dependencies, caches, local databases, secrets, and generated output.
- **Regression check:** Rebuilt from the reduced context and verified the packaged HTTP health and console against PostgreSQL.

## 2026-09-05 — First credentialed Razorpay attempt failed closed

- **Symptom:** The signed mandate passed and the proposal reached `ALLOW`, but execution returned `RAZORPAY_ORDER_CREATION_FAILED` before any provider request.
- **Root cause:** A PowerShell safety wrapper cast a character array to the literal text `System.Char[]` instead of joining its characters, so the process received malformed environment variables.
- **Invariant affected:** External execution availability; no unauthorized order was possible and the failed reservation remained consumed by design.
- **Fix:** Corrected the process-only environment construction, verified only credential lengths and the `rzp_test_` prefix, then reset the demo state before retrying.
- **Regression check:** The clean retry created `order_TYLalcYGCbqDbY`; an independent Razorpay API read-back confirmed its amount, currency, receipt, and `created` status.

## 2026-09-05 — Development SQLite schema missing newly mapped identity columns

- **Symptom:** `POST /api/v1/mandates` returned HTTP 500 with `table mandates has no column named created_by_subject`.
- **Root cause:** SQLAlchemy's `create_all()` does not alter existing SQLite tables created before new columns (`created_by_subject`, `razorpay_payment_id`, `payment_status`, `paid_at`) were mapped in `models.py`.
- **Invariant affected:** Mandate creation availability; audit and authorization were blocked.
- **Fix:** Migrated the local SQLite database schema by adding the missing nullable columns, matching the PostgreSQL Alembic migration contracts.
- **Regression check:** Ran automated live verification (`verify_live.py`) covering all 4 demo beats; all endpoints returned expected structured decisions.

## 2026-09-05 — Failed gateway run was stored as a live benchmark

- **Symptom:** `evals/live_model_outputs.json` reported 200 requested cases but contained 0 successful outputs and 200 Vercel authentication failures.
- **Root cause:** The runner exited successfully after recording per-case errors, and threshold analysis was optional despite the documented workflow.
- **Invariant affected:** Evaluation honesty and reproducibility; runtime authorization was unaffected.
- **Fix:** The live runner now checkpoints atomically, resumes matching model/dataset runs, retries transient provider failures, requires exactly 200 unique cases, fails the command when any case is missing, and generates confusion and threshold-sensitivity metrics by default.
- **Regression check:** A one-case credential probe returned schema-valid Gemini output; the full run records its model ID, dataset SHA-256, timestamps, per-case raw output, latency, and completion flag.

## 2026-09-05 — Protocol projection could not verify its own signature

- **Symptom:** Exporting and immediately importing an interoperability envelope failed with a canonical-payload hash mismatch.
- **Root cause:** The export discarded signed fields such as the original human instruction, then import attempted to invent them while reconstructing the signed bytes.
- **Invariant affected:** Signed authority integrity; no execution path was reached.
- **Fix:** Export carries the exact canonical signed mandate payload; import verifies its hash and signature and rejects any mismatch between signed bounds and projected envelope fields.
- **Test added:** Export/import round-trip plus invalid signature, hash mismatch, incomplete proof, and projection-validation coverage.

## 2026-09-05 — x20 PostgreSQL race fixture violated idempotency before racing

- **Symptom:** The PostgreSQL adversarial suite failed while seeding 20 proposals with one unique `agent_request_id`.
- **Root cause:** The test attempted to bypass the database uniqueness mechanism it was meant to validate and also compared a paise amount against a rupee value.
- **Invariant affected:** Verification quality for replay and concurrency; production uniqueness correctly rejected the invalid fixture.
- **Fix:** Twenty callers now race one persisted proposal. The assertion permits safe in-flight rejection or idempotent replay while requiring exactly one fresh execution and one provider call; amount assertions use paise.
- **Regression check:** All four PostgreSQL row-lock, revocation, execution, and x20 race tests pass.

## 2026-09-05 — Live evaluation post-processing failed after 200 successful calls

- **Symptom:** The live runner completed and checkpointed all 200 Gemini outputs, then failed before writing confusion and threshold metrics.
- **Root cause:** Direct script execution puts `scripts/` rather than the repository root on `sys.path`, so `from scripts.run_eval` could not resolve.
- **Invariant affected:** Evaluation artifact completeness; all raw provider outputs remained safely checkpointed.
- **Fix:** Import the adjacent deterministic helper as `run_eval`; the analyzer refuses incomplete checkpoints and does not repeat completed provider calls.
- **Regression check:** Analyze-only mode generated metrics from the 200/200 complete, dataset-hashed output artifact.

## 2026-09-05 — Negated condition expanded purchase authority

- **Symptom:** Compiling “Nothing refurbished” displayed `allowed_conditions: refurbished` in the signed mandate preview.
- **Root cause:** The condition extractor matched product-condition keywords without first recognizing nearby negation.
- **Invariant affected:** Human delegation boundaries; the compiler could authorize the opposite of an explicit condition restriction.
- **Fix:** Condition extraction now detects `no`, `not`, `nothing`, `avoid`, `without`, and `exclude` before used/refurbished/open-box terms and restricts the draft to `new`.
- **Test added:** Negated refurbished intent compiles to `new`; explicitly requested refurbished intent still compiles to `refurbished`.

## 2026-09-05 — Auth refresh silently displayed zero business data

- **Symptom:** A transient missing Clerk token changed six catalog products and seven audit events to fake zero counts.
- **Root cause:** Each refresh request swallowed authentication errors and substituted empty arrays; the token provider was also installed in an effect vulnerable to React StrictMode cleanup timing.
- **Invariant affected:** Operator observability and UI truthfulness; backend authorization remained fail-closed.
- **Fix:** The token provider is installed synchronously, refresh preserves last-known real state, and API failures surface through the visible error channel.
- **Regression check:** Authenticated reload restores six products; all seven pages were checked for horizontal text overflow at the 1280x720 judge viewport.

## 2026-09-05 â€” Interrupted live-model evidence was not publishable

- **Symptom:** Earlier notes and the evaluation document described a completed 200-case Gemini run, while the retained checkpoint had only 162 successful calls and 38 failures.
- **Root cause:** The original Gemini credential was supplied from the interactive clipboard and was unavailable when the evaluation was resumed; the resume text became the clipboard value instead.
- **Invariant affected:** Evaluation honesty. This did not affect the deterministic hard gate or its fail-closed behavior.
- **Fix:** The runner preserves the checkpoint and exits non-zero on incomplete runs. Public evaluation copy now labels the live result incomplete and removes unsupported model, calibration, and cost claims.
- **Regression check:** The deterministic harness and test suite remain independently reproducible; live analysis refuses incomplete artifacts.
