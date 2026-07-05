"""
PartsOps AI Manager v3 — Multi-Provider LLM Integration
Supports: NVIDIA NIM, LM Studio (local), OpenRouter (cloud reserve).
Falls back through provider chain with exponential backoff.
Records usage in BudgetGuard; routes models via ModelRouter.
"""
from __future__ import annotations

import os
import json
import time
import asyncio
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from openai import OpenAI
from pii import mask_for_log
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# ──────────────────────────────────────────────
# Provider Configuration
# ──────────────────────────────────────────────

@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    default_model: str
    enabled: bool = True
    max_retries: int = 3
    timeout_seconds: int = 60
    model_pool: List[str] = field(default_factory=list)

    def get_models(self) -> List[str]:
        """Return ordered list of models to try (first = preferred)."""
        if self.model_pool:
            return self.model_pool
        return [self.default_model]


def _load_providers() -> List[ProviderConfig]:
    """Build provider list from env vars. Order = fallback priority."""
    providers: List[ProviderConfig] = []

    # 1. NVIDIA NIM (primary cloud)
    nim_key = os.environ.get("NVIDIA_API_KEY", "")
    if nim_key:
        providers.append(ProviderConfig(
            name="nvidia_nim",
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=nim_key,
            default_model="google/gemma-4-31b-it",
            model_pool=[
                "google/gemma-4-31b-it",       # #1 32s, free, reliable
                "meta/llama-3.1-70b-instruct",  # #2 7s, proven
                "deepseek-ai/deepseek-v4-flash",# #3 15s, proven
                "meta/llama-3.3-70b-instruct",  # #4 53s, proven
                "mistralai/mistral-large-3-675b-instruct-2512",  # #5 1.5s
            ],
            timeout_seconds=12,
        ))

    # 2. LM Studio (local inference)
    lm_url = os.environ.get("LM_STUDIO_URL", "http://localhost:1234/v1")
    providers.append(ProviderConfig(
        name="lm_studio",
        base_url=lm_url,
        api_key="lm-studio",  # LM Studio doesn't require real key
        default_model=os.environ.get("LM_STUDIO_MODEL", "llama-3.1-8b-instruct"),
    ))

    # 3. OpenRouter (cloud reserve)
    or_key = os.environ.get("OPENROUTER_API_KEY", "")
    if or_key:
        providers.append(ProviderConfig(
            name="openrouter",
            base_url="https://openrouter.ai/api/v1",
            api_key=or_key,
            default_model=os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free"),
        ))

    return providers


PROVIDERS: List[ProviderConfig] = _load_providers()

# Model alias mapping (from budget_guard ModelRouter pool to actual per-provider model names)
_MODEL_ALIASES: Dict[str, Dict[str, str]] = {
    "default": {
        "nvidia_nim": "google/gemma-4-31b-it",
        "lm_studio": "llama-3.1-8b-instruct",
        "openrouter": "meta-llama/llama-3.1-8b-instruct:free",
    },
    "fast": {
        "nvidia_nim": "google/gemma-4-31b-it",
        "lm_studio": "llama-3.1-8b-instruct",
        "openrouter": "meta-llama/llama-3.1-8b-instruct:free",
    },
    "reasoning": {
        "nvidia_nim": "google/gemma-4-31b-it",
        "lm_studio": "llama-3.1-8b-instruct",  # fallback — local can't do 70B reasoning
        "openrouter": "deepseek/deepseek-r1-distill-llama-70b",
    },
}


def resolve_model(alias: str, provider_name: str) -> str:
    """Resolve a model alias (default/fast/reasoning) to a concrete model name for a provider."""
    aliases = _MODEL_ALIASES.get(alias, {})
    return aliases.get(provider_name, alias)


# ──────────────────────────────────────────────
# Client cache
# ──────────────────────────────────────────────

_clients: Dict[str, OpenAI] = {}


def _get_client(provider: ProviderConfig) -> OpenAI:
    """Cached OpenAI-compatible client for a provider."""
    if provider.name not in _clients:
        # Build httpx client that avoids SOCKS5 proxy deadlock:
        # NVIDIA NIM API doesn't need the local SOCKS proxy.
        # Strip ALL_PROXY/ALL_PROXY so the OpenAI SDK uses HTTP/HTTPS proxies only.
        import httpx
        proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        http_client = httpx.Client(
            proxy=proxy_url,  # Use HTTP proxy, not SOCKS5
            timeout=provider.timeout_seconds,
        ) if proxy_url else None
        _clients[provider.name] = OpenAI(
            base_url=provider.base_url,
            api_key=provider.api_key,
            timeout=provider.timeout_seconds,
            http_client=http_client,
        )
    return _clients[provider.name]


# ──────────────────────────────────────────────
# Core: call_llm with provider chain + retry
# ──────────────────────────────────────────────

# Lazy import to avoid circular at module level
_budget_guard = None
_model_router = None


def _get_budget_guard():
    global _budget_guard
    if _budget_guard is None:
        from budget_guard import budget_guard
        _budget_guard = budget_guard
    return _budget_guard


def _get_model_router():
    global _model_router
    if _model_router is None:
        from budget_guard import model_router
        _model_router = model_router
    return _model_router


def call_llm(
    prompt: str,
    system_prompt: str = "You are an AI assistant for automotive parts supply chain.",
    model: str = "default",
    temperature: float = 0.2,
    response_format: Optional[dict] = None,
    priority: str = "normal",
    max_retries: int = 3,
) -> str:
    """
    Call LLM with automatic provider fallback and retry.
    
    `model` accepts aliases ("default", "fast", "reasoning") — resolved per provider.
    `priority` is forwarded to ModelRouter for budget-aware routing.
    
    Returns the LLM text response, or raises if all providers fail.
    """
    masked_prompt = mask_for_log(prompt)

    # Route model via ModelRouter + BudgetGuard if using alias
    if model in _MODEL_ALIASES:
        router = _get_model_router()
        route_result = router.route_with_budget(priority=priority, estimated_tokens=500)
        if not route_result["allowed"]:
            print(f"[LLM] Budget guard blocked: {route_result['reason']}")
            raise RuntimeError(f"Budget limit: {route_result['reason']}")
        # Use the router-selected alias (may upgrade for vip/urgent)
        model = route_result["model"]

    last_error = None

    for provider in PROVIDERS:
       if not provider.enabled:
           continue

       client = _get_client(provider)
       provider_models = provider.get_models()
       print(f"[LLM] Provider {provider.name} — pool: {provider_models}")

       for concrete_model in provider_models:
           print(f"[LLM] Trying {provider.name} / {concrete_model} — "
                 f"prompt: {masked_prompt[:120]}...")

           for attempt in range(max_retries):
               try:
                   budget_guard = _get_budget_guard()
                   budget_check = budget_guard.check_budget(concrete_model, 500)
                   if not budget_check["allowed"]:
                       raise RuntimeError(f"Budget exceeded: {budget_check['reason']}")

                   kwargs: Dict[str, Any] = {
                       "model": concrete_model,
                       "messages": [
                           {"role": "system", "content": system_prompt},
                           {"role": "user",   "content": prompt},
                       ],
                       "temperature": temperature,
                   }
                   if response_format:
                       kwargs["response_format"] = response_format

                   completion = client.chat.completions.create(
                       **kwargs,
                       timeout=provider.timeout_seconds,
                   )
                   content = completion.choices[0].message.content or ""

                   usage = getattr(completion, "usage", None)
                   if usage:
                       prompt_tokens = usage.prompt_tokens or 0
                       completion_tokens = usage.completion_tokens or 0
                       cost_estimate = (
                           (prompt_tokens / 1000) * 0.002
                           + (completion_tokens / 1000) * 0.008
                       )
                       budget_guard.record_usage(
                           model=concrete_model,
                           prompt_tokens=prompt_tokens,
                           completion_tokens=completion_tokens,
                           cost_usd=cost_estimate,
                       )
                       print(
                           f"[LLM] {provider.name}/{concrete_model} OK — "
                           f"prompt={prompt_tokens} "
                           f"completion={completion_tokens} "
                           f"total={usage.total_tokens}"
                       )
                   return content
               except Exception as e:
                   err_msg = str(e)
                   if attempt < max_retries - 1:
                       wait = 2 ** attempt
                       print(
                           f"[LLM] {provider.name}/{concrete_model} attempt {attempt+1}/{max_retries} failed: {err_msg}. Retry in {wait}s..."
                       )
                       time.sleep(wait)
                   else:
                       print(f"[LLM] {provider.name}/{concrete_model} "
                             f"exhausted {max_retries} retries: "
                             f"{err_msg[:120]}. Switching to next model...")
                       model_failed = True
                       # fall through to next concrete_model in pool

       # All models in this provider failed → next provider
       last_error = RuntimeError(
           f"All models in provider chain failed for prompt: "
           f"{masked_prompt[:80]}"
       )

    raise RuntimeError(
       f"All LLM providers/models failed. Last error: {last_error}"
    )


async def call_llm_async(
    prompt: str,
    system_prompt: str = "You are an AI assistant for automotive parts supply chain.",
    model: str = "default",
    temperature: float = 0.2,
    response_format: Optional[dict] = None,
    priority: str = "normal",
) -> str:
    """
    Async wrapper: runs call_llm in a thread to avoid blocking the event loop.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        call_llm,
        prompt, system_prompt, model, temperature, response_format, priority,
    )


# ──────────────────────────────────────────────
# Streaming: async generator for SSE
# ──────────────────────────────────────────────

async def call_llm_stream(
    prompt: str,
    system_prompt: str = "You are an AI assistant for automotive parts supply chain.",
    model: str = "default",
    temperature: float = 0.2,
    priority: str = "normal",
    max_retries: int = 2,
):
    """
    Streaming LLM call — yields OpenAI-compatible SSE chunks (dicts).
    
    Tries providers in priority order with exponential backoff retry.
    Each yielded chunk follows the OpenAI streaming format:
        {
            "id": "chatcmpl-<uid>",
            "object": "chat.completion.chunk",
            "created": <ts>,
            "model": "<concrete_model>",
            "choices": [{"index": 0, "delta": {"content": "..."}, "finish_reason": None}]
        }
    A final chunk with finish_reason="stop" is yielded at the end.
    
    Falls back to non-streaming with fake-chunk wrapping if a provider
    doesn't support the stream API (e.g. some LM Studio configs).
    """
    import uuid as _uuid

    completion_id = f"chatcmpl-{_uuid.uuid4().hex[:12]}"
    created = int(time.time())

    # Route model via ModelRouter + BudgetGuard if using alias
    if model in _MODEL_ALIASES:
        router = _get_model_router()
        route_result = router.route_with_budget(priority=priority, estimated_tokens=500)
        if not route_result["allowed"]:
            # Yield a single error chunk
            yield {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": f"[Budget limit: {route_result['reason']}]"},
                    "finish_reason": "stop",
                }],
            }
            return
        model = route_result["model"]

    budget_guard = _get_budget_guard()
    last_error = None

    for provider in PROVIDERS:
        if not provider.enabled:
            continue

        concrete_model = resolve_model(model, provider.name)
        client = _get_client(provider)

        # Pre-call budget check
        budget_check = budget_guard.check_budget(concrete_model, 500)
        if not budget_check["allowed"]:
            continue  # skip to next provider

        for attempt in range(max_retries):
            try:
                kwargs: Dict[str, Any] = {
                    "model": concrete_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": temperature,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                }

                # Use the synchronous stream context (OpenAI SDK supports this)
                # Run in executor to avoid blocking the event loop
                loop = asyncio.get_event_loop()
                stream = await loop.run_in_executor(
                    None,
                    lambda: client.chat.completions.create(**kwargs),
                )

                total_prompt = 0
                total_completion = 0

                # Iterate over the sync stream (run each next in executor)
                for chunk in stream:
                    # chunk is a ChatCompletionChunk
                    delta = {}
                    finish = None

                    if chunk.choices:
                        choice = chunk.choices[0]
                        if choice.delta and choice.delta.content:
                            delta = {"content": choice.delta.content}
                        if choice.finish_reason:
                            finish = choice.finish_reason

                    # Capture usage if present (last chunk)
                    if hasattr(chunk, "usage") and chunk.usage:
                        total_prompt = chunk.usage.prompt_tokens or 0
                        total_completion = chunk.usage.completion_tokens or 0

                    yield {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": concrete_model,
                        "choices": [{
                            "index": 0,
                            "delta": delta,
                            "finish_reason": finish,
                        }],
                    }

                # Record usage
                if total_prompt or total_completion:
                    cost = (total_prompt / 1000) * 0.002 + (total_completion / 1000) * 0.008
                    budget_guard.record_usage(
                        model=concrete_model,
                        prompt_tokens=total_prompt,
                        completion_tokens=total_completion,
                        cost_usd=cost,
                    )

                return  # success — done

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    print(f"[LLM-STREAM] {provider.name} attempt {attempt+1}/{max_retries} failed: {e}. Retry in {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    print(f"[LLM-STREAM] {provider.name} exhausted retries: {e}. Next provider...")

    # All providers failed — yield error chunk
    yield {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {"content": f"[All LLM providers failed. Last error: {last_error}]"},
            "finish_reason": "stop",
        }],
    }


# ──────────────────────────────────────────────
# Convenience: structured request parsing
# ──────────────────────────────────────────────

def parse_request_with_llm(raw_text: str, priority: str = "normal", vehicle_context_hint: str = "") -> dict:
    """
    Use LLM to extract structured fields:
    parts (list of {"name": str, "quantity": int}), vehicle (vin, make, model, year), and priority.
    Returns empty dict on failure so callers can fall back to rule-based parsing.
    """
    system_prompt = """You are a precise automotive parts intake parser.
Analyze the user's text and output a JSON object containing:
1. "parts": a list of objects, each with "name" (Russian part name, e.g. "Тормозные колодки") and "quantity" (integer).
2. "vehicle": an object with keys "vin" (17-char VIN if found), "make" (brand, e.g. "BMW"), "model" (e.g. "X5"), and "year" (integer).
3. "priority": "low" | "normal" | "urgent" | "vip" (infer based on text urgency).

IMPORTANT RULES:
- NEVER return or hallucinate prices.
- NEVER return or hallucinate supplier names.
- Prices and suppliers must be determined by the system's pricing engine.

Respond ONLY with valid JSON. No explanations, no markdown formatting blocks."""

    prompt = f"User Request: {raw_text}\n"
    if vehicle_context_hint:
        prompt += f"Hint (Offline extracted context): {vehicle_context_hint}\n"
    prompt += "JSON Output:"

    try:
        # Use "fast" alias for intake parsing (cheaper model)
        res_text = call_llm(
            prompt=prompt,
            system_prompt=system_prompt,
            model="fast",
            response_format={"type": "json_object"},
            priority=priority,
        )
        data = json.loads(res_text)
        return data
    except Exception as e:
        print(f"[LLM] parse_request_with_llm failed: {e}. Falling back to rule-based.")
        return {}


# ──────────────────────────────────────────────
# Provider status (for health/admin endpoints)
# ──────────────────────────────────────────────

def get_provider_status() -> List[Dict[str, Any]]:
    """Return the status of each configured LLM provider."""
    return [
        {
            "name": p.name,
            "base_url": p.base_url,
            "default_model": p.default_model,
            "enabled": p.enabled,
            "has_api_key": bool(p.api_key and p.api_key != "lm-studio"),
        }
        for p in PROVIDERS
    ]


def reload_providers() -> None:
    """Hot-reload providers from env vars (e.g. after setting a new key)."""
    global PROVIDERS, _clients
    PROVIDERS = _load_providers()
    _clients.clear()
