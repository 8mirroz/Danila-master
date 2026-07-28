# PROD Environment Checklist — PartsOps AI Manager

**Дата:** 2026-07-28  
**IDs:** B10 (ERP), B11 (SMTP/delivery), seed/auth/LLM gates  
**Канон env-файла:** `partsops-ai-manager/.env.example`

---

## 1. Pre-flight (must before PARTSOPS_ENV=production)

| # | Check | Prod value | Fail if |
|---|--------|------------|---------|
| 1 | `PARTSOPS_ENV` | `production` | unset / `dev` with real users |
| 2 | `SEED_ON_START` | `0` | `1` on shared DB |
| 3 | `TESTING` | `0` | `1` (enables mock LLM) |
| 4 | `DATABASE_URL` | Postgres DSN | sqlite file path |
| 5 | `PARTSOPS_API_TOKEN` | long random secret | empty (open API) |
| 6 | `ENABLE_STRICT_TENANT_ENFORCEMENT` | `true` | false |
| 7 | `PARTSOPS_CORS_ORIGINS` | real admin origin(s) only | `*` / localhost in public |
| 8 | LLM key | at least one real provider | only mock (TESTING) |
| 9 | `ERP_DRY_RUN` | `0` when ERP live | `1` with expectation of real invoices |
| 10 | `ERPNEXT_URL` + keys | set | dry_run=0 without URL |
| 11 | `ERP_WEBHOOK_SECRET` | persistent secret | process-random default |
| 12 | `SMTP_HOST` (+ user/pass) | set if email delivery required | missing while operators expect mail |
| 13 | `HERMES_API_KEY` | strong ≥16 chars | default/demo key |
| 14 | Uploads dir | writable, not world-readable secrets | unsecured path |

---

## 2. Seed policy (anti-mock)

From `main.py` `_should_seed_on_start()`:

| Condition | Seeds? |
|-----------|--------|
| `SEED_ON_START=1/true/yes` | Yes |
| `SEED_ON_START=0/false` | No |
| `PARTSOPS_ENV=production` (and SEED unset) | **No** |
| `PARTSOPS_ENV=dev\|local\|test\|ci` | Yes |
| Env unset + sqlite / empty DATABASE_URL | Yes (local demo) |
| Env unset + **postgres** | **No** |

**Prod rule:** always set `SEED_ON_START=0` and `PARTSOPS_ENV=production`.

---

## 3. ERP (B10)

| Var | Role |
|-----|------|
| `ERPNEXT_URL` | Base URL ERPNext |
| `ERPNEXT_API_KEY` / `ERPNEXT_API_SECRET` | API auth |
| `ERP_DRY_RUN` | `1` = no external write (safe default when URL empty) |
| `ERP_WEBHOOK_SECRET` | HMAC for payment webhooks |

**Honesty UI:** Admin cockpit «Статус ERP» only reads `/api/admin/data-health` — it does **not** start a full ERP push. Invoice path: `POST /api/erp/invoice/{request_id}` (see `routers/erp.py`).

**Smoke:**

```bash
# dry-run should not claim real sync
curl -s -H "Authorization: Bearer $PARTSOPS_API_TOKEN" \
  -H "X-Tenant-ID: default" \
  "$API/api/admin/data-health" | jq '.health_indicators.erp_health'
```

---

## 4. Delivery (B11)

| Channel | Vars | Behavior without config |
|---------|------|-------------------------|
| Email | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | fail / dry-run in `delivery.py` |
| Telegram | bot token / chat (if used by adapters) | fail without token |
| Outbox | `OutboundMessage` pending | real send via `outbound_dispatch_job` |

**Honesty:** `notify_owner` **queues** outbox (`queued`, not `sent`). Actual send = dispatch + SMTP/TG.

---

## 5. LLM

| Mode | When |
|------|------|
| Mock provider | **Only** `TESTING=1` |
| Production | `TESTING=0` + at least one of NIM / OpenRouter / LM Studio / Ollama |

Never ship production with only mock.

---

## 6. Frontend (admin_cockpit)

```bash
# 06_UI/admin_cockpit/.env
VITE_API_BASE_URL=https://api.example.com
VITE_PARTSOPS_API_TOKEN=<same as backend or scoped>
VITE_PARTSOPS_TENANT_ID=<tenant>
```

---

## 7. Go / No-go

**GO** only if:

- [ ] All rows in §1 set correctly  
- [ ] `SEED_ON_START=0` on prod DB  
- [ ] No `TESTING=1`  
- [ ] Auth token required and works  
- [ ] ERP: either dry_run intentional or live URL+keys  
- [ ] SMTP configured if email is in operator SOP  
- [ ] Health endpoint returns without fake UI %  

**NO-GO** if:

- Demo seed can write to prod DB  
- API open without token  
- Operators think ERP/email «works» while dry_run / no SMTP  

---

## 8. Related anti-mock work

See `mocks-stubs-inventory-2026-07-28.md` (P0–P3 DONE, Devpack scaffold separate).
