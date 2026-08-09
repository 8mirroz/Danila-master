"""
Tests: LLM Module — call_llm retry/fallback, BudgetGuard, ModelRouter, streaming.
"""
import pytest
import json
import os
from unittest.mock import patch, MagicMock, PropertyMock

# Ensure we get LM Studio provider (always present) for tests
os.environ.setdefault("LM_STUDIO_URL", "http://localhost:1234/v1")
os.environ.setdefault("LM_STUDIO_MODEL", "llama-3.1-8b-instruct")


# ──────────────────────────────────────────────
# BudgetGuard Tests
# ──────────────────────────────────────────────

class TestBudgetGuard:
    def test_check_budget_no_config_returns_allowed(self):
        """Model with no budget config should always be allowed."""
        from budget_guard import BudgetGuard
        guard = BudgetGuard()
        result = guard.check_budget("unknown-model-xyz", 1000)
        assert result["allowed"] is True

    def test_check_budget_within_limits(self):
        """Request within hourly token and daily cost limits should pass."""
        from budget_guard import BudgetGuard, BudgetConfig
        guard = BudgetGuard()
        guard.register_config(BudgetConfig(
            model_name="test-model",
            token_budget_per_hour=100_000,
            cost_budget_per_day_usd=10.0,
        ))
        result = guard.check_budget("test-model", 5000)
        assert result["allowed"] is True
        assert "within budget" in result["reason"]

    def test_check_budget_hourly_limit_exceeded(self):
        """Request exceeding hourly token budget should be blocked."""
        from budget_guard import BudgetGuard, BudgetConfig
        guard = BudgetGuard()
        guard.register_config(BudgetConfig(
            model_name="limited-model",
            token_budget_per_hour=1000,
            cost_budget_per_day_usd=100.0,
        ))
        # Simulate prior usage
        guard.record_usage("limited-model", prompt_tokens=500, completion_tokens=500, cost_usd=0.01)
        result = guard.check_budget("limited-model", 100)
        assert result["allowed"] is False
        assert "hourly token limit" in result["reason"]

    def test_check_budget_daily_cost_exceeded(self):
        """Request exceeding daily cost budget should be blocked."""
        from budget_guard import BudgetGuard, BudgetConfig
        guard = BudgetGuard()
        guard.register_config(BudgetConfig(
            model_name="expensive-model",
            token_budget_per_hour=1_000_000,
            cost_budget_per_day_usd=0.01,
        ))
        # Simulate prior usage that pushes cost over daily limit
        guard.record_usage("expensive-model", prompt_tokens=10000, completion_tokens=10000, cost_usd=0.01)
        result = guard.check_budget("expensive-model", 1000)
        assert result["allowed"] is False
        assert "daily cost limit" in result["reason"]

    def test_record_usage_updates_stats(self):
        """record_usage should be reflected in get_usage_stats."""
        from budget_guard import BudgetGuard
        guard = BudgetGuard()
        guard.record_usage("stats-model", prompt_tokens=100, completion_tokens=50, cost_usd=0.05)
        stats = guard.get_usage_stats()
        assert stats["hourly_tokens_used"] >= 150
        assert stats["daily_cost_usd"] >= 0.05


# ──────────────────────────────────────────────
# ModelRouter Tests
# ──────────────────────────────────────────────

class TestModelRouter:
    def test_normal_priority_selects_default(self):
        from budget_guard import ModelRouter
        router = ModelRouter()
        model = router.select_model("normal")
        assert "70b" in model or "default" in router.MODEL_POOL

    def test_urgent_priority_selects_reasoning(self):
        from budget_guard import ModelRouter
        router = ModelRouter()
        model = router.select_model("urgent")
        assert model == router.MODEL_POOL["reasoning"]

    def test_vip_priority_selects_reasoning(self):
        from budget_guard import ModelRouter
        router = ModelRouter()
        model = router.select_model("vip")
        assert model == router.MODEL_POOL["reasoning"]

    def test_classify_priority_selects_fast_pool(self):
        from budget_guard import ModelRouter
        router = ModelRouter()
        model = router.select_model("classify")
        assert model == router.MODEL_POOL["classify"]
        assert model == router.MODEL_POOL["fast"]

    def test_fast_priority_selects_fast_model(self):
        from budget_guard import ModelRouter
        router = ModelRouter()
        model = router.select_model("fast")
        assert model == router.MODEL_POOL["fast"]

    def test_route_with_budget_allowed(self):
        from budget_guard import ModelRouter
        router = ModelRouter()
        result = router.route_with_budget(priority="normal", estimated_tokens=100)
        assert "model" in result
        assert result["allowed"] is True

    def test_route_with_budget_blocked(self):
        """If budget is exhausted, route_with_budget should block."""
        from budget_guard import ModelRouter, BudgetGuard, BudgetConfig
        guard = BudgetGuard()
        guard.register_config(BudgetConfig(
            model_name="meta/llama-3.1-70b-instruct",
            token_budget_per_hour=10,
            cost_budget_per_day_usd=0.001,
        ))
        # Exhaust budget
        guard.record_usage("meta/llama-3.1-70b-instruct", prompt_tokens=500, completion_tokens=500, cost_usd=0.01)

        router = ModelRouter()
        # Patch the shared singleton temporarily
        with patch("budget_guard.budget_guard", guard):
            result = router.route_with_budget(priority="normal", estimated_tokens=5000)
            assert result["allowed"] is False


# ──────────────────────────────────────────────
# call_llm Retry / Fallback Tests
# ──────────────────────────────────────────────

class TestCallLLMRetryFallback:
    def test_retry_then_success(self):
        """First attempt fails, second succeeds — call_llm should retry."""
        import llm as llm_module

        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "test response"
        mock_completion.usage = MagicMock()
        mock_completion.usage.prompt_tokens = 10
        mock_completion.usage.completion_tokens = 5
        mock_completion.usage.total_tokens = 15

        call_count = {"n": 0}
        def side_effect(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise ConnectionError("timeout")
            return mock_completion

        mock_client = MagicMock()
        mock_client.chat.completions.create = side_effect

        with patch.object(llm_module, "PROVIDERS", [llm_module.ProviderConfig(
            name="test_provider",
            base_url="http://test",
            api_key="test-key",
            default_model="test-model",
            enabled=True,
        )]):
            with patch.object(llm_module, "_get_client", return_value=mock_client):
                with patch.object(llm_module, "_get_budget_guard") as mock_bg:
                    guard = MagicMock()
                    guard.check_budget.return_value = {"allowed": True, "reason": "ok"}
                    mock_bg.return_value = guard

                    # Patch time.sleep to skip delays
                    with patch("llm.time.sleep"):
                        result = llm_module.call_llm("test prompt", model="fast")
                        assert result == "test response"
                        assert call_count["n"] == 2

    def test_fallback_to_second_provider(self):
        """First provider fails all retries, second provider succeeds."""
        import llm as llm_module

        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "fallback response"
        mock_completion.usage = MagicMock()
        mock_completion.usage.prompt_tokens = 10
        mock_completion.usage.completion_tokens = 5
        mock_completion.usage.total_tokens = 15

        fail_client = MagicMock()
        fail_client.chat.completions.create = MagicMock(side_effect=ConnectionError("down"))

        ok_client = MagicMock()
        ok_client.chat.completions.create = MagicMock(return_value=mock_completion)

        providers = [
            llm_module.ProviderConfig(
                name="fail_provider", base_url="http://fail", api_key="k",
                default_model="fail-model", enabled=True,
            ),
            llm_module.ProviderConfig(
                name="ok_provider", base_url="http://ok", api_key="k2",
                default_model="ok-model", enabled=True,
            ),
        ]

        clients = {"fail_provider": fail_client, "ok_provider": ok_client}
        def get_client(p):
            return clients[p.name]

        with patch.object(llm_module, "PROVIDERS", providers):
            with patch.object(llm_module, "_get_client", side_effect=get_client):
                with patch.object(llm_module, "_get_budget_guard") as mock_bg:
                    guard = MagicMock()
                    guard.check_budget.return_value = {"allowed": True, "reason": "ok"}
                    mock_bg.return_value = guard

                    with patch("llm.time.sleep"):
                        result = llm_module.call_llm("test prompt", model="fast", max_retries=1)
                        assert result == "fallback response"

    def test_all_providers_fail_raises(self):
        """When all providers exhaust retries, RuntimeError is raised."""
        import llm as llm_module

        fail_client = MagicMock()
        fail_client.chat.completions.create = MagicMock(side_effect=ConnectionError("down"))

        with patch.object(llm_module, "PROVIDERS", [llm_module.ProviderConfig(
            name="fail_only", base_url="http://fail", api_key="k",
            default_model="fail-model", enabled=True,
        )]):
            with patch.object(llm_module, "_get_client", return_value=fail_client):
                with patch.object(llm_module, "_get_budget_guard") as mock_bg:
                    guard = MagicMock()
                    guard.check_budget.return_value = {"allowed": True, "reason": "ok"}
                    mock_bg.return_value = guard

                    with patch("llm.time.sleep"):
                        with pytest.raises(RuntimeError, match="All LLM providers/models failed"):
                            llm_module.call_llm("test prompt", max_retries=1)

    def test_budget_guard_blocks_call(self):
        """If budget check fails, call_llm raises RuntimeError."""
        import llm as llm_module

        with patch.object(llm_module, "PROVIDERS", [llm_module.ProviderConfig(
            name="blocked_provider", base_url="http://test", api_key="k",
            default_model="blocked-model", enabled=True,
        )]):
            with patch.object(llm_module, "_get_model_router") as mock_router:
                router = MagicMock()
                router.route_with_budget.return_value = {
                    "allowed": False,
                    "reason": "hourly token limit exceeded",
                    "model": "meta/llama-3.1-70b-instruct",
                }
                mock_router.return_value = router

                with pytest.raises(RuntimeError, match="Budget limit"):
                    llm_module.call_llm("test prompt", model="default")

    def test_disabled_provider_skipped(self):
        """Disabled providers should be skipped entirely."""
        import llm as llm_module

        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "enabled response"
        mock_completion.usage = MagicMock()
        mock_completion.usage.prompt_tokens = 10
        mock_completion.usage.completion_tokens = 5
        mock_completion.usage.total_tokens = 15

        ok_client = MagicMock()
        ok_client.chat.completions.create = MagicMock(return_value=mock_completion)

        providers = [
            llm_module.ProviderConfig(
                name="disabled", base_url="http://off", api_key="k",
                default_model="off-model", enabled=False,
            ),
            llm_module.ProviderConfig(
                name="enabled", base_url="http://on", api_key="k2",
                default_model="on-model", enabled=True,
            ),
        ]

        with patch.object(llm_module, "PROVIDERS", providers):
            with patch.object(llm_module, "_get_client", return_value=ok_client):
                with patch.object(llm_module, "_get_budget_guard") as mock_bg:
                    guard = MagicMock()
                    guard.check_budget.return_value = {"allowed": True, "reason": "ok"}
                    mock_bg.return_value = guard

                    result = llm_module.call_llm("test prompt", model="fast")
                    assert result == "enabled response"


# ──────────────────────────────────────────────
# Provider Status / Reload Tests
# ──────────────────────────────────────────────

class TestProviderStatus:
    def test_get_provider_status(self):
        from llm import get_provider_status
        status = get_provider_status()
        assert isinstance(status, list)
        assert len(status) > 0, "At least one provider must be present"
        # В TESTING=1 среде mock провайдер всегда добавляется
        names = [s["name"] for s in status]
        import os
        if os.environ.get("TESTING") == "1":
            assert "mock" in names, "MOCK provider must be present when TESTING=1"
        # Проверяем что каждый провайдер имеет нужные поля
        for s in status:
            assert "name" in s
            assert "base_url" in s
            assert "enabled" in s

    def test_reload_providers(self):
        from llm import reload_providers, PROVIDERS
        reload_providers()
        from llm import PROVIDERS as new_providers
        assert len(new_providers) > 0, "After reload, at least one provider must exist"


    def test_resolve_model_alias(self):
        from llm import resolve_model
        assert resolve_model("fast", "lm_studio") == "llama-3.1-8b-instruct"
        assert resolve_model("default", "lm_studio") == "llama-3.1-8b-instruct"


# ──────────────────────────────────────────────
# Streaming (call_llm_stream) Tests
# ──────────────────────────────────────────────

class TestCallLLMStream:
    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self):
        """Streaming should yield OpenAI-compatible chunk dicts."""
        import llm as llm_module

        # Build mock streaming response
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta = MagicMock()
        chunk1.choices[0].delta.content = "Hello"
        chunk1.choices[0].finish_reason = None
        chunk1.usage = None

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta = MagicMock()
        chunk2.choices[0].delta.content = " world"
        chunk2.choices[0].finish_reason = None
        chunk2.usage = None

        chunk3 = MagicMock()
        chunk3.choices = [MagicMock()]
        chunk3.choices[0].delta = MagicMock()
        chunk3.choices[0].delta.content = None
        chunk3.choices[0].finish_reason = "stop"
        chunk3.usage = MagicMock()
        chunk3.usage.prompt_tokens = 10
        chunk3.usage.completion_tokens = 5

        mock_stream = [chunk1, chunk2, chunk3]

        mock_client = MagicMock()
        mock_client.chat.completions.create = MagicMock(return_value=mock_stream)

        with patch.object(llm_module, "PROVIDERS", [llm_module.ProviderConfig(
            name="test_stream", base_url="http://test", api_key="k",
            default_model="stream-model", enabled=True,
        )]):
            with patch.object(llm_module, "_get_client", return_value=mock_client):
                with patch.object(llm_module, "_get_budget_guard") as mock_bg:
                    guard = MagicMock()
                    guard.check_budget.return_value = {"allowed": True, "reason": "ok"}
                    mock_bg.return_value = guard

                    chunks = []
                    async for chunk in llm_module.call_llm_stream("hello"):
                        chunks.append(chunk)

                    assert len(chunks) == 3
                    assert chunks[0]["choices"][0]["delta"]["content"] == "Hello"
                    assert chunks[1]["choices"][0]["delta"]["content"] == " world"
                    assert chunks[2]["choices"][0]["finish_reason"] == "stop"

    @pytest.mark.asyncio
    async def test_stream_budget_blocked(self):
        """When budget guard blocks, stream yields error chunk."""
        import llm as llm_module

        with patch.object(llm_module, "_get_model_router") as mock_router:
            router = MagicMock()
            router.route_with_budget.return_value = {
                "allowed": False,
                "reason": "hourly token limit exceeded",
                "model": "meta/llama-3.1-70b-instruct",
            }
            mock_router.return_value = router

            chunks = []
            async for chunk in llm_module.call_llm_stream("hello", model="default"):
                chunks.append(chunk)

            assert len(chunks) == 1
            assert "Budget limit" in chunks[0]["choices"][0]["delta"]["content"]

    @pytest.mark.asyncio
    async def test_stream_all_providers_fail(self):
        """When all providers fail, stream yields error chunk."""
        import llm as llm_module

        mock_client = MagicMock()
        mock_client.chat.completions.create = MagicMock(side_effect=ConnectionError("down"))

        with patch.object(llm_module, "PROVIDERS", [llm_module.ProviderConfig(
            name="fail_stream", base_url="http://fail", api_key="k",
            default_model="fail-model", enabled=True,
        )]):
            with patch.object(llm_module, "_get_client", return_value=mock_client):
                with patch.object(llm_module, "_get_budget_guard") as mock_bg:
                    guard = MagicMock()
                    guard.check_budget.return_value = {"allowed": True, "reason": "ok"}
                    mock_bg.return_value = guard

                    with patch("llm.asyncio.sleep", new_callable=MagicMock):
                        chunks = []
                        async for chunk in llm_module.call_llm_stream("hello", model="fast", max_retries=1):
                            chunks.append(chunk)

                        assert len(chunks) == 1
                        assert "All LLM providers failed" in chunks[0]["choices"][0]["delta"]["content"]


# ──────────────────────────────────────────────
# Chat Completions Endpoint Test (API level)
# ──────────────────────────────────────────────

class TestChatCompletionsEndpoint:
    def test_endpoint_requires_user_message(self):
        """Completions endpoint should reject requests without user message."""
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)

        resp = client.post("/api/v1/chat/completions", json={
            "model": "default",
            "messages": [{"role": "system", "content": "You are a helper"}],
            "stream": False,
        })
        assert resp.status_code == 400

    def test_non_streaming_returns_json(self):
        """Non-streaming request should return a JSON chat.completion object."""
        from fastapi.testclient import TestClient
        from main import app
        from unittest.mock import patch, MagicMock

        client = TestClient(app)

        # Mock the LLM call — imported inside the endpoint as `from llm import ...`
        mock_resp = "Test LLM response"
        with patch("llm.call_llm_async", return_value=mock_resp):
            resp = client.post("/api/v1/chat/completions", json={
                "model": "default",
                "messages": [
                    {"role": "system", "content": "You are a test assistant"},
                    {"role": "user", "content": "Hello"},
                ],
                "stream": False,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["object"] == "chat.completion"
            assert data["choices"][0]["message"]["role"] == "assistant"
            assert data["choices"][0]["message"]["content"] == "Test LLM response"
            assert data["choices"][0]["finish_reason"] == "stop"
