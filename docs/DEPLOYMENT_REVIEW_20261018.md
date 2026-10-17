# SafeLedger deployment review — 18 October 2026

The user's GitHub changes were retained. This review starts from Pranto-404/SafeLedger-AI commit f606f9f, not the older 842edbf checkout. Uploaded source matches fetched main after ignoring CRLF, except its fixture manifest. The original ZIP and old worktree were not overwritten.

## What works

| Check | Evidence | Limit |
|---|---|---|
| Vercel frontend | Page opens and renders private workspace login | Authenticated UI not exercised in this review |
| Vercel → Render | /api/health and /api/ready return HTTP 200 through Vercel and directly from Render | Does not prove ledger persistence or auto-deploy |
| Existing real-model report | 5/5 tasks, 2/2 attack cases, 1/1 policy case; 14 calls; exact hashes match the uploaded provider, runner and evaluator bytes | Owner-supplied historical run; no new live model run or billing verification |
| Reviewed backend | 298 tests passed; 2 known warnings | Local regression, not independent audit |
| Frontend build | TypeScript and Vite production build passed | Existing installed lock-matched dependencies reused |
| Cloud financial adapter | Actual remote database qualification, isolated synthetic tenant, 4 concurrent approvals; exactly 1 posting, reconciled balance and balanced ledger | Adapter support is not yet configured on Render; final reviewed run in evidence/deployment-review/cloud-finance.log |

## Problems found and changes

1. **Fixture reproducibility failed**: GitHub's manifest contained Windows-byte hashes although fixture blobs checked out on Linux use LF. Regenerated the manifest and pinned fixture JSON and shell scripts to LF. Initial regression: 272 passed, 1 failed; corrected reviewed regression: 298 passed.
2. **Hidden provider retries exceeded the advertised budget**: production-only 5xx retry could perform more HTTP attempts than the evaluator counted. Removed automatic retries and added tests that exercise the non-mock branch for 429/500/502/503/504. Preserved the user's working Gemini request format and prompt changes.
3. **Build identity could be stale**: health returned manual 4a334b3. Health now prefers Render's RENDER_GIT_COMMIT. Actual deployed source and subsequent Git auto-update still need dashboard confirmation.
4. **Signing identity could change silently**: startup generated a new key for malformed/missing values, invalidating signed history. Startup now requires a stable valid key. The existing 32-character hex doubling derivation remains unchanged for legacy compatibility; it does not add entropy. Verify the deployed normalized key before publishing. Never replace an existing ledger's signing key casually.
5. **Tokens were logged and expired without recovery**: seed now saves initial tokens to an exclusive mode-0600 private file, never stdout. Added trusted renewal that only renews existing active demo identities, preserves data/roles, keeps the 24-hour maximum, and rolls back if an identity is missing or changed.
6. **Render SQLite is ephemeral**: optional Turso primary HTTP support was integrated with the user's Render topology. Lost streams fail closed; there is no transaction retry or local replica. Existing production still uses SQLite until an operator preserves/migrates data and configures the remote variables. No paid disk was purchased.
7. **Original ZIP contains secrets/runtime state**: .env, .git, local SQLite and caches are inappropriate for a public submission. The reviewed source package excludes those; original upload was preserved. The API key was not printed or sent to a model during review.

## Trusted operator steps before release

- Preserve the actual Render database and its signing identity. Inspect whether it has proposals/postings; do not silently substitute an older synthetic cloud seed. If migration is needed, move the complete schema/data and verify audit signatures using the same key before cutover.
- Configure TURSO_DATABASE_URL and TURSO_AUTH_TOKEN privately on Render; this review did not change hosting settings. /api/ready will identify libsql after a correct cutover. Do not use public Vite variables for secrets.
- Retrieve credentials only through a private operator channel. For expired sessions run, on the backend with the existing DB and normalized signing key:

  `python scripts/renew_demo_sessions.py --output .private/render/renewed-sessions.json --ttl-seconds 86400`

  The destination must be new and inside .private. It does not extend old sessions or alter authority.
- Both hosting dashboards redirected this browser to sign-in; account configuration/build logs were not inspected. The local Browser extension's control tool was absent. Do not interpret public endpoint checks as dashboard access.
- A Git push dry-run was rejected by automatic approval review because publication was not sufficiently authorized by the inspection request. No push/deployment was performed. Obtain explicit approval for publishing this concrete revision, then re-fetch and check expected main HEAD before pushing without force.
- After an authorized publish, verify Vercel/Render deployed commit, private login, owner proposal, independent approval, replay/concurrent denial semantics, one posting and audit, then restart/persistence and actual auto-deploy.

Budget remains BDT0. No paid provider, plan, disk, credit purchase or billing activation was used. This is a reviewed competition prototype, not a production financial service or independent security certification.
