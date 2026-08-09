"""C1/C2 tests: inbound email webhook, artifacts, ingest → create_request."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import main
from database import get_session
from models import UploadArtifact
from models_email import EmailMessage
from rbac import create_signed_token, _get_api_token
from services.email_ingest import extract_org_slug_from_recipients, upsert_inbox_config


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import models  # noqa: F401
    import models_email  # noqa: F401

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session, monkeypatch, tmp_path):
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("PARTSOPS_EMAIL_WEBHOOK_SECRET", "test-email-webhook-secret-32chars!!")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    # settings is property-based — patch module settings.UPLOAD_DIR via env already
    # Force settings reload path: settings.UPLOAD_DIR reads env each time (property) OK

    def get_session_override():
        return session

    def fake_create_request(tenant_id, payload_data, x_idempotency_key=None):
        # Simulate RequestService.create_request without hitting global engine
        from models import PartRequest
        from sqlmodel import select as sel

        if x_idempotency_key:
            existing = session.exec(
                sel(PartRequest).where(
                    PartRequest.idempotency_key == x_idempotency_key,
                    PartRequest.tenant_id == tenant_id,
                )
            ).first()
            if existing:
                return {
                    "request": {
                        "request_id": existing.request_id,
                        "status": existing.status,
                        "source": existing.source,
                    },
                    "idempotent": True,
                }
        rid = f"REQ-TEST-{PartRequest.__tablename__}-{x_idempotency_key or 'x'}"[-20:]
        # stable short id
        rid = "REQ-" + hashlib.sha256((x_idempotency_key or rid).encode()).hexdigest()[:8].upper()
        req = PartRequest(
            request_id=rid,
            tenant_id=tenant_id,
            idempotency_key=x_idempotency_key,
            source=payload_data.get("source", "EMAIL"),
            status="PART_EXTRACTION",
            priority=payload_data.get("priority", "normal"),
            customer_name=payload_data.get("customer_name", "Email RFQ"),
            parts_json="[]",
        )
        session.add(req)
        session.commit()
        return {
            "request": {
                "request_id": rid,
                "status": req.status,
                "source": req.source,
            },
            "idempotent": False,
        }

    monkeypatch.setattr(
        "services.email_ingest._invoke_create_request",
        fake_create_request,
    )

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


def test_attachment_base64_becomes_artifact(client: TestClient, session: Session, tmp_path):
    upsert_inbox_config(
        session,
        tenant_id="default",
        org_slug="default",
        address="rfq+default@inbound.example",
    )
    content = b"pad,qty\nfront brake pad,2\n"
    payload = {
        "message_id": "<csv@x>",
        "from": "a@b.com",
        "to": ["rfq+default@inbound.example"],
        "subject": "CSV RFQ",
        "text_body": "",
        "attachments": [
            {
                "filename": "rfq.csv",
                "content_type": "text/csv",
                "bytes_base64": base64.b64encode(content).decode(),
            }
        ],
    }
    raw = json.dumps(payload).encode()
    res = client.post(
        "/api/integrations/email/inbound",
        content=raw,
        headers={"Content-Type": "application/json", "X-PartsOps-Signature": sign(raw)},
    )
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["status"] == "parsed"
    assert body["attachment_artifact_ids"]
    aid = body["attachment_artifact_ids"][0]
    art = session.exec(select(UploadArtifact).where(UploadArtifact.artifact_id == aid)).first()
    assert art is not None
    assert art.tenant_id == "default"
    assert art.source == "email"
    assert Path(art.stored_path).is_file()
    assert Path(art.stored_path).read_bytes() == content


def test_ingest_free_text_creates_request(client: TestClient, session: Session):
    upsert_inbox_config(
        session,
        tenant_id="default",
        org_slug="default",
        address="rfq+default@inbound.example",
    )
    payload = {
        "message_id": "<ingest-body@x>",
        "from": "a@b.com",
        "to": ["rfq+default@inbound.example"],
        "subject": "Need pads",
        "text_body": "Need 2 front brake pads OEM 34116761280",
    }
    raw = json.dumps(payload).encode()
    created = client.post(
        "/api/integrations/email/inbound",
        content=raw,
        headers={"Content-Type": "application/json", "X-PartsOps-Signature": sign(raw)},
    ).json()
    mid = created["email_message_id"]
    assert created["status"] == "parsed"

    ing = client.post(
        f"/api/email/messages/{mid}/ingest",
        headers=auth_headers("default", "manager"),
        json={},
    )
    assert ing.status_code == 200, ing.text
    data = ing.json()
    assert data["status"] == "ingested"
    assert data["request_id"].startswith("REQ-")
    assert data["idempotent"] is False

    msg = session.get(EmailMessage, mid)
    assert msg is not None
    assert msg.status == "ingested"
    assert msg.request_id == data["request_id"]

    # second ingest is idempotent
    again = client.post(
        f"/api/email/messages/{mid}/ingest",
        headers=auth_headers("default", "manager"),
        json={},
    )
    assert again.status_code == 200
    assert again.json()["request_id"] == data["request_id"]
    assert again.json()["idempotent"] is True


def test_ingest_cross_tenant_forbidden(client: TestClient, session: Session):
    upsert_inbox_config(
        session,
        tenant_id="tenant-a",
        org_slug="acme",
        address="rfq+acme@inbound.example",
    )
    payload = {
        "message_id": "<cross@x>",
        "from": "a@b.com",
        "to": ["rfq+acme@inbound.example"],
        "text_body": "parts list",
    }
    raw = json.dumps(payload).encode()
    mid = client.post(
        "/api/integrations/email/inbound",
        content=raw,
        headers={"Content-Type": "application/json", "X-PartsOps-Signature": sign(raw)},
    ).json()["email_message_id"]

    res = client.post(
        f"/api/email/messages/{mid}/ingest",
        headers=auth_headers("tenant-b", "manager"),
        json={},
    )
    assert res.status_code == 404


def test_auto_ingest_creates_request(client: TestClient, session: Session):
    upsert_inbox_config(
        session,
        tenant_id="default",
        org_slug="default",
        address="rfq+default@inbound.example",
        auto_ingest=True,
    )
    payload = {
        "message_id": "<auto@x>",
        "from": "a@b.com",
        "to": ["rfq+default@inbound.example"],
        "text_body": "auto oil filter x1",
    }
    raw = json.dumps(payload).encode()
    res = client.post(
        "/api/integrations/email/inbound",
        content=raw,
        headers={"Content-Type": "application/json", "X-PartsOps-Signature": sign(raw)},
    )
    assert res.status_code == 202, res.text
    body = res.json()
    assert body.get("auto_ingested") is True
    assert body["status"] == "ingested"
    assert body.get("request_id", "").startswith("REQ-")
