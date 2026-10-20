"""Runs the committed randomized financing test (api/tests/test_financing_fuzz.py) with many seeds and counts what really happened.
The test builds random businesses and 1-10 random lender quotes per round and asserts: no crash, money conserved to the minor unit,
fitting offers ranked first, costs sorted, schedules add up. Rounds whose random terms are invalid are refused, which the test treats as the correct outcome; each round also re-runs the match with the quotes shuffled and requires the same answer.
    python submission/evidence_build/financing_stress.py [seeds]      (nothing here touches a network or a database)"""
import importlib.util, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('fuzz', ROOT / 'api' / 'tests' / 'test_financing_fuzz.py')
fuzz = importlib.util.module_from_spec(spec); spec.loader.exec_module(fuzz)
REAL = random.Random
seeds = int(sys.argv[1]) if len(sys.argv) > 1 else 119
rounds_per_seed = 120
failures = 0; t0 = time.time()
for seed in range(seeds):
    fuzz.random.Random = lambda _x, s=seed: REAL(s)  # the test constructs Random(20261020); use our own seed instead
    try:
        fuzz.test_random_quotes_never_crash_and_conserve_money()
    except Exception as e:
        failures += 1
        print('seed', seed, 'FAILED', type(e).__name__, str(e)[:200])
print(f'seeds run                    : {seeds}')
print(f'rounds per seed              : {rounds_per_seed}')
print(f'randomized scenarios (rounds): {seeds * rounds_per_seed}')
print(f'seeds with a failed assertion: {failures}')
print(f'seconds                      : {time.time() - t0:.1f}')
sys.exit(1 if failures else 0)
