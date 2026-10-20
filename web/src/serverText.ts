import {T} from './i18n';
/** Fixed sentences the server sends. Listed here so they can be translated; anything not listed is shown as received. */
export const serverText=[
 T('Deterministic scenario, not a probabilistic prediction'),
 T('Daily closing balances; within-day liquidity is not modeled'),
 T('Overdue open obligations and scheduled cash start on day one; only scheduled inflows shift in delayed scenario'),
 T('Linked invoice/event counted once; identical canonical invoice duplicates counted once; possible duplicates both counted conservatively'),
 T('Scheduled outflows assumed to occur on planned dates; no new sales, tax, interest or financing inferred'),
];
