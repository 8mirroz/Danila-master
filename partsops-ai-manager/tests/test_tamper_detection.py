"""
Test for Event Store tamper detection.
Verifies that manual/unauthorized modifications to events break the hash chain.
"""
import pytest
from sqlmodel import Session
from database import engine, init_db
from models import RequestEvent
from event_store import emit_event, verify_event_chain

def test_tamper_detection_breaks_chain():
    init_db()
    with Session(engine) as session:
        request_id = "REQ-TAMPER-TEST"
        tenant_id = "tenant_test"
        
        # 1. Emit events normally
        e1 = emit_event(session, request_id, "EVENT_1", payload={"k": "v1"}, tenant_id=tenant_id)
        e2 = emit_event(session, request_id, "EVENT_2", payload={"k": "v2"}, tenant_id=tenant_id)
        
        # 2. Verify chain is valid
        res = verify_event_chain(request_id, session, tenant_id=tenant_id)
        assert res["valid"] is True
        
        # 3. Simulate unauthorized database modification (tamper)
        e1_db = session.get(RequestEvent, e1.id)
        e1_db.payload_json = '{"k": "tampered_value"}'
        session.add(e1_db)
        session.commit()
        
        # 4. Verify chain detects the tamper
        res_tampered = verify_event_chain(request_id, session, tenant_id=tenant_id)
        assert res_tampered["valid"] is False
        assert res_tampered["reason"] == "Хеш события не совпадает с persisted content"
        assert res_tampered["broken_at_event_id"] == e1.event_id

def test_chain_break_detection():
    init_db()
    with Session(engine) as session:
        request_id = "REQ-CHAIN-TEST"
        tenant_id = "tenant_test"
        
        e1 = emit_event(session, request_id, "EVENT_A", payload={}, tenant_id=tenant_id)
        e2 = emit_event(session, request_id, "EVENT_B", payload={}, tenant_id=tenant_id)
        
        # Tamper: changing previous_event_hash breaks the chain logic
        e2_db = session.get(RequestEvent, e2.id)
        e2_db.previous_event_hash = "fake_hash_123"
        session.add(e2_db)
        session.commit()
        
        res = verify_event_chain(request_id, session, tenant_id=tenant_id)
        assert res["valid"] is False
        assert "Цепочка нарушена: ожидался previous_hash=" in res["reason"]
