# Supplier Workspace Upgrade Plan

## Purpose

Обновить раздел поставщиков из рабочего MVP в полноценный operator workspace:
- управлять поставщиками как master-data сущностями;
- работать с таблицами/прайс-листами без Excel;
- видеть аналитику, лог изменений и качество данных;
- ускорить повседневные действия закупщика через более удобный UI.

## Source Of Truth Checked

- `partsops-ai-manager/06_UI/admin_cockpit/src/components/SuppliersPage.tsx`
- `partsops-ai-manager/06_UI/admin_cockpit/src/components/SupplierDetailPage.tsx`
- `partsops-ai-manager/06_UI/admin_cockpit/src/components/SupplierCards.tsx`
- `partsops-ai-manager/06_UI/admin_cockpit/src/components/supplierTypes.ts`
- `partsops-ai-manager/main.py`

## Current Implementation

Что уже есть в коде:
- каталог поставщиков с live API, фильтрами, counters и двумя режимами просмотра;
- создание, редактирование и архивирование поставщика;
- detail workspace с вкладками `overview`, `profile`, `tables`, `analytics`, `logs`, `settings`;
- управление таблицами поставщика: создание, импорт, активация, замена версий, редактирование метаданных;
- live preview строк таблицы и просмотр позиции без открытия Excel;
- редактирование отдельной строки и bulk update для набора строк;
- backend endpoints для supplier CRUD, tables, rows, analytics, logs, reliability history, price history.

## Main Gaps

Что ещё не дотягивает до целевого экрана:
- `analytics` и `logs` есть на API, но UI можно сделать глубже и полезнее для ежедневной работы;
- нет полноценного compare-mode между версиями таблиц;
- нет явного quality-center по ошибкам импорта, маппингу колонок и проблемным строкам;
- ручной рейтинг есть в модели/API, но UX рейтинга и причин изменения пока слабый;
- нет supplier timeline уровня “кто, что, когда изменил” с удобной фильтрацией;
- не оформлен отдельный подэкран таблиц как самостоятельный рабочий режим с фокусом на данные;
- каталог можно усилить массовыми действиями, приоритезацией рисков и быстрыми сценариями;
- `settings` как вкладка присутствует в структуре, но её стоит наполнить реальными настройками и guardrails.

## Target Information Architecture

### 1. Supplier Catalog

Главный экран должен отвечать на вопросы:
- с кем сейчас всё хорошо;
- у кого stale feed / плохой SLA / низкий рейтинг;
- у кого нет активной таблицы;
- кого нужно открыть первым.

Состав:
- sticky top bar: поиск, фильтры, `Добавить поставщика`, `Импорт таблицы`, `Проблемные`;
- counters: active, pending review, blocked, stale feeds, no active table;
- views: cards, compact table, risk queue;
- quick actions: открыть, таблицы, редактировать, рейтинг, архивировать.

### 2. Supplier Workspace

Внутри карточки поставщика оставить 6 зон:
- `Overview`
- `Profile`
- `Tables`
- `Analytics`
- `Logs`
- `Settings`

Роль вкладок:
- `Overview`: health snapshot, alerts, last sync, active tables, recent operator events;
- `Profile`: master data, контакты, owner, условия работы, заметки;
- `Tables`: основная рабочая зона по прайсам и live preview;
- `Analytics`: reliability, price delta, feed freshness, coverage, usage;
- `Logs`: хронология действий и изменений;
- `Settings`: rating policy, import defaults, sync policy, archive/block controls.

### 3. Tables Sub-screen

`Tables` должна стать отдельным подэкраном внутри supplier workspace, а не просто вкладкой со списком.

Состав:
- левый rail: список таблиц и версий;
- центральная зона: grid preview выбранной таблицы;
- правый inspector: детальная карточка строки, warnings, raw payload, quick edit;
- верхняя панель действий: upload, replace, activate, compare, export, bulk edit, search.

## Functional Upgrade Streams

## Stream A. Supplier Master Data

Цель:
сделать поставщика полностью управляемой сущностью.

Расширения:
- editable status lifecycle: `active`, `pending`, `blocked`, `archived`;
- owner assignment и ответственность;
- payment/delivery terms как отдельные контролируемые поля;
- internal notes + last decision note;
- manual rating c reason;
- block/archive reason с обязательным комментарием.

Definition of done:
- оператор может полностью завести и сопровождать поставщика из UI;
- любое критичное изменение оставляет понятный след в логе.

## Stream B. Tables And Live Data Operations

Цель:
сделать раздел таблиц главным операционным инструментом поставщика.

Расширения:
- отдельный режим `Table Workspace`;
- compare двух версий таблицы: added / removed / changed rows;
- indicators по качеству импорта: skipped rows, empty OEM, zero stock, duplicated rows;
- pinned columns и плотный grid для просмотра позиций;
- row-level warnings и быстрые фильтры `errors only`, `stock=0`, `price changed`, `duplicate`;
- bulk actions: category change, stock correction, SLA correction, deactivate rows later if needed.

Definition of done:
- оператор может открыть таблицу и понять её качество и содержание без Excel;
- новая версия таблицы может быть сравнена с предыдущей перед активацией.

## Stream C. Analytics

Цель:
перевести аналитику из “справочной” в “управленческую”.

Добавить на UI:
- reliability trend;
- manual vs auto rating divergence;
- freshness / sync health;
- catalog coverage by category;
- average delivery trend;
- average price deviation vs history;
- table quality score;
- supplier usage in actual request matching, если связка с order flow доступна.

Definition of done:
- по экрану аналитики видно не только состояние поставщика, но и что делать дальше.

## Stream D. Logs, Audit, Timeline

Цель:
дать прозрачную историю работы с поставщиком.

Добавить:
- unified timeline: supplier edits, rating changes, imports, replacements, bulk edits, archive/block actions;
- filters by actor, event type, table, date range;
- human-readable event payload rendering;
- short system comments for important events: `table activated`, `feed stale`, `rating reduced`.

Definition of done:
- любой спорный change можно быстро восстановить по timeline без просмотра БД.

## Stream E. UX And Visual Hierarchy

Цель:
сделать страницу быстрее в работе и визуально чище.

Изменения:
- усилить hierarchy между catalog, detail и tables mode;
- дать проблемным поставщикам приоритет через risk-first sorting;
- уменьшить визуальный шум в карточках и усилить actionable controls;
- использовать единые badge states: `active`, `pending`, `blocked`, `stale`, `draft`, `invalid`;
- в table workspace перейти к более плотному data-grid layout;
- вынести warnings и critical actions в predictable зоны.

Definition of done:
- раздел воспринимается как control-plane, а не как набор карточек.

## Recommended Delivery Plan

### Phase 1. Close UX/Data Gaps In Existing Workspace

Сделать:
- наполнить `analytics`, `logs`, `settings` реальным UI;
- добавить rating edit с reason;
- добавить archive/block reason;
- усилить overview alerts.

Результат:
- текущая архитектура начинает работать как целостный supplier workspace.

### Phase 2. Build Full Table Workspace

Сделать:
- развернуть `tables` в трёхпанельный подэкран;
- добавить row inspector, warnings, filters;
- добавить version compare и quality-center.

Результат:
- таблицы становятся самостоятельным рабочим контуром.

### Phase 3. Add Operational Analytics

Сделать:
- построить chart/cards layer поверх existing analytics API;
- добавить quality and freshness scoring;
- связать аналитику с активными таблицами и рейтингом.

Результат:
- оператор видит health, risk и динамику, а не только сырые цифры.

### Phase 4. Catalog Optimization

Сделать:
- risk queue mode;
- mass actions;
- richer sorting and saved filters;
- “needs attention” funnels.

Результат:
- каталог становится экраном приоритезации, а не просто списком.

## Acceptance Criteria

- можно добавить нового поставщика и полностью заполнить его профиль;
- можно открыть поставщика и увидеть его live status, таблицы, рейтинг, аналитику и историю;
- можно импортировать новую таблицу, открыть строку, отредактировать позицию и сравнить версию с предыдущей;
- можно без Excel понять, что находится в прайсе и какие строки проблемные;
- можно быстро найти поставщиков, требующих внимания, по stale feed, плохому SLA или низкому рейтингу;
- любое значимое изменение оставляет читаемый лог в supplier timeline.

## Risks

- compare-mode для крупных таблиц может потребовать отдельной оптимизации API и пагинации;
- quality scoring быстро разрастается, если не зафиксировать MVP набор правил;
- timeline может стать шумным без нормализации event types и payload rendering;
- UI таблиц нужно проектировать как data-heavy surface, иначе он потеряет скорость на больших прайсах.

## Recommended Next Implementation Slice

Следующий практический шаг:
- сначала сделать полноценные `Analytics`, `Logs` и `Settings`;
- затем выделить `Tables` в усиленный data-workspace с compare-mode;
- после этого вернуться к catalog и сделать risk-first triage.
