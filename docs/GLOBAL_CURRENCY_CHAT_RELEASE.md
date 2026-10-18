# Global currency and workspace chat release

Target: Pranto-404/SafeLedger-AI, existing safeledger-ai production project.

Changes:
- Remove the landing-page preloaded-data sales box and redundant empty-account banner.
- Support 165 ISO 4217 currency/fund codes with numeric minor units from SIX List One (2026-09-17). One currency per workspace, no FX conversion. Account and workspace creation allow currency selection; an owner can change an untouched workspace. Existing economics cannot be relabelled. Import currency must match.
- Signed proposals, postings, forecast and AI facts retain the workspace currency. Exact frontend parsing handles 0/2/3/4 digits and rejects excessive precision. Backend integer calculations are unchanged.
- Add a lazy corner chat on every authenticated page and preserve the Assistant section/history within the current workspace session. No history in browser storage. Explicit private rule-based help and opt-in external AI modes, with status failures/retry and retained failed questions.
- Reduce login database round trips (atomic budget increment returning count, identity join, remove duplicated foreign-key setup). Preload workspace code when authentication starts. No weakening of password hashing, cookies, CSRF or rate limits.

Validation:
- 335 backend tests passed, including foreign-currency signed payments/replay, currency locking, CSRF, tenant isolation and existing BDT history.
- Node currency parser/formatter precision and bounds checks passed.
- TypeScript and production Vite build passed; separate Assistant chunk is about 3.6 kB gzip.
- Live browser verification is pending deployment.

Boundaries:
- External AI live inference is not verified: automatic approval review blocked a live financial query with external-AI consent. No retry of that transmission was made. Synthetic-only provider testing needs specific permission for Google Gemini.
- Production API still runs on Render Free. Native Vercel migration is kept on migration/vercel-native-20261018 pending database environment access and preservation of the existing signing key. Cold-start login delays cannot be claimed resolved.
- No paid services, new model billing or automatic currency conversion were enabled.
