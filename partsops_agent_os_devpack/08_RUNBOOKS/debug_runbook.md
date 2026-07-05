# Debug Runbook

## Если agent run упал

1. Открыть Agent Run Inspector.
2. Найти failed stage.
3. Проверить input schema.
4. Проверить output schema.
5. Проверить tool calls.
6. Проверить policy snapshot.
7. Проверить model response.
8. Запустить replay from failed stage.
9. Если ошибка повторяется — создать eval case.
10. Если ошибка опасная — quarantine request.

## Если вырос бюджет

1. Открыть Budget Panel.
2. Проверить top cost runs.
3. Включить low-cost mode.
4. Ограничить parallel runs.
5. Запустить cost report.

## Если tool call опасный

1. Заблокировать tool.
2. Открыть Tool Calls.
3. Создать incident.
4. Проверить RBAC и permission guard.
5. Добавить regression test.
