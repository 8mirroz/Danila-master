import pytest
from fastapi.testclient import TestClient
from main import app
from rbac import create_signed_token
from models import PartRequest
from database import engine
from sqlmodel import Session

client = TestClient(app)
SECRET = "test-token"  # from conftest.py

@pytest.fixture(autouse=True)
def setup_test_requests():
    from sqlmodel import SQLModel
    # Make sure all tables are registered and created
    from models import PartRequest, SupplierOffer, RequestEvent, MatchEvidence, ERPSyncLog, GoldenSample  # noqa
    from suppliers import Supplier, SupplierCatalogItem, Invoice  # noqa
    SQLModel.metadata.create_all(engine)
    
    # Insert test data into test_database.db
    with Session(engine) as session:
        # Clear existing requests
        from sqlmodel import delete
        session.exec(delete(PartRequest))
        
        req_a = PartRequest(
            request_id="REQ-TENANT-A-01",
            tenant_id="tenant_A",
            source="api",
            source_text="Need brake pads for BMW A",
            status="pending"
        )
        req_b = PartRequest(
            request_id="REQ-TENANT-B-01",
            tenant_id="tenant_B",
            source="api",
            source_text="Need oil filter for Toyota B",
            status="pending"
        )
        session.add(req_a)
        session.add(req_b)
        session.commit()
    yield

def test_signed_token_isolation():
    # Token signed specifically for tenant_A, role manager
    token_a = create_signed_token("tenant_A", "manager", SECRET)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 1. tenant_A can view own requests
    res = client.get("/api/requests", headers=headers_a)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["request_id"] == "REQ-TENANT-A-01"

    # 2. tenant_A cannot view tenant_B request (returns 404 or 403, here 404 is preferred)
    res_b = client.get("/api/requests/REQ-TENANT-B-01", headers=headers_a)
    assert res_b.status_code in (404, 403)

def test_header_spoofing_prevention():
    # Token is signed for tenant_A, but client sends X-Tenant-ID: tenant_B
    token_a = create_signed_token("tenant_A", "manager", SECRET)
    headers = {
        "Authorization": f"Bearer {token_a}",
        "X-Tenant-ID": "tenant_B"
    }
    
    # System must ignore X-Tenant-ID and use tenant_A from signed claims
    res = client.get("/api/requests", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["request_id"] == "REQ-TENANT-A-01" # Only tenant_A requests returned!

def test_cross_tenant_mutation_prevention():
    token_a = create_signed_token("tenant_A", "manager", SECRET)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Try to transition tenant_B's request state
    payload = {"target_state": "processing", "reason": "hack", "actor_id": "manager"}
    res = client.post("/api/requests/REQ-TENANT-B-01/transition", headers=headers_a, json=payload)
    assert res.status_code in (404, 403)

def test_role_escalation_prevention():
    # manager role cannot delete or manage users/system configurations (if such routes exist)
    # Let's test that an unprivileged endpoint transitions correctly, but RoleChecker prevents access if restricted.
    # In partsops-ai-manager, RoleChecker is used in delete/manage endpoints if defined.
    # Let's verify that a bad role token (e.g. invalid_role) is rejected
    token_bad = create_signed_token("tenant_A", "invalid_role", SECRET)
    res = client.get("/api/requests", headers={"Authorization": f"Bearer {token_bad}"})
    assert res.status_code == 403  # invalid role normalized/rejected

def test_unauthenticated_blocked():
    # Attempt request without authorization header
    res = client.get("/api/requests")
    assert res.status_code == 401
