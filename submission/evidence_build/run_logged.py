"""Runs one command, saves its raw output with a header (command, start time, git commit, exit code, duration).
    python submission/evidence_build/run_logged.py <log_name> <working_dir_relative_to_repo> -- <command ...>
Nothing is edited: the body of the log is exactly what the command printed (only e-mail addresses are masked)."""
import re, subprocess, sys, time, datetime, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
LOGS = Path(os.environ.get('EVIDENCE_LOGS', r'D:\China Comp\Capzoryx_Submission_Final\Capzoryx_Execution_Evidence_Logs'))
name, cwd = sys.argv[1], sys.argv[2]
cmd = sys.argv[sys.argv.index('--') + 1:]
commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
t0 = time.time(); start = datetime.datetime.now().astimezone()
env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1', NO_COLOR='1', FORCE_COLOR='0')
p = subprocess.run(cmd, cwd=ROOT / cwd, capture_output=True, env=env, shell=(os.name == 'nt'))
out = (p.stdout.decode('utf-8', 'replace') + (('\n--- stderr ---\n' + p.stderr.decode('utf-8', 'replace')) if p.stderr.strip() else ''))
out = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', out)
out = re.sub(r'[\w.+-]+@[\w-]+\.[\w.-]+', '[email-masked]', out)
head = f"Capzoryx Copilot - execution evidence log\nCommand : {' '.join(cmd)}\nFolder  : {cwd}\nStarted : {start.strftime('%Y-%m-%d %H:%M:%S %z')}\nCommit  : {commit}\nExit    : {p.returncode}\nSeconds : {time.time() - t0:.1f}\n{'=' * 70}\n"
(LOGS / name).write_bytes((head + out).encode('utf-8'))  # bytes: keep plain 
 line endings
print(name, 'exit', p.returncode, f'{time.time() - t0:.1f}s')
