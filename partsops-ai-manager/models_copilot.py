"""
PartsOps AI Manager v3 — SQLModel entities for Copilot (Hermes Assistant).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional, List, Any
from sqlmodel import SQLModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CopilotConversation(SQLModel, table=True):
    __tablename__ = "copilot_conversations"

    id: str = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    owner_fingerprint: str = Field(default="admin")
    hermes_session_id: Optional[str] = Field(default=None)
    title: str = Field(default="Диалог с Hermes")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime = Field(index=True)


class CopilotMessage(SQLModel, table=True):
    __tablename__ = "copilot_messages"

    id: str = Field(default=None, primary_key=True)
    conversation_id: str = Field(foreign_key="copilot_conversations.id", index=True)
    role: str = Field(description="user|assistant|system")
    masked_content: str
    sources_json: str = Field(default="[]", description="JSON serialized list of sources")
    created_at: datetime = Field(default_factory=utc_now)

    @property
    def sources(self) -> List[Any]:
        try:
            return json.loads(self.sources_json)
        except Exception:
            return []

    @sources.setter
    def sources(self, value: List[Any]):
        self.sources_json = json.dumps(value)


class CopilotRun(SQLModel, table=True):
    __tablename__ = "copilot_runs"

    id: str = Field(default=None, primary_key=True)
    conversation_id: str = Field(foreign_key="copilot_conversations.id", index=True)
    correlation_id: str = Field(index=True)
    status: str = Field(default="running", description="running|completed|failed|stopped")
    context_ref_json: str = Field(default="{}")
    hermes_run_id: Optional[str] = Field(default=None, index=True)
    provider: str = Field(default="anthropic")
    model: str = Field(default="claude-3-5-haiku")
    tokens_used: int = Field(default=0)
    cost_usd: float = Field(default=0.0)
    latency_ms: int = Field(default=0)
    error_code: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)
