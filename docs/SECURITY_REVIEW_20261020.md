# Security and quality review, 20 October 2026

Scope: the live site (https://safeledger-ai.vercel.app, API on Render), the repository at `0e01d5c`, and a local production-like build (production CSP and headers, same-origin API proxy, throwaway database). Method: source review of authentication, tenancy, approval and agent code; passive probes of the live site; adversarial and randomized tests; browser checks at 360, 390, 768, 900, 1024 and 1366 px; WCAG 2 A/AA scans with axe-core; dependency advisories. **No accounts were created and no passwords were submitted on the live site**; everything that needs a session ran against the local build. One live load probe (finding 0) did cause a temporary outage, described below.

This is an internal review, not an independent penetration test.

## Findings and fixes

| # | Severity | Finding | Evidence | Fix (release 0.4.1) |
| --- | --- | --- | --- | --- |
| 0 | **High (availability)** | Every request that was rejected for rate limiting, and every unauthenticated request, still cost a **database write** (the per-minute budget row) on the single remote Turso writer. A burst of parallel hostile requests therefore jams the writer and every user gets 503. | The review's own live test, 300 parallel unauthenticated requests, took the production API offline for about 8 minutes (01:59–02:07 Dhaka, 20 Oct); it recovered by itself. The state before the fix was the same for any attacker. | Rate-limit counters and login lockouts moved to process memory (`api/app/ratelimit.py`): hostile and rejected traffic now costs no database write (asserted by a regression test that forbids write transactions during a 300-request parallel flood). A per-address request ceiling (1,200 per minute) applies before any database access, and write transactions are serialized inside the process so bursts queue instead of racing the single remote writer. |
| 1 | **High** | Per-address rate limits could be bypassed. uvicorn trusts `X-Forwarded-For` and used its left-most value as the client address. A caller reaching the API directly could rotate it per request and evade the signup, login, recovery and unauthenticated-probe limits. | Live: 24 requests with a fixed address were limited after 20; 24 requests with a random forged header were never limited. A second live probe of the first fix showed Render exposes **no** trustworthy address (no `cf-connecting-ip`, no infrastructure-appended entry), so a per-address key cannot be made unforgeable on this platform. | Per-address limits are now documented as a fairness tool only. Security rests on limits that do not depend on the address: per-account failed-attempt lockouts, global ceilings, an hourly signup cap, memory-only counters and bounded hashing concurrency. `security.client_keys`, `ratelimit.py`. Behind Vercel the address is set by Vercel and reliable; only direct callers of the Render origin can forge it. |
| 2 | **High** | Password guessing was capped only per minute, which allows about 11,500 guesses per day per account, and every attempt (including successful ones) counted. | Source review of `accounts.login`. | Rolling 15-minute failed-attempt lockouts per account (40, address-independent), plus per account+address (8) and per address (40) as fairness limits, checked before any hashing. Successful logins do not count. Same for recovery. |
| 3 | Medium | Weak passwords such as `password123` were accepted. | Source review. | Common-password list, username-as-password and low-variety rejection at signup and recovery (not at login, so existing users can still sign in). Friendly UI message. |
| 4 | Medium | Account-capacity exhaustion: with the bypass above, an attacker could fill the 1,000-account cap and block new signups during judging. | Derived from finding 1. | Hourly global signup ceiling (200), per-minute global (30) and per-address limits; cap raised to 5,000. |
| 5 | Medium | Financing engine edge case (found by randomized testing): a tiny principal split over many installments produced BDT 0 payments, and the "lowest balance with financing" included the pre-loan day-0 balance, contradicting the fit status. | `test_financing_fuzz.py` failed on two invariants. | Quotes whose principal is smaller than the installment count, or that yield an empty installment, are rejected; the lowest balance is computed over post-financing days only. |
| 6 | Medium | Layout bug at tablet width (768 px): page-level horizontal scroll on five pages because the header action buttons could not wrap. | Browser measurement: 21–47 px overflow. | Header wraps between 761 px and desktop; verified zero overflow at all six widths. |
| 7 | Medium | UX trap: an approver could start a payment proposal that they are then forbidden to approve, blocking the invoice for 15 minutes. | UI review. | Only the owner sees "Review payment" and the assistant's proposal permission; approvers see an explanation. The server rules are unchanged. |
| 8 | Low | A deployment on Render without the persistent database variables would have started on ephemeral SQLite and silently lost the ledger (audit item SL-008). | Source review. | Hosted startup now fails closed unless `SAFELEDGER_ALLOW_EPHEMERAL_DB=1`. |
| 9 | Low | Expired sessions were never deleted. | Source review. | Purged at login. |
| 10 | Low | Financing quotes (private business data) lived in `localStorage` and were trusted when loaded. | Source review. | Tab-scoped `sessionStorage`, strict validation on load, cleared at sign-out. Verified against injected malformed and HTML-containing entries. |
| 11 | Low | Two diverging `vercel.json` files (audit item SL-011). | Source review. | Identical headers and rewrites; locked `npm ci`; added `object-src 'none'` and `Cross-Origin-Opener-Policy`. |
| 12 | Low | Friendly messages missing for lockout, busy hashing, capacity and origin errors. | UI review. | Added. |

## Checks that passed (no change needed)

- **Production headers** on the site and through the API proxy: CSP (`default-src 'self'`, no inline script or style), HSTS, `X-Frame-Options: DENY`, `nosniff`, `no-referrer`, Permissions-Policy, `Cache-Control: no-store` on API responses. API docs and OpenAPI are closed in production (404).
- **CSRF and origin:** a request without the client header is refused (403); cross-origin preflights receive no `Access-Control-Allow-Origin`; mutations need an exact origin.
- **Input handling:** malformed JSON (422), duplicate keys, 2 MB body (413), junk bearer token (401), unsupported content type (415).
- **Stored XSS:** an invoice memo containing `<img src=x onerror=alert(1)>` renders as inert text; no element is created and no script runs. Lender names with HTML tags render as text.
- **Authorization:** owner-only, approver-only and viewer rules, independent approval, replay and tamper cases, cross-tenant isolation (existing suite). The new financing route is covered for anonymous, viewer and wrong-currency cases.
- **Dependencies:** `npm audit` (production and development): 0 vulnerabilities. `pip-audit` on `api/requirements.lock.txt`: no known vulnerabilities. A CI job now repeats both on every push (informational).
- **Secret scan:** known credential patterns, full history: passed.
- **Accessibility:** axe-core WCAG 2.0/2.1 A and AA rules on all eight pages as approver, and to the financing results in light and dark themes: zero violations. (Automated checks do not replace screen-reader and device testing.)
- **Randomized financing check:** 119 seeds × 120 rounds (about 14,000 random quote sets): no crashes; money conserved exactly (payments minus interest equal principal, total cost equals interest plus fees); fitting offers always rank first; ranking independent of input order.

## Residual risks (also in `docs/SECURITY_SELF_ASSESSMENT.md`)

- Rate-limit counters and lockouts are in memory: they reset when the single API instance restarts or sleeps, and are not shared across instances. A multi-instance deployment would need a shared store.
- A direct caller can forge the client address, so per-address limits do not stop them; only the address-independent limits (per-account lockouts, global and hourly ceilings) apply. They can also be used to deny service for a known username for up to 15 minutes, or to exhaust the hourly signup ceiling. No WAF or CAPTCHA.
- Free-tier limits: Render cold starts (mitigated by the keep-alive workflow, which is best-effort), Gemini quota.
- An administrator holding both the database and signing key can rewrite history; no external anchor yet.
- No MFA, no email-based recovery, no independent penetration test, no physical-device or screen-reader audit.

## Full review (release 0.7.6)

Second pass on 20 October 2026, after releases 0.5 to 0.7.5 added accounts, sharing, two-step sign-in, email codes, photo reading and 36 languages. Scope: every route in `api/app` (authentication, sessions, recovery and reset, two-step sign-in, workspaces, sharing, clearing, records, proposals and approvals, assistant, scan, language, exchange rate, agent), the mail relay, the public endpoints, rate limiting, CORS and CSRF, headers (both `vercel.json` copies and the live site, read-only), the front end (rendering of user text, PDF, storage, third-party requests), dependencies and repository history. Method: source review, new regression tests, `scripts/security_probe.py` against a local server, a local browser session. **No accounts were created and no load, fuzz or probe traffic was sent to the live site**; only `GET /api/health`, the home page headers and `/docs` on the API origin were requested. Internal review, not an independent penetration test.

### Found and fixed in 0.7.6

| # | Severity | Finding | Evidence | Fix |
| --- | --- | --- | --- | --- |
| A | **Medium** | The recovery key bypassed two-step sign-in. `POST /api/auth/recover` reset the password and issued a session from the username and the static recovery key alone. | Source review of `accounts.recover`; `test_recovery_key_needs_the_second_step_when_two_step_is_on`; probe checks 58 and 59. | Recovery now needs an authenticator or backup code when two-step is on, checked before the key is spent; the sign-in page asks for it. |
| B | **Medium** (abuse, availability) | The site could be used as an open mailer. Signup with an email, "add email" and invitation emails had no per-recipient or site-wide ceiling, so a free account could flood any address and exhaust the relay's daily quota (about 100 a day on a personal Gmail), which would switch off email codes for everyone during judging. | Source review of `mailer`, `profile.set_email`, `workspaces.invite`, `accounts.signup`; tests for each path. | Every message passes `mailer.reserve()`: 5 an hour per recipient, 40 an hour site-wide (verification and invitations), 90 a day in total. The address is never logged. |
| C | Low to medium (cost) | `GET /api/i18n` is public. A language that could not be completed made every request call the cloud model again, up to the 30 a minute global budget (about 43,000 a day), draining the free quota that photo reading and the assistant share. | Source review; `test_failed_translation_attempts_back_off`. | A translation attempt that gains nothing or fails pauses further attempts for that language for 5 minutes. A language that is making progress is not slowed. |
| D | Low | `POST /api/auth/reset/confirm` answered differently for registered and unregistered emails ("password too weak" and "second factor required" appeared only for real accounts), allowing probing of which emails have accounts and which use two-step. | Source review; `test_reset_confirm_answers_alike_for_known_and_unknown_addresses`. | Identical answers until a correct emailed code is presented; asking for the second factor no longer burns the code. |
| E | Low (privacy) | The owner's "smart assist off" switch did not apply to invited viewers or approvers: their questions, sentences and the agent planner sent the owner's cash facts to the cloud model under the teammate's own setting. | Source review; `test_teammates_cannot_send_owner_records_to_the_model_when_the_owner_turned_it_off`. | The owner's switch also governs teammates' requests in that workspace (`WORKSPACE_OWNER_SMART_ASSIST_OFF`). |
| F | Low (functional) | A member the owner removed (or who left) could never be invited again: joining answered "already a member". | `test_a_removed_member_can_be_invited_again`. | The old seat is reactivated with the newly invited role; an owner's own seat can never be changed this way. |
| G | Low (hardening) | Email codes were hashed with an all-zero key if `SAFELEDGER_SIGNING_KEY` was missing. Production always has the key, so this was not exploitable there. | Source review. | The server refuses (`SIGNING_KEY_NOT_CONFIGURED`). |
| H | Low (quality) | The first load of the workspace raced with its own cancellation (visible with `npm run dev`, where React mounts twice): "signal is aborted without reason" and a stuck "Loading your verified financial overview". Production builds mount once. | Reproduced in a local browser, then verified fixed. | Each load belongs to its own mount. |

Documentation fixed: invitation expiry (owner-chosen, default 72 hours, at most 168; the text said one hour) and the stale "no MFA" statements.

### Checked and sound (no change needed)

- **Authorization on every route.** Business scope always comes from the session (`principal`); object identifiers (proposal, trace, member, invitation, workspace) are filtered by tenant or by the caller's own account; owner-only, approver-only and viewer rules are rechecked inside the write transaction; viewers cannot add records, propose, approve or manage people; owners cannot approve; an approver cannot approve their own proposal; roles in request bodies are rejected (`extra=forbid`). Concurrent and replayed approvals post exactly once (existing tests).
- **CSRF.** Session cookies are HttpOnly, SameSite=Lax and Secure on hosted platforms; every state-changing request with a cookie needs an exact allowed Origin plus `X-SafeLedger-Client`, and every POST must be `application/json`. No GET changes state apart from the public language cache.
- **Injection.** All SQL is parameterised (no string-built statements); JSON bodies reject duplicate keys and non-finite numbers; photo and scan uploads are checked by size, base64 validity and magic bytes (SVG refused); model output (sentences, photos, translations, agent plans) is parsed into typed drafts or fixed codes and never saved without the owner confirming through the records API.
- **Mail relay.** Recipients pass a strict address pattern (no line breaks); subject and text are fixed templates; the relay URL must be a `https://script.google.com/` address; the secret is read from the environment only and never logged.
- **Transport and headers.** Live home page and API through Vercel: CSP `default-src 'self'` without inline script or style, HSTS, frame denial, nosniff, no-referrer, permissions policy; the API origin refuses `/docs`. Both `vercel.json` files carry the same security headers (the root copy adds caching rules and the old-address redirect).
- **Supply chain.** The built site makes no third-party request (no CDN scripts, no web fonts; the PDF library mentions a CDN address in a function the site never calls, and the CSP would block it). `npm audit --omit=dev`: 0 vulnerabilities. `pip-audit` on the lock file: none. Secret scan over 75 commits: clean.
- **Errors and logs.** Errors are short codes; database failures log only the exception type; mail failures log no address or body; no stack trace reaches a client (probe checks).

### Remaining risks, most important first

1. **Sign-in can be slowed for a known username.** After 40 recent failures against one username, sign-ins for it are limited to one attempt every 20 seconds, so an attacker who keeps trying can starve the real owner. The alternative (a hard lock) is worse. Client addresses are forgeable on this hosting, so per-address limits cannot help; a CAPTCHA or an edge firewall would.
2. **One password-hashing slot.** Hashing is serialised (one scrypt at a time, 8 second wait). A flood of junk sign-in or sign-up requests with forged addresses, up to the global caps (300 a minute for sign-in), can keep that slot busy and delay everyone's sign-in. Existing sessions are unaffected. Not tested live, by rule.
3. **Rate limits and lockouts live in memory.** They reset when the free server restarts and would not be shared across instances.
4. **"Two people approve" is per account, not per person.** One person can register two accounts. Without identity checks this cannot be solved; it is stated in the known-risk list.
5. **Invitation codes travel in the link** (`?join=`). They can appear in hosting logs until used or expired (default 72 hours; owners can pick 1 hour). A URL fragment would avoid server logs.
6. **Mail depends on one Gmail relay** with a small daily quota; the new ceilings protect it but do not enlarge it.
7. **Dependency hygiene.** The production lock file also installs the test runner (`pytest`, `pluggy`, `iniconfig`, `Pygments`); harmless at runtime but unnecessary. GitHub Actions are pinned to major tags, not commit hashes.
8. **No account deletion or data-erasure flow;** clearing hides data for 30 days and the signed history is append-only by design.
9. **The cookie name has no `__Host-` prefix;** the cookie is already Secure, HttpOnly, SameSite=Lax and path-scoped.
10. Administrator trust, no independent penetration test, no screen-reader or device lab: unchanged (see the self-assessment).

Result of the final run on release 0.7.6: `python -m pytest api/tests -q` gives 487 passed, 1 skipped and the two known Windows-only failures; `scripts/security_probe.py` against a local server passes 60 of 60 checks; `npm run build` and `node scripts/extract_ui_strings.cjs --check` pass.

## How to repeat

```bash
python -m pytest api/tests -q
python -m pytest api/tests/test_security_hardening.py api/tests/test_financing_fuzz.py -q
npm audit --prefix web && pip-audit -r api/requirements.lock.txt --no-deps --disable-pip
python scripts/security_scan.py
```
