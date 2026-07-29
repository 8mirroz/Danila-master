"""
Tests: Event Store — hash chain integrity, event emission, chain verification.
"""
import pytest
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool

from models import RequestEvent, PartRequest, SupplierOffer, MatchEvidence, ERPSyncLog, GoldenSample
from suppliers import Supplier, SupplierCatalogItem, Invoice
from event_store import emit_event, get_events, verify_event_chain, emit_state_change
from models import EventType


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


class TestEventEmission:
    def test_emit_creates_event(self, session):
        event = emit_event(session, "REQ-001", EventType.REQUEST_RECEIVED)
        assert event.event_id is not None
        assert event.request_id == "REQ-001"
        assert event.event_type == EventType.REQUEST_RECEIVED
        assert event.event_hash is not None

    def test_emit_sets_previous_hash_to_none_for_first_event(self, session):
        event = emit_event(session, "REQ-001", EventType.REQUEST_RECEIVED)
        assert event.previous_event_hash is None

    def test_emit_chains_events(self, session):
        e1 = emit_event(session, "REQ-001", EventType.REQUEST_RECEIVED)
        e2 = emit_event(session, "REQ-001", EventType.PART_INTENT_EXTRACTED)
        assert e2.previous_event_hash == e1.event_hash

    def test_emit_different_requests_independent_chains(self, session):
        e1 = emit_event(session, "REQ-001", EventType.REQUEST_RECEIVED)
        e2 = emit_event(session, "REQ-002", EventType.REQUEST_RECEIVED)
        assert e2.previous_event_hash is None  # different request, independent chain

    def test_emit_with_payload(self, session):
        import json
        payload = {"source": "telegram", "parts_count": 3}
        event = emit_event(session, "REQ-001", EventType.REQUEST_RECEIVED, payload=payload)
        assert event.payload_json is not None
        stored_payload = json.loads(event.payload_json)
        assert stored_payload["source"] == "telegram"
        assert stored_payload["parts_count"] == 3

    def test_emit_state_change_convenience(self, session):
        event = emit_state_change(session, "REQ-001", "NEW", "NORMALIZING", reason="Test")
        assert event.event_type == EventType.STATE_CHANGED
        import json
        assert event.payload_json is not None
        payload = json.loads(event.payload_json)
        assert payload["from"] == "NEW"
        assert payload["to"] == "NORMALIZING"
        assert payload["reason"] == "Test"


class TestEventChainVerification:
    def test_valid_chain(self, session):
        emit_event(session, "REQ-001", EventType.REQUEST_RECEIVED)
        emit_event(session, "REQ-001", EventType.PART_INTENT_EXTRACTED)
        emit_event(session, "REQ-001", EventType.MATCH_CANDIDATE_CREATED)
        result = verify_event_chain("REQ-001", session)
        assert result["valid"] is True
        assert result["total_events"] == 3

    def test_empty_chain_is_valid(self, session):
        result = verify_event_chain("REQ-NONEXISTENT", session)
        assert result["valid"] is True
        assert result["total_events"] == 0

    def test_get_events_chronological(self, session):
        emit_event(session, "REQ-001", EventType.REQUEST_RECEIVED)
        emit_event(session, "REQ-001", EventType.VIN_VALIDATED)
        emit_event(session, "REQ-001", EventType.PART_INTENT_EXTRACTED)
        events = get_events("REQ-001", session)
        assert len(events) == 3
        types = [e.event_type for e in events]
        assert types[0] == EventType.REQUEST_RECEIVED
        assert types[2] == EventType.PART_INTENT_EXTRACTED

    def test_verify_event_chain_detects_payload_tamper(self, session):
        event = emit_event(session, "REQ-001", EventType.REQUEST_RECEIVED, payload={"source": "telegram"})
        event.payload_json = '{"source":"tampered"}'
        session.add(event)
        session.commit()

        result = verify_event_chain("REQ-001", session)
        assert result["valid"] is False
        assert result["broken_at_event_id"] == event.event_id
        assert "хеш" in result["reason"].lower() or "persisted" in result["reason"].lower()
