"""Start a local API, wait for readiness, run smoke, then terminate the server."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

with tempfile.TemporaryDirectory(prefix="safeledger-smoke-") as temp:
    env = dict(os.environ, SAFELEDGER_DB=str(Path(temp) / "smoke.sqlite3"))
    evidence = Path(os.environ.get("SAFELEDGER_EVIDENCE_DIR", "evidence/m0"))
    evidence.mkdir(parents=True, exist_ok=True)
    with (evidence / "uvicorn.log").open("w") as log:
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "api.app.main:app", "--host", "127.0.0.1", "--port", "8000"], env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            for attempt in range(50):
                if server.poll() is not None:
                    raise RuntimeError("API exited before readiness; inspect uvicorn.log")
                try:
                    with urlopen("http://127.0.0.1:8000/api/ready", timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("API did not become ready within 5 seconds")
            subprocess.run([sys.executable, "scripts/smoke.py"], check=True, env=env)
        finally:
            server.terminate()
            server.wait(timeout=5)
