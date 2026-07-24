from __future__ import annotations

from typing import Any
import csv
import io
import uuid
from datetime import datetime, timezone
from io import BytesIO
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from database import get_session
from rbac import get_privileged_tenant
from services.contract_operations import (approve_contract, collect_evidence, create_contract,
                                          evaluate_policy, export_contract, review_position)
from models import ContractPosition, PriceEvidence
from models import EventType, UploadArtifact
from app.automation.storage import storage
from event_store import emit_event

router = APIRouter(prefix="/api/contracts", tags=["Contract Operations"])


class ContractCreate(BaseModel):
    contract_ref: str = "2026.170160"
    positions: list[dict[str, Any]] = Field(min_length=1)
    actor_id: str = "operator"


class EvidenceBatch(BaseModel):
    rows: list[dict[str, Any]] = Field(min_length=1)
    actor_id: str = "crawler"


class ReviewPayload(BaseModel):
    evidence_id: str
    actor_id: str = "operator"
    comment: str | None = None


@router.post("", status_code=201)
def create(payload: ContractCreate, session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    if payload.contract_ref != "2026.170160":
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Unsupported contract_ref")
    return create_contract(session, tenant_id, payload.positions, payload.actor_id)


@router.post("/upload", status_code=201)
async def upload(file: UploadFile = File(...), session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    """Accept a UTF-8/CP1251 CSV contract list; crawler output is a later step."""
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1251")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise HTTPException(status_code=422, detail="Contract CSV is empty")
    positions = [{"part_number": row.get("part_number") or row.get("article") or row.get("OEM"),
                  "description": row.get("description") or row.get("part_name"),
                  "quantity": row.get("quantity") or row.get("qty") or 1} for row in rows]
    result = create_contract(session, tenant_id, positions, "operator")
    artifact_id = f"contract_art_{uuid.uuid4().hex[:12]}"
    stored_path, safe_filename, size_bytes = storage.save_file(
        tenant_id, artifact_id, BytesIO(raw), file.filename or "contract.csv")
    artifact = UploadArtifact(artifact_id=artifact_id, tenant_id=tenant_id, request_id=result["request_id"],
                              original_filename=file.filename or "contract.csv", safe_filename=safe_filename,
                              stored_path=stored_path, content_type=file.content_type, size_bytes=size_bytes,
                              sha256=storage.calculate_sha256(stored_path), source="upload",
                              uploaded_by="operator", status="attached",
                              created_at=datetime.now(timezone.utc).replace(tzinfo=None))
    session.add(artifact)
    emit_event(session, result["request_id"], EventType.DOCUMENT_PARSED, actor_type="user", actor_id="operator",
               payload={"artifact_id": artifact_id, "filename": file.filename}, tenant_id=tenant_id, commit=False)
    session.commit()
    result["artifact_id"] = artifact_id
    return result


@router.post("/{request_id}/evidence")
def evidence(request_id: str, payload: EvidenceBatch, session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    return collect_evidence(session, request_id, tenant_id, payload.rows, payload.actor_id)


@router.get("/{request_id}/positions")
def positions(request_id: str, session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    rows = session.exec(select(ContractPosition).where(ContractPosition.request_id == request_id,
                                                       ContractPosition.tenant_id == tenant_id).order_by(ContractPosition.line_no)).all()
    return [{"position_id": row.position_id, "line_no": row.line_no, "part_number": row.part_number,
             "description": row.description, "quantity": row.quantity, "review_status": row.review_status,
             "selected_evidence_id": row.selected_evidence_id,
             "evidence": [{"evidence_id": evidence.evidence_id, "source": evidence.source,
                            "price": evidence.price, "source_url": evidence.source_url,
                            "captured_at": evidence.captured_at.isoformat(),
                            "screenshot_ref": evidence.screenshot_ref,
                            "screenshot_sha256": evidence.screenshot_sha256}
                           for evidence in session.exec(select(PriceEvidence).where(
                               PriceEvidence.position_id == row.position_id,
                               PriceEvidence.tenant_id == tenant_id)).all()]} for row in rows]


@router.get("/{request_id}/crawler-manifest")
def crawler_manifest(request_id: str, session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    rows = session.exec(select(ContractPosition).where(ContractPosition.request_id == request_id,
                                                       ContractPosition.tenant_id == tenant_id).order_by(ContractPosition.line_no)).all()
    if not rows:
        raise HTTPException(status_code=404, detail="Contract request not found")
    return {"request_id": request_id, "contract_ref": "2026.170160",
            "articles": [row.part_number for row in rows],
            "sources": ["exist.ru", "autodoc.ru", "rossko.ru"],
            "required_evidence": ["source_url", "captured_at", "screenshot_path"]}


@router.post("/{request_id}/evaluate")
def evaluate(request_id: str, session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    return evaluate_policy(session, request_id, tenant_id, "policy_engine")


@router.post("/{request_id}/positions/{position_id}/review")
def review(request_id: str, position_id: str, payload: ReviewPayload, session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    return review_position(session, request_id, tenant_id, position_id, payload.evidence_id, payload.actor_id, payload.comment)


@router.post("/{request_id}/approve")
def approve(request_id: str, session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    return approve_contract(session, request_id, tenant_id, "operator")


@router.post("/{request_id}/export")
def export(request_id: str, session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    return export_contract(session, request_id, tenant_id, "operator")
