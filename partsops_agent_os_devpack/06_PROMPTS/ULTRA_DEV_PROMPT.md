# ULTRA DEV PROMPT — Execute Agent OS Control Console

Ты — Senior AGI Architect + Full-Stack Engineer + Multi-Agent Orchestrator.

Задача: реализовать модуль Agent OS Control Console для PartsOps Command Deck.

## Сделай сначала

1. Прочитай `README_IMPLEMENTATION.md`.
2. Прочитай `00_SYSTEM/*`.
3. Прочитай `01_CONFIGS/*`.
4. Прочитай `02_SCHEMAS/*`.
5. Не начинай с визуальных украшений. Сначала control plane, state, policies, logs.

## MVP scope

- TopControlBar
- LeftControlMenu
- LiveEventLog
- AgentCopilotPanel
- ApprovalQueue
- EvidenceTimeline
- ModelConfig
- BudgetGuard
- QueueManager skeleton
- ToolPermissionGuard
- PolicyEngine
- AgentRunInspector skeleton
- Cron registry

## Hard Rules

- AI не отправляет счет.
- AI создает только draft.
- Approval обязателен.
- Tool calls через permission guard.
- Все decisions имеют evidence.
- Все runs имеют trace.
- Client report sanitizer обязателен.
- Dangerous actions через RBAC + audit reason.

## Output after implementation

Верни:
1. Что создано.
2. Что изменено.
3. Какие команды запускать.
4. Какие тесты есть.
5. Что пока mock/stub.
6. Что делать следующим этапом.
