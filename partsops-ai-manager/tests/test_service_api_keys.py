from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session

from database import engine
from main import app
from models import PartRequest, RequestState

client = TestClient(app)
HEADERS = {
    "Authorization": "Bearer test-token",
    "X-Tenant-ID": "key-tenant",
    "X-User-Role": "admin",
}


def setup_function():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def teardown_function():
    SQLModel.metadata.drop_all(engine)


def test_service_key_is_scoped_and_revocable():
    created = client.post(
        "/api/integrations/service-keys",
        headers=HEADERS,
        json={"name": "ERP staging", "scopes": ["erp:read"]},
    )
    assert created.status_code == 201
    secret = created.json()["secret"]
    assert (
        client.get(
            "/api/integrations/service-session",
            headers={"X-PartsOps-Service-Key": secret},
        ).json()["organization_id"]
        == "key-tenant"
    )
    assert (
        client.post(
            f"/api/integrations/service-keys/{created.json()['key_id']}/revoke",
            headers=HEADERS,
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/integrations/service-session",
            headers={"X-PartsOps-Service-Key": secret},
        ).status_code
        == 403
    )


def test_service_key_can_read_only_its_erp_tenant():
    with Session(engine) as session:
        session.add(
            PartRequest(
                request_id="REQ-INTEGRATION",
                tenant_id="key-tenant",
                source="test",
                status=RequestState.APPROVED,
            )
        )
        session.commit()
    secret = client.post(
        "/api/integrations/service-keys",
        headers=HEADERS,
        json={"name": "ERP", "scopes": ["erp:read"]},
    ).json()["secret"]
    response = client.get(
        "/api/erp/integration/status/REQ-INTEGRATION",
        headers={"X-PartsOps-Service-Key": secret},
    )
    assert response.status_code == 200
    assert response.json()["request_id"] == "REQ-INTEGRATION"


def test_erp_connection_health_requires_admin(monkeypatch):
    monkeypatch.setattr(
        "erp_adapter.check_erpnext_connection",
        lambda: {"status": "connected", "writes_enabled": True},
    )

    forbidden = client.get(
        "/api/erp/connection-health",
        headers={"Authorization": "Bearer test-token", "X-Tenant-ID": "tenant-key", "X-User-Role": "manager"},
    )
    allowed = client.get(
        "/api/erp/connection-health",
        headers={"Authorization": "Bearer test-token", "X-Tenant-ID": "tenant-key", "X-User-Role": "admin"},
    )

    assert forbidden.status_code == 403
    assert allowed.json() == {"status": "connected", "writes_enabled": True}
