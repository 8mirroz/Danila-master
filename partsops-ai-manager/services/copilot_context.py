"""
PartsOps AI Manager v3 — Server-Side Copilot Context Builder & Grounding Verification.
Builds PII-masked ContextEnvelope for Hermes runs and validates cited help sources.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from pii import mask_request_for_agent, mask_for_log
from state_machine import get_allowed_next
from services.help_service import get_help_sources_for_context


class CopilotContextRef(BaseModel):
    screen_id: str = Field(default="kanban_board", description="Active screen identifier")
    selected_request_id: Optional[str] = Field(default=None, description="Optional selected order ID")
    active_step: Optional[int] = Field(default=None, description="Optional active workflow step number")


class ContextEnvelope(BaseModel):
    screen_id: str
    screen_title: str
    selected_request: Optional[Dict[str, Any]] = None
    allowed_next_statuses: List[str] = Field(default_factory=list)
    evidence_summary: Optional[Dict[str, Any]] = None
    blocking_reasons: List[str] = Field(default_factory=list)
    allowed_user_actions: List[Dict[str, str]] = Field(default_factory=list)
    available_help_sources: List[Dict[str, str]] = Field(default_factory=list)
    timestamp: str


SCREEN_TITLES: Dict[str, str] = {
    "kanban_board": "Канбан-доска заказов",
    "order_details": "Детализация заказа",
    "suppliers_page": "Матрица и реестр поставщиков",
    "invoices_registry": "Реестр счетов",
    "contract_control": "Контрактный контроль",
    "agent_os_panel": "Операторская консоль Agent OS",
}


import re

def build_context_envelope(
    session: Session,
    tenant_id: str,
    context_ref: CopilotContextRef,
    user_role: str = "manager",
    query: Optional[str] = None
) -> ContextEnvelope:
    screen_id = context_ref.screen_id
    screen_title = SCREEN_TITLES.get(screen_id, "Операционный экран")

    order_dict: Optional[Dict[str, Any]] = None
    allowed_next: List[str] = []
    blocking_reasons: List[str] = []
    evidence_summary: Optional[Dict[str, Any]] = None

    target_request_id = context_ref.selected_request_id
    if not target_request_id and query:
        # Real IDs are like REQ-ED8AE3E0 / REQ-LIVE-20260805, not only digits.
        match = re.search(r"REQ-[A-Z0-9][A-Z0-9_-]{2,}", query, re.IGNORECASE)
        if match:
            target_request_id = match.group(0).upper()

    resolved_request_id: Optional[str] = None

    if target_request_id:
        from models import PartRequest
        # Check by request_id (e.g. 'REQ-1001') or numeric id
        stmt = select(PartRequest).where(
            (PartRequest.request_id == target_request_id) | (PartRequest.request_id == str(target_request_id).upper()),
            PartRequest.tenant_id == tenant_id
        )
        order = session.exec(stmt).first()
        if not order:
            try:
                numeric_id = int(str(target_request_id).replace("REQ-", "").strip())
                stmt_num = select(PartRequest).where(
                    PartRequest.id == numeric_id,
                    PartRequest.tenant_id == tenant_id
                )
                order = session.exec(stmt_num).first()
            except ValueError:
                order = None

        if order:
            raw_dict = order.model_dump()
            order_dict = mask_request_for_agent(raw_dict)
            resolved_request_id = order.request_id
            
            # Extract allowed next state transitions
            current_status = getattr(order, "status", "DRAFT")
            if hasattr(current_status, "value"):
                current_status = current_status.value
            allowed_next = get_allowed_next(current_status)

            # Check blocking reasons
            if current_status == "BLOCKED" or getattr(order, "is_blocked", False):
                blocking_reasons.append("Заказ заблокирован: требуются ручное подтверждение Evidence Gates.")
            if getattr(order, "pricing_anomaly", False):
                blocking_reasons.append("Обнаружена ценовая аномалия: маржа выходит за допустимые границы.")

            evidence_summary = {
                "gate_vin_valid": getattr(order, "gate_vin_valid", True),
                "gate_price_margin": getattr(order, "gate_price_margin", True),
                "gate_supplier_sla": getattr(order, "gate_supplier_sla", True),
            }

    # Available UI actions for screen
    allowed_user_actions = [
        {"action": "open_screen", "label": "Открыть экран", "screen_id": screen_id}
    ]
    active_req_id = resolved_request_id or context_ref.selected_request_id
    if active_req_id:
        allowed_user_actions.append({
            "action": "open_request",
            "label": "Открыть карточку заказа",
            "request_id": active_req_id
        })

    # Get available help sources
    sources = get_help_sources_for_context(
        screen_id=screen_id,
        user_role=user_role,
        query=query,
        limit=3
    )

    formatted_sources = [
        {"source_id": s["source_id"], "title": s["title"]}
        for s in sources
    ]

    return ContextEnvelope(
        screen_id=screen_id,
        screen_title=screen_title,
        selected_request=order_dict,
        allowed_next_statuses=allowed_next,
        evidence_summary=evidence_summary,
        blocking_reasons=blocking_reasons,
        allowed_user_actions=allowed_user_actions,
        available_help_sources=formatted_sources,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


def validate_and_filter_sources(
    available_sources: List[Dict[str, str]],
    response_text: str
) -> List[Dict[str, str]]:
    """
    Validate that cited sources were actually present in the context envelope for this run
    AND were explicitly cited in the assistant's response text.
    """
    valid_sources = []
    response_lower = response_text.lower()

    for source in available_sources:
        s_id = source["source_id"]
        title = source.get("title", "")
        if s_id.lower() in response_lower or (title and title.lower() in response_lower):
            valid_sources.append(source)

    return valid_sources


def compact_envelope_for_hermes(envelope: ContextEnvelope, *, max_help: int = 3) -> Dict[str, Any]:
    """Shrink ContextEnvelope for Hermes prompts.

    Full order dumps (parts_json, match_evidence_json, …) blow token budgets and
    make NVIDIA fallback chains hang. Send only operator-relevant fields.
    """
    import json as _json

    order = envelope.selected_request
    compact_order: Optional[Dict[str, Any]] = None
    if order:
        parts_count = 0
        parts_preview: List[str] = []
        raw_parts = order.get("parts_json")
        if raw_parts:
            try:
                parts = _json.loads(raw_parts) if isinstance(raw_parts, str) else raw_parts
                if isinstance(parts, list):
                    parts_count = len(parts)
                    for p in parts[:4]:
                        if not isinstance(p, dict):
                            continue
                        name = p.get("name") or p.get("oem") or p.get("oem_number") or "позиция"
                        qty = p.get("quantity") or p.get("qty") or 1
                        parts_preview.append(f"{name} ×{qty}")
            except (TypeError, ValueError, _json.JSONDecodeError):
                pass

        vehicle = " ".join(
            str(x).strip()
            for x in (
                order.get("vehicle_make"),
                order.get("vehicle_model"),
                order.get("vehicle_year"),
            )
            if x
        ).strip() or None

        compact_order = {
            "request_id": order.get("request_id") or order.get("id"),
            "status": order.get("status"),
            "customer_name": order.get("customer_name"),
            "priority": order.get("priority"),
            "vehicle": vehicle,
            "vin_masked": order.get("vehicle_vin_masked"),
            "parts_count": parts_count,
            "parts_preview": parts_preview,
            "source": order.get("source"),
        }

    help_items = [
        {"source_id": s.get("source_id"), "title": s.get("title")}
        for s in (envelope.available_help_sources or [])[:max_help]
        if s.get("source_id")
    ]

    return {
        "screen_id": envelope.screen_id,
        "screen_title": envelope.screen_title,
        "selected_request": compact_order,
        "allowed_next_statuses": list(envelope.allowed_next_statuses or [])[:10],
        "evidence_summary": envelope.evidence_summary,
        "blocking_reasons": list(envelope.blocking_reasons or [])[:8],
        "allowed_user_actions": list(envelope.allowed_user_actions or [])[:6],
        "available_help_sources": help_items,
    }


def build_hermes_instructions(envelope: ContextEnvelope) -> str:
    """Compact Russian system instructions + slim context for Hermes runs."""
    compact = compact_envelope_for_hermes(envelope)
    compact_json = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    return (
        "Ты Hermes — read-only операционный помощник PartsOps Admin Cockpit. "
        "Отвечай только по-русски, кратко, в Markdown.\n"
        "Правила:\n"
        "1) READ-ONLY: не меняй статусы, не обещай закупки/списания, не вызывай write-tools.\n"
        "2) Если selected_request есть — объясни статус, блокировки, Evidence Gates и allowed_next_statuses.\n"
        "3) Если selected_request null — опиши экран и подскажи выбрать/ввести REQ-…\n"
        "4) Не выводи сырой JSON, debug-дампы, allowlist-перечисления.\n"
        "5) Навигацию предлагай только по allowed_user_actions.\n"
        f"Контекст (JSON): {compact_json}"
    )
