import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool
from models import PartRequest, GoldenSample, EventType, RequestEvent
from learning import save_manual_correction, calculate_system_accuracy
import json


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_save_manual_correction(db_session: Session):
    # Setup test request
    req = PartRequest(
        request_id="REQ-LEARN-1",
        tenant_id="tenant-1",
        source="manual",
        status="MANUAL_REVIEW"
    )
    db_session.add(req)
    db_session.commit()

    # Call the learning loop function
    sample = save_manual_correction(
        session=db_session,
        request_id="REQ-LEARN-1",
        tenant_id="tenant-1",
        source_text="тормозные колодки",
        corrected_parts_json='[{"name": "Тормозные колодки", "quantity": 1}]',
        correction_reason_tags=["wrong_quantity", "wrong_brand"],
        user_id="admin-test",
        corrected_vehicle_json='{"make": "BMW"}'
    )

    assert sample.sample_id.startswith("GLD-")
    assert sample.request_id == "REQ-LEARN-1"
    assert sample.approved_by == "admin-test"
    assert "wrong_quantity" in sample.correction_reason_tags

    # Verify event was emitted
    event = db_session.exec(
        select(RequestEvent).where(RequestEvent.event_type == EventType.GOLDEN_SAMPLE_CREATED)
    ).first()
    
    assert event is not None
    assert event.request_id == "REQ-LEARN-1"
    payload = json.loads(event.payload_json)
    assert payload["sample_id"] == sample.sample_id


def test_calculate_system_accuracy(db_session: Session):
    # Setup 2 PAID requests, one with correction, one without
    req1 = PartRequest(request_id="REQ-1", tenant_id="tenant-1", source="manual", status="PAID")
    req2 = PartRequest(request_id="REQ-2", tenant_id="tenant-1", source="manual", status="PAID")
    db_session.add_all([req1, req2])
    db_session.commit()

    # Correction only for REQ-1
    save_manual_correction(
        session=db_session,
        request_id="REQ-1",
        tenant_id="tenant-1",
        source_text="test",
        corrected_parts_json="[]",
        correction_reason_tags=["wrong_vin"],
        user_id="admin"
    )

    metrics = calculate_system_accuracy(db_session, "tenant-1")

    assert metrics["total_requests"] == 2
    assert metrics["manual_corrections"] == 1
    assert metrics["accuracy_percent"] == 50.0
    assert metrics["top_correction_reasons"][0][0] == "wrong_vin"
    
    # Check isolation for another tenant
    metrics_tenant2 = calculate_system_accuracy(db_session, "tenant-2")
    assert metrics_tenant2["total_requests"] == 0
    assert metrics_tenant2["accuracy_percent"] == 100.0
