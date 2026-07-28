---
name: partsops-troubleshooting
description: Troubleshooting guide for partial, stale, offline, blocked states, ERP and supplier sync issues in PartsOps.
---

# Skill: PartsOps Troubleshooting

## Частые операционные проблемы

1. **Заказ в статусе BLOCKED**:
   - Причина: не пройден один из Evidence Gates (например, маржа меньше минимальной или не совпадает артикль).
   - Действие: оператор должен проверить вкладку "Evidence Gates" в карточке заказа и вручную подтвердить расхождение.

2. **Статус поставщика STALE или OFFLINE**:
   - Причина: прайс-лист не обновлялся более 24 часов или API поставщика временно недоступно.
   - Действие: проверить реестр поставщиков на экране `suppliers_page` или запросить ручное обновление цен.

3. **Ошибка синхронизации ERP**:
   - Причина: таймаут ответа ERP-адаптера или несовпадение реквизитов.
   - Действие: проверить логи на экране `agent_os_panel` в разделе ERP Traces.
