# Preliminary risk register — M0, NOT a security certification
Current exposure: loopback-only API bootstrap; M1 financial analysis is internal CLI/service only, no financial data HTTP or mutation routes. Production not approved. Controls below are planned unless explicitly tested.

| ID | Risk | Required control / test | State |
| --- | --- | --- | --- |
| SEC01 | Unauthorized/self approval | Server sessions, separate approver, negative permission tests | M2 pending |
| SEC02 | Double posting/replay/race | Atomic transaction, unique proposal key, concurrent retry/restart tests | M2 pending |
| SEC03 | Changed/stale approval | Immutable action hash/version/expiry; substitution/expiry tests | M2 pending |
| SEC04 | Tenant data leak | Auth-derived tenant every query; tenant A/B negative tests | M2 pending |
| SEC05 | Prompt/tool injection | Tool allowlist + per-tool schema + backend authorization + adversarial provider tests | Outer envelope tested only; M3 pending |
| SEC06 | Wrong financial facts | Strict minor units, reconciliation and independent expected fixtures | M1 strict money/reconciliation/forecast/offer tests passed; execution reconciliation pending M2 |
| SEC07 | Upload/formula injection | Size/row caps, encoding/schema checks, escaped export | M1 bounded JSON/CSV parsing and formula-escape helper tested; HTTP upload/export endpoints pending |
| SEC08 | Secret leakage | No secrets in source/log; history/dependency scans | Full scan pending |
| SEC09 | Audit alteration | Transactional append-only API, chained digests, exported anchor | M2 pending |
| SEC10 | Provider outage/cost abuse | Time/token/call limits, rate limits, explicit degraded mode | Not configured; M3 pending |
| SEC11 | Hosting persistence/CORS/HTTPS | Authorized host, durable volume, origin config, restart evidence | M6 blocked on host |

M0 negative-route tests establish that future write routes are absent, not that future authorization is implemented. No completed security-flow, E2E, browser, independent audit or dependency vulnerability scan is claimed.

M1 provenance: canonical dataset/source hashes, atomic import rollback and modified/deleted source-row detection tested. A privileged writer can rewrite data and digests together; cryptographic audit is pending. Inert malicious memo leaves deterministic financial output unchanged; live LLM injection and HTTP auth remain untested. See evidence/m1/pytest.xml and M1_BUG_LOG.md.
