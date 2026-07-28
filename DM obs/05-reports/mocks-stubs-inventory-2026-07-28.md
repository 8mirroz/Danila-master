# Реестр моков и заглушек — Danila Master / PartsOps

**Дата:** 2026-07-28  
**Scope:** `/Users/user/projects/Danila master`

---

## 1. Концепт системы

**PartsOps AI Manager** — operational control plane для закупки автозапчастей:

| Контур | Путь | Роль |
|--------|------|------|
| Admin Cockpit | `partsops-ai-manager/06_UI/admin_cockpit` | Операторский UI: очередь, matching, pricing, suppliers, audit |
| Backend API | `partsops-ai-manager/` (FastAPI) | State machine, agents, ERP outbox, automation jobs |
| Client Portal | `partsops-ai-manager/06_UI/client_portal` | Публичный трекинг / accept-reject оффера |
| Crawler | `my-crawler/` | Exist / Autodoc / Rossko — live scraping (не mock) |
| Agent OS Devpack | `partsops_agent_os_devpack/` | Scaffold контрактов агентов + static console |
| Telegram bot | `partsops_bot/` | Бот (без явных mock/stub в коде) |
| Memory | `DM obs/` | Планы, DoD, UX-правила |

**Цель (из overview):** premium operational cockpit, data-dense, explainable, без «generic dashboard».  
**Стадия:** discovery / demo active; runtime modes DEV–STAGE–PROD.  
**Hard rules:** admin-only invoice, tool permissions, traces, evidence, hide margin from client.

**Ключевой принцип из docs:** live data > decorative mock; если данных нет — explicit `partial` / `stale` / `blocked`, а не fake percentage.

---

## 2. Классификация (легенда)

| Класс | Смысл | Нужно ли «чинить» |
|-------|--------|-------------------|
| **T** Test mock | `unittest.mock`, MagicMock, test fixtures | Нет (норма) |
| **S** Seed / demo data | Стартовые поставщики/каталог для локального DEMO | Оставить для DEV; не путать с PROD |
| **D** Dry-run / simulation | Поведение без внешних SMTP/ERP | Норма для DEV; в PROD выключить |
| **U** UI demo fallback | Ложные данные, когда API пустой | **Да** — убрать или пометить |
| **P** Production stub | Каркас без реальной логики, может врать в runtime | **Да** — приоритет |
| **C** Contract scaffold | Devpack TODO-agents | Отдельный трек (не runtime ai-manager) |

---

## 3. Полный реестр

### 3.1 Backend production stubs / fallbacks — `partsops-ai-manager`

| ID | Где | Класс | Состояние | Что делает | Риск | Задача |
|----|-----|-------|-----------|------------|------|--------|
| B1 | `app/automation/engines/vin_query_engine.py` | **P** | stub | `decode_vin` → `{decoded: False, reason: "stub"}` | VIN-джобы не декодируют | Подключить real VIN API / локальный decoder |
| B2 | `app/automation/engines/*` (12 engines) | **P** | noop/placeholder | `sync_erp`, `escalate`, `notify`, `generate_po`, `check_policy`, `score_quotes`, `find_suppliers` — пустой «ok» | Automation layer — каркас | Реализовать по приоритету job'ов или удалить dead code |
| B3 | Engines: `decision_engine`, `erp_hub_engine`, `quote_score_engine`, `vendor_query_engine` | **P** | empty file | Только docstring «placeholder for Phase 4» | Пустые модули | Реализовать или удалить |
| B4 | `app/automation/jobs/notify_owner_job.py` | **P** | event-only | Пишет event `notification: true`, **не шлёт** email/TG | Оператор думает, что уведомление ушло | Вызвать `delivery.py` / real channel |
| B5 | `app/automation/jobs/dead_letter_cleanup_job.py` | **P** | no-op | Всегда `removed: 0` | DLQ не чистится | Реальная retention-логика |
| B6 | `client_portal.py` → `verify_tracking_token` | **P** | broken stub | `return False  # Placeholder` | Dead API; основной path — DB lookup | Удалить или реализовать |
| B7 | `llm.py` mock provider | **D/S** | intentional | MOCK только при `TESTING=1` | Низкий (gated) | Оставить; не включать в PROD |
| B8 | `matcher.py` `MOCK_INVENTORY` | **S/P** | fallback | Если DB пуст — in-memory 5 позиций | В PROD при пустой БД «находит» фейковые детали | В PROD: fail closed / empty |
| B9 | `suppliers.py` SEED_* + Invoice «Mock ERP Invoice» | **S** | seed on startup | `main.py` → `seed_database` | DEMO-данные в dev DB | Seed только DEV/TESTING |
| B10 | `erp_adapter.py` | **D** | dry-run default | `ERP_DRY_RUN=1` или нет `ERPNEXT_URL` | Тихий dry-run | PROD: URL + secret + dry_run=0 |
| B11 | `delivery.py` email/telegram | **D** | dry-run / SMTP gate | Dry-run = simulated send | Ожидаемо | Конфиг SMTP/TG в STAGE+ |
| B12 | `app/agents/legacy_intake_pipeline.py` VIN fallback | **P** | heuristic mock | WBA→BMW X5 2018 else Toyota Camry 2017 | **Ложный VIN decode** | `vin_validity=unknown` + UI badge |
| B13 | Intake classifier / parts extractor fallbacks | **D/P** | local heuristics | Keyword spam/parts без LLM | Degraded mode | Оставить + confidence |
| B14 | `01_CONFIGS/llm_providers.yaml` mock block | **D** | config | Документированный mock provider | — | Оставить |

**Engines (B2) — детальный список:**

```
vin_query_engine.py          → stub reason
erp_connector_engine.py      → synced: False
escalation_engine.py         → escalated: False
notification_engine.py       → sent: False
po_generation_engine.py      → po_number: None
policy_engine.py             → violations: []
quote_evaluation_engine.py   → best_quote: None
supplier_discovery_engine.py → []
decision_engine.py           → empty placeholder
erp_hub_engine.py            → empty placeholder
quote_score_engine.py        → empty placeholder
vendor_query_engine.py       → empty placeholder
```

Jobs в основном **не stubs**: domain-логика + dry_run gate. Исключения: B4, B5.

---

### 3.2 Frontend UI mocks — Admin Cockpit

| ID | Где | Класс | Состояние | Суть | Задача |
|----|-----|-------|-----------|------|--------|
| U1 | `CompletedOrdersHistory.tsx` | **U** | **active fake** | Пустой list → 6 hardcoded заказов (`CRM_MOCK`) | Empty state без fake data |
| U2 | `MultiAgentOrchestraView.tsx` | **U** | **active fake** | `mockRun()` demo pipeline | Empty/partial; demo за flag |
| U3 | `RightPanel.tsx` | **U**/naming | source=`UI_MOCK` | Source label ручного intake | → `UI_MANUAL` / `OPERATOR_UI` |
| U4 | `InvoicesRegistry.tsx` | comment | soft | mock/session inference | Status из API |
| U5 | `Primitives.tsx` WorkspaceHeader | fixed | ok | fake telemetry already removed | — |
| U6 | Global Search / Keyboard shortcuts | **P** (UI) | not built | CMD+K / shortcuts | Implement or unclaim |
| U7 | Overview metrics (docs) | **U/P** | partial live | Часть KPI hardcoded | Live metrics API |
| U8 | ERP Sync / Payments UI | **P** | stub UX | Нет payment/ERP status UI | ERP status panel |
| U9 | File intake copy | soft | | Upload copy ≠ OCR complete | Честный UX |

**Не моки:** HTML `placeholder="..."` на inputs.

---

### 3.3 Agent OS Devpack — scaffold stubs

| ID | Где | Класс | Состояние |
|----|-----|-------|-----------|
| C1 | `04_BACKEND_CONTRACTS/agents/*.py` (11 agents) | **C** | Все `status: "stub"` + TODO |
| C2 | `05_FRONTEND/src/App.tsx` | **C/U** | Static hardcoded suppliers/requests |
| C3 | Rollout Phase 1 | **C** | Mock metrics / events / approvals |

Stub-агенты: `supervisor`, `offer_ranker`, `invoice_draft`, `debug`, `catalog_matcher`, `vehicle_validator`, `supplier_query`, `report`, `risk_checker`, `request_parser`, `operator_copilot`.

**Важно:** не путать с runtime `partsops-ai-manager/app/agents/*`.

---

### 3.4 Test mocks (не tech debt)

| Область | Примеры | Класс |
|---------|---------|-------|
| `partsops-ai-manager/tests/*` | unittest.mock, MagicMock, TEST_MOCK, FakeHermesTransport | **T** |
| `my-crawler/tests/*` | unit tests | **T** |

---

### 3.5 Crawler / Bot

| Модуль | Моки? | Комментарий |
|--------|-------|-------------|
| `my-crawler` | Нет production mocks | Live Playwright |
| `partsops_bot` | Нет | Реальный bot code |

---

## 4. Анализ состояния (сводка)

| Слой | % «не mock» | Комментарий |
|------|-------------|-------------|
| Core request lifecycle | ~80–90% | DEMO path рабочий |
| Matching / pricing | ~70% | DB real; empty-DB mock residual |
| Delivery / ERP | ~40% | Outbox есть; default dry-run |
| Automation engines | ~10% | Jobs wired; engines stubs |
| Agent OS Devpack | ~5% | Scaffold only |
| Admin UI polish | ~60–70% | 2–3 hard UI fakes + gaps |

**LIVE:** request CRUD, state machine, matching (DB), pricing/gates/audit, crawler, supplier CRUD, Hermes (if configured), delivery (if env).  
**DRY-RUN by design:** ERP, SMTP simulation, LLM mock (TESTING), seed.  
**STUB/FAKE tech debt:** engines×12, VIN mock, notify_owner, DLQ cleanup, verify_tracking_token, MOCK_INVENTORY, U1/U2 UI fakes, ERP payments UX, Devpack.

---

## 5. Задачи (backlog)

### P0 — убрать ложь в UI/runtime
1. ~~U1 CompletedOrdersHistory — remove fake list~~ **DONE 2026-07-28**  
2. ~~U2 MultiAgentOrchestraView — remove silent mockRun~~ **DONE 2026-07-28**  
3. ~~B12 VIN mock assignment → unknown~~ **DONE 2026-07-28**  
4. ~~B8 MOCK_INVENTORY only TESTING=1~~ **DONE 2026-07-28**  

> SDD W1: Spec Approved → parallel implementers → Code Reviewer **LGTM**. Residual: U3 `UI_MOCK` naming (W2).  


### P1 — critical production stubs
5. ~~B4 notify_owner → real channel~~ **DONE 2026-07-28** (outbox enqueue, not false sent)  
6. ~~B1 real VIN engine or mark partial~~ **DONE 2026-07-28** (offline WMI via `pii.decode_vin_offline`)  
7. B10/B11 PROD env checklist  
8. U8 ERP/payment status UI  
9. ~~B6 fix/remove verify_tracking_token~~ **DONE 2026-07-28** (DB-backed, tests)  

### P2 — automation engines
10. ~~Implement used engines vs delete and inline~~ **DONE 2026-07-28** — engines honesty layer: `implemented`/`status`/`reason`, thin adapters (notify outbox, offline VIN, quote rank, supplier DB, local PO draft); erp_hub/vendor explicit `not_wired`. Jobs still inline (not rewired). Reviewer fixes: ERP dry-run `synced=False`, PII-mask notify logs.  
11. ~~B5 dead_letter cleanup~~ **DONE 2026-07-28** (failed exhausted + retention)  
12. Policy/quote/supplier discovery if jobs depend — optional rewire jobs → engines (out of scope)  

### P3 — UX honesty
13. ~~U3 rename UI_MOCK~~ **DONE 2026-07-28** (`UI_MANUAL`)  
14. ~~U6 CMD+K / shortcuts~~ **DONE 2026-07-28** (⌘K + G-seq + ⌘N/R; inputs ignored)  
15. ~~U7 live overview metrics~~ **DONE 2026-07-28** (ERP KPI: OK/Сбой/н/д, no fake 100%)  
16. ~~Seed behind SEED_ON_START~~ **DONE 2026-07-28** (explicit flag / prod off / sqlite default)  
17. ~~U8 ERP fake push UX~~ **DONE 2026-07-28** (CommandPalette + dashboard + notify.erpSync = health check only)  
18. ~~AgentMonitor fake logs~~ **DONE 2026-07-28**  
19. ~~JobReportView demo parts / 100% / 1.2d~~ **DONE 2026-07-28**

### P4 / ops / Devpack
- ~~B10/B11 PROD env checklist~~ **DONE 2026-07-28** → `prod-env-checklist-2026-07-28.md` + `.env.example`  
- ~~C1 Devpack agents stub honesty~~ **DONE 2026-07-28** → `ok=False`, `not_implemented`, no fake success  
- ~~C2 Devpack frontend mock label~~ **DONE 2026-07-28** → SPEC banner + mock metric captions  
- ~~C3 Rollout Phase 1 docs~~ **DONE 2026-07-28**  

### SDD execution log
- W1 P0 (U1,U2,B8,B12): Spec → Imp×2 → Review LGTM  
- W2 (U3,B6): Imp → Review LGTM  
- W3 (B4,B5,B1): Imp → Review LGTM · tests 36 related passed  
- P2 engines honesty: Imp → Review (2 fixes applied) · full suite **259 passed, 1 skipped**  
- P3 UX honesty: shortcuts, ERP labels, seed, AgentMonitor, JobReportView  
- P4: PROD checklist + Devpack scaffold honesty  
- P5 residual: AnalogComparisonMatrix live API; Excel no demo rows; escalate/VIN jobs use engines; quote_evaluate uses decide()

### P4 — Devpack
17. Wire to ai-manager agents or mark spec-only  
18. Static frontend → API or archive  

---

## 6. Концептуальные выводы

1. Test/seed/dry-run — OK; silent UI fakes и VIN mock auto — вредят trust.  
2. Automation engines — главный каркасный долг.  
3. «Demo path без заглушек» = UI workflow, не engines/ERP/notify.  
4. Devpack ≠ production agents.  
5. DoD запрещает fake metrics — U1/U2/U7 нарушают.

---

## 7. Файлы-источники

**Stubs:** `app/automation/engines/*`, `jobs/notify_owner_job.py`, `jobs/dead_letter_cleanup_job.py`, `client_portal.py`, `matcher.py`, `legacy_intake_pipeline.py`, `llm.py`, `erp_adapter.py`, `delivery.py`, `suppliers.py`  
**UI fakes:** `CompletedOrdersHistory.tsx`, `MultiAgentOrchestraView.tsx`, `RightPanel.tsx`  
**Scaffold:** `partsops_agent_os_devpack/04_BACKEND_CONTRACTS/agents/*`, `05_FRONTEND/src/App.tsx`  
**Docs:** `app-functional-description.md`, `QA_LIVE_AUDIT_REPORT_V2.md`, `supplier-workspace-implementation-plan.md`
