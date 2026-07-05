#!/usr/bin/env python3
"""
PartsOps AI Manager v3 — Control Plane Readiness Validator.

Ruflo-inspired guardrail check that bundles the highest-value runtime
integrity signals into one fast, repeatable smoke:
- append-only event chain integrity
- tamper detection on stored events
- terminal state invariant enforcement
- PII masking before logs / agent boundary
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine, select

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from event_store import emit_event, verify_event_chain
from models import EventType, PartRequest, RequestEvent, RequestState
from pii import mask_for_log
from state_machine import validate_transition


def _build_temporary_chain():
    with tempfile.TemporaryDirectory(prefix="partsops-control-plane-") as tmpdir:
        db_path = Path(tmpdir) / "readiness.db"
        engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            request = PartRequest(
                tenant_id="tenant-readiness",
                request_id="REQ-READINESS-001",
                source="validator",
                status=RequestState.FULFILLED,
                customer_name="Ivan Petrov",
                parts_json=json.dumps([{"name": "Тормозные колодки", "quantity": 1}], ensure_ascii=False),
                audit_chain_complete=True,
            )
            session.add(request)
            session.commit()

            emit_event(
                session=session,
                request_id=request.request_id,
                event_type=EventType.REQUEST_RECEIVED.value,
                actor_type="system",
                actor_id="readiness-check",
                payload={"source": request.source, "status": RequestState.NEW},
                tenant_id=request.tenant_id,
            )
            emit_event(
                session=session,
                request_id=request.request_id,
                event_type=EventType.STATE_CHANGED.value,
                actor_type="system",
                actor_id="readiness-check",
                payload={"from": RequestState.NEW, "to": RequestState.NORMALIZING},
                tenant_id=request.tenant_id,
            )

            clean_chain = verify_event_chain(
                request.request_id,
                session,
                tenant_id=request.tenant_id,
            )

            tamper_target = session.exec(
                select(RequestEvent)
                .where(RequestEvent.request_id == request.request_id, RequestEvent.tenant_id == request.tenant_id)
                .order_by(RequestEvent.id.desc())
            ).first()
            if tamper_target is None:
                raise RuntimeError("failed to seed readiness chain")

            tamper_target.payload_json = json.dumps({"tampered": True}, ensure_ascii=False)
            session.add(tamper_target)
            session.commit()

            tampered_chain = verify_event_chain(
                request.request_id,
                session,
                tenant_id=request.tenant_id,
            )

        return {
            "request_id": request.request_id,
            "clean_chain": clean_chain,
            "tampered_chain": tampered_chain,
        }


def run_checks() -> dict:
    chain = _build_temporary_chain()

    transition_blocked = validate_transition(
        RequestState.FULFILLED,
        RequestState.CLOSED,
        request_data={"audit_chain_complete": False},
        strict_invariants=True,
    )
    transition_allowed = validate_transition(
        RequestState.FULFILLED,
        RequestState.CLOSED,
        request_data={"audit_chain_complete": True},
        strict_invariants=True,
    )

    sample_log = (
        "Contact Ivan Petrov at +7 (912) 345-67-89 or ivan.petrov@example.com "
        "for VIN WBA3C3C50EF123456"
    )
    masked_log = mask_for_log(sample_log)

    checks = {
        "event_chain_integrity": {
            "ok": bool(chain["clean_chain"].get("valid")),
            "details": chain["clean_chain"],
        },
        "event_chain_tamper_detection": {
            "ok": chain["tampered_chain"].get("valid") is False,
            "details": chain["tampered_chain"],
        },
        "terminal_state_invariant": {
            "ok": transition_blocked.get("allowed") is False and transition_allowed.get("allowed") is True,
            "details": {
                "blocked": transition_blocked,
                "allowed": transition_allowed,
            },
        },
        "pii_masking": {
            "ok": masked_log != sample_log and "[EMAIL_СКРЫТ]" in masked_log and "[VIN_СКРЫТ]" in masked_log,
            "details": {"sample": sample_log, "masked": masked_log},
        },
    }

    ok = all(item["ok"] for item in checks.values())
    return {"ok": ok, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description="PartsOps control plane readiness validator")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    report = run_checks()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        print("PartsOps control plane readiness")
        for name, item in report["checks"].items():
            status = "OK" if item["ok"] else "FAIL"
            print(f"- {name}: {status}")
            if not item["ok"]:
                print(f"  details: {item['details']}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
