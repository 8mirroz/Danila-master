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

## Структура кода

Claude / агенты должны знать следующие точки входа:

| Модуль | Назначение | Правило адресации |
|---|---|---|
| `main.py` | FastAPI endpoints (runtime, ~1000 строк) | Только endpoints; бизнес-логику переноси в `services/` |
| `models.py` | SQLModel таблицы (`PartRequest`, `RequestEvent`, `Invoice`, `Supplier`, `RequestScore`, `ApprovalTicket`, `LLMUsageLog`, ...) | Один source of truth на схему |
| `database.py` | `engine`, `get_session`, `init_db` | Все запросы через `Session(engine)` |
| `event_store.py` | `emit_event`, `emit_state_change`, `verify_event_chain` | Tenant-scoped SHA-256 hash chain |
| `rbac.py` | `get_current_principal`, `RoleChecker` | Bearer token + X-Tenant-ID required |
| `state_machine.py` | `validate_transition`, `transition` | Все статусы проходят здесь |
| `pricing.py` | `compute_price`, `check_margin_guard`, `PricingContext` | Только backend |
| `pii.py` | `mask_phone`, `mask_email`, `mask_vin`, `mask_name` | Обрабатывает перед логированием и LLM |
| `app/automation/` | Job runners, engines, policies | 1 job = 1 file, поддерживают dry_run |

Состояние на сейчас: много логики в `partsops-ai-manager/main.py` (runtime-комбайн). Планируется рефактор:
```
services/
  request_service.py
  pricing_service.py
  audit_service.py
routers/
  requests.py
  pricing.py
  invoices.py
  chat.py
```

## RBAC quick reference (rbac.py)

```python
# В депенденсах endpoints:
principal: CurrentPrincipal = Depends(get_current_principal)
tenant_id: str = Depends(get_current_tenant)

# Жёсткие правила:
# - Без PARTSOPS_API_TOKEN — dev mode, X-Tenant-ID принимается из header, роль = manager
# - С PARTSOPS_API_TOKEN — только Bearer валиден, headers игнорируются без него
# - admin / manager / finance — единственные allowed roles
```

## Event Store invariants

```python
# emit_event → вычисляет event_hash (SHA-256 canonical JSON)
# previous_event_hash → chain-link на last event для того же request_id + tenant_id
# verify_event_chain → rekursive hash-проверка, вламывается на:
#   - payload_json tamper
#   - evidence_refs tamper
#   - переставленный previous_event_hash
```

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
- ❌ Не импортируй опциональные модули (agent_orchestrator, base_agent) без `try/except`.
- ❌ Не коммить `.env`, `*.db`, `__pycache__/`.
- ❌ Не трогай `DM obs/` — это Obsidian vault, синхронизируется скриптом.
- ❌ Не добавляй node_modules/ или сборки frontend в main репо.

## Frontend Vite-проверки
- После изменений в `06_UI/admin_cockpit/src/`: `npx tsc --noEmit -p tsconfig.app.json`.
- Vite dev-server: default порт 5173 (не 3000).
- `TS6133` (noUnusedLocals) не блокирует Vite runtime, но `TS2304` — блокирует трансформацию → белый экран.

## Obsidian

См. `scripts/sync_obsidian.sh` и `/.agents/AGENTS.md`.
Vault: `/Users/user/projects/Danila master/DM obs/`.
После архитектурных изменений и закрытых задач запускай:
```bash
cd /Users/user/projects/Danila master && bash scripts/sync_obsidian.sh
```
