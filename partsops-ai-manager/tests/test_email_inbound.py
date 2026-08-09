"""C1 tests: inbound email webhook, idempotency, tenant isolation."""
from __future__ import annotations

import hashlib
import hmac
import json
import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import main
from database import get_session
from models_email import EmailInboxConfig, EmailMessage
from rbac import create_signed_token, _get_api_token
from services.email_ingest import extract_org_slug_from_recipients, upsert_inbox_config


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Ensure email models are in metadata
    import models_email  # noqa: F401

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session, monkeypatch):
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("PARTSOPS_EMAIL_WEBHOOK_SECRET", "test-email-webhook-secret-32chars!!")

    def get_session_override():
        return session

    main.app.dependency_overrides[get_session] = get_session_override
    client = TestClient(main.app)
    yield client
    main.app.dependency_overrides.clear()


def auth_headers(tenant_id: str = "default", role: str = "manager") -> dict:
    secret = _get_api_token()
    headers = {"X-Tenant-ID": tenant_id, "X-User-Role": role}
    if secret:
        headers["Authorization"] = f"Bearer {create_signed_token(tenant_id, role, secret)}"
    return headers


def sign(body: bytes, secret: str = "test-email-webhook-secret-32chars!!") -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_extract_org_slug():
    assert extract_org_slug_from_recipients(["rfq+acme@inbound.example"]) == "acme"
    assert extract_org_slug_from_recipients(["Buyer <rfq+Acme.Co@x.com>"]) == "acme.co"
    assert extract_org_slug_from_recipients(["other@x.com"]) is None


def test_webhook_unknown_recipient(client: TestClient):
    payload = {
        "provider": "mailgun",
        "message_id": "<m1@test>",
        "from": "buyer@partner.ru",
        "to": ["rfq+unknown@inbound.example"],
        "subject": "RFQ",
        "text_body": "need pads",
    }
    raw = json.dumps(payload).encode()
    res = client.post(
        "/api/integrations/email/inbound",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-PartsOps-Signature": sign(raw),
        },
    )
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "EMAIL_UNKNOWN_RECIPIENT"


def test_webhook_idempotent_and_masks_pii(client: TestClient, session: Session):
    upsert_inbox_config(
        session,
        tenant_id="tenant-a",
        org_slug="acme",
        address="rfq+acme@inbound.example",
        auto_ingest=False,
    )

    payload = {
        "provider": "mailgun",
        "message_id": "<unique-msg-42@mail>",
        "from": "john.doe@partner.ru",
        "to": ["rfq+acme@inbound.example"],
        "subject": "Заявка",
        "text_body": "Клиент john.doe@partner.ru, VIN WBA3C3C50EF123456, нужно 2 колодки",
        "attachments": [{"filename": "rfq.xlsx", "content_type": "application/vnd.ms-excel"}],
        "auth_results": {"spf": "pass"},
    }
    raw = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "X-PartsOps-Signature": sign(raw)}

    first = client.post("/api/integrations/email/inbound", content=raw, headers=headers)
    assert first.status_code == 202, first.text
    body = first.json()
    assert body["status"] == "parsed"
    assert body["tenant_id"] == "tenant-a"
    msg_id = body["email_message_id"]

    second = client.post("/api/integrations/email/inbound", content=raw, headers=headers)
    assert second.status_code == 202
    assert second.json()["status"] == "duplicate"
    assert second.json()["email_message_id"] == msg_id

    # tenant list
    listed = client.get("/api/email/messages", headers=auth_headers("tenant-a", "manager"))
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["id"] == msg_id
    assert "john.doe@partner.ru" not in rows[0]["from_masked"]
    assert "***" in rows[0]["from_masked"] or "jo" in rows[0]["from_masked"]
    assert "WBA3C3C50EF123456" not in rows[0]["body_masked_excerpt"]
    assert rows[0]["status"] == "parsed"


def test_tenant_isolation_list(client: TestClient, session: Session):
    upsert_inbox_config(
        session,
        tenant_id="tenant-a",
        org_slug="acme",
        address="rfq+acme@inbound.example",
    )
    upsert_inbox_config(
        session,
        tenant_id="tenant-b",
        org_slug="beta",
        address="rfq+beta@inbound.example",
    )

    for slug, mid in (("acme", "<a@x>"), ("beta", "<b@x>")):
        payload = {
            "message_id": mid,
            "from": "x@y.com",
            "to": [f"rfq+{slug}@inbound.example"],
            "subject": slug,
            "text_body": "hi",
        }
        raw = json.dumps(payload).encode()
        res = client.post(
            "/api/integrations/email/inbound",
            content=raw,
            headers={"Content-Type": "application/json", "X-PartsOps-Signature": sign(raw)},
        )
        assert res.status_code == 202

    a_list = client.get("/api/email/messages", headers=auth_headers("tenant-a")).json()
    b_list = client.get("/api/email/messages", headers=auth_headers("tenant-b")).json()
    assert len(a_list) == 1 and a_list[0]["subject"] == "acme"
    assert len(b_list) == 1 and b_list[0]["subject"] == "beta"

    # B cannot read A's message
    a_id = a_list[0]["id"]
    leak = client.get(f"/api/email/messages/{a_id}", headers=auth_headers("tenant-b"))
    assert leak.status_code == 404


def test_reject_message(client: TestClient, session: Session):
    upsert_inbox_config(
        session,
        tenant_id="default",
        org_slug="default",
        address="rfq+default@inbound.example",
    )
    payload = {
        "message_id": "<rej@x>",
        "from": "a@b.com",
        "to": ["rfq+default@inbound.example"],
        "subject": "x",
        "text_body": "body",
    }
    raw = json.dumps(payload).encode()
    created = client.post(
        "/api/integrations/email/inbound",
        content=raw,
        headers={"Content-Type": "application/json", "X-PartsOps-Signature": sign(raw)},
    ).json()
    mid = created["email_message_id"]

    res = client.post(
        f"/api/email/messages/{mid}/reject",
        headers=auth_headers("default", "manager"),
        json={"reason": "spam"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "rejected"
    assert res.json()["rejection_reason"] == "spam"


def test_invalid_signature(client: TestClient, session: Session):
    upsert_inbox_config(
        session,
        tenant_id="default",
        org_slug="default",
        address="rfq+default@inbound.example",
    )
    payload = {
        "message_id": "<bad-sig@x>",
        "from": "a@b.com",
        "to": ["rfq+default@inbound.example"],
        "text_body": "x",
    }
    raw = json.dumps(payload).encode()
    res = client.post(
        "/api/integrations/email/inbound",
        content=raw,
        headers={"Content-Type": "application/json", "X-PartsOps-Signature": "sha256=deadbeef"},
    )
    assert res.status_code == 401


def test_admin_config_put_get(client: TestClient):
    put = client.put(
        "/api/email/config",
        headers=auth_headers("org-1", "admin"),
        json={
            "org_slug": "org1",
            "address": "rfq+org1@inbound.example",
            "auto_ingest": False,
            "allowed_senders": ["@partner.ru"],
        },
    )
    assert put.status_code == 200, put.text
    assert put.json()["configured"] is True
    assert put.json()["org_slug"] == "org1"

    get = client.get("/api/email/config", headers=auth_headers("org-1", "admin"))
    assert get.status_code == 200
    assert get.json()["address"] == "rfq+org1@inbound.example"

    # manager cannot configure
    denied = client.put(
        "/api/email/config",
        headers=auth_headers("org-1", "manager"),
        json={"org_slug": "x", "address": "rfq+x@y.com"},
    )
    assert denied.status_code == 403


def test_disallowed_attachment_rejected(client: TestClient, session: Session):
    upsert_inbox_config(
        session,
        tenant_id="default",
        org_slug="default",
        address="rfq+default@inbound.example",
    )
    payload = {
        "message_id": "<exe@x>",
        "from": "a@b.com",
        "to": ["rfq+default@inbound.example"],
        "text_body": "see attach",
        "attachments": [{"filename": "malware.exe"}],
    }
    raw = json.dumps(payload).encode()
    res = client.post(
        "/api/integrations/email/inbound",
        content=raw,
        headers={"Content-Type": "application/json", "X-PartsOps-Signature": sign(raw)},
    )
    assert res.status_code == 202
    assert res.json()["status"] == "rejected"
