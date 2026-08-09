# Growth & Optimization Snapshot — 2026-08-09

## Executed (S1 partial)

| ID | Change |
|----|--------|
| **D-CI** | CI runs full `pytest tests/` (was partial file list) |
| **S-MATCH** | Matcher SQL prefilter by OEM/brand/name tokens + `MAX_CATALOG_CANDIDATES` cap |
| **S-OEM-IDX** | Indexes on `oem_number`, `brand`, `(tenant_id, oem_number)` + model Field index |

## Still open (priority)

- **P-OPS** prod S3 + ERPNext checklist execution  
- **S-BUDGET** persist BudgetGuard across workers  
- **A-GOD** split contract_operations / requests router  
- **I-GOLD** nightly golden regression  

## Metrics to track post-matcher

- Matcher p95 with 10k+ catalog rows  
- CI wall time after full suite  
