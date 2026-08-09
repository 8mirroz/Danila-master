# Design Partner Gate — ERPNext + S3/Object Storage

**Дата:** 2026-08-08  
**Назначение:** закрыть open items из `docs/beta-readiness.md` перед подключением design partners.  
**Не путать с:** loopback staging proofs (`verify_staging_erp_dlq.py`, MinIO bootstrap).

---

## 0. Preconditions

| Check | Command / evidence |
|-------|-------------------|
| `PARTSOPS_ENV=production` or dedicated partner staging | env dump redacted |
| PostgreSQL only (no SQLite) | `DATABASE_URL` starts with `postgresql` |
| OIDC required for customer traffic | Keycloak realm + org claim verified |
| `TESTING=0`, `SEED_ON_START=0` | env |
| `ERP_DRY_RUN=0` only after health OK | env |
| Strong secrets rotated if ever leaked via compose config | incident log |

Local anti-stub hardening (2026-08-08) is code-complete; this document is **ops evidence**, not more silent fakes.

---

## 1. S3-compatible production storage

### 1.1 Provision

- [ ] Dedicated bucket (not shared MinIO bootstrap from docker staging)
- [ ] Least-privilege IAM / access key (upload + get + delete only under tenant prefix)
- [ ] Server-side encryption enabled (SSE-S3 or SSE-KMS)
- [ ] Versioning **or** documented retention lifecycle
- [ ] Block public ACLs / public policy
- [ ] CORS only if browser direct upload is used (prefer server-side)

### 1.2 App config

Set (names as used by PartsOps storage layer / `.env.example`):

```bash
PARTSOPS_STORAGE_BACKEND=s3   # or project-specific key
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=...
S3_BUCKET=...
S3_ENDPOINT_URL=...           # if MinIO/R2/Yandex
# optional path prefix
S3_KEY_PREFIX=partsops/
```

Confirm no secrets in `VITE_*` variables.

### 1.3 Drill (capture output)

```bash
# Against the partner/staging stack with real bucket credentials injected by the platform:
python scripts/verify_staging_s3_storage.py
```

Required evidence:

- [ ] Upload succeeds
- [ ] Tenant metadata / path isolation visible in object key
- [ ] SHA-256 materialization matches
- [ ] Cleanup removes temporary object
- [ ] Lifecycle / retention policy document linked (PDF or console screenshot + date)

**Release rule:** local MinIO proof from 2026-08-01 is **not** sufficient for paid partners.

---

## 2. ERPNext authorized connector

### 2.1 Preflight (read-only)

As organization admin:

```http
GET /api/erp/connection-health
```

Eligible only if:

```json
{"status": "connected", "dry_run": false}
```

Blockers (do **not** treat as success):

| status | Meaning |
|--------|---------|
| `not_configured` | missing URL |
| `credentials_missing` | missing API key/secret |
| `unreachable` | network/DNS |
| `authentication_failed` | bad credentials |
| `unexpected_response` | non-ERP surface |

### 2.2 Config

```bash
ERPNEXT_URL=https://erp.partner-or-sandbox.example
ERPNEXT_API_KEY=...
ERPNEXT_API_SECRET=...
ERP_DRY_RUN=0
ERP_WEBHOOK_SECRET=<persistent-random-32+>
PARTSOPS_ENV=production   # or partner staging with dry_run=0 only when intentional
```

- [ ] Sandbox/site is **authorized** by the partner (written OK)
- [ ] Scoped API user (Sales Invoice / Customer only — no System Manager if avoidable)
- [ ] Idempotency keys preserved on retry

### 2.3 Transport + DLQ drill

```bash
# First: health must be connected + dry_run false
# Then prove retry/DLQ against authorized non-prod endpoint (not only loopback mock):
python scripts/verify_staging_erp_dlq.py
```

Plus one **happy-path** invoice draft:

1. Create RFQ → READY_FOR_APPROVAL → finance approve → quote snapshot  
2. Trigger ERP sync job / `POST` ERP sync for that request  
3. Confirm ERP document name stored and `ERPSyncLog.status=SUCCESS` only after real HTTP success  
4. Confirm PO local drafts stay `LOCAL_DRAFT` until real PO API exists  

### 2.4 Honesty rules (code, 2026-08-08)

| Component | Behavior |
|-----------|----------|
| `po_create_job` | `LOCAL_DRAFT`, never silent SUCCESS |
| `erp_hub_engine` | routes to connector only with session+request_id |
| `erp_connector_engine` | dry-run → `synced=False`, status partial |
| Cockpit ERP KPI | OK / Сбой / н/д — no fake 100% |

---

## 3. End-to-end partner smoke (one organization)

```bash
bash scripts/verify_staging_quoteops.sh   # or partner-equivalent
bash scripts/verify_staging_security.sh
bash scripts/verify_staging_worker_recovery.sh
bash scripts/verify_beta_staging.sh
```

- [ ] JWT org boundary holds  
- [ ] Quota concurrency gate  
- [ ] Quote PDF/XLSX download  
- [ ] Worker restart without lost pipeline events  

---

## 4. Sign-off template

```text
Partner: _______________
Date: _______________
S3 drill log: _______________
ERP health JSON: _______________
ERP invoice doc name: _______________
DLQ drill log: _______________
Operator: _______________
PO decision: GO / NO-GO
```

**NO-GO if any:** cross-tenant leak, ERP SUCCESS without document, public portal shows margin/match_score, seed/demo data in partner DB.

---

## 5. Related scripts

| Script | Role |
|--------|------|
| `scripts/verify_staging_s3_storage.py` | object storage |
| `scripts/verify_staging_erp_dlq.py` | ERP retry/DLQ transport |
| `scripts/verify_staging_quoteops.sh` | full QuoteOps workflow |
| `scripts/verify_staging_security.sh` | tenant + upload + hash chain |
| `scripts/verify_beta_staging.sh` | gate wrapper |
| `docs/beta-readiness.md` | master release gate |

---

*Generated as residual of stubs audit execution 2026-08-08.*
