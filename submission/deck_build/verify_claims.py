"""Re-derives the numbers quoted in the pitch deck from the repository (run from the repo root; Python 3.12 venv with api/requirements-dev.txt).
Prints one line per claim. Nothing here touches the network, the live site or any database except pytest's temporary ones.
    python submission/deck_build/verify_claims.py
"""
import json, random, re, subprocess, sys
REAL_RANDOM = random.Random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
out = {}

# 1. Backend test count (collection only; the full run is `python -m pytest api/tests -q`).
r = subprocess.run([sys.executable, '-m', 'pytest', 'api/tests', '--collect-only', '-q', '-p', 'no:cacheprovider'], cwd=ROOT, capture_output=True, text=True)
m = re.search(r'(\d+) tests? collected', r.stdout)
out['backend_tests_collected'] = int(m.group(1)) if m else r.stdout[-200:]

# 2. Randomized financing check: the committed test uses one seed x 120 rounds; the review ran 119 seeds x 120 rounds.
sys.path.insert(0, str(ROOT / 'api' / 'tests'))
import importlib.util
spec = importlib.util.spec_from_file_location('fuzz', ROOT / 'api' / 'tests' / 'test_financing_fuzz.py')
fuzz = importlib.util.module_from_spec(spec); spec.loader.exec_module(fuzz)
seeds, rounds = 119, 120
for seed in range(seeds):
    fuzz.random.Random = lambda _x, s=seed: REAL_RANDOM(s)   # the test constructs Random(20261020); substitute our seed
    fuzz.test_random_quotes_never_crash_and_conserve_money()
out['randomized_financing_scenarios'] = f'{seeds} seeds x {rounds} rounds = {seeds * rounds}, all invariants held'

# 3. Languages and currencies.
out['interface_languages'] = len(list((ROOT / 'web/public/locales').glob('*.json'))) + 1  # + English source
out['currencies_in_picker_data'] = len(re.findall(r'"code"', (ROOT / 'web/src/currencies.ts').read_text(encoding='utf-8')))
print(json.dumps(out, indent=2))
