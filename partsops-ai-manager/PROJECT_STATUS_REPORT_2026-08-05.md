# Отчет о состоянии проекта PartsOps AI Manager

Дата проверки: 05.08.2026  
Канонический объект: `/Users/user/projects/Danila master/partsops-ai-manager`

## Итоговый статус

Проект находится на стадии **функционального прототипа / pre-staging стабилизации**: основные backend-контуры и операторский cockpit реализованы и проходят автоматические проверки, но live-runtime не поднят, рабочая SQLite-база отстает от migration head, а production-readiness не подтверждена.

Это не стадия «готово к релизу». Корректная ближайшая цель — **поднять единый runtime, применить миграции, пройти API/UI smoke и закрыть найденные runtime- и UX-гейты**.

## Что реально подтверждено

| Область | Результат | Доказательство |
|---|---|---|
| Backend | PASS | `359 passed, 1 skipped` при `./venv/bin/python -m pytest tests/ -q` |
| Frontend lint | PASS | `npm run lint` |
| Frontend production build | PASS | `npm run build`, Vite собрал `dist` |
| TypeScript | PASS | `npm run build` включает `tsc -b`; отдельная проверка указана ниже |
| Архитектурное ядро | Реализовано | State Machine, Event Store, tenant/RBAC, pricing/contract flows, durable pipeline runs |
| Operator UI | Реализовано частично | Admin Cockpit, Kanban, supplier/request/audit surfaces |
| Live backend | НЕ подтверждено | На момент проверки listener на `8000` отсутствовал |
| Live frontend | НЕ подтверждено | На момент проверки Vite listener отсутствовал |
| Migration state | BLOCKED | DB `9c5d7e1a2b34`, head `6a1f4e8b2c70`; `alembic check` сообщает `Target database is not up to date` |

## Состав объекта и стадии

- `partsops-ai-manager` — единственный backend/runtime и источник бизнес-логики.
- `06_UI/admin_cockpit` — текущий операторский интерфейс; Kanban связан с durable pipeline queue и worker.
- `my-crawler` — отдельный crawler-контур для Exist/Autodoc/Rossko; его production coverage и health-verdict требуют отдельной проверки.
- `partsops_bot` — внешний/legacy adapter, не второй backend.
- `partsops_agent_os_devpack` — спецификация/blueprint, не live runtime.

Текущая стадия по слоям:

1. **Core backend:** функционально развит, автоматический suite зеленый.
2. **Durable workflow / Kanban:** код и тесты есть, live worker/API execution не подтверждены в этой проверке.
3. **Admin Cockpit:** собирается и проходит lint, но визуальный и browser E2E smoke еще не выполнены.
4. **Integration runtime:** не принят — нет живого backend/frontend/Hermes процесса и база не синхронизирована с head.
5. **Production:** не принят.

## Текущее состояние checkout

В рабочем дереве уже были изменения, их не трогал:

- `.agents/AGENTS.md`
- `DM obs/00-overview.md`
- `06_UI/admin_cockpit/src/components/KanbanBoard.tsx`
- `06_UI/admin_cockpit/src/components/KanbanCard.tsx`

Последний HEAD: `f6388f2 test: verify ERP connection preflight in staging`.  
`git diff --check` ошибок не обнаружил.

## Основные ограничения и риски

- SQLite не на актуальной схеме; запускать live smoke до миграции нельзя считать валидным приемочным тестом.
- `start.sh` поднимает Hermes, backend, pipeline worker и Vite вместе и требует сильный `HERMES_API_KEY`; для локальной проверки backend можно запускать отдельно.
- Frontend build выдает предупреждение о крупном JS chunk (~783 kB minified) и ineffective dynamic import для `src/lib/api.ts`; это не блокирует сборку, но требует оптимизации до production.
- Полный backend suite зеленый, но сопровождается 1797 warnings: устаревший `datetime.utcnow()`, предупреждение Starlette/httpx, runtime warning для временного ERP secret и warning коллекции `TestResult`.
- Автоматические тесты не заменяют проверку реального HTTP API, worker lease/replay, SSE и browser UI.

## Как затестировать локально

### 1. Проверить миграции и применить их к локальной БД

```bash
cd "/Users/user/projects/Danila master/partsops-ai-manager"
./venv/bin/alembic current
./venv/bin/alembic heads
./venv/bin/alembic upgrade head
./venv/bin/alembic check
```

`upgrade head` изменяет локальную БД, поэтому перед ним сохраните или скопируйте локальный database-файл, если в нем есть нужные данные.

### 2. Backend smoke

В отдельном терминале:

```bash
cd "/Users/user/projects/Danila master/partsops-ai-manager"
export PARTSOPS_API_TOKEN=test-token
export TESTING=1
./venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

Проверки:

```bash
curl -i http://127.0.0.1:8000/
curl -s http://127.0.0.1:8000/openapi.json | python3 -m json.tool >/dev/null
curl -s -H 'Authorization: Bearer test-token' \
  -H 'X-Tenant-ID: default' \
  http://127.0.0.1:8000/api/requests | python3 -m json.tool
curl -s -H 'Authorization: Bearer test-token' \
  -H 'X-Tenant-ID: default' \
  http://127.0.0.1:8000/api/admin/data-health | python3 -m json.tool
```

Ожидание: health/OpenAPI — HTTP 200; защищенные endpoint-ы возвращают валидный JSON и не дают доступ к чужому tenant.

### 3. Worker и durable pipeline

```bash
cd "/Users/user/projects/Danila master/partsops-ai-manager"
./venv/bin/python -m app.automation.pipeline_worker --once
```

Для постоянного режима:

```bash
./venv/bin/python -m app.automation.pipeline_worker
```

В cockpit создать/запустить pipeline run, проверить переход `queued -> running -> completed/failed`, наличие `PipelineRunEvent` и повторное подключение к SSE после перезапуска worker.

### 4. Frontend checks

```bash
cd "/Users/user/projects/Danila master/partsops-ai-manager/06_UI/admin_cockpit"
npm run lint
npm run build
npx tsc --noEmit -p tsconfig.app.json
npm run dev -- --port 5173
```

В браузере пройти основной операторский цикл: `queue -> inspect -> compare -> approve/escalate -> draft ERP`, затем проверить пустое состояние, ошибку API, обновление Kanban и audit detail.

### 5. Полный автоматический suite

```bash
cd "/Users/user/projects/Danila master/partsops-ai-manager"
./venv/bin/python -m pytest tests/ -q
```

Зафиксированный результат этой проверки: **359 passed, 1 skipped**.

## Критерий перехода на следующую стадию

Считать объект готовым к staging smoke только после того, как:

1. база обновлена до `6a1f4e8b2c70` и `alembic check` проходит;
2. одновременно живы backend, frontend и worker, без дублей процессов;
3. `/` и защищенные API дают реальные HTTP 200;
4. Kanban pipeline проходит полный DB-backed цикл с событиями и audit;
5. browser smoke подтверждает основные UI-сценарии;
6. отдельно зафиксированы результаты crawler и Hermes integration, если они входят в приемку.

