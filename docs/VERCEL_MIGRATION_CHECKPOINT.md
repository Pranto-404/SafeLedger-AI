# Continuation — 19 October 2026 (Asia/Dhaka)

Production now uses f4b0193a6336b5e758c01b75c4c8f12e2373165d, including global currency and workspace chat. These changes have been merged into this native migration candidate so cutover will preserve all current behavior. The 21 entrypoint/currency integration tests and frontend production build pass. The original qualification below describes the earlier candidate, not this updated build.

The local Vercel connection dialog now has Production + Preview selected but NOT saved. Temporary Preview database access and copying existing Render signing/provider secrets into this same Vercel project still require specific user confirmation. No secrets were changed during the currency/chat release. Keep Production access, do not create paid resources, and withdraw temporary Preview access after successful cutover. Live Gemini inference also remains unverified because automatic approval review blocked the earlier live-data transmission; ask for synthetic-only Google Gemini test permission.

# Native Vercel migration — 18 October 2026

Status: preview build and CDN delivery verified; database qualification and
production cutover are pending. Do not describe the migration as complete.

## Verified

- The user's local Edge browser is connected through the Browser extension.
  Existing signed-in GitHub, Vercel and Render tabs were used. No cloud browser
  was used during this continuation.
- Production remains `safeledger-ai.vercel.app`, with the working API proxied
  to `safeledger-ai.onrender.com`. Main is still `3d00de9`.
- Isolated branch: `migration/vercel-native-20261018`.
- Application candidate: `e539fcef81eaef45716d503f26ac8c0b6db0004c`.
- Vercel preview: `https://safeledger-9i3yxinxl-challanger2.vercel.app`.
- Deployment: `GDGZ1kjBnhaf4dxCTFk6R2jweSZL` (Ready, 17-second build).
- Resources: one Python 3.12 function (8.07 MB, 300-second maximum) and five
  static CDN assets. The landing page renders while the API lacks its database
  connection. Assistant and Workspace remain separate lazy-loaded chunks.
- Full existing backend suite: 325 passed. Four additional entrypoint tests
  verify legacy signing identity compatibility and rejection of missing or
  invalid signing keys. Logs are in `evidence/vercel-migration/`.
- Render's existing environment uses a 32-character signing key; its startup
  script repeats that value to obtain the effective 64-character identity.
  `api/vercel.py` now applies exactly that same compatibility rule without
  generating or rotating any secret. No secret values are committed.

## Remaining deployment gate

The first native preview failed startup with `Persistent database required on
Vercel`. Vercel's Turso variables currently target Production only. The
existing signing variable targets Production and Preview (a temporary setting
from the preceding session); its value has not been reconciled with Render.

An unsaved database connection settings dialog is open in the user's local
Vercel tab. No database Preview access has been saved. Explicit action-time
confirmation is needed before expanding live database access to Preview.
Batch that confirmation with copying the existing Render signing and optional
free-provider AI configuration into the same Vercel project's server-side
environment settings. Do not expose secrets to chat, logs, Git or frontend.

After confirmation:

1. Reconcile existing signing identity and persistent database credentials;
   retain Production access and grant only the temporary Preview access needed
   for this migration. Keep all secret settings sensitive/server-side.
2. Preserve the current free-only provider configuration, including explicit
   free-tier and host restrictions. Do not enable a paid fallback.
3. Redeploy the candidate and verify readiness plus the old personal account's
   balance, signed audit and existing single posting before new writes.
4. Test exact manual inputs, authentication/isolation, independent approval,
   replay protection, export/recovery and persistence on the native deployment.
5. Only after qualification, update main with an expected-head guard, verify
   the public deployment and remove temporary Preview secret access.
6. Keep Render intact until the replacement has passed these gates. Do not
   delete records or purchase resources.

The earlier delivered ZIP represents the current production application,
not this unqualified migration candidate. Update final delivery only after
successful production qualification.
