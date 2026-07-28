---
name: partsops-request-explainer
description: Explains order status transitions, allowed next states, evidence gates, and blocking reasons in PartsOps.
---

# Skill: PartsOps Request Explainer

## Статусы заказа и Workflow

- `DRAFT` — Новая заявка. Разрешен переход в `PARSED` или `BLOCKED`.
- `PARSED` — Заявка распарсена, VIN расшифрован. Допустим переход в `MATCHING`.
- `MATCHING` — Подбор аналогов и предложение поставщиков. Допустим переход в `PRICED` или `BLOCKED`.
- `PRICED` — Рассчитана маржа и цены. Допустим переход в `CONTRACT_VERIFIED`.
- `CONTRACT_VERIFIED` — Пройдены проверки контрактов и Evidence Gates. Переход в `INVOICED`.
- `INVOICED` — Сформирован счет на оплату. Переход в `COMPLETED`.
- `BLOCKED` — Заказ заблокирован из-за отсутствия обязательных подтверждений (Evidence Gates), ценовых аномалий или проблем с VIN/PII.

## Evidence Gates (Гейты доказательств)

Каждый переход требует валидных гейтов:
- `GATE_VIN_VALID`: Подтвержденная расшифровка VIN.
- `GATE_PRICE_MARGIN`: Процент маржи в пределах допустимого коридора.
- `GATE_SUPPLIER_SLA`: Поставщик активен и в пределах допустимого SLA.
- `GATE_PII_CLEAN`: Входные данные обезличены.
