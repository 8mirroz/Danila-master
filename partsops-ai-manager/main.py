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

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as session:
        seed_database(session)
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

# Include routers
app.include_router(requests_router)
app.include_router(suppliers_router)
app.include_router(observability_router)
app.include_router(chat_router)
app.include_router(erp_router)
app.include_router(catalog_router)


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