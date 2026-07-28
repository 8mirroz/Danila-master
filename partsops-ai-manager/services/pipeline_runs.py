"""Durable pipeline-run queue used by the Kanban operator workflow."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from event_store import emit_event
from models import PartRequest, PipelineRun, PipelineRunEvent, RequestState


ACTIVE_STATUSES = {"queued", "running"}
TERMINAL_STATUSES = {"completed", "failed", "blocked"}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json_load(value: Optional[str], fallback: Any) -> Any:
    try:
        return json.loads(value) if value else fallback
    except json.JSONDecodeError:
        return fallback


def _serialize_run(run: PipelineRun, *, idempotent: bool = False) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "request_id": run.request_id,
        "status": run.status,
        "start_from": run.start_from,
        "requested_lane": run.requested_lane,
        "correlation_id": run.correlation_id,
        "error_message": run.error_message,
        "result": _json_load(run.result_json, None),
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "idempotent": idempotent,
    }


def _resolve_start_from(request: PartRequest) -> str:
    status = str(request.status)
    if status == RequestState.APPROVED:
        return "delivery"
    if status in {RequestState.SENT_TO_CLIENT, RequestState.INVOICE_DRAFTED}:
        return "reporting"
    if status == RequestState.READY_FOR_APPROVAL:
        raise HTTPException(
            status_code=422,
            detail="Запрос ожидает решения оператора: сначала согласуйте или отправьте на доработку.",
        )
    if status in {RequestState.CLOSED, RequestState.CANCELLED, RequestState.CLIENT_REJECTED, RequestState.EXPIRED}:
        raise HTTPException(status_code=422, detail="Для терминального запроса pipeline не запускается.")
    parts = _json_load(request.parts_json, [])
    if not isinstance(parts, list) or not parts:
        raise HTTPException(
            status_code=422,
            detail="Нельзя запустить pipeline: добавьте хотя бы одну распознанную позицию в запрос.",
        )
    return "processing"


def start_pipeline_run(
    session: Session,
    *,
    request_id: str,
    tenant_id: str,
    requested_by: str,
    requested_lane: Optional[str],
) -> tuple[PipelineRun, bool]:
    request = session.exec(
        select(PartRequest).where(
            PartRequest.request_id == request_id,
            PartRequest.tenant_id == tenant_id,
        )
    ).first()
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")

    existing = session.exec(
        select(PipelineRun)
        .where(PipelineRun.request_id == request_id, PipelineRun.tenant_id == tenant_id)
        .where(PipelineRun.status.in_(ACTIVE_STATUSES))
        .order_by(PipelineRun.created_at.desc())
    ).first()
    if existing:
        return existing, True

    run = PipelineRun(
        run_id=f"PR-{uuid.uuid4().hex[:12].upper()}",
        tenant_id=tenant_id,
        request_id=request_id,
        requested_by=requested_by,
        requested_lane=requested_lane,
        start_from=_resolve_start_from(request),
        correlation_id=str(uuid.uuid4()),
        status="queued",
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    append_run_event(session, run, "queued", message="Запуск pipeline поставлен в очередь.")
    emit_event(
        session=session,
        request_id=request_id,
        event_type="PIPELINE_RUN_QUEUED",
        actor_type="user",
        actor_id=requested_by,
        payload={"run_id": run.run_id, "correlation_id": run.correlation_id, "start_from": run.start_from},
        tenant_id=tenant_id,
    )
    return run, False


def get_pipeline_run(session: Session, *, request_id: str, run_id: str, tenant_id: str) -> PipelineRun:
    run = session.exec(
        select(PipelineRun).where(
            PipelineRun.run_id == run_id,
            PipelineRun.request_id == request_id,
            PipelineRun.tenant_id == tenant_id,
        )
    ).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return run


def list_run_events(session: Session, *, run_id: str, tenant_id: str, after: int = 0) -> list[PipelineRunEvent]:
    return session.exec(
        select(PipelineRunEvent)
        .where(PipelineRunEvent.run_id == run_id, PipelineRunEvent.tenant_id == tenant_id)
        .where(PipelineRunEvent.sequence > after)
        .order_by(PipelineRunEvent.sequence)
    ).all()


def append_run_event(
    session: Session,
    run: PipelineRun,
    event_type: str,
    *,
    phase: Optional[str] = None,
    message: str = "",
    payload: Optional[dict[str, Any]] = None,
) -> PipelineRunEvent:
    previous = session.exec(
        select(PipelineRunEvent)
        .where(PipelineRunEvent.run_id == run.run_id, PipelineRunEvent.tenant_id == run.tenant_id)
        .order_by(PipelineRunEvent.sequence.desc())
    ).first()
    event = PipelineRunEvent(
        run_id=run.run_id,
        tenant_id=run.tenant_id,
        sequence=(previous.sequence if previous else 0) + 1,
        event_type=event_type,
        phase=phase,
        message=message,
        payload_json=json.dumps(payload or {}, ensure_ascii=False, default=str),
        created_at=_now(),
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def claim_next_run(session: Session, *, worker_id: str, lease_seconds: int = 120) -> Optional[PipelineRun]:
    now = _now()
    candidates = session.exec(
        select(PipelineRun)
        .where((PipelineRun.status == "queued") | ((PipelineRun.status == "running") & (PipelineRun.lease_expires_at < now)))
        .order_by(PipelineRun.created_at)
    ).all()
    if not candidates:
        return None
    run = candidates[0]
    run.status = "running"
    run.lease_owner = worker_id
    run.lease_expires_at = now + timedelta(seconds=lease_seconds)
    run.started_at = run.started_at or now
    run.updated_at = now
    session.add(run)
    session.commit()
    session.refresh(run)
    append_run_event(session, run, "started", message="Worker начал выполнение pipeline.")
    return run


def execute_claimed_run(session: Session, run: PipelineRun) -> PipelineRun:
    from app.agents import AgentType, create_orchestrator

    def on_phase(event_type: str, phase: str, data: dict[str, Any]) -> None:
        append_run_event(
            session,
            run,
            event_type,
            phase=phase,
            message=data.get("message", ""),
            payload=data.get("payload", {}),
        )

    try:
        orchestrator = create_orchestrator(tenant_id=run.tenant_id)
        result = orchestrator.continue_pipeline(
            request_id=run.request_id,
            start_from=AgentType(run.start_from),
            on_phase=on_phase,
        )
        run.result_json = json.dumps({
            "success": result.success,
            "request_id": result.request_id,
            "phases": {name: phase.to_dict() for name, phase in result.phases.items()},
            "errors": result.errors,
            "warnings": result.warnings,
            "total_time_ms": result.total_time_ms,
        }, ensure_ascii=False, default=str)
        run.status = "completed" if result.success else "failed"
        run.error_message = "; ".join(result.errors) if result.errors else None
        append_run_event(
            session,
            run,
            "completed" if result.success else "failed",
            message="Pipeline завершён." if result.success else "Pipeline завершился с ошибкой.",
            payload={"errors": result.errors, "warnings": result.warnings},
        )
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger("services.pipeline_runs").exception(
            "Pipeline run %s failed", run.run_id
        )
        run.status = "failed"
        # Honest operator-facing error (truncated); full traceback stays in logs.
        run.error_message = str(exc)[:500] or "Pipeline execution failed"
        append_run_event(
            session,
            run,
            "failed",
            message="Pipeline завершился внутренней ошибкой.",
            payload={"error": run.error_message},
        )
    finally:
        run.finished_at = _now()
        run.updated_at = _now()
        run.lease_owner = None
        run.lease_expires_at = None
        session.add(run)
        session.commit()
        session.refresh(run)
    return run


def run_once(worker_id: str) -> Optional[dict[str, Any]]:
    from database import engine
    with Session(engine) as session:
        run = claim_next_run(session, worker_id=worker_id)
        if run is None:
            return None
        return _serialize_run(execute_claimed_run(session, run))


def serialize_run(run: PipelineRun, *, idempotent: bool = False) -> dict[str, Any]:
    return _serialize_run(run, idempotent=idempotent)
