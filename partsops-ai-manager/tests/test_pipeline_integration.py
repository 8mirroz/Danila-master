"""Integration tests for the multi-agent pipeline."""
import pytest
import json
from datetime import datetime

from fastapi.testclient import TestClient

from main import app
from database import engine
from sqlmodel import SQLModel, Session, select
from models import PartRequest, RequestState, EventType, ApprovalTicket, OutboundMessage
from suppliers import seed_database

client = TestClient(app)

AUTH_HEADERS = {
    "Authorization": "Bearer test-token",
    "X-Tenant-ID": "default",
}
APPROVAL_HEADERS = {**AUTH_HEADERS, "X-User-Role": "admin"}


@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_database(session)
    yield
    SQLModel.metadata.drop_all(engine)


def approve_sync_and_send(request_id: str) -> None:
    """Advance an approved quote through explicit invoice, ERP and delivery commands."""
    assert client.post(
        f"/api/requests/{request_id}/approve",
        json={"action": "approve"},
        headers=APPROVAL_HEADERS,
    ).status_code == 200
    assert client.post(
        f"/api/erp/invoice/{request_id}", headers=APPROVAL_HEADERS
    ).status_code == 200
    sync = client.post(
        f"/api/erp/sync/{request_id}",
        json={"dry_run": True},
        headers=APPROVAL_HEADERS,
    )
    assert sync.status_code == 200
    assert sync.json()["request_status"] == "ERP_SYNCED"
    sent = client.post(
        f"/api/delivery/send/{request_id}",
        json={"channel": "email", "recipient": "buyer@example.com", "dry_run": True},
        headers=APPROVAL_HEADERS,
    )
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"


def test_full_pipeline_runs_successfully():
    """Full pipeline: intake -> processing -> delivery -> reporting."""
    response = client.post(
        "/api/pipeline/run",
        json={
            "source": "telegram",
            "text": "Тормозные колодки для BMW X5 2018 VIN: WBAXX5C55JWE12345",
            "customer_name": "Иван",
            "customer_phone": "+79991234567",
            "customer_email": "ivan@example.com",
            "priority": "normal",
            "metadata": {
                "source_metadata": {"message_id": 1, "chat_id": 100, "user_id": 100}
            },
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["request_id"] is not None
    assert set(data["phases"].keys()) == {"intake", "processing", "delivery", "reporting"}


def test_pipeline_creates_request_with_original_ref():
    """Pipeline must store the original request reference."""
    response = client.post(
        "/api/pipeline/run",
        json={
            "source": "telegram",
            "text": "Воздушный фильтр BMW X3",
            "customer_name": "Петр",
            "customer_phone": "+79990000000",
            "customer_email": "petr@example.com",
            "metadata": {"source_metadata": {"message_id": 2, "chat_id": 200, "user_id": 200}},
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    request_id = response.json()["request_id"]

    with Session(engine) as session:
        request = session.exec(
            select(PartRequest).where(PartRequest.request_id == request_id)
        ).first()
        assert request is not None
        assert request.raw_input_ref is not None
        assert "tg:msg" in request.raw_input_ref


def test_pipeline_status_flow():
    """A completed pipeline stops at an auditable operator-approval gate."""
    response = client.post(
        "/api/pipeline/run",
        json={
            "source": "email",
            "text": "Масляный фильтр для BMW",
            "customer_name": "Алексей",
            "customer_email": "alex@example.com",
        },
        headers=AUTH_HEADERS,
    )
    request_id = response.json()["request_id"]

    status_resp = client.get(
        f"/api/pipeline/status/{request_id}", headers=AUTH_HEADERS
    )
    assert status_resp.json()["status"] == "READY_FOR_APPROVAL"

    tickets_resp = client.get(
        f"/api/requests/{request_id}/approval-tickets", headers=AUTH_HEADERS
    )
    assert tickets_resp.status_code == 200
    assert tickets_resp.json()[0]["status"] == "pending"


def test_approval_workflow_issues_quote_without_fake_erp_sync():
    """Approval issues the quote but never manufactures an ERP sync state."""
    # Run pipeline
    run_resp = client.post(
        "/api/pipeline/run",
        json={
            "source": "telegram",
            "text": "Тормозные колодки BMW X5",
            "customer_name": "Олег",
            "customer_phone": "+7999222333",
            "customer_email": "oleg@example.com",
            "metadata": {"source_metadata": {"message_id": 3, "chat_id": 300, "user_id": 300}},
        },
        headers=AUTH_HEADERS,
    )
    request_id = run_resp.json()["request_id"]

    # Approve
    approve_resp = client.post(
        f"/api/requests/{request_id}/approve",
        json={
            "action": "approve",
            "comment": "Одобрено",
            "actor_id": "untrusted-client-identity",
        },
        headers=APPROVAL_HEADERS,
    )
    assert approve_resp.status_code == 200
    approve_data = approve_resp.json()
    assert approve_data["success"] is True
    assert "Quote issued" in approve_data["message"]

    # Quote delivery and ERP export are separate explicit operations.
    status_resp = client.get(
        f"/api/pipeline/status/{request_id}", headers=AUTH_HEADERS
    )
    assert status_resp.json()["status"] == "APPROVED"

    invoice_resp = client.post(
        f"/api/erp/invoice/{request_id}", headers=APPROVAL_HEADERS
    )
    assert invoice_resp.status_code == 200
    assert invoice_resp.json()["status"] == "DRAFT_CREATED"
    assert client.get(
        f"/api/pipeline/status/{request_id}", headers=AUTH_HEADERS
    ).json()["status"] == "INVOICE_DRAFTED"

    events_resp = client.get(
        f"/api/requests/{request_id}/events", headers=AUTH_HEADERS
    )
    transitions = {
        event["payload"].get("to")
        for event in events_resp.json()["events"]
        if event["event_type"] == EventType.STATE_CHANGED
    }
    assert RequestState.ERP_SYNCING not in transitions
    assert RequestState.ERP_SYNCED not in transitions

    # Approval ticket must be stored
    tickets_resp = client.get(
        f"/api/requests/{request_id}/approval-tickets", headers=AUTH_HEADERS
    )
    tickets = tickets_resp.json()
    assert len(tickets) >= 1
    assert tickets[0]["status"] == "approved"
    assert tickets[0]["decided_by"] == "operator:admin"


def test_manager_cannot_approve_pricing():
    """Only finance and admins can approve a pricing decision."""
    run_resp = client.post(
        "/api/pipeline/run",
        json={
            "source": "telegram",
            "text": "Тормозные колодки BMW X5",
            "customer_name": "Role proof",
        },
        headers=AUTH_HEADERS,
    )
    request_id = run_resp.json()["request_id"]

    response = client.post(
        f"/api/requests/{request_id}/approve",
        json={"action": "approve"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Pricing approval requires finance or admin role"


def test_approval_issues_versioned_quote_before_delivery():
    """A real approval must snapshot the selected offer and make a quote exportable."""
    run_resp = client.post(
        "/api/pipeline/run",
        json={
            "source": "telegram",
            "text": "Тормозные колодки BMW X5",
            "customer_name": "Quote buyer",
            "customer_phone": "+7999222333",
            "customer_email": "quote@example.com",
            "metadata": {"source_metadata": {"message_id": 31, "chat_id": 3100, "user_id": 3100}},
        },
        headers=AUTH_HEADERS,
    )
    assert run_resp.status_code == 200
    request_id = run_resp.json()["request_id"]

    approval = client.post(
        f"/api/requests/{request_id}/approve",
        json={"action": "approve", "comment": "Quote approved"},
        headers=APPROVAL_HEADERS,
    )
    assert approval.status_code == 200
    quote = approval.json()["quote"]
    assert quote["request_id"] == request_id
    assert quote["version"] == 1
    assert quote["selected_offers"]

    assert client.get(
        f"/api/quotes/{quote['quote_id']}/export/xlsx", headers=AUTH_HEADERS
    ).headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument"
    )
    assert client.get(
        f"/api/quotes/{quote['quote_id']}/export/pdf", headers=AUTH_HEADERS
    ).headers["content-type"].startswith("application/pdf")


def test_reject_workflow():
    """Rejecting a request should move to CLIENT_REJECTED."""
    run_resp = client.post(
        "/api/pipeline/run",
        json={
            "source": "crm",
            "text": "Тормозные колодки BMW",
            "customer_name": "CRM Клиент",
            "customer_phone": "+7999555666",
            "customer_email": "crm@example.com",
        },
        headers=AUTH_HEADERS,
    )
    request_id = run_resp.json()["request_id"]

    reject_resp = client.post(
        f"/api/requests/{request_id}/approve",
        json={"action": "reject", "comment": "Цена too high"},
        headers=APPROVAL_HEADERS,
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["new_status"] == "CLIENT_REJECTED"

    status_resp = client.get(
        f"/api/pipeline/status/{request_id}", headers=AUTH_HEADERS
    )
    assert status_resp.json()["status"] == "CLIENT_REJECTED"


def test_client_portal_tracking_token_flow():
    """Client can track order via token, accept/reject offers."""
    run_resp = client.post(
        "/api/pipeline/run",
        json={
            "source": "telegram",
            "text": "Передний амортизатор BMW X5",
            "customer_name": "Максим",
            "customer_phone": "+79997778899",
            "customer_email": "max@example.com",
            "metadata": {"source_metadata": {"message_id": 4, "chat_id": 400, "user_id": 400}},
        },
        headers=AUTH_HEADERS,
    )
    request_id = run_resp.json()["request_id"]

    approve_sync_and_send(request_id)

    # Generate tracking token
    token_resp = client.post(
        f"/api/requests/{request_id}/generate-tracking-token", headers=AUTH_HEADERS
    )
    assert token_resp.status_code == 200
    token = token_resp.json()["tracking_token"]

    # Track request
    track_resp = client.get(f"/api/client/track/{token}", headers=AUTH_HEADERS)
    assert track_resp.status_code == 200
    assert track_resp.json()["status"] == "SENT_TO_CLIENT"

    # Accept offer
    accept_resp = client.post(
        f"/api/client/track/{token}/accept", headers=AUTH_HEADERS
    )
    assert accept_resp.json()["ok"] is True
    assert accept_resp.json()["new_status"] == "PAID"

    status_resp = client.get(
        f"/api/pipeline/status/{request_id}", headers=AUTH_HEADERS
    )
    assert status_resp.json()["status"] == "PAID"


def test_client_portal_reject_flow():
    """Client can reject offer via tracking token."""
    run_resp = client.post(
        "/api/pipeline/run",
        json={
            "source": "email",
            "text": "Тормозные колодки BMW X5",
            "customer_name": "Николай",
            "customer_email": "nik@example.com",
        },
        headers=AUTH_HEADERS,
    )
    request_id = run_resp.json()["request_id"]

    approve_sync_and_send(request_id)

    token_resp = client.post(
        f"/api/requests/{request_id}/generate-tracking-token", headers=AUTH_HEADERS
    )
    token = token_resp.json()["tracking_token"]

    reject_resp = client.post(
        f"/api/client/track/{token}/reject",
        json={"reason": "Нашел дешевле"},
        headers=AUTH_HEADERS,
    )
    assert reject_resp.json()["ok"] is True
    assert reject_resp.json()["new_status"] == "CLIENT_REJECTED"


def test_delivery_logs_stored():
    """Outbound delivery messages must be persisted and retrievable."""
    run_resp = client.post(
        "/api/pipeline/run",
        json={
            "source": "telegram",
            "text": "Тормозной диск BMW X5",
            "customer_name": "Дмитрий",
            "customer_phone": "+79990001122",
            "customer_email": "dima@example.com",
            "metadata": {"source_metadata": {"message_id": 5, "chat_id": 500, "user_id": 500}},
        },
        headers=AUTH_HEADERS,
    )
    request_id = run_resp.json()["request_id"]

    approve_sync_and_send(request_id)

    delivery_resp = client.get(
        f"/api/delivery/status/{request_id}", headers=AUTH_HEADERS
    )
    logs = delivery_resp.json()
    assert isinstance(logs, list)
    assert len(logs) >= 1
    assert logs[0]["channel"] == "email"


def test_generate_tracking_token_endpoint_creates_token():
    """Endpoint must create and store a tracking token."""
    run_resp = client.post(
        "/api/pipeline/run",
        json={
            "source": "crm",
            "text": "Тормозные колодки BMW",
            "customer_name": "Сергей",
            "customer_email": "sergey@example.com",
        },
        headers=AUTH_HEADERS,
    )
    request_id = run_resp.json()["request_id"]

    token_resp = client.post(
        f"/api/requests/{request_id}/generate-tracking-token", headers=AUTH_HEADERS
    )
    assert token_resp.status_code == 200
    data = token_resp.json()
    assert data["success"] is True
    assert "tracking_token" in data
    assert data["tracking_url"].endswith(data["tracking_token"])

    with Session(engine) as session:
        request = session.exec(
            select(PartRequest).where(PartRequest.request_id == request_id)
        ).first()
        assert request.tracking_token == data["tracking_token"]
        assert request.tracking_token_expires_at is not None
