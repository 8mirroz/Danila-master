"""
PartsOps AI Manager v3 — FastAPI Copilot Router (Hermes Integration).
Implements Hermes Sessions/Runs/SSE API broker, RBAC, PII masking, rate limits, and real Hermes CLI/Server execution.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Optional, Dict, Any, List, Set
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select, func

from database import get_session
from rbac import get_current_tenant, RoleChecker, CurrentPrincipal, get_current_principal
from settings import settings
from pii import secure_pre_parse
from models_copilot import CopilotConversation, CopilotMessage, CopilotRun
from services.copilot_context import (
    CopilotContextRef,
    build_context_envelope,
    build_hermes_instructions,
    validate_and_filter_sources,
)
from services.help_service import get_help_source_by_id
from services.hermes_transport import HermesTransport, HermesTransportError, is_strong_api_key
from services.local_copilot import build_local_reply, chunk_text

router = APIRouter(prefix="/api/copilot", tags=["Copilot"])

require_copilot_role = RoleChecker(allowed_roles=["admin", "manager"])
PARTSOPS_SKILLS = ["partsops-navigation", "partsops-request-explainer", "partsops-troubleshooting"]
_LOCAL_FALLBACK_CODES = {
    "HERMES_KEY_NOT_CONFIGURED",
    "HERMES_TIMEOUT",
    "HERMES_START_TIMEOUT",
    "HERMES_STREAM_TIMEOUT",
    "HERMES_UPSTREAM_RETRYABLE",
    "HERMES_AUTH_FAILED",
    "HERMES_CONTRACT_MISMATCH",
    "HERMES_UNAVAILABLE",
    "HERMES_INVALID_RESPONSE",
}

# Global run memory lock for active runs and native upstream identifiers.
_active_runs: Dict[str, asyncio.Task] = {}
_run_cancel_events: Dict[str, asyncio.Event] = {}
_run_upstream_ids: Dict[str, str] = {}
_run_locks: Dict[str, asyncio.Lock] = {}

# Tenant rate limit counters (minute window)
_tenant_run_history: Dict[str, List[datetime]] = {}
# Process-local concurrent slots: reserved at run *create* (closes queue race where
# many clients create runs before any SSE stream starts). Released once per run_id
# on SSE finally or stop — never double-decrement.
# Abandoned queued runs (client never SSE/stop) are reaped after TTL so slots
# do not leak forever in this process.
_tenant_concurrent_runs: Dict[str, int] = {}
_run_concurrent_holders: Dict[str, str] = {}  # run_id -> tenant_id
_run_concurrent_reserved_at: Dict[str, float] = {}  # run_id -> time.monotonic()
_run_slot_streaming: Set[str] = set()  # run_ids with active SSE (never reap while streaming)
_concurrent_lock = threading.Lock()


def _abandoned_slot_ttl_seconds() -> float:
    try:
        return max(1.0, float(settings.COPILOT_ABANDONED_SLOT_TTL_SECONDS))
    except (TypeError, ValueError, AttributeError):
        return 120.0


def _reap_abandoned_slots_unlocked(now: Optional[float] = None) -> int:
    """Release non-streaming slots older than TTL. Caller must hold _concurrent_lock."""
    deadline = _abandoned_slot_ttl_seconds()
    ts = time.monotonic() if now is None else now
    reaped = 0
    for run_id, reserved_at in list(_run_concurrent_reserved_at.items()):
        if run_id in _run_slot_streaming:
            continue
        if (ts - reserved_at) < deadline:
            continue
        tenant_id = _run_concurrent_holders.pop(run_id, None)
        _run_concurrent_reserved_at.pop(run_id, None)
        _run_slot_streaming.discard(run_id)
        if tenant_id is None:
            continue
        _tenant_concurrent_runs[tenant_id] = max(
            0, _tenant_concurrent_runs.get(tenant_id, 1) - 1
        )
        reaped += 1
    return reaped


def _reserve_concurrent_slot(tenant_id: str, run_id: str, max_concurrent: int) -> int:
    """Atomically reserve a concurrent slot for run_id. Returns count after reserve.

    Raises HTTPException 429 if tenant is already at the process-local cap.
    Idempotent if the same run_id already holds a slot.
    Reaps abandoned (non-streaming, past TTL) slots before enforcing the cap.
    """
    with _concurrent_lock:
        _reap_abandoned_slots_unlocked()
        if run_id in _run_concurrent_holders:
            return _tenant_concurrent_runs.get(tenant_id, 0)
        current = _tenant_concurrent_runs.get(tenant_id, 0)
        if current >= max_concurrent:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "COPILOT_CONCURRENT_LIMIT",
                    "message": (
                        f"Превышен лимит параллельных запросов "
                        f"(максимум {max_concurrent} параллельно)."
                    ),
                    "retry_after_seconds": 5,
                    "scope": "process",  # in-memory per worker; not shared across processes
                    "max_concurrent": max_concurrent,
                    "current_concurrent": current,
                },
                headers={"Retry-After": "5"},
            )
        _tenant_concurrent_runs[tenant_id] = current + 1
        _run_concurrent_holders[run_id] = tenant_id
        _run_concurrent_reserved_at[run_id] = time.monotonic()
        return current + 1


def _claim_stream_slot(run_id: str) -> bool:
    """Exclusive SSE claim for run_id.

    Returns False if another stream already owns this run (prevents dual Hermes
    execution / double release races). Marks streaming so TTL reaper will not
    free the concurrent slot mid-SSE.
    """
    with _concurrent_lock:
        if run_id in _run_slot_streaming:
            return False
        _run_slot_streaming.add(run_id)
        return True


def _reap_abandoned_slots() -> int:
    """Public reaper entry (e.g. health probe for long-idle workers)."""
    with _concurrent_lock:
        return _reap_abandoned_slots_unlocked()


def _release_concurrent_slot(run_id: str) -> None:
    """Release reservation for run_id if still held (idempotent)."""
    with _concurrent_lock:
        tenant_id = _run_concurrent_holders.pop(run_id, None)
        _run_concurrent_reserved_at.pop(run_id, None)
        _run_slot_streaming.discard(run_id)
        if tenant_id is None:
            return
        _tenant_concurrent_runs[tenant_id] = max(
            0, _tenant_concurrent_runs.get(tenant_id, 1) - 1
        )


class CreateConversationRequest(BaseModel):
    title: Optional[str] = Field(default="Диалог с Hermes")


class CreateRunRequest(BaseModel):
    message: str = Field(..., max_length=4000, description="User message text")
    context_ref: CopilotContextRef = Field(default_factory=CopilotContextRef)


class NavigationAction(BaseModel):
    action: str = Field(..., description="open_screen | open_request | focus_control")
    screen_id: Optional[str] = None
    request_id: Optional[str] = None
    element_id: Optional[str] = None


ALLOWLISTED_ACTIONS = {"open_screen", "open_request", "focus_control"}


async def check_hermes_health_async() -> Dict[str, Any]:
    transport = HermesTransport()
    started = datetime.now(timezone.utc)
    key_ok = is_strong_api_key(settings.HERMES_API_KEY)
    local_ok = bool(settings.COPILOT_LOCAL_FALLBACK)
    prefer_local = bool(settings.COPILOT_PREFER_LOCAL)
    base = {
        "profile": "partsops",
        "skills": PARTSOPS_SKILLS,
        "local_fallback": local_ok,
        "prefer_local": prefer_local,
        "key_configured": key_ok,
        "hermes_url": settings.HERMES_API_URL,
    }
    if prefer_local and local_ok:
        # Operator-forced grounded path — still probe Hermes for honesty in diagnostics.
        hermes_probe: Dict[str, Any] = {"reachable": False}
        if key_ok:
            try:
                caps = await transport.capabilities()
                hermes_probe = {
                    "reachable": True,
                    "model": caps.get("model"),
                    "latency_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
                }
            except HermesTransportError as probe_exc:
                hermes_probe = {"reachable": False, "error": probe_exc.code}
        return {
            **base,
            "status": "degraded",
            "mode": "local",
            "version": "local-grounded",
            "model": "partsops-local",
            "capabilities": ["local_grounded_reply", "context_envelope", "help_corpus"],
            "hint": "COPILOT_PREFER_LOCAL=1 — ответы из ContextEnvelope/справки (Hermes sidecar не обязателен).",
            "hermes_probe": hermes_probe,
        }
    if not key_ok:
        return {
            **base,
            "status": "degraded" if local_ok else "offline",
            "mode": "local" if local_ok else "unavailable",
            "version": "unknown",
            "capabilities": ["local_grounded_reply"] if local_ok else [],
            "error": "HERMES_KEY_NOT_CONFIGURED",
            "hint": "Положите сильный ключ в .hermes_api_key или export HERMES_API_KEY, затем: hermes --profile partsops gateway run",
        }
    try:
        capabilities = await transport.capabilities()
        return {
            **base,
            "status": "online",
            "mode": "hermes",
            "version": capabilities.get("version") or capabilities.get("platform_version") or "unknown",
            "model": capabilities.get("model"),
            "capabilities": [key for key, enabled in capabilities.get("features", {}).items() if enabled is True],
            "skills": capabilities.get("skills") or PARTSOPS_SKILLS,
            "latency_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        }
    except HermesTransportError as exc:
        return {
            **base,
            "status": "degraded" if local_ok else "offline",
            "mode": "local" if local_ok else "unavailable",
            "version": "unknown",
            "capabilities": ["local_grounded_reply"] if local_ok else [],
            "error": exc.code,
            "hint": (
                "Hermes sidecar offline. Локальный grounded-режим активен."
                if local_ok
                else f"Запустите: hermes --profile partsops gateway run  # URL {settings.HERMES_API_URL}"
            ),
        }


@router.get("/health")
async def copilot_health(
    principal: CurrentPrincipal = Depends(get_current_principal)
):
    # Opportunistic reaper so long-idle workers free abandoned slots without
    # waiting for the next run create (process-local honesty).
    reaped = _reap_abandoned_slots()
    health = await check_hermes_health_async()
    if reaped:
        health = {**health, "abandoned_slots_reaped": reaped}
    return health


@router.post("/conversations")
def create_conversation(
    req: CreateConversationRequest,
    tenant_id: str = Depends(get_current_tenant),
    role: str = Depends(require_copilot_role),
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_session),
):
    now = datetime.now(timezone.utc)
    conv_id = f"conv-{uuid.uuid4().hex[:12]}"
    expires_at = now + timedelta(days=30)

    conv = CopilotConversation(
        id=conv_id,
        tenant_id=tenant_id,
        owner_fingerprint=principal.role,
        title=req.title or "Диалог с Hermes",
        created_at=now,
        updated_at=now,
        expires_at=expires_at,
    )
    session.add(conv)
    session.commit()
    session.refresh(conv)

    return {
        "id": conv.id,
        "tenant_id": conv.tenant_id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat(),
        "expires_at": conv.expires_at.isoformat(),
    }


@router.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(
    conversation_id: str,
    tenant_id: str = Depends(get_current_tenant),
    role: str = Depends(require_copilot_role),
    session: Session = Depends(get_session),
):
    conv = session.get(CopilotConversation, conversation_id)
    if not conv or conv.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Разговор не найден")

    stmt = select(CopilotMessage).where(
        CopilotMessage.conversation_id == conversation_id
    ).order_by(CopilotMessage.created_at.asc())
    
    messages = session.exec(stmt).all()
    return [
        {
            "id": msg.id,
            "role": msg.role,
            "content": msg.masked_content,
            "sources": msg.sources,
            "created_at": msg.created_at.isoformat(),
        }
        for msg in messages
    ]


@router.post("/conversations/{conversation_id}/runs")
async def create_copilot_run(
    conversation_id: str,
    req: CreateRunRequest,
    tenant_id: str = Depends(get_current_tenant),
    role: str = Depends(require_copilot_role),
    session: Session = Depends(get_session),
):
    conv = session.get(CopilotConversation, conversation_id)
    if not conv or conv.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Разговор не найден")

    # Rate limiting check (settings-driven per tenant; process-local counters)
    now = datetime.now(timezone.utc)
    recent_runs = [
        t for t in _tenant_run_history.get(tenant_id, [])
        if now - t < timedelta(minutes=1)
    ]
    if len(recent_runs) >= settings.COPILOT_RPM_LIMIT:
        retry_after = 60
        if recent_runs:
            oldest = min(recent_runs)
            elapsed = (now - oldest).total_seconds()
            retry_after = max(1, min(60, int(60 - elapsed) + 1))
        raise HTTPException(
            status_code=429,
            detail={
                "code": "COPILOT_RPM_LIMIT",
                "message": (
                    f"Превышен лимит запросов ({settings.COPILOT_RPM_LIMIT} сообщений в минуту)."
                ),
                "retry_after_seconds": retry_after,
                "scope": "process",  # not cluster-wide / multi-worker shared
            },
            headers={"Retry-After": str(retry_after)},
        )
    recent_runs.append(now)
    _tenant_run_history[tenant_id] = recent_runs

    # Daily budget check ($10 default)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    daily_cost_stmt = select(func.sum(CopilotRun.cost_usd)).where(
        CopilotRun.created_at >= start_of_day
    )
    daily_cost = session.exec(daily_cost_stmt).first() or 0.0
    if daily_cost >= settings.COPILOT_DAILY_BUDGET_USD:
        raise HTTPException(status_code=402, detail="Дневной бюджет Copilot исчерпан ($10.00). Запросы заблокированы.")

    # PII masking on user input message
    parsed_input = secure_pre_parse(req.message)
    masked_user_message = parsed_input["masked_text"]

    # Store User Message
    user_msg_id = f"msg-{uuid.uuid4().hex[:12]}"
    user_msg = CopilotMessage(
        id=user_msg_id,
        conversation_id=conversation_id,
        role="user",
        masked_content=masked_user_message,
        sources_json="[]",
        created_at=now,
    )
    session.add(user_msg)

    # Create Copilot Run entity
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    correlation_id = f"corr-{uuid.uuid4().hex[:8]}"
    
    run = CopilotRun(
        id=run_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        status="queued",
        context_ref_json=req.context_ref.model_dump_json(),
        provider="hermes",
        model="partsops",
        tokens_used=0,
        cost_usd=0.0,
        latency_ms=0,
        created_at=now,
    )
    session.add(run)

    conv.updated_at = now
    session.add(conv)
    session.commit()

    # Reserve concurrent slot at create (not only at SSE) so queued runs count
    # against the cap and close the multi-create-before-stream race.
    try:
        _reserve_concurrent_slot(
            tenant_id, run_id, int(settings.COPILOT_MAX_CONCURRENT_RUNS)
        )
    except HTTPException:
        # Roll back the just-created run so we do not leave orphan queued rows
        # that never held a slot (client will retry).
        session.delete(run)
        session.delete(user_msg)
        session.commit()
        raise

    _run_cancel_events[run_id] = asyncio.Event()

    return {
        "run_id": run_id,
        "conversation_id": conversation_id,
        "correlation_id": correlation_id,
        "status": "queued",
    }


@router.get("/runs/{run_id}/events")
async def stream_run_events(
    run_id: str,
    tenant_id: str = Depends(get_current_tenant),
    role: str = Depends(require_copilot_role),
    session: Session = Depends(get_session),
):
    """Relay one authenticated native Hermes run as a stable PartsOps SSE stream."""
    run = session.get(CopilotRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run не найден")

    conv = session.get(CopilotConversation, run.conversation_id)
    if not conv or conv.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    terminal = (run.status or "").lower()
    if terminal in {"completed", "failed", "stopped", "cancelled"}:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "COPILOT_RUN_TERMINAL",
                "message": f"Run уже завершён (status={run.status}); повторный SSE запрещён.",
                "status": run.status,
            },
        )

    # Exclusive stream: second concurrent SSE must not double-execute Hermes.
    if not _claim_stream_slot(run_id):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "COPILOT_STREAM_IN_PROGRESS",
                "message": "SSE-поток для этого run уже активен.",
                "run_id": run_id,
            },
        )

    def encode(payload: Dict[str, Any]) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    async def event_generator() -> AsyncGenerator[str, None]:
        # Concurrent slot reserved at create; stream claim already exclusive above.
        cancel_event = _run_cancel_events.setdefault(run_id, asyncio.Event())
        transport = HermesTransport()
        sequence = 0
        assistant_text = ""
        terminal = False
        start_time = datetime.now(timezone.utc)

        def event(type_name: str, **payload: Any) -> Dict[str, Any]:
            nonlocal sequence
            sequence += 1
            return {
                "type": type_name,
                "run_id": run_id,
                "correlation_id": run.correlation_id,
                "sequence": sequence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **payload,
            }

        try:
            yield encode(event("run.started"))

            history_stmt = select(CopilotMessage).where(
                CopilotMessage.conversation_id == run.conversation_id,
            ).order_by(CopilotMessage.created_at.asc())
            history = session.exec(history_stmt).all()
            current_message = next((msg.masked_content for msg in reversed(history) if msg.role == "user"), "")

            context_ref = CopilotContextRef.model_validate_json(run.context_ref_json)
            envelope = build_context_envelope(
                session=session,
                tenant_id=tenant_id,
                context_ref=context_ref,
                user_role=role,
                query=current_message,
            )

            history_for_model = history[:-1] if history and history[-1].role == "user" else history
            conversation_history = []
            for msg in history_for_model[-6:]:
                if msg.role not in {"user", "assistant"} or not msg.masked_content:
                    continue
                # Cap history turns so Hermes prompt stays within small token budget.
                content = msg.masked_content
                if len(content) > 600:
                    content = content[:600].rstrip() + "…"
                conversation_history.append({"role": msg.role, "content": content})
            instructions = build_hermes_instructions(envelope)
            # Also keep user message bounded (API already max_length=4000, but trim for speed).
            if current_message and len(current_message) > 1500:
                current_message = current_message[:1500].rstrip() + "…"

            async def stream_local_fallback(reason_code: str) -> AsyncGenerator[str, None]:
                """Grounded local answer when Hermes is missing/offline."""
                nonlocal assistant_text, terminal
                yield encode(event(
                    "run.progress",
                    label="Локальный grounded-режим",
                    detail=f"Hermes недоступен ({reason_code}) — отвечаем по ContextEnvelope",
                ))
                answer, valid_sources = await asyncio.to_thread(
                    build_local_reply,
                    envelope=envelope,
                    user_message=current_message,
                    # None → honor COPILOT_LOCAL_LLM env (default on; set 0 for pure grounded)
                    prefer_llm=None,
                )
                assistant_text = answer
                for piece in chunk_text(answer, size=64):
                    if cancel_event.is_set():
                        run.status = "stopped"
                        run.error_code = "CANCELLED"
                        session.add(run)
                        session.commit()
                        yield encode(event("run.stopped", code="CANCELLED", retryable=True))
                        terminal = True
                        return
                    yield encode(event("assistant.delta", text=piece))
                    await asyncio.sleep(0)  # let event loop flush SSE chunks

                for source in valid_sources:
                    yield encode(event(
                        "source",
                        source_id=source["source_id"],
                        title=source.get("title") or source["source_id"],
                    ))
                for action in envelope.allowed_user_actions:
                    if action.get("action") in ALLOWLISTED_ACTIONS and (
                        action.get("screen_id") in {None, envelope.screen_id}
                        or action.get("request_id") == context_ref.selected_request_id
                    ):
                        yield encode(event("navigation.action", action=action))

                if assistant_text:
                    session.add(CopilotMessage(
                        id=f"msg-{uuid.uuid4().hex[:12]}",
                        conversation_id=run.conversation_id,
                        role="assistant",
                        masked_content=assistant_text,
                        sources_json=json.dumps(valid_sources, ensure_ascii=False),
                        created_at=datetime.now(timezone.utc),
                    ))
                run.status = "completed"
                run.provider = "local_fallback"
                run.model = "partsops-local"
                run.error_code = None
                run.tokens_used = 0
                run.cost_usd = 0.0
                run.latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                session.add(run)
                session.commit()
                yield encode(event(
                    "run.completed",
                    usage={
                        "tokens": 0,
                        "cost_usd": 0.0,
                        "latency_ms": run.latency_ms,
                        "mode": "local_fallback",
                        "hermes_error": reason_code,
                    },
                ))
                terminal = True

            use_local = False
            local_reason = ""
            if settings.COPILOT_PREFER_LOCAL and settings.COPILOT_LOCAL_FALLBACK:
                use_local = True
                local_reason = "COPILOT_PREFER_LOCAL"
            elif not is_strong_api_key(settings.HERMES_API_KEY) and settings.COPILOT_LOCAL_FALLBACK:
                use_local = True
                local_reason = "HERMES_KEY_NOT_CONFIGURED"
            else:
                try:
                    run_lock = _run_locks.setdefault(run_id, asyncio.Lock())
                    async with run_lock:
                        if not run.hermes_run_id:
                            try:
                                upstream = await asyncio.wait_for(
                                    transport.start_run(
                                        message=current_message,
                                        instructions=instructions,
                                        conversation_history=conversation_history,
                                        session_id=conv.hermes_session_id,
                                    ),
                                    timeout=settings.COPILOT_HERMES_START_TIMEOUT_SECONDS,
                                )
                            except asyncio.TimeoutError as te:
                                raise HermesTransportError(
                                    f"Hermes start exceeded {settings.COPILOT_HERMES_START_TIMEOUT_SECONDS}s",
                                    code="HERMES_START_TIMEOUT",
                                    retryable=True,
                                ) from te
                            run.hermes_run_id = str(upstream["run_id"])
                            conv.hermes_session_id = str(upstream.get("session_id") or upstream["run_id"])
                            run.provider = "hermes"
                            run.model = str(upstream.get("model") or "partsops")
                            run.status = "running"
                            _run_upstream_ids[run_id] = run.hermes_run_id
                            session.add(conv)
                            session.add(run)
                            session.commit()
                        else:
                            _run_upstream_ids[run_id] = run.hermes_run_id
                except HermesTransportError as start_exc:
                    if settings.COPILOT_LOCAL_FALLBACK and start_exc.code in _LOCAL_FALLBACK_CODES:
                        use_local = True
                        local_reason = start_exc.code
                    else:
                        raise

            if use_local:
                async for frame in stream_local_fallback(local_reason):
                    yield frame
                return

            async for upstream_event in transport.stream_run(_run_upstream_ids[run_id]):
                if cancel_event.is_set():
                    try:
                        await transport.stop_run(_run_upstream_ids[run_id])
                    except HermesTransportError:
                        pass
                    run.status = "stopped"
                    run.error_code = "CANCELLED"
                    session.add(run)
                    session.commit()
                    yield encode(event("run.stopped", code="CANCELLED", retryable=True))
                    terminal = True
                    return

                upstream_type = upstream_event.get("event") or upstream_event.get("type")
                if upstream_type == "message.delta":
                    delta = str(upstream_event.get("delta") or upstream_event.get("text") or "")
                    if delta:
                        assistant_text += delta
                        yield encode(event("assistant.delta", text=delta))
                elif upstream_type in {"tool.started", "tool.completed", "reasoning.available", "subagent.start", "subagent.complete"}:
                    yield encode(event("run.progress", label="Hermes проверяет read-only контекст"))
                elif upstream_type == "approval.request":
                    try:
                        await transport.stop_run(_run_upstream_ids[run_id])
                    except HermesTransportError:
                        pass
                    run.status = "failed"
                    run.error_code = "READ_ONLY_POLICY_VIOLATION"
                    session.add(run)
                    session.commit()
                    yield encode(event("run.failed", code="READ_ONLY_POLICY_VIOLATION", message="Hermes запросил запрещённое действие.", retryable=False))
                    terminal = True
                    return
                elif upstream_type in {"run.cancelled", "run.stopped"}:
                    run.status = "stopped"
                    run.error_code = "CANCELLED"
                    session.add(run)
                    session.commit()
                    yield encode(event("run.stopped", code="CANCELLED", retryable=True))
                    terminal = True
                    return
                elif upstream_type == "run.failed":
                    error_code = str(upstream_event.get("code") or "HERMES_RUN_FAILED")
                    if settings.COPILOT_LOCAL_FALLBACK:
                        async for frame in stream_local_fallback(error_code):
                            yield frame
                        return
                    run.status = "failed"
                    run.error_code = error_code
                    session.add(run)
                    session.commit()
                    yield encode(event("run.failed", code=error_code, message="Hermes не смог завершить проверку.", retryable=False))
                    terminal = True
                    return
                elif upstream_type == "run.completed":
                    output = upstream_event.get("output") or upstream_event.get("response") or ""
                    if not assistant_text and output:
                        assistant_text = str(output)
                    usage = upstream_event.get("usage") or {}
                    valid_sources = [
                        src for src in validate_and_filter_sources(envelope.available_help_sources, assistant_text)
                        if get_help_source_by_id(src.get("source_id", "")) is not None
                    ]
                    for source in valid_sources:
                        yield encode(event("source", source_id=source["source_id"], title=source["title"]))
                    for action in envelope.allowed_user_actions:
                        if action.get("action") in ALLOWLISTED_ACTIONS and (
                            action.get("screen_id") in {None, envelope.screen_id}
                            or action.get("request_id") == context_ref.selected_request_id
                        ):
                            yield encode(event("navigation.action", action=action))

                    if assistant_text:
                        session.add(CopilotMessage(
                            id=f"msg-{uuid.uuid4().hex[:12]}",
                            conversation_id=run.conversation_id,
                            role="assistant",
                            masked_content=assistant_text,
                            sources_json=json.dumps(valid_sources, ensure_ascii=False),
                            created_at=datetime.now(timezone.utc),
                        ))
                    usage_tokens = usage.get("total_tokens") or usage.get("tokens") or 0
                    run.status = "completed"
                    run.tokens_used = int(usage_tokens or 0)
                    run.cost_usd = float(usage.get("cost_usd") or 0.0)
                    run.latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                    session.add(run)
                    session.commit()
                    yield encode(event("run.completed", usage={"tokens": run.tokens_used, "cost_usd": run.cost_usd, "latency_ms": run.latency_ms}))
                    terminal = True
                    return

            if not terminal:
                if settings.COPILOT_LOCAL_FALLBACK:
                    async for frame in stream_local_fallback("HERMES_UPSTREAM_EOF"):
                        yield frame
                    return
                run.status = "failed"
                run.error_code = "HERMES_UPSTREAM_EOF"
                session.add(run)
                session.commit()
                yield encode(event("run.failed", code="HERMES_UPSTREAM_EOF", message="Поток Hermes завершился без terminal-события.", retryable=True))

        except HermesTransportError as exc:
            if settings.COPILOT_LOCAL_FALLBACK and exc.code in _LOCAL_FALLBACK_CODES:
                # Rebuild minimal envelope path already completed above if we got here
                # mid-stream — re-enter local answer using last known message.
                try:
                    history_stmt = select(CopilotMessage).where(
                        CopilotMessage.conversation_id == run.conversation_id,
                    ).order_by(CopilotMessage.created_at.asc())
                    history = session.exec(history_stmt).all()
                    current_message = next((msg.masked_content for msg in reversed(history) if msg.role == "user"), "")
                    context_ref = CopilotContextRef.model_validate_json(run.context_ref_json)
                    envelope = build_context_envelope(
                        session=session,
                        tenant_id=tenant_id,
                        context_ref=context_ref,
                        user_role=role,
                        query=current_message,
                    )
                    answer, valid_sources = build_local_reply(
                        envelope=envelope,
                        user_message=current_message,
                        prefer_llm=None,
                    )
                    yield encode({
                        "type": "run.progress",
                        "run_id": run_id,
                        "correlation_id": run.correlation_id,
                        "sequence": sequence + 1,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "label": "Локальный grounded-режим",
                        "detail": f"Hermes error {exc.code}",
                    })
                    sequence += 1
                    for piece in chunk_text(answer, size=64):
                        sequence += 1
                        yield encode({
                            "type": "assistant.delta",
                            "run_id": run_id,
                            "correlation_id": run.correlation_id,
                            "sequence": sequence,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "text": piece,
                        })
                    for source in valid_sources:
                        sequence += 1
                        yield encode({
                            "type": "source",
                            "run_id": run_id,
                            "correlation_id": run.correlation_id,
                            "sequence": sequence,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "source_id": source["source_id"],
                            "title": source.get("title") or source["source_id"],
                        })
                    session.add(CopilotMessage(
                        id=f"msg-{uuid.uuid4().hex[:12]}",
                        conversation_id=run.conversation_id,
                        role="assistant",
                        masked_content=answer,
                        sources_json=json.dumps(valid_sources, ensure_ascii=False),
                        created_at=datetime.now(timezone.utc),
                    ))
                    run.status = "completed"
                    run.provider = "local_fallback"
                    run.model = "partsops-local"
                    run.error_code = None
                    run.latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                    session.add(run)
                    session.commit()
                    sequence += 1
                    yield encode({
                        "type": "run.completed",
                        "run_id": run_id,
                        "correlation_id": run.correlation_id,
                        "sequence": sequence,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "usage": {
                            "tokens": 0,
                            "cost_usd": 0.0,
                            "latency_ms": run.latency_ms,
                            "mode": "local_fallback",
                            "hermes_error": exc.code,
                        },
                    })
                except Exception:
                    run.status = "failed"
                    run.error_code = exc.code
                    run.latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                    session.add(run)
                    session.commit()
                    yield encode(event("run.failed", code=exc.code, message=str(exc), retryable=exc.retryable))
            else:
                run.status = "failed"
                run.error_code = exc.code
                run.latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                session.add(run)
                session.commit()
                yield encode(event("run.failed", code=exc.code, message=str(exc), retryable=exc.retryable))
        except asyncio.CancelledError:
            cancel_event.set()
            raise
        except Exception:
            run.status = "failed"
            run.error_code = "COPILOT_INTERNAL_ERROR"
            session.add(run)
            session.commit()
            yield encode(event("run.failed", code="COPILOT_INTERNAL_ERROR", message="Внутренняя ошибка Copilot.", retryable=True))
        finally:
            # Terminal-before-release: a late second SSE client must see
            # COPILOT_RUN_TERMINAL, not re-claim the slot and dual-execute Hermes
            # when the first stream ended without a terminal status write.
            try:
                session.refresh(run)
                st = (run.status or "").lower()
                if st not in {"completed", "failed", "stopped", "cancelled"}:
                    cancelled = cancel_event.is_set()
                    run.status = "stopped" if cancelled else "failed"
                    run.error_code = run.error_code or (
                        "CANCELLED" if cancelled else "COPILOT_STREAM_ENDED"
                    )
                    run.latency_ms = int(
                        (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                    )
                    session.add(run)
                    session.commit()
            except Exception:
                pass
            _release_concurrent_slot(run_id)
            _run_cancel_events.pop(run_id, None)
            _run_upstream_ids.pop(run_id, None)
            _run_locks.pop(run_id, None)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/runs/{run_id}/stop")
async def stop_copilot_run(
    run_id: str,
    tenant_id: str = Depends(get_current_tenant),
    role: str = Depends(require_copilot_role),
    session: Session = Depends(get_session),
):
    run = session.get(CopilotRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run не найден")

    conv = session.get(CopilotConversation, run.conversation_id)
    if not conv or conv.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    cancel_evt = _run_cancel_events.get(run_id)
    if cancel_evt:
        cancel_evt.set()

    upstream_id = run.hermes_run_id or _run_upstream_ids.get(run_id)
    if upstream_id:
        try:
            await HermesTransport().stop_run(upstream_id)
        except HermesTransportError as exc:
            run.error_code = exc.code

    run.status = "stopped"
    session.add(run)
    session.commit()

    # Release slot if client stops a queued run without (or before) SSE finally.
    _release_concurrent_slot(run_id)
    _run_cancel_events.pop(run_id, None)

    return {"status": "stopped", "run_id": run_id}


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    tenant_id: str = Depends(get_current_tenant),
    role: str = Depends(require_copilot_role),
    session: Session = Depends(get_session),
):
    conv = session.get(CopilotConversation, conversation_id)
    if not conv or conv.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Разговор не найден")

    # Delete messages
    stmt_msg = select(CopilotMessage).where(CopilotMessage.conversation_id == conversation_id)
    messages = session.exec(stmt_msg).all()
    for m in messages:
        session.delete(m)

    # Delete runs
    stmt_runs = select(CopilotRun).where(CopilotRun.conversation_id == conversation_id)
    runs = session.exec(stmt_runs).all()
    for r in runs:
        session.delete(r)

    session.delete(conv)
    session.commit()

    return {"status": "deleted", "id": conversation_id}


@router.get("/sources/{source_id}")
def get_help_source(
    source_id: str,
    tenant_id: str = Depends(get_current_tenant),
    role: str = Depends(require_copilot_role),
):
    source = get_help_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Статья справки не найдена")
    return source
