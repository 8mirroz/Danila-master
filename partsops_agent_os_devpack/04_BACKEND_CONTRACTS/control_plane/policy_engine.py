from dataclasses import dataclass
from typing import List

@dataclass
class PolicyResult:
    passed: bool
    reasons: List[str]
    requires_admin: bool = False

class PolicyEngine:
    def check_invoice_gate(self, *, admin_approved: bool, evidence_complete: bool, margin_ok: bool, draft_only: bool) -> PolicyResult:
        reasons = []
        if not admin_approved:
            reasons.append("admin approval missing")
        if not evidence_complete:
            reasons.append("evidence incomplete")
        if not margin_ok:
            reasons.append("margin policy failed")
        if not draft_only:
            reasons.append("invoice must be draft only")
        return PolicyResult(passed=not reasons, reasons=reasons, requires_admin=not admin_approved)

    def check_matching_review(self, *, match_score: float, analog_used: bool, safety_critical: bool, stale_price: bool) -> PolicyResult:
        reasons = []
        if match_score < 0.90:
            reasons.append("match score below 0.90")
        if analog_used:
            reasons.append("analog used")
        if safety_critical:
            reasons.append("safety critical part")
        if stale_price:
            reasons.append("stale price")
        return PolicyResult(passed=True, reasons=reasons, requires_admin=bool(reasons))
