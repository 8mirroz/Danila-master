"""
W3 P1 honesty tests for automation stubs: notify_owner, dead_letter_cleanup, vin_query.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, select

from database import engine
from models import OutboundMessage, PartRequest, RequestState
from app.automation.context import AutomationContext
from app.automation.jobs import notify_owner_job, dead_letter_cleanup_job
from app.automation.engines.vin_query_engine import decode_vin


@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


def _make_request(session: Session, request_id: str = "REQ-NOTIFY-1", tenant_id: str = "default") -> PartRequest:
    req = PartRequest(
        request_id=request_id,
        tenant_id=tenant_id,
        source="manual",
        status=RequestState.NEW,
        customer_name="Test Owner",
    )
    session.add(req)
    session.commit()
    session.refresh(req)
    return req


# ── B4 notify_owner ──────────────────────────────────────────────


def test_notify_owner_dry_run_honest():
    with Session(engine) as session:
        _make_request(session)
        ctx = AutomationContext(
            tenant_id="default",
            actor_id="test",
            request_id="REQ-NOTIFY-1",
            dry_run=True,
            payload={"recipient": "owner@example.com"},
        )
        res = notify_owner_job.run(session, ctx)
        assert res["ok"] is True
        assert res["dry_run"] is True
        assert res["notified"] is False
        assert res.get("queued") is False
        msgs = session.exec(select(OutboundMessage)).all()
        assert len(msgs) == 0


def test_notify_owner_missing_recipient():
    with Session(engine) as session:
        _make_request(session)
        ctx = AutomationContext(
            tenant_id="default",
            actor_id="test",
            request_id="REQ-NOTIFY-1",
            dry_run=False,
            payload={},
        )
        res = notify_owner_job.run(session, ctx)
        assert res["ok"] is False
        assert res["error"] == "missing_recipient"
        assert res["notified"] is False
        msgs = session.exec(select(OutboundMessage)).all()
        assert len(msgs) == 0


def test_notify_owner_with_recipient_queues_outbox():
    with Session(engine) as session:
        _make_request(session)
        ctx = AutomationContext(
            tenant_id="default",
            actor_id="test",
            request_id="REQ-NOTIFY-1",
            dry_run=False,
            payload={"recipient": "owner@example.com", "channel": "email"},
        )
        res = notify_owner_job.run(session, ctx)
        assert res["ok"] is True
        assert res["notified"] is False
        assert res["queued"] is True
        assert res.get("outbound_message_id") is not None

        msg = session.exec(
            select(OutboundMessage).where(OutboundMessage.id == res["outbound_message_id"])
        ).first()
        assert msg is not None
        assert msg.status == "pending"
        assert msg.recipient == "owner@example.com"
        assert msg.channel == "email"
        assert msg.request_id == "REQ-NOTIFY-1"
        assert msg.idempotency_key == "notify_owner:REQ-NOTIFY-1:email"


# ── B5 dead_letter_cleanup ───────────────────────────────────────


def test_dead_letter_dry_run_would_remove():
    with Session(engine) as session:
        old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=100)
        msg = OutboundMessage(
            tenant_id="default",
            request_id="REQ-DL-1",
            channel="email",
            recipient="x@example.com",
            subject="dead",
            body_text="body",
            idempotency_key="dl-test-1",
            status="failed",
            attempts=3,
            max_attempts=3,
            created_at=old,
            updated_at=old,
        )
        session.add(msg)
        session.commit()

        ctx = AutomationContext(
            tenant_id="default",
            actor_id="test",
            dry_run=True,
            payload={"retention_hours": 72},
        )
        res = dead_letter_cleanup_job.run(session, ctx)
        assert res["ok"] is True
        assert res["dry_run"] is True
        assert res["would_remove"] == 1
        assert res["removed"] == 0
        # still present
        assert session.exec(select(OutboundMessage)).first() is not None


def test_dead_letter_removes_old_failed_only():
    with Session(engine) as session:
        old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=100)
        recent = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)

        dead_old = OutboundMessage(
            tenant_id="default",
            request_id="REQ-DL-OLD",
            channel="email",
            recipient="old@example.com",
            subject="old dead",
            body_text="body",
            idempotency_key="dl-old-failed",
            status="failed",
            attempts=3,
            max_attempts=3,
            created_at=old,
            updated_at=old,
        )
        pending = OutboundMessage(
            tenant_id="default",
            request_id="REQ-DL-P",
            channel="email",
            recipient="p@example.com",
            subject="pending",
            body_text="body",
            idempotency_key="dl-pending",
            status="pending",
            attempts=0,
            max_attempts=3,
            created_at=old,
            updated_at=old,
        )
        sent = OutboundMessage(
            tenant_id="default",
            request_id="REQ-DL-S",
            channel="email",
            recipient="s@example.com",
            subject="sent",
            body_text="body",
            idempotency_key="dl-sent",
            status="sent",
            attempts=1,
            max_attempts=3,
            created_at=old,
            updated_at=old,
        )
        failed_recent = OutboundMessage(
            tenant_id="default",
            request_id="REQ-DL-RECENT",
            channel="email",
            recipient="r@example.com",
            subject="recent failed",
            body_text="body",
            idempotency_key="dl-recent-failed",
            status="failed",
            attempts=3,
            max_attempts=3,
            created_at=recent,
            updated_at=recent,
        )
        session.add(dead_old)
        session.add(pending)
        session.add(sent)
        session.add(failed_recent)
        session.commit()

        ctx = AutomationContext(
            tenant_id="default",
            actor_id="test",
            dry_run=False,
            payload={"retention_hours": 72},
        )
        res = dead_letter_cleanup_job.run(session, ctx)
        assert res["ok"] is True
        assert res["removed"] == 1

        remaining = session.exec(select(OutboundMessage)).all()
        keys = {m.idempotency_key for m in remaining}
        assert "dl-old-failed" not in keys
        assert "dl-pending" in keys
        assert "dl-sent" in keys
        assert "dl-recent-failed" in keys


# ── B1 vin_query_engine ──────────────────────────────────────────


def test_decode_vin_bmw_offline():
    vin = "WBA3C3C50EF123456"
    result = decode_vin(vin)
    assert result["make"] == "BMW"
    assert result["decoded"] is True or result["partial"] is True
    assert result.get("reason") != "stub"
    assert result.get("source") == "offline_wmi"
    assert result.get("vin_validity") == "valid"


def test_decode_vin_empty():
    result = decode_vin("")
    assert result["decoded"] is False
    assert result["reason"] == "empty_vin"
    assert result.get("reason") != "stub"
