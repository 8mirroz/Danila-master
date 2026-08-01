"""
Tests for ERPNext Outbox Adapter (Phase 4)
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from sqlmodel import SQLModel, create_engine, Session, select
from datetime import datetime

from database import engine
from models import PartRequest, RequestState, ERPSyncLog, RequestEvent, EventType
from suppliers import Invoice, Supplier
from erp_adapter import (
    _attempt_erp_sync,
    check_erpnext_connection,
    verify_webhook_signature,
    compute_webhook_signature,
    sync_invoice_draft,
    process_payment_webhook,
    get_pending_outbox,
    get_dlq_entries,
    retry_sync_entry,
)

@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


def test_hmac_webhook_signature_verification():
    secret = "test-secret"
    payload = b'{"event": "payment_received"}'
    
    # Calculate valid signature
    valid_sig = compute_webhook_signature(payload, secret)
    
    assert verify_webhook_signature(payload, valid_sig, secret) is True
    assert verify_webhook_signature(payload, "invalid-signature", secret) is False
    assert verify_webhook_signature(payload, valid_sig, "wrong-secret") is False


def test_sync_invoice_draft_dry_run():
    with Session(engine) as session:
        # Create test request and invoice
        req = PartRequest(
            request_id="REQ-TEST-1",
            tenant_id="default",
            source="manual",
            status=RequestState.APPROVED,
            customer_name="Test Customer",
        )
        invoice = Invoice(
            invoice_number="INV-TEST-1",
            tenant_id="default",
            request_id="REQ-TEST-1",
            supplier_id="SUP-1",
            customer_name="Test Customer",
            items_json=json.dumps([{"part_name": "Фильтр", "quantity": 1, "sale_price": 1000.0, "line_total": 1000.0}]),
            subtotal=1000.0,
            tax=200.0,
            total=1200.0,
            status="DRAFT",
        )
        session.add(req)
        session.add(invoice)
        session.commit()
        
        # Test dry-run sync
        res = sync_invoice_draft("REQ-TEST-1", session, dry_run=True)
        assert res["status"] == "SUCCESS"
        assert res["dry_run"] is True
        
        # Verify ERPSyncLog record
        sync_log = session.exec(select(ERPSyncLog).where(ERPSyncLog.request_id == "REQ-TEST-1")).first()
        assert sync_log is not None
        assert sync_log.status == "SUCCESS"
        assert sync_log.attempt_count == 1
        assert sync_log.erp_document_type == "SalesInvoice"
        assert "DRY-SINV" in sync_log.erp_document_name


def test_real_erp_attempt_uses_configured_httpx_client(monkeypatch):
    import httpx

    captured = {}

    class Response:
        status_code = 201

        @staticmethod
        def json():
            return {"data": {"name": "SINV-PROOF"}}

    class Client:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, url, **kwargs):
            captured["url"] = url
            captured["post_kwargs"] = kwargs
            return Response()

    monkeypatch.setattr(httpx, "Client", Client)
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *_args, **_kwargs: pytest.fail("ERP sync must use the configured HTTP client"),
    )
    monkeypatch.setattr("erp_adapter.ERPNEXT_URL", "https://erp.example.test")
    monkeypatch.setattr("erp_adapter.ERPNEXT_API_KEY", "proof-key")
    monkeypatch.setattr("erp_adapter.ERPNEXT_API_SECRET", "proof-secret")

    result = _attempt_erp_sync(ERPSyncLog(sync_id="SYNC-PROOF"), {"doctype": "Sales Invoice"}, False)

    assert result == {
        "success": True,
        "erp_document_name": "SINV-PROOF",
        "dry_run": False,
    }
    assert captured["url"] == "https://erp.example.test/api/resource/Sales Invoice"
    assert captured["post_kwargs"]["json"] == {"data": {"doctype": "Sales Invoice"}}
    assert captured["client_kwargs"]["timeout"] == 30.0


def test_erpnext_connection_health_is_read_only_and_hides_credentials(monkeypatch):
    import httpx

    captured = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"message": "erpnext-operator"}

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, url, **kwargs):
            captured["url"] = url
            captured["headers"] = kwargs["headers"]
            return FakeResponse()

    monkeypatch.setattr("erp_adapter.ERPNEXT_URL", "https://erp.example.test")
    monkeypatch.setattr("erp_adapter.ERPNEXT_API_KEY", "proof-key")
    monkeypatch.setattr("erp_adapter.ERPNEXT_API_SECRET", "proof-secret")
    monkeypatch.setattr(httpx, "Client", FakeClient)

    result = check_erpnext_connection()

    assert result == {"status": "connected", "dry_run": True}
    assert captured["url"] == "https://erp.example.test/api/method/frappe.auth.get_logged_user"
    assert captured["client_kwargs"]["timeout"] == 5.0
    assert "proof-key" in captured["headers"]["Authorization"]
    assert "Authorization" not in result


def test_erpnext_connection_health_reports_missing_configuration(monkeypatch):
    monkeypatch.setattr("erp_adapter.ERPNEXT_URL", "")

    assert check_erpnext_connection()["status"] == "not_configured"


def test_sync_invoice_draft_already_synced_idempotency():
    with Session(engine) as session:
        req = PartRequest(
            request_id="REQ-TEST-2",
            tenant_id="default",
            source="manual",
            status=RequestState.APPROVED,
            customer_name="Test Customer",
        )
        invoice = Invoice(
            invoice_number="INV-TEST-2",
            tenant_id="default",
            request_id="REQ-TEST-2",
            supplier_id="SUP-1",
            customer_name="Test Customer",
            items_json=json.dumps([]),
            subtotal=1000.0,
            tax=200.0,
            total=1200.0,
            status="DRAFT",
        )
        sync_log = ERPSyncLog(
            sync_id="SYNC-OLD",
            tenant_id="default",
            request_id="REQ-TEST-2",
            erp_document_type="SalesInvoice",
            erp_document_name="SINV-OLD",
            idempotency_key="erp-sync-invoice-INV-TEST-2",
            status="SUCCESS",
            attempt_count=1,
            succeeded_at=datetime.utcnow(),
        )
        session.add(req)
        session.add(invoice)
        session.add(sync_log)
        session.commit()
        
        # Run sync again
        res = sync_invoice_draft("REQ-TEST-2", session, dry_run=True)
        assert res["status"] == "ALREADY_SYNCED"
        assert res["sync_id"] == "SYNC-OLD"


def test_process_payment_webhook_updates_status():
    with Session(engine) as session:
        req = PartRequest(
            request_id="REQ-TEST-3",
            tenant_id="default",
            source="manual",
            status=RequestState.INVOICE_DRAFTED,
            customer_name="Test Customer",
            pricing_evidence_json='{"total": 1200.0}',
            erp_quotation_ref="Q-123",
            margin_policy_passed=True
        )
        invoice = Invoice(
            invoice_number="INV-TEST-3",
            tenant_id="default",
            request_id="REQ-TEST-3",
            supplier_id="SUP-1",
            customer_name="Test Customer",
            items_json=json.dumps([]),
            subtotal=1000.0,
            tax=200.0,
            total=1200.0,
            status="DRAFT",
        )
        session.add(req)
        session.add(invoice)
        session.commit()
        
        # Simulate webhook payment callback
        webhook_payload = {
            "event": "payment_received",
            "invoice_number": "INV-TEST-3",
            "payment_ref": "PAY-NEW-123",
            "amount": 1200.0,
            "currency": "RUB",
            "paid_at": datetime.utcnow().isoformat(),
        }
        
        res = process_payment_webhook(webhook_payload, session)
        assert res["status"] == "PROCESSED"
        assert res["new_state"] == RequestState.PAID
        
        # Verify invoice is PAID
        session.refresh(invoice)
        assert invoice.status == "PAID"
        
        # Verify request has payment ref and updated state
        session.refresh(req)
        assert req.status == RequestState.PAID
        assert req.erp_payment_ref == "PAY-NEW-123"
        
        # Verify events emitted
        events = session.exec(select(RequestEvent).where(RequestEvent.request_id == "REQ-TEST-3")).all()
        event_types = [e.event_type for e in events]
        assert EventType.PAYMENT_STATUS_SYNCED in event_types
        assert EventType.STATE_CHANGED in event_types


def test_process_payment_webhook_idempotency_duplicate():
    with Session(engine) as session:
        req = PartRequest(
            request_id="REQ-TEST-4",
            tenant_id="default",
            source="manual",
            status=RequestState.PAID,
            customer_name="Test Customer",
            pricing_evidence_json='{"total": 1200.0}',
            erp_quotation_ref="Q-123",
            margin_policy_passed=True,
            erp_payment_ref="PAY-1"
        )
        invoice = Invoice(
            invoice_number="INV-TEST-4",
            tenant_id="default",
            request_id="REQ-TEST-4",
            supplier_id="SUP-1",
            customer_name="Test Customer",
            items_json=json.dumps([]),
            subtotal=1000.0,
            tax=200.0,
            total=1200.0,
            status="PAID",
        )
        sync_log = ERPSyncLog(
            sync_id="SYNC-PAY-4",
            tenant_id="default",
            request_id="REQ-TEST-4",
            erp_document_type="PaymentEntry",
            erp_document_name="PAY-1",
            idempotency_key="webhook-payment-INV-TEST-4",
            status="SUCCESS",
            attempt_count=1,
            succeeded_at=datetime.utcnow(),
        )
        session.add(req)
        session.add(invoice)
        session.add(sync_log)
        session.commit()
        
        # Submit duplicate webhook
        webhook_payload = {
            "event": "payment_received",
            "invoice_number": "INV-TEST-4",
            "payment_ref": "PAY-1",
            "amount": 1200.0,
        }
        res = process_payment_webhook(webhook_payload, session)
        assert res["status"] == "DUPLICATE"
        assert res["sync_id"] == "SYNC-PAY-4"


def test_retry_outbox_advances_to_dlq_on_max_attempts():
    with Session(engine) as session:
        sync_log = ERPSyncLog(
            sync_id="SYNC-FAIL-1",
            tenant_id="default",
            request_id="REQ-FAIL-1",
            erp_document_type="SalesInvoice",
            idempotency_key="key-fail-1",
            status="RETRYING",
            attempt_count=2,
            erp_response_json='{"error": "Previous failure"}',
            created_at=datetime.utcnow(),
        )
        session.add(sync_log)
        session.commit()
        
        # Retry with a mock function causing HTTP failure
        # To avoid sleeping, we can patch time.sleep
        with patch("time.sleep") as mock_sleep:
            # We also mock _attempt_erp_sync to return failure
            with patch("erp_adapter._attempt_erp_sync") as mock_sync_attempt:
                mock_sync_attempt.return_value = {"success": False, "error": "Persistent Error"}
                
                res = retry_sync_entry(sync_log, session, dry_run=False)
                
                assert res["status"] == "DLQ"
                assert sync_log.attempt_count == 3
                assert sync_log.status == "DLQ"
                assert sync_log.last_error == "Persistent Error"
                mock_sleep.assert_called_once()


def test_process_payment_webhook_rejects_invalid_amount():
    with Session(engine) as session:
        req = PartRequest(
            request_id="REQ-TEST-5",
            tenant_id="default",
            source="manual",
            status=RequestState.SENT_TO_CLIENT,
            customer_name="Test Customer",
        )
        invoice = Invoice(
            invoice_number="INV-TEST-5",
            tenant_id="default",
            request_id="REQ-TEST-5",
            supplier_id="SUP-1",
            customer_name="Test Customer",
            items_json=json.dumps([]),
            subtotal=1000.0,
            tax=200.0,
            total=1200.0,
            status="DRAFT",
        )
        session.add(req)
        session.add(invoice)
        session.commit()
        
        # Mismatched amount
        webhook_payload = {
            "event": "payment_received",
            "invoice_number": "INV-TEST-5",
            "payment_ref": "PAY-BAD",
            "amount": 999.0,
            "currency": "RUB",
        }
        res = process_payment_webhook(webhook_payload, session)
        assert res["status"] == "ERROR"
        assert "does not match invoice total" in res["reason"]
        
        # Zero amount
        webhook_payload["amount"] = 0
        res = process_payment_webhook(webhook_payload, session)
        assert res["status"] == "ERROR"
        assert "Invalid payment amount" in res["reason"]


def test_webhook_secret_is_not_default():
    from erp_adapter import ERP_WEBHOOK_SECRET
    assert ERP_WEBHOOK_SECRET != "partsops-webhook-secret-default"
    assert len(ERP_WEBHOOK_SECRET) >= 32
