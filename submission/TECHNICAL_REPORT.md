# SafeLedger AI — current technical report

18 October 2026 · Topic E, AI as a Financial Participant · Public financial simulation

Live application: https://safeledger-ai.vercel.app/
Repository: https://github.com/Pranto-404/SafeLedger-AI
Qualified product release:25a255e; final health/copy polish:4a4bbd7. Exact evidence and source hashes are in `evidence/finalization/`. This report describes the current product; earlier presentation/video artifacts are historical drafts.

## Problem and product

An SME owner needs to understand available cash, upcoming supplier obligations and the evidence behind a proposed payment. SafeLedger combines exact deterministic financial calculations with a bounded AI assistant and a separate human approval workflow. The Verified Decision Chain is: source evidence → calculation → recommendation → backend policy → independent human approval → one atomic sandbox posting → signed audit.

New personal accounts start at BDT 0 with no sample transactions. Users can enter their own non-sensitive figures or explicitly create a separate practice workspace with sample data. A login-free guest example is read-only. The application does not connect to banks, move real funds, underwrite loans or certify imported records as authentic.

## Architecture and persistence

React 19/TypeScript/Vite serves eight views: overview, data, invoices, cash flow, financing, assistant, approvals and audit. The frontend is on Vercel and proxies same-origin API calls to FastAPI/Pydantic on Render Free. Persistent Turso uses the primary-only Hrana HTTP adapter; local development uses SQLite. No authoritative local-cloud replica or ephemeral production ledger is used. Signed account, proposal, posting, audit and rate-limit state lives in the database.

A combined workspace endpoint returns a consistent snapshot rather than repeating seven independent data loads. The interface uses local system fonts and no new animation dependencies. The production frontend bundle after polish is approximately74.4kB gzipped JavaScript and4.85kB gzipped CSS. Small opacity/transform animations respect reduced-motion preferences. These bundle sizes are build measurements, not a guarantee of network latency or universal device performance.

A native Vercel FastAPI backend candidate has been prepared separately with runtime source/required fixtures only. Local import and persistent-database fail-closed behavior pass. Its deployment is blocked by403 access to the existing Vercel team/project and absent CLI authentication. No native runtime, speedup or migration is claimed. Render remains the actual backend.

## Data and calculations

All financial amounts use strict integer BDT minor units;100 minor units =BDT 1.00. Schemas reject booleans, floating amounts, unsupported dates, unknown authority fields, invalid linked settlements and inconsistent duplicate invoice economics. Cleared cash changes current balance; scheduled cash and unpaid invoices change forecasts. An unpaid invoice is not prematurely deducted from cleared cash.

Users add append-only cash records or unpaid supplier invoices. Complete Dataset JSON is accepted only into an untouched empty workspace. Duplicate JSON keys and oversized bodies are rejected before model validation. Vendor permission is explicit: imports do not automatically authorize payees. Cash records are self-reported historical/planned activity; invoice payments must use their approval flow rather than being independently recorded again as unrelated cash.

Each input request carries an idempotency UUID and expected source revision. A locked transaction checks identity/audit/revision, validates the full extended dataset, retains the immutable old version, appends source evidence, updates the head, verifies existing signed postings and records the audit. A retry of the same UUID/payload returns the existing outcome; UUID reuse with changed content and stale concurrent edits fail. The mechanism prevents request replay, not a user's intentional creation of economically identical cash records with new UUIDs.

Historical proposals bind their exact dataset fingerprint and invoice economics. After new evidence is appended, verification loads the immutable bound version and checks continuity of that invoice against current evidence. Existing signatures, approvals, ledger entries and audit events are not rewritten.

Forecasts calculate daily7/30-day scheduled cash under stated reserve and receipt-delay assumptions. Canonically duplicate invoices are counted once; possible duplicates are conservatively flagged/blocked for execution. Paid invoice overlays remove their future obligation and add the actual sandbox outflow once. Financing compares three explicitly fictional BDT 50,000/30-day offers using stated flat term interest/fees, net proceeds, total cost, repayment and modeled capacity. No APR, lender approval probability or financial advice is invented.

## Identity and payment authority

Public signup uses username and an exact8–128-character password. Password strength is a UI estimate; no personal password is sent to a third-party scoring service. Salted scrypt hashing, bounded hashing concurrency, database-backed request limits, Secure/HttpOnly/SameSite cookies,24-hour sessions and server-side logout revocation are retained. Cookie mutations require an exact allowed Origin and application header. Optional legacy bearer access remains collapsed compatibility functionality.

Owners can invite an independently registered approver using a one-time, hashed, one-hour code. Roles and workspace scope come from authenticated server state. The owner/proposer cannot self-approve. A proposal binds tenant, invoice, payee, currency, amount, source hash, dataset version, proposer and expiry. Execution rechecks permission, expiry, funds/reserve, vendor allowlist and duplicate risk. Approval and paired ledger entries occur in one transaction; unique posting constraints make retries idempotent. HMAC-protected chained audit evidence detects unauthorized modification without the signing key.

## AI interaction and boundaries

Question shortcuts and direct task input make the assistant easier to use. Deterministic balance, outlook and invoice-risk insights remain usable without a model call. The model can request only finite typed read/propose tools. It cannot approve, execute, run arbitrary SQL/code, retrieve secrets or change roles. Proposal permission requires explicit caller consent and one scoped invoice. Financial values and source references are validated against backend facts.

The configured free model has finite budgets/deadlines and no paid retry or fallback. The actual public smoke returned the source-grounded BDT 85,000 balance from newly entered manual data without proposing/executing a payment. This is an integration smoke, not statistical model accuracy. The earlier uploaded eight-case provider report is retained historical evidence with its original source hashes; it is not relabeled as evaluation of every later UI/auth/input change.

## Verification and limits

The full backend suite passed312 tests with two known warnings. Focused post-polish deployment/input checks passed20 tests. The latest browser suite passed16 scenarios and six automated axe scans, including valid/invalid JSON uploads, manual exact-cent entries, separate demos, invitations, one posting and login/logout. Viewports360/390/768/1366px had no tested horizontal overflow or captured page errors. This is Chromium/Linux emulation, not physical Android/iOS/Safari or full WCAG certification.

The actual public API passed34 acceptance checks: preservation of existing account/ledger; zero-start8-character signup; cookie flags; exact-cent own input; replay/conflict; unpaid forecast; independent approval; tenant isolation; one audited execution; preserved historical proof after append; CSRF denial; separate optional demo; grounded live AI; logout and restored login. Source/private-value scans passed before Git publication. Subsequent redeployment persistence is recorded separately in `evidence/finalization/persistence.json` when completed.

The product is a public sandbox release. Free-service cold starts/quotas, lack of password recovery, append-only corrections via new workspaces, unverified self-reported inputs, database/signing-key administrator trust and finite internal testing remain disclosed limitations. It is not a certified real-money financial production service. Registration/eligibility, owner-selected project license, final spoken presentation/demo refresh and external submission receipt are separate competition tasks.
