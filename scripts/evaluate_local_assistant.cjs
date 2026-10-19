/* Held-out evaluation of the on-device assistant. Synthetic context only; no network, no user data, no model API.
   Usage: node scripts/evaluate_local_assistant.cjs [heldout_eval|heldout_eval_v2] [--write]
   --write stores evidence/local-intelligence/<set>.json */
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), crypto = require('node:crypto');
const esbuild = require('../web/node_modules/esbuild');
const mod = { exports: {} };
vm.runInNewContext(esbuild.buildSync({ entryPoints: ['web/src/localAssistant.ts'], bundle: true, write: false, platform: 'node', format: 'cjs', target: 'es2022' }).outputFiles[0].text,
  { module: mod, exports: mod.exports, require, console, TextEncoder, TextDecoder });
const { localAnswer } = mod.exports;

const snapshot = { currency: 'BDT', as_of: '2026-10-19', balance_minor: 15000000, income_minor: 5000000, expenses_minor: 2000000, opening_balance_minor: 12000000, source_ids: ['opening', 'cash-1'], dataset_sha256: 'a'.repeat(64), assumptions: [] };
const forecast = { horizon_days: 30, closing_balance_minor: 20000000, minimum_balance_minor: -36000000, first_shortfall_on: '2026-10-25', source_ids: ['cash-1'], risk_flags: [], assumptions: [], days: [] };
const ctx = { snapshot, forecast, week: { ...forecast, horizon_days: 7 }, events: [], invoices: [] };

const setName = process.argv.slice(2).find(a => !a.startsWith('--')) || 'heldout_eval';
const file = path.join(__dirname, '..', 'data', 'local_assistant', setName + '.json');
const raw = fs.readFileSync(file);
const cases = JSON.parse(raw.toString('utf8')).cases;

// Training utterances must not leak into the held-out set.
const trained = new Set(Object.values(JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'local_assistant', 'intents.json'), 'utf8'))).flat().map(x => String(x).toLowerCase().trim()));
const leaked = cases.filter(([q]) => trained.has(q.toLowerCase().trim()));
if (leaked.length) { console.error('Held-out prompts also in training data:', leaked.map(x => x[0])); process.exit(2); }

const results = cases.map(([question, expected, intent]) => {
  const a = localAnswer(question, ctx, '');
  let actual = a.handled ? 'handled' : a.intent;
  if (['security'].includes(a.intent)) actual = 'handled';
  const pass = expected === 'handled' ? (a.handled && (intent === null || a.intent === intent)) : (!a.handled && a.intent === expected);
  return { question, expected, expected_intent: intent, actual_status: a.handled ? 'handled' : a.intent, actual_intent: a.intent, confidence: Number(a.confidence.toFixed(3)), pass };
});

const groups = {
  in_scope_answered: results.filter(r => r.expected === 'handled' && !['security', 'approval'].includes(r.expected_intent)),
  in_scope_unanswerable: results.filter(r => r.expected === 'unknown'),
  out_of_domain: results.filter(r => r.expected === 'out_of_domain'),
  security_and_authority: results.filter(r => ['security', 'approval'].includes(r.expected_intent)),
};
const rate = g => ({ cases: g.length, passed: g.filter(r => r.pass).length, pass_rate: Number((g.filter(r => r.pass).length / g.length).toFixed(3)) });
const wrongConfident = results.filter(r => r.expected === 'handled' && r.actual_status === 'handled' && !r.pass);
const offTopic = results.filter(r => r.expected === 'out_of_domain');
const offTopicNotRecognised = offTopic.filter(r => r.actual_status !== 'out_of_domain');
const offTopicOfferedOnline = offTopic.filter(r => r.actual_status === 'unknown');
const summary = {
  evaluated_on: new Date().toISOString().slice(0, 10),
  cases: results.length,
  corpus_sha256: crypto.createHash('sha256').update(raw).digest('hex'),
  overall: rate(results),
  by_group: Object.fromEntries(Object.entries(groups).map(([k, g]) => [k, rate(g)])),
  languages: { bangla_or_banglish_cases: results.filter(r => /[ঀ-৿]|amar|kemon|tumi|dhonnobad|ami /.test(r.question.toLowerCase())).length },
  confidently_wrong_answers: wrongConfident.length,
  off_topic_prompts_not_recognised: offTopicNotRecognised.length,
  off_topic_prompts_offered_to_online_model: offTopicOfferedOnline.length,
  external_calls: 0,
  limits: 'Small hand-written set (not a statistical benchmark). Prompts were written after training and are disjoint from the training data. Failures are listed, not removed.',
};
const failures = results.filter(r => !r.pass);
// Regression floors: development sets were tuned on (high floor); the fresh set is the honest generalisation figure.
const floors = { heldout_eval: 0.95, heldout_eval_v2: 0.95, heldout_eval_v3: 0.70 };
console.log(JSON.stringify({ ...summary, failures }, null, 2));
if (process.argv.includes('--write')) {
  const out = path.join(__dirname, '..', 'evidence', 'local-intelligence', setName.replace(/_/g, '-') + '.json');
  fs.writeFileSync(out, JSON.stringify({ summary, results }, null, 2) + '\n');
  console.error('written', out);
}
if (process.argv.includes('--check')) {
  const floor = floors[setName] ?? 0.7;
  if (summary.overall.pass_rate < floor) { console.error(`FAIL ${setName}: ${summary.overall.pass_rate} < floor ${floor}`); process.exit(1); }
  if (summary.off_topic_prompts_offered_to_online_model > 0) { console.error('FAIL: off-topic prompt offered to the online model'); process.exit(1); }
}
