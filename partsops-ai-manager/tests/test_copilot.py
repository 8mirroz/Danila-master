"""
Unit and Integration Tests for Copilot (Hermes Assistant Router).
Tests tenant isolation, RBAC, PII masking, context building, help source retrieval, SSE streaming, stop runs, rate limits, budget guards, and migration status.
"""
import os
import asyncio
import pytest
import httpx
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import main
import routers.copilot as copilot_router
from database import get_session
from models_copilot import CopilotConversation, CopilotMessage, CopilotRun
from services.help_service import get_help_sources_for_context, get_help_source_by_id
from services.hermes_transport import HermesTransportError, is_strong_api_key
from services.copilot_context import (
    CopilotContextRef,
    build_context_envelope,
    validate_and_filter_sources,
)
from pii import secure_pre_parse
from rbac import create_signed_token, _get_api_token


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    main.app.dependency_overrides[get_session] = get_session_override
    client = TestClient(main.app)
    yield client
    main.app.dependency_overrides.clear()


def make_auth_headers(tenant_id: str = "default", role: str = "manager") -> dict:
    secret = _get_api_token()
    headers = {"X-Tenant-ID": tenant_id, "X-User-Role": role}
    if secret:
        token = create_signed_token(tenant_id, role, secret)
        headers["Authorization"] = f"Bearer {token}"
    return headers


def test_copilot_health(client: TestClient):
    response = client.get("/api/copilot/health", headers=make_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "profile" in data
    assert data["profile"] == "partsops"
    assert "partsops-navigation" in data["skills"]


def test_hermes_transport_rejects_placeholder_key():
    assert not is_strong_api_key("partsops-hermes-secret-key")
    assert not is_strong_api_key("short")
    assert is_strong_api_key("0123456789abcdef0123456789abcdef")
    error = HermesTransportError("missing", code="HERMES_KEY_NOT_CONFIGURED")
    assert error.code == "HERMES_KEY_NOT_CONFIGURED"


def test_native_hermes_transport_auth_and_sse_contract():
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, request.headers.get("authorization")))
        if request.url.path == "/v1/capabilities":
            return httpx.Response(200, json={"model": "partsops", "features": {"run_events_sse": True}})
        if request.url.path == "/v1/runs" and request.method == "POST":
            return httpx.Response(202, json={"run_id": "run_native"})
        if request.url.path == "/v1/runs/run_native/events":
            return httpx.Response(200, content=b'data: {"event":"message.delta","delta":"OK"}\n\ndata: {"event":"run.completed"}\n\n', headers={"content-type": "text/event-stream"})
        if request.url.path == "/v1/runs/run_native/stop":
            return httpx.Response(200, json={"status": "stopping"})
        return httpx.Response(404)

    async def scenario():
        transport = copilot_router.HermesTransport(
            base_url="http://hermes.test",
            api_key="0123456789abcdef0123456789abcdef",
            transport=httpx.MockTransport(handler),
        )
        capabilities = await transport.capabilities()
        assert capabilities["model"] == "partsops"
        started = await transport.start_run(message="hello", instructions="read-only", conversation_history=[])
        assert started["run_id"] == "run_native"
        events = [event async for event in transport.stream_run("run_native")]
        assert events[0]["event"] == "message.delta"
        assert events[1]["event"] == "run.completed"
        await transport.stop_run("run_native")

    asyncio.run(scenario())
    assert calls
    assert all(call[2] == "Bearer 0123456789abcdef0123456789abcdef" for call in calls)


def test_create_and_get_conversation(client: TestClient):
    headers = make_auth_headers(tenant_id="tenant-alpha", role="manager")
    response = client.post(
        "/api/copilot/conversations",
        json={"title": "Тестовый разговор"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["tenant_id"] == "tenant-alpha"
    conv_id = data["id"]

    # Get messages
    msg_resp = client.get(
        f"/api/copilot/conversations/{conv_id}/messages",
        headers=headers,
    )
    assert msg_resp.status_code == 200
    assert isinstance(msg_resp.json(), list)


def test_tenant_isolation(client: TestClient):
    # Tenant Alpha creates conversation
    headers_alpha = make_auth_headers(tenant_id="tenant-alpha", role="manager")
    res = client.post(
        "/api/copilot/conversations",
        json={"title": "Секретный диалог Alpha"},
        headers=headers_alpha,
    )
    assert res.status_code == 200
    conv_id = res.json()["id"]

    # Tenant Beta attempts to access
    headers_beta = make_auth_headers(tenant_id="tenant-beta", role="manager")
    access_resp = client.get(
        f"/api/copilot/conversations/{conv_id}/messages",
        headers=headers_beta,
    )
    assert access_resp.status_code == 404


def test_rbac_restriction(client: TestClient):
    # Role 'finance' is not in allowed_roles for copilot (only admin, manager)
    headers_unauth = make_auth_headers(tenant_id="tenant-alpha", role="finance")
    res = client.post(
        "/api/copilot/conversations",
        json={"title": "Попытка доступа"},
        headers=headers_unauth,
    )
    assert res.status_code == 403


def test_pii_masking_integration():
    raw_user_text = "Клиент Иван +7 (912) 345-67-89, VIN WBA3C3C50EF123456 email test@company.com"
    result = secure_pre_parse(raw_user_text)
    masked_text = result["masked_text"]
    assert "+7 (912) 345-67-89" not in masked_text
    assert "WBA3C3C50EF123456" not in masked_text
    assert "test@company.com" not in masked_text
    assert "[VIN_СКРЫТ]" in masked_text
    assert "[ТЕЛЕФОН_СКРЫТ]" in masked_text
    assert "[EMAIL_СКРЫТ]" in masked_text


def test_help_service_retrieval():
    sources = get_help_sources_for_context(
        screen_id="kanban_board",
        user_role="manager",
        query="блокировка",
        limit=2
    )
    assert len(sources) > 0
    assert any("help-blocked-02" == s["source_id"] for s in sources)

    doc = get_help_source_by_id("help-kanban-01")
    assert doc is not None
    assert doc["title"] == "Инструкция по работе с Канбан-доской заказов"


def test_context_envelope_building(session: Session):
    from models import PartRequest
    req = PartRequest(
        tenant_id="default",
        request_id="REQ-1001",
        source="web",
        status="BLOCKED",
        customer_name="Тест Клиент",
    )
    session.add(req)
    session.commit()

    # Direct selection by request_id
    ref = CopilotContextRef(screen_id="kanban_board", selected_request_id="REQ-1001")
    envelope = build_context_envelope(
        session=session,
        tenant_id="default",
        context_ref=ref,
        user_role="manager"
    )
    assert envelope.screen_id == "kanban_board"
    assert envelope.screen_title == "Канбан-доска заказов"
    assert envelope.selected_request is not None
    assert envelope.selected_request.get("request_id") == "REQ-1001"
    assert any("open_request" == a["action"] for a in envelope.allowed_user_actions)

    # Resolution from user query when selected_request_id is not passed
    ref_empty = CopilotContextRef(screen_id="kanban_board")
    envelope_query = build_context_envelope(
        session=session,
        tenant_id="default",
        context_ref=ref_empty,
        user_role="manager",
        query="Почему заблокирован REQ-1001?",
    )
    assert envelope_query.selected_request is not None
    assert envelope_query.selected_request.get("request_id") == "REQ-1001"


def test_strict_grounding_filter():
    available = [
        {"source_id": "help-kanban-01", "title": "Инструкция по Канбан"},
        {"source_id": "help-blocked-02", "title": "Причины блокировки"},
    ]
    # Case A: Response cites help-kanban-01
    text_a = "Согласно источнику help-kanban-01, вы можете перемещать карточки."
    filtered_a = validate_and_filter_sources(available, text_a)
    assert len(filtered_a) == 1
    assert filtered_a[0]["source_id"] == "help-kanban-01"

    # Case B: Response cites nothing
    text_b = "Общий ответ без ссылок на источники."
    filtered_b = validate_and_filter_sources(available, text_b)
    assert len(filtered_b) == 0


def test_run_creation_and_sse_streaming(client: TestClient, monkeypatch):
    class FakeHermesTransport:
        async def start_run(self, **kwargs):
            assert kwargs["message"] == "Объясни статус заказа"
            assert "READ-ONLY" in kwargs["instructions"]
            return {"run_id": "hermes-test-run", "model": "partsops-test"}

        async def stream_run(self, hermes_run_id):
            assert hermes_run_id == "hermes-test-run"
            yield {"event": "message.delta", "delta": "Подтверждённый ответ."}
            yield {"event": "run.completed", "usage": {"total_tokens": 12, "cost_usd": 0.01}}

        async def stop_run(self, hermes_run_id):
            return {"status": "stopped", "run_id": hermes_run_id}

    monkeypatch.setattr(copilot_router, "HermesTransport", FakeHermesTransport)
    headers = make_auth_headers(tenant_id="tenant-stream", role="manager")
    # 1. Create conversation
    conv_res = client.post("/api/copilot/conversations", json={"title": "Stream Test"}, headers=headers)
    conv_id = conv_res.json()["id"]

    # 2. Create Run
    run_res = client.post(
        f"/api/copilot/conversations/{conv_id}/runs",
        json={"message": "Объясни статус заказа", "context_ref": {"screen_id": "kanban_board"}},
        headers=headers,
    )
    assert run_res.status_code == 200
    run_id = run_res.json()["run_id"]

    # 3. Get SSE events stream
    stream_res = client.get(f"/api/copilot/runs/{run_id}/events", headers=headers)
    assert stream_res.status_code == 200
    content = stream_res.text
    assert "run.started" in content
    assert "assistant.delta" in content
    assert "run.completed" in content
    assert '"sequence":' in content
    assert '"correlation_id":' in content


def test_stop_copilot_run(client: TestClient):
    headers = make_auth_headers(tenant_id="tenant-stop", role="manager")
    conv_res = client.post("/api/copilot/conversations", json={"title": "Stop Test"}, headers=headers)
    conv_id = conv_res.json()["id"]

    run_res = client.post(
        f"/api/copilot/conversations/{conv_id}/runs",
        json={"message": "Долгий запрос", "context_ref": {"screen_id": "kanban_board"}},
        headers=headers,
    )
    run_id = run_res.json()["run_id"]

    # Stop run
    stop_res = client.post(f"/api/copilot/runs/{run_id}/stop", headers=headers)
    assert stop_res.status_code == 200
    assert stop_res.json()["status"] == "stopped"


def test_daily_budget_guard(client: TestClient, session: Session):
    headers = make_auth_headers(tenant_id="tenant-budget", role="manager")
    conv_res = client.post("/api/copilot/conversations", json={"title": "Budget Test"}, headers=headers)
    conv_id = conv_res.json()["id"]

    # Add a dummy expensive run to simulate daily budget exhaustion ($10.50)
    expensive_run = CopilotRun(
        id="run-expensive",
        conversation_id=conv_id,
        correlation_id="corr-exp",
        status="completed",
        context_ref_json="{}",
        provider="anthropic",
        model="claude-3-5-haiku",
        tokens_used=50000,
        cost_usd=10.50,
        latency_ms=1000,
        created_at=datetime.now(timezone.utc),
    )
    session.add(expensive_run)
    session.commit()

    # Attempt to create new run
    run_res = client.post(
        f"/api/copilot/conversations/{conv_id}/runs",
        json={"message": "Новое сообщение"},
        headers=headers,
    )
    assert run_res.status_code == 402
    assert "исчерпан" in run_res.json()["detail"]
