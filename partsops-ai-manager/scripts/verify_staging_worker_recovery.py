"""Prepare, verify and clean up a durable worker-recovery proof run."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete
from sqlmodel import Session, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import engine
from models import (
    PartRequest,
    PipelineRun,
    PipelineRunEvent,
    RequestEvent,
    RequestState,
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def prepare() -> None:
    suffix = uuid.uuid4().hex[:12]
    tenant_id = f"worker-proof-{suffix}"
    request_id = f"REQ-WORKER-PROOF-{suffix}"
    run_id = f"PR-WORKER-PROOF-{suffix.upper()}"
    now = _now()
    with Session(engine) as session:
        session.add(
            PartRequest(
                request_id=request_id,
                tenant_id=tenant_id,
                source="worker-recovery-proof",
                status=RequestState.PART_EXTRACTION,
                customer_name="Worker recovery proof",
                parts_json='[{"name":"Proof position","quantity":1}]',
            )
        )
        session.add(
            PipelineRun(
                run_id=run_id,
                tenant_id=tenant_id,
                request_id=request_id,
                requested_by="staging-worker-verifier",
                start_from="invalid_recovery_proof",
                correlation_id=str(uuid.uuid4()),
                status="running",
                lease_owner="worker-before-restart",
                lease_expires_at=now - timedelta(seconds=5),
                started_at=now - timedelta(seconds=10),
                created_at=now - timedelta(seconds=10),
                updated_at=now - timedelta(seconds=10),
            )
        )
        session.add(
            PipelineRunEvent(
                run_id=run_id,
                tenant_id=tenant_id,
                sequence=1,
                event_type="pre_restart",
                message="Proof run persisted before worker restart.",
                payload_json="{}",
                created_at=now - timedelta(seconds=10),
            )
        )
        session.commit()
    print(json.dumps({"tenant_id": tenant_id, "request_id": request_id, "run_id": run_id}))


def verify(tenant_id: str, run_id: str) -> None:
    with Session(engine) as session:
        run = session.exec(
            select(PipelineRun).where(
                PipelineRun.tenant_id == tenant_id,
                PipelineRun.run_id == run_id,
            )
        ).first()
        events = session.exec(
            select(PipelineRunEvent)
            .where(
                PipelineRunEvent.tenant_id == tenant_id,
                PipelineRunEvent.run_id == run_id,
            )
            .order_by(PipelineRunEvent.sequence)
        ).all()
    if run is None:
        raise RuntimeError("Worker recovery proof run was not found")
    if run.status in {"queued", "running"}:
        print("staging_worker_recovery=pending")
        raise SystemExit(2)
    sequences = [event.sequence for event in events]
    event_types = [event.event_type for event in events]
    if run.status != "failed" or run.lease_owner is not None or run.finished_at is None:
        raise RuntimeError("Recovered run did not settle into a released terminal state")
    if sequences != list(range(1, len(events) + 1)):
        raise RuntimeError(f"Pipeline event sequence is not replayable: {sequences}")
    if event_types != ["pre_restart", "started", "failed"]:
        raise RuntimeError(f"Unexpected recovered event sequence: {event_types}")
    print("staging_worker_recovery=passed restart=1 replayable_events=3 terminal=failed")


def cleanup(tenant_id: str, request_id: str, run_id: str) -> None:
    with Session(engine) as session:
        session.exec(
            delete(PipelineRunEvent).where(
                PipelineRunEvent.tenant_id == tenant_id,
                PipelineRunEvent.run_id == run_id,
            )
        )
        session.exec(
            delete(RequestEvent).where(
                RequestEvent.tenant_id == tenant_id,
                RequestEvent.request_id == request_id,
            )
        )
        session.exec(
            delete(PipelineRun).where(
                PipelineRun.tenant_id == tenant_id,
                PipelineRun.run_id == run_id,
            )
        )
        session.exec(delete(PartRequest).where(PartRequest.request_id == request_id))
        session.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("prepare")
    for command in ("verify", "cleanup"):
        subparser = subcommands.add_parser(command)
        subparser.add_argument("--tenant-id", required=True)
        subparser.add_argument("--request-id", required=command == "cleanup")
        subparser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "verify":
        verify(args.tenant_id, args.run_id)
    else:
        cleanup(args.tenant_id, args.request_id, args.run_id)


if __name__ == "__main__":
    main()
