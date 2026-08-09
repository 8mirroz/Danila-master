"""A1: email inbound → real RequestService.create_request on shared engine."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

import main
from database import engine, get_session
from models import PartRequest, UploadArtifact
from models_email import EmailMessage
from rbac import create_signed_token, _get_api_token
from services.email_ingest import upsert_inbox_config

SECRET = "test-email-webhook-secret-32chars!!"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("PARTSOPS_API_TOKEN", "test-token")
    monkeypatch.setenv("PARTSOPS_EMAIL_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))

    # Ensure email models registered
    import models  # noqa: F401
    import models_email  # noqa: F401
    import models_copilot  # noqa: F401

    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    def get_session_override():
        with Session(engine) as session:
            yield session

    main.app.dependency_overrides[get_session] = get_session_override
    # Real create_request — do NOT mock _invoke_create_request
    client = TestClient(main.app)
    yield client
    main.app.dependency_overrides.clear()


def auth(tenant: str = "default", role: str = "manager") -> dict:
    headers = {"X-Tenant-ID": tenant, "X-User-Role": role}
    secret = _get_api_token()
    if secret:
        headers["Authorization"] = f"Bearer {create_signed_token(tenant, role, secret)}"
    return headers


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_ingest_creates_part_request_with_email_source(client: TestClient):
    with Session(engine) as session:
        upsert_inbox_config(
            session,
            tenant_id="default",
            org_slug="default",
            address="rfq+default@inbound.example",
            auto_ingest=False,
        )

    payload = {
        "provider": "mailgun",
        "message_id": "<integration-real-create@test>",
        "from": "buyer@partner.example",
        "to": ["rfq+default@inbound.example"],
        "subject": "Need brake pads",
        "text_body": "Please quote 2x front brake pads OEM 34116761280 for BMW X5",
    }
    raw = json.dumps(payload).encode()
    r1 = client.post(
        "/api/integrations/email/inbound",
        content=raw,
        headers={"Content-Type": "application/json", "X-PartsOps-Signature": sign(raw)},
    )
    assert r1.status_code == 202, r1.text
    emsg_id = r1.json()["email_message_id"]
    assert r1.json()["status"] == "parsed"

    r2 = client.post(
        f"/api/email/messages/{emsg_id}/ingest",
        headers=auth(),
        json={},
    )
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert data["status"] == "ingested"
    request_id = data["request_id"]
    assert request_id.startswith("REQ-")

    with Session(engine) as session:
        req = session.exec(
            select(PartRequest).where(PartRequest.request_id == request_id)
        ).first()
        assert req is not None
        assert req.source == "EMAIL"
        assert req.tenant_id == "default"
        assert req.idempotency_key == f"email:default:<integration-real-create@test>"

        msg = session.get(EmailMessage, emsg_id)
        assert msg is not None
        assert msg.status == "ingested"
        assert msg.request_id == request_id

    # Idempotent re-ingest
    r3 = client.post(
        f"/api/email/messages/{emsg_id}/ingest",
        headers=auth(),
        json={},
    )
    assert r3.status_code == 200
    assert r3.json()["request_id"] == request_id
    assert r3.json()["idempotent"] is True

    with Session(engine) as session:
        count = len(
            session.exec(
                select(PartRequest).where(
                    PartRequest.idempotency_key == "email:default:<integration-real-create@test>"
                )
            ).all()
        )
        assert count == 1


def test_csv_attachment_stored_and_ingest_uses_artifact(client: TestClient, tmp_path):
    with Session(engine) as session:
        upsert_inbox_config(
            session,
            tenant_id="default",
            org_slug="default",
            address="rfq+default@inbound.example",
        )

    csv_body = "Артикул;Наименование;Количество\nPAD-01;Колодки передние;2\n"
    payload = {
        "message_id": "<integration-csv@test>",
        "from": "buyer@partner.example",
        "to": ["rfq+default@inbound.example"],
        "subject": "CSV RFQ",
        "text_body": "",
        "attachments": [
            {
                "filename": "rfq.csv",
                "content_type": "text/csv",
                "bytes_base64": base64.b64encode(csv_body.encode("utf-8")).decode(),
            }
        ],
    }
    raw = json.dumps(payload).encode()
    r1 = client.post(
        "/api/integrations/email/inbound",
        content=raw,
        headers={"Content-Type": "application/json", "X-PartsOps-Signature": sign(raw)},
    )
    assert r1.status_code == 202, r1.text
    aids = r1.json().get("attachment_artifact_ids") or []
    assert aids, "expected UploadArtifact ids"
    emsg_id = r1.json()["email_message_id"]

    with Session(engine) as session:
        art = session.exec(
            select(UploadArtifact).where(UploadArtifact.artifact_id == aids[0])
        ).first()
        assert art is not None
        assert art.source == "email"
        assert Path(art.stored_path).is_file()

    r2 = client.post(
        f"/api/email/messages/{emsg_id}/ingest",
        headers=auth(),
        json={},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "ingested"

    with Session(engine) as session:
        art = session.exec(
            select(UploadArtifact).where(UploadArtifact.artifact_id == aids[0])
        ).first()
        assert art is not None
        assert art.request_id == r2.json()["request_id"]
        assert art.status == "attached"
