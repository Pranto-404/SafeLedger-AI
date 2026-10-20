"""Authenticated financial recordkeeping; ledger posting only after human approval."""
from contextlib import asynccontextmanager, closing
import os
import logging
import sqlite3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from api.app import security
from api.app.body_limit import BodyLimitMiddleware
from api.app.ratelimit import limiter
from api.app.routes import router
from api.app.agents.schema import create_schema as agent_schema
from api.app.agents.errors import ProviderError
from api.app.database import connect
from api.app import accounts, inputs, financing, profile, workspaces, fx, assist, i18n, mailer

def _cors_origins() -> list[str]:
    """Read allowed origins from env; default to localhost dev ports only."""
    raw = os.environ.get("SAFELEDGER_CORS_ORIGINS", "")
    origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    if not origins:
        origins = ["http://127.0.0.1:5173", "http://localhost:5173",
                   "http://127.0.0.1:4173", "http://localhost:4173"]
    return origins

SCHEMA_VERSION = 1

@asynccontextmanager
async def lifespan(app: FastAPI):
    limiter.reset()
    mailer.reset_budget()
    with closing(connect()) as db:
        with db:
            db.execute("CREATE TABLE IF NOT EXISTS schema_meta (version INTEGER PRIMARY KEY)")
            db.execute("INSERT OR IGNORE INTO schema_meta(version) VALUES (?)", (SCHEMA_VERSION,))
        security.create_schema(db)
        agent_schema(db)
        accounts.schema(db)
        profile.schema(db)
        i18n.schema(db)
        accounts.archive_legacy_examples(db)
    yield

app = FastAPI(title="Capzoryx Copilot", version="0.7.6", lifespan=lifespan)
app.add_middleware(BodyLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-SafeLedger-Client"],
)
app.include_router(router)
app.include_router(accounts.router)
app.include_router(inputs.router)
app.include_router(financing.router)
app.include_router(profile.router)
app.include_router(workspaces.router)
app.include_router(fx.router)
app.include_router(assist.router)
app.include_router(i18n.router)

@app.exception_handler(ProviderError)
async def ai_error(request,exc):
    return JSONResponse(status_code=503,content={"error":{"code":exc.code},"ai_status":"unavailable","deterministic_finance_available":True,**({"provider_http_status":exc.http_status} if isinstance(exc.http_status,int) and 400<=exc.http_status<=599 else {})})

@app.exception_handler(security.PolicyError)
async def policy_error(request,exc):
    headers={"WWW-Authenticate":"Bearer"} if exc.status==401 else {}
    error={"code":exc.code}
    if exc.retry_after:
        headers["Retry-After"]=str(exc.retry_after);error["retry_after"]=exc.retry_after
    return JSONResponse(status_code=exc.status,content={"error":error},headers=headers)

@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    return JSONResponse(status_code=422,content={"error":{"code":"INVALID_INPUT","fields":[{"field":".".join(map(str,x["loc"])),"message":x["msg"],"type":x["type"]} for x in exc.errors()]}})

@app.exception_handler(sqlite3.Error)
async def database_error(request,exc):
    logging.getLogger("safeledger").warning("Database request rejected; exception_type=%s",type(exc).__name__)
    return JSONResponse(status_code=503,content={"error":{"code":"DATABASE_UNAVAILABLE"}})


@app.middleware("http")
async def headers(request, call_next):
    if (os.environ.get('RENDER') or os.environ.get('VERCEL')) and request.url.path in {'/docs','/redoc','/openapi.json','/docs/oauth2-redirect'}:
        response=JSONResponse(status_code=404,content={'error':{'code':'NOT_FOUND'}})
    else:
        response = await call_next(request)
    response.headers['X-Frame-Options']='DENY'
    response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=(), payment=()'
    if request.url.path.startswith('/api/'):
        response.headers['Content-Security-Policy']="default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    if request.url.scheme=='https' or os.environ.get('RENDER') or os.environ.get('VERCEL'):
        response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

@app.get("/api/health")
def health():
    configured=all(os.environ.get(key) for key in ("SAFELEDGER_LLM_BASE_URL","SAFELEDGER_LLM_MODEL","SAFELEDGER_LLM_API_KEY"))
    return {"status": "ok", "version": "0.7.6", "build_commit": (os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("VERCEL_GIT_COMMIT_SHA") or os.environ.get("SAFELEDGER_BUILD_COMMIT", "development")), "simulation_only": True, "release": "accounts-and-assistant", "ai_status": "configured_not_verified" if configured else "not_configured"}

@app.get("/api/ready")
def ready():
    try:
        with closing(connect()) as db:
            versions = [row[0] for row in db.execute("SELECT version FROM schema_meta")]
        if versions != [SCHEMA_VERSION]:
            raise sqlite3.DatabaseError("Unsupported schema")
    except sqlite3.Error:
        return JSONResponse(status_code=503, content={"status": "not_ready", "database": "unavailable"})
    return {"status": "ready", "database": "libsql" if os.environ.get("TURSO_DATABASE_URL") else "sqlite", "schema_version": SCHEMA_VERSION}
