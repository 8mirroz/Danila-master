from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select
import pytest

from database import engine
from main import app
from suppliers import seed_database

client = TestClient(app, headers={"Authorization": "Bearer test-token"})

@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_database(session)
    yield

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data

def test_create_request_success():
    payload = {
        "source": "TEST_MOCK",
        "text": "Мне нужны тормозные колодки на X5",
        "customer_name": "Test User"
    }
    response = client.post("/api/requests", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "request" in data
    assert "agent_trace" in data
    
    req = data["request"]
    assert req["status"] == "PART_EXTRACTION"
    assert "REQ-" in req["request_id"]
    
    trace = data["agent_trace"]
    assert trace["validation_status"] == "PASSED"
    
def test_create_request_failure():
    payload = {
        "source": "TEST_MOCK",
        "text": "какой-то мусор вместо запчастей",
        "customer_name": "Test User"
    }
    response = client.post("/api/requests", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    req = data["request"]
    assert req["status"] == "NEEDS_CLARIFICATION"
    
    trace = data["agent_trace"]
    assert trace["validation_status"] == "FAILED"

def test_create_request_with_typos():
    """TC-007: Parser should handle typos like 'тармозные калодки'."""
    payload = {
        "source": "TEST_MOCK",
        "text": "тармозные калодки бмв х5 передние",
        "customer_name": "Дмитрий Смирнов"
    }
    response = client.post("/api/requests", json=payload)
    assert response.status_code == 200
    data = response.json()
    req = data["request"]
    assert req["status"] in ("PART_EXTRACTION", "NEEDS_CLARIFICATION")

def test_get_suppliers():
    response = client.get("/api/suppliers")
    assert response.status_code == 200
    suppliers = response.json()
    assert len(suppliers) >= 5

def test_catalog_search():
    response = client.get("/api/catalog/search?q=тормозные колодки BMW")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    assert data["matches"][0]["score"] > 50

def test_invoice_generation():
    # 1. Create a request and move it through the approval path
    payload = {
        "source": "TEST_MOCK",
        "text": "Нужны тормозные колодки на BMW X5",
        "customer_name": "Invoice Test User"
    }
    resp = client.post("/api/requests", json=payload)
    assert resp.status_code == 200
    request_id = resp.json()["request"]["request_id"]

    transition_path = [
        "MATCHING",
        "SUPPLIER_SEARCH",
        "OFFER_RANKING",
        "PRICING_REVIEW",
        "READY_FOR_APPROVAL",
        "APPROVED",
    ]
    for target_state in transition_path:
        step_response = client.post(
            f"/api/requests/{request_id}/transition",
            json={"target_state": target_state, "reason": f"test {target_state}", "actor_id": "admin"},
        )
        assert step_response.status_code == 200

    # 2. Generate invoice after approval
    resp2 = client.post(
        f"/api/erp/invoice/{request_id}",
        json={
            "logistics_cost": 500,
            "target_margin_override": 0.15,
            "urgency_level": "normal",
        },
    )
    assert resp2.status_code == 200
    invoice = resp2.json()
    assert invoice["status"] == "DRAFT_CREATED"
    assert "invoice" in invoice
    assert invoice["invoice"]["total"] > 0
    assert len(invoice["invoice"]["items"]) > 0


def test_invoice_requires_approval():
    payload = {
        "source": "TEST_MOCK",
        "text": "Нужны тормозные колодки на BMW X5",
        "customer_name": "Invoice Gate Test"
    }
    resp = client.post("/api/requests", json=payload)
    assert resp.status_code == 200
    request_id = resp.json()["request"]["request_id"]

    resp2 = client.post(f"/api/erp/invoice/{request_id}")
    assert resp2.status_code == 422


def test_tenant_isolation_for_requests_and_invoices():
    payload_a = {
        "source": "TEST_MOCK",
        "text": "Нужны тормозные колодки на BMW X5",
        "customer_name": "Tenant A"
    }
    payload_b = {
        "source": "TEST_MOCK",
        "text": "Нужны тормозные колодки на Toyota Camry",
        "customer_name": "Tenant B"
    }

    resp_a = client.post("/api/requests", json=payload_a, headers={"X-Tenant-ID": "tenant-a"})
    resp_b = client.post("/api/requests", json=payload_b, headers={"X-Tenant-ID": "tenant-b"})
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200

    request_id_a = resp_a.json()["request"]["request_id"]
    request_id_b = resp_b.json()["request"]["request_id"]

    requests_a = client.get("/api/requests", headers={"X-Tenant-ID": "tenant-a"}).json()
    requests_b = client.get("/api/requests", headers={"X-Tenant-ID": "tenant-b"}).json()

    assert any(item["request_id"] == request_id_a for item in requests_a)
    assert all(item["request_id"] != request_id_b for item in requests_a)
    assert any(item["request_id"] == request_id_b for item in requests_b)
    assert all(item["request_id"] != request_id_a for item in requests_b)
