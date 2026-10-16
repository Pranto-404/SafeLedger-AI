# Milestone acceptance plan
| Gate | Acceptance evidence | Status |
| --- | --- | --- |
| M0 | Read source docs; freeze scope/contracts; executable API/UI build, SQLite readiness and bootstrap tests; Git recovery | Verified |
| M1 | Seeded data ingestion; reconciled exact financial totals; duplicate detection; 7/30-day outlook; fictional offers; independent expected fixtures and pytest | Next |
| M2 | Auth-derived tenant/roles; separate human approval; immutable action hash/expiry; atomic idempotency; audit trace; race/replay/IDOR/security tests | Planned |
| M3 | Real configured LLM, finite typed tools, provenance/number verification, budget/timeouts, injection/outage tests | Planned; provider unresolved |
| M4 | Dashboard/import/cashflow/financing/agent/approval/audit integration, honest status/error/empty states | Planned |
| M5 | Full financial/security suite, independent QA, mobile/keyboard/browser E2E evidence, critical fixes retested | Planned |
| M6 | Authorized persistent deployment, clean clone verification, repository, technical/security docs, <=10-min deck, <=5-min demo and sandbox logs | Planned; registration/access unresolved |

All release blockers in REQUIREMENTS.md remain binding. No completed gate can substitute for missing execution evidence. Owner registration proceeds in parallel; never send identities or organizer requests without explicit authorization.
