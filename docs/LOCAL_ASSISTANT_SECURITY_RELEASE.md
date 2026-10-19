# Local assistant, dashboard and security continuation — 19 October 2026

## Product behavior

- The assistant first uses an on-device hybrid engine: a trained hashed TF-IDF nearest-centroid intent classifier, high-precision finance slot rules, reviewed bilingual knowledge and deterministic rendering of current workspace facts.
- Training corpus: 301 public synthetic utterances across 36 intents in English, Bangla and Banglish. Run `python scripts/train_local_assistant.py` to reproduce `web/src/localModel.ts`. No user records, conversations, credentials or web scrapes are training data.
- This is not a generative local language model and does not understand every topic. It abstains on uncertain/out-of-domain questions. It cannot trade, approve payments, change permissions or alter the ledger.
- Current balance, income, expenses, 7/30-day outlook, risk, open/overdue invoices and recent activity use the current workspace snapshot and link source IDs. Amounts retain their ISO currency/minor units. Historical messages show their snapshot date.
- Local answers do not call a provider. Both the model artifact and online assistant are lazy chunks loaded only when chat is opened. No model download on landing/login, no browser-history training and no financial chat in localStorage.
- The latest question can be sent for bounded external financial analysis only after sharing consent. Earlier private questions are no longer forwarded. Optional OpenAI failover needs separate consent plus owner-configured server authorization.
- Dashboard redesign: light default / optional dark theme, actual-cash summary cards, 30-day scenario chart, invoice overview, recorded activity, independent review and audit status. Theme preference is the only new localStorage item. No prefilled balances, fake returns, fake notifications or sample transactions.

## Zero-spend policy and failover

OpenAI API usage is separately metered. A ChatGPT subscription does not authorize or supply application API usage. No OpenAI calls, credits, billing setup or secrets were introduced here.

The failover implementation remains disabled unless all of these are deliberately configured by an owner who has separately authorized API spending:

- `SAFELEDGER_ALLOW_PAID_AI=1`
- `SAFELEDGER_OPENAI_FALLBACK_ENABLED=1`
- `SAFELEDGER_OPENAI_API_KEY` (server-side secret)
- `SAFELEDGER_OPENAI_MODEL` (explicitly selected model)

Default: local answers + the existing confirmed Gemini free profile. On quota exhaustion, local answers remain available. There is no unannounced paid fallback. Do not enable spend flags merely to pass a test.

When authorized, failover only follows primary quota/timeout/network failure, targets `https://api.openai.com/v1`, never follows arbitrary URL configuration, and shares one 90-second deadline with at most three total HTTP attempts across the two-stage task. Invalid outputs, authentication failures and refusals do not silently switch providers. Financial proposals are created only after the entire bounded rationale passes validation; model calls never approve or execute.

## Security changes and tests

- Removed prior private questions from external model context; current-question-only consent.
- Server enforces primary sharing consent and separately gates secondary sharing.
- Provider status now validates configuration rather than treating the presence of a key as success. No inference occurs on status checks.
- Owner-only `/api/agent/diagnostic` sends fixed synthetic constants to the existing Gemini free provider. It has no dataset read path, accepts no user prompt, requires an explicit confirmation flag and is rate limited. It checks tool planning and constrained structured rationale. No provider key is exposed to the browser.
- Provider HTTP errors expose only a sanitized numeric HTTP status, never raw upstream error bodies or credentials.
- API responses enforce no-store, frame denial, restrictive content policy and feature permissions. HTTPS uses HSTS. Production API docs/schema routes are closed.
- Tested cookie-origin spoofing, forwarding-header spoofing, tenant IDOR, role/consent overposting, strict Boolean validation, self-approval, action-hash tampering, malformed/duplicate JSON, immutable audit triggers and backend signature detection after test-only administrator tampering.
- Attack tests use disposable local databases and synthetic MockTransport responses. No production records, production triggers, signing keys, user roles or permissions were changed.
- Lazy-module failures now show a recoverable error panel instead of silently taking down the workspace.

## Verification record

- Existing 335 backend tests passed before the new tests were added.
- New fallback tests: 12 passed.
- New adversarial tests: 13 passed; audit tampering was rejected by a database trigger, and tampering after test-only trigger removal returned `AUDIT_INTEGRITY_FAILURE`.
- New synthetic diagnostic tests: 4 passed.
- Local acceptance prompts: 36 supported prompts correctly routed/rendered, 22 out-of-domain prompts declined, 8 secret/injection attempts refused; zero external calls. These are development acceptance checks, not a population-level model accuracy claim or independent research benchmark.
- Currency regression checks and production TypeScript/Vite build pass. Assistant chunk is about 35 kB gzip and is deferred.
- Final complete suite: 364 passed. Existing browser acceptance script updated for the new controls; it was not run through a separate browser because the user requested their local Edge session.
- Live local Edge checks passed: light dashboard, dark toggle, greeting, Banglish balance with the actual workspace currency, gratitude in online mode without sharing consent, prompt-injection refusal, Escape close and history retained in the Assistant section.
- Actual Google Gemini synthetic diagnostic passed both tool planning and constrained structured response. No account identifiers, workspace amounts, invoices or prior private chat were sent. The OpenAI branch was tested only using synthetic transports and remains disabled in production.
- Vercel production: 7AWWedXqK17UXMCra7x2ESQA1R5v, Ready, application fb8c3d7ecd8dde64a865c54f58fa89fe97648a03. Render dep-dbart3m1egvs73e0mj6g live; public health and readiness both 200.
- Follow-up UI safeguard: do not show provisional zero balances/invoice figures before the verified snapshot arrives. Theme and local model remain deferred/independent of financial writes.
- CPU-only local-engine sample (not end-to-end latency): median 0.169 ms, p95 0.406 ms over 300 alternating synthetic greeting/concept prompts; zero requests.
- Expanded out-of-domain testing exposed unrelated-topic matches from generic words. A domain gate now requires an actual finance/workspace topic before accepting a learned financial intent; follow-up context and conversational intents remain separate. All 22 expanded out-of-domain prompts decline safely.
- No mobile-browser acceptance claim is made from these desktop checks. No paid service, provider key, signing identity or production access permission was changed.

## Remaining hosting gate

Production remains Vercel frontend + Render API. Native migration branch `migration/vercel-native-20261018` is separate and must absorb this release before eventual cutover. The prior request for temporary Preview database access and copying existing signing/provider secrets has not received explicit action-time confirmation. Do not save that security-sensitive browser change or rotate any credential during this release.

No system can be claimed breach-proof from this test scope. Live Gemini diagnostics and local-browser checks must be recorded separately from mocks.

## Final checkpoint

- Main and deployed frontend source: `04ef451fd7b427e96cb87fd97b5ffa9a484781bf`. Vercel deployment `AHrf8yTavp9euKV5U8Y3zQDdeMAA` is Ready. Backend remains the qualified `fb8c3d7ecd8dde64a865c54f58fa89fe97648a03` on Render; later commits are frontend/evidence only and intentionally skip Render.
- Final live browser checks repeated on that frontend: greeting and Banglish balance answer work locally; an unrelated Mars question safely declines; chat remains available at the corner. Screenshot saved privately, not added to Git.
- Public API health: 200. Unauthenticated workspace: 401. Both have no-store, frame denial, HSTS and feature-permission headers. Browser console errors observed were only from the user's Grammarly extension.
- Local browser viewport emulation did not actually alter DOM dimensions (requested 390px, observed 1912px). Temporary override reset. Do not claim mobile-browser acceptance from this session.
- All source, training examples, generated model, checks and security evidence are in GitHub. This checkpoint does not enable OpenAI spend or grant pending native-migration access.
