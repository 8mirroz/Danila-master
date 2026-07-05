# Задачи реализации PartsOps AI Manager v3 (HYBRID REBUILD)

## 🎯 PHASE 1 — Runtime Foundation (Выполнено ✅)
- [x] Event Store — таблица `RequestEvent` (append-only event log)
- [x] State Machine — enum `RequestState` + ALLOWED_TRANSITIONS карта переходов
- [x] Idempotency Key на эндпоинте создания заявок
- [x] PII Masking — детерминированное маскирование конфиденциальных данных клиентов
- [x] Evidence Object — SQLModel `MatchEvidence` для хранения истории матчинга
- [x] Margin Guard — проверка маржи по политикам на бэкенде
- [x] ERP Sync Log — таблица `ERPSyncLog` для синхронизации счетов с ERP
- [x] Audit Timeline API — эндпоинт получения цепочки событий заявки
- [x] Расширенная модель `PartRequest` с полями PII, VIN и комплектующих
- [x] Matching Score Formula v3 — 9-компонентная формула с весами в `matcher.py`
- [x] Покрытие тестами:
  - [x] Тесты переходов State Machine
  - [x] Тесты Margin Guard и Pricing Formula
  - [x] Тесты маскирования PII
  - [x] Тесты целостности хэш-цепочки Event Store
  - [x] Интеграционные тесты API

## 🖥️ PHASE 2 — Operational Cockpit (Выполнено ✅)
- [x] Интеграция реального списка поставщиков с API `/api/suppliers`
- [x] Выбор активной заявки и переключение в режим Cockpit Workspace
- [x] Компонент `AuditTimeline` с отображением хэш-цепочки и лога
- [x] Компонент `SupplierMatrix` с отображением предложений и детального 9-компонентного Score-отчета
- [x] Компонент `PricingCalculator` со слайдерами маржи, логистикой и проверкой Margin Guard
- [x] Интерактивная смена статусов через State Machine с указанием причин ручного аппрува
- [x] Сборка React фронтенда без ошибок компиляции TypeScript

## 🤖 PHASE 3 — Agent Graph (LangGraph Swarm) (Выполнено ✅)
- [x] Интеграция Intake Classifier (Spam/Validity filter)
- [x] Интеграция VIN Inspector Agent (Scans & decodes VIN via LLM/Regex)
- [x] Parts Extractor Swarm с интеграцией NVIDIA NIM Llama 3.1
- [x] Асинхронный опрос поставщиков (Scatter-Gather) с наполнением Evidence Graph
- [x] Pricing Guard Agent (Margin checking & anomaly alerts in graph)
- [x] Тестовое покрытие всех узлов графа в `test_agents.py`

## 🧠 PHASE 4 — Financial and Supplier Intelligence (Выполнено ✅)
- [x] Добавление append-only лога `PriceHistoryLedger` в модели
- [x] Добавление журнала оценок `SupplierReliabilityLog` в модели
- [x] Реализация расчета 9-дневного медианного показателя цен и запись ценовых обновлений в `intelligence.py`
- [x] Реализация системы оценок риска возвратов по категориям запчастей
- [x] Автоматическая генерация черновиков Purchase Orders (PO), сгруппированных по поставщикам
- [x] Интеграция накопленной статистики цен и рисков возврата в Pricing Guard ноду агента
- [x] Тестовое покрытие аналитических функций в `test_intelligence.py`
