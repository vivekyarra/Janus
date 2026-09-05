# Threat Model

Human purchasing authority, merchant catalog truth, execution capacity, provider credentials, and the audit are protected assets. The buyer agent, product prose, and model output are untrusted.

| Threat | Control | Proof |
|---|---|---|
| Agent modifies mandate | ECDSA P-256 signature over canonical JSON | tampering tests |
| Agent lies about product facts | API accepts product ID and quantity; server resolves facts | integration tests |
| One-paise overflow | integer-subunit comparison | unit test + eval |
| Replay duplicates order | unique request ID, locked proposal, idempotent replay | x20 tests |
| Revoked authority executes | current status check under row lock | PostgreSQL race tests |
| Two executions race | mandate lock + execution limit | two-thread PostgreSQL test |
| Catalog prompt injection | instruction-like evidence quarantine and data-only system prompt | adversarial test |
| Model hallucinates support | cited fields must exist; support needs evidence | semantic tests |
| Model unavailable/malformed | explicit `STEP_UP` | timeout/malformed tests |
| Model overrides money | decision engine handles hard failure first; model has no execution port | code separation |
| Hidden payment path | one adapter reachable through execution service only | repository scan |
| Provider outcome uncertain | reservation remains consumed; failure audited | Razorpay error test |

Residual risks: no production identity provider; demo ECDSA is not hardware-backed WebAuthn; catalog evidence quality is merchant-owned; provider reconciliation is required after a crash between provider acceptance and local acknowledgement; database permissions do not cryptographically notarize audit rows.

