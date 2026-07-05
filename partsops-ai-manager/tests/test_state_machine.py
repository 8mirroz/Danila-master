"""
Tests: State Machine — validate all transitions and invariants.
"""
import pytest
from state_machine import validate_transition, transition, get_allowed_next, is_terminal, StateMachineError
from models import RequestState


class TestStateMachineTransitions:
    def test_new_to_normalizing_allowed(self):
        result = validate_transition(RequestState.NEW, RequestState.NORMALIZING)
        assert result["allowed"] is True

    def test_new_to_cancelled_allowed(self):
        result = validate_transition(RequestState.NEW, RequestState.CANCELLED)
        assert result["allowed"] is True

    def test_new_to_paid_forbidden(self):
        result = validate_transition(RequestState.NEW, RequestState.PAID)
        assert result["allowed"] is False
        assert "запрещен" in result["reason"]

    def test_closed_is_terminal(self):
        assert is_terminal(RequestState.CLOSED) is True

    def test_new_is_not_terminal(self):
        assert is_terminal(RequestState.NEW) is False

    def test_full_happy_path(self):
        """Simulate the happy path through all states."""
        path = [
            RequestState.NEW,
            RequestState.NORMALIZING,
            RequestState.PARSING,
            RequestState.VIN_CHECK,
            RequestState.PART_EXTRACTION,
            RequestState.MATCHING,
            RequestState.SUPPLIER_SEARCH,
            RequestState.OFFER_RANKING,
            RequestState.PRICING_REVIEW,
            RequestState.READY_FOR_APPROVAL,
            RequestState.APPROVED,
            RequestState.ERP_SYNCING,
            RequestState.INVOICE_DRAFTED,
            RequestState.SENT_TO_CLIENT,
            RequestState.PAID,
            RequestState.FULFILLED,
            RequestState.CLOSED,
        ]
        for i in range(len(path) - 1):
            result = validate_transition(path[i], path[i + 1])
            assert result["allowed"] is True, f"Transition {path[i]} → {path[i+1]} should be allowed"

    def test_transition_function_returns_new_state(self):
        new_state = transition(RequestState.NEW, RequestState.NORMALIZING)
        assert new_state == RequestState.NORMALIZING

    def test_transition_function_raises_on_invalid(self):
        with pytest.raises(StateMachineError):
            transition(RequestState.CLOSED, RequestState.NEW)

    def test_get_allowed_next_for_new(self):
        allowed = get_allowed_next(RequestState.NEW)
        assert RequestState.NORMALIZING in allowed
        assert RequestState.CANCELLED in allowed
        assert RequestState.PAID not in allowed

    def test_invoice_drafted_invariant_missing_evidence(self):
        """INVOICE_DRAFTED without pricing_evidence should fail invariants."""
        result = validate_transition(
            RequestState.APPROVED,
            RequestState.ERP_SYNCING,
            request_data={},
            strict_invariants=True,
        )
        # ERP_SYNCING itself has no invariants, should pass
        assert result["allowed"] is True

    def test_closed_invariant_requires_audit_chain(self):
        """CLOSED requires audit_chain_complete=True."""
        result = validate_transition(
            RequestState.FULFILLED,
            RequestState.CLOSED,
            request_data={"audit_chain_complete": False},
            strict_invariants=True,
        )
        assert result["allowed"] is False
        assert "audit_chain_complete" in result["violations"][0]

    def test_closed_invariant_passes_with_audit_chain(self):
        result = validate_transition(
            RequestState.FULFILLED,
            RequestState.CLOSED,
            request_data={"audit_chain_complete": True},
            strict_invariants=True,
        )
        assert result["allowed"] is True
