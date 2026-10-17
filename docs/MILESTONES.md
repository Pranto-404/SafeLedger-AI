# Milestone acceptance plan
| Gate | Acceptance evidence | Status |
| --- | --- | --- |
| M0 | Read source docs; freeze scope/contracts; executable API/UI build, SQLite readiness and bootstrap tests; Git recovery | Verified |
| M1 | Seeded data ingestion; reconciled exact financial totals; duplicate detection; 7/30-day outlook; fictional offers; independent expected fixtures and pytest | Verified |
| M2 | Auth-derived tenant/roles; separate human approval; immutable action hash/expiry; atomic idempotency; audit trace; race/replay/IDOR/security tests | Verified;174 total tests and live API proof |
| M3 | Real configured LLM, finite typed tools, provenance/number verification, budget/timeouts, injection/outage tests | Adapter/dispatcher mock-verified; live evaluation blocked |
| M4 | Dashboard/import/cashflow/financing/agent/approval/audit integration, honest status/error/empty states | Local workflow verified:225 pytest +10 real-browser scenarios; live AI/deployment gates remain |
| M5 | Full financial/security suite, independent QA, mobile/keyboard/browser E2E evidence, critical fixes retested | Local QA verified:225 pytest,18 browser scenarios,10 axe scans,patched dependency audits;independent/live/public-host gates open |
| M6 | Authorized persistent deployment, clean clone verification, repository, technical/security docs, <=10-min deck, <=5-min demo and sandbox logs | Fresh clone verified;English deck/demo/checklist prepared;public deployment/live AI/owner gates remain open |

All release blockers in REQUIREMENTS.md remain binding. No completed gate can substitute for missing execution evidence. Owner registration proceeds in parallel; never send identities or organizer requests without explicit authorization.
