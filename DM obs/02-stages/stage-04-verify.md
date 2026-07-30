# 🧭 Stage: verify

## 🎯 Goal
Подтвердить светлый фирменный cockpit и связанные backend-изменения без
подмены недоступных данных или настроенных scraper-коннекторов статусом live.

## ✅ Entry Criteria
- Светлая дизайн-система, shell и основные рабочие модули обновлены.
- ERP webhook ведёт заявку только по разрешённым переходам state machine.
- SQLite WAL/SHM исключены из контроля версий как runtime-артефакты.

## 🔨 Current Work
- `pytest -q`: 308 passed, 1 skipped.
- Backend CI-набор: 52 passed.
- Cockpit: lint, production build и 24 Playwright-проверки прошли.

## ⛔ Blockers
- Нет. Существуют только предупреждения о deprecated `datetime.utcnow()`,
  `TestClient` и необходимости задать `ERP_WEBHOOK_SECRET` в production.

## 🚪 Exit Criteria
- Изменения закоммичены в `main`; generated SQLite WAL/SHM не возвращены в Git.

## ➡️ Next Stage
- Наблюдение на подключённом backend: состояние scraper-коннектора должно
  отображаться по фактическому результату вызова, а не только по конфигурации.
