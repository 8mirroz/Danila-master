import pytest
from datetime import datetime, timezone
from sqlmodel import Session, SQLModel, create_engine, select

from models import AnalogCandidate, ContractPosition, PriceEvidence, OEMCandidate
from services.analog_resolver import (
    classify_brand_tier,
    detect_oem_unavailability,
    evaluate_analog_risk,
    rank_and_select_analogs,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_classify_brand_tier():
    tier1, risk1 = classify_brand_tier("MANN-FILTER")
    assert tier1 == "OES"
    assert risk1 == 5

    tier2, risk2 = classify_brand_tier("FEBI BILSTEIN")
    assert tier2 == "PREMIUM_AFTERMARKET"
    assert risk2 == 15

    tier3, risk3 = classify_brand_tier("PATRON")
    assert tier3 == "BUDGET"
    assert risk3 == 35

    tier4, risk4 = classify_brand_tier("UNKNOWN_BRAND")
    assert tier4 == "SPEC_MATCH"
    assert risk4 == 55


def test_detect_oem_unavailability_scenarios():
    # Scenario 1: No candidates
    res1 = detect_oem_unavailability([], [])
    assert res1["is_unavailable"] is True
    assert res1["reason_code"] == "OEM_NOT_FOUND"

    # Scenario 2: OEM Candidate present but no evidence
    oem_cand = [OEMCandidate(tenant_id="tenant-a", request_id="R1", position_id="P1", oem_number="34116858047", manufacturer="BMW")]
    res2 = detect_oem_unavailability([], oem_cand)
    assert res2["is_unavailable"] is True
    assert res2["reason_code"] == "OEM_OUT_OF_STOCK"

    # Scenario 3: Available OEM evidence
    ev = [PriceEvidence(
        tenant_id="tenant-a", evidence_id="E1", request_id="R1", position_id="P1",
        source="exist.ru", price=5000, source_url="https://exist.ru/x", captured_at=datetime.now(timezone.utc),
        screenshot_ref="/tmp/test.png", availability_status="available", delivery_eta_days=2
    )]
    res3 = detect_oem_unavailability(ev, oem_cand)
    assert res3["is_unavailable"] is False
    assert res3["reason_code"] == "OEM_AVAILABLE"


def test_evaluate_analog_risk_penalties():
    # Normal OES part
    res_oes = evaluate_analog_risk(brand="MANN", interchange_type="direct", is_safety_related=False)
    assert res_oes["quality_tier"] == "OES"
    assert res_oes["risk_score"] == 5
    assert res_oes["requires_human_approval"] is False

    # Safety-critical Budget part
    res_budget = evaluate_analog_risk(brand="PATRON", interchange_type="direct", is_safety_related=True)
    assert res_budget["quality_tier"] == "BUDGET"
    assert res_budget["risk_score"] == 35 + 30  # 65%
    assert res_budget["requires_human_approval"] is True


def test_rank_and_select_analogs_sorting(db):
    pos = ContractPosition(
        tenant_id="tenant-a", request_id="REQ-TEST", position_id="POS-1", contract_ref="CTR-TEST", line_no=1,
        part_number="34116858047", description="Brake pads", quantity=1
    )
    db.add(pos)

    a1 = AnalogCandidate(
        tenant_id="tenant-a", candidate_id="CAND-BUDGET", request_id="REQ-TEST", position_id="POS-1",
        article="PAT-001", brand="PATRON", source="tecdoc"
    )
    a2 = AnalogCandidate(
        tenant_id="tenant-a", candidate_id="CAND-OES", request_id="REQ-TEST", position_id="POS-1",
        article="ATE-001", brand="ATE", source="tecdoc"
    )
    db.add(a1)
    db.add(a2)
    db.commit()

    ranked = rank_and_select_analogs(db, "POS-1", "tenant-a", is_safety_related=False)
    assert len(ranked) == 2
    assert ranked[0]["brand"] == "ATE"
    assert ranked[0]["quality_tier"] == "OES"
    assert ranked[1]["brand"] == "PATRON"
    assert ranked[1]["quality_tier"] == "BUDGET"
