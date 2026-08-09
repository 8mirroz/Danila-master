# Growth & Optimization Snapshot — 2026-08-09

## Executed

| ID | Change |
|----|--------|
| **D-CI** | CI full `pytest tests/` |
| **S-MATCH** | Matcher SQL prefilter + candidate cap |
| **S-OEM-IDX** | Catalog OEM/brand indexes |
| **S-BUDGET** | BudgetGuard reads `LLMUsageLog` (multi-worker) |
| **S-LLM** | `classify` route + short TTL prompt cache |
| **I-GOLD** | Golden regression report JSON + accuracy alert |
| **A-GOD** | `routers/request_schemas.py` extracted from requests |
| **R-OBS** | `/health` readiness checks (db/storage/erp/budget) |

## Still open (needs ops credentials / larger refactors)

- **P-OPS** prod S3 + ERPNext drills (checklist only)  
- **A-GOD** deeper split of `contract_operations` (2.2k LOC)  
- **P-RFQ-EMAIL** inbound email RFQ

## Metrics to track post-matcher

- Matcher p95 with 10k+ catalog rows  
- CI wall time after full suite  
