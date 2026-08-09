# Design: RFQ Inbound Email

**Status:** Draft for implementation (C0)  
**Date:** 2026-08-09  
**Roadmap link:** `docs/quoteops-saas-roadmap.md` weeks 5–6 (RFQ inbox + inbound email)  
**Growth id:** P-RFQ-EMAIL  

---

## 1. Problem

Design partners still paste RFQs through cockpit (CSV/XLSX upload or free text). Partners already live in email. Without inbound mail:

- Operators re-enter data already attached in mail threads.
- Automation Rate stays capped by UI friction.
- Intake sources stay `FILE_UPLOAD` / manual only.

## 2. Goal

Accept **inbound email → tenant-safe RFQ intake**, reusing existing write paths:

| Existing building block | Reuse |
|-------------------------|--------|
| `services/rfq_imports.py` | Spreadsheet preview + column mapping |
| `services/request_service.create_request` | Canonical request create + quota |
| `process_intake_request` / intake agents | Text/PDF-ish freeform parse |
| `UploadArtifact` + secure upload | Attachment storage |
| `pii.secure_pre_parse` / `mask_email` | Agent/LLM-safe body |
| RBAC + tenant claims | Isolation |

**Non-goals (this design):**

- Outbound quote delivery email (roadmap weeks 9–10, outbox).
- Full IMAP multi-mailbox SaaS for arbitrary customer domains (phase later).
- Auto-reply chatbots in the mail thread.

## 3. Principles

1. **Tenant isolation first** — resolve `tenant_id` from recipient mapping, never from untrusted body fields alone.
2. **One intake write-path** — email does not invent a second request lifecycle.
3. **Review-first for beta** — `auto_ingest=false` by default; operator promotes from inbox.
4. **Idempotent** — `(tenant_id, Message-ID)` unique; duplicates do not double-bill usage.
5. **PII-safe** — raw MIME in tenant object storage; LLM sees masked excerpt only.
6. **Honest status** — UI shows `received | parsed | ingested | rejected | duplicate`, never silent drop.

## 4. Provider choice

| Option | Pros | Cons | Beta |
|--------|------|------|------|
| A. IMAP per tenant | Familiar | Credential sprawl, brittle poll | ❌ |
| B. Shared inbox + `rfq+{org}@` | Easy partner UX | Cross-tenant misroute risk | ⚠️ only with hard tests |
| **C. Signed inbound webhook** (SES / Mailgun / Postmark) | Scalable, HMAC, no long-lived IMAP | DNS + vendor setup | ✅ **default** |

**Dev-only:** optional IMAP poller behind `PARTSOPS_EMAIL_IMAP_URL` for local demos; not required for staging.

### Addressing (recommended)

```
rfq+{org_slug}@inbound.<partsops-domain>
```

Server map: `org_slug → organization_id / tenant_id` (table `EmailInboxConfig`).  
Reject unknown recipients with 404/200-ignore (vendor-dependent) without creating rows.

## 5. Architecture

```
┌──────────────────┐   signed webhook    ┌─────────────────────┐
│ SES / Mailgun    │ ─────────────────► │ POST /api/integrations/email/inbound
└──────────────────┘                     └──────────┬──────────┘
                                                    │
                                         ┌──────────▼──────────┐
                                         │ EmailIngestService  │
                                         │  verify · map · store│
                                         └──────────┬──────────┘
                    ┌───────────────────────────────┼───────────────────────────────┐
                    ▼                               ▼                               ▼
           EmailMessage row                 UploadArtifact(s)                 (optional)
           status=received/parsed           xlsx/csv/pdf/txt                  PartRequest
                                                                              source=EMAIL
```

Worker (optional for heavy MIME): enqueue `email.parse` job after webhook ACK ≤ 3s.

## 6. Data model (additive)

### `EmailInboxConfig`

| Field | Type | Notes |
|-------|------|--------|
| `tenant_id` | str PK-ish | org boundary |
| `address` | str unique | full receive address |
| `org_slug` | str unique | plus-address key |
| `provider` | enum | `ses` \| `mailgun` \| `postmark` \| `imap_dev` |
| `auto_ingest` | bool | default `false` |
| `default_priority` | str | e.g. `normal` |
| `allowed_senders_json` | str? | optional allowlist domains/emails |
| `default_mapping_id` | str? | FK ImportMapping for xlsx |
| `created_at` / `updated_at` | datetime | |

### `EmailMessage`

| Field | Type | Notes |
|-------|------|--------|
| `id` | str | `emsg-…` |
| `tenant_id` | str indexed | |
| `provider_message_id` | str | RFC Message-ID |
| Unique | `(tenant_id, provider_message_id)` | idempotency |
| `from_masked` | str | PII masked |
| `to_address` | str | as received |
| `subject` | str | truncated |
| `received_at` | datetime | |
| `raw_storage_uri` | str | `emails/{tenant}/{id}.eml` |
| `raw_sha256` | str | |
| `body_masked_excerpt` | str | ≤ 4–8k chars |
| `status` | enum | see below |
| `request_id` | str? | set on ingest |
| `rejection_reason` | str? | |
| `attachment_artifact_ids_json` | str | list |
| `spamd_score` / `auth_results` | optional | soft signals |

**Statuses:** `received` → `parsed` → `ingested` | `rejected` | `duplicate`.

Alembic migration only; production remains PostgreSQL.

## 7. API surface

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/integrations/email/inbound` | HMAC + webhook secret | Provider webhook |
| `GET` | `/api/email/messages` | manager+ | Inbox list (tenant scoped) |
| `GET` | `/api/email/messages/{id}` | manager+ | Detail + artifacts |
| `POST` | `/api/email/messages/{id}/ingest` | manager+ | Promote → `PartRequest` |
| `POST` | `/api/email/messages/{id}/reject` | manager+ | Reject with reason |
| `GET` / `PUT` | `/api/email/config` | admin | Inbox config |

### Webhook contract (sketch)

```http
POST /api/integrations/email/inbound
X-PartsOps-Signature: sha256=<hmac>
Content-Type: application/json

{
  "provider": "mailgun",
  "message_id": "<abc@mail.gmail.com>",
  "from": "buyer@partner.ru",
  "to": ["rfq+acme@inbound.partsops.example"],
  "subject": "Заявка на тормоза",
  "received_at": "2026-08-09T12:00:00Z",
  "text_body": "...",
  "html_body": null,
  "attachments": [
    {"filename": "rfq.xlsx", "content_type": "…", "bytes_base64": "…"}
  ],
  "auth_results": {"spf": "pass", "dkim": "pass"}
}
```

**Auth:** HMAC over raw body with `PARTSOPS_EMAIL_WEBHOOK_SECRET`.  
**Tenant resolution:** parse `to` → `org_slug` → `EmailInboxConfig.tenant_id`.  
**Response:** `202 { "email_message_id": "emsg-…", "status": "received" }` or `200` duplicate.

## 8. Processing pipeline

1. Verify signature; reject 401/403.
2. Map recipient → tenant; unknown → log + drop (no cross-tenant guess).
3. Idempotency: existing `(tenant, message_id)` → return duplicate status.
4. Optional sender allowlist check → `rejected` with reason.
5. Store raw `.eml` / provider payload to object storage (S3 or local), SHA-256.
6. Mask body (`secure_pre_parse`); persist excerpt.
7. Attachments:
   - Allow: `.xlsx .xls .csv .pdf .txt .docx`
   - Reject: executables, macros-risky without flag, > size limit (align upload limits)
   - Each → `UploadArtifact` tenant path
8. If spreadsheet: run `rfq_imports` preview with `default_mapping_id` when set.
9. If `auto_ingest=true` and validation ok → `create_request` / intake with `source=EMAIL`.
10. Else leave `parsed` for operator **Создать заявку**.
11. Emit audit events: `email.received`, `email.ingested`, `email.rejected`.
12. Usage billing: **only** on accepted valid positions (same ledger as RFQ import) — never on raw mail receive.

## 9. Cockpit UI

- Nav: **«Входящие email»** near RFQ import / orders.
- List: received_at, from_masked, subject, attachment count, status, request link.
- Detail: excerpt, attachments download, buttons **Создать заявку** / **Отклонить**.
- Config (admin): display address, auto-ingest toggle, default mapping, allowlist.

Empty / error states must be honest (no fake “synced” badges).

## 10. Security & compliance

| Topic | Rule |
|-------|------|
| Cross-tenant | Fixture tests: webhook for org A must not create rows in org B |
| Secrets | Webhook secret + provider keys only in env / secret manager |
| PII | Raw MIME retention TTL (suggest 30–90d); agent path always masked |
| Rate limit | Per IP + per tenant webhook RPM |
| SPF/DKIM | Soft-fail → flag UI; hard reject only if config says so |
| LLM | Never pass full MIME headers with `Authorization` / cookies |

## 11. Settings (env)

```bash
PARTSOPS_EMAIL_WEBHOOK_SECRET=   # required staging/prod
PARTSOPS_EMAIL_PROVIDER=mailgun  # ses|mailgun|postmark|imap_dev
PARTSOPS_EMAIL_MAX_ATTACHMENT_MB=15
PARTSOPS_EMAIL_RAW_TTL_DAYS=60
# dev only
PARTSOPS_EMAIL_IMAP_URL=
```

## 12. Phased delivery

| Phase | Deliverable | Effort | Depends |
|-------|-------------|--------|---------|
| **C0** | This design + ADR | 0.5 d | — | **done 2026-08-09** |
| **C1** | Models, migration, webhook verify + idempotency tests | 2–3 d | C0 | **done 2026-08-09** |
| **C2** | Attachments → artifacts → ingest → `create_request` | 2 d | C1, S3/local storage | **done 2026-08-09** (`store_attachments`, `POST …/ingest`, `auto_ingest`, tests) |
| **C3** | Cockpit inbox UI | 2–3 d | C2 | next |
| **C4** | Staging DNS + vendor + design-partner mailbox | 1–2 d ops | C3, beta secrets | |

## 13. Acceptance criteria (C1–C3)

- [x] Duplicate Message-ID does not create second message row (C1) / request (C2).
- [x] Unknown recipient creates zero rows.
- [x] Manager of tenant A cannot `GET` messages of tenant B.
- [x] Attachments with base64 become `UploadArtifact` (source=email); spreadsheet text best-effort for ingest.
- [x] Free-text body can create request with `source=EMAIL` via `POST …/ingest` (idempotent).
- [x] `auto_ingest=false` never auto-creates; `auto_ingest=true` promotes when content usable.
- [x] Unit + isolation tests in CI (`tests/test_email_inbound.py`).

## 14. Open decisions (defaults if not overridden)

| Decision | Default |
|----------|---------|
| Provider | Mailgun or SES webhook |
| Auto-ingest | `false` (review-first) |
| PDF strategy | Store artifact; text extract best-effort; else operator manual |
| Plus-address vs dedicated domain | Plus-address under platform inbound domain |
| HTML-only mail | Strip tags → text; if empty, `needs_manual_parse` path |

## 15. Implementation sketch (future)

Suggested modules (do not create until C1):

- `models_email.py` or fields in `models.py`
- `services/email_ingest.py`
- `routers/email_inbox.py` + webhook under `routers/integrations.py`
- `06_UI/admin_cockpit/src/components/EmailInboxPage.tsx`
- `tests/test_email_inbound.py`

Wire: `main.py` router include; Alembic revision; `.env.example` keys only.

---

## 16. References

- `services/rfq_imports.py` — spreadsheet RFQ
- `services/request_service.py` — `create_request`
- `docs/quoteops-saas-roadmap.md` — weeks 5–6, 9–10
- `docs/beta-readiness.md` — release gates
- Growth report P-RFQ-EMAIL
