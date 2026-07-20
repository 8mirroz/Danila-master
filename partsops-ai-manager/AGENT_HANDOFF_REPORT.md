# PartsOps AI Manager — Handoff Report

**Snapshot date:** 2026-07-08  
**Scope:** `partsops-ai-manager` only.  
**Note:** this worktree is dirty and already contains pre-existing local edits in backend and UI files. This report documents the current live tree, not a clean branch.

## 1. Executive Summary

`partsops-ai-manager` is a FastAPI control plane for auto-parts intake, supplier matching, pricing, approval, ERP sync, delivery, and audit. It has two UI surfaces:

- `06_UI/admin_cockpit`: primary operator cockpit.
- `06_UI/client_portal`: public tracking/accept-reject portal.

The backend is event-sourced, tenant-scoped, and state-machine driven. The core path is:

1. Intake a request or file artifact.
2. Mask PII before agent/LLM processing.
3. Extract vehicle and part intent.
4. Match supplier catalog items.
5. Calculate price and enforce margin/evidence gates.
6. Route for approval, ERP draft generation, delivery, and client portal actions.
7. Persist every significant step in the append-only event store.

There are also automation jobs, LLM observability, and a learning loop with golden samples.

## 2. Current Shape of the App

The project is not a single monolith anymore, but it is still unevenly split between old and new control paths:

- Legacy path:
  - `agents.py`
  - `agent_orchestrator.py`
  - `process_intake_request(...)` from `agents.py`
- Newer pipeline package:
  - `app/agents/*`
  - `app/automation/*`

The new pipeline is used by `/api/pipeline/run`, while the request service still uses the legacy intake function in some paths. That coexistence is the main architectural fact to keep in mind.

## 3. Main Runtime and Data Flow

### Request intake

- `POST /api/requests` creates a `PartRequest`.
- `RequestService.create_request(...)` does:
  - PII pre-parse via `pii.secure_pre_parse(...)`
  - legacy intake parsing via `process_intake_request(...)`
  - masked persistence of customer and VIN fields
  - event emission: `REQUEST_RECEIVED`, `PART_INTENT_EXTRACTED`, `STATE_CHANGED`

### File intake

- `POST /api/attachments/upload` stores an uploaded artifact in `08_DATA/uploads/<tenant>/...`.
- `POST /api/requests/import-from-artifact` parses uploaded CSV/XLSX/JSON/TXT files and turns them into a request.
- `UploadArtifact` keeps file metadata, hash, and status.

### Matching and pricing

- `matcher.match_part_from_db(...)` does weighted fuzzy matching against `SupplierCatalogItem`.
- `pricing.compute_price(...)` calculates sale price, tax, buffers, and anomaly flags.
- `policy_engine.EvidenceGates` checks:
  - PII safety
  - event-chain validity
  - match confidence
  - pricing policy
  - approval presence
  - delivery safety
  - ERP sync readiness

### Approval and ERP

- `/api/requests/{request_id}/approve` can approve or reject a request and then continue the pipeline.
- `/api/erp/invoice/{request_id}` creates a draft invoice only when the request is already `APPROVED`.

### Delivery and client portal

- `delivery.InvoicePDFGenerator` renders invoice PDFs.
- `delivery.EmailAdapter` and `delivery.TelegramAdapter` queue outbound messages in `OutboundMessage`.
- `client_portal.py` manages public tracking tokens and accept/reject actions.

### Audit and observability

- `event_store.py` writes append-only events with a tenant-scoped SHA-256 hash chain.
- `routers/observability.py` exposes traces, cost metrics, accuracy, and SSE updates.

## 4. Backend Architecture

### App wiring

- `main.py`:
  - loads env vars
  - initializes DB and seeds suppliers during lifespan
  - wires CORS
  - mounts routers
  - serves the health endpoint
- Health response still says `phase: "Phase 1 — Runtime Foundation"`, which should be treated as a generic banner, not the true maturity level of the repo.

### Core platform modules

- `database.py`:
  - builds the SQLModel engine
  - supports SQLite and Postgres
  - creates sessions
- `settings.py`:
  - `DATABASE_URL`
  - `TESTING`
  - upload validation knobs
  - upload directory
- `rbac.py`:
  - tenant and role resolution
  - bearer token handling
  - dev-mode fallback when `PARTSOPS_API_TOKEN` is not set
- `state_machine.py`:
  - validates transitions
  - enforces invariants for invoice/client/paid/closed states
- `event_store.py`:
  - inserts immutable events
  - verifies the hash chain
- `policy_engine.py`:
  - bundles transition, tool permission, and evidence gates

### Domain helpers

- `pii.py`:
  - masks phone, email, VIN, and name
  - `secure_pre_parse(...)` extracts masked text and a vehicle context
- `matcher.py`:
  - RapidFuzz-based matching plus weighted scoring
- `pricing.py`:
  - margin policy, tax, risk buffers, anomaly detection
- `intelligence.py`:
  - 90-day median prices
  - supplier reliability updates
  - return risk assessment
- `learning.py`:
  - golden sample storage
  - system accuracy calculation
- `llm.py`:
  - provider chain for NIM / OpenRouter / LM Studio / Ollama / mock
  - budget and model routing via `budget_guard`

## 5. Data Model

### Request and audit entities

| Model | Purpose |
|---|---|
| `PartRequest` | Main request record, status, customer, vehicle, parts, ERP refs, tracking token |
| `RequestEvent` | Append-only event log with hash chain |
| `MatchEvidence` | Per-part matching evidence and scores |
| `ERPSyncLog` | ERP sync attempt log |
| `GoldenSample` | Human-corrected training sample |
| `UploadArtifact` | File upload artifact metadata |
| `RequestScore` | Aggregated scoring for dashboards/jobs |
| `ApprovalTicket` | Human approval queue record |
| `OutboundMessage` | Outbox record for email/telegram/webhook delivery |
| `LLMUsageLog` | Token/cost/latency observability |
| `JobRun` | Automation audit log |
| `AutomationLock` | TTL-based named lock |

### Supplier entities

| Model | Purpose |
|---|---|
| `Supplier` | Supplier master record |
| `SupplierCatalogItem` | Individual part offer |
| `SupplierTable` | Imported supplier table/version |
| `SupplierTableRow` | Rows inside an imported table |
| `SupplierActivityLog` | Supplier audit log |
| `Invoice` | Draft ERP invoice |
| `PriceHistoryLedger` | Historical price points |
| `SupplierReliabilityLog` | Reliability history |

### State machine

The request lifecycle includes intake, matching, approval, ERP, delivery, closure, and fallback states. Important invariants:

- `INVOICE_DRAFTED` requires pricing evidence, ERP quotation ref, and passing margin policy.
- `SENT_TO_CLIENT` requires `erp_invoice_ref`.
- `PAID` requires `erp_payment_ref`.
- `CLOSED` requires `audit_chain_complete=True`.

## 6. API Surface

### Routers mounted in `main.py`

| Router | Prefix | Notes |
|---|---|---|
| `routers/requests.py` | `/api` | Requests, uploads, pipeline, approval, client portal, delivery helpers |
| `routers/suppliers.py` | `/api/suppliers` | Supplier CRUD, tables, imports, rows, analytics, logs |
| `routers/observability.py` | `/api` | LLM traces, costs, accuracy, SSE |
| `routers/chat.py` | `/api/v1/chat` | Chat completions via the LLM layer |
| `routers/erp.py` | `/api/erp` | Invoice generation |
| `routers/catalog.py` | `/api/catalog` | Catalog search |

### Important request routes

| Route | Purpose |
|---|---|
| `GET /api/requests` | List requests |
| `GET /api/requests/{id}` | Fetch request |
| `POST /api/requests` | Create request |
| `POST /api/requests/{id}/transition` | Manual state transition |
| `POST /api/requests/{id}/correction` | Save manual correction to golden dataset |
| `GET /api/requests/{id}/events` | Event list |
| `GET /api/requests/{id}/audit` | Hash-chain verification |
| `GET /api/requests/{id}/gates` | Evidence gates |
| `POST /api/pipeline/run` | Full multi-agent pipeline |
| `POST /api/pipeline/continue/{request_id}` | Continue from a later phase |
| `GET /api/pipeline/status/{request_id}` | Pipeline status view |
| `POST /api/requests/{id}/approve` | Approve or reject after manual review |
| `GET /api/delivery/status/{request_id}` | Delivery log view |
| `GET /api/delivery/invoice/{request_id}/pdf` | Invoice PDF |
| `POST /api/delivery/send/{request_id}` | Send invoice via email/telegram |
| `POST /api/requests/{id}/generate-tracking-token` | Create public client portal token |
| `GET /api/client/track/{token}` | Public request view |
| `POST /api/client/track/{token}/accept` | Client accepts offer |
| `POST /api/client/track/{token}/reject` | Client rejects offer |

### Important supplier routes

| Route | Purpose |
|---|---|
| `GET /api/suppliers` | List suppliers |
| `POST /api/suppliers` | Create supplier |
| `PATCH /api/suppliers/{id}` | Update supplier |
| `POST /api/suppliers/{id}/archive` | Archive supplier |
| `GET /api/suppliers/{id}/tables` | List tables |
| `POST /api/suppliers/{id}/tables/import` | Import file into supplier tables |
| `GET /api/suppliers/{id}/tables/{table_id}/rows` | Table rows |
| `PATCH /api/suppliers/{id}/tables/{table_id}/rows/{row_key}` | Row edit |
| `POST /api/suppliers/{id}/tables/{table_id}/rows/bulk-update` | Bulk row update |
| `GET /api/suppliers/{id}/analytics` | Supplier analytics |
| `GET /api/suppliers/{id}/logs` | Supplier logs |
| `GET /api/suppliers/{id}/reliability-history` | Reliability history |
| `GET /api/suppliers/{id}/price-history` | Price history |

## 7. Agent System

### Legacy stack

- `agents.py` implements the older LangGraph-style intake graph.
- `agent_orchestrator.py` is a thin wrapper around `process_intake_request(...)`.
- `RequestService.create_request(...)` still uses that legacy intake function.

### New stack

`app/agents/` contains the newer pipeline:

- `base_agent.py`
- `intake_agent.py`
- `processing_agent.py`
- `delivery_agent.py`
- `reporting_agent.py`
- `orchestrator.py`

Pipeline order:

1. Intake
2. Processing
3. Delivery
4. Reporting

### What each agent does

- `IntakeAgent`:
  - parses source-specific input
  - masks PII
  - creates the request record
  - emits the initial event
- `ProcessingAgent`:
  - matches parts
  - computes pricing
  - applies gates
  - creates approval tickets when needed
- `DeliveryAgent`:
  - creates outbound messages
  - chooses email / telegram / download / webhook
  - updates request state
- `ReportingAgent`:
  - sends operator/client notifications
  - writes summary events
  - finalizes status

### Automation registry

- `app/automation/registry.py` registers **25 jobs**.
- `app/automation/runner.py` runs jobs and pipelines with dry-run support, short transactions, and event emission.
- `app/automation/context.py` carries tenant, actor, dry-run, correlation id, and payload.

Important job groups:

- intake: collect / dedupe / validate / VIN / extract intent
- quote: collect / evaluate / policy check
- supplier: match / validate / recalc
- ERP: sync / retry
- lifecycle: auto-advance / archive-close / stalled escalation / SLA watchdog
- observability: metrics refresh / price snapshot / golden regression
- notification: notify owner

### Current automation gap

- `app/automation/jobs/outbound_dispatch_job.py` exists in the worktree and implements outbox dispatch with retry/backoff.
- It is **not yet registered** in `app/automation/registry.py`.

## 8. Frontend Surfaces

### Admin cockpit (`06_UI/admin_cockpit`)

Stack:

- React 19
- Vite 8
- TypeScript 6
- Tailwind
- FontAwesome

Core UX:

- top command bar with global search
- left navigation rail
- right queue rail
- request workspace
- supplier workspace
- kanban board
- pipeline monitor
- multi-agent orchestra
- agent OS panel
- audit timeline
- invoice preview
- evidence gates
- LLM cost dashboard

Key behavior:

- `apiFetch(...)` injects token and tenant headers from env vars.
- SSE listener watches `/api/events/stream`.
- Request selection drives matching/pricing/audit flows.
- `Cmd+K` opens the command palette.

Important components currently wired into the shell:

- `RightPanel`
- `SupplierMatrix`
- `PricingCalculator`
- `AuditTimeline`
- `CompletedOrdersHistory`
- `EvidenceGatesWidget`
- `InvoicePreview`
- `LLMCostPanel`
- `PipelineMonitor`
- `AgentOSPanel`
- `MultiAgentOrchestraView`
- `CommandPalette`

### Client portal (`06_UI/client_portal`)

Stack:

- React 17
- Vite 1
- React Router

Routes:

- `/track/:token`
- `/offer/:token`
- `/offer/:token/accept`
- `/offer/:token/reject`

Behavior:

- bare `fetch(...)` calls the public portal API
- shows public request status, part list, and accept/reject actions
- intentionally simpler than the operator cockpit

### Separate scaffold

- `partsops_agent_os_devpack/05_FRONTEND` is a separate Agent OS scaffold, not the main product UI.

## 9. Runtime, Storage, and Deployment

### Environment and config

Relevant env vars:

- `DATABASE_URL`
- `PARTSOPS_API_TOKEN`
- `PARTSOPS_CORS_ORIGINS`
- `TESTING`
- `MAX_UPLOAD_SIZE_MB`
- `UPLOAD_ALLOWED_EXTENSIONS`
- `UPLOAD_DIR`
- `ENABLE_STRICT_UPLOAD_VALIDATION`
- `ENABLE_STRICT_TENANT_ENFORCEMENT`
- LLM provider vars:
  - `NVIDIA_API_KEY`
  - `OPENROUTER_API_KEY`
  - `LM_STUDIO_URL`
  - `OLLAMA_ENABLED`

### Storage

- Uploads are written to `08_DATA/uploads/<tenant>/`.
- `LocalFileStorage` enforces:
  - tenant-safe paths
  - extension allowlist
  - magic-byte validation
  - max file size
  - SHA-256 hashing

### Deployment files

- `docker-compose.yml` runs backend + frontend + optional Postgres.
- `Dockerfile.backend` expects `requirements.txt`.
- `Dockerfile.frontend` builds the admin cockpit.
- `start.sh` launches backend on port 8000 and frontend on port 3000.

### Important runtime mismatch

- `requirements.txt` is **missing** from `partsops-ai-manager/`, but `Dockerfile.backend` still copies and installs it.
- That makes the backend Docker build path inconsistent in the current tree.
- `start.sh` uses port 3000, while the cockpit tooling and CORS defaults are centered on 5173/5174/5176/4173.

## 10. Testing and Validation

### Test inventory

- There are **19 test files** under `partsops-ai-manager/tests/`.
- The suite covers:
  - API
  - RBAC isolation
  - PII masking
  - secure upload
  - tamper detection
  - matcher
  - pricing
  - intelligence
  - learning
  - observability
  - ERP adapter
  - delivery safety
  - Postgres integration
  - control-plane readiness
  - pipeline integration

### Important integration coverage

`tests/test_pipeline_integration.py` exercises:

- full pipeline run
- approval and continuation
- reject flow
- client portal tracking token creation
- client accept/reject flows
- delivery logs

### UI testing

- `06_UI/admin_cockpit/tests/` contains Playwright specs and debug cases.

### What was not executed here

- I did not run the app or the test suite while producing this report.
- The report is based on source inspection of the current tree plus existing audit docs in the repo.

## 11. Current Risks / Gaps

| Risk | Why it matters |
|---|---|
| Missing `requirements.txt` with a backend Dockerfile reference | Dockerized backend build will fail unless this is fixed or the Dockerfile is updated |
| Dual agent stacks (legacy + new) | Easy to change one path and miss the other |
| `outbound_dispatch_job.py` not registered | Outbox dispatch looks present but is not yet part of the automation registry |
| `start.sh` port mismatch | Confusing local dev startup and UI access |
| Health endpoint still says Phase 1 | Status banner is stale relative to the current feature set |
| Worktree already has local edits | A new agent should avoid clobbering in-progress changes |

## 12. Handoff Notes for the Next Agent

If you need to modify behavior safely, start here:

1. Prefer `routers/` and `services/` over `main.py`.
2. Keep `tenant_id` on every query and every stateful action.
3. Never bypass `state_machine.validate_transition(...)`.
4. Close DB transactions before LLM or external HTTP calls.
5. Use the outbox pattern for outbound messages.
6. Mask PII before logging or sending data to agent/LLM code.
7. Treat the admin cockpit as the main operator workspace, not a generic dashboard.
8. Treat the client portal as a public, token-based surface with reduced data exposure.

## 13. Useful Paths

- Backend entrypoint: `partsops-ai-manager/main.py`
- Models: `partsops-ai-manager/models.py`
- RBAC: `partsops-ai-manager/rbac.py`
- State machine: `partsops-ai-manager/state_machine.py`
- Event store: `partsops-ai-manager/event_store.py`
- Pricing: `partsops-ai-manager/pricing.py`
- Matching: `partsops-ai-manager/matcher.py`
- PII: `partsops-ai-manager/pii.py`
- Client portal: `partsops-ai-manager/client_portal.py`
- Delivery: `partsops-ai-manager/delivery.py`
- ERP adapter: `partsops-ai-manager/erp_adapter.py`
- Request service: `partsops-ai-manager/services/request_service.py`
- Supplier service: `partsops-ai-manager/services/supplier_service.py`
- Automation registry: `partsops-ai-manager/app/automation/registry.py`
- Admin cockpit entrypoint: `partsops-ai-manager/06_UI/admin_cockpit/src/App.tsx`
- Client portal entrypoint: `partsops-ai-manager/06_UI/client_portal/src/App.tsx`

