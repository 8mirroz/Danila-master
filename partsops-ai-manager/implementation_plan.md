# 🚀 Implementation Plan: Внедрение ключевых точек роста PartsOps AI Manager

Этот план описывает последовательную реализацию наиболее эффективных улучшений, сформулированных в продуктовом разборе.

---

## 🎯 Компоненты и этапы реализации

### Этап 1: Kanban & UX Enhancements (Блокеры и карточки)
- **Файлы:** `06_UI/admin_cockpit/src/components/KanbanCard.tsx`, `KanbanBoard.tsx`, `src/types.ts`
- **Изменения:**
  - Добавить отображение микро-бэйджей причин блокировки (`[No VIN]`, `[Low Margin]`, `[ERP Error]`, `[Stale SLA]`).
  - Добавить визуальный индикатор времени нахождения в текущем статусе.

### Этап 2: Мульти-вариантные Коммерческие Предложения (Basic / Standard / Premium)
- **Файлы:** `routers/quotes.py`, `services/quotes.py`, `06_UI/admin_cockpit/src/components/QuotesPanel.tsx`
- **Изменения:**
  - Реализовать генерацию трёх опций КП:
    1. **Оригинал (OEM)** — 100% оригинальные запчасти
    2. **Оптимум (Tier-1)** — проверенные аналоги премиум-брендов (Bosch, Lemforder, Sachs)
    3. **Эконом (Budget)** — доступные бюджетные замены
  - Вывести сравнение 3 вариантов на UI с выбором итогового варианта для клиента.

### Этап 3: Client Portal — Drag-and-Drop Intake & Magic Link Approval
- **Файлы:** `06_UI/client_portal/src/App.tsx`, `src/pages/`, `routers/client_portal.py` (или `requests.py`)
- **Изменения:**
  - Добавить в Client Portal форму мульти-форматной загрузки (XLSX, PDF, фото СТС/запчасти).
  - Реализовать экран просмотра и утверждения 3-вариантного КП клиентом в один клик.

### Этап 4: Smart Model Routing & Fallback в LLM Engine
- **Файлы:** `llm.py`, `settings.py`
- **Изменения:**
  - Реализовать каскадный перехват ошибок вызова LLM (Circuit Breaker / Fallback Chain): `Primary Provider` ➔ `Secondary Provider` ➔ `Structured Fallback Engine`.
  - Гарантировать 100% отказоустойчивость при проблемах у внешних AI-провайдеров.

### Этап 5: Симулятор ценовых сценариев "What-If"
- **Файлы:** `pricing.py`, `06_UI/admin_cockpit/src/components/GlobalPricingSimulator.tsx`
- **Изменения:**
  - Добавить интерактивную симуляцию применения гибких коэффициентов наценок на всю очередь активных заказов с моментальным пересчетом маржи.

---

## 🔍 Verification Plan

### Автоматические тесты:
- `PYTHONPATH=. pytest tests/` — прогон с интеграцией новых тестов на мульти-КП и fallback.
- `npx tsc --noEmit` и `npm run build` для обоих фронтендов (`admin_cockpit` и `client_portal`).

### Браузерная проверка:
- Проверка отображения бэйджей блокеров на Канбане.
- Проверка 3-вариантного КП на экране предложений.
- Проверка Client Portal драг-н-дроп загрузки и утверждения.
