"""RFQ inbound email API — webhook + operator inbox (C1–C3)."""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Deque, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from database import get_session
from rbac import RoleChecker, get_current_principal, get_current_tenant, CurrentPrincipal
from services import email_ingest as ingest
from settings import settings

router = APIRouter(tags=["Email Inbox"])

require_manager = RoleChecker(allowed_roles=["admin", "manager"])
require_admin = RoleChecker(allowed_roles=["admin", "platform_admin"])

# Soft in-memory RPM guard for webhook (per process).
_webhook_hits: Dict[str, Deque[datetime]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    """Best-effort client key for soft RPM.

    By default trust only `request.client.host` (cannot be spoofed by client
    headers). When behind a trusted reverse proxy set PARTSOPS_TRUST_PROXY_XFF=1
    and use the *rightmost* X-Forwarded-For hop (proxy-appended).
    """
    import os

    trust = os.environ.get("PARTSOPS_TRUST_PROXY_XFF", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if trust:
        forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        if forwarded:
            # Rightmost is typically the proxy-appended client IP when hop count is trusted.
            parts = [p.strip() for p in forwarded.split(",") if p.strip()]
            if parts:
                return parts[-1]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _enforce_webhook_rpm(request: Request) -> None:
    limit = int(settings.EMAIL_WEBHOOK_RPM or 0)
    if limit <= 0:
        return
    ip = _client_ip(request)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=1)
    q = _webhook_hits[ip]
    while q and q[0] < window_start:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "EMAIL_WEBHOOK_RATE_LIMIT",
                "message": f"Webhook rate limit exceeded ({limit}/min)",
            },
        )
    q.append(now)


class InboundEmailAttachment(BaseModel):
    filename: str = ""
    content_type: str = ""
    # C1 accepts metadata only; bytes_base64 optional for future C2
    bytes_base64: Optional[str] = None


class InboundEmailPayload(BaseModel):
    provider: str = Field(default="mailgun")
    message_id: str = Field(..., min_length=1, max_length=500)
    from_: str = Field(default="", alias="from")
    to: list[str] = Field(default_factory=list)
    subject: str = ""
    received_at: Optional[str] = None
    text_body: Optional[str] = None
    html_body: Optional[str] = None
    attachments: list[InboundEmailAttachment] = Field(default_factory=list)
    auth_results: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class InboxConfigPayload(BaseModel):
    org_slug: str = Field(..., min_length=1, max_length=64)
    address: str = Field(..., min_length=3, max_length=320)
    provider: str = Field(default="mailgun")
    auto_ingest: bool = False
    default_priority: str = "normal"
    allowed_senders: list[str] = Field(default_factory=list)


class RejectPayload(BaseModel):
    reason: str = Field(default="operator_rejected", max_length=500)


class IngestPayload(BaseModel):
    """Reserved for future force/re-ingest flags."""
    force: bool = False


@router.post("/api/integrations/email/inbound", status_code=202)
async def inbound_email_webhook(
    request: Request,
    session: Session = Depends(get_session),
    x_partsops_signature: Optional[str] = Header(default=None, alias="X-PartsOps-Signature"),
):
    """Provider webhook — HMAC verified; tenant from recipient map only."""
    _enforce_webhook_rpm(request)
    raw = await request.body()
    try:
        ingest.verify_webhook_signature(raw, x_partsops_signature)
    except ingest.EmailIngestError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc

    try:
        payload_model = InboundEmailPayload.model_validate_json(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid payload: {exc}") from exc

    data = payload_model.model_dump(by_alias=True)
    # normalize alias key for service
    if "from_" in data and "from" not in data:
        data["from"] = data.pop("from_")
    elif "from_" in data:
        data["from"] = data.pop("from_")

    try:
        result = ingest.receive_inbound_email(session, data)
    except ingest.EmailIngestError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc

    return result


@router.get("/api/email/messages")
def list_email_messages(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    tenant_id: str = Depends(get_current_tenant),
    role: str = Depends(require_manager),
    session: Session = Depends(get_session),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    return ingest.list_messages(session, tenant_id, status=status, limit=limit)


@router.get("/api/email/messages/{message_id}")
def get_email_message(
    message_id: str,
    tenant_id: str = Depends(get_current_tenant),
    role: str = Depends(require_manager),
    session: Session = Depends(get_session),
):
    return ingest.get_message(session, tenant_id, message_id)


@router.post("/api/email/messages/{message_id}/reject")
def reject_email_message(
    message_id: str,
    payload: RejectPayload,
    tenant_id: str = Depends(get_current_tenant),
    role: str = Depends(require_manager),
    session: Session = Depends(get_session),
):
    return ingest.reject_message(session, tenant_id, message_id, payload.reason)


@router.post("/api/email/messages/{message_id}/ingest")
def ingest_email_message(
    message_id: str,
    payload: IngestPayload = IngestPayload(),
    tenant_id: str = Depends(get_current_tenant),
    role: str = Depends(require_manager),
    session: Session = Depends(get_session),
):
    """Promote a parsed email into PartRequest (source=EMAIL). Idempotent."""
    _ = payload.force  # reserved
    return ingest.ingest_message(session, tenant_id, message_id)


@router.get("/api/email/config")
def get_email_config(
    tenant_id: str = Depends(get_current_tenant),
    role: str = Depends(require_admin),
    session: Session = Depends(get_session),
):
    cfg = ingest.get_inbox_config(session, tenant_id)
    if not cfg:
        return {"configured": False, "tenant_id": tenant_id}
    return {"configured": True, **ingest.config_to_dict(cfg)}


@router.put("/api/email/config")
def put_email_config(
    payload: InboxConfigPayload,
    tenant_id: str = Depends(get_current_tenant),
    role: str = Depends(require_admin),
    session: Session = Depends(get_session),
):
    cfg = ingest.upsert_inbox_config(
        session,
        tenant_id=tenant_id,
        org_slug=payload.org_slug,
        address=payload.address,
        provider=payload.provider,
        auto_ingest=payload.auto_ingest,
        default_priority=payload.default_priority,
        allowed_senders=payload.allowed_senders,
    )
    return {"configured": True, **ingest.config_to_dict(cfg)}
