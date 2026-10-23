# Security policy

Capzoryx Copilot handles financial records, so we take reports seriously.

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Use GitHub's private reporting instead:
**Security tab > Report a vulnerability** on this repository. Include what you found, the steps to reproduce it, and the effect you expect it to have.

We will acknowledge a report as soon as we can, fix confirmed problems in the next release, and credit you if you wish.

## Supported version

Only the latest release on the `main` branch (currently 0.7.x) receives fixes.

## Please keep testing safe

- Test against a **local copy** (see the README), never against the live site with load, fuzzing or automated account creation.
- Do not access, change or delete other people's data.
- Do not test email or translation endpoints in a way that sends messages to other people or uses up the free quotas.

## What we already do

See `docs/SECURITY_SELF_ASSESSMENT.md` for controls, the 20 October 2026 review and the honest list of remaining limits. In short: server-enforced roles and independent payment approval, scrypt password hashing, two-step sign-in, an append-only ledger with a signed audit chain, strict content security policy, rate limits and lockouts, and regression tests for every fixed issue.

This is an internal self-assessment, not an independent penetration test.
