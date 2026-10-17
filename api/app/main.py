"""M2 authenticated synthetic-finance API; sandbox posting only after human approval."""
from contextlib import asynccontextmanager, closing
import os
import logging
import sqlite3
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from api.app import security
from api.app.body_limit import BodyLimitMiddleware
from api.app.routes import router
from api.app.agents import runner
from api.app.agents.provider import ProviderError

SCHEMA_VERSION = 1

def connect():
    connection = sqlite3.connect(os.environ.get("SAFELEDGER_DB", "./safeledger.sqlite3"), timeout=5, check_same_thread=False)
    connection.execute("PRAGMA foreign_keys=ON")
    return connection

@asynccontextmanager
async def lifespan(app: FastAPI):
    with closing(connect()) as db:
        with db:
            db.execute("CREATE TABLE IF NOT EXISTS schema_meta (version INTEGER PRIMARY KEY)")
            db.execute("INSERT OR IGNORE INTO schema_meta(version) VALUES (?)", (SCHEMA_VERSION,))
        security.create_schema(db)
        runner.create_schema(db)
    yield

app = FastAPI(title="SafeLedger AI", version="0.3.0", lifespan=lifespan)
app.add_middleware(BodyLimitMiddleware)
app.include_router(router)

@app.exception_handler(ProviderError)
async def ai_error(request,exc):
    return JSONResponse(status_code=503,content={"error":{"code":exc.code},"ai_status":"unavailable","deterministic_finance_available":True})

@app.exception_handler(security.PolicyError)
async def policy_error(request,exc):
    headers={"WWW-Authenticate":"Bearer"} if exc.status==401 else {}
    return JSONResponse(status_code=exc.status,content={"error":{"code":exc.code}},headers=headers)

@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    return JSONResponse(status_code=422,content={"error":{"code":"INVALID_INPUT","fields":[{"field":".".join(map(str,x["loc"])),"message":x["msg"],"type":x["type"]} for x in exc.errors()]}})

@app.exception_handler(sqlite3.Error)
async def database_error(request,exc):
    logging.getLogger("safeledger").warning("Database request rejected; exception_type=%s",type(exc).__name__)
    return JSONResponse(status_code=503,content={"error":{"code":"DATABASE_UNAVAILABLE"}})


@app.middleware("http")
async def headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

@app.get("/api/health")
def health():
    configured=all(os.environ.get(key) for key in ("SAFELEDGER_LLM_BASE_URL","SAFELEDGER_LLM_MODEL","SAFELEDGER_LLM_API_KEY"))
    return {"status": "ok", "version": "0.3.0", "build_commit": os.environ.get("SAFELEDGER_BUILD_COMMIT", "development"), "simulation_only": True, "milestone": "M3", "ai_status": "configured_not_verified" if configured else "not_configured"}

@app.get("/api/ready")
def ready():
    try:
        with closing(connect()) as db:
            versions = [row[0] for row in db.execute("SELECT version FROM schema_meta")]
        if versions != [SCHEMA_VERSION]:
            raise sqlite3.DatabaseError("Unsupported schema")
    except sqlite3.Error:
        return JSONResponse(status_code=503, content={"status": "not_ready", "database": "unavailable"})
    return {"status": "ready", "database": "sqlite", "schema_version": SCHEMA_VERSION}
