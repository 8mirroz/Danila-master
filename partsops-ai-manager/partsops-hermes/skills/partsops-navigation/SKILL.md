---
name: partsops-navigation
description: Navigation guide and allowed UI actions for PartsOps Admin Cockpit.
---

# Skill: PartsOps Navigation

## Доступные экраны Admin Cockpit (`screen_id`)

1. `kanban_board` — Канбан-доска текущих заказов по этапам pipeline.
2. `order_details` — Карточка выбранного заказа (детализация, позиции, поставщики, аналоги).
3. `suppliers_page` — Реестр и матрица поставщиков, показатели надежности (SLA).
4. `invoices_registry` — Реестр счетов, проверка накладных и актов.
5. `contract_control` — Панель контрактного контроля и верификации SLA.
6. `agent_os_panel` — Диагностика Hermes Copilot, LLM-трасс и системных логов.

## Безопасные действия навигации

Когда оператору требуется перейти в раздел или подсветить элемент, указывай соответствующие action IDs:
- `open_screen`: Переход на экран (аргумент: `screen_id`).
- `open_request`: Открытие карточки заказа (аргумент: `request_id`).
- `focus_control`: Подсветка конкретного элемента интерфейса (аргумент: `element_id`).
