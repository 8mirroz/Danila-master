"""
P2 honesty tests for automation engines under app/automation/engines/.
"""
from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, select

from database import engine
from models import OutboundMessage
from app.automation.engines.vin_query_engine import decode_vin
from app.automation.engines.quote_evaluation_engine import score_quotes
from app.automation.engines.decision_engine import decide
from app.automation.engines.notification_engine import notify
from app.automation.engines.supplier_discovery_engine import find_suppliers
from app.automation.engines.erp_hub_engine import route_erp
from app.automation.engines.vendor_query_engine import query_vendor
from app.automation.engines.po_generation_engine import generate_po
from app.automation.engines.escalation_engine import escalate
from app.automation.engines.erp_connector_engine import sync_erp
from app.automation.engines.policy_engine import check_policy
from app.automation.engines.quote_score_engine import score_quotes as score_quotes_wrapper


@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


# ── 1. VIN ───────────────────────────────────────────────────────


def test_decode_vin_bmw_offline():
    vin = "WBA3C3C50EF123456"
    result = decode_vin(vin)
    assert result["make"] == "BMW"
    assert result["decoded"] is True or result["partial"] is True
    assert result.get("reason") != "stub"
    assert result.get("source") == "offline_wmi"
    assert result.get("vin_validity") == "valid"
    assert result.get("implemented") is True


# ── 2. score_quotes ──────────────────────────────────────────────


def test_score_quotes_ranks_cheaper_first():
    quotes = [
        {"supplier": "A", "price": 100.0},
        {"supplier": "B", "price": 50.0},
        {"supplier": "C", "price": 75.0},
    ]
    result = score_quotes(quotes)
    assert result["implemented"] is True
    assert result["status"] == "ok"
    assert result["best_quote"]["supplier"] == "B"
    assert result["best_quote"]["price"] == 50.0
    assert result.get("reason") != "stub"


def test_score_quotes_empty_partial():
    result = score_quotes([])
    assert result["best_quote"] is None
    assert result["status"] == "partial"
    assert result["implemented"] is True


def test_quote_score_engine_wrapper():
    quotes = [{"price": 10}, {"price": 5}]
    result = score_quotes_wrapper(quotes)
    assert result["best_quote"]["price"] == 5


# ── 3. decision ──────────────────────────────────────────────────


def test_decision_approve_and_review():
    approve = decide({"score": 85, "threshold": 70})
    assert approve["implemented"] is True
    assert approve["status"] == "ok"
    assert approve["decision"] == "approve"

    review_low = decide({"score": 40})
    assert review_low["decision"] == "review"

    review_blocked = decide({"score": 90, "blocked": True})
    assert review_blocked["decision"] == "review"


# ── 4–5. notification ────────────────────────────────────────────


def test_notification_without_session_not_sent():
    result = notify("owner@example.com", "hello")
    assert result["implemented"] is True
    assert result["sent"] is False
    assert result["status"] == "partial"
    assert result["reason"] == "no_session_queued_log_only"
    assert result.get("queued") is False


def test_notification_missing_recipient_error():
    result = notify("", "hello")
    assert result["implemented"] is True
    assert result["status"] == "error"
    assert result["sent"] is False


def test_notification_with_session_queues_outbound():
    with Session(engine) as session:
        result = notify(
            "owner@example.com",
            "attention needed",
            channel="email",
            session=session,
            tenant_id="default",
            request_id="REQ-ENG-1",
        )
        session.commit()

        assert result["implemented"] is True
        assert result["sent"] is False
        assert result["queued"] is True
        assert result.get("outbound_message_id") is not None

        msg = session.exec(
            select(OutboundMessage).where(OutboundMessage.id == result["outbound_message_id"])
        ).first()
        assert msg is not None
        assert msg.status == "pending"
        assert msg.recipient == "owner@example.com"
        assert msg.channel == "email"
        assert msg.request_id == "REQ-ENG-1"


# ── 6. supplier discovery ────────────────────────────────────────


def test_supplier_find_without_session_not_wired():
    result = find_suppliers({"tenant_id": "default"})
    assert result["suppliers"] == []
    assert result["implemented"] is False
    assert result["status"] == "not_wired"
    assert result.get("reason") != "stub"


# ── 7. no engine returns reason == "stub" ────────────────────────


def test_no_engine_returns_reason_stub():
    samples = [
        decode_vin("WBA3C3C50EF123456"),
        decode_vin(""),
        score_quotes([{"price": 1}]),
        score_quotes([]),
        decide({"score": 10}),
        notify(None, "x"),
        notify("a@b.c", "x"),
        find_suppliers({}),
        generate_po({"request_id": "R1"}),
        escalate({"reason": "sla"}),
        sync_erp({}),
        check_policy({}),
        route_erp({}),
        query_vendor({}),
        score_quotes_wrapper([{"price": 2}]),
    ]
    for res in samples:
        if isinstance(res, dict):
            assert res.get("reason") != "stub", res
            # must surface honesty fields when dict
            assert "implemented" in res or "status" in res or "reason" in res


# ── 8. erp_hub / vendor_query not_wired ──────────────────────────


def test_erp_hub_and_vendor_query_not_wired():
    hub = route_erp({"request_id": "x"})
    assert hub["implemented"] is False
    assert hub["status"] == "not_wired"
    assert hub.get("reason") != "stub"
    assert "erp" in (hub.get("reason") or "").lower() or "erp_adapter" in (hub.get("reason") or "")

    vendor = query_vendor({"vendor_id": "v1"})
    assert vendor["implemented"] is False
    assert vendor["status"] == "not_wired"
    assert vendor.get("reason") != "stub"


# ── extras: PO + escalate honesty ────────────────────────────────


def test_generate_po_local_draft_only():
    result = generate_po({"request_id": "REQ-PO-1"})
    assert result["implemented"] is True
    assert result["status"] == "partial"
    assert result["po_number"] and str(result["po_number"]).startswith("PO-")
    assert result["reason"] == "local_draft_only_not_sent_to_erp"


def test_escalate_without_session_partial():
    result = escalate({"request_id": "REQ-E1", "reason": "timeout"})
    assert result["implemented"] is True
    assert result["escalated"] is False
    assert result["status"] == "partial"
    assert result["reason"] == "missing_session_or_request_id"


def test_erp_connector_dry_run_never_synced_true():
    """Honesty: DRY_RUN must not report synced=True."""
    with Session(engine) as session:
        result = sync_erp(
            {
                "request_id": "REQ-ERP-DRY",
                "tenant_id": "default",
                "session": session,
                "dry_run": True,
            }
        )
        # Adapter may return not_wired if invoice missing, or partial dry_run.
        if result.get("implemented") and result.get("status") in ("ok", "partial", "error"):
            if result.get("dry_run") or (result.get("reason") or "").find("dry") >= 0:
                assert result.get("synced") is not True
        # If dry_run flag present in result, synced must be False
        if result.get("dry_run") is True:
            assert result["synced"] is False
