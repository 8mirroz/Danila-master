from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Body, File, UploadFile
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from database import get_session
from rbac import get_privileged_tenant, get_current_tenant, get_current_principal, CurrentPrincipal
from services.request_service import RequestService
from app.automation.storage import storage
from models import UploadArtifact, EventType
from event_store import emit_event

router = APIRouter(prefix="/api", tags=["Requests & Attachments"])


class RawRequestPayload(BaseModel):
    source: str
    text: str
    customer_name: str = "Unknown"
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    vehicle_vin: Optional[str] = None
    priority: str = "normal"


class ManualCorrectionPayload(BaseModel):
    source_text: str
    corrected_parts_json: str
    correction_reason_tags: list[str] = []
    corrected_vehicle_json: Optional[str] = None


class ImportFromArtifactPayload(BaseModel):
    artifact_id: str
    source: str = "FILE_UPLOAD"
    customer_name: str = "File Upload Client"
    priority: str = "normal"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.post("/attachments/upload", status_code=201)
async def upload_attachment(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_current_tenant),
    principal: CurrentPrincipal = Depends(get_current_principal),
    request_id: Optional[str] = Header(None),
    session: Session = Depends(get_session),
):
    try:
        artifact_id = f"art_{uuid.uuid4().hex[:12]}"
        stored_path, safe_filename, size_bytes = storage.save_file(
            tenant_id=tenant_id,
            artifact_id=artifact_id,
            file_obj=file.file,
            original_filename=file.filename,
        )
        artifact = UploadArtifact(
            artifact_id=artifact_id,
            tenant_id=tenant_id,
            request_id=request_id,
            original_filename=file.filename,
            safe_filename=safe_filename,
            stored_path=stored_path,
            content_type=file.content_type,
            size_bytes=size_bytes,
            sha256=storage.calculate_sha256(stored_path),
            uploaded_by=principal.tenant_id,
            status="stored",
            created_at=_utcnow(),
        )
        session.add(artifact)
        session.commit()
        session.refresh(artifact)
        if request_id:
            emit_event(
                session=session,
                request_id=request_id,
                event_type=EventType.DOCUMENT_PARSED,
                actor_type="user",
                actor_id=principal.tenant_id,
                payload={"artifact_id": artifact_id, "filename": file.filename},
                tenant_id=tenant_id,
            )
        return {
            "status": "success",
            "artifact_id": artifact.artifact_id,
            "stored_path": artifact.stored_path,
            "sha256": artifact.sha256,
        }
    except Exception as exc:  # pragma: no cover - defensive
        if "stored_path" in locals():
            storage.delete_file(stored_path)
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc


@router.get("/requests")
def get_requests(
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return RequestService.get_requests(session, tenant_id)


@router.post("/requests/import-from-artifact")
def import_from_artifact(
    payload: ImportFromArtifactPayload,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    """Import a request from a previously uploaded artifact (file)."""
    from agents import process_intake_request
    from pii import secure_pre_parse
    from services.supplier_service import SupplierService
    from sqlmodel import select
    from models import UploadArtifact
    from event_store import emit_event, EventType
    
    # Get the artifact
    artifact = session.exec(
        select(UploadArtifact).where(
            UploadArtifact.artifact_id == payload.artifact_id,
            UploadArtifact.tenant_id == tenant_id
        )
    ).first()
    
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    if artifact.status != "stored":
        raise HTTPException(status_code=400, detail=f"Artifact not ready for import (status: {artifact.status})")
    
    # Parse the file content
    file_type = artifact.content_type or ""
    filename = artifact.original_filename
    stored_path = artifact.stored_path
    
    # Read and parse the file
    try:
        from services.supplier_service import _parse_supplier_table_file, _extract_supplier_table_rows
        raw_rows, file_type = _parse_supplier_table_file(stored_path, filename, file_type)
        normalized_rows, mapped_columns, validation_summary = _extract_supplier_table_rows(raw_rows)
        
        # Build text representation for intake pipeline
        text_parts = []
        for row in normalized_rows:
            part_name = row.get("part_name", "")
            if part_name:
                oem = row.get("oem_number", "")
                brand = row.get("brand", "")
                qty = row.get("stock_qty", 1)
                text_parts.append(f"{part_name} {oem} {brand} x{qty}")
        
        text_content = "\n".join(text_parts) if text_parts else f"File upload: {filename}"
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")
    
    # Run through intake pipeline
    try:
        intake_result = process_intake_request(
            text=text_content,
            priority=payload.priority,
        )
        
        # Create the request
        request_payload = {
            "source": payload.source,
            "text": text_content,
            "customer_name": payload.customer_name,
            "priority": payload.priority,
        }
        
        # Add vehicle info from intake
        if intake_result.get("vehicle_make"):
            request_payload["vehicle_vin"] = intake_result.get("vehicle_vin") or ""
        
        new_request = RequestService.create_request(tenant_id, request_payload, None)
        
        # Emit event linking artifact to request
        emit_event(
            session=session,
            request_id=new_request["request_id"],
            event_type=EventType.DOCUMENT_PARSED,
            actor_type="user",
            actor_id="file_import",
            payload={"artifact_id": artifact.artifact_id, "filename": filename},
            tenant_id=tenant_id,
        )
        
        # Update artifact status
        artifact.status = "attached"
        artifact.request_id = new_request["request_id"]
        session.add(artifact)
        session.commit()
        
        return new_request
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {e}")


@router.post("/requests")
def create_request(
    payload: RawRequestPayload,
    session: Session = Depends(get_session),
    x_idempotency_key: Optional[str] = Header(default=None),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return RequestService.create_request(tenant_id, payload.model_dump(), x_idempotency_key)


@router.get("/requests/{request_id}")
def get_request(
    request_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return RequestService.get_request(session, request_id, tenant_id)


@router.post("/requests/{request_id}/transition")
def transition_state(
    request_id: str,
    body: dict[str, Any] = Body(...),
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    target_state = body.get("target_state")
    reason = body.get("reason", "")
    actor_id = body.get("actor_id", "admin")
    if not target_state:
        raise HTTPException(status_code=400, detail="target_state is required")
    return RequestService.transition_state(session, request_id, tenant_id, target_state, reason, actor_id)


@router.post("/requests/{request_id}/correction")
def create_manual_correction(
    request_id: str,
    payload: ManualCorrectionPayload,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return RequestService.create_manual_correction(session, request_id, tenant_id, payload.model_dump())


@router.get("/requests/{request_id}/gates")
def get_request_gates(
    request_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return RequestService.get_request_gates(session, request_id, tenant_id)


@router.get("/requests/{request_id}/events")
def get_request_events(
    request_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return RequestService.get_request_events(session, request_id, tenant_id)


@router.get("/requests/{request_id}/audit")
def audit_event_chain(
    request_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return RequestService.audit_event_chain(session, request_id, tenant_id)
