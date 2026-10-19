/* Checks that sentences become correct draft records (amounts, direction, dates) and that questions never do. */
const assert = require('node:assert/strict'), vm = require('node:vm'), path = require('node:path');
const esbuild = require('../web/node_modules/esbuild');
const mod = { exports: {} };
vm.runInNewContext(esbuild.buildSync({ entryPoints: [path.join(__dirname, '..', 'web', 'src', 'recordParser.ts')], bundle: true, write: false, platform: 'node', format: 'cjs', target: 'es2022' }).outputFiles[0].text, { module: mod, exports: mod.exports, console });
const { parseRecordSentence, looksLikeTransaction } = mod.exports;
const today = new Date(2026, 9, 20);            // 20 Oct 2026, local
const opts = { currency: 'BDT', digits: 2, today };
const p = q => parseRecordSentence(q, opts);

const cases = [
  ['I paid Rahman 5000 taka for freight', { kind: 'cash', direction: 'outflow', amount_minor: 500000, status: 'cleared', effective_on: '2026-10-20' }],
  ['paid 5k to Dhaka Packaging yesterday', { kind: 'cash', direction: 'outflow', amount_minor: 500000, effective_on: '2026-10-19' }],
  ['received 20,000 from Karim Traders', { kind: 'cash', direction: 'inflow', amount_minor: 2000000 }],
  ['Sold goods for Tk 1.5 lakh today', { kind: 'cash', direction: 'inflow', amount_minor: 15000000 }],
  ['got 2 lakh from customer on 25 Oct', { kind: 'cash', direction: 'inflow', amount_minor: 20000000, status: 'scheduled', effective_on: '2026-10-25' }],
  ['rent 12000 paid', { kind: 'cash', direction: 'outflow', amount_minor: 1200000 }],
  ['আজ ৫০০০ টাকা খরচ করলাম', { kind: 'cash', direction: 'outflow', amount_minor: 500000, effective_on: '2026-10-20' }],
  ['আমি রহিমকে ২৫০০ টাকা দিলাম', { kind: 'cash', direction: 'outflow', amount_minor: 250000 }],
  ['ami 3000 taka peyechi', { kind: 'cash', direction: 'inflow', amount_minor: 300000 }],
  ['salary 45000 paid on 2026-10-01', { kind: 'cash', direction: 'outflow', amount_minor: 4500000, effective_on: '2026-10-01' }],
  ['bill from Rahman Logistics 3500 due in 10 days', { kind: 'invoice', amount_minor: 350000, vendor_name: 'Rahman Logistics', due_on: '2026-10-30' }],
  ['I owe Dhaka Packaging 12000 taka invoice', { kind: 'invoice', amount_minor: 1200000 }],
  ['spent $40 on cartons', { kind: 'cash', direction: 'outflow', amount_minor: 4000 }],
];
for (const [q, expected] of cases) {
  const d = p(q);
  assert(d && d.ok, 'should parse: ' + q);
  for (const [k, v] of Object.entries(expected)) assert.equal(d[k], v, `${q} -> ${k}: ${d[k]} !== ${v}`);
  assert(d.amount_minor > 0 && Number.isSafeInteger(d.amount_minor) && d.warnings.every(w => typeof w === 'string'), q);
}
assert.equal(p('I paid Rahman 5000 taka for freight').vendor_name, 'Rahman');
assert.equal(p('received 20,000 from Karim Traders').vendor_name, 'Karim Traders');

// Questions, chit-chat and numbers without a transaction are never turned into records.
for (const q of ['How much did I spend?', 'what is my balance', 'How do I record a payment of 500?', 'show 10 invoices', 'hello', 'I have 5 questions', 'আমার খরচ কত?', 'Should I pay 5000 now?', 'The year 2026 is good', '', 'paid', '12345']) assert.equal(p(q), null, 'must not parse: ' + q);
// Absurd amounts and dates are not accepted blindly.
assert.equal(p('paid 99999999999999 taka'), null);
assert.equal(p('paid 0 taka'), null);
assert(looksLikeTransaction('Mr Karim gave me 500 for the order') && !looksLikeTransaction('What did I pay?'));
// Dates inside references are not mistaken for amounts.
assert.equal(p('paid invoice 2026-10-12 total 4500').amount_minor, 450000);
console.log('record parser: ' + cases.length + ' sentences and the negative cases passed');
