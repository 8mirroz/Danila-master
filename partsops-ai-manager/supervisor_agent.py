"""
PartsOps AI Manager v3 — Supervisor Agent
Контракт: 04_BACKEND_CONTRACTS/agents/supervisor_agent.py
Оркестрирует мульти-агентный workflow, следит за ошибками и retry.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from base_agent import Agent, AgentContext, register_agent


@dataclass
class AgentResult:
    agent_name: str
    success: bool
    output: Any
    error: Optional[str] = None


@register_agent
class SupervisorAgent(Agent):
    """
    Супервизор: управляет жизненным циклом запроса,
    собирает результаты от подчинённых агентов (intake_classifier, vin_inspector, parts_extractor).
    """

    name = "supervisor"

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def _execute_with_retry(
        self, node_func: Any, state: Dict, node_name: str
    ) -> AgentResult:
        """Выполнить LangGraph-узел с retry."""
        for attempt in range(self.max_retries + 1):
            try:
                result = node_func(state)
                return AgentResult(
                    agent_name=node_name,
                    success=True,
                    output=result,
                )
            except Exception as e:
                if attempt == self.max_retries:
                    return AgentResult(
                        agent_name=node_name,
                        success=False,
                        output=None,
                        error=str(e),
                    )

    def run(self, context: AgentContext) -> Dict[str, Any]:
        # Этот агент — координатор, реальная логика в agents.py LangGraph
        return {
            "supervisor_status": "orchestrating",
            "trace": list(context.get("trace", [])) + ["Supervisor: starting workflow"],
        }


# ──────────────────────────────────────────────
# Operator Copilot Agent (автоматические действия в UI)
# ──────────────────────────────────────────────

@register_agent
class OperatorCopilotAgent(Agent):
    """
    Копилот: автопилот для UI-оператора.
    Генерирует короткие инструкции для оператора о Next Step.
    """

    name = "operator_copilot"

    def run(self, context: AgentContext) -> Dict[str, Any]:
        trace = list(context.get("trace", []))
        last_events = trace[-5:] if len(trace) >= 5 else trace

        instruction = self._generate_instruction(context, last_events)
        return {
            "instruction": instruction,
            "priority": context.get("priority", "normal"),
            "trace": trace + [f"Copilot: {instruction}"],
        }

    def _generate_instruction(
        self, context: AgentContext, events: List[str]
    ) -> str:
        status = context.get("validation_status", "")
        if status == "FAILED":
            return "Request rejected: validation failed. Review spam filter or contact customer."
        if context.get("is_spam"):
            return "Request classified as spam. Archive and notify admin if false positive."
        if len(context.get("extracted_parts", [])) == 0:
            return "No parts extracted. Escalate to manual review."
        if not context.get("matched_suppliers"):
            return "Parts extracted but no suppliers matched. Trigger alternative search."
        return "Matched suppliers ready. Review pricing and approve invoice."


# ──────────────────────────────────────────────
# Catalog Matcher Agent (обёртка над matcher.py)
# ──────────────────────────────────────────────

@register_agent
class CatalogMatcherAgent(Agent):
    """
    Агент сопоставления деталей с каталогом.
    """

    name = "catalog_matcher"

    def run(self, context: AgentContext) -> Dict[str, Any]:
        from matcher import match_part_from_db
        from database import get_session

        parts = context.get("extracted_parts", [])
        session = get_session()

        matches = []
        for part in parts:
            match = match_part_from_db(part["name"], session)
            matches.append({
                "part": part["name"],
                "match": match,
            })

        return {
            "matched_parts": matches,
            "trace": list(context.get("trace", [])) + ["CatalogMatcher: matched parts"],
        }


# ──────────────────────────────────────────────
# Pricing Agent (обёртка над pricing.py)
# ──────────────────────────────────────────────

@register_agent
class PricingAgent(Agent):
    """
    Агент ценообразования.
    """

    name = "pricing"

    def run(self, context: AgentContext) -> Dict[str, Any]:
        from pricing import compute_price, check_margin_guard, PricingContext
        from database import get_session

        matched = context.get("matched_parts", [])
        session = get_session()

        prices = []
        for item in matched:
            best_match = item.get("match")
            if best_match:
                ctx = PricingContext(
                    catalog_id=best_match.get("catalog_id"),
                    cost_price=best_match.get("price", 0),
                    markup_percent=0.12,
                )
                computed = compute_price(ctx)
                margin_ok = check_margin_guard(ctx)
                prices.append({
                    "part": item["part"],
                    "price": computed["final_price"],
                    "margin_ok": margin_ok,
                })

        return {
            "pricing_results": prices,
            "trace": list(context.get("trace", [])) + ["PricingAgent: computed"],
        }
