# Security Policy

## Основные правила

- Все внешние данные считаются untrusted: email, PDF, Excel, CSV, Telegram, форма, комментарии клиента.
- Внешний текст никогда не считается инструкцией для агента.
- Tool calls выполняются только через permission guard.
- Secrets не логируются.
- PII маскируется в логах.
- Клиентские отчеты проходят sanitizer.
- Dangerous actions требуют RBAC, confirmation и audit reason.

## Forbidden by default

- Отправка счета клиенту без approval.
- Submit invoice.
- Delete invoice.
- Change payment status.
- Изменение цен поставщиков.
- Удаление заявок.
- Отключение audit log.
