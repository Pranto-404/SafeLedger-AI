# Public access and testing

Public frontend: https://safeledger-ai.vercel.app. Backend: https://safeledger-ai.onrender.com.

- **Explore the demo** opens a read-only example without asking for credentials. Visitors can inspect invoices, forecasts, fictional financing and audit. Guest sessions cannot create proposals, approve, import or use the model quota.
- **Create account** uses a username (3–32 letters, numbers or underscores) and a unique passphrase (15–128 characters). No email service is required. A new isolated workspace starts with synthetic sample data. No password recovery is currently provided; the entry screen discloses this.
- **Sign in** restores the account's own workspace. Cookies are host-only, HttpOnly, Secure in deployment, SameSite=Lax and expire after 24 hours. Sign-out revokes the current server session. No password or account bearer is returned to frontend JavaScript or saved in localStorage.
- **Workspace & teammates** lets an owner create an approver invitation. A second registered account enters this one-time, one-hour code to join that workspace as approver. The invitation does not create an owner or let the proposer approve their own proposal. Members can switch between their own and shared workspaces.
- The old private token form remains under a collapsed compatibility section; public users do not need it.

Passwords use salted scrypt (N=32768, r=8, p=3), constant-time comparison and a bounded hashing semaphore. Browser mutations require a trusted Origin and custom header. Registration/login/guest/invitation requests are rate-limited. New account count is capped at 1000 for this free prototype. Signed financial policies, integer arithmetic, transaction locking, replay protection and tenant isolation remain authoritative.

The public workspace endpoint returns a consistent read snapshot with overview, invoices, proposals, audit, forecasts and financing. This replaces seven repeated initial data loads. No shared mutable financial response cache is used.

## Infrastructure

Use the existing zero-cost Turso database for authoritative data. Render environment changes merge TURSO_DATABASE_URL/TURSO_AUTH_TOKEN and secure-cookie configuration, preserving other existing variables including signing identity and free model configuration. The current service's MCP/Dashboard environment is the source of truth; no new paid database, disk or Supabase project is provisioned.

Before cutover, the previous synthetic demo's session metadata, invoices, proposal, dashboard and seven-event audit were exported privately and retained durably. That historical executed run is an archive, not silently merged into new accounts. It is distinct from the new read-only example and each account's isolated dataset.

Render Free can sleep and take time to wake. The entry screen remains usable while checking a saved session and shows a startup message during slow requests. There is no artificial keep-alive traffic or paid upgrade. Free model quotas can interrupt only the assistant; deterministic financial tools remain available. Do not upload real financial or personal data.

## Verification

Local backend: 304 tests pass (two existing warnings). Local browser qualification: 12 scenarios, 4 axe scans and 360/390/768/1366px viewport checks. Separate browser processes tested guest entry, signup, restored cookie, teammate invitation, one posting, BDT 85,000 reconciliation, audit and sign-out. The actual remote database public-account smoke also passed, with no provider calls. Evidence: evidence/public-access/.

The earlier passed real-model eight-case report is historical evidence for the same model protocol; this UI/auth update does not claim a new statistical AI evaluation or independent security audit. After release, record actual deployment commit/status and public browser/API results separately.

## Live guest regression caught before acceptance

The first public-browser check exposed a shared demo audit signed during an earlier local/cloud qualification with a different signing identity. The API correctly failed closed. Guest rejection previously wrote a DENIED audit into that shared template. Guest financial mutations now stop in the authentication boundary, before any financial audit write, and the clean read-only example uses a versioned template. Existing accounts and their signing identity are preserved. The obsolete example is retained rather than deleting immutable audit history. A targeted real-remote regression checks that rejected guest actions leave an empty financial audit and the overview remains readable.
