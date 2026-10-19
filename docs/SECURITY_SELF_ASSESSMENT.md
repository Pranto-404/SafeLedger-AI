# Security self-assessment: permission tiers and known-risk register

Release 0.4.1 (financing match + security hardening), 20 October 2026. This is an internal assessment by the team, not an independent penetration test or certification. Evidence: `api/tests/` (414 backend tests plus a 14,000-scenario randomized check of the financing engine (see `docs/SECURITY_REVIEW_20261020.md`)), `.github/workflows/ci.yml`, `scripts/security_scan.py` and the release notes in `docs/`.

## 1. Design principle: the AI is never the authority for money

SafeLedger treats the language model, the browser and every user-supplied text as untrusted. Money, identity, permissions and execution are decided only by server-side policy over verified records:

`source evidence → deterministic calculation → bounded AI explanation/proposal → server policy → independent human approval → one atomic ledger posting → signed audit`

## 2. Permission tiers (enforced on the server)

| Capability | Owner | Approver | Viewer | AI agent (tool runner) | Anonymous |
| --- | --- | --- | --- | --- | --- |
| Read dashboard, invoices, forecast, audit | Yes | Yes | Yes | Read tools only, current tenant | No (401) |
| Add records / import / change empty-workspace currency | Yes | No (403) | No | No | No |
| Allow or block a payee (vendor permission) | Yes | No | No | No | No |
| Run financing match (records signed analysis event) | Yes | Yes | No (403) | No tool exposed | No |
| Create payment proposal | Yes | Yes | No | Only with explicit per-request user permission, one scoped invoice, after analysis | No |
| Approve / reject / execute a proposal | **No: cannot approve own work** | Yes, only if not the proposer | No | **No tool exists** | No |
| Invite teammate | Yes (approver or viewer only) | No | No | No | No |
| Export workspace records | Yes | Yes | Yes | No | No |

Roles come from authenticated server state, never from a request body. Invitations are one-time, hashed and expire after one hour; they can grant only approver or viewer. Hiding a button in the UI is never the control: every route rechecks the role inside the transaction.

## 3. Threats, controls and residual risk

| Threat | Implemented control | Evidence / residual risk |
| --- | --- | --- |
| Password guessing | Salted scrypt (N=32768, r=8, p=3), 8–128 exact characters, common-password and username-as-password rejection at signup/recovery, rolling 15-minute failed-attempt lockouts per account (40) plus per account+address (8) and per address (40), checked before any hashing, bounded hashing concurrency | Tests for hashing, lockouts, forged-header resistance and timing-equalized unknown users. Per-address limits can be forged by a direct caller of the API origin (the platform exposes no trustworthy address), so the per-account lockout is the binding control. No MFA. |
| Session theft / CSRF | Secure HttpOnly SameSite=Lax cookie, 24 h expiry, server-side revocation, exact Origin plus `X-SafeLedger-Client` header on every mutation | CSRF and logout tests. A compromised device remains out of scope. |
| Tenant escape / IDOR | Business scope from session; membership-checked switching; object IDs filtered by tenant | Cross-tenant read/write tests return 403/404 with no leak. |
| Self-approval / role escalation | Distinct approver required; proposer can never execute; invitations limited to approver/viewer | Adversarial tests for self-approval, forged role fields and invitation reuse. |
| Payment tampering / replay | Proposal binds payee, amount, currency, source hash, dataset version, proposer and 15-minute expiry with HMAC; approval must echo the exact action hash; `BEGIN IMMEDIATE` atomic posting; unique constraints | Concurrent approvals produce exactly one posting; replay returns the same posting; ledger deltas sum to zero. |
| Duplicate invoice payment | Canonical vendor + normalized reference; similarity ≥ 0.85 flags possible duplicates; execution blocked until reviewed | Heuristic: may over-flag similar references or miss unrelated-number duplicates. |
| Prompt injection (memo, task text) | Memos are escaped untrusted data; model can only pick from finite typed read/propose tools; second stage may return only fact IDs and reason codes, validated against server facts | Injection tests in suite. Finite evaluation, not proof that every attack fails. |
| AI fabricating numbers | All displayed amounts come from deterministic objects; model output with invented amounts, IDs or prose fails validation | Mocked and live synthetic diagnostics. No statistical accuracy claim. |
| Private data sent to AI provider | On-device intent model answers first; out-of-domain and security prompts are never sent; in-scope questions ask permission before the first share; only the current question and relevant verified facts leave | Own acceptance script: 36/36 supported, 22/22 off-topic kept local, 8/8 security prompts refused, zero external calls. Independent fresh set (95 prompts): off-topic 100% kept local, 41.7% of security prompts recognised by the on-device layer; the server, not the assistant, enforces authority (`docs/LOCAL_ASSISTANT_EVALUATION.md`). Finance questions wrongly judged off-topic can be sent only through an explicit user choice plus the permission card. Free provider terms may allow training on submissions; the UI warns users. |
| Misleading financing advice | Quotes are labelled user-supplied; exact integer schedules; effective annual rate is an IRR estimate; suspect terms (> 100% effective or fees > 20%) are excluded from best match; no eligibility or approval claims | 18 financing tests with independent arithmetic. Not financial advice; repayment capacity ignores unrecorded future sales. |
| Financing analysis tampering | Reserve and cash flow are read from the server, not the request; result fingerprint stored in a signed audit event | Analysis never writes to the ledger (asserted in tests). |
| Audit tampering | Tenant hash chain + HMAC-SHA256; database triggers reject update/delete on audit, approvals, postings and ledger | Tamper test detects a modified event. An administrator holding both database and key is outside HMAC protection; no external anchor yet. |
| Malformed input / resource abuse | Strict Pydantic contracts (no floats, booleans or numeric strings as money), 1 MiB body cap, duplicate JSON keys rejected, per-route rate budgets (end-user address, infrastructure address when supplied, global ceiling), hourly signup ceiling, counters held in process memory so hostile traffic never writes to the database, account cap 5,000 | Validation tests; the forged-header bypass of per-address limits was reproduced on production on 20 Oct; address-independent limits now carry the load. Not a distributed WAF: a botnet with many real addresses is only slowed. |
| Stale credentials | Expired sessions are purged at login; failed-attempt rows pruned after 60 minutes; financing quotes kept in tab-scoped storage, validated on load and cleared at sign-out | Covered by tests. |
| Secret leakage | Server-only credentials; nothing sensitive in the JS bundle; ignored `.env`/`.private`; known-pattern history scan in CI | Pattern scan cannot prove absence of every secret. |
| Storage loss | Persistent Turso primary over HTTPS; signing key preserved across deploys; startup refuses an invalid key and **refuses to start on Render or Vercel without the persistent database** | Workspace export is not a full disaster-recovery restore; no restore drill yet. |

## 4. Known-risk list (honest limitations)

1. **No bank connection.** Records are self-reported; approval records a payment in the ledger but moves no money.
2. **Free hosting.** Render Free cold starts (30–60 s on first request) and Gemini free-tier quotas can make the first action slow or the online assistant unavailable. Deterministic finance keeps working.
3. **Forecasts are deterministic scenarios**, not probabilistic predictions; future sales, tax and seasonality are not modelled.
4. **Financing match depends on quote accuracy.** SafeLedger does not verify lenders, eligibility or regulatory disclosures.
5. **Duplicate detection is heuristic.**
6. **Administrator trust.** Whoever controls the database and the signing key could rewrite history; external anchoring and key rotation are future work.
7. **No MFA, no email recovery service** (one-time recovery code only).
8. **Testing is finite.** No independent penetration test, physical iOS/Android device lab or full WCAG audit has been performed.

## 5. What we will not claim

We do not describe SafeLedger as bank-grade, breach-proof, certified, compliant with a specific regulator, or an autonomous payment agent. It is a tested competition prototype with server-enforced controls and disclosed limits.
