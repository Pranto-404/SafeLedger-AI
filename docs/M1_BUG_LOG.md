# M1 findings and fixes
- FIN-DUP-01: first suite run had 1 failure/110 passes. The possible-duplicate detector grouped every same-vendor/date/amount invoice, including unrelated fixture numbers. Added normalized-number similarity >=0.85 and clustering; exact/near/baseline regressions now pass. Original failed run kept as evidence/m1/pytest-first-run.log. No test was removed or disabled.
- INTAKE-NUM-01: source review found CSV integer conversion could raise a generic error for a very long digit string. Limit length before conversion; regression asserts an actionable amount_minor error on line2.
- PROV-01: load initially checked snapshot digest only. Added verification of every persisted source row checksum/payload/count and tests for deleted rows, modified hash and modified payload.
- Warnings: existing Starlette/httpx deprecation remains. The intentional post-validation model-mutation test generates a Pydantic serializer warning before validation rejects the float. Warning output is retained.

No independent reviewer, real model injection evaluation, HTTP tenant enforcement or sandbox execution security pass is claimed. Those remain later gates.

Source formatting check caught generated CSV CRLF and trailing spaces in raw pytest output. Generator now writes LF CSV and fixture hashes were regenerated. Raw .log evidence stays verbatim and is exempt from source whitespace formatting via .gitattributes; tests and source checks remain enabled.
