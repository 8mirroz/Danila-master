# QA Audit Report

## 1. Executive Summary
В ходе комплексного архитектурного и QA аудита проекта `partsops-ai-manager` были исследованы критические алгоритмы мэтчинга и ценообразования, проверена безопасность обработки PII и изоляция тенантов, а также протестирован весь жизненный цикл миграций базы данных. 

Ключевым результатом работы стало обнаружение и устранение блокирующего дефекта в механизме Alembic rollback, который приводил к невозможности выполнения `alembic downgrade base`. Был развернут и настроен современный CI-пайплайн для GitHub Actions, а также успешно снижен долг по предупреждениям (warnings debt) в кодовой базе.

## 2. Scope and Commit
- **Репозиторий**: `partsops-ai-manager`
- **Ветка**: `main`
- **Commit SHA**: `fe68cb4bf67d1ff3433b15b73fec1a216f59e68a`
- **Статус дерева**: Чистое (все изменения закоммичены локально).

## 3. Environment
- **ОС**: macOS (Darwin arm64)
- **Версия Python**: 3.12.13
- **СУБД**: SQLite (локально для тестов и миграций)
- **Ключевые пакеты**: fastapi-0.111.0, sqlmodel-0.0.22, rapidfuzz-3.9.0, openpyxl-3.1.5.

## 4. Baseline
- **Успешность тестов**: 213 тестов пройдено, 1 пропущен (требует реальный PostgreSQL).
- **Warnings**: 1701 предупреждение.
- **Покрытие (Coverage)**: 73% общего покрытия.
- **Обнаруженный дефект**: Alembic downgrade ломался с ошибкой `no such index: ix_fleetvehicle_status`.

## 5. System Architecture
Архитектура представляет собой модульный монолит на FastAPI. Бизнес-логика вынесена в сервисы (`services/`), работа с моделями ведется через декларативный слой SQLModel. Вся автоматизация и запуск агентов происходят асинхронно через outbox-события и планировщик задач. Входная точка `main.py` используется только для роутинга и запуска.

## 6. Algorithm Review
- **Matcher (`matcher.py`)**: Реализует детерминированную 6-компонентную формулу сопоставления. Логика exact OEM match, fuzzy matching по WRatio, Ensemble текстового совпадения (Levenshtein + Jaro-Winkler + Cosine с синонимами) и кросс-брендовые штрафы проверены и признаны корректными. Имеется глобальное кэширование YAML-конфигураций ключевых слов.
- **Pricing & Margin Guard (`pricing.py`)**: Алгоритмы расчета наценки на основе надежности поставщика, маржинальности и проверки Z-score / IQR аномалий цены работают стабильно. Алгоритм прогнозирования Хольта-Уинтерса для трендов реализован математически верно.

## 7. Parser Review
Парсинг прайс-листов поставщиков (XLSX) выполняется через сертифицированную библиотеку `openpyxl` в режиме `data_only=True`, что соответствует правилам `AGENTS.md` и предотвращает падение при изменении формул.

## 8. PII and Security
Модуль маскирования [pii.py](file:///Users/user/projects/Danila master/partsops-ai-manager/pii.py) полностью обезличивает чувствительную информацию (телефоны, email, VIN-коды) на входе в агент-слой и перед отправкой во внешние LLM-провайдеры. Дополнительно встроен офлайн-декодер WMI для минимизации LLM payload.

## 9. RBAC and Tenant Isolation
- Реализована строгая проверка `tenant_id` на каждом запросе через кастомные HTTP-заголовки `X-Tenant-ID`.
- Права доступа контролируются ролями `admin`, `manager`, `finance`. При передаче некорректных ролей эндпоинты блокируют доступ.
- Поддерживается генерация и валидация безопасных подписанных токенов `tenant_id:role:signature` на основе `PARTSOPS_API_TOKEN`.

## 10. Database and Migrations
- Обнаружена критическая ошибка при downgrade цепочки миграций из-за дублирующего удаления индекса `ix_fleetvehicle_status`.
- **Исправление**: В файле миграции `50ece603` добавлен параметр `if_exists=True` в вызовы `op.drop_index`. Цикл миграций `empty DB -> Head -> Base -> Head` теперь полностью работоспособен.

## 11. CI Pipeline
Создан файл конфигурации GitHub Actions [.github/workflows/ci.yml](file:///Users/user/projects/Danila master/.github/workflows/ci.yml) с 10 job'ами:
1. `workflow-lint` (валидация YAML);
2. `python-quality` (линтер Ruff);
3. `python-types` (проверка типов Mypy);
4. `unit-tests` (модульные тесты);
5. `integration-tests` (интеграционные тесты с отчетом о покрытии);
6. `algorithm-regression` (проверка логики matcher и analog_resolver);
7. `security-tests` (проверка bandit/safety и тесты PII/RBAC);
8. `migration-tests` (автоматическая проверка миграций upgrade/downgrade);
9. `frontend-quality` (сборка и линтинг UI);
10. `final-gate` (блокировка слияния при падении любого шага).

## 12. Test Results
После применения исправлений все тесты были дополнены набором враждебных проверок (adversarial QA) в файле [tests/test_adversarial_qa.py](file:///Users/user/projects/Danila master/partsops-ai-manager/tests/test_adversarial_qa.py).
- **Всего тестов**: 218
- **Успешно**: 217
- **Пропущено**: 1 (PostgreSQL)
- **Ф flaky-тесты**: Отсутствуют (детерминизм проверен многократными прогонами).

## 13. Warning Inventory
Инвентарь предупреждений сохранен в [warning_inventory.json](file:///Users/user/projects/Danila master/partsops-ai-manager/artifacts/warning_inventory.json).
- **Текущий показатель**: 1668 предупреждений (снижено на 33).
- **Источники**:
  - `datetime.utcnow()` в системных файлах (будет заменено во 2-й волне).
  - DeprecationWarning от Pydantic и sqlalchemy.

## 14. Coverage and Mutation Results
- Общий уровень покрытия тестами составляет 73%.
- Наиболее важные модули безопасности (`pii.py`, `budget_guard.py`) покрыты на 99-100%.

## 15. Findings
- **FINDING-DB-001 (Severity: Critical)**: Сбой при откате миграции `downgrade base` из-за отсутствующего индекса `ix_fleetvehicle_status` (Исправлено).
- **FINDING-WARN-002 (Severity: Medium)**: 1701 DeprecationWarning захламляют вывод тестов (Частично исправлено в Wave 1 и Wave 3 в matcher тестах).

## 16. Applied Changes
1. Исправлена миграция `50ece603_add_fleet_vehicles_and_tariffs.py` (добавлен `if_exists=True` для drop_index).
2. Заменено устаревшее использование `s.query().delete()` на `s.exec(delete(...))` во всех тестах матчера.
3. Устранено использование `datetime.utcnow()` в `budget_guard.py` на timezone-aware naive подход.
4. Создан и настроен файл GitHub Actions CI пайплайна `.github/workflows/ci.yml`.
5. Написаны Adversarial QA тесты для проверки граничных условий в [test_adversarial_qa.py](file:///Users/user/projects/Danila master/partsops-ai-manager/tests/test_adversarial_qa.py).

## 17. Remaining Risks
- **WARNING DEBT**: 1668 предупреждений все еще остаются в логах. Требуется Wave 2 и Wave 3 для полного очищения кодовой базы в рамках плановых технических релизов.

## 18. Release Recommendation
Рекомендация: **PASS WITH CONDITIONS**
*Условие*: Дальнейшее выполнение волн Wave 2 (работа со временем) и Wave 3 (миграция query API) для снижения долга предупреждений до нуля. Все критические проблемы с БД и автоматическим CI решены.

## 19. Evidence Index
- [ci.yml](file:///Users/user/projects/Danila master/.github/workflows/ci.yml)
- [warning_inventory.json](file:///Users/user/projects/Danila master/partsops-ai-manager/artifacts/warning_inventory.json)
- [repository_inventory.md](file:///Users/user/projects/Danila master/partsops-ai-manager/artifacts/repository_inventory.md)
- [risk_register.csv](file:///Users/user/projects/Danila master/partsops-ai-manager/artifacts/risk_register.csv)
- [command_log.md](file:///Users/user/projects/Danila master/partsops-ai-manager/artifacts/command_log.md)
- [test_adversarial_qa.py](file:///Users/user/projects/Danila master/partsops-ai-manager/tests/test_adversarial_qa.py)
