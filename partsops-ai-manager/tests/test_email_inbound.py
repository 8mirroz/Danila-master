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
from services.email_ingest import (
    extract_org_slug_from_recipients,
    get_message_stats,
    upsert_inbox_config,
)


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

    # Redelivery must bump stats.duplicate while row stays parsed (not status=duplicate)
    stats_after_dup = get_message_stats(session, "tenant-a")
    assert stats_after_dup["duplicate"] == 1
    assert stats_after_dup["total"] == 1
    third = client.post("/api/integrations/email/inbound", content=raw, headers=headers)
    assert third.status_code == 202
    assert third.json()["status"] == "duplicate"
    assert get_message_stats(session, "tenant-a")["duplicate"] == 2

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


def test_signature_wrong_length_is_401_not_500(client: TestClient, session: Session):
    upsert_inbox_config(
        session,
        tenant_id="default",
        org_slug="default",
        address="rfq+default@inbound.example",
    )
    payload = {
        "message_id": "<short-sig@x>",
        "from": "a@b.com",
        "to": ["rfq+default@inbound.example"],
        "text_body": "x",
    }
    raw = json.dumps(payload).encode()
    res = client.post(
        "/api/integrations/email/inbound",
        content=raw,
        headers={"Content-Type": "application/json", "X-PartsOps-Signature": "sha256=ab"},
    )
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "EMAIL_SIGNATURE_INVALID"


def test_extensionless_attachment_with_bytes_rejected(client: TestClient, session: Session):
    upsert_inbox_config(
        session,
        tenant_id="default",
        org_slug="default",
        address="rfq+default@inbound.example",
    )
    payload = {
        "message_id": "<noext@x>",
        "from": "a@b.com",
        "to": ["rfq+default@inbound.example"],
        "text_body": "see attach",
        "attachments": [
            {
                "filename": "malware",
                "bytes_base64": base64.b64encode(b"MZ").decode(),
            }
        ],
    }
    raw = json.dumps(payload).encode()
    res = client.post(
        "/api/integrations/email/inbound",
        content=raw,
        headers={"Content-Type": "application/json", "X-PartsOps-Signature": sign(raw)},
    )
    assert res.status_code == 202
    assert res.json()["status"] == "rejected"


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


def test_webhook_rate_limit(client: TestClient, session: Session, monkeypatch):
    from settings import settings as settings_mod
    import routers.email_inbox as email_router

    monkeypatch.setattr(type(settings_mod), "EMAIL_WEBHOOK_RPM", property(lambda self: 2))
    # Isolate from other tests that hit the same in-memory RPM buckets.
    email_router._webhook_hits.clear()

    upsert_inbox_config(
        session,
        tenant_id="default",
        org_slug="default",
        address="rfq+default@inbound.example",
    )
    def post_once(mid: str):
        payload = {
            "message_id": mid,
            "from": "a@b.com",
            "to": ["rfq+default@inbound.example"],
            "text_body": "rate",
        }
        raw = json.dumps(payload).encode()
        return client.post(
            "/api/integrations/email/inbound",
            content=raw,
            headers={"Content-Type": "application/json", "X-PartsOps-Signature": sign(raw)},
        )

    assert post_once("<rl-1@x>").status_code == 202
    assert post_once("<rl-2@x>").status_code == 202
    third = post_once("<rl-3@x>")
    assert third.status_code == 429
    body = third.json()["detail"]
    assert body["code"] == "EMAIL_WEBHOOK_RATE_LIMIT"
    assert body.get("scope") == "process"
    assert 1 <= int(body.get("retry_after_seconds", 0)) <= 60
    assert third.headers.get("Retry-After") is not None
    assert 1 <= int(third.headers["Retry-After"]) <= 60


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


def test_get_message_stats_service_and_endpoint(client: TestClient, session: Session):
    """Stats are scoped by tenant_id; empty keys default to 0."""
    empty = get_message_stats(session, "tenant-stats-a")
    assert empty == {
        "total": 0,
        "parsed": 0,
        "ingested": 0,
        "rejected": 0,
        "received": 0,
        "ingesting": 0,
        "duplicate": 0,
    }

    upsert_inbox_config(
        session,
        tenant_id="tenant-stats-a",
        org_slug="stats-a",
        address="rfq+stats-a@inbound.example",
    )
    upsert_inbox_config(
        session,
        tenant_id="tenant-stats-b",
        org_slug="stats-b",
        address="rfq+stats-b@inbound.example",
    )

    def post_inbound(to_addr: str, mid: str) -> None:
        payload = {
            "message_id": mid,
            "from": "buyer@partner.ru",
            "to": [to_addr],
            "subject": "RFQ",
            "text_body": "need pads x2",
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
        assert res.status_code == 202, res.text

    post_inbound("rfq+stats-a@inbound.example", "<stats-a-1@x>")
    post_inbound("rfq+stats-a@inbound.example", "<stats-a-2@x>")
    post_inbound("rfq+stats-b@inbound.example", "<stats-b-1@x>")

    # Mark one tenant-a message rejected so counts diverge by status
    msgs_a = session.exec(
        select(EmailMessage).where(EmailMessage.tenant_id == "tenant-stats-a")
    ).all()
    assert len(msgs_a) == 2
    msgs_a[0].status = "rejected"
    session.add(msgs_a[0])
    session.commit()

    stats_a = get_message_stats(session, "tenant-stats-a")
    assert stats_a["total"] == 2
    assert stats_a["rejected"] == 1
    assert stats_a["parsed"] + stats_a["received"] + stats_a["ingested"] + stats_a["ingesting"] == 1
    assert stats_a["ingested"] == 0
    assert stats_a["ingesting"] == 0

    stats_b = get_message_stats(session, "tenant-stats-b")
    assert stats_b["total"] == 1
    assert stats_b["rejected"] == 0

    # API: manager can read own tenant stats
    res = client.get("/api/email/stats", headers=auth_headers("tenant-stats-a", "manager"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 2
    assert body["rejected"] == 1
    assert set(body.keys()) == {
        "total",
        "parsed",
        "ingested",
        "rejected",
        "received",
        "ingesting",
        "duplicate",
    }
    assert body["duplicate"] == 0

    # Cross-tenant: tenant-b token must not see tenant-a totals
    res_b = client.get("/api/email/stats", headers=auth_headers("tenant-stats-b", "manager"))
    assert res_b.status_code == 200
    assert res_b.json()["total"] == 1


def test_duplicate_webhook_increments_stats_duplicate(client: TestClient, session: Session):
    """Provider redelivery: API status=duplicate, stats.duplicate++, row status unchanged."""
    upsert_inbox_config(
        session,
        tenant_id="tenant-dup-stats",
        org_slug="dup-stats",
        address="rfq+dup-stats@inbound.example",
    )
    payload = {
        "message_id": "<dup-stats-1@x>",
        "from": "buyer@partner.ru",
        "to": ["rfq+dup-stats@inbound.example"],
        "subject": "RFQ pads",
        "text_body": "need pads x2",
    }
    raw = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "X-PartsOps-Signature": sign(raw),
    }

    first = client.post("/api/integrations/email/inbound", content=raw, headers=headers)
    assert first.status_code == 202, first.text
    assert first.json()["status"] == "parsed"
    assert get_message_stats(session, "tenant-dup-stats")["duplicate"] == 0

    second = client.post("/api/integrations/email/inbound", content=raw, headers=headers)
    assert second.status_code == 202
    assert second.json()["status"] == "duplicate"

    stats = get_message_stats(session, "tenant-dup-stats")
    assert stats["total"] == 1
    assert stats["duplicate"] == 1
    assert stats["parsed"] == 1  # original status preserved

    api = client.get(
        "/api/email/stats",
        headers=auth_headers("tenant-dup-stats", "manager"),
    )
    assert api.status_code == 200
    assert api.json()["duplicate"] == 1
    assert api.json()["parsed"] == 1


def test_reject_while_ingesting_returns_409(client: TestClient, session: Session):
    """CAS: operator must not clobber an in-flight ingest claim."""
    upsert_inbox_config(
        session,
        tenant_id="default",
        org_slug="default",
        address="rfq+default@inbound.example",
    )
    payload = {
        "message_id": "<race-rej@x>",
        "from": "a@b.com",
        "to": ["rfq+default@inbound.example"],
        "subject": "race",
        "text_body": "parts",
    }
    raw = json.dumps(payload).encode()
    mid = client.post(
        "/api/integrations/email/inbound",
        content=raw,
        headers={"Content-Type": "application/json", "X-PartsOps-Signature": sign(raw)},
    ).json()["email_message_id"]

    msg = session.get(EmailMessage, mid)
    assert msg is not None
    msg.status = "ingesting"
    session.add(msg)
    session.commit()

    res = client.post(
        f"/api/email/messages/{mid}/reject",
        headers=auth_headers("default", "manager"),
        json={"reason": "too_late"},
    )
    assert res.status_code == 409, res.text
    assert "in progress" in res.json()["detail"].lower()

    session.refresh(msg)
    assert msg.status == "ingesting"
    assert msg.rejection_reason is None


def test_ingest_while_ingesting_returns_409(client: TestClient, session: Session):
    """Second ingest while claim held must not double-create a request."""
    upsert_inbox_config(
        session,
        tenant_id="default",
        org_slug="default",
        address="rfq+default@inbound.example",
    )
    payload = {
        "message_id": "<race-ing@x>",
        "from": "a@b.com",
        "to": ["rfq+default@inbound.example"],
        "text_body": "parts",
    }
    raw = json.dumps(payload).encode()
    mid = client.post(
        "/api/integrations/email/inbound",
        content=raw,
        headers={"Content-Type": "application/json", "X-PartsOps-Signature": sign(raw)},
    ).json()["email_message_id"]

    msg = session.get(EmailMessage, mid)
    assert msg is not None
    msg.status = "ingesting"
    session.add(msg)
    session.commit()

    res = client.post(
        f"/api/email/messages/{mid}/ingest",
        headers=auth_headers("default", "manager"),
        json={},
    )
    assert res.status_code == 409, res.text
    assert "in progress" in res.json()["detail"].lower()


def test_reject_idempotent_and_blocks_after_ingest(client: TestClient, session: Session):
    upsert_inbox_config(
        session,
        tenant_id="default",
        org_slug="default",
        address="rfq+default@inbound.example",
    )
    payload = {
        "message_id": "<rej-idem@x>",
        "from": "a@b.com",
        "to": ["rfq+default@inbound.example"],
        "text_body": "body",
    }
    raw = json.dumps(payload).encode()
    mid = client.post(
        "/api/integrations/email/inbound",
        content=raw,
        headers={"Content-Type": "application/json", "X-PartsOps-Signature": sign(raw)},
    ).json()["email_message_id"]

    first = client.post(
        f"/api/email/messages/{mid}/reject",
        headers=auth_headers("default", "manager"),
        json={"reason": "spam"},
    )
    assert first.status_code == 200
    assert first.json()["status"] == "rejected"

    second = client.post(
        f"/api/email/messages/{mid}/reject",
        headers=auth_headers("default", "manager"),
        json={"reason": "spam_again"},
    )
    assert second.status_code == 200
    assert second.json()["status"] == "rejected"
    # first reason preserved (idempotent, no overwrite of terminal reject)
    assert second.json()["rejection_reason"] == "spam"

    # cannot ingest after reject
    bad_ing = client.post(
        f"/api/email/messages/{mid}/ingest",
        headers=auth_headers("default", "manager"),
        json={},
    )
    assert bad_ing.status_code == 422

    # cannot reject after successful ingest of another message
    payload2 = {
        "message_id": "<rej-after-ing@x>",
        "from": "a@b.com",
        "to": ["rfq+default@inbound.example"],
        "text_body": "need oil filter",
    }
    raw2 = json.dumps(payload2).encode()
    mid2 = client.post(
        "/api/integrations/email/inbound",
        content=raw2,
        headers={"Content-Type": "application/json", "X-PartsOps-Signature": sign(raw2)},
    ).json()["email_message_id"]
    ing = client.post(
        f"/api/email/messages/{mid2}/ingest",
        headers=auth_headers("default", "manager"),
        json={},
    )
    assert ing.status_code == 200
    rej_after = client.post(
        f"/api/email/messages/{mid2}/reject",
        headers=auth_headers("default", "manager"),
        json={"reason": "late"},
    )
    assert rej_after.status_code == 409


def test_ingest_claim_lost_to_reject_returns_422(client: TestClient, session: Session):
    """If reject wins CAS first, ingest must not create a request."""
    upsert_inbox_config(
        session,
        tenant_id="default",
        org_slug="default",
        address="rfq+default@inbound.example",
    )
    payload = {
        "message_id": "<claim-lost@x>",
        "from": "a@b.com",
        "to": ["rfq+default@inbound.example"],
        "text_body": "parts",
    }
    raw = json.dumps(payload).encode()
    mid = client.post(
        "/api/integrations/email/inbound",
        content=raw,
        headers={"Content-Type": "application/json", "X-PartsOps-Signature": sign(raw)},
    ).json()["email_message_id"]

    # Simulate concurrent reject winning before ingest claim
    msg = session.get(EmailMessage, mid)
    assert msg is not None
    msg.status = "rejected"
    msg.rejection_reason = "won_race"
    session.add(msg)
    session.commit()

    res = client.post(
        f"/api/email/messages/{mid}/ingest",
        headers=auth_headers("default", "manager"),
        json={},
    )
    assert res.status_code == 422, res.text


def test_threaded_double_ingest_single_request(monkeypatch, tmp_path):
    """Two concurrent ingest workers: CAS ensures at most one PartRequest."""
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from fastapi import HTTPException
    from models import PartRequest
    from services.email_ingest import ingest_message

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import models  # noqa: F401
    import models_email  # noqa: F401

    SQLModel.metadata.create_all(engine)

    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))

    create_calls = {"n": 0}
    create_lock = threading.Lock()
    gate = threading.Barrier(2, timeout=5)

    def fake_create_request(tenant_id, payload_data, x_idempotency_key=None):
        # Hold both winners-of-race at create edge so loser must hit CAS, not only
        # sequential re-read. Only CAS winner reaches this function.
        with create_lock:
            create_calls["n"] += 1
        if x_idempotency_key:
            with Session(engine) as s:
                existing = s.exec(
                    select(PartRequest).where(
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
        rid = "REQ-" + hashlib.sha256((x_idempotency_key or "x").encode()).hexdigest()[:8].upper()
        with Session(engine) as s:
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
            s.add(req)
            s.commit()
        return {
            "request": {"request_id": rid, "status": "PART_EXTRACTION", "source": "EMAIL"},
            "idempotent": False,
        }

    monkeypatch.setattr(
        "services.email_ingest._invoke_create_request",
        fake_create_request,
    )

    with Session(engine) as session:
        upsert_inbox_config(
            session,
            tenant_id="default",
            org_slug="default",
            address="rfq+default@inbound.example",
        )
        msg = EmailMessage(
            id="em-thread-double",
            tenant_id="default",
            provider="mailgun",
            provider_message_id="<thread-double@x>",
            from_masked="a@b.com",
            to_address="rfq+default@inbound.example",
            subject="thread race",
            body_masked_excerpt="oil filter x1",
            status="parsed",
        )
        session.add(msg)
        session.commit()
        mid = msg.id

    results: list[dict] = []
    errors: list[HTTPException] = []
    lock = threading.Lock()

    def worker() -> None:
        gate.wait()
        with Session(engine) as s:
            try:
                out = ingest_message(s, "default", mid)
                with lock:
                    results.append(out)
            except HTTPException as exc:
                with lock:
                    errors.append(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(worker) for _ in range(2)]
        for f in as_completed(futs):
            f.result(timeout=10)

    with Session(engine) as session:
        session.expire_all()
        final = session.get(EmailMessage, mid)
        assert final is not None
        assert final.status == "ingested"
        assert final.request_id
        reqs = session.exec(
            select(PartRequest).where(
                PartRequest.tenant_id == "default",
                PartRequest.source == "EMAIL",
            )
        ).all()
        assert len(reqs) == 1, f"expected single PartRequest, got {len(reqs)}"
        assert reqs[0].request_id == final.request_id

    # One hard success; peer is 409 in-progress, or rare idempotent re-read after finish
    assert len(results) >= 1
    assert all(r.get("request_id") == final.request_id for r in results)
    for exc in errors:
        assert exc.status_code == 409
        assert "in progress" in str(exc.detail).lower() or "race" in str(exc.detail).lower()
    # create_request at most once (CAS winner only); never double-create
    assert create_calls["n"] == 1
    assert len(results) + len(errors) == 2


def test_ingest_failure_releases_claim_then_retry_succeeds(monkeypatch, tmp_path):
    """Mid-flight create_request failure must CAS-release claim so retry can ingest."""
    from models import PartRequest
    from services.email_ingest import ingest_message

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import models  # noqa: F401
    import models_email  # noqa: F401

    SQLModel.metadata.create_all(engine)

    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))

    calls = {"n": 0}

    def flaky_create_request(tenant_id, payload_data, x_idempotency_key=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated create_request failure")
        if x_idempotency_key:
            with Session(engine) as s:
                existing = s.exec(
                    select(PartRequest).where(
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
        rid = "REQ-" + hashlib.sha256((x_idempotency_key or "x").encode()).hexdigest()[:8].upper()
        with Session(engine) as s:
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
            s.add(req)
            s.commit()
        return {
            "request": {"request_id": rid, "status": "PART_EXTRACTION", "source": "EMAIL"},
            "idempotent": False,
        }

    monkeypatch.setattr(
        "services.email_ingest._invoke_create_request",
        flaky_create_request,
    )

    mid = "em-claim-release"
    with Session(engine) as session:
        upsert_inbox_config(
            session,
            tenant_id="default",
            org_slug="default",
            address="rfq+default@inbound.example",
        )
        session.add(
            EmailMessage(
                id=mid,
                tenant_id="default",
                provider="mailgun",
                provider_message_id="<claim-release@x>",
                from_masked="a@b.com",
                to_address="rfq+default@inbound.example",
                subject="claim release",
                body_masked_excerpt="filter x2",
                status="parsed",
            )
        )
        session.commit()

    with Session(engine) as session:
        with pytest.raises(RuntimeError, match="simulated create_request failure"):
            ingest_message(session, "default", mid)
        session.expire_all()
        after_fail = session.get(EmailMessage, mid)
        assert after_fail is not None
        assert after_fail.status == "parsed", "claim must release to parsed for retry"
        assert after_fail.request_id is None

    with Session(engine) as session:
        out = ingest_message(session, "default", mid)
        assert out["status"] == "ingested"
        assert out["request_id"]
        session.expire_all()
        final = session.get(EmailMessage, mid)
        assert final is not None
        assert final.status == "ingested"
        assert final.request_id == out["request_id"]

    assert calls["n"] == 2


def test_ingest_mid_flight_peer_409_then_retry_after_release(monkeypatch, tmp_path):
    """While claim held (ingesting), peer gets 409; after failure release, retry succeeds."""
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from fastapi import HTTPException
    from models import PartRequest
    from services.email_ingest import ingest_message

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import models  # noqa: F401
    import models_email  # noqa: F401

    SQLModel.metadata.create_all(engine)

    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))

    hold = threading.Event()
    entered = threading.Event()
    calls = {"n": 0}
    lock = threading.Lock()

    def blocking_then_fail_create(tenant_id, payload_data, x_idempotency_key=None):
        with lock:
            calls["n"] += 1
            n = calls["n"]
        if n == 1:
            entered.set()
            # Hold claim while peer races
            assert hold.wait(timeout=5), "test gate timeout"
            raise RuntimeError("mid-flight boom")
        # Success path for retry after release
        rid = "REQ-" + hashlib.sha256((x_idempotency_key or "x").encode()).hexdigest()[:8].upper()
        with Session(engine) as s:
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
            s.add(req)
            s.commit()
        return {
            "request": {"request_id": rid, "status": "PART_EXTRACTION", "source": "EMAIL"},
            "idempotent": False,
        }

    monkeypatch.setattr(
        "services.email_ingest._invoke_create_request",
        blocking_then_fail_create,
    )

    mid = "em-mid-flight"
    with Session(engine) as session:
        upsert_inbox_config(
            session,
            tenant_id="default",
            org_slug="default",
            address="rfq+default@inbound.example",
        )
        session.add(
            EmailMessage(
                id=mid,
                tenant_id="default",
                provider="mailgun",
                provider_message_id="<mid-flight@x>",
                from_masked="a@b.com",
                to_address="rfq+default@inbound.example",
                subject="mid flight",
                body_masked_excerpt="gasket",
                status="parsed",
            )
        )
        session.commit()

    peer_errors: list[HTTPException] = []
    holder_errors: list[BaseException] = []
    results_lock = threading.Lock()

    def holder() -> None:
        with Session(engine) as s:
            try:
                ingest_message(s, "default", mid)
            except Exception as exc:
                with results_lock:
                    holder_errors.append(exc)

    def peer() -> None:
        assert entered.wait(timeout=5)
        with Session(engine) as s:
            try:
                ingest_message(s, "default", mid)
            except HTTPException as exc:
                with results_lock:
                    peer_errors.append(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_hold = pool.submit(holder)
        f_peer = pool.submit(peer)
        assert entered.wait(timeout=5)
        # Peer should see ingesting / race while claim held
        f_peer.result(timeout=10)
        hold.set()
        f_hold.result(timeout=10)

    assert len(holder_errors) == 1
    assert isinstance(holder_errors[0], RuntimeError)
    assert len(peer_errors) == 1
    assert peer_errors[0].status_code == 409

    with Session(engine) as session:
        session.expire_all()
        released = session.get(EmailMessage, mid)
        assert released is not None
        assert released.status == "parsed"

    # Operator/retry after release
    with Session(engine) as session:
        out = ingest_message(session, "default", mid)
        assert out["status"] == "ingested"
        assert out["request_id"]


def test_ingest_no_request_id_releases_claim_then_reject(monkeypatch, tmp_path):
    """create_request without request_id must CAS-release ingesting→parsed (not leave claim stuck).

    Concurrent reject after release must succeed (not 409 ingesting).
    """
    from fastapi import HTTPException
    from services.email_ingest import ingest_message, reject_message

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import models  # noqa: F401
    import models_email  # noqa: F401

    SQLModel.metadata.create_all(engine)

    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))

    def empty_create_request(tenant_id, payload_data, x_idempotency_key=None):
        # Honest empty payload — no request id
        return {"request": {}, "idempotent": False}

    monkeypatch.setattr(
        "services.email_ingest._invoke_create_request",
        empty_create_request,
    )

    mid = "em-no-rid"
    with Session(engine) as session:
        upsert_inbox_config(
            session,
            tenant_id="default",
            org_slug="default",
            address="rfq+default@inbound.example",
        )
        session.add(
            EmailMessage(
                id=mid,
                tenant_id="default",
                provider="mailgun",
                provider_message_id="<no-rid@x>",
                from_masked="a@b.com",
                to_address="rfq+default@inbound.example",
                subject="no rid",
                body_masked_excerpt="pads",
                status="parsed",
            )
        )
        session.commit()

    with Session(engine) as session:
        with pytest.raises(HTTPException) as ei:
            ingest_message(session, "default", mid)
        assert ei.value.status_code == 500
        assert "request_id" in str(ei.value.detail).lower()
        session.expire_all()
        after = session.get(EmailMessage, mid)
        assert after is not None
        assert after.status == "parsed", "claim must release on empty request_id"
        assert after.request_id is None

    # After release, operator reject must not see ingesting
    with Session(engine) as session:
        rejected = reject_message(session, "default", mid, reason="empty_create")
        assert rejected["status"] == "rejected"
        session.expire_all()
        final = session.get(EmailMessage, mid)
        assert final is not None
        assert final.status == "rejected"
        assert final.rejection_reason == "empty_create"
