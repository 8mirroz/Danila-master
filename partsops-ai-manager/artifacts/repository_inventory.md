# Repository Inventory

## 1. Общая информация
- **Корневая директория**: `/Users/user/projects/Danila master/partsops-ai-manager`
- **Ветка**: `main`
- **Текущий коммит (SHA)**: `fe68cb4bf67d1ff3433b15b73fec1a216f59e68a`
- **Статус рабочей директории**: чистая (изменения внесены только в `migrations` и `.github/workflows/ci.yml`)

## 2. Архитектура и Структура файлов
Проект построен на стеке: FastAPI, SQLModel (SQLAlchemy), Alembic, Pydantic v2, RapidFuzz.

### Ключевые компоненты
- [main.py](file:///Users/user/projects/Danila master/partsops-ai-manager/main.py): Входная точка API. Содержит инициализацию FastAPI и роутеров.
- [models.py](file:///Users/user/projects/Danila master/partsops-ai-manager/models.py): Описание всех сущностей БД и схем Pydantic.
- [database.py](file:///Users/user/projects/Danila master/partsops-ai-manager/database.py): Конфигурация подключения к БД и сессий.
- [matcher.py](file:///Users/user/projects/Danila master/partsops-ai-manager/matcher.py): Движок fuzzy matching (6-компонентная формула с RapidFuzz и кэшированием ключевых слов из YAML).
- [services/analog_resolver.py](file:///Users/user/projects/Danila master/partsops-ai-manager/services/analog_resolver.py): Алгоритмы классификации брендов и оценки рисков аналогов.
- [pii.py](file:///Users/user/projects/Danila master/partsops-ai-manager/pii.py): Маскирование персональных данных (телефоны, email, VIN) до LLM/логов.
- [pricing.py](file:///Users/user/projects/Danila master/partsops-ai-manager/pricing.py): Алгоритмы расчета цен, наценок, маржинальности и прогнозирования Holt-Winters.
- [budget_guard.py](file:///Users/user/projects/Danila master/partsops-ai-manager/budget_guard.py): Лимитирование токенов и стоимости LLM запросов.
- [rbac.py](file:///Users/user/projects/Danila master/partsops-ai-manager/rbac.py): Контроль доступа на основе ролей (`admin`, `manager`, `finance`) и подписей тенантов.

## 3. Проверка зависимостей (Dependency Authority)
Зависимости зафиксированы в [requirements.txt](file:///Users/user/projects/Danila master/partsops-ai-manager/requirements.txt):
- FastAPI, SQLModel, Uvicorn.
- rapidfuzz, openpyxl, pandas.
- reportlab, weasyprint для генерации документов.
- Кэшированная venv среда использует Python 3.12.13.
