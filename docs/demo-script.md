# Five-Minute Demo

Reset with `.\.venv\Scripts\python scripts\demo_reset.py`. Confirm PostgreSQL, Razorpay test keys, and semantic model credentials first.

## 0:00–0:35 — Problem and boundary

“An AI buyer can claim it followed a human instruction. A merchant should independently prove that claim before money moves.” Show the four-node control room and that the model has no path to Razorpay.

## 0:35–1:35 — Valid execution

Issue the default ₹20k mandate. Show the reviewed constraints and ECDSA envelope. Propose Product A; show hard `PASS`, semantic `SUPPORTED`, final `ALLOW`. Create the order and read the same `order_...` ID in Razorpay test-mode Orders.

## 1:35–2:20 — Hard block

From a fresh mandate propose Product B at ₹21,499. Show `AMOUNT_LIMIT_EXCEEDED`, actual `2149900`, expected `<= 2000000`, source `merchant_catalog`, and no execution control.

## 2:20–3:20 — Semantic step-up

Propose Product D: metallic gold, party collection, oversized branding. Show hard `PASS`, semantic `CONTRADICTED`, final `STEP_UP`, binding hash, and “THIS PROPOSAL ONCE.” Reject; show no order.

## 3:20–4:05 — Revocation

Issue a fresh mandate, revoke it, then let Agent Checkout attempt Product A. Show `MANDATE_REVOKED`, hard `FAIL`, final `BLOCK`, and no execution control.

## 4:05–5:00 — Evidence

Expand audit entries for the hard failure, semantic result, rejection, and revocation. Show the full tests and `scripts/run_eval.py`.

Close: “AI classifies fuzzy intent from merchant evidence. It never decides exact monetary authority. Unknown, malformed, or unavailable goes to a human; irreversible action stays behind signed policy, current state, database uniqueness, and one audited Razorpay adapter.”

