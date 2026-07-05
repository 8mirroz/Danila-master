# Agent OS Control Console — UI Specification

## Цель экрана

Показать оператору состояние AI-движка и дать управление: пауза, запуск, перезапуск, safe mode, debug, approval, replay.

## Layout

- Top Control Bar
- Left Control Menu
- Center Viewport with tabs
- Right Agent Copilot
- Bottom Debug Layer

## Top Control Bar

Показывает:

- Agent OS badge
- DEV/STAGE/PROD
- поток активен / пауза / safe mode / incident
- session spend
- daily budget
- RPM
- queue health
- active threads
- error rate
- pause / resume / restart / safe mode / emergency stop

## Left Menu

Разделы:

1. Model Configuration
2. Model Routing
3. Budget & Limits
4. Tools & MCP
5. Workflow Policies
6. Validation Gates
7. Cron Jobs
8. Memory
9. Prompt Registry
10. Security
11. Feature Flags

## Center Tabs

1. Live Event Log
2. Agent Run Inspector
3. Workflow Graph
4. Queue Manager
5. Tool Calls
6. Eval Lab
7. Debug Console
8. Incident Center
9. Analytics

## Right Panel

- Active Agent Card
- Approval Queue
- Decision Quiz
- Suggested Actions
- Exceptions

## Bottom Debug Layer

Tabs:

- Evidence
- Trace
- Raw JSON
- Errors
- Replay
- Rollback
