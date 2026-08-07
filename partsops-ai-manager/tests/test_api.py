from datetime import datetime, timezone
import ast
from pathlib import Path
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
from models import PartRequest
from suppliers import Invoice
from app.automation.rate_limiter import rate_limiter

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
    rate_limiter._windows.clear()
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
    assert len(suppliers) >= 3


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

    catalog = client.get(f"/api/suppliers/{supplier_id}/items")
    assert catalog.status_code == 200
    assert {item["part_name"] for item in catalog.json()} == {
        "Brake Disc Front",
        "Cabin Filter",
    }

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
            headers={"X-User-Role": "finance"} if target_state == "APPROVED" else None,
        )
        assert step_response.status_code == 200

    # Evidence and quotation are produced by an upstream integration in production.
    # This explicit in-memory fixture keeps the test from inventing them in runtime code.
    with Session(engine) as session:
        request = session.exec(select(PartRequest).where(PartRequest.request_id == request_id)).one()
        request.pricing_evidence_json = json.dumps({"source": "test-pricing-evidence"})
        request.margin_policy_passed = True
        request.erp_quotation_ref = "Q-TEST-001"
        request.match_evidence_json = json.dumps({
            part["name"]: {"item": {"catalog_id": "CAT-001"}}
            for part in json.loads(request.parts_json or "[]")
            if isinstance(part, dict) and part.get("name")
        })
        session.add(request)
        session.commit()

    preview = client.post(f"/api/erp/pricing/preview/{request_id}")
    assert preview.status_code == 200
    assert preview.json()["pricing"]["client_price"] > 0

    # 2. Generate invoice after approval
    resp2 = client.post(
        f"/api/erp/invoice/{request_id}",
        headers={"X-User-Role": "finance"},
    )
    assert resp2.status_code == 200
    invoice = resp2.json()
    assert invoice["status"] == "DRAFT_CREATED"
    assert "invoice" in invoice
    assert invoice["invoice"]["total"] > 0
    assert len(invoice["invoice"]["items"]) > 0

    duplicate = client.post(
        f"/api/erp/invoice/{request_id}",
        headers={"X-User-Role": "finance"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["idempotent"] is True
    assert duplicate.json()["invoice"]["invoice_number"] == invoice["invoice"]["invoice_number"]

    sync = client.post(f"/api/erp/sync/{request_id}", json={}, headers={"X-User-Role": "admin"})
    assert sync.status_code == 200
    assert sync.json()["sync"]["sync_id"]


def test_workspace_contract_uses_server_principal_and_rejects_manager_approval():
    created = client.post("/api/requests", json={
        "source": "TEST_MOCK",
        "text": "Нужен масляный фильтр BMW",
        "customer_name": "Workspace Test",
    })
    assert created.status_code == 200
    request_id = created.json()["request"]["request_id"]

    session_payload = client.get("/api/session").json()
    assert session_payload["role"] == "manager"
    workspace = client.get(f"/api/requests/{request_id}/workspace")
    assert workspace.status_code == 200
    data = workspace.json()
    assert data["request"]["request_id"] == request_id
    assert "allowed_actions" in data
    assert "principal_permissions" in data

    forbidden = client.post(
        f"/api/requests/{request_id}/transition",
        json={"target_state": "APPROVED", "reason": "forbidden", "actor_id": "admin"},
    )
    assert forbidden.status_code == 403


def test_pricing_policy_rejects_client_side_overrides():
    created = client.post("/api/requests", json={
        "source": "TEST_MOCK",
        "text": "Нужны тормозные колодки BMW X5",
        "customer_name": "Pricing Policy Test",
    })
    request_id = created.json()["request"]["request_id"]
    response = client.post(
        f"/api/erp/pricing/preview/{request_id}",
        json={"margin_override": 0.99, "logistics_cost": 1},
    )
    assert response.status_code == 422
    status = client.get(f"/api/erp/status/{request_id}")
    assert status.status_code == 200
    assert status.json()["sync_status"] == "NOT_SYNCED"


def _set_request_lifecycle_fixture(request_id: str, status: str) -> None:
    with Session(engine) as session:
        request = session.exec(select(PartRequest).where(PartRequest.request_id == request_id)).one()
        request.status = status
        request.match_evidence_json = json.dumps({
            "Тормозные колодки": {"item": {"catalog_id": "CAT-001"}},
        })
        request.pricing_evidence_json = json.dumps({
            "source": "test-pricing-evidence",
            "approved_offer_snapshot": {
                "Тормозные колодки": {"item": {"catalog_id": "CAT-001"}},
            },
        })
        request.margin_policy_passed = True
        request.erp_quotation_ref = "Q-TEST-LOCK"
        session.add(request)
        session.commit()


def _offer_payload() -> dict:
    return {
        "part_name": "Тормозные колодки",
        "offer": {"item": {"catalog_id": "CAT-001"}},
    }


def test_admin_cannot_transition_directly_to_erp_syncing():
    created = client.post("/api/requests", json={
        "source": "TEST_MOCK", "text": "Нужны тормозные колодки BMW", "customer_name": "ERP Transition Test",
    })
    request_id = created.json()["request"]["request_id"]
    _set_request_lifecycle_fixture(request_id, "APPROVED")

    response = client.post(
        f"/api/requests/{request_id}/transition",
        json={"target_state": "ERP_SYNCING", "reason": "manual bypass"},
        headers={"X-User-Role": "admin"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "INTERNAL_TRANSITION_ONLY"


@pytest.mark.parametrize("status", ["APPROVED", "INVOICE_DRAFTED"])
def test_offer_selection_is_locked_outside_matching(status: str):
    created = client.post("/api/requests", json={
        "source": "TEST_MOCK", "text": "Нужны тормозные колодки BMW", "customer_name": "Offer Lock Test",
    })
    request_id = created.json()["request"]["request_id"]
    _set_request_lifecycle_fixture(request_id, status)

    response = client.post(f"/api/requests/{request_id}/actions/select_offer", json=_offer_payload())
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OFFER_SELECTION_NOT_ALLOWED"


def test_legacy_matches_respects_offer_lifecycle_lock():
    created = client.post("/api/requests", json={
        "source": "TEST_MOCK", "text": "Нужны тормозные колодки BMW", "customer_name": "Legacy Offer Lock Test",
    })
    request_id = created.json()["request"]["request_id"]
    _set_request_lifecycle_fixture(request_id, "APPROVED")

    response = client.post(f"/api/requests/{request_id}/matches", json=_offer_payload())
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OFFER_SELECTION_NOT_ALLOWED"


def test_sync_to_erp_is_a_command_and_is_idempotent():
    created = client.post("/api/requests", json={
        "source": "TEST_MOCK", "text": "Нужны тормозные колодки BMW", "customer_name": "ERP Command Test",
    })
    request_id = created.json()["request"]["request_id"]
    _set_request_lifecycle_fixture(request_id, "INVOICE_DRAFTED")
    with Session(engine) as session:
        session.add(Invoice(
            tenant_id="default", invoice_number="INV-ERP-COMMAND", request_id=request_id,
            supplier_id="SUP-001", customer_name="ERP Command Test", items_json="[]", status="DRAFT",
        ))
        session.commit()

    synced = client.post(
        f"/api/erp/sync/{request_id}", json={},
        headers={"X-User-Role": "admin", "X-Idempotency-Key": "sync-command-1"},
    )
    assert synced.status_code == 200
    assert synced.json()["request_status"] == "ERP_SYNCED"

    repeated = client.post(
        f"/api/erp/sync/{request_id}", json={},
        headers={"X-User-Role": "admin", "X-Idempotency-Key": "sync-command-1"},
    )
    assert repeated.status_code == 200
    assert repeated.json()["sync"]["idempotent"] is True


def test_workspace_exposes_erp_command_only_when_its_prerequisites_exist():
    created = client.post("/api/requests", json={
        "source": "TEST_MOCK", "text": "Нужны тормозные колодки BMW", "customer_name": "ERP Capability Test",
    })
    request_id = created.json()["request"]["request_id"]
    _set_request_lifecycle_fixture(request_id, "INVOICE_DRAFTED")

    before_invoice = client.get(
        f"/api/requests/{request_id}/workspace",
        headers={"X-User-Role": "admin"},
    )
    assert before_invoice.status_code == 200
    assert "sync_to_erp" not in {action["id"] for action in before_invoice.json()["allowed_actions"]}

    with Session(engine) as session:
        session.add(Invoice(
            tenant_id="default", invoice_number="INV-ERP-CAPABILITY", request_id=request_id,
            supplier_id="SUP-001", customer_name="ERP Capability Test", items_json="[]", status="DRAFT",
        ))
        session.commit()

    after_invoice = client.get(
        f"/api/requests/{request_id}/workspace",
        headers={"X-User-Role": "admin"},
    )
    assert after_invoice.status_code == 200
    assert "sync_to_erp" in {action["id"] for action in after_invoice.json()["allowed_actions"]}


def test_generate_invoice_has_no_direct_status_assignment():
    tree = ast.parse(Path("services/request_service.py").read_text())
    generate_invoice = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "generate_invoice"
    )
    direct_status_assignments = [
        node for node in ast.walk(generate_invoice)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "req"
            and target.attr == "status"
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        )
    ]
    assert direct_status_assignments == []


def test_workspace_action_rejects_stale_request_version():
    created = client.post("/api/requests", json={
        "source": "TEST_MOCK", "text": "Нужны тормозные колодки BMW", "customer_name": "Version Test",
    })
    request_id = created.json()["request"]["request_id"]
    _set_request_lifecycle_fixture(request_id, "MATCHING")

    response = client.post(
        f"/api/requests/{request_id}/actions/transition",
        json={"target_state": "SUPPLIER_SEARCH", "reason": "stale client"},
        headers={"X-Request-Version": "2000-01-01T00:00:00"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "REQUEST_VERSION_CONFLICT"


def test_invoice_requires_approval():
    payload = {
        "source": "TEST_MOCK",
        "text": "Нужны тормозные колодки на BMW X5",
        "customer_name": "Invoice Gate Test"
    }
    resp = client.post("/api/requests", json=payload)
    assert resp.status_code == 200
    request_id = resp.json()["request"]["request_id"]

    resp2 = client.post(f"/api/erp/invoice/{request_id}", headers={"X-User-Role": "finance"})
    assert resp2.status_code == 422


def test_operator_invoice_draft_without_pre_stamped_quotation():
    """Operator cockpit path: APPROVED + selected offers, no prior Q-ref / margin stamp.

    generate_invoice must recompute pricing, stamp margin_policy_passed, assign
    Q-DRAFT-*, and produce INVOICE_DRAFTED (see RequestService.generate_invoice).
    """
    payload = {
        "source": "TEST_MOCK",
        "text": "Нужны тормозные колодки на BMW X5",
        "customer_name": "Operator Invoice Draft",
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
            json={"target_state": target_state, "reason": f"test {target_state}"},
            headers={"X-User-Role": "finance"} if target_state == "APPROVED" else {"X-User-Role": "admin"},
        )
        assert step_response.status_code == 200, step_response.text

    with Session(engine) as session:
        request = session.exec(select(PartRequest).where(PartRequest.request_id == request_id)).one()
        # Explicitly clear pre-stamps that production agent pipeline may set.
        request.margin_policy_passed = None
        request.erp_quotation_ref = None
        # Keep minimal pricing_evidence so optional reads don't NPE; invoice path recomputes.
        request.pricing_evidence_json = None
        parts = json.loads(request.parts_json or "[]")
        request.match_evidence_json = json.dumps({
            part["name"]: {
                "item": {
                    "catalog_id": (part.get("best_match") or {}).get("catalog_id") or "CAT-001",
                    "price": (part.get("best_match") or {}).get("price") or 1000,
                },
                "supplier_id": (part.get("supplier") or {}).get("supplier_id") or "SUP-001",
            }
            for part in parts
            if isinstance(part, dict) and part.get("name")
        })
        session.add(request)
        session.commit()

    invoice_resp = client.post(
        f"/api/requests/{request_id}/actions/create_invoice",
        json={},
        headers={"X-User-Role": "admin"},
    )
    assert invoice_resp.status_code == 200, invoice_resp.text
    body = invoice_resp.json()
    assert body["request"]["status"] == "INVOICE_DRAFTED"

    with Session(engine) as session:
        request = session.exec(select(PartRequest).where(PartRequest.request_id == request_id)).one()
        assert request.margin_policy_passed is True
        assert request.erp_quotation_ref is not None
        assert str(request.erp_quotation_ref).startswith("Q-DRAFT-")
        assert request.erp_invoice_ref
        evidence = json.loads(request.pricing_evidence_json or "{}")
        assert evidence.get("approved_offer_snapshot")


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
