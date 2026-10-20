# Security self-assessment: permission tiers and known-risk register

Release 0.7.6 (accounts, languages, photo reading, landing page), 20 October 2026. Earlier text describes the 0.4.1 baseline; section 10 lists what changed and section 11 the full review of 20 October. This is an internal assessment by the team, not an independent penetration test or certification. Evidence: `api/tests/` (490 backend tests, 487 passing on Windows with 2 Windows-only failures and 1 skip, plus a 14,000-scenario randomized check of the financing engine (see `docs/SECURITY_REVIEW_20261020.md`)), `.github/workflows/ci.yml`, `scripts/security_scan.py` and the release notes in `docs/`.

## 1. Design principle: the AI is never the authority for money

Capzoryx Copilot treats the language model, the browser and every user-supplied text as untrusted. Money, identity, permissions and execution are decided only by server-side policy over verified records:

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

Roles come from authenticated server state, never from a request body. Invitations are one-time, hashed and expire after the time the owner chooses (default 72 hours, at most 168); they can grant only approver or viewer. Hiding a button in the UI is never the control: every route rechecks the role inside the transaction.

## 3. Threats, controls and residual risk

| Threat | Implemented control | Evidence / residual risk |
| --- | --- | --- |
| Password guessing | Salted scrypt (N=32768, r=8, p=3), 8–128 exact characters, common-password and username-as-password rejection at signup/recovery, rolling 15-minute failed-attempt lockouts per account (40) plus per account+address (8) and per address (40), checked before any hashing, bounded hashing concurrency | Tests for hashing, lockouts, forged-header resistance and timing-equalized unknown users. Per-address limits can be forged by a direct caller of the API origin (the platform exposes no trustworthy address), so the per-account lockout is the binding control. Optional TOTP two-step sign-in (section 10); the recovery key and the email reset both ask for it when it is on. |
| Session theft / CSRF | Secure HttpOnly SameSite=Lax cookie, 24 h expiry, server-side revocation, exact Origin plus `X-SafeLedger-Client` header on every mutation | CSRF and logout tests. A compromised device remains out of scope. |
| Tenant escape / IDOR | Business scope from session; membership-checked switching; object IDs filtered by tenant | Cross-tenant read/write tests return 403/404 with no leak. |
| Self-approval / role escalation | Distinct approver required; proposer can never execute; invitations limited to approver/viewer | Adversarial tests for self-approval, forged role fields and invitation reuse. |
| Payment tampering / replay | Proposal binds payee, amount, currency, source hash, dataset version, proposer and 15-minute expiry with HMAC; approval must echo the exact action hash; `BEGIN IMMEDIATE` atomic posting; unique constraints | Concurrent approvals produce exactly one posting; replay returns the same posting; ledger deltas sum to zero. |
| Duplicate invoice payment | Canonical vendor + normalized reference; similarity ≥ 0.85 flags possible duplicates; execution blocked until reviewed | Heuristic: may over-flag similar references or miss unrelated-number duplicates. |
| Prompt injection (memo, task text) | Memos are escaped untrusted data; model can only pick from finite typed read/propose tools; second stage may return only fact IDs and reason codes, validated against server facts | Injection tests in suite. Finite evaluation, not proof that every attack fails. |
| AI fabricating numbers | All displayed amounts come from deterministic objects; model output with invented amounts, IDs or prose fails validation | Mocked and live synthetic diagnostics. No statistical accuracy claim. |
| Private data sent to AI provider | On-device intent model answers first; out-of-domain and security prompts are never sent unless the owner insists; the cloud is used only while the owner's **smart assist** switch is on (it is on by default for a new account, and the owner's switch also governs invited teammates); only the current question, a short text of figures (no supplier names or memos) or the photo leave. Agent runs need an explicit consent flag and send the chosen invoice | Own acceptance script: 36/36 supported, 22/22 off-topic kept local, 8/8 security prompts refused, zero external calls. Independent fresh set (95 prompts): off-topic 100% kept local, 41.7% of security prompts recognised by the on-device layer; the server, not the assistant, enforces authority (`docs/LOCAL_ASSISTANT_EVALUATION.md`). Finance questions wrongly judged off-topic can be sent only through an explicit user choice plus the permission card. Free provider terms may allow the provider to keep and use submissions; until 20 Oct the Settings text said the opposite, and it now says the free service may keep what it receives. |
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
4. **Financing match depends on quote accuracy.** Capzoryx Copilot does not verify lenders, eligibility or regulatory disclosures.
5. **Duplicate detection is heuristic.**
6. **Administrator trust.** Whoever controls the database and the signing key could rewrite history; external anchoring and key rotation are future work.
7. **Two-step sign-in is optional** (off until a person turns it on). Recovery is by a one-time recovery key or, when the site's mail relay is configured, by an emailed code; with two-step on, both also need an authenticator or backup code, so losing the phone *and* the backup codes means losing the account.
8. **Testing is finite.** No independent penetration test, physical iOS/Android device lab or full WCAG audit has been performed. An automated axe-core scan (`scripts/axe_scan.cjs`) found four issue types on 20 Oct, all fixed; it is clean on 20 views, which is not a substitute for screen-reader testing.
9. **Reserve and payment limit are fixed.** Each workspace starts with reserve 0 and a payment limit of 100,000 currency units and no screen changes them.
10. **No erasure, no record editing, no restore.** Clearing data hides it for 30 days; saved records cannot be edited or deleted; the JSON backup has no import path.
11. **Interface translations are machine-made and unreviewed**; some static language files miss the newest phrases (English shows until the server translates them).

## 5. What we will not claim

We do not describe Capzoryx Copilot as bank-grade, breach-proof, certified, compliant with a specific regulator, or an autonomous payment agent. It is a tested competition prototype with server-enforced controls and disclosed limits.

## 10. Changes in release 0.5 to 0.7

New controls
- **Two-step sign-in:** TOTP (RFC 6238) with replay protection, hashed one-time backup codes and a sealed secret; enabling and disabling need the password. Reset by email also asks for the second factor when it is on.
- **Email codes:** six digits, HMAC-hashed, ten-minute expiry, five attempts; replies for unknown addresses are identical to known ones. Mail goes through a relay that checks a shared secret; failures never log addresses.
- **Sign-in (0.7.5):** usernames are canonical lowercase and trimmed (any capitalisation signs in; signup and the database refuse case-variant duplicates, and a one-time migration lowercases older rows and reports collisions). Failed sign-ins always return the same generic answer, whether or not the account exists. "Keep me signed in" gives a 30-day server session and matching HttpOnly, SameSite=Lax (Secure in production) cookie; otherwise 24 hours. Logout and password change revoke sessions on the server, and switching workspace keeps the session's remaining lifetime. Lockouts report how long to wait (Retry-After): 8 failures from one client and name lock that client for up to 15 minutes, and a success clears it; 40 failures against one name from many clients slow that name to one attempt per 20 seconds instead of locking out the real owner, so an attacker cannot lock someone out, and guessing speed stays capped. The browser may offer to save the login through the standard password manager; the password is never stored by the app, only the last username on the device.
- **Sessions:** logout ends the server session; a password change signs every other device out; per-account failure lockouts and address-independent request budgets.
- **Sharing:** roles are enforced on the server; invitation links are single use, expire, and the public preview reveals only the workspace name, role and inviter name for a valid link.
- **Clearing data:** owner-only, soft archive with a 30-day restore (the ledger itself stays append-only).
- **Photo and chat records:** model output is only a draft; amounts, currencies, dates and names are re-validated on the server and saved only through the owner-only, idempotent records API after confirmation. Images are size-limited and checked by magic bytes.
- **Languages:** `/api/i18n` is public but bounded: allow-listed languages only, only strings from a fixed server-side list are translated, outputs are sanitised (no markup, placeholders preserved), and the work is cached so it runs at most once per language.

Evidence and how to repeat it
- `python -m pytest api/tests -q`: 490 tests; on Windows 487 pass, 1 is skipped and 2 fail (a POSIX file-mode check and a CRLF fixture-hash check), and all pass on Linux CI.
- `python scripts/security_probe.py http://127.0.0.1:8000`: 60 black-box checks (anonymous access, origin enforcement, hostile input on public endpoints, error shape, cookie flags, oversized bodies, session replay and revocation, lockout, cross-account isolation). Local servers only.
- `python scripts/security_scan.py` (secret scan over the full history), `npm audit --omit=dev` and `pip-audit` on the lock file: clean at the time of writing.
- Frontend: no inline script or style, no `innerHTML`, `eval` or dynamic code; CSP `default-src 'self'`.

Known limits, unchanged or new
- Client addresses are forgeable on the free hosting tier, so limits are per account and global, not per address.
- Email delivery depends on a Gmail account through Apps Script (about 100 recipients a day for a personal account).
- Translations and photo reading use a cloud model; a wrong reading is caught by the confirm step, not by the model.
- Nothing connects to a bank or wallet; planned import features would only create drafts for the owner to confirm.

## 11. Full security review of 20 October 2026 (release 0.7.6)

An internal white-box and local black-box review of every route, the mail relay, the public endpoints, rate limiting, headers, dependencies and the front end. Details, evidence and the ranked list of remaining risks: `docs/SECURITY_REVIEW_20261020.md`, section "Full review (release 0.7.6)". Fixed, each with a regression test in `api/tests/test_security_review_20261020.py`:

- **Recovery key bypassed two-step sign-in** (medium): with two-step on, the recovery key plus the username reset the password and signed in without the second step. It now needs an authenticator or backup code, like the emailed reset.
- **Mail sender abuse** (medium, availability): anyone with a free account could make the site email any address (signup, add-email, invitations), flooding a victim and burning the daily quota of the Gmail relay. Now at most 5 messages an hour per recipient, 40 an hour site-wide for verification and invitation mail, and 90 a day in total (`SAFELEDGER_MAIL_DAILY_CAP`); password-reset mail is exempt only from the hourly site-wide ceiling.
- **Language endpoint quota drain** (low to medium, cost): a language that could never be completed made every public request call the cloud model again (up to the 30 a minute global budget). An attempt that gains nothing or fails now pauses further attempts for that language for 5 minutes.
- **Reset confirmation revealed account existence** (low): "password too weak" and "second factor required" answers differed between registered and unregistered emails. Answers are now identical until a correct emailed code is presented.
- **Owner's smart-assist switch did not protect teammates' requests** (low, privacy): an invited viewer or approver could send the owner's records to the cloud model while the owner had smart assist off. The owner's switch now governs every teammate's request in that workspace.
- **A removed member could never be invited again** (functional): the old seat is now reactivated with the new role.
- **Email codes could be hashed with a public all-zero key** if the signing key were missing (hardening): the server now refuses instead.
- Front end (not a security issue): a race in the first workspace load, visible in the development server as "signal is aborted without reason" and a stuck overview.
- Documentation corrected: invitation expiry (owner-chosen, default 72 hours) and the optional two-step sign-in.

Remaining limits, in plain terms: a determined attacker who knows a username can still slow that account's sign-in (one attempt every 20 seconds once 40 recent attempts failed) and can keep the single password-hashing slot busy, delaying everyone's sign-in; this is the cost of free hosting with forgeable client addresses and no CAPTCHA or WAF. Independent approval is per account, not per person (one person can register two accounts). Rate-limit counters are in memory and reset when the server restarts. Invitation links carry the code in the web address, so it can appear in hosting logs until it expires or is used.

## 12. Additions on 20 October 2026 (evening, while writing the technical documentation)

- **Language files could be erased by the server.** When the server had no translations (a fresh database or no model key), its empty answer replaced the shipped static translation file in the browser and the emptiness was cached. Fixed: server answers are merged into what the browser already has (`web/src/i18n.tsx`, `scripts/check_i18n.cjs`).
- **Accessibility scan of the current build** found four issue types the earlier review had not seen (dimmed landing steps, a profile button whose spoken name omitted its visible text, a low-contrast phone menu and scrollable tables that could not be reached by keyboard). All four were fixed; `scripts/axe_scan.cjs` is clean on the sign-in page and nine workspace pages at desktop and phone width.
- **Wording that overclaimed was corrected:** "nothing is kept for training" (Settings), "backup file for restoring" (Settings) and "over 170 currencies" (landing page, README; the code has 165, the list shows 155, 152 had a live rate that day).
- Full detail and the complete cross-check: `submission/Capzoryx_Copilot_Technical_Documentation.pdf`, sections 7.9 and 13.
