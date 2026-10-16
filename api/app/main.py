"""M0 bootstrap only. No ledger mutation or user-data endpoints are exposed."""
from contextlib import asynccontextmanager
import os
import sqlite3
from fastapi import FastAPI
from fastapi.responses import JSONResponse

SCHEMA_VERSION = 1

def connect():
    connection = sqlite3.connect(os.environ.get("SAFELEDGER_DB", "./safeledger.sqlite3"), timeout=5)
    connection.execute("PRAGMA foreign_keys=ON")
    return connection

@asynccontextmanager
async def lifespan(app: FastAPI):
    with connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS schema_meta (version INTEGER PRIMARY KEY)")
        db.execute("INSERT OR IGNORE INTO schema_meta(version) VALUES (?)", (SCHEMA_VERSION,))
    yield

app = FastAPI(title="SafeLedger AI", version="0.0.1", lifespan=lifespan)

@app.middleware("http")
async def headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.0.1", "build_commit": os.environ.get("SAFELEDGER_BUILD_COMMIT", "development"), "simulation_only": True, "milestone": "M0", "ai_status": "not_configured"}

@app.get("/api/ready")
def ready():
    try:
        with connect() as db:
            versions = [row[0] for row in db.execute("SELECT version FROM schema_meta")]
        if versions != [SCHEMA_VERSION]:
            raise sqlite3.DatabaseError("Unsupported schema")
    except sqlite3.Error:
        return JSONResponse(status_code=503, content={"status": "not_ready", "database": "unavailable"})
    return {"status": "ready", "database": "sqlite", "schema_version": SCHEMA_VERSION}
