# Agent Roles

## SupervisorAgent
Главный координатор. Запускает этапы, следит за state machine, отправляет в review.

## RequestParserAgent
Разбирает заявку клиента: авто, VIN, детали, количество, ограничения.

## VehicleValidatorAgent
Проверяет полноту данных машины и формирует вопросы клиенту.

## SupplierQueryAgent
Запрашивает поставщиков, прайсы, API, email и сохраняет evidence.

## CatalogMatcherAgent
Сопоставляет OEM, артикулы, бренды, аналоги и названия.

## OfferRankerAgent
Выбирает лучший, дешевый, быстрый и безопасный варианты.

## RiskCheckerAgent
Проверяет риски: аналог, safety-critical, низкая уверенность, stale price, плохой поставщик.

## ReportAgent
Делает admin report и client report. Клиентский отчет не раскрывает маржу.

## InvoiceDraftAgent
Создает только draft счета после approval и всех gates.

## DebugAgent
Разбирает ошибки, предлагает replay, создает eval case.

## OperatorCopilotAgent
Показывает оператору простые варианты действий: approve, ask client, rerun, escalate.
