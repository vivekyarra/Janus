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
