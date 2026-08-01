import json

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from database import engine
from main import app
from models import GoldenSample, PartRequest, RequestState

client = TestClient(app)
HEADERS = {
    "Authorization": "Bearer test-token",
    "X-Tenant-ID": "analytics-tenant",
    "X-User-Role": "admin",
}


def setup_function():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def teardown_function():
    SQLModel.metadata.drop_all(engine)


def test_automation_rate_counts_only_ready_unmodified_positions():
    with Session(engine) as session:
        session.add(
            PartRequest(
                request_id="REQ-AUTO",
                tenant_id="analytics-tenant",
                source="test",
                status=RequestState.APPROVED,
                parts_json=json.dumps([{"name": "A"}, {"name": "B"}]),
            )
        )
        session.add(
            PartRequest(
                request_id="REQ-PENDING",
                tenant_id="analytics-tenant",
                source="test",
                status=RequestState.PART_EXTRACTION,
                parts_json=json.dumps([{"name": "C"}]),
            )
        )
        session.commit()
    response = client.get("/api/analytics/quoteops", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["automation_rate"] == 66.7
    assert response.json()["automated_positions"] == 2


def test_automation_rate_and_pending_approvals_include_ready_for_approval():
    with Session(engine) as session:
        session.add(
            PartRequest(
                request_id="REQ-READY-FOR-APPROVAL",
                tenant_id="analytics-tenant",
                source="test",
                status=RequestState.READY_FOR_APPROVAL,
                parts_json=json.dumps([{"name": "A"}, {"name": "B"}]),
            )
        )
        session.add(
            PartRequest(
                request_id="REQ-PRICING-REVIEW",
                tenant_id="analytics-tenant",
                source="test",
                status=RequestState.PRICING_REVIEW,
                parts_json=json.dumps([{"name": "C"}]),
            )
        )
        session.commit()

    response = client.get("/api/analytics/quoteops", headers=HEADERS)

    assert response.status_code == 200
    assert response.json()["automated_positions"] == 2
    assert response.json()["automation_rate"] == 66.7
    assert response.json()["ready_for_approval_requests"] == 1
    assert response.json()["pending_approvals"] == 1


def test_automation_rate_excludes_only_attributed_manual_positions():
    with Session(engine) as session:
        session.add(
            PartRequest(
                request_id="REQ-PARTIAL-CORRECTION",
                tenant_id="analytics-tenant",
                source="test",
                status=RequestState.APPROVED,
                parts_json=json.dumps([{"name": "A"}, {"name": "B"}, {"name": "C"}]),
            )
        )
        session.add(
            GoldenSample(
                sample_id="GLD-PARTIAL",
                request_id="REQ-PARTIAL-CORRECTION",
                tenant_id="analytics-tenant",
                source_text="A, B, C",
                corrected_parts_json=json.dumps([{"name": "A*"}, {"name": "B"}, {"name": "C"}]),
                corrected_position_indexes_json=json.dumps([0]),
            )
        )
        session.commit()

    response = client.get("/api/analytics/quoteops", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["automated_positions"] == 2
    assert response.json()["manually_corrected_positions"] == 1
    assert response.json()["automation_rate"] == 66.7


def test_automation_rate_treats_legacy_unattributed_corrections_conservatively():
    with Session(engine) as session:
        session.add(
            PartRequest(
                request_id="REQ-LEGACY-CORRECTION",
                tenant_id="analytics-tenant",
                source="test",
                status=RequestState.APPROVED,
                parts_json=json.dumps([{"name": "A"}, {"name": "B"}]),
            )
        )
        session.add(
            GoldenSample(
                sample_id="GLD-LEGACY",
                request_id="REQ-LEGACY-CORRECTION",
                tenant_id="analytics-tenant",
                source_text="A, B",
                corrected_parts_json=json.dumps([{"name": "A*"}, {"name": "B"}]),
            )
        )
        session.commit()

    response = client.get("/api/analytics/quoteops", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["automated_positions"] == 0
    assert response.json()["unattributed_manual_correction_requests"] == 1


def test_manual_correction_flow_records_position_attribution_for_automation_rate():
    with Session(engine) as session:
        session.add(
            PartRequest(
                request_id="REQ-CORRECTION-FLOW",
                tenant_id="analytics-tenant",
                source="test",
                status=RequestState.APPROVED,
                parts_json=json.dumps([{"name": "A"}, {"name": "B"}]),
            )
        )
        session.commit()

    correction = client.post(
        "/api/requests/REQ-CORRECTION-FLOW/correction",
        headers=HEADERS,
        json={
            "source_text": "A, B",
            "corrected_parts_json": json.dumps([{"name": "A*"}, {"name": "B"}]),
            "corrected_position_indexes": [0],
            "correction_reason_tags": ["wrong_brand"],
        },
    )
    assert correction.status_code == 200

    response = client.get("/api/analytics/quoteops", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["automated_positions"] == 1
    assert response.json()["manually_corrected_positions"] == 1


def test_manual_correction_rejects_position_indexes_outside_request():
    with Session(engine) as session:
        session.add(
            PartRequest(
                request_id="REQ-INVALID-CORRECTION",
                tenant_id="analytics-tenant",
                source="test",
                status=RequestState.APPROVED,
                parts_json=json.dumps([{"name": "A"}]),
            )
        )
        session.commit()

    correction = client.post(
        "/api/requests/REQ-INVALID-CORRECTION/correction",
        headers=HEADERS,
        json={
            "source_text": "A",
            "corrected_parts_json": json.dumps([{"name": "A*"}]),
            "corrected_position_indexes": [1],
        },
    )
    assert correction.status_code == 422
