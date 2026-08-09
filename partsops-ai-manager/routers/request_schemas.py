"""Pydantic request payloads for /api request routes (extracted from requests.py)."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field as PydanticField


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
    corrected_position_indexes: Optional[list[int]] = None
    correction_reason_tags: list[str] = []
    corrected_vehicle_json: Optional[str] = None


class MatchSelectionPayload(BaseModel):
    part_name: str = PydanticField(min_length=1)
    offer: dict[str, Any]


class WorkspaceActionPayload(BaseModel):
    target_state: Optional[str] = None
    reason: str = ""
    part_name: Optional[str] = None
    offer: Optional[dict[str, Any]] = None


class PipelineRunPayload(BaseModel):
    requested_lane: Optional[str] = PydanticField(default=None, max_length=64)


class ImportFromArtifactPayload(BaseModel):
    artifact_id: str
    source: str = "FILE_UPLOAD"
    customer_name: str = "File Upload Client"
    priority: str = "normal"


class PipelineRequestPayload(BaseModel):
    """Payload for running the full multi-agent pipeline"""

    source: str
    text: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    customer_erp_id: Optional[str] = None
    vehicle_vin: Optional[str] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_year: Optional[int] = None
    vehicle_generation: Optional[str] = None
    vehicle_engine: Optional[str] = None
    parts_data: Optional[list[dict[str, Any]]] = None
    metadata: Optional[dict[str, Any]] = None
    priority: str = "normal"


class PipelineContinuePayload(BaseModel):
    """Payload for continuing a pipeline from a specific stage"""

    start_from: str = "processing"


class ApprovalActionPayload(BaseModel):
    """Payload for approve/reject actions"""

    action: str
    comment: Optional[str] = None


class ClientPortalViewPayload(BaseModel):
    tracking_token: str


class ClientPortalActionPayload(BaseModel):
    tracking_token: str
    action: str
    reason: Optional[str] = None
