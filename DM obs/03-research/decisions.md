# ⚖️ Decisions

## ✅ Validated Decisions
- TBD

## ⚖️ Decision | 2026-06-26T13:23:27+03:00

Инициализация интеграции с Obsidian

## ⚖️ Decision | 2026-06-29T03:52:12+03:00

Implemented Phase 5: RBAC, Multi-tenancy, and Learning Loop

## ⚖️ Decision | 2026-06-29T05:54:32+03:00

Интеграция математических алгоритмов из UI в backend (Fuzzy Matching, Set Cover, SAW, Holt-Winters)

## ⚖️ Decision | 2026-06-29T15:07:17+03:00

Упрощение воркфлоу до 3 шагов, локализация интерфейса и интеграция кнопок одобрения в калькулятор

## ⚖️ Decision | 2026-06-29T22:50:40+03:00

Редизайн WorkspaceHeader и перевод статистики очереди в строчный формат

## ⚖️ Decision | 2026-06-29T22:54:07+03:00

Интеграция Drag & Drop для документов PDF, Excel и Word в панель быстрого ввода

## ⚖️ Decision | 2026-06-29T23:30:01+03:00

Исправление переполнения контейнера статистики очереди с переходом на мини-бейджи

## ⚖️ Decision | 2026-06-30T05:47:21+03:00

Редизайн экранов и добавление модулей аналитики и Монитора Агента

## ⚖️ Decision | 2026-06-30T06:33:06+03:00

Обновлен блок аналитики с инфографикой классов, неизвестных и воронки статусов заказов

## ⚖️ Decision | 2026-06-30T06:37:36+03:00

Создан план развития и улучшений модуля мониторинга ИИ-агентов (Agent Monitor)

## ⚖️ Decision | 2026-06-30T06:41:04+03:00

Реализован интерактивный пульт управления ИИ-агентом (Agent Monitor) и расширенная аналитика заказов (Analytics Grid)

## ⚖️ Decision | 2026-06-30T16:51:01+03:00

Оптимизация и минимизация топ меню, переименование проекта в Данила Мастер

## ⚖️ Decision | 2026-07-04T06:31:16+03:00

Premium Sidebar redesign with dark green glassmorphism

## ⚖️ Decision | 2026-07-04T06:31:29+03:00

Redesigned left navigation rail to premium glassmorphism dark-green style

## ⚖️ Decision | 2026-07-04T06:42:42+03:00

Полный редизайн интерфейса под светлую тему Glassmorphism

## ⚖️ Decision | 2026-07-04T07:51:02+03:00

Модернизация логов аудита и локализация PartsOps Cockpit

## ⚖️ Decision | 2026-07-05T01:00:47+03:00

Восстановлена работоспособность Open WebUI путем добавления HF_ENDPOINT

## ⚖️ Decision | 2026-07-05T01:15:43+03:00

Настроены подключения моделей NVIDIA NIM и LM Studio в Open WebUI

## ⚖️ Decision | 2026-07-05T02:23:33+03:00

Перенос Канбан-доски в боковое меню навигации и премиум-редизайн шапки дашборда

## ⚖️ Decision | 2026-07-05T04:44:48+03:00

Phase 9 Client Portal MVP — доведение проекта до финального состояния

## ⚖️ Decision | 2026-07-05T04:53:50+03:00

Полный раздел поставщиков — карточки, детали, таблица категорий

## ⚖️ Decision | 2026-07-05T06:18:03+03:00

Карточка поставщика - полноэкранная страница с вкладками

## ⚖️ Decision | 2026-07-06T04:52:56+03:00

Learning: добавлены Code Hygiene Rules, исправлен порт Vite, добавлена секция Frontend Vite-проверки

## ⚖️ Decision | 2026-07-06T05:50:35+03:00

Рефакторинг структуры проекта, улучшение безопасности Multi-Tenancy, openpyxl парсинг и маскирование PII

## ⚖️ Decision | 2026-07-06T06:11:45+03:00

Установка и настройка NASM и Codex MCP

## ⚖️ Decision | 2026-07-06T06:13:37+03:00

Удаление NASM, установка и настройка Taste Skill и подключение к Codex

## ⚖️ Decision | 2026-07-06T07:13:33+03:00

Production Stabilization Program: PostgreSQL migration track, zero-trust RBAC, secure upload pipeline

## ⚖️ Decision | 2026-07-08T05:51:55+03:00

Решение проблемы автодополнения Autodoc через JS-клик кнопки поиска

## ⚖️ Decision | 2026-07-20T22:05:26+03:00

P0: Extract intake pipeline to app.agents.legacy_intake_pipeline

## ⚖️ Validated Summary | 2026-07-21

- Legacy intake graph (узлы classifier/vin/parts/scatter/pricing/gates + intake_app + full_pipeline_graph + process_intake_request) вынесен из `partsops-ai-manager/agents.py` в `partsops-ai-manager/app/agents/legacy_intake_pipeline.py`.
- `agents.py` стал re-export шимом через `__getattr__` + `importlib.import_module` — круговой импорт `app.agents.* ↔ agents` решён.
- Поведение идентичное: все 10 публичных символов доступны по старым путям, тесты test_agents.py::TestE2EAgentWorkflow, test_automation_pipeline.py::test_full_pipeline_graph_initializes проходят локально.
- Коммит: `261b0a7 P0: Extract intake pipeline into app.agents.legacy_intake_pipeline + shim` (ветка `audit/scrape-fixes`).

## Открытые вопросы (Phase 2+)

- P2 кандидат: транзакционная гигиена — закрытие сессии БД до LLM/HTTP-вызовов внутри `process_intake_request`/узлов графа. После 7 промежуточных коммитов (LLM circuit-breaker, rate-limiter, parser-guards) — контекст требует ревизии.
- P3 кандидат: `settings.PHASE_LABEL` отстаёт от фактической стадии (`Phase 1 — Runtime Foundation`).
- P4: разграничение продуктивого пути `process_intake_request` ↔ new-стек `app.agents.*` для `/api/requests` — пока сосуществуют.

## ⚖️ Decision | 2026-07-21T00:31:36+03:00

Learn: gallery-dl Pinterest scraping skill + Genesis workflow

## ⚖️ Decision | 2026-07-25T11:46:55+03:00

PartsOps AI Manager Admin Cockpit Premium UI Redesign and Concept Design Reference

## ⚖️ Decision | 2026-07-25T13:56:10+03:00

Implemented 6 Reference Design Sections in Admin Cockpit UI (Deep Graphite Theme, Radar Charts, LLM Telemetry, Cryptographic Audit Log)

## ⚖️ Decision | 2026-07-26T16:36:49+03:00

Implemented Batch OEM Search, Job Report Screen, and XLSX export via openpyxl

## ⚖️ Decision | 2026-07-27T02:06:55+03:00

ADR: Alembic Migration Downgrade Safety & Warning Remediation Rules

## ⚖️ Decision | 2026-07-28T02:22:59+03:00

Интеграция Hermes Copilot в PartsOps Admin Cockpit (Read-Only sidecar, API Server contract, PII masking, Help corpus, SSE)

## ⚖️ Decision | 2026-07-28T09:40:55+03:00

Исправление интеграции Hermes Copilot: вызов Hermes CLI -z, исправленный hermes serve, авторизованный SSE, строгое цитирование источников, линейная миграция Alembic

## ⚖️ Decision | 2026-07-28T14:23:05+03:00

Soft UI Refactor Admin Cockpit: Light mode CSS tokens, self-hosted Plus Jakarta Sans, Phosphor icons, typed view model

## ⚖️ Decision | 2026-07-28T14:28:27+03:00

Fixed sidebar footer clipping and icon mapping in Admin Cockpit

## ⚖️ Decision | 2026-07-28T18:00:36+03:00

Removed hover actions block from Kanban cards and updated icons in Kanban board

## ⚖️ Decision | 2026-07-28T18:03:23+03:00

Implemented confirmation modal, animated progress bar, and algorithm execution logs during Kanban drag-and-drop transitions

## ⚖️ Decision | 2026-07-28T18:04:38+03:00

Fixed parameter order in KanbanBoard onTransitionRequest call and implemented live telemetry logs connected to backend transition API

## ⚖️ Decision | 2026-07-28T18:08:26+03:00

Added supplier initials avatar circle and phone/email action links next to contact in SupplierCards

## ⚖️ Decision | 2026-07-28T18:32:05+03:00

Redesigned SupplierDetailPage with premium glassmorphism layout and GSAP motion, fixed Tables tab CSS Grid column and table horizontal clipping

## ⚖️ Decision | 2026-07-28T18:34:53+03:00

Redesigned new table form with a premium drag and drop zone, hover transitions, file remove button, and renamed the submit button to Создать таблицу

## ⚖️ Decision | 2026-07-28T18:39:41+03:00

Fixed Suppliers tab content wrapping in App.tsx to enable true edge-to-edge layout for workspace view, eliminating double paddings and clipping

## ⚖️ Decision | 2026-07-28T19:18:33+03:00

Grouped monitoring/tech menu items in sidebar under Admin section

## ⚖️ Decision | 2026-07-28T19:26:58+03:00

Redesigned Custom intake with chevron stepper, real supplier sources and modal editor

## ⚖️ Decision | 2026-07-28T19:41:47+03:00

Deploy-ready enhancements for Custom intake panel: presets, API pings, position management

## ⚖️ Decision | 2026-07-28T19:53:42+03:00

Refactored Custom intake: separated Sources into Step 2, added high-contrast buttons and automated Drag and Drop parsing

## ⚖️ Decision | 2026-07-28T20:06:23+03:00

Redesigned Dashboard and WorkspaceHeader into premium hero cards inspired by reference UI

## ⚖️ Decision | 2026-07-28T20:20:50+03:00

Connected real ping-all endpoint and localized UI states to Russian

## ⚖️ Decision | 2026-07-28T21:53:54+03:00

Кастомный экспорт цен в XLSX по форме договора с гиперссылками на скриншоты скрапинга

## ⚖️ Decision | 2026-07-28T22:00:59+03:00

Обновлены поставщики для скрапинга (Exist.ru, Autodoc.ru, Rossko.ru) и наименования в отчете Excel переведены на русский язык

## ⚖️ Decision | 2026-07-28T22:25:11+03:00

Интегрирован обновленный дизайн отчета пользователя: черная шапка DIN Condensed, 4-строчная геометрия блоков, DIN Alternate и зебра-подсветка

## ⚖️ Decision | 2026-07-28T22:31:23+03:00

Реализована итоговая строка Total (G и M), прочерки '-', безопасный фоллбэк Calibri и архитектура хранилища скриншотов storage/evidence
