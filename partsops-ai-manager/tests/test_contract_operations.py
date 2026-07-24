
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from event_store import verify_event_chain
from models import ContractPosition, PartRequest, PriceEvidence, RequestState
from services.contract_operations import (approve_contract, collect_evidence, create_contract,
                                          evaluate_policy, export_contract, review_position)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def row(part, source, price, screenshot):
    return {"part_number": part, "source": source, "price": price,
            "source_url": f"https://{source}/price/{part}",
            "captured_at": "2026-07-24T10:00:00+00:00",
            "screenshot_ref": str(screenshot)}


def test_contract_evidence_policy_review_and_export(db, tmp_path):
    created = create_contract(db, "tenant-a", [{"part_number": "OC90", "description": "filter", "quantity": 2}], "op")
    request_id = created["request_id"]
    screenshot = tmp_path / "price.png"
    screenshot.write_bytes(b"\x89PNG\r\n\x1a\ncontract-evidence")
    collected = collect_evidence(db, request_id, "tenant-a", [row("OC90", "exist.ru", 250, screenshot), row("OC90", "autodoc.ru", 275, screenshot), row("OC90", "rossko.ru", 260, screenshot)], "crawler")
    assert collected["evidence_created"] == 3
    evaluated = evaluate_policy(db, request_id, "tenant-a", "policy")
    assert evaluated["needs_review"] is False
    approve_contract(db, request_id, "tenant-a", "op")
    exported = export_contract(db, request_id, "tenant-a", "op")
    assert exported["lines"][0]["source_url"].startswith("https://")
    assert exported["lines"][0]["screenshot_ref"]
    assert Path(exported["lines"][0]["screenshot_ref"]).is_file()
    assert verify_event_chain(request_id, db, "tenant-a")["valid"]


def test_incomplete_evidence_is_rejected_and_tenant_isolation(db, tmp_path):
    created = create_contract(db, "tenant-a", [{"part_number": "X", "quantity": 1}], "op")
    with pytest.raises(Exception):
        collect_evidence(db, created["request_id"], "tenant-a", [{"part_number": "X", "source": "exist.ru", "price": 1, "source_url": "https://exist.ru/x", "captured_at": "2026-07-24T10:00:00+00:00"}], "crawler")
    with pytest.raises(Exception):
        evaluate_policy(db, created["request_id"], "tenant-b", "policy")


def test_policy_routes_price_spread_to_review(db, tmp_path):
    created = create_contract(db, "tenant-a", [{"part_number": "X", "quantity": 1}], "op")
    screenshot = tmp_path / "price.png"
    screenshot.write_bytes(b"\x89PNG\r\n\x1a\ncontract-evidence")
    collect_evidence(db, created["request_id"], "tenant-a", [
        row("X", "exist.ru", 100, screenshot),
        row("X", "autodoc.ru", 110, screenshot),
        row("X", "rossko.ru", 300, screenshot),
    ], "crawler")
    evaluated = evaluate_policy(db, created["request_id"], "tenant-a", "policy")
    assert evaluated["needs_review"] is True
    position = db.exec(select(ContractPosition).where(ContractPosition.request_id == created["request_id"])).one()
    evidence = db.exec(select(PriceEvidence).where(PriceEvidence.position_id == position.position_id)).first()
    reviewed = review_position(db, created["request_id"], "tenant-a", position.position_id, evidence.evidence_id, "operator", "selected after review")
    assert reviewed["status"] == RequestState.READY_FOR_APPROVAL
    approve_contract(db, created["request_id"], "tenant-a", "operator")
    assert export_contract(db, created["request_id"], "tenant-a", "operator")["lines"]
