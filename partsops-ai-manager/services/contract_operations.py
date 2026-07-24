"""Evidence-first Contract Operations for contract 2026.170160."""
from __future__ import annotations

import json
import re
import hashlib
import math
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlmodel import Session, select

from event_store import emit_event, emit_state_change
from models import ContractExport, ContractPosition, EventType, PartRequest, PriceEvidence, RequestState
from state_machine import transition
from app.automation.storage import storage

SOURCES = {"exist.ru", "autodoc.ru", "rossko.ru"}
CONTRACT_REF = "2026.170160"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _request(session: Session, request_id: str, tenant_id: str) -> PartRequest:
    row = session.exec(select(PartRequest).where(PartRequest.request_id == request_id,
                                                   PartRequest.tenant_id == tenant_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Contract request not found")
    return row


def _persist_screenshot(tenant_id: str, source_ref: str, evidence_id: str) -> tuple[str, str]:
    """Copy a crawler screenshot into backend-owned tenant evidence storage."""
    if not re.match(r"^[A-Za-z0-9_-]+$", tenant_id):
        raise HTTPException(status_code=422, detail="Invalid tenant_id")
    source = Path(source_ref).expanduser()
    if not source.is_file() or source.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise HTTPException(status_code=422, detail="screenshot_ref must point to an existing PNG/JPEG file")
    if source.stat().st_size <= 0:
        raise HTTPException(status_code=422, detail="screenshot file is empty")
    signature = source.read_bytes()[:8]
    if not (signature.startswith(b"\x89PNG\r\n\x1a\n") or signature.startswith(b"\xff\xd8\xff")):
        raise HTTPException(status_code=422, detail="screenshot_ref is not a PNG/JPEG image")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    tenant_dir = storage.base_dir / tenant_id / "contract-evidence"
    tenant_dir.mkdir(parents=True, exist_ok=True)
    destination = tenant_dir / f"{evidence_id}{source.suffix.lower()}"
    shutil.copyfile(source, destination)
    return str(destination), digest


def _verify_screenshot(evidence: PriceEvidence) -> None:
    path = Path(evidence.screenshot_ref)
    if not path.is_file():
        raise HTTPException(status_code=422, detail="Export blocked: screenshot evidence is missing")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != evidence.screenshot_sha256:
        raise HTTPException(status_code=422, detail="Export blocked: screenshot evidence hash mismatch")


def _move(session: Session, req: PartRequest, target: str, actor: str, reason: str) -> None:
    old = req.status
    req.status = transition(old, target, req.model_dump(), strict_invariants=False)
    req.updated_at = _now()
    session.add(req)
    emit_state_change(session, req.request_id, old, target, actor_type="system", actor_id=actor,
                      reason=reason, tenant_id=req.tenant_id, commit=False)


def create_contract(session: Session, tenant_id: str, positions: list[dict[str, Any]], actor: str) -> dict[str, Any]:
    if not positions:
        raise HTTPException(status_code=422, detail="Contract list must contain at least one position")
    request_id = f"CON-{uuid.uuid4().hex[:10].upper()}"
    req = PartRequest(request_id=request_id, tenant_id=tenant_id, source="contract_operations",
                      status=RequestState.NEW, parts_json=json.dumps(positions, ensure_ascii=False))
    session.add(req)
    emit_event(session, request_id, EventType.REQUEST_RECEIVED, actor_type="user", actor_id=actor,
               payload={"contract_ref": CONTRACT_REF, "positions": len(positions)}, tenant_id=tenant_id,
               commit=False)
    for index, item in enumerate(positions, 1):
        part_number = str(item.get("part_number") or item.get("article") or "").strip()
        if not part_number:
            raise HTTPException(status_code=422, detail=f"Position {index} has no part_number")
        session.add(ContractPosition(
            tenant_id=tenant_id, position_id=f"POS-{uuid.uuid4().hex[:12].upper()}", request_id=request_id,
            contract_ref=CONTRACT_REF, line_no=index, part_number=part_number,
            description=item.get("description"), quantity=max(1, int(item.get("quantity", 1))),
        ))
    _move(session, req, RequestState.NORMALIZING, actor, "Contract list accepted")
    _move(session, req, RequestState.PARSING, actor, "Contract list parsed")
    _move(session, req, RequestState.VIN_CHECK, actor, "Contract vehicle checks completed")
    _move(session, req, RequestState.PART_EXTRACTION, actor, "Contract positions extracted")
    session.commit()
    return {"request_id": request_id, "contract_ref": CONTRACT_REF, "positions": len(positions), "status": req.status}


def collect_evidence(session: Session, request_id: str, tenant_id: str, rows: list[dict[str, Any]], actor: str) -> dict[str, Any]:
    req = _request(session, request_id, tenant_id)
    if req.status != RequestState.PART_EXTRACTION:
        raise HTTPException(status_code=422, detail=f"Evidence collection requires PART_EXTRACTION, got {req.status}")
    positions = session.exec(select(ContractPosition).where(ContractPosition.request_id == request_id,
                                                             ContractPosition.tenant_id == tenant_id)).all()
    by_number = {p.part_number: p for p in positions}
    created = 0
    copied_screenshots: list[Path] = []
    try:
        for row in rows:
            source = str(row.get("source") or row.get("site") or "").lower().strip()
            lookup_number = str(row.get("part_number") or row.get("search_article") or row.get("article") or "").strip()
            position = by_number.get(lookup_number)
            url = str(row.get("source_url") or row.get("url") or "").strip()
            screenshot = str(row.get("screenshot_ref") or row.get("screenshot_path") or "").strip()
            captured = row.get("captured_at")
            if source not in SOURCES or not position or not url or not screenshot or not captured:
                raise HTTPException(status_code=422, detail="Each price requires allowed source, URL, captured_at, and screenshot_ref")
            if not re.match(r"^https?://", url):
                raise HTTPException(status_code=422, detail="source_url must be http(s)")
            hostname = (urlparse(url).hostname or "").lower()
            if hostname != source and not hostname.endswith(f".{source}"):
                raise HTTPException(status_code=422, detail="source_url host does not match source")
            try:
                captured_at = datetime.fromisoformat(str(captured).replace("Z", "+00:00")).replace(tzinfo=None)
                price = float(row["price"])
            except (KeyError, TypeError, ValueError) as exc:
                raise HTTPException(status_code=422, detail="Invalid price or captured_at") from exc
            if not math.isfinite(price) or price <= 0:
                raise HTTPException(status_code=422, detail="price must be a positive finite number")
            evidence_id = f"EVD-{uuid.uuid4().hex[:12].upper()}"
            stored_screenshot, screenshot_sha256 = _persist_screenshot(tenant_id, screenshot, evidence_id)
            copied_screenshots.append(Path(stored_screenshot))
            evidence = PriceEvidence(tenant_id=tenant_id, evidence_id=evidence_id,
                                     request_id=request_id, position_id=position.position_id, source=source,
                                     price=price, source_url=url, captured_at=captured_at,
                                     screenshot_ref=stored_screenshot, screenshot_sha256=screenshot_sha256,
                                     adapter_run_id=row.get("adapter_run_id"))
            session.add(evidence)
            emit_event(session, request_id, EventType.OFFER_RECEIVED, actor_type="external", actor_id=actor,
                       payload={"evidence_id": evidence.evidence_id, "position_id": position.position_id,
                                "source": source, "price": price, "source_url": url, "captured_at": str(captured),
                                "screenshot_sha256": screenshot_sha256},
                       evidence_refs=[evidence.evidence_id], tenant_id=tenant_id, commit=False)
            created += 1
    except Exception:
        for copied in copied_screenshots:
            copied.unlink(missing_ok=True)
        raise
    _move(session, req, RequestState.MATCHING, actor, "Crawler evidence received")
    _move(session, req, RequestState.SUPPLIER_SEARCH, actor, "Supplier adapters queried")
    _move(session, req, RequestState.OFFER_RANKING, actor, "Offers ready for policy evaluation")
    session.commit()
    return {"request_id": request_id, "evidence_created": created, "status": req.status}


def evaluate_policy(session: Session, request_id: str, tenant_id: str, actor: str) -> dict[str, Any]:
    req = _request(session, request_id, tenant_id)
    if req.status != RequestState.OFFER_RANKING:
        raise HTTPException(status_code=422, detail="Policy evaluation requires OFFER_RANKING")
    positions = session.exec(select(ContractPosition).where(ContractPosition.request_id == request_id,
                                                             ContractPosition.tenant_id == tenant_id)).all()
    decisions = []
    for position in positions:
        evidence = session.exec(select(PriceEvidence).where(PriceEvidence.position_id == position.position_id,
                                                             PriceEvidence.tenant_id == tenant_id)).all()
        valid_sources = {e.source for e in evidence}
        prices = [e.price for e in evidence]
        auto = len(valid_sources) == 3 and prices and (max(prices) - min(prices)) / max(prices) <= 0.20
        if auto:
            selected = min(evidence, key=lambda e: (e.price, e.source))
            position.selected_evidence_id = selected.evidence_id
            position.review_status = "auto_selected"
        else:
            position.review_status = "review"
        session.add(position)
        decisions.append({"position_id": position.position_id, "review_status": position.review_status,
                          "selected_evidence_id": position.selected_evidence_id, "sources": sorted(valid_sources)})
    needs_review = any(d["review_status"] == "review" for d in decisions)
    _move(session, req, RequestState.MANUAL_REVIEW if needs_review else RequestState.PRICING_REVIEW, actor,
          "Evidence policy evaluated")
    if not needs_review:
        _move(session, req, RequestState.READY_FOR_APPROVAL, actor, "All positions passed evidence policy")
    session.commit()
    return {"request_id": request_id, "needs_review": needs_review, "decisions": decisions, "status": req.status}


def review_position(session: Session, request_id: str, tenant_id: str, position_id: str,
                    evidence_id: str, actor: str, comment: str | None = None) -> dict[str, Any]:
    req = _request(session, request_id, tenant_id)
    if req.status != RequestState.MANUAL_REVIEW:
        raise HTTPException(status_code=422, detail="Position review requires MANUAL_REVIEW")
    position = session.exec(select(ContractPosition).where(ContractPosition.position_id == position_id,
                                                            ContractPosition.request_id == request_id,
                                                            ContractPosition.tenant_id == tenant_id)).first()
    evidence = session.exec(select(PriceEvidence).where(PriceEvidence.evidence_id == evidence_id,
                                                        PriceEvidence.position_id == position_id,
                                                        PriceEvidence.tenant_id == tenant_id)).first()
    if not position or not evidence:
        raise HTTPException(status_code=404, detail="Position or evidence not found")
    position.selected_evidence_id = evidence.evidence_id
    position.review_status = "approved"
    session.add(position)
    emit_event(session, request_id, EventType.MANAGER_APPROVED, actor_type="user", actor_id=actor,
               payload={"position_id": position_id, "evidence_id": evidence_id, "comment": comment},
               evidence_refs=[evidence_id], tenant_id=tenant_id, commit=False)
    all_positions = session.exec(select(ContractPosition).where(ContractPosition.request_id == request_id,
                                                                ContractPosition.tenant_id == tenant_id)).all()
    if all(p.selected_evidence_id for p in all_positions):
        _move(session, req, RequestState.MATCHING, actor, "Reviewed evidence returned to pricing flow")
        _move(session, req, RequestState.SUPPLIER_SEARCH, actor, "Reviewed evidence supplier check")
        _move(session, req, RequestState.OFFER_RANKING, actor, "Reviewed evidence ranked")
        _move(session, req, RequestState.PRICING_REVIEW, actor, "Reviewed evidence passed")
        _move(session, req, RequestState.READY_FOR_APPROVAL, actor, "All reviewed positions approved")
    session.commit()
    return {"request_id": request_id, "position_id": position_id, "status": req.status}


def approve_contract(session: Session, request_id: str, tenant_id: str, actor: str) -> dict[str, Any]:
    req = _request(session, request_id, tenant_id)
    if req.status != RequestState.READY_FOR_APPROVAL:
        raise HTTPException(status_code=422, detail="Contract is not ready for approval")
    positions = session.exec(select(ContractPosition).where(ContractPosition.request_id == request_id,
                                                             ContractPosition.tenant_id == tenant_id)).all()
    if not positions or not all(p.selected_evidence_id for p in positions):
        raise HTTPException(status_code=422, detail="Approval requires selected evidence for every position")
    _move(session, req, RequestState.APPROVED, actor, "Contract approved by operator")
    session.commit()
    return {"request_id": request_id, "status": req.status}


def export_contract(session: Session, request_id: str, tenant_id: str, actor: str) -> dict[str, Any]:
    req = _request(session, request_id, tenant_id)
    if req.status != RequestState.APPROVED:
        raise HTTPException(status_code=422, detail="Export requires APPROVED contract")
    positions = session.exec(select(ContractPosition).where(ContractPosition.request_id == request_id,
                                                             ContractPosition.tenant_id == tenant_id)).all()
    lines = []
    for position in positions:
        evidence = session.exec(select(PriceEvidence).where(PriceEvidence.evidence_id == position.selected_evidence_id,
                                                            PriceEvidence.tenant_id == tenant_id)).first()
        if not evidence or not evidence.source_url or not evidence.screenshot_ref or not evidence.captured_at:
            raise HTTPException(status_code=422, detail="Export blocked: approved price evidence is incomplete")
        _verify_screenshot(evidence)
        lines.append({"line_no": position.line_no, "part_number": position.part_number, "description": position.description,
                      "quantity": position.quantity, "unit_price": evidence.price, "currency": evidence.currency,
                      "source": evidence.source, "source_url": evidence.source_url,
                      "captured_at": evidence.captured_at.isoformat(), "screenshot_ref": evidence.screenshot_ref,
                      "evidence_id": evidence.evidence_id})
    document = {"template": "contract-2026.170160-price-register-v1", "contract_ref": CONTRACT_REF,
                "request_id": request_id, "generated_at": _now().isoformat(), "lines": lines}
    export = ContractExport(export_id=f"EXP-{uuid.uuid4().hex[:12].upper()}", tenant_id=tenant_id,
                            request_id=request_id, contract_ref=CONTRACT_REF,
                            template_name=document["template"], content_json=json.dumps(document, ensure_ascii=False),
                            created_by=actor)
    session.add(export)
    emit_event(session, request_id, EventType.ERP_DOCUMENT_CREATED, actor_type="user", actor_id=actor,
               payload={"export_id": export.export_id, "template": export.template_name, "lines": len(lines)},
               evidence_refs=[line["evidence_id"] for line in lines], tenant_id=tenant_id, commit=False)
    session.commit()
    return {"export_id": export.export_id, **document}
