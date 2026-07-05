# Test Plan

## P0 Tests

- State machine allows only valid transitions.
- Invoice gate blocks without admin approval.
- ToolPermissionGuard blocks forbidden tools.
- ModelRouter sends deterministic tasks to no-LLM route.
- BudgetGuard pauses at hard limit.
- Client report sanitizer removes margin/purchase price.

## P1 Tests

- Agent run creates trace.
- Failed run creates debug event.
- Stale price triggers review.
- Low match score triggers review.
- Safety-critical part triggers review.

## P2 Tests

- Eval case created from failed run.
- Replay from failed step works with mock tools.
- Policy snapshot can rollback.
