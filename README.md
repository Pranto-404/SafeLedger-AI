# SafeLedger AI
Topic E — SME Finance Copilot. Competition prototype; synthetic data and sandbox only.

**Current checkpoint: M2 secure sandbox execution.** Authenticated financial APIs, deterministic analysis, separate human approval, transactional idempotent sandbox posting and signed audit traces are implemented and tested. The connected financial UI and LLM integration are upcoming milestones. Registration is unconfirmed. See PROJECT_STATUS.md before continuing.

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

The runner creates temporary private credentials, starts the real API, proves duplicate/viewer/hash denials, sends4 concurrent human approvals plus retries, verifies a single balanced posting, restarts the actual process, checks replay and offline audit hashes, then deletes private credentials. Public evidence goes in evidence/m2/. No real money or LLM calls. This is API E2E evidence; browser/mobile E2E is pending M4/M5.

M2 routes are documented in docs/API_CONTRACT.md. There is no public `/execute`; authenticated approval invokes a server-only executor atomically. An owner may import one validated snapshot into its own business; import never allowlists payees or configures limits. Those are trusted local admin decisions. Prototype DB/event caps, single BDT currency, full invoice payments and financial assumptions remain documented limits.
