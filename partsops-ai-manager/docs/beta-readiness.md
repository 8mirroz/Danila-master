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

Run `scripts/verify_beta_staging.sh` with production secrets injected by the
deployment platform. The script rejects local storage, legacy auth and SQLite
before applying migrations; `PARTSOPS_STAGING_HEALTH_URL` additionally proves
the deployed health endpoint.

The staging compose stack starts `pipeline-worker-staging` separately after
migrations. Its process state and replay of a queued pipeline run must be
captured as part of the worker-restart release gate below.

- [ ] Provision Keycloak and record the issuer, audience, organization claim,
  role claim and a successful signed JWT request against staging. Each user
  must have an `organization_id` user attribute; the imported realm maps it
  into the access token.
- [ ] Run the full workflow against production-like PostgreSQL, including a
  concurrent quota-reservation test.
- [ ] Configure the S3-compatible production bucket, credentials, lifecycle
  retention and signed-access policy, then capture an upload/restore drill.
- [ ] Provision the ERPNext connector with scoped credentials and prove an
  outbox retry/DLQ run against an authorized non-production endpoint.
- [ ] Perform backup/restore into a clean environment and a worker-restart run
  without losing a durable pipeline event.
- [ ] Execute cross-tenant, signed-upload and audit-immutability security tests
  in the staging deployment.

## Release decision inputs

The beta is eligible for paid design partners only when three organizations are
provisioned, onboarding can be completed within two working days, and the
product owner has captured a baseline for Automation Rate, time-to-quote and
AI/storage gross margin. Marketplace, inventory and additional ERP connectors
remain explicitly out of this gate.
