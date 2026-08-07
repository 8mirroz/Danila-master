import pytest
from app.automation.engines.policy_engine import check_policy
from models import PartRequest

def test_check_policy_none():
    res = check_policy(None)
    assert res["implemented"] is False
    assert res["status"] == "not_wired"
    assert res["ok"] is False

def test_check_policy_unsupported():
    res = check_policy(123)
    assert res["implemented"] is False
    assert res["status"] == "not_wired"

def test_check_policy_simple_field_dict_ok():
    payload = {
        "score": 0.95,
        "min_score": 0.80,
        "margin": 0.25,
        "min_margin": 0.10
    }
    res = check_policy(payload)
    assert res["implemented"] is True
    assert res["ok"] is True
    assert res["violations"] == []

def test_check_policy_simple_field_dict_violations():
    payload = {
        "score": 0.50,
        "min_score": 0.80,
        "margin": 0.05,
        "min_margin": 0.10
    }
    res = check_policy(payload)
    assert res["implemented"] is True
    assert res["ok"] is False
    assert len(res["violations"]) == 2

def test_check_policy_request_like():
    req = PartRequest(
        request_id="REQ-POL-001",
        tenant_id="default",
        status="APPROVED",
        source="api",
        raw_text="Policy test"
    )
    res = check_policy(req)
    assert "implemented" in res

def test_check_policy_nested_dict():
    req = PartRequest(
        request_id="REQ-POL-002",
        tenant_id="default",
        status="NEW",
        source="api",
        raw_text="Nested test"
    )
    res = check_policy({"request": req})
    assert "implemented" in res

def test_check_policy_margin_rate():
    res = check_policy({"margin_rate": 0.02, "min_margin": 0.05})
    assert res["implemented"] is True
    assert res["ok"] is False

