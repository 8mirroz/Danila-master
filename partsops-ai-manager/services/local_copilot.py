"""Local grounded Copilot fallback when Hermes sidecar is unavailable.

Produces a useful Russian read-only answer from the ContextEnvelope and help
corpus without calling external Hermes. Optionally enriches via project LLM
if a provider is configured (best-effort, never blocks on LLM failure).
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from services.copilot_context import ContextEnvelope, validate_and_filter_sources
from services.help_service import get_help_source_by_id

logger = logging.getLogger(__name__)


def _status_label(status: str) -> str:
    labels = {
        "NEW": "Новый",
        "NORMALIZING": "Нормализация",
        "PARSING": "Разбор",
        "VIN_CHECK": "Проверка VIN",
        "PART_EXTRACTION": "Извлечение позиций",
        "MATCHING": "Подбор",
        "SUPPLIER_SEARCH": "Поиск поставщиков",
        "OFFER_RANKING": "Ранжирование офферов",
        "PRICING_REVIEW": "Проверка цен",
        "READY_FOR_APPROVAL": "Готово к согласованию",
        "FINANCE_REVIEW": "Финансовый контроль",
        "APPROVED": "Одобрено",
        "ERP_SYNCING": "Синхронизация ERP",
        "ERP_SYNCED": "Синхронизировано с ERP",
        "ERP_SYNC_FAILED": "Ошибка ERP",
        "SENT_TO_CLIENT": "Отправлено клиенту",
        "INVOICE_DRAFTED": "Черновик счёта",
        "NEEDS_CLARIFICATION": "Нужно уточнение",
        "NEEDS_MANUAL_PARSE": "Ручной разбор",
        "BLOCKED": "Заблокирован",
        "CANCELLED": "Отменён",
        "FAILED": "Ошибка",
        "EXPIRED": "Истёк",
    }
    return labels.get((status or "").upper(), status or "—")


def build_local_reply(
    *,
    envelope: ContextEnvelope,
    user_message: str,
    prefer_llm: bool | None = None,
) -> Tuple[str, List[Dict[str, str]]]:
    """Return (markdown_answer, valid_source_chips)."""
    if prefer_llm is None:
        raw = __import__("os").environ.get("COPILOT_LOCAL_LLM", "1").strip().lower()
        prefer_llm = raw not in {"0", "false", "no", "off"}
    help_sources = envelope.available_help_sources or []
    query = (user_message or "").strip()

    order = envelope.selected_request
    parts: List[str] = []

    if order:
        status = str(order.get("status") or "—")
        req_id = str(order.get("request_id") or order.get("id") or "—")
        customer = str(order.get("customer_name") or "клиент")
        vehicle = " ".join(
            str(x).strip()
            for x in (order.get("vehicle_make"), order.get("vehicle_model"), order.get("vehicle_year"))
            if x
        ).strip()
        parts_count = 0
        try:
            import json as _json
            raw = order.get("parts_json")
            parsed = _json.loads(raw) if isinstance(raw, str) and raw else raw
            if isinstance(parsed, list):
                parts_count = len(parsed)
        except Exception:
            pass
        parts.append(f"### Заказ `{req_id}`")
        meta = [
            f"**Статус:** {_status_label(status)} (`{status}`)",
            f"**Клиент:** {customer}",
        ]
        if vehicle:
            meta.append(f"**Авто:** {vehicle}")
        if parts_count:
            meta.append(f"**Позиций:** {parts_count}")
        if order.get("priority"):
            meta.append(f"**Приоритет:** {order.get('priority')}")
        parts.append("\n".join(meta))
        if envelope.blocking_reasons:
            parts.append("**Блокировки:**")
            for reason in envelope.blocking_reasons:
                parts.append(f"- {reason}")
        else:
            parts.append("Блокировок Evidence Gates не зафиксировано.")

        if envelope.allowed_next_statuses:
            next_labels = ", ".join(f"`{s}`" for s in envelope.allowed_next_statuses[:8])
            parts.append(f"**Допустимые следующие шаги:** {next_labels}")

        if envelope.evidence_summary:
            gates = envelope.evidence_summary
            gate_lines = []
            for key, ok in gates.items():
                mark = "✓" if ok else "✗"
                gate_lines.append(f"- {mark} `{key}`")
            parts.append("**Evidence Gates:**\n" + "\n".join(gate_lines))
    else:
        parts.append(f"### Экран: {envelope.screen_title}")
        parts.append(
            "Заказ сейчас не выбран. Для разбора конкретной заявки укажите номер "
            "(например `REQ-…`) или выберите карточку в очереди."
        )
        if help_sources:
            parts.append("**Полезные статьи по этому экрану:**")
            for src in help_sources[:3]:
                title = src.get("title") or src.get("source_id")
                parts.append(f"- {title}")

    # Intent snippets from query
    q = query.lower()
    if any(w in q for w in ("что делать", "дальше", "следующ", "как продолж", "next")):
        if order and envelope.allowed_next_statuses:
            parts.append(
                "\n**Рекомендация:** проверьте Evidence Gates и выполните один из "
                f"допустимых переходов: {', '.join(envelope.allowed_next_statuses[:5])}."
            )
        else:
            parts.append(
                "\n**Рекомендация:** выберите заказ в канбане или очереди «Входящие», "
                "затем спросите «что делать дальше»."
            )
    if any(w in q for w in ("блок", "stuck", "застрял", "почему")):
        if envelope.blocking_reasons:
            parts.append("\nПричины блокировки перечислены выше — снимите гейты в карточке заказа.")
        else:
            parts.append("\nЯвных блокировок по текущему контексту нет. Проверьте SLA поставщиков и устаревшие фиды.")

    if help_sources:
        # Append first help excerpt for grounding
        first = help_sources[0]
        body = first.get("content") or ""
        if body:
            excerpt = body[:320].rstrip()
            if len(body) > 320:
                excerpt += "…"
            parts.append(f"\n> **Справка:** {first.get('title', '')}\n> {excerpt}")

    parts.append(
        "\n_Режим: локальный grounded fallback (Hermes sidecar недоступен). "
        "Ответ только read-only, без изменения статусов._"
    )

    answer = "\n\n".join(parts)

    # Optional LLM polish — best effort
    if prefer_llm:
        polished = _try_llm_polish(envelope=envelope, user_message=query, draft=answer)
        if polished:
            answer = polished

    valid_sources = validate_and_filter_sources(help_sources, answer)
    # Keep only sources that exist in corpus
    valid_sources = [
        src for src in valid_sources
        if get_help_source_by_id(src.get("source_id", "")) is not None
    ]
    if not valid_sources and help_sources:
        # Always surface top help hits even if citation filter was strict
        valid_sources = [
            {"source_id": s["source_id"], "title": s.get("title", s["source_id"])}
            for s in help_sources[:2]
            if s.get("source_id")
        ]

    return answer, valid_sources


def _try_llm_polish(*, envelope: ContextEnvelope, user_message: str, draft: str) -> Optional[str]:
    try:
        from llm import call_llm  # local import — avoids circular load at import time
    except Exception:
        return None

    system = (
        "Ты read-only операционный помощник PartsOps Admin Cockpit. "
        "Отвечай только по-русски, кратко, в Markdown. "
        "Не выдумывай факты вне ContextEnvelope. "
        "Не предлагай менять статусы напрямую — только explain + allowed next steps. "
        "Не выводи сырой JSON."
    )
    try:
        from services.copilot_context import compact_envelope_for_hermes

        facts = compact_envelope_for_hermes(envelope)
    except Exception:
        facts = {
            "screen_id": envelope.screen_id,
            "screen_title": envelope.screen_title,
            "selected_request": (envelope.selected_request or {}).get("request_id")
            if envelope.selected_request
            else None,
            "allowed_next_statuses": list(envelope.allowed_next_statuses or [])[:8],
            "blocking_reasons": list(envelope.blocking_reasons or [])[:5],
        }
    import json as _json

    prompt = (
        f"Вопрос оператора:\n{user_message}\n\n"
        f"ContextEnvelope (факты, compact):\n{_json.dumps(facts, ensure_ascii=False)}\n\n"
        f"Черновик ответа (используй как основу, улучши формулировки):\n{draft}\n"
    )
    try:
        text = call_llm(
            prompt=prompt,
            system_prompt=system,
            model="fast",
            temperature=0.2,
            priority="normal",
            max_retries=1,
        )
        text = (text or "").strip()
        if len(text) < 40:
            return None
        # Soft guard: keep local footer honesty
        if "локальный" not in text.lower() and "fallback" not in text.lower():
            text += (
                "\n\n_Режим: локальный grounded fallback (Hermes sidecar недоступен)._"
            )
        return text
    except Exception as exc:
        logger.debug("local copilot LLM polish skipped: %s", exc)
        return None


def chunk_text(text: str, size: int = 48) -> List[str]:
    """Split answer into small chunks for SSE-like streaming UX."""
    if not text:
        return []
    # Prefer splitting on whitespace boundaries
    chunks: List[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= size:
            chunks.append(remaining)
            break
        cut = remaining.rfind(" ", 0, size)
        if cut < size // 3:
            cut = size
        chunks.append(remaining[:cut])
        remaining = remaining[cut:]
    return chunks
