import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from main import app
from database import get_session
from models import PartRequest, RequestEvent, LLMUsageLog, ERPSyncLog, ApprovalTicket
from suppliers import Supplier, Invoice

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session
    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

def test_data_health_empty(client: TestClient):
    """Test data health output with an empty database."""
    headers = {"Authorization": "Bearer test-token", "X-Tenant-ID": "default"}
    response = client.get("/api/admin/data-health", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "healthy")
    assert "entity_counts" in data
    assert "health_indicators" in data

def test_data_health_with_stuck_requests_and_failing_erp(client: TestClient, session: Session):
    """Test data health indicators and alerts when requests are stuck and ERP sync fails."""
    headers = {"Authorization": "Bearer test-token", "X-Tenant-ID": "default"}

    stale_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=48)
    
    # Create a stuck request
    stuck_req = PartRequest(
        request_id="REQ-STUCK-001",
        tenant_id="default",
        status="NEW",
        created_at=stale_time,
        updated_at=stale_time,
        source="api",
        raw_text="Stuck request"
    )
    session.add(stuck_req)

    # Create a failing ERP sync log
    failing_erp = ERPSyncLog(
        sync_id="SYNC-STUCK-001",
        request_id="REQ-STUCK-001",
        tenant_id="default",
        erp_document_type="INVOICE",
        erp_document_name="INV-001",
        idempotency_key="IDEM-STUCK-001",
        status="FAILED",
        attempt=1,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    session.add(failing_erp)
    session.commit()

    response = client.get("/api/admin/data-health", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert data["entity_counts"]["requests"]["total"] >= 1
    assert data["health_indicators"]["queue_staleness"]["stuck_over_24h"] >= 1
    assert data["health_indicators"]["erp_health"]["currently_failing"] >= 1
    assert len(data["alerts"]) >= 1
