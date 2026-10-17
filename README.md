# SafeLedger AI
Topic E — SME Finance Copilot. Competition prototype; synthetic data and sandbox only.

**Current checkpoint: M3 adapter implemented; live AI evaluation pending.** Authenticated financial APIs and secure sandbox execution remain verified. The bounded agent adapter/dispatcher are mock-tested; actual provider configuration, connected financial UI and deployment remain pending. Registration is unconfirmed. See PROJECT_STATUS.md before continuing.

## Local setup
Python 3.12 and Node 22.12+ (validated here on Node 24.19.0). Run from the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r api/requirements.lock.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m uvicorn api.app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd web
npm ci
npm run build
npm run dev
```
Open http://127.0.0.1:5173. Windows: use `.venv\Scripts\python.exe` instead of `.venv/bin/python`. API documentation: http://127.0.0.1:8000/docs. Health: `/api/health`; readiness: `/api/ready`. Standalone live smoke: `.venv/bin/python scripts/verify_bootstrap.py` (starts and stops its own local API). `SAFELEDGER_DB` selects a local SQLite path; parent directory must exist. Never expose this development server to the public internet as a financial service.

Frontend production deployment and a persistent Python backend are not configured. Vite's development proxy is local only; production needs an explicit same-origin reverse proxy or validated CORS configuration. Do not put SQLite on ephemeral serverless storage.

## Recovery
Read PROJECT_STATUS.md, NEXT_STEPS.md, docs/REQUIREMENTS.md and `git log -5 --oneline`. Do not re-read the PDFs unless a requirement is missing or changes. Verify the current test suite before editing. Source hashes are in docs/SOURCE_MANIFEST.json; attachments contain no implementation evidence.

## Safety and ownership
No real banking integrations. Never commit real financial data, IDs, passports, credentials or `.env` files. Owner must select the GitHub account/repository and provide registration status. Dependency licenses and a project license need an owner decision before public release. No compliance certification is claimed.


## M1 reproducible financial demo
After installing `api/requirements.lock.txt`, run:

```bash
.venv/bin/python scripts/m1_demo.py
```

It stages 45 synthetic invoices and 60 cash events into a temporary SQLite database, verifies fixed expected outcomes, and prints source-linked 7/30-day projections plus three fictional offers. It executes no payments and calls no AI provider. Regenerate fixtures with `.venv/bin/python scripts/build_fixtures.py`; byte/checksum reproducibility is tested. Invoice/event CSV samples are included; amounts are integer poysha, e.g. BDT35,000 = 3,500,000 minor units. M2 exposes these services through authenticated APIs; the standalone M1 demo remains credential-free. See docs/FINANCIAL_METHODS.md and evidence/m1/ for formulas, results and limitations.


## M2 local authenticated sandbox
Generate a private demo (random credentials,24-hour sessions, synthetic data only):

```bash
.venv/bin/python scripts/bootstrap_demo.py
source .private/demo/demo.env
.venv/bin/python -m uvicorn api.app.main:app --host 127.0.0.1 --port 8000
```

`source` is for Bash. Other shells must load the two environment variables privately using their own syntax. Generated `.private/demo/sessions.json` holds distinct owner/approver/viewer/agent bearer tokens: use them only in the Authorization header, never URLs, screenshots, shared chat, public frontend configuration or Git. POSIX directory/file permissions are700/600; check appropriate private ACLs on other operating systems. No public/default credentials or HTTP role-switch endpoint. Keep `demo.env` and SQLite together across restart; changing the signing key invalidates historical verification. Expired sessions require trusted local administrator provisioning; there is no public renewal/login or recovery endpoint yet. Bootstrap refuses to overwrite an existing demo.

For a complete automated live HTTP proof without handling credentials manually:

```bash
.venv/bin/python scripts/m2_http_demo.py
```

The runner creates temporary private credentials, starts the real API, proves duplicate/viewer/hash denials, sends4 concurrent human approvals plus retries, verifies a single balanced posting, restarts the actual process, checks replay and offline audit hashes, then deletes private credentials. Public evidence goes in evidence/m2/. No real money or LLM calls. This is API E2E evidence; M4 adds actual browser/mobile evidence below.

M2 routes are documented in docs/API_CONTRACT.md. There is no public `/execute`; authenticated approval invokes a server-only executor atomically. An owner may import one validated snapshot into its own business; import never allowlists payees or configures limits. Those are trusted local admin decisions. Prototype DB/event caps, single BDT currency, full invoice payments and financial assumptions remain documented limits.

## M3 bounded agent (live provider not yet evaluated)
Authenticated POST /api/agent/tasks accepts `{task,invoice_id?,allow_proposal:false}`. Model tool calls are schema-validated; all money/source facts come from backend services. Explicit allow_proposal=true with invoice_id only permits a pending proposal when caller and M2 policy allow it. AI cannot approve/execute. Rationale uses constrained codes/references rendered alongside verified facts; unverified model prose is never displayed.

Set SAFELEDGER_LLM_BASE_URL,SAFELEDGER_LLM_MODEL,SAFELEDGER_LLM_API_KEY privately. Compatible HTTPS /v1 endpoint must match the admin-configured host allowlist. No live provider key/model/budget is configured in this checkpoint. Tests use clearly labeled mocks/MockTransport; real-model evaluation remains pending. Missing service returns503,while deterministic financial APIs continue. See docs/M3_AGENT_DESIGN.md.

## Vercel and updates
Owner authorized Vercel/Git auto-deployment. Actual Git-project creation attempt returned403 Forbidden for scope challanger2; no deployment URL or automatic-update success is claimed. CLI fallback credentials are absent. See docs/DEPLOYMENT_STATUS.md and evidence/m3/vercel-attempt.json. Frontend hosting also needs an authorized durable Python backend: React-only Vercel hosting cannot make the SQLite finance workflow live by itself.

## M4 connected dashboard
With the private M2 API running on port 8000, run `npm ci --prefix web` then `npm run dev --prefix web`. Open the displayed localhost URL and paste a privately generated session token into the password field. Sign out of owner and sign in with the separate approver session to approve a proposal. Reload/sign-out clears the token; it is never stored in browser storage. No demo credentials ship in the application.

Eight views connect real APIs: overview, invoice register with source IDs, deterministic 7/30-day outlook and 30-day what-if scenario, fictional financing, bounded assistant, approval confirmation, verified audit JSON export, and owner-only immutable JSON import. All financial totals/policy decisions come from the backend. AI-offline errors do not disable deterministic finance. JSON import preserves the original request text so duplicate keys cannot be silently normalized by browser parsing. CSV file upload, real lenders and real payments are not provided. The UI deliberately has no independent role or tenant selector.

Browser proof (real Vite proxy/FastAPI/SQLite, private temporary sessions):

```bash
npm ci --prefix web
cd web && npx playwright install chromium && cd ..
.venv/bin/python scripts/m4_browser_demo.py
```

The runner starts/stops its own loopback servers on free ports and writes synthetic screenshots, server logs, audit export and browser-results.json to evidence/m4/browser. Set `SAFELEDGER_EVIDENCE_DIR` to a fresh directory to retain earlier runs. No browser trace/request-header recording is enabled because authorization headers are secrets. If using a separately installed Playwright/browser runtime, `SAFELEDGER_PLAYWRIGHT_MODULE` may select its module and `SAFELEDGER_CHROMIUM_MODULE` the optional @sparticuz/chromium module entry. This is test infrastructure only, not a production browser dependency. Default Playwright browser download failed in the current environment; actual successful execution used Playwright1.62.1 + npm-provided Chromium153.0.8010.0. See evidence/m4/ for setup failures and actual successes.

For a custom local backend port, set `SAFELEDGER_DEV_API_URL=http://127.0.0.1:PORT` when starting Vite. This setting is proxy-only, not a browser credential or production deployment configuration.

## M5 security and failure-path QA
After installing the locked Python/web dependencies and Playwright Chromium,run:

```bash
SAFELEDGER_EVIDENCE_DIR=evidence/new-m5-run .venv/bin/python scripts/m5_browser_qa.py
```

This reuses the local real-server harness with private fixture setup,no public test/admin endpoint. It exercises server-denied expired/tampered approvals,rejection replay,tenant/role bypass,network failure/recovery,in-flight logout isolation,inert stored HTML/instruction memos,session401 and10 automated axe accessibility scans. No real LLM/payment call. Environment-specific optional browser runtime settings remain as documented for M4. The full successful owner→independent approval→ledger workflow remains `scripts/m4_browser_demo.py`.

Known-advisory checks:`npm audit --prefix web` and `python -m pip_audit -r api/requirements.lock.txt` (install pip-audit separately as a QA tool). `python scripts/security_scan.py` checks limited credential patterns across reachable Git history/tracked working files and ignored private paths,reporting locations only. Scope is intentionally stated;passing is not proof of complete security. esbuild0.28.1 is a deliberate override to remediate the reported dev-server advisory;reconsider when Vite supports it natively. Full M5 findings,evidence and remaining release limits:docs/M5_QA_REPORT.md.
