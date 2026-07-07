from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel
import pytest

from database import engine
from main import app
from models import PartRequest, RequestState
from suppliers import Supplier, seed_database

# Client configured with valid API token
client_a = TestClient(app, headers={"Authorization": "Bearer test-token", "X-Tenant-ID": "tenant-a"})
client_b = TestClient(app, headers={"Authorization": "Bearer test-token", "X-Tenant-ID": "tenant-b"})
client_unauthorized = TestClient(app, headers={"X-Tenant-ID": "tenant-a"})  # No token, will fall to default tenant


@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_database(session)
    yield


def test_tenant_isolation_on_requests():
    # 1. Create request in tenant-a
    payload = {
        "source": "TEST_ISOLATION",
        "text": "Тормозные диски BMW",
        "customer_name": "Tenant A Customer",
    }
    create_resp = client_a.post("/api/requests", json=payload)
    assert create_resp.status_code == 200
    req_id = create_resp.json()["request"]["request_id"]

    # 2. Verify client_a can read it
    read_resp_a = client_a.get(f"/api/requests/{req_id}")
    assert read_resp_a.status_code == 200
    assert read_resp_a.json()["customer_name"].startswith("Tenant A")

    # 3. Verify client_b CANNOT read it (should get 404 Request not found)
    read_resp_b = client_b.get(f"/api/requests/{req_id}")
    assert read_resp_b.status_code == 404

    # 4. Verify client_b CANNOT list it
    list_resp_b = client_b.get("/api/requests")
    assert list_resp_b.status_code == 200
    assert len(list_resp_b.json()) == 0


def test_tenant_isolation_on_suppliers():
    # 1. Create supplier in tenant-a
    payload = {
        "supplier_id": "SUP-TENANT-A",
        "name": "Supplier for A",
        "email": "supplier-a@example.com",
    }
    create_resp = client_a.post("/api/suppliers", json=payload)
    assert create_resp.status_code == 200

    # 2. Verify client_a can read it
    read_resp_a = client_a.get("/api/suppliers/SUP-TENANT-A")
    assert read_resp_a.status_code == 200
    assert read_resp_a.json()["name"] == "Supplier for A"

    # 3. Verify client_b CANNOT read it
    read_resp_b = client_b.get("/api/suppliers/SUP-TENANT-A")
    assert read_resp_b.status_code == 404


def test_token_required_for_tenant_access():
    # Without authorization header, request is forced to DEFAULT_TENANT
    # Let's create request using client_a (tenant-a)
    payload = {
        "source": "TEST_ISOLATION",
        "text": "Тормозные диски BMW",
        "customer_name": "Tenant A Customer",
    }
    create_resp = client_a.post("/api/requests", json=payload)
    assert create_resp.status_code == 200
    req_id = create_resp.json()["request"]["request_id"]

    # Trying to read from tenant-a without token returns 401 (unauthorized because PARTSOPS_API_TOKEN is configured)
    read_resp = client_unauthorized.get(f"/api/requests/{req_id}", headers={"X-Tenant-ID": "tenant-a"})
    assert read_resp.status_code == 401
