# M5 local adversarial QA checkpoint
Story: a private owner/session opens a source-backed dashboard,proposes an invoice,and an independent authenticated human reviews a signed action before the backend may atomically post to a synthetic SQLite ledger;errors must remain visible and other sessions/businesses must not inherit data or permission.

## Actual evidence
| Boundary | Executed evidence | Result |
| --- | --- | --- |
| UI→API→SQLite→render | scripts/m4_browser_demo.py with patched dependencies;10 scenarios,4viewport widths;full-workflow-regression/ | Passed;real sandbox posting12000000→8500000 minor;exactly1 execution |
| Denied actions→UI | scripts/m5_browser_qa.py;8 adversarial scenarios;browser-final/ | Passed;real expired signed action/wrong hash/rejection replay/role/tenant denials;zero execution |
| Session/error handling | Real login401,held old request across logout,network abort then recovery | Passed;no persistent token/stale tenant totals;no page errors |
| Stored untrusted data | Real immutable fixture with HTML/script and prompt instruction in memo | Escaped inert text,no DOM script/image execution,no posting;this is not a real-model injection evaluation |
| Keyboard/accessibility | Tab/Shift+Tab loop,Escape/focus return;axe4.14.0 scans login,8views,dialog |10 scans,zero automated WCAG2/2.1A/AA violations;not full WCAG conformance |
| Money/security regression |225 pytest tests +actual uvicorn4concurrent approvals/replay/restart +offline audit | Passed,no skips;2 known warnings preserved |
| Build/dependencies | TypeScript/Vite7.3.7 build,pip check,compileall,npm audit,pip-audit -r lock | Passed;zero known advisories reported by final registries |
| Credential hygiene | scripts/security_scan.py over all reachable historical blobs +tracked working tree and ignore checks | No known-pattern candidates;scope/count in credential-scan.json;not proof of no secrets/PII |

## Findings and fixes
1. Initial npm audit flagged Vite7.3.1(high) and esbuild0.27.7(low),covering dev-server file-access advisories. Upgrade Vite7.3.7 and explicit esbuild0.28.1 override;retain lock and verify actual build/API proxy/browser integration. The override crosses esbuild's pre1.0 minor boundary;real build and full workflows passed. Reassess/remove override after Vite natively depends on patched esbuild. No production SDK/stack migration.
2. pip-audit reported pytest9.0.2 temporary-directory advisory PYSEC-2026-1845/GHSA-6w46-j5rx-g56g twice in its response;one distinct advisory. Pin9.0.3;all225 tests pass. No blanket upgrade of runtime packages.
3. Browser Tab-focus assertion failed after a denied approval. Native modal alone allowed focus to leave the document through browser chrome. Explicit cycling over visible enabled controls now keeps Tab/Shift+Tab within the dialog. Retest passed;M4 Escape/focus-return regression also passed.
4. axe found insufficient contrast on eyebrow/nav index text and visible/accessibility name mismatch on invoice action buttons. Darken text;accessible label now includes visible “Review payment” text plus invoice ID. No rules suppressed. Initial10 violations across10 scans became0.
5. Defensive cancellation check prevents an aborted old session's parsed response from invoking global logout after a new session mounts. Existing cancellation remains;real held-request/tenant switch test passes.

## Manual review and limits
Reviewed token-derived roles/tenants,independent-human enforcement,strict approval/hash/expiry contracts,atomic BEGIN IMMEDIATE postings,source/posting/HMAC verification,provider host/tool/call budgets,escaped memo rendering,memory-only tokens,raw JSON import and audit export. Existing tests already cover forged signatures,modified source/state,SQL transaction failure/concurrency,expiry boundary,IDOR and prompt/tool escalation;they were not duplicated just to increase counts. Public same-origin proxy,TLS,frontend security headers,session lifecycle/key rotation and external audit anchors still require deployment work. No Vercel/static-only release claimed.

Developer executed these tests;no separate independent reviewer/device-lab sign-off exists. Chromium153 on Linux was used;Safari/Firefox/real Android/iOS are not verified. Local network abort is an explicit fault injection;financial denial responses come from actual FastAPI/SQLite. Live model configuration/task accuracy/injection evaluation remains absent. Registry scans are point-in-time known-advisory checks,not guarantees. No critical application failure remains reproduced by the recorded local suites;release still requires M3 live evaluation,M6 persistent HTTPS deployment/clean clone/submission and independent review. Registration remains owner's parallel responsibility.

Primary advisory references: https://github.com/vitejs/vite/security/advisories/GHSA-v2wj-q39q-566r ; https://github.com/evanw/esbuild/security/advisories/GHSA-g7r4-m6w7-qqqr ; see retained npm/pip JSON for all IDs/ranges. Original failures are retained in browser-initial.log and browser-after-focus-fix.log/results;no failing test/rule was disabled.
