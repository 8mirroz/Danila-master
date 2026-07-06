import os
import pytest
from sqlmodel import Session, select
from database import engine, init_db
from models import PartRequest, RequestEvent, EventType
from suppliers import Supplier

# This test requires PostgreSQL to be running on port 5433 (via docker compose)
# We skip the test if PostgreSQL is not available
pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql://"),
    reason="PostgreSQL integration test requires DATABASE_URL to start with postgresql://"
)

@pytest.fixture(scope="module", autouse=True)
def setup_postgres_db():
    # Initialize the database (this will drop all/create all if needed, but since we have migrations,
    # let's just make sure table creation/metadata is applied)
    init_db()
    yield

def test_postgres_crud():
    with Session(engine) as session:
        # 1. Create a Supplier
        new_supplier = Supplier(
            supplier_id="TEST-SUP-PG",
            tenant_id="tenant_pg_test",
            name="PG Test Supplier",
            contact_person="John Doe",
            phone="+79991112233",
            email="pg_test@example.com",
            reliability_score=0.95
        )
        session.add(new_supplier)
        
        # 2. Create a PartRequest
        new_request = PartRequest(
            request_id="REQ-PG-001",
            tenant_id="tenant_pg_test",
            source="api",
            source_text="Test request for parts",
            status="pending",
            raw_data_json="{}"
        )
        session.add(new_request)
        
        # 3. Create a RequestEvent
        new_event = RequestEvent(
            event_id="EVT-PG-001",
            request_id="REQ-PG-001",
            tenant_id="tenant_pg_test",
            event_type=EventType.REQUEST_RECEIVED,
            actor_type="system",
            actor_id="system",
            payload_json='{"status": "PASSED"}',
            event_hash="dummy_hash_pg",
            previous_event_hash="root_dummy_pg"
        )
        session.add(new_event)
        session.commit()

    # Read back and verify
    with Session(engine) as session:
        supplier = session.exec(select(Supplier).where(Supplier.supplier_id == "TEST-SUP-PG")).first()
        assert supplier is not None
        assert supplier.name == "PG Test Supplier"

        request = session.exec(select(PartRequest).where(PartRequest.request_id == "REQ-PG-001")).first()
        assert request is not None
        assert request.status == "pending"

        event = session.exec(select(RequestEvent).where(RequestEvent.event_id == "EVT-PG-001")).first()
        assert event is not None
        assert event.event_type == EventType.REQUEST_RECEIVED

        # Clean up
        session.delete(event)
        session.delete(request)
        session.delete(supplier)
        session.commit()
