# Stubs Audit Execution — 2026-08-08

**Источник плана:** session plan.md (аудит заглушек)  
**Статус:** Wave A–E code path executed (infra-only gates documented)

---

## Closed in code

| ID | Change |
|----|--------|
| **U-SM** | `SmartMatchCards.tsx` — empty state, no fake Brembo/Bosch/TRW offers |
| **B-PO** | `po_create_job` → `LOCAL_DRAFT`, never SUCCESS without ERP; sync_id set |
| **E-VND** | `vendor_query_engine` → catalog match via `match_part_from_db` when session+query |
| **E-HUB** | `erp_hub_engine` → thin route to `sync_erp` when session+request_id |
| **L-INT** | Single facade `app.agents.intake_facade.parse_intake_text`; RequestService, routers, IntakeAgent, agent_orchestrator, agents shim |
| **B-BOT** | TLS default secure; tenant from config; no default `test-token` |
| **DOC-PHASE** | `PHASE_LABEL` default → Phase 2 — QuoteOps Beta Hardening |
| **U-CP** | Client portal: removed fake OEM/Tier-1/Econ packages; honest empty/error; RUB; no `/track/default` |
| **B-CP-API** | `get_public_request_view` no longer returns `match_score` or `tracking_token` |
| **B-QCOL** | `quote_collect_job` — empty payload → partial + `external_pull=false` |
| **OPS** | `docs/design-partner-erp-s3-checklist.md` + links from beta-readiness |
| **DEV** | `start.sh` explicit Vite :5173, `PARTSOPS_FRONTEND_PORT`, cd fix |

## Still open (ops / product, not silent stubs)

| Item | Why not closed in this PR |
|------|---------------------------|
| Prod ERPNext authorized endpoint | Needs customer ERP + credentials drill |
| Prod S3 lifecycle/policies | Needs cloud bucket provisioning |
| Full VIN decoder (beyond WMI) | Optional external API behind flag |
| Devpack live agents | Scaffold by design — archive or merge later |
| Client portal redesign | Separate UX track |

## Tests added

- `test_vendor_query_with_session_empty_catalog_partial`
- `test_po_create_local_draft_not_success`

## Intentional keep

- `TESTING=1` LLM mock / MOCK_INVENTORY
- ERP_DRY_RUN default outside production
- Jobs dry_run early return
