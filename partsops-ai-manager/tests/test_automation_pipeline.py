"""
Tests for Full-Cycle Automation Pipeline (Phase 8)
"""
import pytest
import json
from datetime import datetime, timedelta
from sqlmodel import SQLModel, Session, select

from database import engine
from models import PartRequest, RequestState, SupplierReliabilityLog, PriceHistoryLedger
from suppliers import Supplier, SupplierCatalogItem
from policy_engine import policy_engine
from app.automation.context import AutomationContext
from app.automation.runner import run_job
from app.automation.registry import get_job
from agents import full_pipeline_graph

@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


def test_auto_advance_policy_logic():
    with Session(engine) as session:
        # Create a request that matches all auto-advance criteria
        req_ok = PartRequest(
            request_id="REQ-AUTO-OK",
            tenant_id="default",
            source="manual",
            status=RequestState.PART_EXTRACTION,
            customer_name="John Doe",
            customer_phone_masked="+7 (999) ***-45-67",
            customer_email_masked="j***@example.com",
            parts_json=json.dumps([{"name": "Filter", "match_score": 85.0, "quantity": 1}]),
            pricing_evidence_json=json.dumps({
                "line_items": [
                    {"part_name": "Filter", "margin": 0.25, "supplier_reliability": 0.90}
                ]
            }),
        )
        
        # Create a request that fails due to low match score
        req_bad_score = PartRequest(
            request_id="REQ-AUTO-BAD-SCORE",
            tenant_id="default",
            source="manual",
            status=RequestState.PART_EXTRACTION,
            customer_name="John Doe",
            customer_phone_masked="+7 (999) ***-45-67",
            customer_email_masked="j***@example.com",
            parts_json=json.dumps([{"name": "Filter", "match_score": 60.0, "quantity": 1}]),
            pricing_evidence_json=json.dumps({
                "line_items": [
                    {"part_name": "Filter", "margin": 0.25, "supplier_reliability": 0.90}
                ]
            }),
        )
        
        # Create a request that fails due to high margin
        req_bad_margin = PartRequest(
            request_id="REQ-AUTO-BAD-MARGIN",
            tenant_id="default",
            source="manual",
            status=RequestState.PART_EXTRACTION,
            customer_name="John Doe",
            customer_phone_masked="+7 (999) ***-45-67",
            customer_email_masked="j***@example.com",
            parts_json=json.dumps([{"name": "Filter", "match_score": 85.0, "quantity": 1}]),
            pricing_evidence_json=json.dumps({
                "line_items": [
                    {"part_name": "Filter", "margin": 0.55, "supplier_reliability": 0.90}
                ]
            }),
        )
        
        session.add(req_ok)
        session.add(req_bad_score)
        session.add(req_bad_margin)
        session.commit()
        
        assert policy_engine.auto_advance_policy(req_ok, session) is True
        assert policy_engine.auto_advance_policy(req_bad_score, session) is False
        assert policy_engine.auto_advance_policy(req_bad_margin, session) is False


def test_auto_advance_job():
    context = AutomationContext(
        tenant_id="default",
        correlation_id="CORR-AUTO-JOB",
        actor_id="scheduler",
        dry_run=False,
    )
    
    with Session(engine) as session:
        # Request satisfying criteria
        req = PartRequest(
            request_id="REQ-JOB-OK",
            tenant_id="default",
            source="manual",
            status=RequestState.PART_EXTRACTION,
            customer_name="John Doe",
            customer_phone_masked="+7 (999) ***-45-67",
            customer_email_masked="j***@example.com",
            parts_json=json.dumps([{"name": "Filter", "match_score": 85.0, "quantity": 1}]),
            pricing_evidence_json=json.dumps({
                "line_items": [
                    {"part_name": "Filter", "margin": 0.25, "supplier_reliability": 0.90}
                ]
            }),
        )
        session.add(req)
        session.commit()
        
        res = run_job(session, "auto_advance", context)
        assert res["ok"] is True
        assert res["result"]["advanced_count"] == 1
        
        # Verify req was moved to READY_FOR_APPROVAL
        session.refresh(req)
        assert req.status == RequestState.READY_FOR_APPROVAL


def test_sla_watchdog_job():
    context = AutomationContext(
        tenant_id="default",
        correlation_id="CORR-SLA",
        actor_id="scheduler",
        dry_run=False,
    )
    
    with Session(engine) as session:
        # Request stalled in MATCHING > 5 mins
        req1 = PartRequest(
            request_id="REQ-SLA-1",
            tenant_id="default",
            source="manual",
            status=RequestState.MATCHING,
            customer_name="John Doe",
        )
        session.add(req1)
        session.commit()
        
        # Manually backdate updated_at
        session.exec(__import__('sqlmodel').text("UPDATE partrequest SET updated_at = datetime('now', '-20 minutes') WHERE request_id = 'REQ-SLA-1'"))
        session.commit()
        
        res = run_job(session, "sla_watchdog", context)
        assert res["ok"] is True
        assert res["result"]["alerts_triggered"] >= 1


def test_supplier_recalc_job():
    context = AutomationContext(
        tenant_id="default",
        correlation_id="CORR-RECALC",
        actor_id="scheduler",
        dry_run=False,
    )
    
    with Session(engine) as session:
        supplier = Supplier(
            supplier_id="SUP-RECALC",
            name="EuroParts Recalc",
            contact_person="Becker",
            email="becker@example.com",
            phone="123",
            city="Munich",
            specialization="Brakes",
            reliability_score=0.5,
        )
        session.add(supplier)
        
        log1 = SupplierReliabilityLog(
            supplier_id="SUP-RECALC",
            reliability_score=0.9,
            logged_at=datetime.utcnow() - timedelta(days=5),
        )
        log2 = SupplierReliabilityLog(
            supplier_id="SUP-RECALC",
            reliability_score=0.8,
            logged_at=datetime.utcnow() - timedelta(days=10),
        )
        session.add(log1)
        session.add(log2)
        session.commit()
        
        res = run_job(session, "supplier_recalc", context)
        assert res["ok"] is True
        assert res["result"]["recalculated_count"] == 1
        
        session.refresh(supplier)
        assert abs(supplier.reliability_score - 0.85) < 0.01


def test_price_snapshot_job():
    context = AutomationContext(
        tenant_id="default",
        correlation_id="CORR-SNAPSHOT",
        actor_id="scheduler",
        dry_run=False,
    )
    
    with Session(engine) as session:
        supplier = Supplier(
            supplier_id="SUP-1",
            name="EuroParts",
            contact_person="Becker",
            email="becker@example.com",
            phone="123",
            city="Munich",
            specialization="Brakes",
            reliability_score=0.5,
        )
        session.add(supplier)
        session.commit()
        
        item = SupplierCatalogItem(
            tenant_id="default",
            catalog_id="CAT-123",
            supplier_id="SUP-1",
            part_name="Brake Pads",
            oem_number="OEM-123",
            brand="Brembo",
            price=1500.0,
            stock_qty=10,
        )
        session.add(item)
        session.commit()
        
        res = run_job(session, "price_snapshot", context)
        assert res["ok"] is True
        assert res["result"]["recorded_count"] == 1
        
        ledger_entries = session.exec(select(PriceHistoryLedger)).all()
        assert len(ledger_entries) == 1
        assert ledger_entries[0].price == 1500.0


def test_full_pipeline_graph_initializes():
    assert full_pipeline_graph is not None
    # We can check that the nodes exist in the graph
    nodes = full_pipeline_graph.nodes
    assert "classifier" in nodes
    assert "vin_inspector" in nodes
    assert "extractor" in nodes
    assert "scatter_gather" in nodes
    assert "pricing_guard" in nodes
    assert "gates_checker" in nodes
