"""
Tests for Observability & Correlation ID (Phase 6)
"""
import pytest
import time
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from database import engine
from models import LLMUsageLog
from middleware import get_correlation_id, correlation_id_var
from main import app
from llm import call_llm

@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


def test_correlation_id_middleware_injects_headers():
    client = TestClient(app)
    
    # 1. Without X-Correlation-ID header, middleware should generate one
    response = client.get("/api/state-machine/PART_EXTRACTION")
    assert response.status_code == 200
    assert "X-Correlation-ID" in response.headers
    assert response.headers["X-Correlation-ID"].startswith("CORR-")
    assert "X-Response-Time-Ms" in response.headers
    
    # 2. With X-Correlation-ID header, middleware should reuse it
    custom_id = "MY-CUSTOM-CORR-123"
    response2 = client.get("/api/state-machine/PART_EXTRACTION", headers={"X-Correlation-ID": custom_id})
    assert response2.status_code == 200
    assert response2.headers["X-Correlation-ID"] == custom_id
    assert "X-Response-Time-Ms" in response2.headers


@patch("llm._get_client")
@patch("llm._get_budget_guard")
def test_llm_call_records_usage_log(mock_budget, mock_client):
    # Setup budget mock
    mock_bg = MagicMock()
    mock_bg.check_budget.return_value = {"allowed": True, "reason": "OK"}
    mock_budget.return_value = mock_bg

    # Setup openai mock client
    mock_openai = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Response content"
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    
    # Mock token usage
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 100
    mock_usage.completion_tokens = 50
    mock_usage.total_tokens = 150
    mock_completion.usage = mock_usage
    
    mock_openai.chat.completions.create.return_value = mock_completion
    mock_client.return_value = mock_openai

    # Set correlation ID context
    token = correlation_id_var.set("TEST-LLM-CORR")
    try:
        content = call_llm("Test prompt", system_prompt="Test system")
        assert content == "Response content"
        
        # Verify database logs
        with Session(engine) as session:
            logs = session.exec(select(LLMUsageLog)).all()
            assert len(logs) == 1
            log = logs[0]
            assert log.correlation_id == "TEST-LLM-CORR"
            assert log.status == "ok"
            assert log.prompt_tokens == 100
            assert log.completion_tokens == 50
            assert log.total_tokens == 150
            assert log.cost_usd > 0
    finally:
        correlation_id_var.reset(token)


def test_observability_endpoints():
    client = TestClient(app)
    
    import os
    token = os.getenv("PARTSOPS_API_TOKEN", "")
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    # Populate database with dummy logs
    with Session(engine) as session:
        log1 = LLMUsageLog(
            provider="mock_provider",
            model="mock_model_1",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.0006,
            latency_ms=120,
            status="ok",
            correlation_id="CORR-1",
        )
        log2 = LLMUsageLog(
            provider="mock_provider",
            model="mock_model_2",
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
            cost_usd=0.0012,
            latency_ms=250,
            status="ok",
            correlation_id="CORR-2",
        )
        session.add(log1)
        session.add(log2)
        session.commit()

    # 1. Test traces endpoint
    response = client.get("/api/admin/observability/traces", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["correlation_id"] == "CORR-2"
    assert data[1]["correlation_id"] == "CORR-1"

    # 2. Test llm-costs endpoint
    response = client.get("/api/admin/observability/llm-costs", headers=headers)
    assert response.status_code == 200
    costs = response.json()
    assert costs["count"] == 2
    assert pytest.approx(costs["total_cost_usd"], 0.00001) == 0.0018
    assert costs["by_provider"]["mock_provider"] == pytest.approx(0.0018, 0.00001)
    assert costs["by_model"]["mock_model_1"] == pytest.approx(0.0006, 0.00001)
    assert costs["by_model"]["mock_model_2"] == pytest.approx(0.0012, 0.00001)


def test_request_gates_endpoint():
    client = TestClient(app)
    from models import PartRequest, RequestState
    
    with Session(engine) as session:
        req = PartRequest(
            request_id="REQ-GATES-1",
            tenant_id="default",
            source="manual",
            status=RequestState.NEW,
            customer_name="John Doe",
            customer_phone_masked="+7 (999) ***-45-67",
            customer_email_masked="j***@example.com",
            parts_json=json.dumps([{"name": "Filter", "match_score": 90.0, "quantity": 1}]),
        )
        session.add(req)
        session.commit()
        
    response = client.get("/api/requests/REQ-GATES-1/gates")
    assert response.status_code == 200
    res = response.json()
    assert res["request_id"] == "REQ-GATES-1"
    gates = res["gates"]
    assert "PII_SAFE" in gates
    assert gates["PII_SAFE"]["passed"] is True
    assert "EVENT_CHAIN_VALID" in gates
    assert "MATCH_CONFIDENCE" in gates
    assert gates["MATCH_CONFIDENCE"]["passed"] is True
    assert "PRICING_POLICY" in gates
    assert "OPERATOR_APPROVAL" in gates
    assert "DELIVERY_SAFE" in gates
    assert "ERP_SYNC_VALID" in gates
