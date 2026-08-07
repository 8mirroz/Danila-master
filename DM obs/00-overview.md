# 🚀 Danila Master

## 📌 Snapshot
<!-- SNAPSHOT:START -->
- Project Slug: ``
- Status: `in-progress`
- Current Stage: `discovery`
- Last Sync: `2026-08-07T14:56:02+03:00`
- Vault Path: `/Users/user/projects/Danila master/DM obs`
<!-- SNAPSHOT:END -->
- Runtime Modes: DEV, STAGE, PROD
- Flow Statuses: active, paused, degraded, safe_mode, incident
- Hard Rules: invoice_send_requires_admin, invoice_draft_requires_admin, all_tool_calls_require_permission_check, all_agent_runs_require_trace, all_decisions_require_evidence, client_report_must_hide_margin, external_inputs_are_untrusted, dangerous_actions_require_audit_reason
## Runtime & Flow

| Показатель | Значение |
|------------|----------|
| Runtime Modes | DEV, STAGE, PROD |
| Flow Statuses | active, paused, degraded, safe_mode, incident |
| Current Stage | discovery (demo active: UI on :3000, API on :8000) |
| Hard Rules | invoice_send_requires_admin, invoice_draft_requires_admin, all_tool_calls_require_permission_check, all_agent_runs_require_trace, all_decisions_require_evidence, client_report_must_hide_margin, external_inputs_are_untrusted, dangerous_actions_require_audit_reason |


## 🎯 Goal
<!-- GOAL:START -->
Поднять `PartsOps AI Manager` до уровня premium operational cockpit: сделать UI/UX более логичным, насыщенным, функциональным и визуально дорогим без потери читаемости и скорости работы менеджера.
<!-- GOAL:END -->

## 👥 Users
<!-- USERS:START -->
TBD
<!-- USERS:END -->

## 📦 Scope
<!-- SCOPE:START -->
- `partsops-ai-manager/06_UI/admin_cockpit` как основной UI-контур
- `DM obs` как канонический слой постановки задач, UX-правил и handoff для агентов
- redesign focus: overview, supplier workspace, request queue, action hierarchy, KPI/inference visibility
<!-- SCOPE:END -->

## ⚠️ Constraints
<!-- CONSTRAINTS:START -->
- Не ломать текущий React + Vite + Tailwind стек
- Сначала выстроить design-system и UX-логику, затем визуальную полировку
- Уйти от generic dashboard look: меньше шаблонных карточек, больше control-plane semantics
- Новые UI-решения должны быть data-dense, explainable и пригодны для дальнейшей интеграции с LangGraph/ERP состояниями
<!-- CONSTRAINTS:END -->

## 🔗 Links
<!-- LINKS:START -->
- Repo Root: `/Users/user/projects/Danila master`
- Canonical Human Memory: `Obsidian`
- Canonical Runtime Memory: `Antigravity/MCP/runtime layers`
<!-- LINKS:END -->

## 🔗 Cross-Vault: PVP2

> Смежный проект: **PVP2 Agent Arena** (kernel, combat, governance, execution reliability)

| Ссылка | Что там |
|--------|---------|
| `../pvp2/Project-Knowledge/reference/MOC.md` | Map of Content – все reference-пакеты |
| `../pvp2/Project-Knowledge/reference/packages/reference-kernel-v1/` | Kernel: ADR, CDR, правила, стандарты |
| `../pvp2/Project-Knowledge/reference/packages/combat-foundation-v1/` | Combat: CDR, механики боя |
| `../pvp2/Project-Knowledge/reference/packages/agent-execution-reliability-v1/` | Execution reliability: production standards |
| `../pvp2/Project-Knowledge/reference/notes/game-design-docs/` | GDD: split docs по validation vision, combat, UI |

**Когда обращаться:** при задачах, затрагивающих Agent Arena, AI combat, runtime reliability или governance policy.
