"""Inbound RFQ email ingest.

C1: verify webhook, map tenant, idempotent store.
C2: attachments → UploadArtifact; ingest → RequestService.create_request (source=EMAIL).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, List, Optional

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from models import UploadArtifact
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
    """HMAC-SHA256 over raw body; header forms: `sha256=<hex>` or bare hex.

    Always returns 401-class EmailIngestError on bad signatures (never 500 from
    hmac.compare_digest length mismatch).
    """
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
    # Normalize: accept only lowercase hex of digest length (sha256 = 64).
    provided_norm = provided.lower()
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if len(provided_norm) != len(expected) or any(c not in "0123456789abcdef" for c in provided_norm):
        raise EmailIngestError("Invalid webhook signature", code="EMAIL_SIGNATURE_INVALID", status_code=401)
    if not hmac.compare_digest(expected, provided_norm):
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


def _payload_for_raw_store(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop attachment bytes from raw audit JSON (artifacts store the files)."""
    safe = dict(payload)
    atts = safe.get("attachments")
    if isinstance(atts, list):
        stripped = []
        for att in atts:
            if not isinstance(att, dict):
                continue
            item = {k: v for k, v in att.items() if k != "bytes_base64"}
            if "bytes_base64" in att:
                item["bytes_base64_omitted"] = True
                item["bytes_base64_len"] = len(str(att.get("bytes_base64") or ""))
            stripped.append(item)
        safe["attachments"] = stripped
    return safe


def _store_raw_payload(tenant_id: str, message_id: str, payload: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Best-effort local raw store (without attachment base64); C4 may use S3."""
    try:
        base = Path(settings.UPLOAD_DIR or "08_DATA/uploads")
        # sanitize tenant segment
        clean_tenant = re.sub(r"[^a-zA-Z0-9._-]+", "_", tenant_id)[:80] or "tenant"
        dest_dir = base / clean_tenant / "emails"
        dest_dir.mkdir(parents=True, exist_ok=True)
        safe_id = re.sub(r"[^a-zA-Z0-9._-]+", "_", message_id)[:80]
        path = dest_dir / f"{safe_id}.json"
        raw = json.dumps(_payload_for_raw_store(payload), ensure_ascii=False, default=str).encode("utf-8")
        path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        return str(path), digest
    except OSError:
        return None, None


def message_to_dict(msg: EmailMessage) -> dict[str, Any]:
    # Do not expose full filesystem paths to operators — only presence + digest.
    raw_uri = msg.raw_storage_uri
    raw_name = Path(raw_uri).name if raw_uri else None
    return {
        "id": msg.id,
        "tenant_id": msg.tenant_id,
        "provider_message_id": msg.provider_message_id,
        "provider": msg.provider,
        "from_masked": msg.from_masked,
        "to_address": msg.to_address,
        "subject": msg.subject,
        "received_at": msg.received_at.isoformat() if msg.received_at else None,
        "raw_storage_uri": raw_name,
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
    if not isinstance(attachments_meta, list):
        attachments_meta = []
    attachment_names: list[str] = []
    for att in attachments_meta:
        if not isinstance(att, dict):
            continue
        name = str(att.get("filename") or "")
        ext = Path(name).suffix.lower()
        # Reject missing extension when binary payload is present (policy bypass).
        has_b64 = bool(att.get("bytes_base64"))
        if has_b64 and (not ext or ext not in ALLOWED_ATTACHMENT_EXT):
            if status != "rejected":
                status = "rejected"
                rejection = f"disallowed_attachment:{ext or 'missing_ext'}"
        elif ext and ext not in ALLOWED_ATTACHMENT_EXT:
            if status != "rejected":
                status = "rejected"
                rejection = f"disallowed_attachment:{ext}"
        if name:
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

    emsg_id = f"emsg-{uuid.uuid4().hex[:12]}"
    # Insert message first (empty artifacts) so unique(tenant, message_id) races
    # resolve to IntegrityError → duplicate without orphan files.
    msg = EmailMessage(
        id=emsg_id,
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
        status=status if status == "rejected" else "received",
        rejection_reason=rejection,
        attachment_artifact_ids_json="[]",
        auth_results_json=json.dumps(payload.get("auth_results") or {}, ensure_ascii=False),
        created_at=now_naive,
        updated_at=now_naive,
    )
    ar = msg.auth_results
    if attachment_names:
        ar["attachment_filenames"] = attachment_names
    msg.auth_results = ar

    session.add(msg)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
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
        raise

    session.refresh(msg)

    artifact_ids: list[str] = []
    attach_errors: list[str] = []
    if msg.status != "rejected":
        artifact_ids, attach_errors = store_attachments(
            session,
            tenant_id=cfg.tenant_id,
            email_message_id=msg.id,
            attachments=attachments_meta,
        )
        if attach_errors and not artifact_ids and not excerpt.strip():
            msg.status = "rejected"
            msg.rejection_reason = attach_errors[0]
        else:
            msg.status = "parsed"
        msg.attachment_artifact_ids_json = json.dumps(artifact_ids, ensure_ascii=False)
        ar = msg.auth_results
        if attach_errors:
            ar["attachment_errors"] = attach_errors
        msg.auth_results = ar
        msg.updated_at = utc_now().replace(tzinfo=None)
        session.add(msg)
        session.commit()
        session.refresh(msg)

    result: dict[str, Any] = {
        "email_message_id": msg.id,
        "status": msg.status,
        "tenant_id": msg.tenant_id,
        "auto_ingest": cfg.auto_ingest,
        "attachment_artifact_ids": artifact_ids,
        "note": None,
    }

    # C2: optional auto promote when configured and content is usable
    if cfg.auto_ingest and msg.status == "parsed" and _has_usable_ingest_content(msg):
        try:
            ingested = ingest_message(session, cfg.tenant_id, msg.id)
            result.update({
                "status": ingested.get("status"),
                "request_id": ingested.get("request_id"),
                "auto_ingested": True,
                "note": "auto_ingest created request",
            })
        except Exception as exc:  # honesty: leave parsed, surface error
            session.refresh(msg)
            ar = msg.auth_results
            ar["auto_ingest_error"] = str(exc)[:500]
            msg.auth_results = ar
            msg.updated_at = utc_now().replace(tzinfo=None)
            session.add(msg)
            session.commit()
            result["note"] = f"auto_ingest failed: {exc}"
            result["auto_ingested"] = False
    elif msg.status == "parsed":
        result["note"] = "stored for operator review; POST …/ingest to create_request"

    return result


def _max_attachment_bytes() -> int:
    mb = min(int(settings.EMAIL_MAX_ATTACHMENT_MB), int(settings.MAX_UPLOAD_SIZE_MB))
    return max(1, mb) * 1024 * 1024


def _safe_filename(name: str) -> str:
    base = Path(name or "attachment.bin").name
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", base).strip("._") or "attachment.bin"
    return cleaned[:180]


def store_attachments(
    session: Session,
    *,
    tenant_id: str,
    email_message_id: str,
    attachments: list[Any],
) -> tuple[list[str], list[str]]:
    """Decode base64 attachments → UploadArtifact rows. Returns (ids, errors)."""
    artifact_ids: list[str] = []
    errors: list[str] = []
    max_bytes = _max_attachment_bytes()
    base = Path(settings.UPLOAD_DIR).absolute() / tenant_id / "emails" / email_message_id
    now_naive = utc_now().replace(tzinfo=None)

    for att in attachments:
        if not isinstance(att, dict):
            continue
        filename = str(att.get("filename") or "attachment.bin")
        ext = Path(filename).suffix.lower()
        b64 = att.get("bytes_base64")
        if not b64:
            # metadata-only — no fake artifact
            continue
        if not ext or ext not in ALLOWED_ATTACHMENT_EXT:
            errors.append(f"disallowed_attachment:{ext or 'missing_ext'}")
            continue
        try:
            raw = base64.b64decode(str(b64), validate=False)
        except Exception:
            errors.append(f"invalid_base64:{filename}")
            continue
        if not raw:
            errors.append(f"empty_attachment:{filename}")
            continue
        if len(raw) > max_bytes:
            errors.append(f"attachment_too_large:{filename}")
            continue

        artifact_id = f"art_{uuid.uuid4().hex[:12]}"
        safe = _safe_filename(filename)
        try:
            base.mkdir(parents=True, exist_ok=True)
            stored = base / f"{artifact_id}_{safe}"
            stored.write_bytes(raw)
        except OSError as exc:
            errors.append(f"store_failed:{filename}:{exc}")
            continue

        digest = hashlib.sha256(raw).hexdigest()
        artifact = UploadArtifact(
            artifact_id=artifact_id,
            tenant_id=tenant_id,
            request_id=None,
            original_filename=filename,
            safe_filename=safe,
            stored_path=str(stored),
            content_type=str(att.get("content_type") or ""),
            size_bytes=len(raw),
            sha256=digest,
            source="email",
            uploaded_by="email_webhook",
            status="stored",
            created_at=now_naive,
        )
        session.add(artifact)
        artifact_ids.append(artifact_id)

    if artifact_ids:
        session.flush()
    return artifact_ids, errors


def _has_usable_ingest_content(msg: EmailMessage) -> bool:
    if (msg.body_masked_excerpt or "").strip():
        return True
    return bool(msg.attachment_artifact_ids)


def _text_from_spreadsheet_artifact(artifact: UploadArtifact) -> str:
    """Best-effort row dump using supplier/RFQ table parser (honest empty on failure)."""
    try:
        from services.supplier_service import (
            _extract_supplier_table_rows,
            _parse_supplier_table_file,
        )

        raw_rows, _ = _parse_supplier_table_file(
            artifact.stored_path,
            artifact.original_filename,
            artifact.content_type or "",
        )
        normalized_rows, _, _ = _extract_supplier_table_rows(raw_rows)
        parts: list[str] = []
        for row in normalized_rows:
            part_name = row.get("part_name") or row.get("description") or ""
            if not part_name:
                continue
            oem = row.get("oem_number", "")
            brand = row.get("brand", "")
            qty = row.get("stock_qty") or row.get("quantity") or 1
            parts.append(f"{part_name} {oem} {brand} x{qty}".strip())
        return "\n".join(parts)
    except Exception:
        return ""


def _text_from_txt_artifact(artifact: UploadArtifact) -> str:
    try:
        path = Path(artifact.stored_path)
        if not path.is_file():
            return ""
        if path.suffix.lower() not in {".txt", ".csv"}:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")[:MAX_EXCERPT]
    except OSError:
        return ""


def build_ingest_text(session: Session, msg: EmailMessage) -> str:
    chunks: list[str] = []
    subject = (msg.subject or "").strip()
    body = (msg.body_masked_excerpt or "").strip()
    if subject:
        chunks.append(f"Subject: {subject}")
    if body:
        chunks.append(body)

    for aid in msg.attachment_artifact_ids:
        art = session.exec(
            select(UploadArtifact).where(
                UploadArtifact.artifact_id == aid,
                UploadArtifact.tenant_id == msg.tenant_id,
            )
        ).first()
        if not art:
            continue
        ext = Path(art.original_filename or "").suffix.lower()
        extracted = ""
        if ext in {".xlsx", ".xls", ".csv"}:
            extracted = _text_from_spreadsheet_artifact(art)
        if not extracted and ext in {".txt", ".csv"}:
            extracted = _text_from_txt_artifact(art)
        if extracted.strip():
            chunks.append(f"[attachment {art.original_filename}]\n{extracted.strip()}")
        else:
            chunks.append(
                f"[attachment {art.original_filename} stored as {art.artifact_id}; "
                f"no text extract — may need manual parse]"
            )

    text = "\n\n".join(chunks).strip()
    if not text:
        text = (
            f"Email RFQ {msg.id}: empty body and no extractable attachments. "
            f"Subject was empty. Operator review required."
        )
    return text[: max(MAX_EXCERPT * 2, 16000)]


def _invoke_create_request(
    tenant_id: str,
    payload: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    """Indirection for tests (monkeypatch) and R7-compliant RequestService."""
    from services.request_service import RequestService

    return RequestService.create_request(tenant_id, payload, idempotency_key)


def ingest_message(
    session: Session,
    tenant_id: str,
    message_id: str,
) -> dict[str, Any]:
    """Promote EmailMessage → PartRequest (source=EMAIL), link artifacts.

    CAS: only one worker transitions parsed/received → ingesting → ingested.
    """
    msg = session.get(EmailMessage, message_id)
    if not msg or msg.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Email message not found")

    if msg.status == "ingested" and msg.request_id:
        return {
            "email_message_id": msg.id,
            "request_id": msg.request_id,
            "status": "ingested",
            "idempotent": True,
            "attachment_artifact_ids": msg.attachment_artifact_ids,
        }

    if msg.status in {"rejected", "duplicate", "ingesting"}:
        # ingesting: concurrent worker owns the promote — re-read shortly for result
        if msg.status == "ingesting":
            raise HTTPException(
                status_code=409,
                detail="Ingest already in progress",
            )
        raise HTTPException(
            status_code=422,
            detail=f"Cannot ingest message in status={msg.status}",
        )

    now_naive = utc_now().replace(tzinfo=None)
    # Atomic claim: only one concurrent ingest wins.
    claim = session.execute(
        update(EmailMessage.__table__)
        .where(
            EmailMessage.__table__.c.id == message_id,
            EmailMessage.__table__.c.tenant_id == tenant_id,
            EmailMessage.__table__.c.status.in_(("parsed", "received")),
        )
        .values(status="ingesting", updated_at=now_naive)
    )
    session.commit()
    if claim.rowcount == 0:
        session.expire_all()
        msg = session.get(EmailMessage, message_id)
        if msg and msg.status == "ingested" and msg.request_id:
            return {
                "email_message_id": msg.id,
                "request_id": msg.request_id,
                "status": "ingested",
                "idempotent": True,
                "attachment_artifact_ids": msg.attachment_artifact_ids,
            }
        if msg and msg.status == "ingesting":
            raise HTTPException(
                status_code=409,
                detail="Ingest already in progress",
            )
        if msg and msg.status in {"rejected", "duplicate"}:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot ingest message in status={msg.status}",
            )
        raise HTTPException(
            status_code=409,
            detail="Ingest race lost or message not ready",
        )

    session.expire_all()
    msg = session.get(EmailMessage, message_id)
    if not msg or msg.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Email message not found")

    cfg = get_inbox_config(session, tenant_id)
    priority = (cfg.default_priority if cfg else None) or "normal"
    text_content = build_ingest_text(session, msg)
    idem_key = f"email:{tenant_id}:{msg.provider_message_id}"

    payload = {
        "source": "EMAIL",
        "text": text_content,
        "customer_name": "Email RFQ",
        "priority": priority,
    }

    try:
        created = _invoke_create_request(tenant_id, payload, idem_key)
    except Exception:
        # Release claim so operator can retry.
        msg.status = "parsed"
        msg.updated_at = utc_now().replace(tzinfo=None)
        session.add(msg)
        session.commit()
        raise

    request_obj = created.get("request") or {}
    request_id = request_obj.get("request_id")
    if not request_id:
        msg.status = "parsed"
        msg.updated_at = utc_now().replace(tzinfo=None)
        session.add(msg)
        session.commit()
        raise HTTPException(status_code=500, detail="create_request returned no request_id")

    now_naive = utc_now().replace(tzinfo=None)
    for aid in msg.attachment_artifact_ids:
        art = session.exec(
            select(UploadArtifact).where(
                UploadArtifact.artifact_id == aid,
                UploadArtifact.tenant_id == tenant_id,
            )
        ).first()
        if not art:
            continue
        art.request_id = request_id
        art.status = "attached"
        session.add(art)

    msg.status = "ingested"
    msg.request_id = request_id
    msg.updated_at = now_naive
    session.add(msg)
    session.commit()
    session.refresh(msg)

    return {
        "email_message_id": msg.id,
        "request_id": request_id,
        "status": "ingested",
        "idempotent": bool(created.get("idempotent")),
        "attachment_artifact_ids": msg.attachment_artifact_ids,
        "request": request_obj,
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


def get_message_stats(session: Session, tenant_id: str) -> dict[str, int]:
    """Per-tenant counts of email_messages by status (tenant isolation only)."""
    from sqlalchemy import func
    from sqlmodel import col

    rows = session.exec(
        select(EmailMessage.status, func.count(col(EmailMessage.id)))
        .where(EmailMessage.tenant_id == tenant_id)
        .group_by(EmailMessage.status)
    ).all()
    by_status: dict[str, int] = {str(s or ""): int(c or 0) for s, c in rows}
    total = sum(by_status.values())
    return {
        "total": total,
        "parsed": by_status.get("parsed", 0),
        "ingested": by_status.get("ingested", 0),
        "rejected": by_status.get("rejected", 0),
        "received": by_status.get("received", 0),
        "ingesting": by_status.get("ingesting", 0),
    }


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
    """Operator reject with CAS: only parsed/received → rejected.

    Prevents clobbering concurrent ingest (status=ingesting) or terminal states.
    """
    msg = session.get(EmailMessage, message_id)
    if not msg or msg.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Email message not found")
    if msg.status == "ingested":
        raise HTTPException(status_code=409, detail="Already ingested")
    if msg.status == "ingesting":
        raise HTTPException(
            status_code=409,
            detail="Ingest already in progress; cannot reject",
        )
    if msg.status == "rejected":
        # Idempotent: already rejected
        return message_to_dict(msg)
    if msg.status not in {"parsed", "received"}:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot reject message in status={msg.status}",
        )

    reason_clean = (reason or "operator_rejected")[:500]
    now_naive = utc_now().replace(tzinfo=None)
    claim = session.execute(
        update(EmailMessage.__table__)
        .where(
            EmailMessage.__table__.c.id == message_id,
            EmailMessage.__table__.c.tenant_id == tenant_id,
            EmailMessage.__table__.c.status.in_(("parsed", "received")),
        )
        .values(
            status="rejected",
            rejection_reason=reason_clean,
            updated_at=now_naive,
        )
    )
    session.commit()
    if claim.rowcount == 0:
        session.expire_all()
        msg = session.get(EmailMessage, message_id)
        if msg and msg.tenant_id == tenant_id and msg.status == "rejected":
            return message_to_dict(msg)
        if msg and msg.status == "ingested":
            raise HTTPException(status_code=409, detail="Already ingested")
        if msg and msg.status == "ingesting":
            raise HTTPException(
                status_code=409,
                detail="Ingest already in progress; cannot reject",
            )
        raise HTTPException(
            status_code=409,
            detail="Reject race lost or message not ready",
        )

    session.expire_all()
    msg = session.get(EmailMessage, message_id)
    if not msg or msg.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Email message not found")
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
