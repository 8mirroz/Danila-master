# Anti-Mock Hardening — Closeout Report

**Дата:** 2026-07-28  
**Метод:** Subagent-Driven Development (Spec → Implement → Review)  
**Инвентарь:** `mocks-stubs-inventory-2026-07-28.md`  
**PROD checklist:** `prod-env-checklist-2026-07-28.md`

---

## Goal

Убрать silent fakes/stubs, которые врут оператору или production-path, не ломая intentional test mocks / dry-run.

---

## Completed waves

| Wave | Scope | Result |
|------|--------|--------|
| **W0** | Spec review P0 | Plan Approved |
| **W1 P0** | U1/U2 UI fakes, B8 matcher, B12 VIN mock | LGTM |
| **W2** | U3 `UI_MANUAL`, B6 `verify_tracking_token` | LGTM |
| **W3** | B4 notify outbox, B5 DLQ, B1 VIN offline | LGTM |
| **P2** | Automation engines honesty + registry | LGTM (post-fix dry-run/PII) |
| **P3** | Shortcuts, ERP KPI, seed gate, AgentMonitor, JobReport | LGTM (post-fix erpSync) |
| **P4** | PROD `.env.example` + checklist; Devpack scaffold honesty | Done |
| **P5** | Analogs live API, Excel no demo, jobs→engines | Done |
| **P6** | Analogs tenant default `default`; public view token expiry | Done |

---

## Key code outcomes

### Must never lie (fixed)

- Completed orders empty state (no CRM_MOCK list)
- Orchestra error path empty (no mockRun)
- VIN exception → `unknown` (no BMW/Toyota invent)
- Matcher empty DB without TESTING → `[]`
- notify_owner queues outbox (`notified: false`)
- ERP UI: OK/Сбой/н/д, not «100%» / «sync started»
- JobReport / Analogs / Excel: no demo rows
- Devpack agents: `ok=False`, `not_implemented`

### Intentional (kept)

- `TESTING=1` LLM mock + matcher MOCK_INVENTORY
- ERP_DRY_RUN / SMTP missing → no real send
- Seed on sqlite/dev only (prod/postgres fail-safer)

---

## Validation (last full run)

```text
TESTING=1 pytest → 260+ passed, 1 skipped
admin_cockpit tsc --noEmit → exit 0
```

(Re-run after P6 expiry/tenant patches as part of closeout.)

---

## Ops go-live

1. Copy `partsops-ai-manager/.env.example` → `.env`
2. Follow `prod-env-checklist-2026-07-28.md`
3. **Required:** `PARTSOPS_ENV=production`, `SEED_ON_START=0`, `TESTING=0`, `PARTSOPS_API_TOKEN=…`
4. ERP/SMTP only when operators are told they are live

---

## Out of scope / residual

| Item | Note |
|------|------|
| Full ERP push one-click | No backend job; UI honesty only |
| Wire every automation job to engines | Partial (escalate, VIN, quote decide) |
| Devpack static console live API | Labeled SPEC/MOCK by design |
| Unrelated local WIP on branch | Review `git status` before commit |

---

## Recommendation

Create one (or stacked) git commit(s) for anti-mock hardening after human review of `git diff --stat`.
