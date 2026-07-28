# Durable Pipeline Ops Runbook

**Дата:** 2026-07-28  
**Коммит:** `1c5e423` (durable Kanban pipeline) + anti-mock `72ac639`  
**Код:** `partsops-ai-manager/services/pipeline_runs.py`, `app/automation/pipeline_worker.py`

---

## 1. What it does

Operator Kanban / API can **queue** a multi-agent pipeline run without blocking the HTTP request:

1. `POST /api/requests/{id}/pipeline-runs` → status `queued` (202) or existing active run (200 idempotent)
2. Worker claims run with DB lease → status `running`
3. Orchestrator runs phases with `on_phase` → `PipelineRunEvent` stream
4. Terminal: `completed` | `failed` | `blocked`
5. UI/API can poll `GET …/pipeline-runs/{run_id}` or SSE `…/events`

---

## 2. Migration

```bash
cd partsops-ai-manager
source venv/bin/activate   # if used
export DATABASE_URL=...    # prod/stage DSN
alembic upgrade head
# expected head: 9c5d7e1a2b34
alembic heads
```

SQLite local/dev: `init_db()` / `SQLModel.metadata.create_all` also creates tables when models are imported.

---

## 3. Worker process

```bash
cd partsops-ai-manager
export DATABASE_URL=...
export PARTSOPS_PIPELINE_WORKER_ID="$(hostname)-$$"   # optional stable id
export PYTHONPATH=.

# one shot (CI / debug)
python -m app.automation.pipeline_worker --once

# long-running
python -m app.automation.pipeline_worker --poll-seconds 1.0
```

**systemd sketch:**

```ini
[Service]
WorkingDirectory=/opt/partsops/partsops-ai-manager
EnvironmentFile=/opt/partsops/.env
Environment=PYTHONPATH=.
ExecStart=/opt/partsops/venv/bin/python -m app.automation.pipeline_worker --poll-seconds 1
Restart=always
```

Without a worker, runs stay **`queued`** forever — UI must show that honestly.

---

## 4. API smoke

```bash
TOKEN=...
API=http://127.0.0.1:8000
REQ=REQ-...

# enqueue
curl -sS -X POST -H "Authorization: Bearer $TOKEN" -H "X-Tenant-ID: default" \
  -H "Content-Type: application/json" \
  -d '{"requested_lane":"matching"}' \
  "$API/api/requests/$REQ/pipeline-runs" | jq .

# status
curl -sS -H "Authorization: Bearer $TOKEN" -H "X-Tenant-ID: default" \
  "$API/api/requests/$REQ/pipeline-runs/PR-..." | jq .
```

---

## 5. Contract export template

See `partsops-ai-manager/docs/contract-export-templates.md` (physical files still go under `08_DATA/templates/`, which may be gitignored).

```bash
export PARTSOPS_CONTRACT_EXPORT_TEMPLATE=/path/to/Форма\ ответа_договор.xlsx
```

Missing template → **422**, no silent empty workbook.

---

## 6. Local start.sh (optional worker)

```bash
export PARTSOPS_START_PIPELINE_WORKER=1
./start.sh
```

When set, `start.sh` spawns the pipeline worker next to backend/frontend.

---

## 7. Docker notes

`docker-compose.yml` currently sets `TESTING=1` on backend — **dev/demo only**.  
For STAGE/PROD compose override:

- `TESTING=0`
- `SEED_ON_START=0`
- `PARTSOPS_ENV=production`
- real `PARTSOPS_API_TOKEN`, `DATABASE_URL`, ERP/SMTP as in `prod-env-checklist-2026-07-28.md`
- run migrations in entrypoint or init job
- add a `pipeline-worker` service using the same image/env as backend

---

## 8. Failure modes

| Symptom | Cause | Action |
|---------|--------|--------|
| Runs stuck `queued` | No worker | Start worker / check lease |
| `failed` quickly | Agent/orchestrator error | Read `error_message` + logs |
| Export 422 template | Missing XLSX | Set env / place template |
| SSE ends early | Terminal status | Expected for completed/failed |

---

## Related docs

- `prod-env-checklist-2026-07-28.md`
- `anti-mock-closeout-2026-07-28.md`
- `mocks-stubs-inventory-2026-07-28.md`
