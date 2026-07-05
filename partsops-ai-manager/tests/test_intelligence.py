"""
Tests: Phase 4 Intelligence Layer (Price curves, Supplier reliability, Return Risk, PO drafts)
"""
import pytest
from sqlmodel import SQLModel, Session, select
from datetime import datetime, timedelta

from database import engine
from models import PriceHistoryLedger, SupplierReliabilityLog, PartRequest
from suppliers import Supplier, SupplierCatalogItem, seed_database
from intelligence import (
    get_90d_median_price,
    record_price_update,
    update_supplier_reliability,
    assess_return_risk,
    generate_purchase_order_drafts
)


@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_database(session)
    yield
    SQLModel.metadata.drop_all(engine)


def test_median_price_calculation():
    with Session(engine) as session:
        # Check median of seeded price history (CAT-001 has 4500, 4500*0.98=4410, 4500*0.95=4275)
        median = get_90d_median_price("CAT-001", session)
        assert median is not None
        assert median == 4410.0  # Median of [4275, 4410, 4500] is 4410.0


def test_record_price_update():
    with Session(engine) as session:
        record_price_update("CAT-001", 5000.0, "RUB", session)
        
        # Re-check median with new price added: [4275, 4410, 4500, 5000] -> median is (4410 + 4500)/2 = 4455
        median = get_90d_median_price("CAT-001", session)
        assert median == 4455.0


def test_supplier_reliability_update():
    with Session(engine) as session:
        # Initial score for SUP-001 is 0.92
        sup = session.exec(select(Supplier).where(Supplier.supplier_id == "SUP-001")).first()
        assert sup.reliability_score == 0.92
        
        # Downgrade due to SLA breach
        update_supplier_reliability("SUP-001", 0.85, "sla_breach", "Late delivery shipment #12", session)
        
        # Refetch
        session.expire_all()
        sup = session.exec(select(Supplier).where(Supplier.supplier_id == "SUP-001")).first()
        assert sup.reliability_score == 0.85
        
        # Verify log entry exists
        log_entry = session.exec(
            select(SupplierReliabilityLog).where(
                SupplierReliabilityLog.supplier_id == "SUP-001",
                SupplierReliabilityLog.event_type == "sla_breach"
            )
        ).first()
        assert log_entry is not None
        assert "изменено с 0.92 на 0.85" in log_entry.reason


def test_assess_return_risk():
    res_high = assess_return_risk("Амортизатор передний", "Bilstein")
    assert res_high["risk_level"] == "high"
    assert res_high["is_non_returnable"] is True
    assert res_high["policy_margin"] == 0.20
    
    res_low = assess_return_risk("Масляный фильтр", "Bosch")
    assert res_low["risk_level"] == "low"
    assert res_low["is_non_returnable"] is False
    assert res_low["policy_margin"] == 0.12


def test_generate_purchase_order_drafts():
    with Session(engine) as session:
        # Create a mock validated PartRequest with 2 items from different suppliers
        import json
        parts_data = [
            {
                "name": "Тормозные колодки",
                "quantity": 2,
                "best_match": {
                    "catalog_id": "CAT-001",
                    "name": "Тормозные колодки передние BMW X5",
                    "price": 4500.0
                },
                "supplier": {"supplier_id": "SUP-001", "name": "АвтоАльянс"}
            },
            {
                "name": "Масляный фильтр",
                "quantity": 1,
                "best_match": {
                    "catalog_id": "CAT-006",
                    "name": "Масляный фильтр BMW N55",
                    "price": 1100.0
                },
                "supplier": {"supplier_id": "SUP-002", "name": "ЕвроПарт"}
            }
        ]
        
        req = PartRequest(
            request_id="REQ-TESTPO",
            source="TEST",
            status="VALIDATED",
            parts_json=json.dumps(parts_data)
        )
        session.add(req)
        session.commit()
        
        po_drafts = generate_purchase_order_drafts("REQ-TESTPO", session)
        assert len(po_drafts) == 2  # Grouped into 2 POs (SUP-001 and SUP-002)
        
        po_sup1 = next(po for po in po_drafts if po["supplier_id"] == "SUP-001")
        assert po_sup1["total_cost"] == 9000.0  # 4500 * 2
        assert len(po_sup1["items"]) == 1
        
        po_sup2 = next(po for po in po_drafts if po["supplier_id"] == "SUP-002")
        assert po_sup2["total_cost"] == 1100.0  # 1100 * 1
