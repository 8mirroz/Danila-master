"""Policy checks engine — thin delegate to root policy_engine / simple field checks."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def check_policy(data: Any) -> dict:
    """
    Run lightweight policy checks.

    Preference order:
    1. Request-like object + root PolicyEngine / EvidenceGates
    2. Simple min_score / margin field rules on dict
    3. not_wired when nothing usable
    """
    if data is None:
        return {
            "implemented": False,
            "status": "not_wired",
            "reason": "no_policy_input; use root policy_engine.policy_engine / EvidenceGates",
            "violations": [],
            "ok": False,
        }

    # Request-like object (PartRequest or duck-typed)
    if not isinstance(data, dict) and hasattr(data, "request_id"):
        return _check_request_like(data)

    if not isinstance(data, dict):
        return {
            "implemented": False,
            "status": "not_wired",
            "reason": "unsupported_policy_input; use root policy_engine / EvidenceGates",
            "violations": [],
            "ok": False,
        }

    payload: Dict[str, Any] = data

    # Nested request object
    request_obj = payload.get("request")
    if request_obj is not None and hasattr(request_obj, "request_id"):
        session = payload.get("session")
        return _check_request_like(request_obj, session=session)

    # Simple field-based rules
    has_score = "min_score" in payload or "match_score" in payload or "score" in payload
    has_margin = "margin" in payload or "margin_rate" in payload
    if has_score or has_margin:
        violations = _simple_field_violations(payload)
        return {
            "implemented": True,
            "status": "ok" if not violations else "partial",
            "reason": None if not violations else "policy_violations",
            "violations": violations,
            "ok": len(violations) == 0,
        }

    return {
        "implemented": False,
        "status": "not_wired",
        "reason": "no_usable_policy_fields; use root policy_engine.policy_engine / EvidenceGates",
        "violations": [],
        "ok": False,
    }


def _simple_field_violations(payload: Dict[str, Any]) -> List[str]:
    violations: List[str] = []
    min_score = payload.get("min_score")
    if min_score is None:
        min_score = 70.0
    score = payload.get("match_score", payload.get("score"))
    if score is not None:
        try:
            if float(score) < float(min_score):
                violations.append(f"score_below_min:{score}<{min_score}")
        except (TypeError, ValueError):
            violations.append("score_not_numeric")

    margin = payload.get("margin", payload.get("margin_rate"))
    if margin is not None:
        try:
            m = float(margin)
            # accept either 0-1 fraction or 0-100 percent
            if m > 1.0:
                m = m / 100.0
            if m < 0.10:
                violations.append(f"margin_below_min:{margin}")
            if m > 0.50:
                violations.append(f"margin_above_auto_max:{margin}")
        except (TypeError, ValueError):
            violations.append("margin_not_numeric")

    return violations


def _check_request_like(request: Any, session: Optional[Any] = None) -> dict:
    violations: List[str] = []
    try:
        from policy_engine import policy_engine as root_pe
    except Exception as exc:
        logger.warning("root policy_engine unavailable: %s", exc)
        return {
            "implemented": False,
            "status": "not_wired",
            "reason": f"root_policy_engine_unavailable:{exc}",
            "violations": [],
            "ok": False,
        }

    try:
        if session is not None and hasattr(root_pe, "auto_advance_policy"):
            allowed = root_pe.auto_advance_policy(request, session)
            if not allowed:
                violations.append("auto_advance_policy_denied")
            return {
                "implemented": True,
                "status": "ok" if not violations else "partial",
                "reason": None if not violations else "policy_violations",
                "violations": violations,
                "ok": len(violations) == 0,
                "auto_advance": bool(allowed),
            }

        # Without session: surface gates that don't need DB if payload-like fields exist
        gates = getattr(root_pe, "gates", None)
        if gates is not None and hasattr(gates, "gate_match_confidence"):
            try:
                g = gates.gate_match_confidence(request)
                if not g.get("passed"):
                    violations.append(f"match_confidence:{g.get('reason')}")
            except Exception:
                pass
            try:
                g = gates.gate_pricing_policy(request)
                if not g.get("passed"):
                    violations.append(f"pricing_policy:{g.get('reason')}")
            except Exception:
                pass

            if violations or True:
                return {
                    "implemented": True,
                    "status": "partial" if violations else "ok",
                    "reason": "gates_without_session" if not session else None,
                    "violations": violations,
                    "ok": len(violations) == 0,
                }
    except Exception as exc:
        logger.exception("check_policy request-like failed")
        return {
            "implemented": True,
            "status": "error",
            "reason": str(exc),
            "violations": [],
            "ok": False,
        }

    return {
        "implemented": True,
        "status": "partial",
        "reason": "request_present_but_limited_checks",
        "violations": violations,
        "ok": True,
    }
