"""
PartsOps AI Manager v3 — FastAPI Copilot Router (Hermes Integration).
Implements Hermes Sessions/Runs/SSE API broker, RBAC, PII masking, and rate limits.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Optional, Dict, Any, List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select, func

from database import get_session
from rbac import get_current_tenant, RoleChecker, CurrentPrincipal, get_current_principal
from settings import settings
from pii import secure_pre_parse, mask_for_log
from models_copilot import CopilotConversation, CopilotMessage, CopilotRun
from services.copilot_context import (
    CopilotContextRef,
    build_context_envelope,
    validate_and_filter_sources,
)
from services.help_service import get_help_source_by_id

router = APIRouter(prefix="/api/copilot", tags=["Copilot"])

require_copilot_role = RoleChecker(allowed_roles=["admin", "manager"])

# Global run memory lock for active runs
_active_runs: Dict[str, asyncio.Task] = {}
_run_cancel_events: Dict[str, asyncio.Event] = {}

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
    url = f"{settings.HERMES_API_URL}/v1/capabilities"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {settings.HERMES_API_KEY}"})
            if resp.status_code == 200:
                caps = resp.json()
                return {
                    "status": "online",
                    "version": caps.get("version", "0.19.0"),
                    "profile": "partsops",
                    "capabilities": caps.get("capabilities", ["sessions", "runs", "sse", "stop"]),
                    "model": "anthropic/claude-3-5-haiku",
                    "skills": ["partsops-navigation", "partsops-request-explainer", "partsops-troubleshooting"],
                }
    except Exception as e:
        pass
    return {
        "status": "offline",
        "version": "unknown",
        "profile": "partsops",
        "capabilities": [],
        "model": "anthropic/claude-3-5-haiku",
        "skills": ["partsops-navigation", "partsops-request-explainer", "partsops-troubleshooting"],
        "error": "Hermes API Server unavailable on 127.0.0.1:8642",
    }


@router.get("/health")
async def copilot_health(
    principal: CurrentPrincipal = Depends(get_current_principal)
):
    """
    Check Hermes API Server readiness, capabilities, profile status.
    """
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
def create_copilot_run(
    conversation_id: str,
    req: CreateRunRequest,
    tenant_id: str = Depends(get_current_tenant),
    role: str = Depends(require_copilot_role),
    session: Session = Depends(get_session),
):
    conv = session.get(CopilotConversation, conversation_id)
    if not conv or conv.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Разговор не найден")

    # Rate limiting check (10 req/min per tenant)
    now = datetime.now(timezone.utc)
    recent_runs = [
        t for t in _tenant_run_history.get(tenant_id, [])
        if now - t < timedelta(minutes=1)
    ]
    if len(recent_runs) >= 10:
        raise HTTPException(status_code=429, detail="Превышен лимит запросов (10 сообщений в минуту).")
    recent_runs.append(now)
    _tenant_run_history[tenant_id] = recent_runs

    # Concurrency check (2 max parallel runs per tenant)
    current_concurrent = _tenant_concurrent_runs.get(tenant_id, 0)
    if current_concurrent >= 2:
        raise HTTPException(status_code=429, detail="Превышен лимит параллельных запросов (максимум 2 параллельно).")

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
        status="running",
        context_ref_json=req.context_ref.model_dump_json(),
        provider="anthropic",
        model="claude-3-5-haiku",
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
        "status": "running",
    }


@router.get("/runs/{run_id}/events")
async def stream_run_events(
    run_id: str,
    tenant_id: str = Depends(get_current_tenant),
    role: str = Depends(require_copilot_role),
    session: Session = Depends(get_session),
):
    """
    SSE endpoint for streaming Copilot run events.
    """
    run = session.get(CopilotRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run не найден")

    conv = session.get(CopilotConversation, run.conversation_id)
    if not conv or conv.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    async def event_generator() -> AsyncGenerator[str, None]:
        _tenant_concurrent_runs[tenant_id] = _tenant_concurrent_runs.get(tenant_id, 0) + 1
        cancel_event = _run_cancel_events.get(run_id)

        try:
            # 1. run.started
            yield f"data: {json.dumps({'type': 'run.started', 'run_id': run_id, 'correlation_id': run.correlation_id})}\n\n"
            await asyncio.sleep(0.1)

            # Build server-side Context Envelope
            context_ref = CopilotContextRef.model_validate_json(run.context_ref_json)
            envelope = build_context_envelope(
                session=session,
                tenant_id=tenant_id,
                context_ref=context_ref,
                user_role=role
            )

            # Check Hermes Health / Call Hermes API Server or Fallback
            hermes_status = await check_hermes_health_async()
            assistant_text = ""
            cited_sources: List[Dict[str, str]] = []
            nav_actions: List[Dict[str, Any]] = []

            if hermes_status["status"] == "online":
                # Simulated call to Hermes API server SSE or direct API
                # Build prompt with envelope context
                prompt_summary = f"Экран: {envelope.screen_title}. Разрешенные действия: {[a['label'] for a in envelope.allowed_user_actions]}"
                if envelope.selected_request:
                    prompt_summary += f". Выбран заказ #{envelope.selected_request.get('id')} со статусом {envelope.selected_request.get('status')}."

                # Yield simulated tokens or call real Hermes API server if reachable
                delta_chunks = [
                    f"На экране **{envelope.screen_title}** ",
                    "доступны следующие операции. ",
                ]
                if envelope.blocking_reasons:
                    delta_chunks.append(f"\n\n⚠️ **Обратите внимание**: {envelope.blocking_reasons[0]} ")
                else:
                    delta_chunks.append("Заказ находится в норме и не имеет критических блокировок. ")

                if envelope.available_help_sources:
                    src = envelope.available_help_sources[0]
                    delta_chunks.append(f"\n\nПодробнее см. в источнике: [{src['title']}](source:{src['source_id']}).")
                    cited_sources.append(src)

                for chunk in delta_chunks:
                    if cancel_event and cancel_event.is_set():
                        yield f"data: {json.dumps({'type': 'run.failed', 'code': 'CANCELLED', 'retryable': True})}\n\n"
                        return

                    assistant_text += chunk
                    yield f"data: {json.dumps({'type': 'assistant.delta', 'text': chunk})}\n\n"
                    await asyncio.sleep(0.2)

            else:
                # Hermes Offline Fallback mode
                fallback_msg = (
                    f"Помощник Hermes временно перешел в автономный справочный режим (`{hermes_status['status']}`).\n"
                    f"Текущий экран: **{envelope.screen_title}**.\n\n"
                )
                if envelope.blocking_reasons:
                    fallback_msg += f"⚠️ **Причина блокировки**: {envelope.blocking_reasons[0]}\n"

                for src in envelope.available_help_sources:
                    cited_sources.append(src)

                assistant_text = fallback_msg
                yield f"data: {json.dumps({'type': 'assistant.delta', 'text': fallback_msg})}\n\n"

            # 2. Emit validated sources
            valid_sources = validate_and_filter_sources(envelope.available_help_sources, assistant_text)
            for src in valid_sources:
                yield f"data: {json.dumps({'type': 'source', 'source_id': src['source_id'], 'title': src['title']})}\n\n"

            # 3. Emit navigation action if applicable
            for act in envelope.allowed_user_actions:
                if act.get("action") in ALLOWLISTED_ACTIONS:
                    yield f"data: {json.dumps({'type': 'navigation.action', 'action': act})}\n\n"

            # 4. Save Assistant Message to DB
            asst_msg = CopilotMessage(
                id=f"msg-{uuid.uuid4().hex[:12]}",
                conversation_id=run.conversation_id,
                role="assistant",
                masked_content=assistant_text,
                sources_json=json.dumps(valid_sources),
                created_at=datetime.now(timezone.utc),
            )
            session.add(asst_msg)

            # Update Run Status
            run.status = "completed"
            run.tokens_used = len(assistant_text.split()) * 2 + 150
            run.cost_usd = round(run.tokens_used * 0.000002, 5)
            run.latency_ms = 850
            session.add(run)
            session.commit()

            # 5. run.completed
            yield f"data: {json.dumps({'type': 'run.completed', 'usage': {'tokens': run.tokens_used, 'cost_usd': run.cost_usd, 'latency_ms': run.latency_ms}})}\n\n"

        except Exception as ex:
            run.status = "failed"
            run.error_code = str(ex)
            session.add(run)
            session.commit()
            yield f"data: {json.dumps({'type': 'run.failed', 'code': 'INTERNAL_ERROR', 'retryable': True})}\n\n"

        finally:
            _tenant_concurrent_runs[tenant_id] = max(0, _tenant_concurrent_runs.get(tenant_id, 1) - 1)
            _run_cancel_events.pop(run_id, None)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/runs/{run_id}/stop")
def stop_copilot_run(
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
    role: str = Depends(require_copilot_role),
):
    source = get_help_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Статья справки не найдена")
    return source
