# M6 reproducibility and submission preparation
This checkpoint prepares local delivery. It does not declare public deployment,registration,live AI or competition submission complete.

## Fresh-clone qualification
Verified application/source commit:7c7f03f43f6963ed4d642091676e5d7445a610bb. scripts/verify_clean_clone.py cloned the public GitHub repository,checked out that exact commit,created a new venv,installed api/requirements.lock.txt,ran226 tests,installed web with npm ci,built TypeScript/Vite,ran bootstrap smoke,live HTTP concurrency/replay/restart,10 full-flow browser scenarios and8 adversarial browser scenarios with10axe scans. All15 recorded commands passed. Source,command arrays,exit codes and timing:evidence/m6/reproducibility-verified/result.json. Browser/server evidence and JUnit retained in that directory.

Isolation covers checkout,Python site packages and node_modules. OS,Python/Node tools and an existing Chromium153 executable remain shared. Optional @sparticuz archive extraction failed on chown in this environment;verified runs select SAFELEDGER_CHROMIUM_EXECUTABLE=/tmp/chromium. No claim of a pristine machine or normal CDN browser installation success. No private LLM config is copied into qualification. No real money/customer data.

## Actual findings and corrections
First attempt at f1e58c6 passed finance tests/build/bootstrap/HTTP then failed optional browser extraction. It also exposed an orphaned npm/Vite child that prevented temporary checkout cleanup. POSIX harness now starts a separate process group,terminates the group and verifies both server ports close. Partial startup also cleans up. Regression starts a real child listener,verifies it accepts connections,then confirms teardown closes it.

An edit to the new regression's child Python import introduced a NameError,which the second fresh-clone attempt at ffbce2e caught. This intermediate published commit was not a release. Corrected import at7c7f03f,explicit targeted regression pass,and final clean-clone run pass. Failure logs remain in reproducibility/ and reproducibility-final/. No test was removed. POSIX regression has an explicit platform skip on Windows,which has not been qualified;the verified Linux suite has zero skips. M5's225 tests remain,plus1 harness test.

README and architecture no longer describe already implemented UI/auth/agent adapter as future work. The application still honestly reports an unconfigured real AI provider. No financial permission/calculation policy was weakened during M6.

## Submission handoff
English technical report,release checklist and4min20s rehearsal script:submission/. Editable10-slide deck contains speaker notes and510-second target timing,not a measured spoken rehearsal. Its final package/font/native-table checks and visual review are recorded separately. The actual screen demo uses browser screencast frames and pauses during private login/account changes. English captions disclose local sandbox and AI unavailable. It has no narration audio. Only the final reviewed version is a handoff artifact;first capture had oversized captions and was revised to avoid obscuring approval controls. Final reviewed video duration is117.12seconds;exact artifact hashes are in evidence/m6/artifact-manifest.json. The deck/video are handed off separately;their authoring content/recording scripts remain in Git.

Final release remains blocked on private real-model evaluation,authorized durable backend/Vercel scope,actual HTTPS/restart/Git-triggered update proof,independent review/device qualification,owner registration,project-license/attribution decision and owner-approved external submission. No IDs,organizer requests or messages have been sent. docs/DEPLOYMENT_STATUS.md preserves prior403 evidence;unchanged calls are not retried.
