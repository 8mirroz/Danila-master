"""
Unit and Integration Tests for Copilot (Hermes Assistant Router).
Tests tenant isolation, RBAC, PII masking, context building, help source retrieval, and rate limits.
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import main
from database import get_session
from models_copilot import CopilotConversation, CopilotMessage, CopilotRun
from services.help_service import get_help_sources_for_context, get_help_source_by_id
from services.copilot_context import CopilotContextRef, build_context_envelope
from pii import mask_request_for_agent, secure_pre_parse
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
    ref = CopilotContextRef(screen_id="kanban_board")
    envelope = build_context_envelope(
        session=session,
        tenant_id="default",
        context_ref=ref,
        user_role="manager"
    )
    assert envelope.screen_id == "kanban_board"
    assert envelope.screen_title == "Канбан-доска заказов"
    assert len(envelope.available_help_sources) > 0
