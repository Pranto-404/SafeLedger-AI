# Preliminary risk register — M0, NOT a security certification
Current exposure: loopback-only bootstrap with no financial data or mutation routes. Production not approved. Controls below are planned unless explicitly tested.

| ID | Risk | Required control / test | State |
| --- | --- | --- | --- |
| SEC01 | Unauthorized/self approval | Server sessions, separate approver, negative permission tests | M2 pending |
| SEC02 | Double posting/replay/race | Atomic transaction, unique proposal key, concurrent retry/restart tests | M2 pending |
| SEC03 | Changed/stale approval | Immutable action hash/version/expiry; substitution/expiry tests | M2 pending |
| SEC04 | Tenant data leak | Auth-derived tenant every query; tenant A/B negative tests | M2 pending |
| SEC05 | Prompt/tool injection | Tool allowlist + per-tool schema + backend authorization + adversarial provider tests | Outer envelope tested only; M3 pending |
| SEC06 | Wrong financial facts | Strict minor units, reconciliation and independent expected fixtures | Strict input contract tested; M1 pending |
| SEC07 | Upload/formula injection | Size/row caps, encoding/schema checks, escaped export | Model row/field caps only; parser/export pending |
| SEC08 | Secret leakage | No secrets in source/log; history/dependency scans | Full scan pending |
| SEC09 | Audit alteration | Transactional append-only API, chained digests, exported anchor | M2 pending |
| SEC10 | Provider outage/cost abuse | Time/token/call limits, rate limits, explicit degraded mode | Not configured; M3 pending |
| SEC11 | Hosting persistence/CORS/HTTPS | Authorized host, durable volume, origin config, restart evidence | M6 blocked on host |

M0 negative-route tests establish that future write routes are absent, not that future authorization is implemented. No completed security-flow, E2E, browser, independent audit or dependency vulnerability scan is claimed.
