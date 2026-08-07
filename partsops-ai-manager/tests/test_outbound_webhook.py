import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import SQLModel, Session, select

from app.automation.context import AutomationContext
from app.automation.jobs import outbound_dispatch_job
from database import engine
from models import OutboundMessage


@pytest.fixture(autouse=True)
def clean_database():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)

def test_webhook_requires_https_and_configured_secret(monkeypatch):
    message = OutboundMessage(tenant_id="tenant-a", channel="webhook", recipient="http://example.test/hook", body_text="event", idempotency_key="webhook-1")
    success, error = outbound_dispatch_job._dispatch_webhook(message)
    assert not success and "HTTPS" in (error or "")
    message.recipient = "https://example.test/hook"
    monkeypatch.setenv("PARTSOPS_OUTBOUND_WEBHOOK_ALLOWED_HOSTS", "example.test")
    monkeypatch.delenv("PARTSOPS_OUTBOUND_WEBHOOK_SECRET", raising=False)
    success, error = outbound_dispatch_job._dispatch_webhook(message)
    assert not success and "secret" in (error or "")

def test_webhook_signs_canonical_envelope(monkeypatch):
    monkeypatch.setenv("PARTSOPS_OUTBOUND_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("PARTSOPS_OUTBOUND_WEBHOOK_ALLOWED_HOSTS", "example.test")
    message = OutboundMessage(id=7, tenant_id="tenant-a", request_id="REQ-1", channel="webhook", recipient="https://example.test/hook", subject="ready", body_text="event", payload_json=json.dumps({"status": "ready"}), idempotency_key="webhook-2")
    class Response: status_code = 202
    captured = {}
    monkeypatch.setattr("httpx.post", lambda url, **kwargs: captured.update(url=url, **kwargs) or Response())
    success, error = outbound_dispatch_job._dispatch_webhook(message)
    assert success and error is None
    assert captured["headers"]["X-PartsOps-Event-ID"] == "webhook-2"
    assert captured["headers"]["X-PartsOps-Signature"].startswith("sha256=")


def test_outbox_dispatch_marks_successful_webhook_sent(monkeypatch):
    monkeypatch.setenv("PARTSOPS_OUTBOUND_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("PARTSOPS_OUTBOUND_WEBHOOK_ALLOWED_HOSTS", "example.test")

    class Response:
        status_code = 202

    monkeypatch.setattr("httpx.post", lambda *args, **kwargs: Response())
    with Session(engine) as session:
        message = OutboundMessage(
            tenant_id="tenant-a",
            channel="webhook",
            recipient="https://example.test/hooks/quote-ready",
            body_text="event",
            idempotency_key="dispatch-success",
        )
        session.add(message)
        session.commit()

        result = outbound_dispatch_job.run(
            session, AutomationContext(tenant_id="tenant-a", actor_id="test")
        )
        dispatched = session.exec(
            select(OutboundMessage).where(OutboundMessage.id == message.id)
        ).one()

    assert result["dispatched"] == 1
    assert dispatched.status == "sent"
    assert dispatched.attempts == 1
    assert dispatched.sent_at is not None


def test_outbox_dispatch_schedules_retry_then_dead_letters_failed_webhook():
    with Session(engine) as session:
        message = OutboundMessage(
            tenant_id="tenant-a",
            channel="webhook",
            recipient="http://example.test/not-https",
            body_text="event",
            idempotency_key="dispatch-dead-letter",
            max_attempts=2,
        )
        session.add(message)
        session.commit()

        context = AutomationContext(tenant_id="tenant-a", actor_id="test")
        first = outbound_dispatch_job.run(session, context)
        retried = session.exec(
            select(OutboundMessage).where(OutboundMessage.id == message.id)
        ).one()
        assert retried.status == "pending"
        assert retried.next_retry_at is not None

        retried.next_retry_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        session.add(retried)
        session.commit()
        second = outbound_dispatch_job.run(session, context)
        dead_letter = session.exec(
            select(OutboundMessage).where(OutboundMessage.id == message.id)
        ).one()

    assert first["failed"] == 1
    assert second["failed"] == 1
    assert dead_letter.status == "failed"
    assert dead_letter.attempts == 2
    assert dead_letter.last_error is not None
