"""
PartsOps AI Manager v3 — Tool Permission Guard
Движок контроля разрешений на вызов инструментов (tools) с RBAC-политиками.
Контракт: 04_BACKEND_CONTRACTS/agents/tool_permission_guard.py
"""

from __future__ import annotations

from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolPolicy:
    """Политика доступа к конкретному инструменту для роли."""
    tool_name: str
    allowed_roles: Set[str]
    require_approval: bool = False
    allowed_tenants: Optional[Set[str]] = None  # None = все тенанты


@dataclass(frozen=True)
class ApprovalTicket:
    """Билет на human approval (создаётся при require_approval=True)."""
    tool_name: str
    role: str
    tenant_id: str
    requested_by: str
    status: str = "pending"  # pending | approved | rejected


class ToolPermissionGuard:
    """
    Централизованный гвард инструментов.
    Используется до фактического вызовом любого инструмента (каталог, прайсинг и т.д.).
    """

    BUILTIN_POLICIES: List[ToolPolicy] = [
        ToolPolicy(
            tool_name="catalog_search",
            allowed_roles={"admin", "manager", "finance"},
        ),
        ToolPolicy(
            tool_name="supplier_match",
            allowed_roles={"admin", "manager"},
        ),
        ToolPolicy(
            tool_name="pricing_compute",
            allowed_roles={"admin", "manager", "finance"},
        ),
        ToolPolicy(
            tool_name="pricing_override",
            allowed_roles={"admin"},
            require_approval=True,
        ),
        ToolPolicy(
            tool_name="invoice_generate",
            allowed_roles={"admin", "manager"},
            require_approval=True,
        ),
        ToolPolicy(
            tool_name="pii_mask",
            allowed_roles={"admin", "manager", "finance"},
        ),
        ToolPolicy(
            tool_name="event_audit",
            allowed_roles={"admin", "manager", "finance"},
        ),
        ToolPolicy(
            tool_name="rbac_admin",
            allowed_roles={"admin"},
            require_approval=True,
        ),
        ToolPolicy(
            tool_name="learning_correction",
            allowed_roles={"admin", "manager"},
            require_approval=True,
        ),
        ToolPolicy(
            tool_name="erp_sync",
            allowed_roles={"admin"},
            require_approval=True,
        ),
    ]

    def __init__(self) -> None:
        self._policies: Dict[str, ToolPolicy] = {
            p.tool_name: p
            for p in self.BUILTIN_POLICIES
        }
        self._approval_queue: List[ApprovalTicket] = []

    def register_policy(self, policy: ToolPolicy) -> None:
        """Добавить/обновить политику для инструмента."""
        self._policies[policy.tool_name] = policy

    def check(
        self,
        tool_name: str,
        role: str,
        tenant_id: str,
    ) -> Dict:
        """
        Проверяет, можно ли вызвать инструмент.
        Возвращает dict: {allowed: bool, reason: str, approval_required: bool}
        """
        policy = self._policies.get(tool_name)
        if policy is None:
            # Инструмент не зарегистрирован — по умолчанию запрещён
            return {
                "allowed": False,
                "reason": f"tool '{tool_name}' is not registered in permission guard",
                "approval_required": True,
            }

        if role not in policy.allowed_roles:
            return {
                "allowed": False,
                "reason": (
                    f"role '{role}' not in allowed roles: "
                    f"{sorted(policy.allowed_roles)}"
                ),
                "approval_required": policy.require_approval,
            }

        if policy.allowed_tenants is not None:
            if tenant_id not in policy.allowed_tenants:
                return {
                    "allowed": False,
                    "reason": f"tenant '{tenant_id}' not allowed for '{tool_name}'",
                    "approval_required": policy.require_approval,
                }

        return {
            "allowed": True,
            "reason": "allowed",
            "approval_required": policy.require_approval,
        }

    def request_approval(
        self,
        tool_name: str,
        role: str,
        tenant_id: str,
        requested_by: str = "system",
    ) -> ApprovalTicket:
        """Создать approval ticket (pending)."""
        ticket = ApprovalTicket(
            tool_name=tool_name,
            role=role,
            tenant_id=tenant_id,
            requested_by=requested_by,
        )
        self._approval_queue.append(ticket)
        return ticket

    def approve(self, ticket: ApprovalTicket) -> None:
        ticket.status = "approved"

    def reject(self, ticket: ApprovalTicket) -> None:
        ticket.status = "rejected"

    def list_pending(self) -> List[ApprovalTicket]:
        return [t for t in self._approval_queue if t.status == "pending"]


# Singleton-гвард
permission_guard = ToolPermissionGuard()
