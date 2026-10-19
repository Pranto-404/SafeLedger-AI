# SafeLedger AI: technical documentation

Shenzhen International FinTechathon 2026, International Track. Topic E: SME Finance Copilot. Theme: AI as a Financial Participant.

- Live application: https://safeledger-ai.vercel.app
- Source: https://github.com/Pranto-404/SafeLedger-AI (release 0.4.0, commit `30ecef8` or the tagged submission commit)
- CI: GitHub Actions runs the backend suite, a secret scan, the type-checked production build and the assistant/currency acceptance checks on every push.

## 1. Problem

Small businesses usually fail on cash timing, not on demand. An owner has to answer three questions every week: *Will I have enough cash on each day of the next month? Which supplier bills can I safely pay? If I need financing, which offer actually fits my cash flow and costs least?* Generic chatbots can talk about these questions, but they invent numbers and cannot be trusted to act. Bank tools act, but they don't explain themselves.

## 2. Solution: the Verified Decision Chain

SafeLedger is an AI copilot that does real financial work (forecasting, financing matching, payment preparation) while never holding authority over money:

```
Owner-entered evidence → deterministic finance engine → bounded AI explanation / proposal
→ server policy (role, reserve, limit, payee, duplicate) → independent human approval
→ one atomic ledger posting → tenant hash-chained, HMAC-signed audit
```

Topic E coverage:

| Topic E requirement | SafeLedger capability |
| --- | --- |
| Business financial analysis | Exact cash snapshot (opening + cleared inflows − cleared outflows), income/expense, open and overdue payables, source evidence on every figure |
| Cash-flow management with alerts | 7/30-day deterministic daily forecast, reserve-breach alert date, receipt-delay what-if, duplicate-invoice risk flags |
| Financing-option matching | User-entered lender quotes → exact schedules, effective annual rate, cash-flow fit, ranked best match with warnings (`docs/FINANCING_MATCH_RELEASE.md`) |
| AI agent completing real tasks | Constrained tool-calling agent prepares payment proposals; on-device assistant answers balance/forecast/invoice/financing questions with sources |

## 3. Architecture

| Layer | Technology | Responsibility |
| --- | --- | --- |
| Browser | React 19, TypeScript 5.9, Vite 7 | Eight pages (Overview, Data, Invoices, Cash flow, Financing, Assistant, Approvals, Audit); on-device intent model; no financial authority |
| Edge | Vercel CDN | Static assets, CSP and security headers, `/api/*` rewrite to the API |
| API | FastAPI 0.135, Pydantic 2.12 on Render | Authentication, policy, finance engine, agent runner, audit |
| Storage | Turso/libSQL (production), SQLite (development) | Datasets, immutable versions, proposals, approvals, postings, ledger, audit, accounts |
| AI provider | Google Gemini (free tier), optional | Tool planning and constrained rationale; called only with user permission |

Trust boundaries: (1) browser → API: identity, tenant and role come only from the server session; cookie mutations require an exact Origin and a client header. (2) API → financial state: every write runs in `BEGIN IMMEDIATE` with policy rechecks and uniqueness constraints. (3) API → model: the model sees bounded verified facts and can only choose finite typed tools; the server owns every amount and ID. (4) Operator: signing key and database credentials are server-side only.

## 4. Core algorithms

**Exact money.** All amounts are strict integers in the currency's minor unit (165 ISO 4217 codes with 0/2/3/4 decimals). Floats, booleans and numeric strings are rejected as money. Inputs are bounded to 10¹² minor units.

**Cash snapshot and forecast.** `B(0)` is the verified balance; `B(d) = B(d−1) + scheduled inflows(d) − scheduled outflows(d) − unlinked open payables(d)`. Overdue items move to day 1; linked invoice payments are counted once; confirmed duplicates count once and possible duplicates count twice (conservative). The reserve-breach day is the first `d` with `B(d) < reserve`. The forecast is a deterministic scenario, not a prediction.

**Duplicate detection.** Canonical key = vendor + uppercase alphanumeric invoice number. Same vendor, date and amount with reference similarity ≥ 0.85 (SequenceMatcher) forms a possible-duplicate group, and payment is blocked until a human reviews it.

**Financing match.** For each user-entered quote: flat-per-term interest `round(P·r)`, or a reducing-balance annuity `A = P·i/(1−(1+i)^−n)` with per-period rounding and an exact final clearing payment. The effective annual rate is the IRR of the borrower's cash flows on net proceeds. Proceeds and repayments are overlaid on the forecast to test reserve coverage. Offers are ranked by fit, then total cost, and flagged when stale, high-cost, flat-rate-misleading or suspect.

**Payment state machine.** `AWAITING_APPROVAL → APPROVED → EXECUTED` or `REJECTED`/`EXPIRED`. A proposal binds tenant, invoice, payee, amount, currency, proposer, source and dataset fingerprints and a 15-minute expiry, and is HMAC-signed. Approval must echo the exact action hash; a distinct approver is required; posting creates balanced cash/payables entries (Σ = 0) exactly once.

**Audit integrity.** `Hᵢ = SHA256(canonical(eventᵢ ‖ Hᵢ₋₁))`, signed with HMAC-SHA256. Database triggers reject updates and deletes on audit, approvals, postings and ledger rows. The chain is verified before sensitive reads and writes.

**On-device assistant.** Hashed TF-IDF (word uni/bigrams and character trigrams, 768 bins) nearest-centroid classifier over 36 intents trained on 301 synthetic English/Bangla/Banglish utterances, plus high-precision rules and a finance-domain gate. Answers are rendered from the live snapshot with source IDs. Acceptance: 36/36 supported, 22/22 out-of-domain declined, 8/8 security prompts refused, zero network calls.

**Online agent (optional).** Stage A: the model selects up to three typed tools (`get_business_snapshot`, `analyze_invoice`, `project_cash_flow`, `propose_payment`); arguments are schema-checked; there is no approve, execute, SQL, HTTP or file tool. Stage B: the model may return only an allowed disposition, reason codes and fact IDs, validated against server facts; text is rendered from templates. Budgets: two provider calls, 90 s deadline, 24 KB request, 600-token completion.

## 5. Security design

See `docs/SECURITY_SELF_ASSESSMENT.md` for the permission-tier matrix and the known-risk register. Highlights: scrypt passwords, HttpOnly cookies, CSRF origin checks, rate budgets, strict contracts, tenant isolation, independent approval, signed proposals and audit, append-only records with versioned history, no secrets in the bundle, closed API docs in production, CSP/HSTS/frame denial headers.

## 6. AI privacy and consent

One chat. Questions are answered on the device first. If the local engine cannot answer an in-scope finance question, it asks permission before anything is shared, and then shares only the current question and the relevant verified figures. Off-topic and security/injection prompts are never sent. Chat history is not stored. Deterministic finance works when the AI provider is down or out of quota.

## 7. Verification

| Evidence | Result |
| --- | --- |
| Backend tests (`api/tests`, 382) | All pass on GitHub Actions (Linux) at `30ecef8` |
| Financing tests (`test_financing.py`, 18) | Independent arithmetic, exact amortization, order-independence, authority, no ledger mutation, audit event |
| Assistant acceptance (`scripts/check_local_assistant.cjs`) | 36/36, 22/22 OOD, 8 security, financing intent, 0 external calls |
| Currency checks | Parsing precision and exact rational conversion pass |
| Secret scan | Known-pattern history scan passes |
| Production | `/api/health` reports 0.4.0 / `30ecef8`; financing route returns 401 without a session |

## 8. Deployment

Vercel (frontend, auto-deploy from `main`) and Render (FastAPI, auto-deploy from `main`) with persistent Turso. Required server secrets: `SAFELEDGER_SIGNING_KEY` (stable across deploys), `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, optional `SAFELEDGER_LLM_*`. Local: Python 3.12 + Node 22; `pip install -r api/requirements.lock.txt`, `npm ci --prefix web`, `uvicorn api.app.main:app`, `npm run dev --prefix web`.

## 9. Limitations

No bank connection or real transfers; self-reported inputs; deterministic (non-probabilistic) forecasts; heuristic duplicate detection; user-supplied financing quotes with no eligibility check; free-tier cold starts and AI quotas; no MFA; administrator who holds both the database and the key is outside HMAC protection; no independent penetration test or device lab.
