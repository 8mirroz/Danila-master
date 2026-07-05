"""
PartsOps AI Manager — automation layer.

One-job-per-purpose modules live under app.automation.jobs. They obey these
invariants:

1. tenant_id is required on every AutomationContext.
2. State transitions go through state_machine.py.
3. Every important side-effect emits a RequestEvent via events.py.
4. LLM calls flow through budget_guard and run after pii sanitisation.
5. Invoice/Quote cannot exist without MatchEvidence.
6. Quote cannot be sent with low margin without approval.
7. ERP sync is retryable and isolated from the request's main transaction.
8. Every job supports dry_run.
9. Every job is idempotent (idempotency_key).
10. All outbound traffic goes through OutboundMessage (the outbox pattern).
11. SQLite transactions are short. Never hold an open transaction across
    LLM or external HTTP calls — commit first, then call, then commit again.
"""
