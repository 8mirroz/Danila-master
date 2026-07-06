# Supplier Workspace Implementation Plan

## Context

Source of truth checked:
- `partsops-ai-manager/06_UI/admin_cockpit/src/App.tsx`
- `partsops-ai-manager/06_UI/admin_cockpit/src/components/SuppliersPage.tsx`
- `partsops-ai-manager/06_UI/admin_cockpit/src/components/SupplierCards.tsx`
- `partsops-ai-manager/06_UI/admin_cockpit/src/components/SupplierDetailPage.tsx`
- `partsops-ai-manager/suppliers.py`
- `partsops-ai-manager/models.py`
- `DM obs/03-research/app-functional-description.md`
- `DM obs/06-agents/ui-premium-design-system.md`

## Current State

What exists now:
- supplier page is reachable from `admin_cockpit` via `activeNav === 'suppliers'`;
- list page renders supplier cards;
- detail page exists as fullscreen tabbed view;
- backend data model already has `Supplier`, `SupplierCatalogItem`, `SupplierReliabilityLog`, `PriceHistoryLedger`.

What is missing now:
- no real supplier CRUD flow in backend;
- no real supplier edit/settings workflow in UI;
- no dedicated supplier table management screen;
- no live table row inspection workflow for catalog positions;
- no supplier analytics API;
- no supplier activity log/audit API;
- current supplier page uses local mock data instead of live backend as primary source;
- current category/statistics/history tabs are demo-level placeholders.

## Target Product Scope

The supplier area should become a real operator workspace with 3 levels:

1. Supplier catalog screen
- searchable list/grid;
- status, freshness, SLA, risk, rating, table count;
- quick actions: add supplier, edit, archive, open tables, open analytics.

2. Supplier detail workspace
- profile and legal/contact data;
- operational settings;
- pricing/feed configuration;
- notes, internal comments, rating controls;
- history of changes and operational events.

3. Supplier tables sub-screen
- separate sub-screen inside supplier workspace;
- list of all uploaded tables/feeds for the supplier;
- live preview of rows and positions without opening Excel;
- import, replace, rename, deactivate, compare table versions;
- drill-down into a selected item row.

## UI Structure

### A. Catalog Page

Replace the current simple card wall with:
- top control bar: search, filters, `Add supplier`, `Import table`, `Needs review` toggle;
- segmented counters: active, pending verification, stale feeds, blocked suppliers;
- switchable views: cards and compact table;
- richer card/table columns: reliability, avg delivery, freshness, categories, active tables, last update, owner.

### B. Supplier Detail Workspace

Recommended tabs:
- `Overview`
- `Profile & Contacts`
- `Tables`
- `Analytics`
- `Logs & Audit`
- `Settings`

Overview should show:
- supplier health summary;
- rating and manual override;
- current active tables;
- recent changes;
- operational alerts: stale feed, low stock coverage, SLA drop, import failures.

### C. Tables Sub-screen

This is the key addition for the user's request.

Inside `Tables`:
- left pane: table/feed list with version, source, uploaded_at, row_count, freshness, status;
- center pane: preview grid for selected table;
- top actions: add table, upload new version, map columns, replace, disable, export, compare versions;
- row inspector drawer: part name, OEM, brand, price, stock, delivery, category, raw row payload.

### D. Analytics & Logs

Analytics:
- price coverage;
- reliability trend;
- delivery SLA trend;
- acceptance rate in matched offers;
- stale feed detection;
- average price delta vs median.

Logs:
- supplier created/updated;
- table uploaded/replaced/deactivated;
- manual rating changes;
- feed validation errors;
- import/mapping history;
- operator comments.

## Data Model Plan

### 1. Extend supplier master record

Current `Supplier` is too thin. Add fields such as:
- `status` (`active`, `pending`, `blocked`, `archived`);
- `rating_manual`;
- `rating_auto`;
- `account_owner`;
- `payment_terms`;
- `delivery_terms`;
- `currency_default`;
- `notes_internal`;
- `last_feed_at`;
- `last_sync_status`.

### 2. Add supplier table registry

New entity recommended: `SupplierTable`
- `table_id`
- `supplier_id`
- `name`
- `source_type` (`excel`, `csv`, `api`, `manual`)
- `filename`
- `version`
- `status`
- `uploaded_at`
- `uploaded_by`
- `row_count`
- `mapped_columns_json`
- `validation_summary_json`
- `is_active`

### 3. Add per-row storage for live preview

Recommended entity: `SupplierTableRow`
- `table_id`
- `row_key`
- `part_name`
- `oem_number`
- `brand`
- `price`
- `currency`
- `stock_qty`
- `delivery_days`
- `category`
- `raw_payload_json`

If volume grows later, this can be moved to a dedicated ingestion store, but for MVP the SQLModel path is acceptable.

### 4. Add operational log table

Recommended entity: `SupplierActivityLog`
- `event_id`
- `supplier_id`
- `table_id` optional
- `event_type`
- `actor_id`
- `payload_json`
- `created_at`

### 5. Keep current intelligence tables

Reuse:
- `SupplierReliabilityLog`
- `PriceHistoryLedger`

These should feed the new analytics tab instead of remaining backend-only data.

## Backend/API Plan

### Phase 1 API: Supplier CRUD

- `GET /api/suppliers`
- `POST /api/suppliers`
- `GET /api/suppliers/{supplier_id}`
- `PATCH /api/suppliers/{supplier_id}`
- `POST /api/suppliers/{supplier_id}/archive`
- `POST /api/suppliers/{supplier_id}/rating`

### Phase 2 API: Supplier tables

- `GET /api/suppliers/{supplier_id}/tables`
- `POST /api/suppliers/{supplier_id}/tables`
- `GET /api/suppliers/{supplier_id}/tables/{table_id}`
- `PATCH /api/suppliers/{supplier_id}/tables/{table_id}`
- `POST /api/suppliers/{supplier_id}/tables/{table_id}/activate`
- `POST /api/suppliers/{supplier_id}/tables/{table_id}/replace`
- `GET /api/suppliers/{supplier_id}/tables/{table_id}/rows`
- `GET /api/suppliers/{supplier_id}/tables/{table_id}/rows/{row_key}`

### Phase 3 API: Analytics and logs

- `GET /api/suppliers/{supplier_id}/analytics`
- `GET /api/suppliers/{supplier_id}/logs`
- `GET /api/suppliers/{supplier_id}/reliability-history`
- `GET /api/suppliers/{supplier_id}/price-history`

### Phase 4 API: Import pipeline

- upload artifact;
- parse spreadsheet;
- preview columns;
- confirm mapping;
- persist rows into `SupplierTableRow`;
- write validation + activity log;
- optionally mark as active table version.

## Frontend Implementation Plan

### Phase 1. Replace mock-only supplier page with live data

Tasks:
- move `SuppliersPage` from local mock data to `apiJson`;
- create supplier DTOs and loading/error/empty states;
- keep current fullscreen detail pattern, but wire it to real selected supplier data.

Definition of done:
- supplier catalog loads from backend;
- no primary dependency on local mocks;
- stale/empty/error states are explicit.

### Phase 2. Add supplier management flows

Tasks:
- add `Add supplier` modal/drawer;
- add `Edit supplier` flow from detail header;
- add status/rating/settings editing;
- add optimistic refresh or invalidation after save.

Definition of done:
- operator can create and edit a supplier without touching code or DB;
- rating and status changes are stored and visible immediately.

### Phase 3. Build the Tables sub-screen

Tasks:
- add `Tables` tab in `SupplierDetailPage`;
- implement table list + row preview grid + row detail drawer;
- add upload/replace/version actions;
- add filter/search by OEM, brand, part name.

Definition of done:
- operator can inspect any supplier table row live in UI without opening Excel;
- operator can add a new table and replace an existing version.

### Phase 4. Add analytics and logs

Tasks:
- replace placeholder `Statistics` and `History` tabs with backend-driven analytics/logs;
- surface reliability trend, feed freshness, row coverage, import failures, rating events;
- add warning banners for stale or invalid feeds.

Definition of done:
- supplier screen explains health, changes, and risk;
- analytics and logs come from backend, not demo constants.

### Phase 5. UX hardening

Tasks:
- compact operator-friendly layout;
- consistent action hierarchy;
- bulk actions for table/version management;
- state badges: `loading`, `empty`, `stale`, `blocked`, `syncing`, `invalid mapping`.

Definition of done:
- supplier workspace feels like an operator control plane, not a demo showcase.

## Recommended Delivery Order

1. Backend supplier CRUD + live UI fetch.
2. Supplier detail editing.
3. Supplier table registry + row preview APIs.
4. Tables sub-screen in UI.
5. Supplier analytics/logs.
6. Import mapping and version comparison polish.

## Risks

- current `main.py` state is unstable and should be normalized before expanding API surface;
- existing supplier UI components are ahead of backend contract and will drift further if CRUD is added ad hoc;
- spreadsheet ingestion can balloon scope if column mapping and versioning are not constrained in MVP;
- row preview performance may degrade if all spreadsheet rows are loaded at once, so pagination is required from the start.

## MVP Boundary

Recommended MVP:
- create supplier;
- edit supplier profile/settings/rating;
- upload one or more tables per supplier;
- preview rows in UI;
- replace/activate table versions;
- basic analytics;
- supplier activity log.

Not required in MVP:
- full spreadsheet formula engine;
- Excel-like inline editing for every cell;
- complex BI dashboards;
- automatic reconciliation across multiple supplier versions.

## Validation Plan

Backend:
- add API tests for supplier CRUD;
- add API tests for supplier tables and row preview;
- add tests for rating/log creation and activity history.

Frontend:
- `npm run lint`
- `npm run build`

Manual:
- create supplier;
- edit supplier;
- upload table;
- open table preview;
- inspect row;
- change rating;
- verify analytics/log surfaces update.
