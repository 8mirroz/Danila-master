"""
PartsOps AI Manager v3 — FastAPI Control Plane.

This runtime keeps the existing request workflow alive and adds the supplier
workspace backend contract used by the admin cockpit.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from database import engine, init_db
from middleware import CorrelationIDMiddleware
from suppliers import seed_database
from settings import settings

# Import routers
from routers.requests import router as requests_router
from routers.suppliers import router as suppliers_router
from routers.observability import router as observability_router
from routers.chat import router as chat_router
from routers.erp import router as erp_router
from routers.catalog import router as catalog_router
from routers.data_health import router as data_health_router
from routers.contracts import router as contracts_router
from routers.webhooks import router as webhooks_router
from routers.analogs import router as analogs_router
from routers.copilot import router as copilot_router
from routers.saas import router as saas_router
from routers.rfq_imports import router as rfq_imports_router
from routers.quotes import router as quotes_router
from routers.integrations import router as integrations_router
from routers.analytics import router as analytics_router
import models_copilot

load_dotenv()


def _should_seed_on_start() -> bool:
    """Demo seed is opt-in for production-like DBs; local sqlite/dev still seeds by default."""
    raw = os.getenv("SEED_ON_START")
    if raw is not None:
        return raw.strip().lower() in ("1", "true", "yes")
    env = os.getenv("PARTSOPS_ENV", os.getenv("ENV", "")).lower()
    if env in ("prod", "production"):
        return False
    if env in ("dev", "development", "test", "local", "ci"):
        return True
    # Env unset: seed only for sqlite / empty DATABASE_URL (local demo), never for postgres by default.
    db_url = (os.getenv("DATABASE_URL") or "").strip().lower()
    if not db_url or db_url.startswith("sqlite"):
        return True
    return False


def _should_initialize_schema_on_start() -> bool:
    """Keep SQLite development convenient without racing Alembic on PostgreSQL."""
    db_url = (os.getenv("DATABASE_URL") or "").strip().lower()
    return not db_url.startswith(("postgresql://", "postgres://"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_auth_configuration()
    if _should_initialize_schema_on_start():
        init_db()
    else:
        print("[startup] schema initialization deferred to Alembic")
    if _should_seed_on_start():
        with Session(engine) as session:
            seed_database(session)
    else:
        print("[startup] seed_database skipped (SEED_ON_START=0 or prod env)")
    yield


app = FastAPI(
    title="PartsOps AI Manager API",
    version="3.0",
    description="Evidence-based operational control plane for auto parts supply automation.",
    lifespan=lifespan,
)

# CORS from settings
cors_origins = [
    origin.strip()
    for origin in (
        os.getenv("PARTSOPS_CORS_ORIGINS")
        or settings.CORS_ALLOW_ORIGINS
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CorrelationIDMiddleware)

# Include routers. SaaS precedes requests because it owns the enriched /api/session
# contract while preserving the existing principal and permissions fields.
app.include_router(saas_router)
app.include_router(requests_router)
app.include_router(suppliers_router)
app.include_router(observability_router)
app.include_router(chat_router)
app.include_router(erp_router)
app.include_router(catalog_router)
app.include_router(data_health_router)
app.include_router(contracts_router)
app.include_router(webhooks_router)
app.include_router(analogs_router)
app.include_router(copilot_router)
app.include_router(rfq_imports_router)
app.include_router(quotes_router)
app.include_router(integrations_router)
app.include_router(analytics_router)

@app.get("/")
def read_root():
    return {
        "status": "ok",
        "message": "PartsOps AI Manager Control Plane v3",
        "version": "3.0",
        "phase": settings.PHASE_LABEL,
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "version": "3.0",
        "phase": settings.PHASE_LABEL,
    }
