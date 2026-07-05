"""
PartsOps AI Manager v3 — State Machine
Validates state transitions, enforces invariants, emits state change events.
"""
from typing import Optional
from models import RequestState, ALLOWED_TRANSITIONS


class StateMachineError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class StateMachineInvariantError(Exception):
    """Raised when a state invariant is violated."""
    pass


# ──────────────────────────────────────────────
# Invariants per state
# ──────────────────────────────────────────────

def check_invariants(target_state: str, request_data: dict) -> list[str]:
    """
    Check state-specific invariants.
    Returns list of violations. Empty list = all invariants satisfied.
    """
    violations = []

    if target_state == RequestState.INVOICE_DRAFTED:
        if not request_data.get("pricing_evidence_json"):
            violations.append("INVOICE_DRAFTED требует наличия pricing_evidence_json")
        if not request_data.get("erp_quotation_ref"):
            violations.append("INVOICE_DRAFTED требует наличия erp_quotation_ref")
        if request_data.get("margin_policy_passed") is False:
            violations.append("INVOICE_DRAFTED требует выполнения margin_policy_passed=True")

    if target_state == RequestState.SENT_TO_CLIENT:
        if not request_data.get("erp_invoice_ref"):
            violations.append("SENT_TO_CLIENT требует наличия erp_invoice_ref")

    if target_state == RequestState.PAID:
        if not request_data.get("erp_payment_ref"):
            violations.append("PAID требует наличия erp_payment_ref")

    if target_state == RequestState.CLOSED:
        if not request_data.get("audit_chain_complete", False):
            violations.append("CLOSED требует выполнения audit_chain_complete=True")

    return violations


# ──────────────────────────────────────────────
# Transition validator
# ──────────────────────────────────────────────

def validate_transition(
    current_state: str,
    target_state: str,
    request_data: Optional[dict] = None,
    strict_invariants: bool = False,
) -> dict:
    """
    Validate a state transition.

    Returns:
        {"allowed": True/False, "reason": str, "violations": list}
    """
    allowed_next = ALLOWED_TRANSITIONS.get(current_state, [])

    if target_state not in allowed_next:
        return {
            "allowed": False,
            "reason": f"Переход {current_state} → {target_state} запрещен",
            "violations": [],
        }

    violations = []
    if request_data and strict_invariants:
        violations = check_invariants(target_state, request_data)
        if violations:
            return {
                "allowed": False,
                "reason": f"Нарушение инвариантов для статуса {target_state}",
                "violations": violations,
            }

    return {
        "allowed": True,
        "reason": f"Переход {current_state} → {target_state} корректен",
        "violations": [],
    }


def transition(
    current_state: str,
    target_state: str,
    request_data: Optional[dict] = None,
    strict_invariants: bool = False,
) -> str:
    """
    Perform a validated state transition.
    Returns the new state or raises StateMachineError.
    """
    result = validate_transition(current_state, target_state, request_data, strict_invariants)
    if not result["allowed"]:
        raise StateMachineError(f"{result['reason']}. Нарушения: {result['violations']}")
    return target_state


def get_allowed_next(current_state: str) -> list[str]:
    """Return list of valid next states from current state."""
    return ALLOWED_TRANSITIONS.get(current_state, [])


def is_terminal(state: str) -> bool:
    """Return True if the state has no allowed transitions."""
    return len(ALLOWED_TRANSITIONS.get(state, [])) == 0
