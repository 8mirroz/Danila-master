# PartsOps AI Manager — Agent Rules

Этот файл — краткий ориентир для любого агента (Hermes, Claude, Codex и т.д.), который стартует в `partsops-ai-manager/`. Цель: не тратить первый запрос на repeat-опрос “что такое, как запустить”, работать сразу с кодом.

## Start

```bash
cd partsops-ai-manager

# Шаг 1. Окружение: локально или через управляемую venv
if [ ! -d venv ]; then
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt 2>/dev/null || pip install fastapi sqlmodel uvicorn python-dotenv pydantic
else
  source venv/bin/activate
fi

# Шаг 2. Конфиг
cp .env.example .env 2>/dev/null
export PARTSOPS_API_TOKEN=test-token   # локально любой токен
export TESTING=1                        # отключает внешние вызовы в тестах

# Шаг 3. БД и запуск
uvicorn main:app --reload --port 8000 --host 0.0.0.0
```

Проверка:
```bash
curl -s -H "Authorization: Bearer test-token" -H "X-Tenant-ID: default" http://localhost:8000/ | python3 -m json.tool
```

Frontend (через Vite):
```bash
cd partsops-ai-manager/06_UI/admin_cockpit
npm install && npm run dev
```

## Обязательные non-negotiables

1. **tenant_id обязателен на каждом запросе.** Запрос без `X-Tenant-ID` получает `default`, но никогда не должен течь в чужой tenant.
2. **State Machine — единственный путь транзишенов.** Никаких `UPDATE status SET ...` вне `state_machine.validate_transition`.
3. **Любая опциональная импортируемая зависимость — lazy.** Если модуль может отсутствовать (`agent_orchestrator`, `base_agent` и т.д.), импортируй его в `try/except` с флагом доступности. Endpoint возвращает `501`, если модуль не собран.
4. **LLM и внешние HTTP — после commit, до commit.** Транзакции к БД должны закрываться до вызова LLM/внешнего API.
5. **Все outbound-сообщения через outbox.** Файл `app/automation/events.py`, таблица `outboundmessage`.
6. **События в Event Store emit'ятся атомарно с основной операцией.** End-of-request не означает end-of-record.
7. **PII — до агент-слоя.** Все совпадения с PHI/PII/обиды проходят через `pii.*` функции перед логированием.
8. **Тесты — с фикстурами тестовой БД в памяти.** Никаких изменений в `database.db` в продакшене из кода тестов.

## Project Reality

- Live backend entrypoint: `main.py`
- Preferred business logic placement: `services/`
- Preferred HTTP surface: `routers/`
- Preferred agent layer: `app/agents/*`
- Preferred automation layer: `app/automation/jobs/*`
- Job registration: `app/automation/registry.py`
- Current live operator UI: `06_UI/admin_cockpit`
- Secondary frontend surface: `06_UI/client_portal`
- `agents.py` and `agent_orchestrator.py` are legacy surfaces; do not add new core logic there.
- Request lifecycle changes go through `app/agents/*` plus `services/` and `routers/`.
- Scheduled work goes through `app/automation/jobs/*` and `app/automation/registry.py`.

## Business Domain / Contract Rules

Core domain: request intake, supplier matching, pricing evidence, invoice/ERP flow, audit trail, operator review.

Treat these as implementation targets only after checking live code coverage:

- SLA limits by request type
- pricing evidence requirements
- OEM vs OEQ policy by category
- approval gates before financial or fulfillment transitions
- document-generation deadlines
- return / closure conditions for old parts
- watchdog automation for stalled or breached requests

Verify live code first; do not assume the policy is already implemented.

## 🛡️ Agent Safety Rules (выучены на опыте)

### Работа с файлами
- **view_file output ≠ file content** — вывод `view_file` содержит `<N>: ` префиксы перед каждой строкой. Этот вывод **НИКОГДА** не должен напрямую использоваться как содержимое для `write_to_file` / `replace_file_content`. Брать только чистый контент.
- **Синтаксис перед перезапуском**: выполнить `python3 -m py_compile main.py` ДО `kill` старого процесса.
- **Порядок hot-patch**: `patch → validate → kill → start`. Никогда `kill → patch → start`.
- **Запрещены `.bak`, `.bak2`, `.backup` файлы** — использовать `git stash` или git-ветки.

### CORS / порты
- Frontend Vite: default порт **5173**, может занять **5174** если 5173 занят. Проверять: `ps aux | grep vite`.
- CORS origins: хранить только в `.env` → `PARTSOPS_CORS_ORIGINS`. **Не хардкодить в `main.py`**.
- Диагностика «фронт не работает»:
  1. `ps aux | grep vite` → узнать реальный порт
  2. `grep CORS .env` → сравнить с портом
  3. `curl http://localhost:8000/` → проверить бэкенд

### TypeScript / Vite
- После любого рефакторинга TSX: `npx tsc --noEmit -p tsconfig.app.json`.
- Закомментированная переменная не должна иметь живых ссылок в коде.
- `TS2304` (Cannot find name) — **блокирует Vite runtime** → белый экран.
- `TS6133` (noUnusedLocals) — не блокирует runtime, но нежелателен.

### main.py — монолит
- Файл `main.py` содержит ~74KB и 38 эндпоинтов. **Не добавлять новые эндпоинты в main.py**.
- Новая логика → `routers/` и `services/`. Использовать существующую структуру как точку входа.

### 🗄️ Миграции Alembic & Базы Данных
- **Идемпотентность отката индексов**: При написании и редактировании Alembic миграций в функции `downgrade()` для любых вызовов `op.drop_index` **ОБЯЗАТЕЛЬНО** указывать параметр `if_exists=True` (`op.drop_index('ix_name', table_name='tbl', if_exists=True)`). Это предотвращает сбои `OperationalError: no such index` при откате, если индекс был удален на предыдущих шагах миграционной цепочки.
- **Migration Gate Check**: Для подтверждения надежности миграций всегда проверять полный цикл: `empty DB -> alembic upgrade head -> alembic downgrade base -> alembic upgrade head`.

### ⚠️ DeprecationWarning & Timezone Handling
- **Замена datetime.utcnow()**: Для устранения `DeprecationWarning: datetime.datetime.utcnow() is deprecated` заменять вызовы на `datetime.now(timezone.utc).replace(tzinfo=None)` (если целевые поля БД/модели работают с наивным временем UTC), чтобы сохранить полную совместимость без предупреждений.
- **Legacy Query API**: В тестах и коде заменять `session.query(Model)` на актуальный `session.exec(select(Model))` (для удаления использовать `session.exec(delete(Model))`).

## Code Map

- `main.py`: HTTP runtime only, no new business logic.
- `models.py`: SQLModel source of truth.
- `database.py`: sessions and DB bootstrap.
- `event_store.py`: event emission and hash chain.
- `rbac.py`: auth and tenant scoping.
- `state_machine.py`: all status transitions.
- `pricing.py`: pricing rules and margin guard.
- `pii.py`: masking before logs/LLM.
- `app/automation/`: jobs, engines, policies.

Runtime note: many flows still pass through `main.py`; prefer `services/` and `routers/` for new logic.

RBAC rule of thumb: `get_current_principal` + `get_current_tenant` in endpoints, and only `admin`, `manager`, `finance` are valid roles.

Event-store rule of thumb: event hash is canonical JSON + tenant/request chain; do not mutate events outside the helper path.

## Запуска тестов

```bash
cd partsops-ai-manager

# Быстрые unit-тесты (in-memory БД):
python3 -m pytest tests/test_events.py tests/test_tamper_detection.py tests/test_api.py -v

# Всё:
python3 -m pytest tests/ -v

# С покрытием:
python3 -m pytest tests/ --cov=. --cov-report=term-missing
```

В `tests/conftest.py` уже настроен `TESTING=1` и чистка `test_database.db`.

## Чего НЕ делать

- ❌ Не писать бизнес-логику в эндпоинт прямо — вынеси в сервис.
- ❌ Не добавляй новую логику в `agents.py` или `agent_orchestrator.py`, если есть `app/agents/*`.
- ❌ Не импортируй опциональные модули (agent_orchestrator, base_agent) без `try/except`.
- ❌ Не коммить `.env`, `*.db`, `__pycache__/`.
- ❌ Не трогай `DM obs/` — это Obsidian vault, синхронизируется скриптом.
- ❌ Не добавляй node_modules/ или сборки frontend в main репо.
- ❌ Не забывай `npx tsc --noEmit -p tsconfig.app.json` после TSX-изменений.
- ❌ Не ломай CORS/портовую схему: Vite 5173, backend 8000, origins из `.env`.
