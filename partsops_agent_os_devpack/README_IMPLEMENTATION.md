# PartsOps Agent OS Control Console — Dev Pack v0.1

Цель пакета: дать разработчику/IDE-агенту готовый стартовый каркас для модуля управления AI-агентом в PartsOps Command Deck.

## Что внутри

- `00_SYSTEM/` — системные правила, права, approval, безопасность.
- `01_CONFIGS/` — политики моделей, бюджета, кронов, валидаций, feature flags.
- `02_SCHEMAS/` — JSON-схемы ключевых сущностей.
- `03_UI_SPEC/` — описание экранов, меню, компонентов и UX-логики.
- `04_BACKEND_CONTRACTS/` — Python-каркас control plane, агентов, очередей, политик, debug.
- `05_FRONTEND/` — React/TypeScript skeleton для Agent OS Console.
- `06_PROMPTS/` — ultra prompt и роли агентов.
- `07_TESTS/` — тест-план и pytest skeleton.
- `08_RUNBOOKS/` — запуск, debug, rollout, rollback.

## MVP-цель

Собрать первый рабочий экран, где оператор видит:

- статус агента;
- модель и бюджет;
- очередь заявок;
- live logs;
- активный agent run;
- approvals;
- tool calls;
- ошибки;
- кнопки pause / resume / safe mode / restart.

## Hard Rules

1. AI не отправляет счет сам.
2. AI может создавать только draft счета.
3. Все рискованные решения идут на admin approval.
4. Все tool calls проходят permission guard.
5. Все решения имеют evidence.
6. Все ошибки пишутся в trace и debug.
7. Клиентский отчет не показывает маржу.
8. Любое изменение политики имеет snapshot и rollback.
