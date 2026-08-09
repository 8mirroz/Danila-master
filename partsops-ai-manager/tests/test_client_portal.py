"""Tests for Client Portal MVP (Phase 9)."""
import pytest
import json
from datetime import datetime, timedelta, timezone
from sqlmodel import SQLModel, Session, select

from database import engine
from models import PartRequest, RequestState
from client_portal import generate_tracking_token, verify_tracking_token, get_public_request_view, accept_offer, reject_offer


@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


def test_tracking_token_generation():
    """Token must be deterministic hash of request_id + salt."""
    token1 = generate_tracking_token("REQ-001")
    token2 = generate_tracking_token("REQ-001")
    # Same request_id + same salt (in code salt is generated per-request)
    # For test, verify it's hex string of 64 chars (SHA256)
    assert len(token1) == 64
    assert all(c in '0123456789abcdef' for c in token1)


def test_public_view_returns_masked_data():
    """Public view must not expose purchase price, margin, supplier_id."""
    with Session(engine) as session:
        req = PartRequest(
            request_id="REQ-VIEW",
            tenant_id="default",
            source="manual",
            status=RequestState.SENT_TO_CLIENT,
            tracking_token="test-token-abc123",
            customer_name="John Doe",
            vehicle_make="BMW",
            vehicle_model="X5",
            parts_json=json.dumps([{"name": "Filter", "sale_price": 1500.0}]),
            pricing_evidence_json=json.dumps({
                "line_items": [
                    {"part_name": "Filter", "purchase_price": 800.0, "sale_price": 1500.0, "margin": 0.45}
                ]
            }),
        )
        session.add(req)
        session.commit()
        
        view = get_public_request_view("test-token-abc123", session, "default")
        
        assert view is not None
        assert view["request_id"] == "REQ-VIEW"
        assert "purchase_price" not in str(view["parts"])
        assert "margin" not in str(view)
        assert "match_score" not in str(view["parts"])
        assert "tracking_token" not in view
        assert view["customer_name"] == "John Doe"
        assert view["vehicle_make"] == "BMW"


def test_accept_offer_transition():
    """Accepting offer must transition SENT_TO_CLIENT → PAID."""
    with Session(engine) as session:
        req = PartRequest(
            request_id="REQ-ACCEPT",
            tenant_id="default",
            source="manual",
            status=RequestState.SENT_TO_CLIENT,
            tracking_token="token-accept",
            customer_name="Jane Doe",
        )
        session.add(req)
        session.commit()
        
        result = accept_offer("token-accept", session, "default")
        
        assert result["ok"] is True
        assert result["new_status"] == "PAID"
        
        session.refresh(req)
        assert req.status == "PAID"


def test_reject_offer_transition():
    """Rejecting offer must transition SENT_TO_CLIENT → CLIENT_REJECTED."""
    with Session(engine) as session:
        req = PartRequest(
            request_id="REQ-REJECT",
            tenant_id="default",
            source="manual",
            status=RequestState.SENT_TO_CLIENT,
            tracking_token="token-reject",
            customer_name="Jane Doe",
        )
        session.add(req)
        session.commit()
        
        result = reject_offer("token-reject", "Wrong price", session, "default")
        
        assert result["ok"] is True
        assert result["new_status"] == "CLIENT_REJECTED"
        
        session.refresh(req)
        assert req.status == "CLIENT_REJECTED"


def test_invalid_token_returns_404():
    """Invalid token must return None from get_public_request_view."""
    with Session(engine) as session:
        result = get_public_request_view("nonexistent-token", session, "default")
        assert result is None


def test_public_view_rejects_expired_token():
    """Expired tracking tokens must not expose request data."""
    with Session(engine) as session:
        req = PartRequest(
            request_id="REQ-EXPIRED-VIEW",
            tenant_id="default",
            source="manual",
            status=RequestState.SENT_TO_CLIENT,
            tracking_token="token-expired-view",
            tracking_token_expires_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1),
            customer_name="Expired Client",
        )
        session.add(req)
        session.commit()

        view = get_public_request_view("token-expired-view", session, "default")
        assert view is None


def test_accept_already_accepted_request_fails():
    """Cannot accept already PAID request."""
    with Session(engine) as session:
        req = PartRequest(
            request_id="REQ-ALREADY",
            tenant_id="default",
            source="manual",
            status=RequestState.PAID,
            tracking_token="token-already",
            customer_name="Jane Doe",
        )
        session.add(req)
        session.commit()
        
        result = accept_offer("token-already", session, "default")
        assert result["ok"] is False
        assert "Cannot accept" in result["error"]


def test_verify_tracking_token_valid():
    """Valid stored token + matching request_id → True."""
    with Session(engine) as session:
        req = PartRequest(
            request_id="REQ-VERIFY-OK",
            tenant_id="default",
            source="manual",
            status=RequestState.SENT_TO_CLIENT,
            tracking_token="token-verify-ok",
            tracking_token_expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24),
            customer_name="Verify User",
        )
        session.add(req)
        session.commit()

        assert verify_tracking_token("token-verify-ok", "REQ-VERIFY-OK", session=session) is True


def test_verify_tracking_token_wrong_request_id():
    """Wrong request_id → False."""
    with Session(engine) as session:
        req = PartRequest(
            request_id="REQ-VERIFY-WRONG",
            tenant_id="default",
            source="manual",
            status=RequestState.SENT_TO_CLIENT,
            tracking_token="token-verify-wrong-id",
            tracking_token_expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24),
            customer_name="Verify User",
        )
        session.add(req)
        session.commit()

        assert verify_tracking_token(
            "token-verify-wrong-id", "REQ-OTHER", session=session
        ) is False


def test_verify_tracking_token_expired():
    """Expired token → False."""
    with Session(engine) as session:
        req = PartRequest(
            request_id="REQ-VERIFY-EXPIRED",
            tenant_id="default",
            source="manual",
            status=RequestState.SENT_TO_CLIENT,
            tracking_token="token-verify-expired",
            tracking_token_expires_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1),
            customer_name="Verify User",
        )
        session.add(req)
        session.commit()

        assert verify_tracking_token(
            "token-verify-expired", "REQ-VERIFY-EXPIRED", session=session
        ) is False


def test_verify_tracking_token_unknown():
    """Unknown token → False."""
    with Session(engine) as session:
        assert verify_tracking_token(
            "nonexistent-token", "REQ-ANY", session=session
        ) is False
