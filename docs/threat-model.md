# Threat Model

Human purchasing authority, merchant catalog truth, execution capacity, provider credentials, and the audit are protected assets. The buyer agent, product prose, and model output are untrusted.

| Threat | Control | Proof |
|---|---|---|
| Agent modifies mandate | ECDSA P-256 signature over canonical JSON | tampering tests (`test_signature_service.py`) |
| Agent lies about product facts | API accepts product ID & quantity only; server resolves authoritative merchant facts | integration tests (`test_killer_scenario.py`) |
| One-paise overflow | Integer-subunit comparison (paise) | unit test + 100 eval cases |
| Replay duplicates order | Unique agent request ID, locked proposal, DB uniqueness, idempotent replay | live x20 replay test (`test_api_replay.py`) |
| Revoked authority executes | Status & version check under row lock before execution reservation | revocation race tests |
| Concurrency execution race | Mandate row lock + execution limit check | row-lock tests (`test_postgres_races.py`) |
| Catalog prompt injection | Unicode NFKC normalization, zero-width stripping, base64 inspection, quarantine | 50 adversarial eval cases (`test_semantic_safety.py`) |
| Model hallucinates support | Cited fields must exist in merchant catalog; support requires verified evidence | semantic safety tests |
| Model unavailable / timeout | Fails safe to `STEP_UP` (escalates to human) | timeout & unavailable tests |
| Model overrides money | Hard gate checked first; semantic model cannot override hard failure | architectural separation |
| Hidden payment path | Single `RazorpayPort` adapter invoked only via `ExecutionService` | zero direct calls |
| Provider failure / timeout | Reservation rolled back within transaction; fails closed without burning slot | `test_razorpay_failure_fails_closed_and_is_audited` |
| Payment spoofing / replay | Server-side Razorpay HMAC-SHA256 signature and provider status verification | `test_payment_verification.py` |

Residual risks: Clerk identity verification handles demo & operator sessions; hardware-backed WebAuthn/passkey ceremony can replace software ECDSA in production; provider reconciliation handles edge cases where network drops after provider order creation.
