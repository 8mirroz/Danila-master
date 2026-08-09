# Runbook: RFQ inbound email (staging / design-partner)

**Status:** C4 ops readiness  
**Depends on:** Alembic `a9e4f1b2c3d0`, API C1–C3, cockpit `EmailInboxPage`  
**Related:** `docs/design-rfq-inbound-email.md`, `scripts/smoke_email_inbound.py`

---

## 1. Goal

Receive partner RFQ mail at `rfq+{org_slug}@inbound.<your-domain>` → PartsOps inbox → operator **Создать заявку** (`source=EMAIL`).

---

## 2. Prerequisites

| Item | Notes |
|------|--------|
| Postgres | Production DB; run migrations |
| `PARTSOPS_EMAIL_WEBHOOK_SECRET` | Strong secret ≥ 16 chars; HMAC body |
| Public HTTPS API | e.g. `https://api.staging.example/api/integrations/email/inbound` |
| Mail vendor | Mailgun **or** SES inbound (recommended over IMAP) |
| Admin user | To `PUT /api/email/config` per tenant |

```bash
cd partsops-ai-manager
alembic upgrade head   # includes a9e4f1b2c3d0 email tables
```

---

## 3. DNS (example: Mailgun)

1. Create receiving domain `inbound.example.com` (or subdomain).
2. Add MX / TXT as vendor requires for inbound routes.
3. SPF/DKIM for domain reputation (soft-fail is OK; hard reject only if configured).

**Addressing convention:**

```
rfq+acme@inbound.example.com   →  org_slug=acme  →  tenant_id via EmailInboxConfig
```

Never trust `tenant` from message body — only recipient map.

---

## 4. Vendor route → webhook

Configure inbound route / receipt rule:

| Setting | Value |
|---------|--------|
| URL | `https://<api-host>/api/integrations/email/inbound` |
| Method | POST JSON |
| Auth | App-level HMAC (see below) — map vendor signing to our header if needed |

**Canonical payload** (adapter layer may transform vendor → this shape):

```json
{
  "provider": "mailgun",
  "message_id": "<unique@mail>",
  "from": "buyer@partner.ru",
  "to": ["rfq+acme@inbound.example.com"],
  "subject": "RFQ …",
  "text_body": "…",
  "html_body": null,
  "attachments": [
    {
      "filename": "rfq.xlsx",
      "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "bytes_base64": "…"
    }
  ],
  "auth_results": { "spf": "pass", "dkim": "pass" }
}
```

**Signature:**

```http
X-PartsOps-Signature: sha256=<hex(hmac_sha256(raw_body, PARTSOPS_EMAIL_WEBHOOK_SECRET))>
```

If vendor only supports their own signature, put a thin edge function that re-signs the body for PartsOps.

**Rate limit:** `PARTSOPS_EMAIL_WEBHOOK_RPM` (default 60/IP/min).

---

## 5. Tenant config (API)

As **admin**:

```bash
curl -sS -X PUT "$BASE/api/email/config" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: $ORG_ID" \
  -H "X-User-Role: admin" \
  -H "Content-Type: application/json" \
  -d '{
    "org_slug": "acme",
    "address": "rfq+acme@inbound.example.com",
    "provider": "mailgun",
    "auto_ingest": false,
    "default_priority": "normal",
    "allowed_senders": []
  }'
```

Or cockpit: **Входящие email** → block «Конфиг inbox (admin)».

Dev seed (local only):

```bash
SEED_EMAIL_INBOX=1 SEED_EMAIL_INBOX_ADDRESS=rfq+default@inbound.local \
  # then start app so seed_database runs
```

---

## 6. Operator flow (cockpit)

1. Open **Входящие email**.
2. Filter status «К разбору» (`parsed`).
3. Open letter → check masked body + attachment artifact ids.
4. **Создать заявку** → `POST …/ingest` → status `ingested` + `request_id`.
5. Open kanban / request card.

If `auto_ingest=true`, webhook may create request immediately; failures surface as `auth_results.auto_ingest_error`.

---

## 7. Local smoke (no vendor)

```bash
export BASE_URL=http://127.0.0.1:8000
export PARTSOPS_API_TOKEN=test-token
export PARTSOPS_EMAIL_WEBHOOK_SECRET=dev-secret-at-least-16
python scripts/smoke_email_inbound.py
```

Expect: `OK request_id=REQ-…`.

---

## 8. Security checklist

- [ ] Webhook secret only in secret manager / env (not git)
- [ ] Unknown `rfq+slug` → 404, zero DB rows
- [ ] Tenant isolation: manager A cannot list B messages
- [ ] Attachment allowlist only (xlsx/csv/pdf/txt/docx)
- [ ] Rotate `PARTSOPS_EMAIL_WEBHOOK_SECRET` after leak
- [ ] HTTPS only in staging/prod

---

## 9. Troubleshooting

| Symptom | Check |
|---------|--------|
| 401 signature | Raw body must match signed bytes; no JSON re-encode |
| 404 unknown recipient | `org_slug` / address in `EmailInboxConfig` |
| 429 | RPM limit; raise `PARTSOPS_EMAIL_WEBHOOK_RPM` carefully |
| ingest 422 | status rejected/duplicate; or empty content |
| UI empty | Backend up; token/tenant headers; filter status |

---

## 10. Rollback

- Disable vendor route (stop inbound).
- Set `auto_ingest=false`.
- Optional: leave tables; data is audit trail.
- Alembic downgrade only if schema must go: `alembic downgrade 7c2e9a1b0d40` (drops email tables).
