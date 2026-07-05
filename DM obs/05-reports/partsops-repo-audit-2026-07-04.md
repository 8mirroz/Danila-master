# PartsOps Repository Audit — 2026-07-04

## Scope

Аудит выполнен для `/Users/user/projects/Danila master` с использованием трех сабагентов:

- backend/API/data integrity: `partsops-ai-manager`
- frontend/admin cockpit: `partsops-ai-manager/06_UI/admin_cockpit`
- docs/ops/repo hygiene: `DM obs`, `partsops_agent_os_devpack`, project root

Живой продукт сейчас состоит из FastAPI + SQLite backend в `partsops-ai-manager` и React/Vite cockpit в `partsops-ai-manager/06_UI/admin_cockpit`. Канонический human-memory/doc слой находится в `DM obs`. `partsops_agent_os_devpack` выглядит как spec/devpack слой и не подключен полностью к runtime.

## Validation Summary

Команды, которые были запущены:

```bash
cd "/Users/user/projects/Danila master/partsops-ai-manager/06_UI/admin_cockpit"
npm run lint
npm run build

cd "/Users/user/projects/Danila master/partsops-ai-manager"
python3 -m pytest -q
./venv/bin/python -m pytest -q
```

Результат:

- `npm run lint` — passed.
- `npm run build` — passed.
- `python3 -m pytest -q` — не запустился: системный Python не содержит `pytest`.
- `./venv/bin/python -m pytest -q` — failed: `1 failed, 102 passed`.

Failing test:

```text
tests/test_llm.py::TestCallLLMRetryFallback::test_retry_then_success
RuntimeError: All LLM providers/models failed
```

Причина по выводу теста: `llm.call_llm()` теперь fast-fail-ит network/timeout ошибки без retry, а тест ожидает retry после первого `ConnectionError("timeout")`. Это либо регрессия поведения retry, либо устаревший тест-контракт.

## Critical Findings

### 1. PII уходит в agent/LLM слой через свободный текст

Severity: Critical

Evidence:

- `partsops-ai-manager/main.py:125-133` маскирует отдельные поля `customer_phone`, `customer_email`, `vehicle_vin`, `customer_name`.
- `partsops-ai-manager/main.py:126` оставляет `agent_text = payload.text`.
- `partsops-ai-manager/main.py:133` отправляет этот raw `agent_text` в `process_intake_request()`.

Risk:

Если телефон, email, VIN или имя находятся внутри `payload.text`, они попадут в agent/LLM pipeline без маскирования. Это противоречит заявленному принципу "PII Masking before agent layer".

Recommended fix:

- Ввести маскирование PII по всему `payload.text` перед вызовом agent layer.
- Разделить raw input storage и PII-safe agent input.
- Добавить тест: request text содержит phone/email/VIN, agent получает masked text.

### 2. RBAC и tenant boundary подделываются headers

Severity: Critical

Evidence:

- `partsops-ai-manager/rbac.py:9-18` берет tenant из `X-Tenant-ID`, default `default`.
- `partsops-ai-manager/rbac.py:21-32` берет role из `X-User-Role`, default `manager`.
- `partsops-ai-manager/main.py:58-64` включает permissive CORS.

Risk:

Любой клиент может выставить `X-User-Role: admin` или чужой `X-Tenant-ID`. Это не security boundary, а локальный stub.

Recommended fix:

- Явно пометить текущий RBAC как dev-only или заменить на JWT/session auth.
- Запретить privileged endpoints без authenticated principal.
- Ограничить CORS через env-configured allowlist.

## High Findings

### 3. Tenant isolation неполная

Severity: High

Evidence:

- `partsops-ai-manager/main.py:266-294` events/audit endpoints не фильтруют tenant.
- `partsops-ai-manager/main.py:323-326` catalog search не принимает tenant.
- `partsops-ai-manager/main.py:449-452` `/api/invoices` возвращает все invoices.
- `partsops-ai-manager/event_store.py:79-85` `get_events()` фильтрует только `request_id`.

Risk:

После появления нескольких tenants возможны cross-tenant reads по events, audit, invoices и catalog.

Recommended fix:

- Протянуть `tenant_id` во все read endpoints.
- Добавить tenant filter в event store helpers и matcher.
- Добавить cross-tenant regression tests.

### 4. State-machine invariants есть, но API transition их не применяет

Severity: High

Evidence:

- `partsops-ai-manager/state_machine.py:57-80` поддерживает `strict_invariants`.
- `partsops-ai-manager/main.py:242` вызывает `validate_transition(req.status, target_state, req.model_dump())` без `strict_invariants=True`.

Risk:

Оператор может перевести заявку в состояние, которое формально требует pricing evidence, ERP refs или audit completion, но данные отсутствуют.

Recommended fix:

- Включить strict invariants для manual transition endpoint.
- Вернуть violations в UI.
- Добавить API tests на `ERP_SYNCING -> INVOICE_DRAFTED` без evidence и `FULFILLED -> CLOSED` без audit chain.

### 5. Invoice generation bypasses approval/state machine

Severity: High

Evidence:

- `partsops-ai-manager/main.py:333-419` создает invoice draft без проверки текущего state.
- `partsops-ai-manager/tests/test_api.py:87-105` закрепляет сценарий: сразу после создания request можно создать invoice.

Risk:

Можно выпустить draft invoice до approval/pricing gates. Это ломает workflow contract и devpack validation gates.

Recommended fix:

- Разрешить invoice generation только из допустимых состояний, например `APPROVED` или `ERP_SYNCING`.
- После успешного draft обновлять ERP refs/state через state machine.
- Переписать тест так, чтобы он сначала проводил заявку через approval path.

### 6. Audit hash chain не детектит payload tampering

Severity: High

Evidence:

- `partsops-ai-manager/event_store.py:88-108` проверяет только `previous_event_hash`.
- Хеш текущего события не пересчитывается из persisted content.

Risk:

Изменение `payload_json`, `actor_id`, `event_type` или timestamp может остаться незамеченным, если linkage не менялся.

Recommended fix:

- Стабилизировать canonical hash payload.
- В `verify_event_chain()` пересчитывать current event hash и сравнивать с persisted `event_hash`.
- Добавить tamper test для `payload_json`.

### 7. Frontend drag/drop Kanban допускает invalid transitions без UX rollback

Severity: High

Evidence:

- `partsops-ai-manager/06_UI/admin_cockpit/src/components/KanbanBoard.tsx:157-173` использует hardcoded target states.
- `partsops-ai-manager/06_UI/admin_cockpit/src/App.tsx:883-897` ловит ошибку transition в console/error alert path без полноценного rollback state.

Risk:

UI выглядит как будто переход доступен, хотя backend может вернуть `422`.

Recommended fix:

- Строить допустимые actions из `/api/state-machine/{state}`.
- Блокировать drag/drop для недопустимых transitions.
- Показывать backend reason/violations в UI.

### 8. Git/repo hygiene контур сломан

Severity: High

Evidence:

- В корне есть `.git`, но `git status` и `git rev-parse` падают.
- `.git` содержит только `hooks/pre-commit`, без нормальной git metadata.
- Root `.gitignore` не найден.
- В дереве лежат `.env`, SQLite DB, `venv`, `dist`, `__pycache__`, `.pytest_cache`.

Risk:

Невозможно надежно контролировать изменения, secrets/artifacts легко случайно перенести или заархивировать, CI/guardrails не опираются на git state.

Recommended fix:

- Восстановить/переинициализировать git metadata осознанно.
- Добавить root `.gitignore`.
- Вынести secrets из рабочей копии или гарантировать, что `.env` never committed.
- Удалить generated/runtime artifacts из отслеживаемого/передаваемого слоя.

## Medium Findings

### 9. Frontend pricing и backend invoice считают разные суммы

Severity: Medium

Evidence:

- `partsops-ai-manager/06_UI/admin_cockpit/src/components/PricingCalculator.tsx:49-95` считает logistics/risk/urgency/margin локально.
- `partsops-ai-manager/06_UI/admin_cockpit/src/components/PricingCalculator.tsx:104-111` отправляет `logistics_cost`, `margin_override`, `urgency_level`.
- `partsops-ai-manager/main.py:365-368` игнорирует эти поля и использует fixed markup `1.30`.

Risk:

Оператор видит одну цену, ERP draft создается с другой.

Recommended fix:

- Сделать backend единственным source of truth для pricing preview и invoice.
- Или явно вернуть backend-calculated preview до draft.
- Добавить contract test на совпадение UI payload и backend invoice calculation.

### 10. Request/invoice writes и events не атомарны

Severity: Medium

Evidence:

- `partsops-ai-manager/main.py:160-184` request commit происходит до серии event commits.
- `partsops-ai-manager/main.py:418-423` invoice commit происходит до event emit.
- `partsops-ai-manager/event_store.py:73-75` каждый event сам делает `commit()`.

Risk:

Ошибка между commit steps оставит бизнес-объект без полного audit trail.

Recommended fix:

- Управлять transaction boundary на уровне endpoint/service.
- Не делать commit внутри низкоуровневого `emit_event()` без явного режима.
- Добавить тест на rollback при simulated event failure.

### 11. File intake в UI есть, backend upload surface отсутствует

Severity: Medium

Evidence:

- `partsops-ai-manager/06_UI/admin_cockpit/src/App.tsx:575-603` принимает drag/drop files.
- Для PDF/DOC/XLS подставляется текстовая заглушка `[Файл: ...]`.
- `partsops-ai-manager/06_UI/admin_cockpit/src/App.tsx:612-619` отправляет обычный JSON в `/api/requests`.
- Backend endpoint с `UploadFile` не найден.

Risk:

Оператор может думать, что файл распознан, хотя в backend ушла только заглушка.

Recommended fix:

- Либо убрать обещание PDF/Word/Excel до появления backend upload/OCR.
- Либо добавить `/api/uploads` + storage + extraction pipeline.
- В UI явно показывать unsupported state для binary docs.

### 12. Offline draft message теряет данные

Severity: Medium

Evidence:

- `partsops-ai-manager/06_UI/admin_cockpit/src/App.tsx:530-560` при ошибке backend показывает "оффлайн-черновик ... подготовлен локально".
- Draft не добавляется в `requests`, не сохраняется в localStorage/session, не экспортируется.

Risk:

Текст заказа потерян, но UX сообщает о подготовленном draft.

Recommended fix:

- Либо сохранять offline draft в явное local/session storage с recovery UI.
- Либо заменить сообщение на честную ошибку отправки.

### 13. AgentMonitor выглядит live, но данные симулированы

Severity: Medium

Evidence:

- `partsops-ai-manager/06_UI/admin_cockpit/src/components/AgentMonitor.tsx:14-31`, `53-73`, `150-164` используют templates/random/timers.

Risk:

Операторский cockpit показывает неоперационные метрики как live status.

Recommended fix:

- Подключить `/api/admin/llm-status`, `/api/admin/budget-stats`, real event stream.
- До подключения пометить блок как simulation/dev или убрать из production cockpit.

### 14. AuditTimeline скрывает ошибку загрузки audit/events

Severity: Medium

Evidence:

- `partsops-ai-manager/06_UI/admin_cockpit/src/components/AuditTimeline.tsx:27-41` превращает failures в empty surface.

Risk:

Нельзя отличить "нет событий" от "audit endpoint недоступен".

Recommended fix:

- Разделить empty, loading, error.
- Показывать HTTP status/reason.
- Добавить retry action.

### 15. Devpack validation/security policies не enforce-ятся runtime

Severity: Medium

Evidence:

- `partsops_agent_os_devpack/01_CONFIGS/validation_gates.yaml` описывает gates.
- Runtime `partsops-ai-manager` не импортирует эти gates.
- Invoice endpoint и transition endpoint работают по локальной логике.

Risk:

Spec слой и runtime расходятся; документы создают ложное чувство безопасности.

Recommended fix:

- Явно выбрать: devpack как documentation-only или как executable policy source.
- Если executable: подключить gates в service layer и покрыть tests.

### 16. Backend reproducibility неполная

Severity: Medium

Evidence:

- `requirements.txt`/`pyproject.toml` для backend не найден.
- `partsops-ai-manager/start.sh:3` жестко зависит от локального `venv`.
- Системный `python3 -m pytest` не работает без локального venv.

Risk:

Новый агент/машина не сможет воспроизвести backend без ручной реконструкции зависимостей.

Recommended fix:

- Добавить backend dependency manifest.
- Зафиксировать supported Python version.
- Добавить `make test-backend` или documented command.

## Low Findings

### 17. `apiFetch` слишком тонкий для cockpit API contract

Severity: Low

Evidence:

- `partsops-ai-manager/06_UI/admin_cockpit/src/lib/api.ts:10-12` только вызывает `fetch`.

Risk:

Нет единого timeout, tenant/auth headers, JSON parse guard и error shape.

Recommended fix:

- Добавить small API client wrapper с typed errors и default headers.

### 18. Неиспользуемые/устаревшие UI surfaces остаются в `src`

Severity: Low

Evidence:

- `RightPanel.tsx`, части `Primitives.tsx`, `InvoicesRegistry.tsx` содержат mock/legacy logic.

Risk:

Растет audit surface, сложнее понимать live path.

Recommended fix:

- Пометить legacy компоненты или удалить после проверки imports.

### 19. Mobile/tablet behavior не валидирован

Severity: Low

Evidence:

- Rails скрываются на `<lg`, critical controls живут в rail surfaces.
- Layout использует nested scroll и `h-screen/overflow-hidden`.

Risk:

На tablet/mobile оператор может потерять intake/queue controls.

Recommended fix:

- Провести Playwright viewport checks.
- Добавить mobile drawer/command fallback для hidden rails.

## Prioritized Fix Plan

1. Security/data boundary:
   - mask full text before agent layer;
   - replace spoofable RBAC headers or gate them as dev-only;
   - tenant-filter events/audit/invoices/catalog.

2. Workflow correctness:
   - enforce strict invariants in transition endpoint;
   - gate invoice generation by state;
   - align invoice state updates and ERP refs.

3. Audit integrity:
   - recompute event hashes during verification;
   - make request/invoice/event writes atomic.

4. Pricing contract:
   - make backend pricing source of truth;
   - remove or reconcile frontend-only totals.

5. UX honesty:
   - remove fake file-recognition promise or implement upload;
   - replace simulated live metrics with real endpoints or explicit dev label;
   - surface audit/load errors.

6. Repo operations:
   - repair git metadata;
   - add root `.gitignore`;
   - define backend dependencies and validation commands.

## Suggested Validation Commands

Frontend:

```bash
cd "/Users/user/projects/Danila master/partsops-ai-manager/06_UI/admin_cockpit"
npm run lint
npm run build
```

Backend:

```bash
cd "/Users/user/projects/Danila master/partsops-ai-manager"
./venv/bin/python -m pytest -q
```

Focused tests to add after fixes:

```bash
cd "/Users/user/projects/Danila master/partsops-ai-manager"
./venv/bin/python -m pytest -q \
  tests/test_api.py \
  tests/test_events.py \
  tests/test_state_machine.py \
  tests/test_llm.py
```

## Notes

- The audit did not change production code.
- This report intentionally does not print secret values from `.env`.
- The backend test suite currently takes about 9 minutes in the local venv and produces many deprecation warnings around `datetime.utcnow()`.
