# QuoteOps managed beta — release evidence

This document is a release gate, not a feature wish list. A checked item needs
current command output or a production-like run linked from the release record.

## Implemented and locally verified

- [x] Tenant-scoped organizations, subscriptions, memberships and idempotent
  valid-position usage.
- [x] Production configuration rejects SQLite and legacy authentication; OIDC
  claims derive the organization boundary.
- [x] RFQ CSV/XLSX intake supports preview, reusable column mappings and an
  idempotent request creation command.
- [x] Quote records retain immutable pricing/selected-offer revisions and
  provide PDF/XLSX downloads.
- [x] S3-compatible storage can persist canonical tenant-safe object URIs and
  materialize a parser cache; the local backend remains the dev/test default.
- [x] Outbound webhooks use the outbox and a signed HTTPS envelope.
- [x] Local staging injects only application configuration into backend and
  worker containers; Keycloak, MinIO and PostgreSQL bootstrap passwords are
  not exposed as standalone application environment variables.
- [x] CI validates the SaaS/API test slice, migrations and cockpit lint/build.

## Required before connecting design partners

If a compose config or terminal log has ever rendered `.env.staging`, rotate
every exposed database, Keycloak, MinIO, ERP and webhook credential before the
next deployment. Do not use `docker compose config` without redaction in a
shared terminal.

For the local staging compose stack, `.env.staging` must also contain fresh
`POSTGRES_PASSWORD`, `KEYCLOAK_ADMIN`, `KEYCLOAK_ADMIN_PASSWORD`,
`MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`. `scripts/start_staging.sh` checks
this without starting containers; it does not source the file.

If Docker Desktop's credential helper is unavailable, run the launcher with an
isolated Docker config and `PARTSOPS_DOCKER_COMPOSE=docker-compose`; this avoids
changing the user's global Docker login configuration.

Run `scripts/verify_beta_staging.sh` with production secrets injected by the
deployment platform. The script rejects local storage, legacy auth and SQLite
before applying migrations; `PARTSOPS_STAGING_HEALTH_URL` additionally proves
the deployed health endpoint.

For a local cockpit against the Docker OIDC stack, copy
`06_UI/admin_cockpit/.env.staging.example` to `.env.staging` in that frontend
directory and run `npm run dev -- --mode staging`. These are public browser
settings only; never place Keycloak, MinIO, database or ERP secrets in a
`VITE_*` variable.

The staging compose stack starts `pipeline-worker-staging` separately after
migrations. Its process state and replay of a queued pipeline run must be
captured as part of the worker-restart release gate below.

- [x] Provision Keycloak and record the issuer, audience, organization claim,
  role claim and a successful signed JWT request against staging. On
  2026-08-01 the local Docker staging stack verified issuer
  `http://localhost:8080/realms/partsops`, audience `partsops-api`, the
  `organization_id` claim, the realm role claim, platform provisioning and an
  authenticated customer `GET /api/session`. The temporary proof organization
  and Keycloak users were removed and direct password grants were restored to
  disabled. Each managed user must have an admin-controlled `organization_id`
  attribute; the imported realm maps it into the access token.
- [x] Run the PostgreSQL quota-reservation gate. On 2026-08-01
  `python scripts/verify_staging_quota_concurrency.py` ran inside the staging
  backend container: two concurrent runs with one billable position resulted
  in exactly one acceptance, one quota rejection and one usage event. The
  verifier self-cleans its temporary organization. The remaining full quote
  workflow gate is tracked with the end-to-end release checks below.
- [ ] Configure the S3-compatible production bucket, credentials, lifecycle
  retention and signed-access policy, then capture an upload/restore drill.
  Local staging storage was proven on 2026-08-01 with
  `python scripts/verify_staging_s3_storage.py` inside `backend-staging`:
  upload, tenant metadata, materialization/SHA-256 and cleanup all passed.
  The staging backend deliberately derives credentials from its isolated
  MinIO bootstrap account; production must use a separate least-privilege
  bucket credential and documented retention/access policies.
- [ ] Provision the ERPNext connector with scoped credentials and prove an
  outbox retry/DLQ run against an authorized non-production endpoint. On
  2026-08-01 `python scripts/verify_staging_erp_dlq.py` proved the adapter's
  actual HTTP retry path against a controlled in-container failure endpoint:
  three attempts, one idempotent record and one DLQ entry, with all temporary
  database rows removed afterward. This is transport/DLQ evidence only; the
  configured external endpoint is loopback and is not represented as an
  authorized ERPNext integration.
- [x] Perform backup/restore into a clean environment and a worker-restart run
  without losing a durable pipeline event. On 2026-08-01
  `bash scripts/verify_staging_worker_recovery.sh` reclaimed an expired lease
  after an actual worker stop/start; its three persisted events remained
  replayable and the run reached a released terminal state. The verifier
  removes its temporary records. `bash scripts/verify_staging_backup_restore.sh`
  also restored a custom logical dump into a separate clean PostgreSQL
  container and matched the schema revision and control data before deleting
  the temporary container and volume.
- [x] Execute cross-tenant, signed-upload and audit-immutability security tests
  in the staging deployment. On 2026-08-01
  `bash scripts/verify_staging_security.sh` used real temporary Keycloak JWTs
  for two organizations: cross-tenant request access and artifact import were
  rejected, a valid CSV upload was stored tenant-scoped, and a controlled
  database tamper was detected by the event hash-chain. The script removes its
  IdP users, database records and S3 object, and restores direct password
  grants to disabled.

## Release decision inputs

The beta is eligible for paid design partners only when three organizations are
provisioned, onboarding can be completed within two working days, and the
product owner has captured a baseline for Automation Rate, time-to-quote and
AI/storage gross margin. Marketplace, inventory and additional ERP connectors
remain explicitly out of this gate.
