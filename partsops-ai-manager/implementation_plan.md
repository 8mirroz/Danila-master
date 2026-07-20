# implementation_plan.md

## Goal

Устранить критические, высокие и средние риски в модуле intake/scraping PartsOps AI Manager:
- заблокировать поддельные платежные вебхуки;
- убрать блокировку FastAPI workers синхронным LLM;
- защититься от DoS через неограниченный парсинг файлов и intake;
- ускорить матчинг деталей и снизить потребление памяти;
- улучшить наблюдаемость внешних вызовов и доставки.

## Task Classification

```yaml
task_class: SYSTEM
risk_level: 4
mutation_scope: code
requires_plan: true
requires_approval: true
expected_validation:
  - syntax
  - typecheck
  - unit
  - integration
rollback_strategy: git branch + revert commits by phase
```

## Source-of-Truth Inputs

- `llm.py`, `agents.py`, `app/agents/intake_agent.py`
- `services/supplier_service.py`, `app/automation/storage.py`
- `delivery.py`, `erp_adapter.py`
- `matcher.py`, `settings.py`
- `routers/requests.py`
- `tests/`

## Current-State Findings

### Critical
1. `process_payment_webhook()` не проверяет сумму платежа (`erp_adapter.py:311-400`).
2. Дефолтный `ERP_WEBHOOK_SECRET` в коде (`erp_adapter.py:46`).
3. Синхронный `call_llm()` блокирует workers на 1–60 секунд (`llm.py:308-475`).

### High
1. N+1 в `matcher.py` при загрузке каталога и поставщиков (`matcher.py:79-114`).
2. Полное чтение файлов в память без таймаута (`services/supplier_service.py:188-250`).
3. `time.sleep` в синхронном LLM-коде (`llm.py:454-459`).
4. Отсутствие circuit breaker для LLM-провайдеров.
5. Нет rate limiting на intake endpoints.

### Medium
1. `httpx` без `Limits` и без валидации прокси (`llm.py:231-241`, `delivery.py:373-387`, `erp_adapter.py:273-278`).
2. Логи через `print` вместо `logging` (`llm.py`).
3. Нет автоматических ретраев для failed outbound доставки.
4. Дублирующая загрузка каталога в память (`matcher.py:73-81`).
5. `asyncio.get_event_loop()` в async-коде может падать (`llm.py:489-491`, `llm.py:581-585`).

## Proposed Architecture

### Phase 1: Security & Financial Integrity
- Убрать хардкод webhook secret. Генерировать безопасный секрет при старте, если env не задан.
- В `process_payment_webhook()` добавить валидацию `amount` и `currency` против `Invoice.total`.
- Добавить fail-closed поведение при несовпадении суммы.

### Phase 2: Non-blocking Intake & File Safety
- Добавить `asyncio`-обертку вокруг LLM вызовов через `loop.run_in_executor` или перенести тяжелые вызовы в отдельный in-process executor с `ProcessPoolExecutor`/`ThreadPoolExecutor`.
- Заменить `time.sleep` на `asyncio.sleep` в async ветке.
- Добавить `slowapi` rate limiter на `POST /api/requests`, `POST /api/requests/import-from-artifact`.
- В `services/supplier_service.py` добавить жесткий лимит размера файла на уровне парсера (не только storage) и таймаут обработки.
- Для CSV/XLSX парсинга добавить проверку размера перед чтением и ограничение по времени через `signal.alarm` (Unix) или thread-based timeout.

### Phase 3: Matcher Performance
- Заменить N+1 на JOIN-запрос с предзагрузкой `Supplier` в словарь.
- Добавить LRU-кэш для нормализованных строк запроса и результата матчинга.
- Убрать дублирующую загрузку всего каталога при каждом вызове; использовать глобальный кэш с TTL/invalidation.

### Phase 4: HTTP Resilience & Observability
- Во всех `httpx.Client` добавить `Limits(max_connections=50, max_keepalive_connections=10)` и `timeout=...`.
- Добавить валидацию прокси-URL: разрешать только явно доверенные хосты или отключать прокси по умолчанию.
- Добавить circuit breaker через `tenacity` для LLM провайдеров: `stop_after_attempt(1)` на каждый провайдер перед fallback.
- Заменить `print` на `logging` с structured formatter или `structlog`.
- Добавить фонового воркера (ARQ/Celery или `BackgroundTasks` + таблица `OutboundMessage`) для повторных попыток failed доставок.

### Phase 5: Testing & Hardening
- Покрыть новыми unit/integration тестами:
  - payment webhook amount mismatch;
  - rate limiter behavior;
  - parser timeout/large file rejection;
  - matcher N+1 fix (assert query count);
  - circuit breaker fallback speed;
- Добавить нагрузочный тест на парсинг файла 50–100 MB (ожидается отказ по лимиту, а не OOM).

## Files/Systems to Touch

- `erp_adapter.py`
- `llm.py`
- `agents.py`
- `app/agents/intake_agent.py`
- `routers/requests.py`
- `services/supplier_service.py`
- `app/automation/storage.py`
- `matcher.py`
- `delivery.py`
- `settings.py`
- `tests/` (новые и обновленные тесты)

## Rollback Plan

1. Каждая фаза коммитится отдельно с префиксом `chore/scrape-audit-phase-N`.
2. Перед началом фазы создается ветка `audit/scrape-fixes`.
3. При проблемах:
   - `git revert <commit-range>` по проблемной фазе;
   - feature flags для rate limiter и circuit breaker (можно выключить через env);
   - fallback к старому `call_llm` через env `PARTSOPS_LLM_LEGACY=1`.
4. Данные: все изменения идемпотентны, без миграций схем.

## Validation Plan

1. `python3 -m py_compile` на всех измененных файлах.
2. `pytest tests/ -v` — существующие тесты должны проходить.
3. Новые тесты:
   - `test_payment_webhook_amount_validation` — отклоняет вебхук с неверной суммой.
   - `test_webhook_secret_not_default` — падает при дефолтном секрете.
   - `test_rate_limiter_blocks_excess` — 429 после превышения лимита.
   - `test_matcher_no_n_plus_one` — asserts количество запросов к БД.
   - `test_large_file_rejected` — файл > лимита отклоняется на уровне парсера.
4. Локальный smoke test:
   - `uvicorn main:app --reload` + `curl` на `/api/requests` с превышением rate limit.
   - Проверка, что LLM fallback работает при недоступном провайдере <5 секунд.
5. СODE REVIEW: минимум 1 ревьювер на каждую фазу.

## Risks

1. **Ломаем совместимость с существующими async routers** при изменении `call_llm` — mitigate: оставляем sync-версию, параллельно добавляем async.
2. **Фalse positive rate limiter на легитимных операторов** — mitigate: настраиваем лимиты через env, начинаем с мягких значений.
3. **Резкое падение производительности matcher при переходе на JOIN** — mitigate: профилируем EXPLAIN QUERY PLAN, индексы уже есть.
4. **Ошибки в валидации суммы платежа** (валюты, partial payments) — mitigate: поддерживаем partial payments через allowlist, документируем политику.
5. **Сложность откатки circuit breaker** — mitigate: оборачиваем в feature flag.

## Acceptance Criteria

1. Дефолтный `ERP_WEBHOOK_SECRET` отсутствует в коде; при старте генерируется секрет из 32+ байт.
2. `process_payment_webhook()` отклоняет payload, где `amount` не совпадает с `invoice.total` с допуском +/- 0.01 (partial payments по политике).
3. Нет блокирующих `time.sleep` в hot path; LLM fallback завершается за <5 секунд при недоступном провайдере.
4. `match_part_from_db()` выполняет не более 2 SQL-запросов независимо от числа деталей.
5. Парсинг файла >15MB завершается ошибкой `UPLOAD_FILE_TOO_LARGE` на уровне парсера за <1 секунду.
6. На `POST /api/requests` срабатывает rate limit после 10 запросов в минуту с одного IP/tenant.
7. Все `httpx` клиенты имеют `Limits(max_connections=50, max_keepalive_connections=10)` и явный `timeout`.
8. Существующий test suite проходит без изменений.

## Execution Steps

### Phase 1: Security & Financial Integrity (1 день)

**Step 1.1: Удалить дефолтный webhook secret**
- Файл: `erp_adapter.py:46`
- Действие: заменить статический дефолт на генерацию через `os.urandom(32).hex()` при импорте, если env не задан.
- Валидация: добавить test, что дефолтный секрет не закоммичен.

**Step 1.2: Валидация суммы платежа**
- Файл: `erp_adapter.py:311-400`
- Действие: после `invoice = session.exec(...)` сравнить `payload["amount"]` с `invoice.total`; допуск `0.01` для partial payments; проверять `currency`.
- Валидация: unit test с неверной суммой, тестовый прогон `tests/test_gates.py`.

### Phase 2: Non-blocking Intake & File Safety (2-3 дня)

**Step 2.1: Async LLM wrapper**
- Файлы: `llm.py`, `agents.py`, `app/agents/intake_agent.py`, `routers/requests.py`, `services/request_service.py`
- Действие: добавить `call_llm_async` как основную обертку; оставить sync-версию для обратной совместимости; заменить `time.sleep` на `asyncio.sleep`.
- Валидация: `pytest tests/test_agents.py tests/test_llm.py`.

**Step 2.2: Rate Limiter**
- Файлы: `routers/requests.py`, `settings.py`
- Действие: добавить `slowapi` limiter на `POST` endpoints; лимит 10/min на tenant; конфиг через env.
- Валидация: curl тест с 11 запросами.

**Step 2.3: File parser hardening**
- Файлы: `services/supplier_service.py`, `app/automation/storage.py`
- Действие: добавить проверку размера перед открытием файла; таймаут парсинга через `signal.SIGALRM` (Unix) или `ThreadPoolExecutor` с timeout; ограничить чтение первыми N строками для CSV.
- Валидация: тест с файлом 50MB, ожидаем `UPLOAD_FILE_TOO_LARGE` за <1s.

### Phase 3: Matcher Performance (1 день)

**Step 3.1: Убрать N+1**
- Файл: `matcher.py`
- Действие: один запрос `SELECT ... FROM suppliercatalogitem LEFT JOIN supplier`; построить `supplier_by_id` dict.
- Валидация: тест `test_matcher_no_n_plus_one` с assert `len(captured_queries) <= 2`.

**Step 3.2: Кэширование**
- Действие: `functools.lru_cache` на очищенную строку запроса; TTL кэш для каталога при росте.
- Валидация: benchmark `match_part_from_db` до/после.

### Phase 4: HTTP Resilience & Observability (1-2 дня)

**Step 4.1: httpx hardening**
- Файлы: `llm.py`, `delivery.py`, `erp_adapter.py`
- Действие: добавить `Limits(max_connections=50, max_keepalive_connections=10)`; явный `timeout`; валидация прокси (разрешать только `http/https` схемы).
- Валидация: unit test на невалидный прокси.

**Step 4.2: Circuit Breaker**
- Файл: `llm.py`
- Действие: обернуть каждый провайдер в `tenacity.Retrying(stop=stop_after_attempt(1), retry=retry_if_exception_type(...))`.
- Валидация: имитация падения провайдера, проверка быстрого fallback.

**Step 4.3: Structured logging**
- Файлы: `llm.py`, `delivery.py`, `erp_adapter.py`
- Действие: заменить `print` на `logging.getLogger(...).info/error`; добавить correlation_id.

**Step 4.4: Outbound retry worker**
- Файлы: `delivery.py`, `app/automation/jobs/`
- Действие: добавить scheduled job, который переотправляет `OutboundMessage` со статусом `failed` и `attempts < MAX`.
- Валидация: integration test с фейловым отправлением и последующим ретраем.

### Phase 5: Testing & Hardening (1-2 дня)

- Написать новые тесты (см. Validation Plan).
- Запустить нагрузочный тест парсинга файла 50MB (локально, с kill после таймаута).
- Code review + merge в `main` через PR.

## Rollback Commands

```bash
git revert <phase1-commit>..<phase2-commit>
export PARTSOPS_LLM_LEGACY=1  # fallback на sync LLM
```

## Approval

Требуется явное одобрение перед началом Phase 1 (изменения в платежном вебхуке) и Phase 2 (изменения в LLM hot path).
