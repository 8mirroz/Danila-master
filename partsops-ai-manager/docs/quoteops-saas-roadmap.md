# PartsOps QuoteOps SaaS Roadmap

## Positioning

PartsOps is being commercialized as AI QuoteOps for parts distributors:

Unstructured RFQ -> recognized lines -> supplier offer matching -> controlled margin -> approved quote -> ERP/export.

The first commercial market is RF/CIS SMB distributors, with a global-ready architecture. The launch format is managed SaaS beta. The North Star is Automation Rate:

```text
Automation Rate = RFQ positions reaching Ready for Approval without manual search/edit / all valid RFQ positions
```

## Development Paths

| Path | Product | When to pursue |
| --- | --- | --- |
| QuoteOps SaaS | Distributor cockpit for RFQ processing and quote generation | Primary path now |
| Embedded Intelligence API | Matching, pricing and evidence API for ERP/DMS partners | After 10 active organizations or 3 partner requests |
| Supplier Marketplace | RFQ exchange and supplier offers inside PartsOps | After 20 active buyers and 100 connected suppliers |
| Vertical Editions | Separate editions for repair shops, fleets and special equipment | After distributor workflow is proven |

Current order: QuoteOps SaaS -> Embedded API -> Marketplace or vertical editions.

## Beta Packaging

| Plan | Monthly price | Included limits |
| --- | ---: | --- |
| Start | 19,900 RUB | 3 users, 500 processed positions, 5 supplier feeds, CSV/XLSX import, PDF/XLSX quote |
| Team | 39,900 RUB | 10 users, 2,000 processed positions, 25 feeds, approvals, ERPNext, extended audit |
| Extra pack | 7,500 RUB | Additional 500 processed positions |

Managed onboarding is a one-time 29,900-49,900 RUB service covering catalog import, column mapping, pricing policy and ERPNext setup. Beta starts with 14 days or 100 processed positions. Payment v1 is external B2B invoice plus manual subscription activation.

## Implemented SaaS Foundation Slice

This repository now has the first backend slice for managed SaaS beta:

- `Organization` maps the existing `tenant_id` boundary to a commercial organization.
- `User` and `Membership` model invitations and organization roles.
- `Subscription` stores trial/active/suspended state, beta plan limits and manual invoice metadata.
- `UsageEvent` is an idempotent ledger for accepted valid RFQ positions.
- `IntegrationConnection` and `OnboardingState` reserve tenant-scoped integration and onboarding state.
- `/api/organizations/current`, `/api/organizations/current/invitations`, `/api/billing/subscription`, `/api/billing/usage`, `/api/platform/subscriptions/{organization_id}/activate` and `/api/platform/subscriptions/{organization_id}/suspend` expose the managed beta control surface.
- New pipeline runs check subscription state and position quota before enqueueing; usage is recorded once per request idempotency key.
- Production authentication now requires Keycloak-compatible OIDC JWTs. The signed `organization_id` and `realm_access.roles` claims are the tenant and role source of truth; browser-supplied tenant/role headers are ignored. The master token is disabled for customer traffic and can only be enabled as a platform-admin migration escape hatch.

## Next 12-Week Execution Plan

Weeks 1-2:

- Keep pricing logic backend-owned and remove any remaining UI/backend price divergence.
- Define production environment, CI/CD, tenant metrics and three design partners.
- Collect 20-30 anonymized real RFQs per design partner.

Weeks 3-4:

- Replace browser tenant headers with OIDC/JWT-derived tenant and role claims.
- Add organization membership screens, platform-admin contour and cross-tenant security tests.
- Make PostgreSQL the only supported production database and keep SQLite for local/test.
- Move uploads/evidence to S3-compatible object storage with tenant-safe paths and SHA-256.

Weeks 5-6:

- Build RFQ inbox for manual, drag/drop, CSV/XLSX and inbound email.
  - Design (2026-08-09): `docs/design-rfq-inbound-email.md` (webhook + review-first inbox).
- Add reusable supplier feed mappings and importer preview.
- Make one backend pricing result the source of truth for UI, quote documents and ERP export.
- Generate versioned PDF/XLSX quotes with validity and change history.

Weeks 7-8:

- Finish trial states, quota UI, usage analytics and onboarding checklist.
- Add demo organization with safe data and guided first run.
- Track activation and Automation Rate at organization level.

Weeks 9-10:

- Register outbound dispatch for email, webhook and ERP with outbox, retry and DLQ.
- Add rate limits, PII retention, secret rotation, backup/restore drill and rollback.
- Add structured logs, tenant-aware metrics and Sentry-compatible errors.

Weeks 11-12:

- Run paid beta with 3 organizations.
- Import supplier feeds and pricing policies together with customers.
- Fix blockers in the core quote workflow only; do not start marketplace or vertical products.
- Make public launch decision from beta metrics.

## Release Gate

Commercial release is allowed only when:

- 3 organizations have paid for beta.
- At least 2 customers use the product repeatedly every week.
- Median Automation Rate reaches 50%.
- Gross margin after AI and storage costs is at least 70%.
- There are no known cross-tenant or financial P1 defects.
- Organization onboarding fits within two working days.
- A typical request can be completed without DB or shell access.

## Explicit Non-Goals For Beta

- Marketplace.
- Warehouse inventory.
- Mobile app.
- Complex forecasting.
- Full self-service payments.
- 1C/Odoo before confirmed demand.
