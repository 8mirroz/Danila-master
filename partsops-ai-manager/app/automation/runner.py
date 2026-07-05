"""
Runner — executes jobs and pipelines from the registry.

Contract:
- `run_job(session, name, context)` — single job.
- `run_pipeline(session, name, context)` — ordered pipeline.

Invariants:
- dry-run is honored end-to-end.
- SQLite transactions stay short — no open tx across LLM / external HTTP.
- Every entered job appends at least one RequestEvent.
- State changes flow exclusively through state_machine helpers.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from sqlmodel import Session

from app.automation.context import AutomationContext
from app.automation.errors import AutomationError
from app.automation.events import append_request_event, append_system_event
from app.automation.registry import get_job, list_jobs
from models import JobRun
from pii import mask_for_log

logger = logging.getLogger("automation.runner")


def _make_job_id(job_name: str, tenant_id: str, request_id: Optional[str]) -> str:
    short = tenant_id[:4].upper()
    return f"JR-{short}-{job_name}-{uuid.uuid4().hex[:8].upper()}"


def _update_job_run(
    session: Session,
    job_run: JobRun,
    *,
    status: str,
    result: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    finished: bool = True,
    incr_events: int = 0,
):
    job_run.status = status
    if finished:
        job_run.finished_at = datetime.utcnow()
    if result is not None:
        import json
        try:
            job_run.result_json = json.dumps(result, default=str)
        except Exception:
            job_run.result_json = json.dumps({"serialization_error": True}, default=str)
    if error_message is not None:
        job_run.error_message = error_message
    if incr_events:
        job_run.events_emitted = (job_run.events_emitted or 0) + incr_events
    session.add(job_run)
    session.commit()


def run_job(
    session: Session,
    name: str,
    context: AutomationContext,
    *,
    event_started: Optional[str] = None,
    event_finished: Optional[str] = None,
) -> Dict[str, Any]:
    started = time.perf_counter()
    job_id = _make_job_id(name, context.tenant_id, context.request_id)
    started_ev = event_started or f"job.{name}.started"
    finished_ev = event_finished or f"job.{name}.finished"

    job_run = JobRun(
        tenant_id=context.tenant_id,
        job_id=job_id,
        job_name=name,
        status="running",
        started_at=datetime.utcnow(),
        dry_run=context.dry_run,
        correlation_id=context.correlation_id,
        idempotency_key=context.idempotency_key,
    )
    session.add(job_run)
    session.commit()
    session.refresh(job_run)

    append_system_event(
        session=session,
        tenant_id=context.tenant_id,
        event_type=started_ev,
        actor_type="automation",
        actor_id=context.actor_id,
        payload={
            "job_id": job_id,
            "request_id": context.request_id,
            "correlation_id": context.correlation_id,
            "dry_run": context.dry_run,
        },
        request_id=context.request_id,
        correlation_id=context.correlation_id,
    )

    func = get_job(name)

    if context.dry_run:
        result: Dict[str, Any] = {
            "ok": True,
            "dry_run": True,
            "skipped": True,
            "result": {"dry_run": True, "message": "No side-effects executed in dry-run."},
        }
        append_system_event(
            session=session,
            tenant_id=context.tenant_id,
            event_type=finished_ev,
            actor_type="automation",
            actor_id=context.actor_id,
            payload={"job_id": job_id, "status": "dry_run", "skipped": True},
            request_id=context.request_id,
        )
        _update_job_run(
            session,
            job_run,
            status="completed",
            result=result,
            finished=True,
            incr_events=2,
        )
    else:
        try:
            result = func(session, context)
            if result is None:
                result = {"ok": True, "result": {}}
            if not isinstance(result, dict):
                result = {"ok": True, "result": result}
            elif "ok" not in result:
                result = {**result, "ok": True}
        except AutomationError as exc:
            code = getattr(exc, "code", "automation_error")
            logger.warning(
                "Job failed: tenant=%s job=%s request=%s code=%s",
                context.tenant_id, name, context.request_id, code,
            )
            append_system_event(
                session=session,
                tenant_id=context.tenant_id,
                event_type=f"job.{name}.failed",
                actor_type="automation",
                actor_id=context.actor_id,
                payload={
                    "job_id": job_id,
                    "request_id": context.request_id,
                    "code": code,
                    "error": mask_for_log(str(exc)),
                    **getattr(exc, "context", {}),
                },
                request_id=context.request_id,
            )
            _update_job_run(
                session,
                job_run,
                status="failed",
                result={"ok": False, "code": code, "message": str(exc)},
                error_message=f"{code}: {exc}",
                finished=True,
                incr_events=2,
            )
            result = {"ok": False, "code": code, "message": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.exception("Job crashed: tenant=%s job=%s request=%s",
                             context.tenant_id, name, context.request_id)
            append_system_event(
                session=session,
                tenant_id=context.tenant_id,
                event_type=f"job.{name}.crashed",
                actor_type="automation",
                actor_id=context.actor_id,
                payload={
                    "job_id": job_id,
                    "request_id": context.request_id,
                    "error": mask_for_log(repr(exc)),
                },
                request_id=context.request_id,
            )
            _update_job_run(
                session,
                job_run,
                status="failed",
                result={"ok": False, "code": "internal_error", "message": repr(exc)},
                error_message=str(exc),
                finished=True,
                incr_events=2,
            )
            result = {"ok": False, "code": "internal_error", "message": repr(exc)}
        else:
            append_system_event(
                session=session,
                tenant_id=context.tenant_id,
                event_type=finished_ev,
                actor_type="automation",
                actor_id=context.actor_id,
                payload={"job_id": job_id, "status": "completed"},
                request_id=context.request_id,
            )
            _update_job_run(
                session,
                job_run,
                status="completed" if result.get("ok") is not False else "failed",
                result=result,
                finished=True,
                incr_events=2,
            )

    duration_ms = int((time.perf_counter() - started) * 1000)
    return {
        "job_id": job_id,
        "job_name": name,
        "ok": bool(result.get("ok")),
        "request_id": context.request_id,
        "dry_run": context.dry_run,
        "duration_ms": duration_ms,
        "result": result,
    }


def run_pipeline(
    session: Session,
    name: str,
    context: AutomationContext,
    *,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    from app.automation.registry import PIPELINE_REGISTRY

    func = PIPELINE_REGISTRY.get(name)
    if func is None:
        raise KeyError(f"Unknown pipeline {name!r}. Available: {sorted(PIPELINE_REGISTRY)}")

    append_system_event(
        session=session,
        tenant_id=context.tenant_id,
        event_type="pipeline.started",
        actor_type="automation",
        actor_id=context.actor_id,
        payload={
            "pipeline": name,
            "request_id": context.request_id,
            "correlation_id": context.correlation_id,
            "dry_run": context.dry_run,
            "limit": limit,
        },
        request_id=context.request_id,
    )
    result = func(session, context)
    if not isinstance(result, dict):
        result = {"ok": True, "result": result}
    append_system_event(
        session=session,
        tenant_id=context.tenant_id,
        event_type="pipeline.finished",
        actor_type="automation",
        actor_id=context.actor_id,
        payload={
            "pipeline": name,
            "request_id": context.request_id,
            "ok": bool(result.get("ok", True)),
        },
        request_id=context.request_id,
    )
    return result
