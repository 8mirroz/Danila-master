"""
PartsOps AI Manager v3 — Policy Engine
Контракт: 04_BACKEND_CONTRACTS/policy_engine.py
Объединяет state_machine + workflow_policies + security_policy в единый движок политик.
"""

from __future__ import annotations

import re
import json
from typing import Dict, Any, Optional
from enum import Enum

from sqlmodel import Session
from state_machine import validate_transition, transition, StateMachineError
from tool_permission_guard import permission_guard
from rbac import get_current_tenant, get_current_role
from event_store import verify_event_chain, get_events
from models import PartRequest, RequestState, EventType


class PolicyViolation(Exception):
    """Политика нарушена."""
    pass


def _gate_result(passed: bool, reason: str, evidence: dict = None) -> dict:
    return {
        "passed": passed,
        "reason": reason,
        "evidence": evidence or {},
        "policy_version": "3.0"
    }


class EvidenceGates:
    """7 защитных гейтов перед генерацией счетов и отправкой."""

    @staticmethod
    def gate_pii_safe(payload: dict) -> dict:
        """Проверяет отсутствие утечек PII (raw VIN/email/телефон) в payload."""
        payload_str = json.dumps(payload, ensure_ascii=False)
        
        # Checking for raw VIN (17 chars, no I/O/Q)
        vin_pattern = r"\b[A-HJ-NPR-Z0-9]{17}\b"
        if re.search(vin_pattern, payload_str):
            return _gate_result(False, "Обнаружен возможный raw VIN в payload", {"pattern": "VIN"})
            
        email_pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
        if re.search(email_pattern, payload_str):
            return _gate_result(False, "Обнаружен возможный raw email в payload", {"pattern": "Email"})
            
        return _gate_result(True, "PII не обнаружены")

    @staticmethod
    def gate_event_chain_valid(request_id: str, session: Session, tenant_id: str) -> dict:
        """Проверяет цепочку хешей событий."""
        res = verify_event_chain(request_id, session, tenant_id=tenant_id)
        if not res["valid"]:
            return _gate_result(False, res.get("reason", "Нарушена цепочка событий"), {"chain_result": res})
        return _gate_result(True, "Цепочка событий валидна", {"total_events": res["total_events"]})

    @staticmethod
    def gate_match_confidence(request: PartRequest) -> dict:
        """Блокирует авто-переход, если match_score хотя бы одного элемента каталога < 70%."""
        if not request.parts_json:
            return _gate_result(False, "Нет данных о запчастях")
        try:
            parts = json.loads(request.parts_json)
        except Exception:
            return _gate_result(False, "Ошибка парсинга parts_json")
            
        low_confidence_items = []
        for part in parts:
            score = part.get("match_score", 0.0)
            if score < 70.0:
                low_confidence_items.append(part.get("name", "Unknown"))
                
        if low_confidence_items:
            return _gate_result(False, f"Низкая уверенность матчинга для: {', '.join(low_confidence_items)}")
        return _gate_result(True, "Уверенность матчинга достаточна")

    @staticmethod
    def gate_pricing_policy(request: PartRequest) -> dict:
        """Проверяет маржу на выход за границы (> 50% требует ручного одобрения, < 10% отклоняется)."""
        if not request.pricing_evidence_json:
            return _gate_result(False, "Нет данных о ценах")
        try:
            evidence = json.loads(request.pricing_evidence_json)
        except Exception:
            return _gate_result(False, "Ошибка парсинга pricing_evidence_json")
            
        line_items = evidence.get("line_items", [])
        for item in line_items:
            margin = item.get("margin", 0.0)
            if margin < 0.10:
                return _gate_result(False, f"Маржа ниже допустимого минимума 10% для {item.get('part_name')}", {"margin": margin})
            if margin > 0.50 and request.status != RequestState.APPROVED:
                return _gate_result(False, f"Маржа выше 50% требует ручного одобрения для {item.get('part_name')}", {"margin": margin})
                
        return _gate_result(True, "Ценовая политика соблюдена")

    @staticmethod
    def gate_operator_approval(request_id: str, session: Session, tenant_id: str) -> dict:
        """Проверяет наличие события одобрения оператором."""
        events = get_events(request_id, session, tenant_id=tenant_id)
        for event in events:
            if event.event_type == EventType.STATE_CHANGED:
                payload = json.loads(event.payload_json) if event.payload_json else {}
                if payload.get("to") == RequestState.APPROVED:
                    return _gate_result(True, "Найдено событие одобрения", {"event_id": event.event_id})
        return _gate_result(False, "Событие одобрения оператором не найдено")

    @staticmethod
    def gate_delivery_safe(payload: dict) -> dict:
        """Проверяет корректность адресата и очищает текст от prompt-injection."""
        text = json.dumps(payload, ensure_ascii=False).lower()
        injection_phrases = ["ignore previous instructions", "system override", "forget all", "drop table"]
        for phrase in injection_phrases:
            if phrase in text:
                return _gate_result(False, "Обнаружена попытка prompt-injection", {"phrase": phrase})
        return _gate_result(True, "Текст безопасен для доставки")

    @staticmethod
    def gate_erp_sync_valid(request: PartRequest) -> dict:
        """Проверяет готовность данных к отправке в ERP (наличие всех реквизитов и счетов)."""
        if not request.erp_invoice_ref:
            return _gate_result(False, "Отсутствует ссылка на счет ERP")
        if not request.customer_name or request.customer_name == "Unknown":
            return _gate_result(False, "Отсутствует имя клиента")
        return _gate_result(True, "Данные готовы к синхронизации с ERP")


class PolicyEngine:
    """
    Движок политики:
    - Переходы статусов
    - Права доступа к инструментам
    - Workflow (схемы обработки)
    - Protective Gates
    """

    # Допустимые статусы (из devpack: workflow_policies.yaml)
    VALID_STATUSES = {
        "new", "validated", "extracted", "matched",
        "priced", "approved", "in_progress", "shipped",
        "delivered", "closed", "rejected", "spam",
    }

    def __init__(self) -> None:
        self._tenant_id: Optional[str] = None
        self._role: Optional[str] = None
        self.gates = EvidenceGates()

    def bootstrap_context(self, tenant_id: str, role: str) -> None:
        """Установить тенант/роль для текущего контекста."""
        self._tenant_id = tenant_id
        self._role = role

    # ──────────────────────────────────────────────
    # State transitions
    # ──────────────────────────────────────────────

    def transition_allowed(
        self,
        from_state: str,
        to_state: str,
    ) -> bool:
        """Проверить, разрешён ли переход между статусами."""
        try:
            validate_transition(from_state, to_state)
            return True
        except StateMachineError:
            return False

    # ──────────────────────────────────────────────
    # Tool permissions
    # ──────────────────────────────────────────────

    def tool_allowed(self, tool_name: str) -> Dict[str, Any]:
        """Проверить, разрешён ли вызов инструмента в текущем контексте."""
        if self._tenant_id is None or self._role is None:
            raise PolicyViolation("PolicyEngine context not initialized")

        result = permission_guard.check(
            tool_name, self._role, self._tenant_id
        )
        if result["approval_required"] and not result["allowed"]:
            ticket = permission_guard.request_approval(
                tool_name, self._role, self._tenant_id
            )
            result["approval_ticket"] = ticket
        return result

    # ──────────────────────────────────────────────
    # Workflow routing
    # ──────────────────────────────────────────────

    def route_intake_workflow(self, state: Dict) -> str:
        """
        Определить следующий шаг workflow.
        Возвращает имя узла (node) для LangGraph.
        """
        is_spam = state.get("is_spam", False)
        if is_spam:
            return "reject_spam"
        validation = state.get("validation_status", "")
        if validation != "PASSED":
            return "reject_invalid"
        return "continue_extraction"


# Singleton-экземпляр
policy_engine = PolicyEngine()
