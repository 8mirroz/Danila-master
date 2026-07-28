"""
PartsOps AI Manager v3 — FastAPI Copilot Router (Hermes Integration).
Implements Hermes Sessions/Runs/SSE API broker, RBAC, PII masking, rate limits, and real Hermes CLI/Server execution.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Optional, Dict, Any, List
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
    validate_and_filter_sources,
)
from services.help_service import get_help_source_by_id
from services.hermes_transport import HermesTransport, HermesTransportError

router = APIRouter(prefix="/api/copilot", tags=["Copilot"])

require_copilot_role = RoleChecker(allowed_roles=["admin", "manager"])
PARTSOPS_SKILLS = ["partsops-navigation", "partsops-request-explainer", "partsops-troubleshooting"]

# Global run memory lock for active runs and native upstream identifiers.
_active_runs: Dict[str, asyncio.Task] = {}
_run_cancel_events: Dict[str, asyncio.Event] = {}
_run_upstream_ids: Dict[str, str] = {}
_run_locks: Dict[str, asyncio.Lock] = {}

# Tenant rate limit counters (minute window)
_tenant_run_history: Dict[str, List[datetime]] = {}
_tenant_concurrent_runs: Dict[str, int] = {}


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
    try:
        capabilities = await transport.capabilities()
        return {
            "status": "online",
            "profile": "partsops",
            "version": capabilities.get("version") or capabilities.get("platform_version") or "unknown",
            "model": capabilities.get("model"),
            "capabilities": [key for key, enabled in capabilities.get("features", {}).items() if enabled is True],
            "skills": capabilities.get("skills") or PARTSOPS_SKILLS,
            "latency_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        }
    except HermesTransportError as exc:
        return {
            "status": "degraded" if exc.code == "HERMES_KEY_NOT_CONFIGURED" else "offline",
            "profile": "partsops",
            "version": "unknown",
            "capabilities": [],
            "skills": PARTSOPS_SKILLS,
            "error": exc.code,
        }


@router.get("/health")
async def copilot_health(
    principal: CurrentPrincipal = Depends(get_current_principal)
):
    health = await check_hermes_health_async()
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

    # Rate limiting check (settings-driven per tenant)
    now = datetime.now(timezone.utc)
    recent_runs = [
        t for t in _tenant_run_history.get(tenant_id, [])
        if now - t < timedelta(minutes=1)
    ]
    if len(recent_runs) >= settings.COPILOT_RPM_LIMIT:
        raise HTTPException(status_code=429, detail=f"Превышен лимит запросов ({settings.COPILOT_RPM_LIMIT} сообщений в минуту).")
    recent_runs.append(now)
    _tenant_run_history[tenant_id] = recent_runs

    # Concurrency check (settings-driven parallel runs per tenant)
    current_concurrent = _tenant_concurrent_runs.get(tenant_id, 0)
    if current_concurrent >= settings.COPILOT_MAX_CONCURRENT_RUNS:
        raise HTTPException(status_code=429, detail=f"Превышен лимит параллельных запросов (максимум {settings.COPILOT_MAX_CONCURRENT_RUNS} параллельно).")

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

    def encode(payload: Dict[str, Any]) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    async def event_generator() -> AsyncGenerator[str, None]:
        _tenant_concurrent_runs[tenant_id] = _tenant_concurrent_runs.get(tenant_id, 0) + 1
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

            context_ref = CopilotContextRef.model_validate_json(run.context_ref_json)
            envelope = build_context_envelope(
                session=session,
                tenant_id=tenant_id,
                context_ref=context_ref,
                user_role=role,
            )

            history_stmt = select(CopilotMessage).where(
                CopilotMessage.conversation_id == run.conversation_id,
            ).order_by(CopilotMessage.created_at.asc())
            history = session.exec(history_stmt).all()
            current_message = next((msg.masked_content for msg in reversed(history) if msg.role == "user"), "")
            history_for_model = history[:-1] if history and history[-1].role == "user" else history
            conversation_history = [
                {"role": msg.role, "content": msg.masked_content}
                for msg in history_for_model[-12:]
                if msg.role in {"user", "assistant"} and msg.masked_content
            ]
            instructions = (
                "Ты Hermes в PartsOps Admin Cockpit. Отвечай только на русском языке и только на основе "
                "переданного ContextEnvelope и подтверждённых help sources. Режим строго READ-ONLY: "
                "не вызывай terminal, file, web, MCP, delegation, ERP, pricing, supplier, purchasing или "
                "любые инструменты изменения состояния. Не обещай выполнить действие. Если данных недостаточно, "
                "скажи, что не можешь подтвердить. Навигацию предлагай только через allowlisted action objects.\n\n"
                f"ContextEnvelope: {envelope.model_dump_json()}"
            )

            run_lock = _run_locks.setdefault(run_id, asyncio.Lock())
            async with run_lock:
                if not run.hermes_run_id:
                    upstream = await transport.start_run(
                        message=current_message,
                        instructions=instructions,
                        conversation_history=conversation_history,
                        session_id=conv.hermes_session_id,
                    )
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
                run.status = "failed"
                run.error_code = "HERMES_UPSTREAM_EOF"
                session.add(run)
                session.commit()
                yield encode(event("run.failed", code="HERMES_UPSTREAM_EOF", message="Поток Hermes завершился без terminal-события.", retryable=True))

        except HermesTransportError as exc:
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
            _tenant_concurrent_runs[tenant_id] = max(0, _tenant_concurrent_runs.get(tenant_id, 1) - 1)
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
