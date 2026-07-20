"""Tests for LLM circuit breaker."""
import pytest
from unittest.mock import patch, MagicMock
from llm import call_llm, _provider_failures, _PROVIDER_FAILURE_THRESHOLD


def test_circuit_breaker_opens_after_failures(monkeypatch):
    failing_provider = MagicMock()
    failing_provider.name = "test_provider"
    failing_provider.enabled = True
    failing_provider.get_models.return_value = ["test-model"]

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("provider down")

    with patch("llm.PROVIDERS", [failing_provider]):
        with patch("llm._get_client", return_value=mock_client):
            with patch("llm._get_budget_guard") as mock_budget:
                mock_budget.return_value.check_budget.return_value = {"allowed": True}

                with pytest.raises(RuntimeError):
                    call_llm("test prompt")
                assert _provider_failures.get("test_provider", 0) == 1

                with pytest.raises(RuntimeError):
                    call_llm("test prompt")
                assert _provider_failures.get("test_provider", 0) >= _PROVIDER_FAILURE_THRESHOLD


def test_circuit_breaker_resets_on_success(monkeypatch):
    provider = MagicMock()
    provider.name = "test_provider_reset"
    provider.enabled = True
    provider.get_models.return_value = ["test-model"]

    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content="ok"))]
    mock_completion.usage = None
    mock_client.chat.completions.create.return_value = mock_completion

    with patch("llm.PROVIDERS", [provider]):
        with patch("llm._get_client", return_value=mock_client):
            with patch("llm._get_budget_guard") as mock_budget:
                mock_budget.return_value.check_budget.return_value = {"allowed": True}
                mock_budget.return_value.record_usage.return_value = None

                result = call_llm("test prompt")
                assert result == "ok"
                assert _provider_failures.get("test_provider_reset", 0) == 0
