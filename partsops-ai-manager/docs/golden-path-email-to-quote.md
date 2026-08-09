# Golden path: Email RFQ → QuoteOps request

**Date:** 2026-08-10  
**Scope:** vertical slice for design-partner demo (local or staging)

---

## Prerequisites

- API running (`uvicorn` or staging)
- Migration `a9e4f1b2c3d0` applied
- `PARTSOPS_EMAIL_WEBHOOK_SECRET` set
- Cockpit on Vite (optional) with token/tenant env

---

## Steps

### 1. Configure inbox

- API: `PUT /api/email/config` (admin), or cockpit **Входящие email** → config block  
- Example: `org_slug=default`, `address=rfq+default@inbound.local`, `auto_ingest=false`

### 2. Inject a message

**Preferred:** `python scripts/smoke_email_inbound.py`  

**Manual:** signed `POST /api/integrations/email/inbound` with `text_body` and optional `attachments[].bytes_base64`.

**Expected:** HTTP 202, `status=parsed`, `email_message_id=emsg-…`

### 3. Operator review

- Cockpit → **Входящие email**
- Row status **К разбору**
- Detail shows masked body; attachment artifact ids if any

### 4. Create request

- Button **Создать заявку** → `POST /api/email/messages/{id}/ingest`
- **Expected:** `status=ingested`, `request_id=REQ-…`, `PartRequest.source=EMAIL`
- Second ingest returns same `request_id` (idempotent)

### 5. Continue QuoteOps

- Open kanban / request card
- Matching → pricing → approval (existing flows)
- Export / client track as usual

---

## Status map

| Stage | EmailMessage.status | PartRequest |
|-------|---------------------|-------------|
| After webhook | `parsed` | none |
| After ingest | `ingested` | `REQ-…`, source=EMAIL |
| Rejected | `rejected` | none |
| Duplicate Message-ID | response `duplicate` | no new row |

---

## Failure modes (honest)

| Failure | Operator action |
|---------|-----------------|
| Unknown recipient | Fix config address / slug |
| Signature 401 | Check secret and raw body HMAC |
| empty body + no extractable attach | Reject or re-send with content |
| auto_ingest error | Shown in detail; use manual **Создать заявку** |

---

## Success criteria

- [ ] Smoke script prints `OK request_id=REQ-…`
- [ ] UI list shows ingested row with request link
- [ ] No second PartRequest on double ingest
- [ ] Tenant B cannot see tenant A messages
