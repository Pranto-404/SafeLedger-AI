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

## How to repeat

```bash
python -m pytest api/tests -q
python -m pytest api/tests/test_security_hardening.py api/tests/test_financing_fuzz.py -q
npm audit --prefix web && pip-audit -r api/requirements.lock.txt --no-deps --disable-pip
python scripts/security_scan.py
```
