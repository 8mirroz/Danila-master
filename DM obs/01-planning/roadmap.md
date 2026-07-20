# 🗺️ Roadmap

## 🎯 Milestones

### 2026-07-20 — P0 (закрыт, commit `261b0a7`)
- Цель: вынести legacy intake-graph из `partsops-ai-manager/agents.py` (612 строк) в `app/agents/legacy_intake_pipeline.py`, оставить `agents.py` re-export шимом.
- Статус: ✅ merged in `audit/scrape-fixes`. Тесты test_agents.py::TestE2EAgentWorkflow и test_automation_pipeline.py::test_full_pipeline_graph_initializes проходят локально.
- Что осталось от старого P0 (без блокировки P0): переключить активный intake-путь `/api/requests` с `process_intake_request` (legacy path) на `app.agents.IntakeAgent`. Не входит в P0 — отдельный шаг.

### 2026-07-21 — Открыто после анализа
- **P2 кандидат**: транзакционная гигиена (закрытие SQLAlchemy session до LLM/HTTP). После 7 промежуточных фикс-коммитов (LLM circuit-breaker, rate-limiter, parser-guards, httpx-limits, async-nonblocking LLM) контекст изменился — нужна ревизия перед стартом.
- **P3 кандидат**: освежить `settings.PHASE_LABEL` или убрать его с `/health` (legacy `Phase 1 — Runtime Foundation` уже не отражает стадию).
- **P4 кандидат**: явно зафиксировать границу legacy/new в `app/agents/*` (новый контур) и `agents.py` (shim). Сейчас живут параллельно.
- **P5 кандидат**: разобраться с XLSX-stretch (>10 МБ) через openpyxl streaming-mode — не срочно.

### Backlog (из `01-planning/backlog.md`)
- Перенос legacy intake API на новую `app/agents/IntakeAgent` (для `POST /api/requests` и import-from-artifact).
- Подтвердить, закрывают ли 7 промежуточных коммитов риски из аудита (R7/транзакции, RBAC-инъекции, PII-middleware). Если да — переоценить P2/P3.

## 🚧 Не входит (deferred)
- Agent OS devpack vs admin_cockpit — вопрос владения и объединения ставится после стабилизации основного контура.
