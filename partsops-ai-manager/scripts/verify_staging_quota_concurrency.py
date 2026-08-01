"""Prove PostgreSQL quota reservation is atomic in a staging-like runtime.

The verifier creates isolated data, starts two pipeline runs concurrently for a
single remaining billable position, checks that exactly one run is accepted,
and removes every record it created before exiting.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import delete, func
from sqlmodel import Session, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import engine
from models import (
    OnboardingState,
    Organization,
    PartRequest,
    PipelineRun,
    PipelineRunEvent,
    RequestEvent,
    RequestState,
    Subscription,
    UsageEvent,
)
from services.pipeline_runs import start_pipeline_run
from services.saas import ensure_organization


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", "")


def _require_postgres() -> None:
    if not _database_url().startswith(("postgresql://", "postgres://")):
        raise RuntimeError("This verifier must run against PostgreSQL")


def _cleanup(organization_id: str, request_ids: tuple[str, str]) -> None:
    with Session(engine) as session:
        session.exec(
            delete(PipelineRunEvent).where(PipelineRunEvent.tenant_id == organization_id)
        )
        session.exec(delete(PipelineRun).where(PipelineRun.tenant_id == organization_id))
        session.exec(delete(RequestEvent).where(RequestEvent.tenant_id == organization_id))
        session.exec(delete(UsageEvent).where(UsageEvent.organization_id == organization_id))
        session.exec(delete(PartRequest).where(PartRequest.request_id.in_(request_ids)))
        session.exec(
            delete(OnboardingState).where(OnboardingState.organization_id == organization_id)
        )
        session.exec(
            delete(Subscription).where(Subscription.organization_id == organization_id)
        )
        session.exec(
            delete(Organization).where(Organization.organization_id == organization_id)
        )
        session.commit()


def main() -> None:
    _require_postgres()
    suffix = uuid.uuid4().hex[:12]
    organization_id = f"quota-proof-{suffix}"
    request_ids = (f"REQ-QUOTA-{suffix}-A", f"REQ-QUOTA-{suffix}-B")
    barrier = threading.Barrier(2)

    try:
        with Session(engine) as session:
            ensure_organization(session, organization_id, display_name="Quota proof")
            subscription = session.exec(
                select(Subscription).where(
                    Subscription.organization_id == organization_id
                )
            ).one()
            subscription.status = "active"
            subscription.plan_code = "start"
            subscription.position_limit = 1
            session.add(subscription)
            for request_id in request_ids:
                session.add(
                    PartRequest(
                        request_id=request_id,
                        tenant_id=organization_id,
                        source="quota-proof",
                        status=RequestState.PART_EXTRACTION,
                        customer_name="Quota proof",
                        parts_json=json.dumps([{"name": "Proof position", "quantity": 1}]),
                    )
                )
            session.commit()

        def start(request_id: str) -> str:
            with Session(engine) as session:
                barrier.wait(timeout=10)
                try:
                    start_pipeline_run(
                        session,
                        request_id=request_id,
                        tenant_id=organization_id,
                        requested_by="staging-quota-verifier",
                        requested_lane="matching",
                    )
                    return "accepted"
                except HTTPException as exc:
                    session.rollback()
                    if exc.status_code == 402:
                        return "quota_rejected"
                    raise

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(start, request_ids))

        with Session(engine) as session:
            usage = session.exec(
                select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
                    UsageEvent.organization_id == organization_id
                )
            ).one()
            runs = session.exec(
                select(PipelineRun).where(PipelineRun.tenant_id == organization_id)
            ).all()

        if outcomes.count("accepted") != 1 or outcomes.count("quota_rejected") != 1:
            raise RuntimeError(f"Unexpected concurrent outcomes: {outcomes}")
        if int(usage or 0) != 1 or len(runs) != 1:
            raise RuntimeError(
                f"Quota ledger mismatch: usage={int(usage or 0)}, runs={len(runs)}"
            )
        print("staging_quota_concurrency=passed accepted=1 quota_rejected=1 usage=1")
    finally:
        _cleanup(organization_id, request_ids)


if __name__ == "__main__":
    main()
