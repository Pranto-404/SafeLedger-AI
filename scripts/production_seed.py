"""Production seed: auto-seed SQLite on first deploy if DB is empty.

Called by Render's startCommand before uvicorn via render_start.sh.
Reads SAFELEDGER_SIGNING_KEY from environment (Render generates it).
Writes session tokens to stdout ONLY once — capture them in Render logs.
If DB already has data, does nothing (idempotent safe restart).
"""
from pathlib import Path
import json
import os
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.app import security as sec
from api.app.services.intake import parse_json
from api.app.services.storage import store_dataset, create_schema as storage_schema
from api.app.agents import runner

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data/fixtures/seed_2026.json"

def seed_if_empty():
    db_path = os.environ.get("SAFELEDGER_DB", "./safeledger.sqlite3")
    key = os.environ.get("SAFELEDGER_SIGNING_KEY", "")
    if not key:
        print("[seed] ERROR: SAFELEDGER_SIGNING_KEY not set — cannot provision sessions.", flush=True)
        sys.exit(1)

    # Ensure data directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path, timeout=10) as db:
        db.execute("PRAGMA foreign_keys=ON")
        # Create schema tables (idempotent)
        db.execute("CREATE TABLE IF NOT EXISTS schema_meta (version INTEGER PRIMARY KEY)")
        db.execute("INSERT OR IGNORE INTO schema_meta(version) VALUES (1)")
        sec.create_schema(db)
        storage_schema(db)
        runner.create_schema(db)

        # Check if demo data already loaded
        row = db.execute("SELECT count(*) FROM financial_datasets WHERE business_id='synthetic-demo'").fetchone()
        if row and row[0] > 0:
            print("[seed] Demo data already present — skipping seed.", flush=True)
            return

        # Load fixture
        ds = parse_json(FIXTURE.read_bytes())
        store_dataset(db, "synthetic-demo", ds)
        with db:
            db.execute("INSERT OR IGNORE INTO security_policies VALUES (?,?,?)",
                       ("synthetic-demo", 1000000, 10000000))
            db.executemany("INSERT OR IGNORE INTO trusted_vendors VALUES (?,?,1)",
                           [("synthetic-demo", v) for v in sorted({i.vendor_id for i in ds.invoices})])

        # Provision long-lived demo sessions (30 days for competition)
        tokens = {}
        for role in ["owner", "approver", "viewer", "agent"]:
            tokens[role] = sec.provision_session(
                db, f"demo-{role}", "synthetic-demo", role, ttl_seconds=86400
            )

        # Print tokens ONCE to Render logs — judge captures them
        print("[seed] === DEMO SESSION TOKENS (copy from Render logs, do not share publicly) ===", flush=True)
        print(json.dumps({"simulation_only": True, "bearer_tokens": tokens}, indent=2), flush=True)
        print("[seed] === END TOKENS ===", flush=True)
        print("[seed] Seed complete.", flush=True)


if __name__ == "__main__":
    seed_if_empty()
