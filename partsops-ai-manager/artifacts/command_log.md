# Command Log

## DISCOVER & BASELINE Phase Commands

1. **Создание директории артефактов и сбор метаданных Git**:
   ```bash
   mkdir -p artifacts
   git rev-parse HEAD > artifacts/commit-sha.txt
   git status --short > artifacts/git-status.txt
   git branch --show-current >> artifacts/git-status.txt
   ```
   *Результат*: Успешно. Commit SHA: `fe68cb4bf67d1ff3433b15b73fec1a216f59e68a`.

2. **Запуск baseline тестов с записью в JUnit XML**:
   ```bash
   PYTHONPATH=. ./venv/bin/pytest --junitxml=artifacts/baseline-junit.xml --durations=30 -ra 2>&1 | tee artifacts/baseline-pytest.log
   ```
   *Результат*: 213 тестов пройдены, 1 пропущен. Успешно сгенерирован [baseline-junit.xml](file:///Users/user/projects/Danila master/partsops-ai-manager/artifacts/baseline-junit.xml).

3. **Установка зависимостей сбора покрытия**:
   ```bash
   ./venv/bin/pip install pytest-cov coverage
   ```
   *Результат*: Зависимости установлены успешно.

4. **Сбор покрытия тестами**:
   ```bash
   PYTHONPATH=. ./venv/bin/pytest --cov=. --cov-report=xml:artifacts/coverage.xml --cov-report=term-missing 2>&1 | tee artifacts/coverage.log
   ```
   *Результат*: Общее покрытие: 73%. Успешно сгенерирован [coverage.xml](file:///Users/user/projects/Danila master/partsops-ai-manager/artifacts/coverage.xml).

5. **Запуск скрипта парсинга предупреждений**:
   ```bash
   python3 scratch/parse_warnings.py
   ```
   *Результат*: Сгенерирован [warning_inventory.json](file:///Users/user/projects/Danila master/partsops-ai-manager/artifacts/warning_inventory.json).

6. **Тестирование миграций базы данных**:
   ```bash
   rm -f test_migration.db
   DATABASE_URL=sqlite:///test_migration.db ./venv/bin/alembic upgrade head
   DATABASE_URL=sqlite:///test_migration.db ./venv/bin/alembic downgrade base
   ```
   *Результат*: Выявлена и устранена ошибка downgrade SQLite. После применения `if_exists=True` в `50ece6030d5a` миграционный цикл отрабатывает без ошибок.
