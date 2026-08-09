"""Inbound RFQ email ingest (C1): verify webhook, map tenant, idempotent store.

C2 will attach artifacts and call create_request; this module stops at parsed/rejected.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from models_email import EmailInboxConfig, EmailMessage
from pii import mask_email, secure_pre_parse
from settings import settings

PLUS_ADDRESS_RE = re.compile(
    r"(?:^|[<\s,;])(?:rfq\+)?(?P<slug>[a-zA-Z0-9][a-zA-Z0-9._-]{0,62})@",
    re.IGNORECASE,
)
# Prefer explicit rfq+slug@ form first
RFQ_PLUS_RE = re.compile(
    r"rfq\+(?P<slug>[a-zA-Z0-9][a-zA-Z0-9._-]{0,62})@",
    re.IGNORECASE,
)

ALLOWED_ATTACHMENT_EXT = {".xlsx", ".xls", ".csv", ".pdf", ".txt", ".docx"}
MAX_EXCERPT = 8000


class EmailIngestError(Exception):
    def __init__(self, message: str, *, code: str = "EMAIL_INGEST_ERROR", status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def verify_webhook_signature(raw_body: bytes, signature_header: Optional[str]) -> None:
    """HMAC-SHA256 over raw body; header forms: `sha256=<hex>` or bare hex."""
    secret = (settings.EMAIL_WEBHOOK_SECRET or "").strip()
    if not secret:
        # Dev convenience: only when TESTING=1 and secret unset
        import os

        if os.environ.get("TESTING", "").strip() in {"1", "true", "yes"}:
            return
        raise EmailIngestError(
            "PARTSOPS_EMAIL_WEBHOOK_SECRET is not configured",
            code="EMAIL_WEBHOOK_SECRET_MISSING",
            status_code=503,
        )
    if not signature_header:
        raise EmailIngestError("Missing webhook signature", code="EMAIL_SIGNATURE_MISSING", status_code=401)

    provided = signature_header.strip()
    if provided.lower().startswith("sha256="):
        provided = provided.split("=", 1)[1].strip()

    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, provided):
        raise EmailIngestError("Invalid webhook signature", code="EMAIL_SIGNATURE_INVALID", status_code=401)


def extract_org_slug_from_recipients(recipients: list[str]) -> Optional[str]:
    for addr in recipients:
        if not addr:
            continue
        m = RFQ_PLUS_RE.search(addr)
        if m:
            return m.group("slug").lower()
    return None


def resolve_inbox_config(session: Session, recipients: list[str]) -> EmailInboxConfig:
    slug = extract_org_slug_from_recipients(recipients)
    if not slug:
        # Fallback: exact address match
        for addr in recipients:
            normalized = addr.strip().lower()
            if "<" in normalized and ">" in normalized:
                # "Name <user@host>"
                start = normalized.find("<") + 1
                end = normalized.find(">", start)
                normalized = normalized[start:end]
            cfg = session.exec(
                select(EmailInboxConfig).where(EmailInboxConfig.address == normalized)
            ).first()
            if cfg:
                return cfg
        raise EmailIngestError(
            "Unknown recipient — no tenant mapping",
            code="EMAIL_UNKNOWN_RECIPIENT",
            status_code=404,
        )

    cfg = session.exec(
        select(EmailInboxConfig).where(EmailInboxConfig.org_slug == slug)
    ).first()
    if not cfg:
        raise EmailIngestError(
            f"Unknown org_slug '{slug}'",
            code="EMAIL_UNKNOWN_RECIPIENT",
            status_code=404,
        )
    return cfg


def _sender_allowed(cfg: EmailInboxConfig, from_addr: str) -> bool:
    allow = [s.strip().lower() for s in cfg.allowed_senders if str(s).strip()]
    if not allow:
        return True
    from_norm = (from_addr or "").strip().lower()
    if not from_norm:
        return False
    domain = from_norm.split("@")[-1] if "@" in from_norm else ""
    for rule in allow:
        if rule.startswith("@") and domain == rule[1:]:
            return True
        if rule.startswith("*.") and domain.endswith(rule[1:]):
            return True
        if from_norm == rule or domain == rule:
            return True
    return False


def _store_raw_payload(tenant_id: str, message_id: str, payload: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Best-effort local raw store; C2 may redirect to S3."""
    try:
        base = Path(settings.UPLOAD_DIR or "08_DATA/uploads")
        dest_dir = base / tenant_id / "emails"
        dest_dir.mkdir(parents=True, exist_ok=True)
        safe_id = re.sub(r"[^a-zA-Z0-9._-]+", "_", message_id)[:80]
        path = dest_dir / f"{safe_id}.json"
        raw = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        return str(path), digest
    except OSError:
        return None, None


def message_to_dict(msg: EmailMessage) -> dict[str, Any]:
    return {
        "id": msg.id,
        "tenant_id": msg.tenant_id,
        "provider_message_id": msg.provider_message_id,
        "provider": msg.provider,
        "from_masked": msg.from_masked,
        "to_address": msg.to_address,
        "subject": msg.subject,
        "received_at": msg.received_at.isoformat() if msg.received_at else None,
        "raw_storage_uri": msg.raw_storage_uri,
        "raw_sha256": msg.raw_sha256,
        "body_masked_excerpt": msg.body_masked_excerpt,
        "status": msg.status,
        "request_id": msg.request_id,
        "rejection_reason": msg.rejection_reason,
        "attachment_artifact_ids": msg.attachment_artifact_ids,
        "auth_results": msg.auth_results,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "updated_at": msg.updated_at.isoformat() if msg.updated_at else None,
    }


def receive_inbound_email(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    """Idempotent receive: create EmailMessage or return existing duplicate."""
    provider = str(payload.get("provider") or "mailgun")
    message_id = str(payload.get("message_id") or "").strip()
    if not message_id:
        raise EmailIngestError("message_id is required", code="EMAIL_MESSAGE_ID_REQUIRED")

    recipients = payload.get("to") or []
    if isinstance(recipients, str):
        recipients = [recipients]
    if not isinstance(recipients, list) or not recipients:
        raise EmailIngestError("to[] is required", code="EMAIL_RECIPIENT_REQUIRED")

    cfg = resolve_inbox_config(session, [str(r) for r in recipients])

    existing = session.exec(
        select(EmailMessage).where(
            EmailMessage.tenant_id == cfg.tenant_id,
            EmailMessage.provider_message_id == message_id,
        )
    ).first()
    if existing:
        return {
            "email_message_id": existing.id,
            "status": "duplicate",
            "tenant_id": existing.tenant_id,
            "duplicate_of": existing.id,
        }

    from_raw = str(payload.get("from") or "")
    if not _sender_allowed(cfg, from_raw):
        # Still store for audit with rejected status
        status = "rejected"
        rejection = "sender_not_allowed"
    else:
        status = "parsed"
        rejection = None

    text_body = str(payload.get("text_body") or payload.get("html_body") or "")
    parsed = secure_pre_parse(text_body) if text_body else {"masked_text": ""}
    excerpt = (parsed.get("masked_text") or "")[:MAX_EXCERPT]

    attachments_meta = payload.get("attachments") or []
    attachment_names: list[str] = []
    if isinstance(attachments_meta, list):
        for att in attachments_meta:
            if not isinstance(att, dict):
                continue
            name = str(att.get("filename") or "")
            ext = Path(name).suffix.lower()
            if ext and ext not in ALLOWED_ATTACHMENT_EXT:
                if status != "rejected":
                    status = "rejected"
                    rejection = f"disallowed_attachment:{ext or 'unknown'}"
            attachment_names.append(name)

    uri, digest = _store_raw_payload(cfg.tenant_id, message_id, payload)
    now = utc_now()
    # strip tz for sqlite consistency with other models
    now_naive = now.replace(tzinfo=None)

    received_raw = payload.get("received_at")
    if isinstance(received_raw, str) and received_raw:
        try:
            received_at = datetime.fromisoformat(received_raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            received_at = now_naive
    else:
        received_at = now_naive

    msg = EmailMessage(
        id=f"emsg-{uuid.uuid4().hex[:12]}",
        tenant_id=cfg.tenant_id,
        provider_message_id=message_id,
        provider=provider,
        from_masked=mask_email(from_raw) if from_raw else "",
        to_address=str(recipients[0]),
        subject=str(payload.get("subject") or "")[:500],
        received_at=received_at,
        raw_storage_uri=uri,
        raw_sha256=digest,
        body_masked_excerpt=excerpt,
        status=status,
        rejection_reason=rejection,
        attachment_artifact_ids_json="[]",  # C2 binds UploadArtifact ids
        auth_results_json=json.dumps(payload.get("auth_results") or {}, ensure_ascii=False),
        created_at=now_naive,
        updated_at=now_naive,
    )
    # stash attachment filenames in auth_results side channel for C1 visibility
    if attachment_names:
        ar = msg.auth_results
        ar["attachment_filenames"] = attachment_names
        msg.auth_results = ar

    session.add(msg)
    session.commit()
    session.refresh(msg)

    return {
        "email_message_id": msg.id,
        "status": msg.status,
        "tenant_id": msg.tenant_id,
        "auto_ingest": cfg.auto_ingest,
        "note": (
            "C1: stored for operator review; create_request is C2"
            if msg.status == "parsed"
            else None
        ),
    }


def list_messages(
    session: Session,
    tenant_id: str,
    *,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 200))
    stmt = select(EmailMessage).where(EmailMessage.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(EmailMessage.status == status)
    stmt = stmt.order_by(EmailMessage.received_at.desc()).limit(limit)
    return [message_to_dict(m) for m in session.exec(stmt).all()]


def get_message(session: Session, tenant_id: str, message_id: str) -> dict[str, Any]:
    msg = session.get(EmailMessage, message_id)
    if not msg or msg.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Email message not found")
    return message_to_dict(msg)


def reject_message(
    session: Session,
    tenant_id: str,
    message_id: str,
    reason: str = "operator_rejected",
) -> dict[str, Any]:
    msg = session.get(EmailMessage, message_id)
    if not msg or msg.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Email message not found")
    if msg.status == "ingested":
        raise HTTPException(status_code=409, detail="Already ingested")
    msg.status = "rejected"
    msg.rejection_reason = (reason or "operator_rejected")[:500]
    msg.updated_at = utc_now().replace(tzinfo=None)
    session.add(msg)
    session.commit()
    session.refresh(msg)
    return message_to_dict(msg)


def upsert_inbox_config(
    session: Session,
    *,
    tenant_id: str,
    org_slug: str,
    address: str,
    provider: str = "mailgun",
    auto_ingest: bool = False,
    default_priority: str = "normal",
    allowed_senders: Optional[list[str]] = None,
) -> EmailInboxConfig:
    slug = org_slug.strip().lower()
    addr = address.strip().lower()
    existing = session.exec(
        select(EmailInboxConfig).where(EmailInboxConfig.tenant_id == tenant_id)
    ).first()
    now = utc_now().replace(tzinfo=None)
    if existing:
        existing.org_slug = slug
        existing.address = addr
        existing.provider = provider
        existing.auto_ingest = auto_ingest
        existing.default_priority = default_priority
        existing.allowed_senders = allowed_senders or []
        existing.updated_at = now
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    cfg = EmailInboxConfig(
        id=f"eicfg-{uuid.uuid4().hex[:12]}",
        tenant_id=tenant_id,
        org_slug=slug,
        address=addr,
        provider=provider,
        auto_ingest=auto_ingest,
        default_priority=default_priority,
        allowed_senders_json=json.dumps(allowed_senders or [], ensure_ascii=False),
        created_at=now,
        updated_at=now,
    )
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return cfg


def get_inbox_config(session: Session, tenant_id: str) -> Optional[EmailInboxConfig]:
    return session.exec(
        select(EmailInboxConfig).where(EmailInboxConfig.tenant_id == tenant_id)
    ).first()


def config_to_dict(cfg: EmailInboxConfig) -> dict[str, Any]:
    return {
        "id": cfg.id,
        "tenant_id": cfg.tenant_id,
        "org_slug": cfg.org_slug,
        "address": cfg.address,
        "provider": cfg.provider,
        "auto_ingest": cfg.auto_ingest,
        "default_priority": cfg.default_priority,
        "allowed_senders": cfg.allowed_senders,
        "default_mapping_id": cfg.default_mapping_id,
        "created_at": cfg.created_at.isoformat() if cfg.created_at else None,
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }
