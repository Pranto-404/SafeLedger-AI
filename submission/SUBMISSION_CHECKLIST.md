# Submission checklist (deadline 20 Oct 2026, 23:59 Beijing = 21:59 Dhaka = 15:59 UTC)

Send to the organizer address in the official rules (wangyr@pbcsf.tsinghua.edu.cn) from the team leader's own mailbox. Keep the sent email and any reply privately as the receipt. Never commit passports, IDs or the registration form to GitHub.

| # | Organizer requirement | Our artifact | Status |
| --- | --- | --- | --- |
| 0 | Registration form + passport bio pages, all members | Official form (Appendix 3) | **Owner action**: confirm it was sent and acknowledged; if not, send it first |
| 1 | Technical documentation (architecture, core algorithms, security design) | `submission/Capzoryx_Copilot_Technical_Documentation.pdf` (and `.md` with `submission/figures/`) | Written for release 0.7.6 on 20 Oct 2026 |
| 2 | Presentation deck ≤ 10 minutes | 10–12 slides (outline in the strategy PDF) | **To build and rehearse** |
| 3 | Demo video ≤ 5 minutes | `submission/DEMO_SCRIPT.md` | **To record** on the live 0.4.0 build |
| 4 | Source code: README, GitHub link, deployment instructions, test cases | GitHub repo, `README.md`, `api/tests`, CI badge | Ready; tag the submitted commit |
| 5 | Security self-assessment (permission tiers, known-risk list) | `docs/SECURITY_SELF_ASSESSMENT.md` → PDF | Updated for 0.4.0 |
| 6 | Execution evidence: sandbox operation logs + demo video | Audit export JSON + workspace export from the demo account; CI run log link; video | **To export** after recording |

Final gate (all must be true before sending): the same commit SHA appears in the report, deck, video caption and repo tag; the live `/api/health` shows that SHA or a later docs-only commit; the video is ≤ 5:00; no passwords, recovery codes or tokens are visible anywhere.
