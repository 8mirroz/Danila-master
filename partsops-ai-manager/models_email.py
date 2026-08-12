"""SQLModel entities for inbound RFQ email inbox (P-RFQ-EMAIL C1)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EmailInboxConfig(SQLModel, table=True):
    """Per-tenant inbound address mapping (org_slug → tenant)."""

    __tablename__ = "email_inbox_configs"
    __table_args__ = (
        UniqueConstraint("org_slug", name="uq_email_inbox_org_slug"),
        UniqueConstraint("address", name="uq_email_inbox_address"),
    )

    id: str = Field(primary_key=True)
    tenant_id: str = Field(index=True)
    org_slug: str = Field(index=True, description="Plus-address key: rfq+{org_slug}@…")
    address: str = Field(description="Full receive address")
    provider: str = Field(default="mailgun", description="ses|mailgun|postmark|imap_dev")
    auto_ingest: bool = Field(default=False)
    default_priority: str = Field(default="normal")
    allowed_senders_json: str = Field(default="[]", description="JSON list of emails/domains")
    default_mapping_id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @property
    def allowed_senders(self) -> List[str]:
        try:
            data = json.loads(self.allowed_senders_json or "[]")
            return data if isinstance(data, list) else []
        except Exception:
            return []

    @allowed_senders.setter
    def allowed_senders(self, value: List[str]) -> None:
        self.allowed_senders_json = json.dumps(value or [], ensure_ascii=False)


class EmailMessage(SQLModel, table=True):
    """Inbound mail row — review-first inbox before create_request (C2)."""

    __tablename__ = "email_messages"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider_message_id",
            name="uq_email_messages_tenant_message_id",
        ),
    )

    id: str = Field(primary_key=True)
    tenant_id: str = Field(index=True)
    provider_message_id: str = Field(index=True, description="RFC Message-ID")
    provider: str = Field(default="mailgun")
    from_masked: str = Field(default="")
    to_address: str = Field(default="")
    subject: str = Field(default="")
    received_at: datetime = Field(default_factory=utc_now, index=True)
    raw_storage_uri: Optional[str] = Field(default=None)
    raw_sha256: Optional[str] = Field(default=None)
    body_masked_excerpt: str = Field(default="")
    status: str = Field(
        default="received",
        index=True,
        description="received|parsed|ingested|rejected|duplicate",
    )
    request_id: Optional[str] = Field(default=None, index=True)
    rejection_reason: Optional[str] = Field(default=None)
    attachment_artifact_ids_json: str = Field(default="[]")
    auth_results_json: str = Field(default="{}")
    # Denormalized webhook redelivery counter (mirrors auth_results.duplicate_hits).
    # Indexed so list?status=duplicate and stats.sum do not scan JSON blobs.
    duplicate_hits: int = Field(default=0, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @property
    def attachment_artifact_ids(self) -> List[str]:
        try:
            data = json.loads(self.attachment_artifact_ids_json or "[]")
            return data if isinstance(data, list) else []
        except Exception:
            return []

    @attachment_artifact_ids.setter
    def attachment_artifact_ids(self, value: List[str]) -> None:
        self.attachment_artifact_ids_json = json.dumps(value or [], ensure_ascii=False)

    @property
    def auth_results(self) -> dict[str, Any]:
        try:
            data = json.loads(self.auth_results_json or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @auth_results.setter
    def auth_results(self, value: dict[str, Any]) -> None:
        self.auth_results_json = json.dumps(value or {}, ensure_ascii=False)
