# Native Vercel backend candidate — not deployed

The first phase is published at application commit25a255e on the existing Vercel frontend / Render Free backend / persistent Turso. The second phase is blocked by the connected Vercel tool returning403 for `challanger2/safeledger-ai`. No Vercel CLI binary or saved/environment authentication is available. Do not retry unchanged403, use a different account/team, remove deployment protection, or redirect production to an untested backend.

## Concrete prepared source

Run `python scripts/prepare_vercel_backend.py --output .private/vercel-candidate/source` with a new empty output directory. This copies only the runtime Python source and required fictional fixture data, pins existing runtime dependencies, exports `api.app.main:app` through `[tool.vercel]`, and creates a backend-only FastAPI function configuration with60-second maximum duration. It includes no .env, secret, auth state, SQLite, frontend dependencies, tests or evidence. Production root/web Vercel configs and Render remain intact.

This is a local source candidate, not a Vercel build or performance qualification. Official references reviewed18 October2026:
- https://vercel.com/docs/frameworks/backend/fastapi
- https://vercel.com/docs/functions/runtimes/python

## Required private hosting configuration

Use the existing authorized Vercel team and a Free/Hobby backend preview. Ensure no paid plan/add-on/billing activation. Transfer existing application environment values through private hosting configuration, including TURSO_DATABASE_URL, TURSO_AUTH_TOKEN, the exact normalized SAFELEDGER_SIGNING_KEY used by the live Render process, SAFELEDGER_COOKIE_SECURE=1, and existing free-model profile/key/billing-disabled acknowledgement. Do not create a replacement signing key. A legacy32-character hexadecimal Render key is doubled by render_start.sh; preserve its actual64-character effective value. Never write the values into this candidate or Git. Existing request budgets, auth sessions and ledger are database-backed, so they work across function instances. Hash concurrency lock is process-local only and not a global cost/concurrency guarantee.

Use the closest permitted free function region to the existing primary database after checking its region; do not claim a latency improvement before measuring it. Startup/lifespan must actually run schema/template initialization. Use a private preview/test tenant first; use the existing production signing identity only if validating existing signed records with the production database. A different-key staging deployment must use a different database and must not touch the shared production guest template.

## Acceptance before any cutover

1. Validate native build, runtime import/lifespan, persistent database and signed audit with production-compatible identity. Missing remote database must fail closed; no ephemeral SQLite fallback.
2. Test secure same-origin cookies through the frontend proxy, exact allowed Origin/CSRF,8-character signup/login/refresh/logout, zero-start account, isolated optional sample workspace, manual cash/invoice, idempotent concurrent request, historical signed proposal/ledger after appends, independent approval, exactly one posting, tenant isolation and shared database AI/auth limits.
3. Repeat login/balance/posting/audit after a subsequent native redeploy; measure actual cold/warm latency under bounded requests. Test free-model success/quota failure without paid retry/fallback.
4. Only then update the frontend API rewrite to the verified backend. Preserve Render as fallback until the complete public flow and persistence pass on the new origin. Do not delete the service/database.

Access required to resume: a Vercel connection or CLI authorized for the existing `challanger2` project/team. No password or token should be pasted into chat. This access blocker is separate from the already working public website and Git auto-deploy.
