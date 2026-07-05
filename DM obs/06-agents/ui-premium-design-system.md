# 🎨 UI Premium Design System Guide

## 🎯 Purpose
- Дать агентам и дизайнерам единый стандарт для улучшения `PartsOps AI Manager`.
- Перевести `admin_cockpit` из статичного mock dashboard в premium operational control plane.

## 🧭 Source Skills Integrated
- `design-system-architect`
- `ui-premium`

## 🏛 Product Framing
- Продукт не должен выглядеть как generic admin panel.
- Это операторская система для закупки автозапчастей с AI-агентами, статусами, evidences, рисками и быстрыми действиями.
- Интерфейс должен одновременно показывать confidence, очереди, источники данных, SLA и следующий лучший action.

## 🧱 Design System Rules
### 1. Visual hierarchy
- 3 слоя поверхностей: shell, workspace, focused panels.
- Главные действия и critical states должны читаться за 2-3 секунды.
- Каждый экран обязан иметь один primary objective и 1-2 вторичных потока, не больше.

### 2. Token discipline
- Все цвета, отступы, радиусы, тени и motion задаются через CSS variables.
- Базовый набор токенов: `--bg-*`, `--surface-*`, `--accent-*`, `--text-*`, `--border-*`, `--status-*`, `--shadow-*`.
- Нельзя вводить одноразовые inline-цвета, кроме временного прототипирования.

### 3. Premium look
- Вместо плоских карточек использовать layered surfaces, tonal contrast и аккуратные inner/outer shadows.
- Типографика должна быть более характерной, чем текущий `Inter-only` template look.
- Иконки, KPI и статусные бейджи должны быть собраны в единую визуальную систему, а не жить как отдельные декоративные элементы.

### 4. Functional density
- На первом экране должны быть видны: health системы, активные заявки, риски, pending approvals, supplier movement и agent outcomes.
- Карточки без actionability запрещены: каждый крупный блок должен либо объяснять состояние, либо вести к следующему решению.
- Состояние заявки должно показывать не только `status`, но и confidence, owner, blockers, ETA и recommended next step.

### 5. Interaction model
- Основной UX-паттерн: queue -> inspect -> compare -> approve/escalate.
- Важные действия должны быть ближе к данным: approve, compare offers, inspect evidence, create invoice draft.
- Hover, focus, loading, empty, error и partial-data states должны быть спроектированы явно.

### 6. Motion and accessibility
- Motion только смысловой: 150-300ms, без декоративной перегрузки.
- Контраст не ниже 4.5:1.
- Видимый focus-state обязателен для всех interactive controls.

## 🧩 Admin Cockpit Redesign Task
### Objective
- Сделать `admin_cockpit` более premium, логичным, насыщенным и функциональным, сохранив скорость операторской работы.

### Required UI improvements
- Перестроить top bar в control header с environment state, agent health, notifications и global actions.
- Превратить левую колонку из списка поставщиков в intelligent supplier workspace: сегменты, freshness, SLA, risk, filters.
- Переделать center panel в настоящий operations overview: KPI, pipeline, urgent cases, evidence summary, task lanes.
- Усилить правую колонку как request triage rail: draft, validated, blocked, escalated, invoice-ready.
- Добавить explainability surfaces: why selected, confidence, source count, price delta, risk notes.
- Сделать layout менее шаблонным: сильнее контраст shell/workspace/panel, лучше композиция, richer density.

### Deliverables
- Обновленный token set и naming scheme.
- Component inventory для cockpit: shell, data cards, queue items, evidence chips, risk badges, action bars.
- Page brief для `overview` как primary screen.
- Список состояний данных: loading, empty, stale, synced, failed, blocked, awaiting approval.

### Definition of done
- Интерфейс читается как control plane, а не Vite/Tailwind template.
- Пользователь без объяснений понимает system health, priority queue и next actions.
- У каждой ключевой панели есть functional purpose и измеримая ценность.
- UI можно последовательно масштабировать на supplier, request, invoice и audit flows.
