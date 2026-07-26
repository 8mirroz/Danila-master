# Baseline Report

## 1. Параметры запуска
- **Commit SHA**: `fe68cb4bf67d1ff3433b15b73fec1a216f59e68a`
- **Окружение**: Python 3.12.13 (macOS arm64), pytest-9.1.1, sqlmodel-0.0.22, sqlite3.

## 2. Результаты тестирования
- **Всего найдено тестов**: 214
- **Успешно пройдено**: 213
- **Пропущено (skipped)**: 1 (`tests/test_postgres_integration.py` — требует активной строки подключения к реальной PostgreSQL БД).
- **Ошибки (failed)**: 0
- **Общее время прогона**: 20.08 сек.
- **XML-отчет JUnit**: сохранен в [baseline-junit.xml](file:///Users/user/projects/Danila master/partsops-ai-manager/artifacts/baseline-junit.xml).

## 3. Результаты покрытия (Test Coverage)
- **Общий процент покрытия**: 73%
- **Критически важные файлы**:
  - `matcher.py`: 76%
  - `services/analog_resolver.py`: 83%
  - `pii.py`: 99%
  - `pricing.py`: 64%
  - `rbac.py`: 79%
  - `state_machine.py`: 77%
  - `budget_guard.py`: 100% (из файла `models.py` и тестов)
- **XML-отчет покрытия**: сохранен в [coverage.xml](file:///Users/user/projects/Danila master/partsops-ai-manager/artifacts/coverage.xml).
- **Детальный лог**: сохранен в [coverage.log](file:///Users/user/projects/Danila master/partsops-ai-manager/artifacts/coverage.log).

## 4. Классификация предупреждений (Warnings)
Всего зарегистрировано **1701** предупреждение.
- **Legacy utcnow()**: 34 предупреждения типа `DeprecationWarning` от Pydantic и вызовов `datetime.utcnow()` в проекте.
- **SQLModel Query API**: Множество DeprecationWarning от SQLAlchemy из-за использования устаревшего `session.query(...)` вместо `session.exec(select(...))` в тестах (`test_matcher.py`, `test_matcher_n_plus_one.py`).
- **Служебные предупреждения**: `StarletteDeprecationWarning` (использование `httpx` с `TestClient`), отсутствие `ERP_WEBHOOK_SECRET` в переменных окружения во время тестов.

## 5. Обнаруженные критические аномалии (Database Audit)
- Во время `downgrade base` миграции происходил сбой:
  `sqlite3.OperationalError: no such index: ix_fleetvehicle_status`
- **Причина**: Миграция `b7c9e2d4a611` удаляет этот индекс во время downgrade, а затем миграция `50ece6030d5a` пытается удалить его повторно, не проверяя существование.
- **Решение**: Добавлен флаг `if_exists=True` в `op.drop_index` внутри `50ece6030d5a_add_fleet_vehicles_and_tariffs.py`. Цикл upgrade-downgrade-upgrade теперь успешно отрабатывает.
