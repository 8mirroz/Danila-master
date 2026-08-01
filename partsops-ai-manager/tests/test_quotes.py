from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from database import engine
from main import app
from models import PartRequest, RequestState
from suppliers import Supplier, SupplierCatalogItem, seed_database


client = TestClient(app)
HEADERS = {
    "Authorization": "Bearer test-token",
    "X-Tenant-ID": "quote-tenant",
    "X-User-Role": "admin",
}


@pytest.fixture(autouse=True)
def database():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_database(session)
        item = session.exec(
            select(SupplierCatalogItem).where(
                SupplierCatalogItem.tenant_id == "default"
            )
        ).first()
        session.add(
            PartRequest(
                request_id="REQ-QUOTE-1",
                tenant_id="quote-tenant",
                source="test",
                status=RequestState.APPROVED,
                customer_name="Quote buyer",
                margin_policy_passed=True,
                parts_json=json.dumps(
                    [{"name": item.part_name, "quantity": 2}], ensure_ascii=False
                ),
                match_evidence_json=json.dumps(
                    {item.part_name: {"item": {"catalog_id": item.catalog_id}}},
                    ensure_ascii=False,
                ),
            )
        )
        item.tenant_id = "quote-tenant"
        session.add(item)
        supplier = session.exec(select(Supplier).where(Supplier.supplier_id == item.supplier_id)).first()
        supplier.tenant_id = "quote-tenant"
        session.add(supplier)
        session.commit()
    yield
    SQLModel.metadata.drop_all(engine)


def test_issued_quote_snapshots_server_pricing_and_exports_versions():
    first = client.post(
        "/api/quotes",
        json={"request_id": "REQ-QUOTE-1", "valid_for_days": 10},
        headers=HEADERS,
    )
    assert first.status_code == 201
    quote = first.json()
    assert quote["version"] == 1
    assert quote["pricing"]["line_items"]

    second = client.post(
        "/api/quotes", json={"request_id": "REQ-QUOTE-1"}, headers=HEADERS
    )
    assert second.status_code == 201
    assert second.json()["quote_id"] == quote["quote_id"]
    assert second.json()["version"] == 2

    old_version = client.get(
        f"/api/quotes/{quote['quote_id']}?version=1", headers=HEADERS
    )
    assert old_version.status_code == 200
    assert old_version.json()["version"] == 1
    assert (
        client.get(f"/api/quotes/{quote['quote_id']}/export/xlsx", headers=HEADERS)
        .headers["content-type"]
        .startswith("application/vnd.openxmlformats-officedocument")
    )
    assert (
        client.get(f"/api/quotes/{quote['quote_id']}/export/pdf", headers=HEADERS)
        .headers["content-type"]
        .startswith("application/pdf")
    )
