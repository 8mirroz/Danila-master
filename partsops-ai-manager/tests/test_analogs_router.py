import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from main import app
from database import get_session
from models import ContractPosition, AnalogCandidate, OEMCandidate, PriceEvidence, PartRequest

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

def test_analogs_report_not_found(client: TestClient):
    response = client.get("/api/contracts/REQ-UNKNOWN/analogs-report")
    assert response.status_code == 404

def test_analogs_report_and_select(client: TestClient, session: Session):
    # Setup test request and position
    req = PartRequest(
        request_id="REQ-ANALOG-001",
        tenant_id="default",
        status="MATCHING",
        source="api",
        raw_text="Test request"
    )
    session.add(req)

    pos = ContractPosition(
        position_id="POS-001",
        request_id="REQ-ANALOG-001",
        contract_ref="CTR-001",
        line_no=1,
        part_number="12345-ABC",
        description="Brake Pad",
        tenant_id="default",
        position_number=1,
        requested_oem="12345-ABC",
        requested_name="Brake Pad",
        quantity=2,
        brand="Toyota"
    )
    session.add(pos)

    candidate = AnalogCandidate(
        candidate_id="CAN-001",
        request_id="REQ-ANALOG-001",
        position_id="POS-001",
        tenant_id="default",
        article="54321-CBA",
        brand="Bosch",
        source="catalog",
        analog_oem="54321-CBA",
        analog_brand="Bosch",
        analog_name="Brake Pad Premium",
        unit_price=1500.0,
        supplier_id="SUP-001",
        supplier_name="Rossko",
        availability=True,
        delivery_days=2,
        compatibility_score=0.95,
        brand_tier="tier1",
        risk_level="low",
        quality_score=0.90
    )
    session.add(candidate)
    session.commit()

    # 1. Get analogs report
    response = client.get("/api/contracts/REQ-ANALOG-001/analogs-report")
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "REQ-ANALOG-001"
    assert len(data["positions"]) == 1

    # 2. Select analog candidate
    payload = {
        "candidate_id": "CAN-001",
        "reviewer_comment": "Approved tier 1 analog",
        "actor": "manager"
    }
    select_resp = client.post("/api/contracts/REQ-ANALOG-001/positions/POS-001/select-analog", json=payload)
    assert select_resp.status_code == 200
    sel_data = select_resp.json()
    assert sel_data["status"] == "success"
    assert sel_data["position_id"] == "POS-001"
