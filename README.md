# SafeLedger AI

Private financial recordkeeping at https://safeledger-ai.vercel.app. Create a username/password account: every workspace starts with BDT0, no invoices and no cash events. Add your own cash activity and invoices in **Data**, or import your own conforming records JSON into an empty workspace. No demo, guest example or fictional lender offers are exposed by the product.

Passwords accept 8–128 exact characters and have a strength indicator. Sessions use Secure HttpOnly cookies on the deployed site; no token needs to be pasted. Save the one-time recovery code securely. A password reset rotates the code and revokes all sessions. Losing both the password and recovery code prevents self-service recovery; no email service is configured.

Cash amounts use integer poysha and exact decimal validation. An unpaid invoice affects the forecast, not cleared cash. Owners explicitly allow a payee and create a proposal; a separately registered, invited approver reviews it. Approval creates a ledger record once, with signed audit evidence. **No bank connection, bank verification or bank transfer is provided.** Record accuracy depends on the records you enter.

Export records privately with **Export records**. Existing personal accounts, cash records, postings and signed history are retained. Older sample workspaces are access-disabled and archived without deletion; accounts with only an old example receive a new empty personal workspace on password login.

The landing page, workspace and optional Assistant load separately. No external model is contacted on startup or when opening the Assistant. A request needs explicit consent to share non-confidential details. The free provider may use submissions to improve its services: do not submit confidential, sensitive or personal information. The deterministic dashboard, forecasts and approval controls work without AI. There is no paid fallback.

## Run and verify locally

Use Python3.12 and Node22. Install `api/requirements.txt`, `api/requirements-dev.txt` and `npm ci --prefix web`. Set a private `SAFELEDGER_DB_PATH` and `SAFELEDGER_SIGNING_KEY` (see `.env.example`); never publish secrets. Run `python -m uvicorn api.app.main:app`, then `npm run dev --prefix web`. New databases start empty. Keep the signing identity and persistent database together across deployments.

```sh
python -m pytest api/tests -q
npm run build --prefix web
SAFELEDGER_BROWSER_SCRIPT=scripts/real_records_browser.cjs python scripts/run_finalization_browser.py
```

The finite browser suite uses isolated test records and does not call a real model. It needs a Playwright Chromium installation; `SAFELEDGER_CHROMIUM_MODULE` can select an installed serverless Chromium runtime. Current evidence is in `evidence/real-data/` and release status in `REAL_DATA_CHECKPOINT.md`.

## Hosting and limits

Vercel serves the frontend; Render Free currently handles the API with persistent Turso storage. No paid service is enabled. Render cold starts and free quotas remain. Native Vercel FastAPI preparation is in `scripts/prepare_vercel_backend.py`; the generated candidate excludes development fixtures. Backend cutover requires a successful authenticated preview and persistence qualification before changing the working production route.

This is an application release, not an independent security certification, bank service or guaranteed availability contract. Historical competition documents, videos, sample fixtures and reports remain under their original paths for provenance; their demo/token instructions are superseded. See `docs/HISTORICAL_README.md` for those development-only instructions.
