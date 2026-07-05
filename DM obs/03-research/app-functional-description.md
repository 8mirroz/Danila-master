# PartsOps AI Manager — функциональное описание приложения

## 1. Назначение продукта

`PartsOps AI Manager` — это operational control plane для обработки заявок на автозапчасти. Система связывает intake-запросы, AI-разбор текста, подбор деталей, поиск и ранжирование поставщиков, расчет цены, контроль маржи, аудит событий и подготовку ERP-документов.

Главная задача продукта:
- быстро перевести сырую клиентскую заявку в контролируемое закупочное решение;
- показать оператору не только ответ, но и evidence, риски, confidence и следующий лучший action;
- удержать процесс в рамках policy: PII safety, state machine, margin guard, audit trail.

## 2. Архитектурная логика

Приложение состоит из двух основных слоев.

### 2.1 Backend control plane

Реализован на `FastAPI` и отвечает за:
- прием заявок;
- маскирование PII до агентного слоя;
- запуск intake workflow;
- хранение заявок и статусов;
- immutable event store с SHA-256 hash chain;
- валидацию status transition;
- каталог поставщиков и матчинг деталей;
- расчет pricing evidence и draft invoice;
- audit и ERP-связанные ответы.

Ключевые backend-модули:
- `main.py` — API и orchestration;
- `agents.py` — intake workflow через `LangGraph`;
- `matcher.py` — 9-компонентный scoring подбора деталей;
- `pricing.py` — pricing formula, margin policy, anomaly checks;
- `state_machine.py` — правила переходов и инварианты;
- `event_store.py` — event emission и audit chain verification;
- `pii.py` — маскирование персональных данных;
- `models.py` — доменная модель заявки, статусов, событий, evidence и ERP-log.

### 2.2 Frontend admin cockpit

Реализован на `React 19 + TypeScript + Vite + Tailwind/CSS variables`.

Frontend разбит на 3 рабочие зоны:
- `left panel` — supplier workspace;
- `center panel` — overview и workspace выбранной заявки;
- `right panel` — live triage queue.

Frontend не просто отображает данные. Он является операторской оболочкой вокруг backend-state и должен поддерживать паттерн:

`queue -> inspect -> compare -> approve/escalate -> draft ERP`.

## 3. Бизнес-поток приложения

### 3.1 Intake

1. Оператор или внешний источник отправляет текст заявки.
2. Backend принимает `source`, `text`, `customer_name`, optional PII и priority.
3. PII маскируется до того, как данные уходят в агентный слой.
4. Intake workflow пытается:
   - извлечь детали;
   - провалидировать, что хотя бы одна деталь распознана и может быть сопоставлена.
5. Если validation passed, заявка получает `PART_EXTRACTION`.
6. Если validation failed, заявка уходит в `NEEDS_CLARIFICATION`.
7. В event store пишутся:
   - `REQUEST_RECEIVED`;
   - `PART_INTENT_EXTRACTED`;
   - `STATE_CHANGED`.

### 3.2 Matching и supplier decisioning

1. Для каждой распознанной детали система ищет позиции в supplier catalog.
2. Каждая позиция получает итоговый match score.
3. Score раскладывается на explainable breakdown.
4. Оператор в UI видит не только кандидатов, но и доказательную структуру решения.

### 3.3 Pricing и invoice draft

1. Для найденных деталей выбираются лучшие офферы.
2. Считаются purchase cost, buffers, margin и VAT.
3. Проверяется margin policy.
4. Если политика соблюдена, доступно draft invoice action.
5. При создании draft invoice:
   - формируется pricing evidence;
   - создается invoice record;
   - в event store пишется `ERP_DOCUMENT_CREATED`.

### 3.4 Audit и control

Каждое важное действие должно иметь проверяемый след:
- кто инициировал действие;
- когда оно произошло;
- какой payload был записан;
- сохранена ли целостность цепочки событий.

Это дает explainability, разбор инцидентов и защиту от тихих изменений статуса.

## 4. Основные алгоритмы

## 4.1 Алгоритм intake parsing

Источник: `agents.py`

Логика:
- сначала вызывается `parse_request_with_llm`;
- если LLM вернул части, они нормализуются в массив `{ name, quantity }`;
- если LLM не сработал, включается keyword fallback;
- если ничего не найдено, создается `"Неизвестная деталь"`.

Рабочим считается, когда:
- система извлекает хотя бы одну деталь в нормализованной структуре;
- quantity приведено к integer;
- нераспознанный запрос не ломает pipeline, а переводится в controllable fallback state.

Готовым считается, когда:
- есть LLM path и deterministic fallback;
- ошибки парсинга не приводят к падению запроса;
- доля заявок с `NEEDS_CLARIFICATION` контролируема и измеряется.

## 4.2 Алгоритм validation

Источник: `agents.py`

Логика:
- для каждой извлеченной детали вызывается `match_part`;
- если у хотя бы одной детали найден `best_match`, validation считается `PASSED`;
- иначе `FAILED`.

Связи:
- влияет на стартовый статус заявки;
- определяет, попадет ли кейс сразу в рабочий pipeline или в clarifications.

Рабочим считается, когда:
- известные детали проходят валидацию;
- неизвестные не проходят ложно;
- результат детерминирован для одинаковых входов при одинаковой базе.

## 4.3 Алгоритм 9-компонентного matching score

Источник: `matcher.py`

Итоговый score состоит из:
- `OEM exact` — 30%;
- `brand/article` — 18%;
- `normalized name` — 14%;
- `vehicle compatibility` — 12%;
- `side/position` — 8%;
- `quantity pack` — 6%;
- `language synonym` — 5%;
- `historical acceptance` — 4%;
- `supplier data quality` — 3%.

Что делает алгоритм:
- нормализует строку запроса;
- выявляет OEM/brand/vehicle/side signals;
- считает fuzzy similarity;
- добавляет supplier reliability в итог;
- отбрасывает кандидатов ниже `threshold`.

С чем связан:
- с UI-компонентом `SupplierMatrix`;
- с качеством auto-suggestion;
- с explainability: breakdown должен объяснять, почему победил оффер.

Рабочим считается, когда:
- лучшие кандидаты действительно ранжируются выше слабых;
- score breakdown объясним человеку;
- порог фильтрации не пропускает очевидный мусор.

Готовым считается, когда:
- веса валидированы на реальных кейсах;
- есть замер precision/acceptance на golden set;
- neutral scoring не скрывает реальных конфликтов по OEM/brand/vehicle.

## 4.4 Алгоритм pricing

Источник: `pricing.py`, частично UI `PricingCalculator.tsx`

Backend formula:

`client_price = purchase_price + logistics_cost + supplier_risk_buffer + urgency_buffer + target_margin + tax`

Ключевые правила:
- `default margin` — 12%;
- `original_bmw` — 10%;
- `non_returnable` — 18%;
- `high_risk_supplier` — 20%;
- `aftermarket_safety_critical` — 22%.

Дополнительно:
- risk buffer зависит от supplier reliability;
- urgency buffer зависит от уровня срочности;
- проверяется price anomaly относительно `historical_median_price_90d`;
- рассчитывается `auto_approve_allowed`.

Текущее состояние UI:
- frontend калькулятор использует MVP-логику с logistics, urgency и margin override;
- backend invoice endpoint сейчас применяет более упрощенный markup path (`1.30`) и margin guard.

Это важно:
- UI и backend pricing logic сейчас концептуально связаны, но еще не полностью унифицированы;
- документально это нужно считать зоной выравнивания, а не завершенной консистентностью.

Рабочим считается, когда:
- цена считается без ошибок;
- margin violations блокируют draft action;
- оператор понимает, из чего сложилась цена.

Готовым считается, когда:
- UI formula и backend formula совпадают;
- policy-driven pricing не зависит от hidden constants;
- anomaly и auto-approve логика отображаются в интерфейсе явно.

## 4.5 Алгоритм state machine

Источник: `models.py`, `state_machine.py`

State machine описывает допустимые переходы заявки от `NEW` до `CLOSED`, включая ручные и аварийные ветки:
- `NEEDS_CLARIFICATION`;
- `MANUAL_REVIEW`;
- `REWORK`;
- `ERP_SYNC_FAILED`;
- `SUPPLIER_ISSUE`;
- `RETURN_CASE`;
- `FINANCE_REVIEW`.

Что делает:
- запрещает нелегальные переходы;
- может проверять инварианты для целевых состояний.

Критичные инварианты:
- `INVOICE_DRAFTED` требует pricing evidence, ERP quotation ref и passed margin policy;
- `SENT_TO_CLIENT` требует invoice ref;
- `PAID` требует payment ref;
- `CLOSED` требует `audit_chain_complete=True`.

Текущее состояние:
- endpoint ручного transition использует `validate_transition`, но без `strict_invariants=True`;
- значит граф переходов контролируется, а часть бизнес-инвариантов пока не enforce-ится жестко в runtime.

Рабочим считается, когда:
- нелегальный переход получает отказ;
- status меняется только по разрешенному маршруту;
- audit trail фиксирует изменение.

Готовым считается, когда:
- инварианты включены в реальном transition path;
- UI показывает только разрешенные next states;
- terminal states защищены от случайного re-open.

## 4.6 Алгоритм audit chain

Источник: `event_store.py`

Для каждого события:
- генерируется `event_id`;
- берется `previous_event_hash`;
- строится canonical JSON event payload;
- считается `SHA-256`;
- событие сохраняется append-only.

Проверка integrity:
- события читаются по порядку;
- каждый `previous_event_hash` должен совпадать с hash предыдущего события.

С чем связан:
- `AuditTimeline`;
- доверие к системе;
- расследование ручных override и ERP side effects.

Рабочим считается, когда:
- события не теряются;
- chain верифицируется;
- любой разрыв детектируется адресно.

Готовым считается, когда:
- timeline покрывает все ключевые lifecycle actions;
- audit chain status виден оператору и внутреннему аудиту;
- нет silent writes вне event model.

## 4.7 Алгоритм PII masking

Источник: `pii.py`

Что маскируется:
- phone;
- email;
- VIN;
- customer name.

Правило:
- до агентного/LLM слоя доходят только masked значения;
- логирование также должно работать через redaction-safe path.

Рабочим считается, когда:
- агент не видит сырой PII;
- маскировка стабильна и не ломает workflow.

Готовым считается, когда:
- весь intake и логирование проходят через единую PII-safe дисциплину;
- есть тесты на phone/email/VIN/name edge cases.

## 5. UI/UX модель

## 5.1 Главный UX-паттерн

Приложение должно поддерживать короткий операторский цикл:

`увидеть давление очереди -> открыть кейс -> понять, что система нашла -> сравнить поставщиков -> оценить риск и маржу -> перевести статус или собрать invoice`.

UI не должен быть generic dashboard. Он должен отвечать на 5 вопросов:
- что происходит сейчас;
- какой кейс самый срочный;
- насколько система уверена;
- что заблокировано;
- какое следующее действие безопасно.

## 5.2 Визуальная модель

По текущему design system guide:
- shell, workspace и focused panels должны отличаться по слою и назначению;
- все цвета и радиусы живут через CSS tokens;
- интерфейс должен быть data-dense и explainable;
- каждая крупная карточка обязана либо объяснять состояние, либо вести к действию.

Текущий стиль:
- темный premium shell;
- layered surfaces;
- акцентные цвета для confidence, risk, approval и health;
- `Manrope` как основная типографика;
- glass-like control-plane framing.

## 6. Экранная карта и описание функций

## 6.1 Top Bar / Control Header

Источник: `App.tsx`

Функции:
- branding и positioning продукта;
- индикация live environment;
- отображение состояния ERP sync;
- глобальные точки входа: `Overview`, `Security`, `Observability`, `Command Center`.

С чем связан:
- с глобальной навигацией;
- с системным health;
- с ощущением control plane.

Текущее состояние:
- `Overview` возвращает в операционный обзор;
- control header должен показывать environment, backend health, queue counters и быстрые входы в workflow-экраны;
- глобальные действия обязаны сохранять локальный контекст выбранной заявки.

Рабочим считается, когда:
- header показывает реальный environment и global status;
- главная кнопка возвращает в overview;
- глобальные действия не ломают локальный контекст.

Готовым считается, когда:
- все header actions подключены к реальным экранам или drawer/workspace;
- health и sync indicators работают от live data, а не от hardcoded string.

## 6.2 Overview Screen

Источник: `App.tsx`

Назначение:
- дать оператору мгновенное понимание общей operational picture.

Текущие блоки:
- hero statement;
- KPI metrics;
- workflow lanes;
- urgent cases.

Текущие метрики:
- `System confidence`;
- `Approval pressure`;
- `Evidence packs`;
- `Protected margin`.

Связи:
- overview должен агрегировать queue pressure, approvals, evidence coverage, risk и actionability;
- связан с triage rail, supplier intelligence и рабочими статусами заявок.

Текущее состояние:
- overview должен собираться из live/derived counts по `requests`, `suppliers` и `invoices`;
- статические KPI допустимы только как fallback при `partial` или `stale` данных.

Рабочим считается, когда:
- оператор за 2-3 секунды видит общую ситуацию;
- ключевые блоки читаются без перехода в кейс;
- urgent cases ведут к реальному inspect path.

Готовым считается, когда:
- KPI считаются от живых backend-данных;
- каждый overview widget имеет action path;
- отражены states `loading`, `empty`, `stale`, `blocked`, `synced`.

## 6.3 Left Panel — Supplier Workspace

Источник: `App.tsx`

Функции:
- загрузка списка поставщиков через `/api/suppliers`;
- поиск по `name` и `specialization`;
- краткая supplier segmentation:
  - active suppliers;
  - top tier;
  - needs review;
- просмотр карточек поставщиков с reliability, contact, delivery и category.

С чем связан:
- с supplier intelligence;
- с оценкой reliability;
- с decisioning на этапе offer comparison.

Текущее состояние:
- список живой;
- выбор поставщика не открывает отдельный detail state;
- кнопки add/filter пока декоративные.

Рабочим считается, когда:
- поставщики грузятся;
- поиск стабильно фильтрует;
- reliability и SLA видны сразу.

Готовым считается, когда:
- есть фильтры по freshness, category, SLA, risk;
- supplier card ведет к evidence / offer / feed diagnostics;
- stale supplier feed виден как отдельный operational state.

## 6.4 Right Panel — Request Triage Rail

Источник: `RightPanel.tsx`

Функции:
- загрузка очереди заявок через `/api/requests`;
- quick intake через textarea;
- отправка новой заявки на `/api/requests`;
- выбор заявки для центрального workspace;
- отображение статуса, part summary, source и time.

С чем связан:
- это основной вход в ежедневную работу оператора;
- связывает intake, queue management и inspection.

Текущее состояние:
- triage stats должны считаться от реальной очереди и сортироваться по urgency / SLA / blocker presence;
- quick intake допускает file drop и textarea, но не подменяет backend state фиктивными значениями.

Рабочим считается, когда:
- новая заявка создается;
- список обновляется;
- выбранная карточка открывает кейс в center panel.

Готовым считается, когда:
- rail сортируется по urgency/confidence/SLA;
- stats считаются от реальной очереди;
- есть статусы blocked/escalated/invoice-ready/awaiting-clarification.

## 6.5 Request Workspace Header

Источник: `App.tsx`

Появляется после выбора заявки.

Функции:
- показывает request id, customer context, masked PII и текущий status;
- возвращает пользователя в overview;
- задает контекст для дальнейших действий.

С чем связан:
- с карточкой запроса;
- с безопасной работой с клиентскими данными;
- с операторским пониманием, какой кейс открыт сейчас.

Рабочим считается, когда:
- выбранный кейс визуально и логически активен;
- header совпадает с фактическим request state.

Готовым считается, когда:
- кроме status видны blocker, owner, ETA-like urgency cue и recommended next action;
- если live confidence недоступна, UI показывает explicit unavailable/partial state, а не fake percentage.

## 6.6 Customer Profile Card

Источник: `App.tsx`

Функции:
- показывает `customer_name`, masked phone, masked email, priority.

Связи:
- берет данные из `PartRequest`;
- зависит от PII masking discipline.

Рабочим считается, когда:
- поля есть и не раскрывают raw PII;
- fallback значения безопасны.

Готовым считается, когда:
- карта знает channel/source/customer segment;
- priority влияет на downstream sorting и action prompts.

## 6.7 Vehicle Context Card

Источник: `App.tsx`

Функции:
- показывает masked VIN;
- make/model;
- количество частей;
- source заявки.

Связи:
- используется для supplier matching и compatibility reasoning.

Текущее состояние:
- make/model часто пустые, потому что intake их пока не наполняет стабильно.

Рабочим считается, когда:
- карта корректно показывает то, что уже есть в request;
- parts count совпадает с `parts_json`.

Готовым считается, когда:
- vehicle confidence и VIN validity считаются и отображаются явно;
- compatibility риски видны до этапа invoice draft.

## 6.8 Tab Strip

Источник: `App.tsx`

Табы:
- `Cockpit workspace`;
- `Audit timeline`;
- `State transitions`.

Назначение:
- разделить операционную работу, аудит и ручное вмешательство;
- не смешивать обзор данных и административные override.

Рабочим считается, когда:
- переключение между вкладками стабильно;
- выбранная вкладка отражает текущий режим работы.

Готовым считается, когда:
- табы показывают counters/state badges;
- недоступные режимы скрыты или disabled согласно request state и roles.

## 6.9 Supplier & Match Evidence Matrix

Источник: `SupplierMatrix.tsx`

Функции:
- показывает tabs по извлеченным деталям;
- по клику делает `GET /api/catalog/search?q=...`;
- строит таблицу candidate offers;
- показывает цену, stock, delivery, supplier, итоговый score;
- справа раскрывает `Score Evidence` по 9 компонентам.

Это один из самых важных модулей продукта, потому что именно он объясняет, почему система предлагает конкретную деталь.

С чем связан:
- `matcher.py`;
- supplier reliability;
- explainability и confidence;
- будущий manual approval.

Рабочим считается, когда:
- поиск по детали возвращает кандидатов;
- breakdown переключается по выбранной строке;
- оператор видит, почему score высокий или низкий.

Готовым считается, когда:
- можно зафиксировать выбранный offer в request evidence;
- есть явные conflict notes по OEM/brand/vehicle mismatch;
- low-confidence match требует manual confirmation.

## 6.10 Pricing Calculator & Margin Guard

Источник: `PricingCalculator.tsx`

Функции:
- input logistics cost;
- настройка target margin;
- выбор urgency;
- расчет subtotal, VAT и total;
- отображение margin violation;
- action `Draft Invoice in ERPNext`.

С чем связан:
- pricing policy;
- invoice generation endpoint;
- коммерческая управляемость и защита маржи.

Текущее состояние:
- UI умеет запрещать draft при нарушении margin policy;
- invoice generation вызывает `/api/erp/invoice/{request_id}`;
- локальный UI-расчет не полностью равен backend pricing engine.

Рабочим считается, когда:
- изменение inputs пересчитывает результат;
- нарушение policy визуально заметно;
- draft action возвращает invoice number.

Готовым считается, когда:
- pricing evidence сохраняется в request;
- UI показывает backend-confirmed formula, не только локальную оценку;
- draft доступен только при согласованном request state.

## 6.11 Audit Timeline & Hash Chain

Источник: `AuditTimeline.tsx`

Функции:
- загружает `/events` и `/audit`;
- показывает event list по времени;
- показывает actor, payload и shortened hash;
- показывает verified / compromised состояние цепочки.

С чем связан:
- `event_store.py`;
- безопасностью изменений;
- explainability и расследованием инцидентов.

Рабочим считается, когда:
- timeline грузится;
- refresh обновляет данные;
- integrity status соответствует backend check.

Готовым считается, когда:
- все ключевые lifecycle actions действительно попадают в timeline;
- payload human-readable и полезен оператору;
- broken chain считается критическим operational incident.

## 6.12 State Transition Controls

Источник: `App.tsx`

Функции:
- ручной запуск переходов:
  - `PART_EXTRACTION`;
  - `MANUAL_REVIEW`;
  - `APPROVED`;
  - `CANCELLED`;
- запрос причины через prompt;
- отправка `POST /api/requests/{id}/transition`.

С чем связан:
- state machine;
- audit trail;
- режимом admin intervention.

Текущее состояние:
- модуль должен использовать backend-driven allowed_next list;
- hardcoded transitions допустимы только как визуальный fallback при отсутствии ответа API.

Рабочим считается, когда:
- разрешенный переход проходит;
- запрещенный отклоняется с ошибкой;
- причина фиксируется в audit event.

Готовым считается, когда:
- набор действий строится динамически от backend state machine;
- destructive transitions требуют stronger confirmation;
- UI показывает, почему переход доступен или недоступен.

## 7.4 UX scenario validation matrix

Канонические сценарии, по которым валидируется cockpit:

- `Intake`: оператор создает заявку из textarea или файла, после чего кейс появляется в triage rail и открывает workspace.
- `Queue triage`: overview и right rail показывают pressure, urgent work, blocked cases и next action без перехода в detail.
- `Supplier inspect`: выбранная поставщицкая карточка ведет к comparison/evidence view, а stale feed или low reliability видны как state, а не как скрытая ошибка.
- `Match decision`: в матчинге видны recommended offer, альтернативы и conflict/risk notes; выбор предложения записывается в evidence.
- `Pricing approval`: pricing stage блокирует draft invoice до согласования и использует backend allowed transitions.
- `Invoice draft`: после allowed approval actions доступен draft ERP action и виден invoice-ready state.
- `Audit review`: timeline и hash/audit surfaces показывают sequence, actor и integrity state.
- `Empty/failed/partial`: отсутствие данных не маскируется, UI обязан показать empty, failed, partial, stale или blocked явно.

## 7. Интерфейсные метрики

Ниже метрики, по которым интерфейсы этого продукта нужно считать качественными.

## 7.1 Метрики восприятия и UX

- `Time to first understanding`: за сколько секунд оператор понимает общее состояние системы на overview.
  Рабочий ориентир: до 5 сек.
  Готовый уровень: 2-3 сек.

- `Time to inspect case`: время от выбора карточки в очереди до понимания, что с кейсом делать дальше.
  Рабочий ориентир: до 20 сек.
  Готовый уровень: до 10 сек.

- `Decision clarity rate`: доля кейсов, где оператор может назвать следующий action без дополнительных внешних проверок.
  Рабочий ориентир: 70%+.
  Готовый уровень: 90%+.

- `Explainability coverage`: доля ключевых решений, у которых есть reason/evidence/confidence.
  Рабочий ориентир: для matching и pricing.
  Готовый уровень: для matching, pricing, transitions, audit, supplier risk.

## 7.2 Операционные метрики

- `Queue freshness`: возраст данных в triage rail.
- `Approval pressure`: количество кейсов, требующих ручного sign-off.
- `Blocked case count`: число кейсов в clarification/manual review/error ветках.
- `Protected margin rate`: доля draft invoice без margin violations.
- `Supplier reliability exposure`: доля выбранных офферов от low-reliability suppliers.
- `Audit integrity rate`: доля кейсов с валидной event chain.

## 7.3 Метрики готовности интерфейсного состояния

Каждый ключевой экран должен иметь явные состояния:
- `loading`;
- `empty`;
- `partial`;
- `stale`;
- `failed`;
- `blocked`;
- `validated`;
- `invoice-ready`.

Экран считается готовым только если эти состояния:
- спроектированы визуально;
- семантически различимы;
- не требуют чтения консоли, чтобы понять, что происходит.

## 8. Дизайн-стиль и кодовая дисциплина

## 8.1 Дизайн-стиль

Целевой стиль:
- premium operational cockpit;
- не generic admin dashboard;
- высокая информационная плотность;
- сильная иерархия shell/workspace/panel;
- акцент на trust, control, evidence, urgency.

Текущие сильные стороны:
- хороший темный shell;
- token-based color system;
- layered surfaces;
- уже есть задел под explainability.

Что еще не доведено до готовности:
- часть действий декоративна;
- часть overview-метрик hardcoded;
- system health и queue analytics пока не живые;
- состояния данных проработаны не везде.

## 8.2 Кодовая дисциплина

Frontend:
- текущая композиция построена как один `App.tsx` orchestration layer + feature components;
- data fetching выполняется локально внутри компонентов;
- CSS tokens централизованы в `src/index.css`.

Backend:
- логика разнесена по специализированным модулям;
- API достаточно прозрачно отражает доменные сущности;
- event-sourcing и state machine уже формируют правильную архитектурную основу.

Зона риска:
- часть runtime-правил существует в модели/документации, но еще не в полном enforce-режиме;
- frontend и backend pricing semantics пока расходятся;
- некоторые UI-фичи пока ближе к premium mock than fully operational tool.

## 9. Definition of Done по системе в целом

Приложение можно считать рабочим, когда:
- можно создать заявку и увидеть ее в triage rail;
- intake parsing не рушит поток;
- выбранная заявка открывается в workspace;
- supplier matches загружаются;
- pricing calculator считает сумму и блокирует violation;
- audit timeline показывает события;
- ручной transition проходит только по разрешенному пути.

Приложение можно считать готовым как production-grade operational cockpit, когда:
- все ключевые overview и queue-метрики живые;
- matching, pricing и approval показывают explainability;
- state machine и бизнес-инварианты enforce-ятся полностью;
- UI знает реальные status states, а не hardcoded shortcuts;
- supplier, request, invoice и audit flows связаны в единый decision loop;
- оператор может завершить полный цикл без обращения к внешним инструментам для базового кейса;
- система устойчива к ambiguous input, low-confidence match, margin violation и ERP failure;
- все ключевые данные, действия и ошибки видны в интерфейсе, а не скрыты в backend.

## 10. Практический вывод по текущему состоянию

Сейчас `PartsOps AI Manager` уже является хорошим каркасом control plane:
- backend содержит сильную доменную основу;
- UI уже раскладывает продукт на правильные зоны ответственности;
- explainability, audit и margin control заложены на уровне архитектуры.

Но до полностью готового продукта еще нужно довести:
- live metrics вместо статических;
- динамические allowed actions;
- полное выравнивание pricing UI и backend;
- полноценные data states;
- deeper supplier/request/invoice linkage.

Итого:
- как концепт и рабочий прототип система уже состоятельна;
- как production-ready cockpit она близка архитектурно, но еще не завершена операционно.
