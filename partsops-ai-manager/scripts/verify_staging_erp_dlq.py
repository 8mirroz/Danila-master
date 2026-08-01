"""Prove ERP outbox retries reach DLQ through real local HTTP requests.

The verifier starts an in-container authorized failure endpoint, sends a
temporary invoice through the ERP adapter three times, and verifies that its
single idempotent outbox record reaches DLQ. It does not contact the configured
external ERP endpoint and deletes all temporary PostgreSQL records on exit.
"""

from __future__ import annotations

import json
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from sqlalchemy import delete
from sqlmodel import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import erp_adapter
from database import engine
from erp_adapter import get_dlq_entries, get_pending_outbox, sync_invoice_draft
from models import ERPSyncLog, PartRequest, RequestEvent, RequestState
from suppliers import Invoice


class _FailureEndpoint(BaseHTTPRequestHandler):
    calls = 0
    valid_authorization = True

    def do_POST(self) -> None:
        type(self).calls += 1
        if not self.headers.get("Authorization", "").startswith("token "):
            type(self).valid_authorization = False
        self.send_response(503)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"message":"controlled staging ERP failure"}')

    def log_message(self, _format: str, *_args: object) -> None:
        return


def _cleanup(tenant_id: str, request_id: str, invoice_number: str) -> None:
    with Session(engine) as session:
        session.exec(delete(RequestEvent).where(RequestEvent.tenant_id == tenant_id))
        session.exec(delete(ERPSyncLog).where(ERPSyncLog.tenant_id == tenant_id))
        session.exec(
            delete(Invoice).where(
                Invoice.tenant_id == tenant_id,
                Invoice.invoice_number == invoice_number,
            )
        )
        session.exec(delete(PartRequest).where(PartRequest.request_id == request_id))
        session.commit()


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    tenant_id = f"erp-proof-{suffix}"
    request_id = f"REQ-ERP-PROOF-{suffix}"
    invoice_number = f"INV-ERP-PROOF-{suffix}"
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FailureEndpoint)
    endpoint_url = f"http://127.0.0.1:{server.server_port}"
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    previous_url = erp_adapter.ERPNEXT_URL

    try:
        with Session(engine) as session:
            session.add(
                PartRequest(
                    request_id=request_id,
                    tenant_id=tenant_id,
                    source="erp-dlq-proof",
                    status=RequestState.APPROVED,
                    customer_name="ERP DLQ proof",
                )
            )
            session.add(
                Invoice(
                    invoice_number=invoice_number,
                    tenant_id=tenant_id,
                    request_id=request_id,
                    supplier_id="ERP-PROOF",
                    customer_name="ERP DLQ proof",
                    items_json=json.dumps(
                        [
                            {
                                "part_name": "Proof part",
                                "quantity": 1,
                                "sale_price": 100.0,
                                "line_total": 100.0,
                            }
                        ]
                    ),
                    subtotal=100.0,
                    tax=20.0,
                    total=120.0,
                    status="DRAFT",
                )
            )
            session.commit()

        server_thread.start()
        erp_adapter.ERPNEXT_URL = endpoint_url
        statuses: list[str] = []
        with Session(engine) as session:
            for _ in range(3):
                result = sync_invoice_draft(
                    request_id=request_id,
                    tenant_id=tenant_id,
                    session=session,
                    dry_run=False,
                )
                statuses.append(result["status"])
            dlq_entries = get_dlq_entries(session, tenant_id=tenant_id)
            pending_entries = get_pending_outbox(session, tenant_id=tenant_id)

        if statuses != ["RETRYING", "RETRYING", "DLQ"]:
            raise RuntimeError(f"Unexpected ERP retry statuses: {statuses}")
        if _FailureEndpoint.calls != 3 or not _FailureEndpoint.valid_authorization:
            last_error = dlq_entries[0].last_error if dlq_entries else None
            raise RuntimeError(
                "ERP failure endpoint request mismatch: "
                f"calls={_FailureEndpoint.calls}, "
                f"authorization={_FailureEndpoint.valid_authorization}, "
                f"last_error={last_error!r}"
            )
        if len(dlq_entries) != 1 or dlq_entries[0].attempt_count != 3:
            raise RuntimeError("ERP outbox record did not reach the expected DLQ state")
        if pending_entries:
            raise RuntimeError("ERP DLQ record remained pending after max attempts")
        print("staging_erp_dlq=passed http_attempts=3 idempotent_records=1 dlq=1")
    finally:
        erp_adapter.ERPNEXT_URL = previous_url
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
        _cleanup(tenant_id, request_id, invoice_number)


if __name__ == "__main__":
    main()
