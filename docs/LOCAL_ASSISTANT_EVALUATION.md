# On-device assistant: independent evaluation (20 October 2026)

The on-device assistant is a small hashed TF-IDF nearest-centroid intent classifier (43 intents, 442 synthetic training utterances in English, Bangla and Banglish; the figures in this document were first written for 36 intents and 347 utterances, before the website-guide intents were added) plus high-precision rules and a finance-domain gate. It is not a generative model. Its original acceptance suite (36/36 supported, 22/22 off-topic, 8/8 security prompts) was written by the same people who trained it, so it says little about unseen phrasing. This evaluation measures that.

## Method

Three hand-written prompt sets, written after training, with every prompt checked to be absent from the training corpus (`scripts/evaluate_local_assistant.cjs` refuses to run otherwise). Each prompt has an expected behaviour:

- **in-scope, answerable on the device:** correct intent;
- **in-scope, not answerable on the device:** the assistant must not guess; it should offer the permission-gated online model;
- **off-topic:** never answered and never offered to the online model;
- **security / authority:** secrets, injection, cross-tenant access, or a request that the chat itself move or change money: refused.

The engine only ever answers from the user's own loaded figures and cannot act: every approval, payment and permission is enforced by the server. Even a security prompt the assistant fails to recognise cannot change anything; at worst it gets an unhelpful reply, or it is offered the online path, where the model has no approve or execute tool and the server enforces roles.

## Results

| Set | Role | First run, before tuning | After tuning |
| --- | --- | --- | --- |
| `heldout_eval` (110 prompts) | development | **72.7%** (80/110) | 97.3% (107/110, re-run on 20 Oct after the site guide was added; 99.1% before) |
| `heldout_eval_v2` (93 prompts) | development | **66.7%** (62/93) | 97.8% |
| `heldout_eval_v3` (95 prompts) | **fresh, evaluated once, never tuned** | **73.7%** (70/95) | not tuned |

Reading the numbers honestly:

- The post-tuning figures on the first two sets are **not** a measure of quality: the rules and training data were changed after looking at those failures.
- **73.7% on the fresh set is the generalization figure** for unseen phrasing. By group: in-scope answered 72%, in-scope unanswerable 50%, off-topic **100%** (25/25 recognised, none offered online), security and authority 41.7% (5/12 recognised).
- 6 of the 95 fresh answers were confidently wrong (for example a balance-sheet question routed to the balance intent). The reply is shown with its source figures and an answer the user can disregard, but it is an error.
- Bangla and Banglish are about 5% of the fresh set and 11% of the first set: far too few to claim per-language accuracy.

## What was fixed along the way

Real defects found by this exercise and fixed before the first deployment of the new assistant:

1. A **case-sensitive guard**: "How do I let a colleague approve invoices?" was refused as an order to approve something, because the "how/what/why" exemption ignored capital letters.
2. **Income vs expenses confusion**: "How much money came in this month?" answered with expenses.
3. **Dead ends**: many ordinary in-scope questions ("Who approves my payments?", "Show me the most recent transactions") were classed off-topic because the domain gate needed one of a fixed list of words. The gate vocabulary was widened and high-precision paraphrase rules were added.
4. **No path out of a wrong off-topic verdict**: now an explicit "It is about my business finances: ask online" choice appears, which still asks for permission before anything is sent.
5. Wider deny-list for secrets, injection, cross-tenant requests and requests that the chat move or change money.

## Remaining limits

- The engine is a keyword-and-centroid model. On unseen phrasing it is wrong or silent roughly a quarter of the time; the safe failure modes (ask permission, or say it cannot help) are the default.
- Recognition of security prompts is incomplete (42% on the fresh set). Authorisation never depends on it.
- The held-out sets are small and hand-written; they are not a statistical benchmark.

## Reproduce

```bash
node scripts/evaluate_local_assistant.cjs heldout_eval_v3          # prints failures
node scripts/evaluate_local_assistant.cjs heldout_eval_v3 --check  # CI floor: >= 70% and no off-topic prompt offered online
```

Per-prompt results are stored in `evidence/local-intelligence/heldout-eval*.json`.

## Next step for a measurable improvement

Replace the nearest-centroid model with a larger training set (several thousand utterances collected under consent, with Bangla and Banglish coverage) and a held-out test written by someone who has not seen the rules. Re-measure on a new fresh set.
