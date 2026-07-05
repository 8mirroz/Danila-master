# Rollout Plan

## Phase 1 — Static Console

- UI layout.
- Mock metrics.
- Mock events.
- Mock approvals.

## Phase 2 — Backend Contracts

- PolicyEngine.
- ModelRouter.
- BudgetGuard.
- ToolPermissionGuard.
- StateMachine.

## Phase 3 — Real Logs

- EventLogger.
- TraceWriter.
- Tool call logs.
- Queue status.

## Phase 4 — Agent Pipeline

- SupervisorAgent.
- ParserAgent.
- MatcherAgent.
- RiskAgent.
- ReportAgent.
- InvoiceDraftAgent.

## Phase 5 — Safety

- ApprovalService.
- InvoiceGate.
- ReportSanitizer.
- SafeMode.
- KillSwitch.

## Phase 6 — Evals & Replay

- EvalLab.
- ReplayPanel.
- Failed case collector.
- Prompt version regression.
