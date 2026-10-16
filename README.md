# SafeLedger AI
Topic E — SME Finance Copilot. Competition prototype; synthetic data and sandbox only.

**Current checkpoint: M0 bootstrap.** No financial execution, authentication or LLM integration is implemented. Registration is unconfirmed. See PROJECT_STATUS.md before continuing.

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
