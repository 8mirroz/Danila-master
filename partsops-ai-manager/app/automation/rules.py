"""
Policy / rules layer.

Stores policy definitions in YAML under ``automation/policies/`` and
evaluates them with a tiny typed rule engine. Each policy is a
named rule tuple: (condition, action, severity).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

from app.automation.context import AutomationContext

POLICIES_DIR = os.path.join(os.path.dirname(__file__), "policies")
POLICY_CACHE: Optional[Dict[str, Any]] = None


class PolicyError(Exception):
    status_code = 422


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


ConditionFn = Callable[[AutomationContext, Dict[str, Any]], Tuple[bool, Dict[str, Any]]]
ActionFn = Callable[[AutomationContext, Dict[str, Any], Dict[str, Any]], Dict[str, Any]]


# ---- persistence -------------------------------------------------------------

def _normalize_policy_values(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = {}
    for key, value in data.items():
        if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
            normalized[key] = value[0]
        else:
            normalized[key] = value
    return normalized


def _load_policies(force_reload: bool = False) -> Dict[str, Any]:
    global POLICY_CACHE
    if POLICY_CACHE and not force_reload:
        return POLICY_CACHE
    policies: Dict[str, Any] = {}
    if os.path.isdir(POLICIES_DIR):
        for name in sorted(os.listdir(POLICIES_DIR)):
            if not name.endswith(".yaml"):
                continue
            path = os.path.join(POLICIES_DIR, name)
            policy_name = os.path.splitext(name)[0]
            policies[policy_name] = _normalize_policy_values(_parse_policy_file(path))
    POLICY_CACHE = policies
    return policies


def _parse_policy_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    data: Dict[str, Any] = {}
    current = None
    current_value: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current is not None:
            current_value.append(stripped[2:].strip())
            continue
        if ":" not in stripped:
            if current is not None and current_value:
                current_value.append(stripped)
            continue
        if current is not None:
            data[current] = current_value
        key, value = stripped.split(":", 1)
        current = key.strip()
        value = value.strip()
        current_value = [] if value in {"", "[]", "{}"} else [value]
    if current is not None:
        data[current] = current_value
    data.setdefault("name", os.path.splitext(os.path.basename(path))[0])
    data.setdefault("enabled", True)
    data.setdefault("severity", "medium")
    data.setdefault("condition", "default")
    data.setdefault("action", "log")
    return data


# ---- conditions --------------------------------------------------------------

def _condition_default(context: AutomationContext, params: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    return True, {"params": params}


def _condition_customer_tier(context: AutomationContext, params: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    tier = (context.payload or {}).get("customer_tier")
    allowed = _normalize_list_param(params.get("allowed_tiers"))
    details = {"customer_tier": tier, "allowed_tiers": allowed}
    if not allowed:
        return True, details
    return tier in allowed, details


def _condition_request_age(context: AutomationContext, params: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    created_at = (context.payload or {}).get("created_at")
    max_age_hours = _coerce_float(params.get("max_age_hours"), 24)
    details = {"created_at": created_at, "max_age_hours": max_age_hours}
    if created_at is None:
        return True, details
    try:
        requested_at = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return False, details
    age_hours = (_utcnow() - requested_at).total_seconds() / 3600.0
    details["age_hours"] = round(age_hours, 2)
    return age_hours <= max_age_hours, details


def _condition_request_amount(context: AutomationContext, params: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    amount_raw = (context.payload or {}).get("amount", 0)
    try:
        amount = float(amount_raw)
    except Exception:  # noqa: BLE001
        amount = 0.0
    max_amount = _coerce_float(params.get("max_amount"), 10 ** 9)
    details = {"amount": amount, "max_amount": max_amount}
    return amount <= max_amount, details


def _coerce_float(value: Any, fallback: float) -> float:
    if value is None:
        return fallback
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return fallback
    try:
        return float(text)
    except Exception:  # noqa: BLE001
        return fallback


def _normalize_list_param(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    return [part.strip() for part in text.split(",") if part.strip()]


_CONDITIONS: Dict[str, ConditionFn] = {
    "default": _condition_default,
    "customer_tier": _condition_customer_tier,
    "request_age": _condition_request_age,
    "request_amount": _condition_request_amount,
}


# ---- actions ---------------------------------------------------------------

def _action_log(context: AutomationContext, params: Dict[str, Any], details: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "log", "action": "log", "details": details, "message": str(params.get("message", "policy triggered"))}


def _action_pass(context: AutomationContext, params: Dict[str, Any], details: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "pass", "action": "pass", "details": details}


def _action_deny(context: AutomationContext, params: Dict[str, Any], details: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "deny", "action": "deny", "reason": str(params.get("reason", "policy rejected request")), "details": details}


def _normalize_enabled(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "y"}
    return False


_ACTIONS: Dict[str, ActionFn] = {
    "allow": _action_pass,
    "pass": _action_pass,
    "log": _action_log,
    "reject": _action_deny,
    "deny": _action_deny,
    "block": _action_deny,
}


# ---- engine methods ----------------------------------------------------------

def evaluate_policy(name: str, context: AutomationContext) -> Dict[str, Any]:
    policies = _load_policies()
    policy = policies.get(name)
    if not policy:
        raise PolicyError(f"Unknown policy: {name}")
    if not _normalize_enabled(policy.get("enabled", True)):
        return {"status": "skipped", "policy": name, "reason": "disabled"}
    condition_fn = _CONDITIONS.get(str(policy.get("condition", "default")), _condition_default)
    action_fn = _ACTIONS.get(str(policy.get("action", "log")), _action_log)
    matched, details = condition_fn(context, dict(policy))
    result = {"policy": name, "matched": matched, "details": details}
    if not matched:
        return {**result, "status": "fail"}
    action_result = action_fn(context, dict(policy), details)
    return {**result, "status": action_result.get("status", "pass"), "action_result": action_result}


def run_policy_checks(context: AutomationContext) -> Dict[str, Any]:
    policies = _load_policies()
    policy_results = {}
    failed = []
    blocked = []
    for policy_name, policy in policies.items():
        if not _normalize_enabled(policy.get("enabled", True)):
            continue
        summary = evaluate_policy(policy_name, context)
        policy_results[policy_name] = summary
        if summary.get("status") == "fail":
            failed.append(policy_name)
        if summary.get("status") == "block":
            blocked.append(policy_name)
    status = "blocked" if blocked else "failed" if failed else "passed"
    return {"status": status, "policies": policy_results, "failed": failed, "blocked": blocked}


def policy_check(context: AutomationContext) -> Dict[str, Any]:
    return run_policy_checks(context)


