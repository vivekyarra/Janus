# JANUS â€” Judge-Ready Five-Minute Demo Video

**Track:** Razorpay AI Buildathon, Track 01 â€” AI Growth & Agentic Commerce
**Promise to prove:** An AI buyer may propose a checkout, but it cannot move through the Razorpay boundary unless a human's current signed authority and the merchant's evidence both clear.

## Recording contract â€” do this before pressing Record

| Item | Exact action |
|---|---|
| Browser resolution | 1440 Ã— 900, browser zoom 100%, hide bookmarks/extensions, notifications off. |
| App URL | `http://localhost:5173/` â€” JANUS is deliberately a single-page operational console. Every â€œpageâ€ below is a left-sidebar view, so the URL stays exactly this URL. Do **not** invent hash URLs in the recording. |
| API proof URL | `http://localhost:8000/docs` â€” keep in a background tab; only show it if the app UI fails. |
| Razorpay proof | `https://dashboard.razorpay.com/app/dashboard` â€” sign in before recording, switch to **Test Mode**, then use the visible left navigation: **Transactions â†’ Orders**. Keep this in a second background tab. |
| Reset | Run `.\.venv\Scripts\python scripts\demo_reset.py`, start the backend and frontend, then hard-refresh the app. Confirm the Control Room shows the seeded catalog. |
| Cursor | Use a visible cursor with a subtle yellow highlight. Move deliberately, pause 0.7 seconds over the evidence being discussed, and click only after the narration names it. No frantic scrolling. |
| Demo stance | Speak to the camera/screen as a merchant-facing system, not as â€œan AI app.â€ Say **test mode** every time Razorpay is mentioned. Never imply real money moved. |

## The story in one line

**An AI shopper can be brilliant at finding products, but it must not be trusted to authorise its own payment. JANUS gives the merchant a locked payment door: exact authority is deterministic; fuzzy intent is evidence-bound; uncertainty goes back to the human.**

## What judges should see by 5:00

1. A signed human mandate, not a chatbot instruction.
2. A valid agent checkout that creates one Razorpay **test-mode** order.
3. A â‚¹21,499 hard-limit violation that cannot reach Razorpay.
4. A â€œnothing flashyâ€ contradiction that becomes a human step-up, not an AI guess.
5. A revoked mandate that blocks an otherwise valid future attempt.
6. An audit timeline that makes every decision explainable.

---

## Exact five-minute run of show

### 0:00â€“0:25 â€” Cold open: the human problem

**Screen / URL:** `http://localhost:5173/` â†’ left sidebar **Control Room**. Keep the cursor still in the blank space under the title for the first sentence.
**Visual move:** At 0:12, slowly hover the cursor across the top decision/pipeline cards. Do not click.

**Say exactly:**

> â€œAn AI can find the perfect product in seconds. But when it says, â€˜I bought it for you,â€™ a merchant has to ask one uncomfortable question: who gave it permission to spend that money?
>
> In *Oceanâ€™s Eleven*, nobody opens the vault just because one person says they have a plan. Every lock has to clear. JANUS brings that same discipline to AI checkout: the AI can search and propose, but it never gets its own key to the payment vault.â€

**Pause:** 0.5 seconds. Let the Control Room be readable.

### 0:25â€“0:55 â€” Explain JANUS in plain English

**Screen / URL:** still `http://localhost:5173/` â†’ hover the visual pipeline from **Signed Mandate** toward **Razorpay**.
**Cursor path:** Start at the signed-mandate card on the left; glide to the hard-gate card; then point to the human-step-up card. Do not circle the screen.

**Say exactly:**

> â€œJANUS is a merchant-side authorisation gateway for AI buyers. It separates two questions that should never be mixed.
>
> First: are the exact rules true? Is the price below the signed limit? Is this the right merchant, product category, quantity, and active mandate? That is deterministic code.
>
> Second: does the product actually fit a human preference such as â€˜nothing flashyâ€™? That uses merchant catalog evidence. If the answer is unclear, JANUS does not guess. It asks the human.â€

### 0:55â€“1:25 â€” Issue human authority

**Screen / URL:** `http://localhost:5173/` â†’ click sidebar **Issue Mandate**.
**Cursor / click sequence:**

1. Hover **Human Delegation Prompt**.
2. Click inside it; use the exact preset text: `Buy noise-cancelling headphones under â‚¹20k. Nothing refurbished. Good for travel. Nothing flashy.`
3. Hover **COMPILE INTENT BOUNDS** for one beat; click it.
4. After the preview appears, move to the right panel and hover **DETERMINISTIC HARD CONSTRAINTS**; then hover **SEMANTIC INTENT CONSTRAINTS**.
5. Click **SIGN & ACTIVATE MANDATE**.

**Say exactly:**

> â€œThe human does not sign a vague chat message. They review the authority that JANUS compiled. Here, the hard limits are: under twenty thousand rupees, one new pair of headphones, from this merchant. â€˜Good for travelâ€™ and â€˜nothing flashyâ€™ remain semantic requirements.
>
> Notice what JANUS refuses to do: it never invents a price limit from a phrase like â€˜donâ€™t spend too much.â€™ The human must approve exact authority before it becomes active.â€

### 1:25â€“1:42 â€” Show that the authority is real and revocable

**Screen / URL:** same URL â†’ click sidebar **Mandate Envelope**.
**Cursor:** Hover the mandate ID/digest; then hold cursor over **ECDSA P-256 / SHA-256** and the **ACTIVE** badge. Do not click Revoke yet.

**Say exactly:**

> â€œThis is the signed envelope. The signature proves what was approved; live state proves whether it is still usable. A valid signature cannot overrule expiry, consumption, or revocation.â€

### 1:42â€“2:25 â€” Beat 1: valid autonomous execution

**Screen / URL:** same URL â†’ click **Checkout Engine**. The default mode is **Autonomous Buyer Agent**.
**Cursor / click sequence:**

1. Hover **Human Intent Instruction** in the left mission brief.
2. Hover **Authoritative Merchant Authority** â€” say this is merchant data, not agent data.
3. Click **DISPATCH AUTONOMOUS BUYER AGENT** once.
4. When the candidate table appears, hold the cursor over the selected compliant product and its evidence/citation badges.
5. Hover the returned `order_...` identifier. If the Razorpay popup is ready, click **PAY WITH RAZORPAY TEST CHECKOUT** only if you have pre-tested the test payment flow; otherwise stop after the order ID.

**Say exactly:**

> â€œNow the AI buyer does what AI is good at: it searches the merchant catalog and proposes a checkout. But JANUS ignores any price or category the agent might claim. It resolves the facts from the merchant catalog itself.
>
> This candidate clears every deterministic check and the merchant evidence supports the travel and styling intent. Only because both paths clear does JANUS reserve one execution and create exactly one Razorpay **test-mode** order. The order ID on screen is the payment-boundary proof.â€

**Optional Razorpay cutaway â€” 8 seconds maximum:** switch to `https://dashboard.razorpay.com/app/dashboard`, confirm **Test Mode**, click **Transactions**, then **Orders**, and click the matching `order_...` ID. Hover the amount, currency, and receipt/order ID.

**Say exactly:**

> â€œHere is the matching Razorpay test-mode order. This is a sandbox proof, not a claim that real money moved.â€

### 2:25â€“3:00 â€” Beat 2: hard violation, zero payment call

**Screen / URL:** return to `http://localhost:5173/` â†’ in **Checkout Engine**, click **Interactive Simulator**.
**Cursor / click sequence:**

1. Click **Demo 2: Sony Studio (Over limit)**.
2. Hover the visible â‚¹21,499 price.
3. Click **PROPOSE CHECKOUT**.
4. When the verdict appears, park the cursor on the red **BLOCK** badge, then hover `AMOUNT_LIMIT_EXCEEDED` and the failed amount check.
5. Do not click any payment action; there must not be one.

**Say exactly:**

> â€œHere is the moment that matters. The agent proposes a â‚¹21,499 product against a signed â‚¹20,000 limit. JANUS returns `AMOUNT_LIMIT_EXCEEDED`.
>
> This is not a low confidence score. It is a hard stop. No language model gets a vote, no human-friendly explanation can override it, and Razorpay is never called.â€

### 3:00â€“3:40 â€” Beat 3: semantic contradiction becomes human control

**Screen / URL:** still `http://localhost:5173/` â†’ Interactive Simulator.
**Cursor / click sequence:**

1. Click **Demo 3: Aura Gold Party**.
2. Hover the product name and price; stress that it is within budget.
3. Click **PROPOSE CHECKOUT**.
4. When `STEP_UP` appears, hover **DETERMINISTIC HARD GATE** first (all green), then hover the semantic evidence: metallic gold / party collection / oversized branding.
5. Click **HUMAN STEP-UP REQUIRED â€” REVIEW ESCALATION**.

**Say exactly:**

> â€œThis product is inside the budget, so the hard gate passes. But the human said, â€˜Nothing flashy.â€™ The merchant evidence says metallic gold, party collection, and oversized branding.
>
> JANUS does not pretend a model can prove personal taste. It says `STEP_UP`. This is where AI stops and the human becomes the final decision-maker.â€

### 3:40â€“3:58 â€” Reject the step-up

**Screen / URL:** same URL â†’ **Human Step-Up** view.
**Cursor / click sequence:** Hover the evidence and proposal-binding area. Move to **REJECT**. Pause half a second, then click **REJECT** once.

**Say exactly:**

> â€œThe human rejects it. No order is created. If they approved once, that approval would be bound only to this exact mandate, proposal, product, and amountâ€”not converted into permanent AI spending power.â€

### 3:58â€“4:28 â€” Beat 4: revocation wins over an old signature

**Screen / URL:** same URL â†’ click **Issue Mandate**, compile and sign the same preset quickly; then click **Mandate Envelope**.
**Cursor / click sequence:**

1. Hover the **ACTIVE** badge.
2. Hover **REVOKE MANDATE** for a beat and click it once.
3. Click **Checkout Engine** â†’ **Interactive Simulator** â†’ **Demo 1: Sony Voyager** â†’ **PROPOSE CHECKOUT**.
4. Hold cursor over `MANDATE_REVOKED` / **BLOCK**.

**Say exactly:**

> â€œNow imagine the human changes their mind halfway through. The mandate was once valid. It is now revoked. The agent tries the previously compliant product again.
>
> JANUS checks the current database state before execution. The result is `MANDATE_REVOKED`: blocked, audited, and zero Razorpay calls.â€

### 4:28â€“4:48 â€” The merchant can explain every decision

**Screen / URL:** same URL â†’ click sidebar **Signal Feed**.
**Cursor:** Slowly hover, in this order, the hard-failure event, semantic assessment/step-up event, rejection event, revocation/block event, then the successful-order event. Expand only the most legible one; do not race through all entries.

**Say exactly:**

> â€œFor a merchant, a decision is only useful if it can be explained later. JANUS records what was attempted, the signed authority, exact checks, catalog evidence, final decision, and whether Razorpay was called. It stores facts and outcomesâ€”not private chain-of-thought.â€

### 4:48â€“5:00 â€” Closing line

**Screen / URL:** stay on **Signal Feed** with the strongest readable `BLOCK` and `RAZORPAY_ORDER_CREATED` entries visible. Keep cursor still.

**Say exactly:**

> â€œJANUS makes agentic commerce usable for merchants because it puts AI in the right place. AI can propose and interpret. Deterministic policy controls money. Uncertainty returns to the human. And every payment decision leaves an audit trail a merchant can trust.â€

---

## Editorâ€™s cut list â€” non-negotiable

- Keep one continuous screen recording from mandate issuance through the first allowed order; this is the credibility spine.
- Use only two quick cuts: the Razorpay test-mode Dashboard proof and the final audit close-up.
- Cut loading states, typing mistakes, browser navigation, and any failed payment popup.
- Do **not** show API keys, `.env`, source code, terminal output, test cards, or a generic landing page in the five minutes.
- Do **not** claim â€œproduction ready,â€ â€œfraud-proof,â€ â€œAP2 compliant,â€ â€œreal money,â€ or model accuracy from an incomplete live benchmark.
- If Razorpay test checkout itself is not pre-verified that day, show the created `order_...` ID and the Razorpay Dashboard order readback; do not attempt a risky live checkout during recording.

## One-sentence submission caption

**JANUS lets merchants accept AI-buyer checkout proposals without giving an AI the authority to invent payment permission: signed hard limits block deterministically, fuzzy intent is assessed from merchant evidence, and uncertainty returns to the human before Razorpay test-mode execution.**
