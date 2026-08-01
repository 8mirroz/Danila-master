import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from database import get_session
from event_store import emit_event
from models import EventType, ImportMapping, UploadArtifact
from rbac import get_privileged_tenant
from services.request_service import RequestService
from services.rfq_imports import (
    build_rfq_text,
    import_idempotency_key,
    preview,
    save_mapping,
)
from services.saas import mark_onboarding_step

router = APIRouter(prefix="/api/rfq-imports", tags=["RFQ imports"])


class PreviewPayload(BaseModel):
    artifact_id: str
    mapping: Optional[dict[str, str]] = None


class MappingPayload(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    mapping: dict[str, str]


class CommitPayload(PreviewPayload):
    customer_name: str = Field(default="File import")
    priority: str = Field(default="normal", pattern="^(low|normal|urgent|vip)$")


@router.post("/preview")
def preview_import(
    payload: PreviewPayload,
    session: Session = Depends(get_session),
    organization_id: str = Depends(get_privileged_tenant),
):
    return preview(session, organization_id, payload.artifact_id, payload.mapping)


@router.get("/mappings")
def list_mappings(
    session: Session = Depends(get_session),
    organization_id: str = Depends(get_privileged_tenant),
):
    return [
        {
            "name": item.name,
            "mapping": json.loads(item.mapping_json),
            "updated_at": item.updated_at.isoformat(),
        }
        for item in session.exec(
            select(ImportMapping).where(
                ImportMapping.organization_id == organization_id,
                ImportMapping.kind == "rfq",
            )
        ).all()
    ]


@router.post("/mappings", status_code=201)
def create_mapping(
    payload: MappingPayload,
    session: Session = Depends(get_session),
    organization_id: str = Depends(get_privileged_tenant),
):
    item = save_mapping(session, organization_id, payload.name, payload.mapping)
    return {"name": item.name, "mapping": json.loads(item.mapping_json)}


@router.post("/commit", status_code=201)
async def commit_import(
    payload: CommitPayload,
    session: Session = Depends(get_session),
    organization_id: str = Depends(get_privileged_tenant),
):
    import_preview = preview(
        session, organization_id, payload.artifact_id, payload.mapping, include_all=True
    )
    if import_preview["requires_mapping"]:
        raise HTTPException(
            422, "Map a part number or description column before importing"
        )
    artifact = session.exec(
        select(UploadArtifact).where(
            UploadArtifact.artifact_id == payload.artifact_id,
            UploadArtifact.tenant_id == organization_id,
        )
    ).first()
    if not artifact:
        raise HTTPException(404, "Import artifact not found")
    if artifact.status == "attached" and artifact.request_id:
        existing = RequestService.get_request(
            session, artifact.request_id, organization_id
        )
        return {
            "request": {
                "request_id": existing.request_id,
                "status": existing.status,
                "priority": existing.priority,
                "source": existing.source,
                "customer_name": existing.customer_name,
                "created_at": existing.created_at.isoformat()
                if existing.created_at
                else None,
            },
            "idempotent": True,
            "import": {
                "artifact_id": artifact.artifact_id,
                "valid_positions": import_preview["valid_positions"],
            },
        }
    if artifact.status != "stored":
        raise HTTPException(409, "Artifact is unavailable")
    result = await asyncio.to_thread(
        RequestService.create_request,
        organization_id,
        {
            "source": "RFQ_FILE_IMPORT",
            "text": build_rfq_text(import_preview),
            "customer_name": payload.customer_name,
            "priority": payload.priority,
        },
        import_idempotency_key(payload.artifact_id),
    )
    request_id = result["request"]["request_id"]
    artifact.status, artifact.request_id = "attached", request_id
    session.add(artifact)
    emit_event(
        session=session,
        request_id=request_id,
        event_type=EventType.DOCUMENT_PARSED,
        actor_type="user",
        actor_id="rfq_import",
        payload={
            "artifact_id": artifact.artifact_id,
            "mapping": import_preview["mapping"],
            "valid_positions": import_preview["valid_positions"],
        },
        tenant_id=organization_id,
        commit=False,
    )
    session.commit()
    mark_onboarding_step(session, organization_id, "process_first_rfq")
    return {
        "request": result["request"],
        "idempotent": result["idempotent"],
        "import": {
            "artifact_id": artifact.artifact_id,
            "valid_positions": import_preview["valid_positions"],
        },
    }
