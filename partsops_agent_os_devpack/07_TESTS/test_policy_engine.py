from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1] / "04_BACKEND_CONTRACTS"))
from control_plane.policy_engine import PolicyEngine


def test_invoice_gate_blocks_without_admin():
    engine = PolicyEngine()
    result = engine.check_invoice_gate(admin_approved=False, evidence_complete=True, margin_ok=True, draft_only=True)
    assert not result.passed
    assert result.requires_admin


def test_matching_review_required_for_analog():
    engine = PolicyEngine()
    result = engine.check_matching_review(match_score=0.95, analog_used=True, safety_critical=False, stale_price=False)
    assert result.requires_admin
