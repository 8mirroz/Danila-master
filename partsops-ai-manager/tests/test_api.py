from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select
import pytest
import io
import json
import struct
import zlib

from database import engine
from main import app
from suppliers import seed_database

client = TestClient(app, headers={"Authorization": "Bearer test-token"})


def write_png(path, width: int = 640, height: int = 360):
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    scanline = b"\x00" + (b"\xff\xff\xff" * width)
    raw = scanline * height
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )

@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_database(session)
    yield

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data

def test_create_request_success():
    payload = {
        "source": "TEST_MOCK",
        "text": "Мне нужны тормозные колодки на X5",
        "customer_name": "Test User"
    }
    response = client.post("/api/requests", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "request" in data
    assert "agent_trace" in data
    
    req = data["request"]
    assert req["status"] == "PART_EXTRACTION"
    assert "REQ-" in req["request_id"]
    
    trace = data["agent_trace"]
    assert trace["validation_status"] == "PASSED"
    
def test_create_request_failure():
    payload = {
        "source": "TEST_MOCK",
        "text": "какой-то мусор вместо запчастей",
        "customer_name": "Test User"
    }
    response = client.post("/api/requests", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    req = data["request"]
    assert req["status"] == "NEEDS_CLARIFICATION"
    
    trace = data["agent_trace"]
    assert trace["validation_status"] == "FAILED"

def test_create_request_with_typos():
    """TC-007: Parser should handle typos like 'тармозные калодки'."""
    payload = {
        "source": "TEST_MOCK",
        "text": "тармозные калодки бмв х5 передние",
        "customer_name": "Дмитрий Смирнов"
    }
    response = client.post("/api/requests", json=payload)
    assert response.status_code == 200
    data = response.json()
    req = data["request"]
    assert req["status"] in ("PART_EXTRACTION", "NEEDS_CLARIFICATION")

def test_get_suppliers():
    response = client.get("/api/suppliers")
    assert response.status_code == 200
    suppliers = response.json()
    assert len(suppliers) >= 5


def test_supplier_crud_and_tables():
    payload = {
        "name": "QA Supplier",
        "contact_person": "Smoke Test",
        "city": "Moscow",
        "specialization": "Brakes, Filters",
        "reliability_score": 0.88,
        "avg_delivery_days": 2,
        "status": "active",
        "rating_manual": 4.7,
        "account_owner": "Ops QA",
        "payment_terms": "Net 7",
        "delivery_terms": "FCA",
        "currency_default": "RUB",
        "notes_internal": "Created from test",
        "last_sync_status": "synced",
    }
    created = client.post("/api/suppliers", json=payload)
    assert created.status_code == 200
    supplier = created.json()
    assert supplier["name"] == "QA Supplier"
    supplier_id = supplier["supplier_id"]

    patched = client.patch(
        f"/api/suppliers/{supplier_id}",
        json={**payload, "name": "QA Supplier Updated", "status": "pending"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "QA Supplier Updated"
    assert patched.json()["status"] == "pending"

    rating = client.post(
        f"/api/suppliers/{supplier_id}/rating",
        json={"rating_manual": 4.9, "reason": "qa adjustment"},
    )
    assert rating.status_code == 200
    assert rating.json()["rating_manual"] == 4.9

    table = client.post(
        f"/api/suppliers/{supplier_id}/tables",
        json={
            "name": "Primary QA table",
            "filename": "qa-table.xlsx",
            "rows": [
                {
                    "part_name": "Brake Pad Front",
                    "oem_number": "34116852253",
                    "brand": "TRW",
                    "price": 4200,
                    "currency": "RUB",
                    "stock_qty": 12,
                    "delivery_days": 2,
                    "category": "brake",
                }
            ],
        },
    )
    assert table.status_code == 200
    table_id = table.json()["table_id"]

    rows = client.get(f"/api/suppliers/{supplier_id}/tables/{table_id}/rows")
    assert rows.status_code == 200
    assert rows.json()["total"] == 1
    assert rows.json()["rows"][0]["part_name"] == "Brake Pad Front"

    updated_table = client.patch(
        f"/api/suppliers/{supplier_id}/tables/{table_id}",
        json={"name": "Primary QA table renamed", "status": "stale"},
    )
    assert updated_table.status_code == 200
    assert updated_table.json()["name"] == "Primary QA table renamed"
    assert updated_table.json()["status"] == "stale"

    replacement = client.post(
        f"/api/suppliers/{supplier_id}/tables/{table_id}/replace",
        json={
            "name": "Primary QA table v2",
            "filename": "qa-table-v2.xlsx",
            "rows": [
                {
                    "part_name": "Brake Pad Rear",
                    "oem_number": "34216761238",
                    "brand": "ATE",
                    "price": 4600,
                    "currency": "RUB",
                    "stock_qty": 8,
                    "delivery_days": 3,
                    "category": "brake",
                }
            ],
        },
    )
    assert replacement.status_code == 200
    replacement_table = replacement.json()
    assert replacement_table["version"] == 2
    assert replacement_table["row_count"] == 1
    assert replacement_table["is_active"] is True

    tables = client.get(f"/api/suppliers/{supplier_id}/tables")
    assert tables.status_code == 200
    table_versions = tables.json()
    assert len(table_versions) == 2
    assert table_versions[0]["table_id"] == replacement_table["table_id"]
    assert table_versions[1]["is_active"] is False

    analytics = client.get(f"/api/suppliers/{supplier_id}/analytics")
    assert analytics.status_code == 200
    assert analytics.json()["summary"]["table_count"] >= 2

    logs = client.get(f"/api/suppliers/{supplier_id}/logs")
    assert logs.status_code == 200
    assert logs.json()["total"] >= 1


def test_supplier_table_file_import():
    supplier_id = client.get("/api/suppliers").json()[0]["supplier_id"]
    csv_payload = (
        "part_name,oem_number,brand,price,currency,stock_qty,delivery_days,category\n"
        "Brake Disc Front,34116767061,Brembo,7350,RUB,6,3,brake\n"
        "Cabin Filter,64119237555,Mahle,1250,RUB,18,1,filters\n"
    )

    response = client.post(
        f"/api/suppliers/{supplier_id}/tables/import",
        files={"file": ("supplier-upload.csv", io.BytesIO(csv_payload.encode("utf-8")), "text/csv")},
        data={"name": "Supplier Upload Import"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["import_summary"]["imported_rows"] == 2

    table_id = payload["table"]["table_id"]
    rows = client.get(f"/api/suppliers/{supplier_id}/tables/{table_id}/rows")
    assert rows.status_code == 200
    assert rows.json()["total"] == 2
    assert rows.json()["rows"][0]["part_name"] == "Brake Disc Front"

    logs = client.get(f"/api/suppliers/{supplier_id}/logs")
    assert logs.status_code == 200
    assert any(log["event_type"] == "supplier_table_imported" for log in logs.json()["logs"])


def test_contract_crawler_results_upload_imports_price_evidence(tmp_path):
    screenshot = tmp_path / "price.png"
    write_png(screenshot)
    created = client.post("/api/contracts", json={
        "positions": [{"part_number": "OC90", "description": "filter", "quantity": 1}],
        "actor_id": "operator",
    })
    assert created.status_code == 201
    request_id = created.json()["request_id"]
    position = client.get(f"/api/contracts/{request_id}/positions").json()[0]
    position_id = position["position_id"]

    oem = client.post(f"/api/contracts/{request_id}/positions/{position_id}/oem-candidates", json={
        "actor_id": "operator",
        "data": {
            "oem_number": "OC90",
            "manufacturer": "BMW",
            "source": "vin_oem_catalog",
            "compatibility_evidence": [
                {"evidence_type": "vin_oem_catalog", "source": "BMW ETK"},
                {"evidence_type": "official_brand_catalog", "source": "BMW catalog"},
                {"evidence_type": "cross_reference", "source": "validated cross"},
            ],
        },
    })
    assert oem.status_code == 201
    analog = client.post(f"/api/contracts/{request_id}/positions/{position_id}/analog-candidates", json={
        "actor_id": "operator",
        "data": {
            "article": "OC90",
            "brand": "MANN",
            "source": "tecdoc",
            "oem_candidate_id": oem.json()["candidate_id"],
            "independent_confirmations": 2,
            "compatibility_evidence": [
                {"evidence_type": "vin_oem_catalog", "source": "BMW ETK"},
                {"evidence_type": "official_brand_catalog", "source": "MANN catalog"},
                {"evidence_type": "tecdoc", "source": "TecDoc"},
                {"evidence_type": "cross_reference", "source": "validated cross"},
                {"evidence_type": "spec_match", "source": "dimensions"},
            ],
        },
    })
    assert analog.status_code == 201

    payload = {"items": [{
        "site": "exist.ru",
        "article": "OC90",
        "price": "1 250 ₽",
        "url": "https://exist.ru/price/OC90",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "screenshot": str(screenshot),
        "stock_qty": 8,
        "delivery_days": 2,
    }]}
    uploaded = client.post(
        f"/api/contracts/{request_id}/crawler-results/upload",
        files={"file": ("crawler-results.json", io.BytesIO(json.dumps(payload).encode("utf-8")), "application/json")},
    )
    assert uploaded.status_code == 200
    result = uploaded.json()
    assert result["evidence_created"] == 1
    assert result["adapter_stats"]["normalized"] == 1

    positions = client.get(f"/api/contracts/{request_id}/positions").json()
    evidence = positions[0]["evidence"][0]
    assert evidence["source"] == "exist.ru"
    assert evidence["price"] == 1250
    assert evidence["screenshot_sha256"]
    assert evidence["screenshot_readability_status"] == "readable"
    assert evidence["screenshot_completeness_status"] == "complete"

    orchestrated = client.post(f"/api/contracts/{request_id}/orchestrate", json={"actor_id": "contract-agent"})
    assert orchestrated.status_code == 200
    orchestration = orchestrated.json()
    assert orchestration["ok"] is True
    assert orchestration["job_name"] == "contract_orchestrate"
    assert orchestration["result"]["processed"] == 1


def test_supplier_table_row_update_and_bulk_update():
    supplier_id = client.get("/api/suppliers").json()[0]["supplier_id"]
    table = client.post(
        f"/api/suppliers/{supplier_id}/tables",
        json={
            "name": "Editable table",
            "filename": "editable.csv",
            "rows": [
                {
                    "part_name": "Brake Hose Front",
                    "oem_number": "34326755524",
                    "brand": "ATE",
                    "price": 2100,
                    "currency": "RUB",
                    "stock_qty": 4,
                    "delivery_days": 3,
                    "category": "brake",
                },
                {
                    "part_name": "Wheel Bearing",
                    "oem_number": "31226765601",
                    "brand": "SKF",
                    "price": 5700,
                    "currency": "RUB",
                    "stock_qty": 2,
                    "delivery_days": 5,
                    "category": "suspension",
                },
            ],
        },
    )
    assert table.status_code == 200
    table_id = table.json()["table_id"]

    rows = client.get(f"/api/suppliers/{supplier_id}/tables/{table_id}/rows").json()["rows"]
    first_key = rows[0]["row_key"]
    second_key = rows[1]["row_key"]

    patched = client.patch(
        f"/api/suppliers/{supplier_id}/tables/{table_id}/rows/{first_key}",
        json={"price": 2350, "stock_qty": 7, "delivery_days": 2},
    )
    assert patched.status_code == 200
    assert patched.json()["price"] == 2350
    assert patched.json()["stock_qty"] == 7
    assert patched.json()["delivery_days"] == 2

    bulk = client.post(
        f"/api/suppliers/{supplier_id}/tables/{table_id}/rows/bulk-update",
        json={"row_keys": [first_key, second_key], "category": "service-parts", "delivery_days": 4},
    )
    assert bulk.status_code == 200
    assert bulk.json()["updated_count"] == 2

    refreshed = client.get(f"/api/suppliers/{supplier_id}/tables/{table_id}/rows").json()["rows"]
    assert all(row["category"] == "service-parts" for row in refreshed)
    assert all(row["delivery_days"] == 4 for row in refreshed)

def test_catalog_search():
    response = client.get("/api/catalog/search?q=тормозные колодки BMW")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    assert data["matches"][0]["score"] > 50

def test_invoice_generation():
    # 1. Create a request and move it through the approval path
    payload = {
        "source": "TEST_MOCK",
        "text": "Нужны тормозные колодки на BMW X5",
        "customer_name": "Invoice Test User"
    }
    resp = client.post("/api/requests", json=payload)
    assert resp.status_code == 200
    request_id = resp.json()["request"]["request_id"]

    transition_path = [
        "MATCHING",
        "SUPPLIER_SEARCH",
        "OFFER_RANKING",
        "PRICING_REVIEW",
        "READY_FOR_APPROVAL",
        "APPROVED",
    ]
    for target_state in transition_path:
        step_response = client.post(
            f"/api/requests/{request_id}/transition",
            json={"target_state": target_state, "reason": f"test {target_state}", "actor_id": "admin"},
        )
        assert step_response.status_code == 200

    preview = client.post(
        f"/api/erp/pricing/preview/{request_id}",
        json={
            "logistics_cost": 500,
            "target_margin_override": 0.15,
            "urgency_level": "normal",
        },
    )
    assert preview.status_code == 200
    assert preview.json()["pricing"]["client_price"] > 0

    # 2. Generate invoice after approval
    resp2 = client.post(
        f"/api/erp/invoice/{request_id}",
        json={
            "logistics_cost": 500,
            "target_margin_override": 0.15,
            "urgency_level": "normal",
        },
    )
    assert resp2.status_code == 200
    invoice = resp2.json()
    assert invoice["status"] == "DRAFT_CREATED"
    assert "invoice" in invoice
    assert invoice["invoice"]["total"] > 0
    assert len(invoice["invoice"]["items"]) > 0

    duplicate = client.post(
        f"/api/erp/invoice/{request_id}",
        json={
            "logistics_cost": 500,
            "target_margin_override": 0.15,
            "urgency_level": "normal",
        },
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["idempotent"] is True
    assert duplicate.json()["invoice"]["invoice_number"] == invoice["invoice"]["invoice_number"]


def test_invoice_requires_approval():
    payload = {
        "source": "TEST_MOCK",
        "text": "Нужны тормозные колодки на BMW X5",
        "customer_name": "Invoice Gate Test"
    }
    resp = client.post("/api/requests", json=payload)
    assert resp.status_code == 200
    request_id = resp.json()["request"]["request_id"]

    resp2 = client.post(f"/api/erp/invoice/{request_id}")
    assert resp2.status_code == 422


def test_tenant_isolation_for_requests_and_invoices():
    payload_a = {
        "source": "TEST_MOCK",
        "text": "Нужны тормозные колодки на BMW X5",
        "customer_name": "Tenant A"
    }
    payload_b = {
        "source": "TEST_MOCK",
        "text": "Нужны тормозные колодки на Toyota Camry",
        "customer_name": "Tenant B"
    }

    resp_a = client.post("/api/requests", json=payload_a, headers={"X-Tenant-ID": "tenant-a"})
    resp_b = client.post("/api/requests", json=payload_b, headers={"X-Tenant-ID": "tenant-b"})
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200

    request_id_a = resp_a.json()["request"]["request_id"]
    request_id_b = resp_b.json()["request"]["request_id"]

    requests_a = client.get("/api/requests", headers={"X-Tenant-ID": "tenant-a"}).json()
    requests_b = client.get("/api/requests", headers={"X-Tenant-ID": "tenant-b"}).json()

    assert any(item["request_id"] == request_id_a for item in requests_a)
    assert all(item["request_id"] != request_id_b for item in requests_a)
    assert any(item["request_id"] == request_id_b for item in requests_b)
    assert all(item["request_id"] != request_id_a for item in requests_b)
