# 🛠 Hermes ↔ PartsOps — Integration Plan

Цель: превратить Hermes из generic-агента в рабочий инструмент именно под этот проект. Чтобы каждая сэссия по `partsops-ai-manager` стартовала уже с правилами, ран-буком и подцеплкой к Obsidian vault, без повторных разъяснений.

Контекст на сейчас:
- `/Users/user/projects/Danila master/.agents/AGENTS.md` есть, но только про sync. Под проектный запуск — нет.
- В `partsops-ai-manager/` нет `AGENTS.md` / `.hermes/project.yaml`.
- Проектных skills в `~/.hermes/profiles/zera/skills/` нет — всё generic.
- Все cron-задачи в `~/.hermes/profiles/zera/cron/` про Zera в целом, ни одна не привязана к PartsOps.
- Vault `DM obs/` уже структурирован (00..06 секции) и имеет скрипт `scripts/sync_obsidian.sh` → Python через `obsidian_project`.

Принцип: каждый пункт имеет проверяемое DoD — иначе не “готово”.

---

## Phase 0 — Инвентаризация и гигиена (≈30 мин)

Что нельзя начинать интеграцию, не убрав шум в корне:

- [ ] Удалить корневой мусор, к hermes не относящийся: `RightPanel.tsx`, `triageStats.value`, `llm.py` (там строка с patch-командой) — это артефакты прошлой правки, не актив.
- [ ] Решить судьбу `partsops_structure_logic_patch.diff` и `.safe.diff` в корне: либо применить, либо удалить, не оставлять как “припаркованный”.
- [ ] `partsops-ai-manager/.gitignore` проверить: точно ли исключаются `webui.db`, `venv/`, `__pycache__/`, `.bak` файлы.
- [ ] `partsops_bot/` — отдельный git-репо с `bot.py` + `config.py`. Решить: оставить как есть, либо принять в общий репо Danila master.

DoD: `git status` показывает только осознанные untracked, никаких мусорных файлов.

---

## Phase 1 — Проектный AGENTS.md + переменные окружения (≈45 мин)

Прямой смысл: hermes автоматически подцепляет корневой `AGENTS.md` сэссии, если он есть в workdir. Сейчас он один — про sync. Этого мало.

- [ ] Создать `partsops-ai-manager/AGENTS.md` со спецификой приложения:
  - запуск: `. venv/bin/activate && uvicorn main:app --reload --port 8000`
  - тесты: `pytest tests/ -q`
  - lint/format: `ruff check . && ruff format --check .`
  - критические секреты и откуда они грузятся (`PARTSOPS_TG_TOKEN` из `~/.hermes/profiles/zera/.env.partsops` через `bot/config.py`).
  - правила: tenant_id обязателен, state machine единственный путь транзишенов, LLM только через budget_guard, никаких лонг-транзакций поверх `requests`.
- [ ] В корневом `.agents/AGENTS.md` оставить только правила sync и общие правила. Избегать overlap с проектным.
- [ ] Обновить `.env.example` (или создать) в `partsops-ai-manager/`: `DATABASE_URL=sqlite:///./database.db`, `PARTSOPS_API_TOKEN=`, `LLM_PROVIDER=stub` для local-dev. Не выкладывать `bot.py`-секреты сюда.
- [ ] Положить `partsops-ai-manager/README.md` с 30 секундным how-to-run.

DoD: `cat partsops-ai-manager/AGENTS.md | grep -E "uvicorn|pytest|tenant_id"` — 3 совпадения. Любая новая сэссия в этом workdir автоматом видит эти правила.

---

## Phase 2 — Skills для Hermes под PartsOps (≈2 ч)

Skill — это persistent-инструкция, которую я гружу через `skill_view` по имени. Сейчас под проект ничего нет, поэтому каждый раз “с нуля”.

- [ ] `partsops-dev-runbook` — единственный навыг, который нужен hermes для ежедневной работы в проекте:
  - Триггер: любой запрос “исправь”, “добавь endpoint”, “запусти тесты”, “почему не стартует backend”.
  - Содержимое: дерево `partsops-ai-manager/`, что есть в `app/automation/`, где API (`main.py` пока runtime-комбайн, планируется рефактор), как делать запросы в БД через SQLModel, как устроен RBAC (`rbac.py`: Bearer token + X-Tenant-ID), как трогать `event_store.py` без поломки tenant-scoped hash chain.
  - Pitfalls: long transactions поверх LLM, подмена роли через headers без Bearer, fake file parsing в `RightPanel.tsx`, hardcoded metrics в overview.
  - Verification commands: `curl localhost:8000/api/health`, `pytest -q app/automation/`, `ruff check app/`.
- [ ] `partsops-code-review` — для самопроверки перед сдачей: RBAC spoofing, tenant isolation, evidence tampering, idempotency_key, dry_run, fallback на 501 для optional модулей.

DoD: `skill_view partsops-dev-runbook` возвращает осмысленный текст, я могу загрузить его за 1 токен-вызов и не пересказывать каждый раз дерево проекта пользователю.

---

## Phase 3 — Cron-обвязка под PartsOps (≈1.5 ч)

Чтобы проект жил без участия пользователя: smoke проверки, sync_obsidian при изменениях, периодический аудит-дайджест.

- [ ] `partsops-nightly-smoke` — каждый день 23:30 локального времени:
  - workdir = `/Users/user/projects/Danila master`.
  - Перейти в `partsops-ai-manager`, активировать venv, прогнать `pytest -q tests/` и `ruff check .`, поднять `uvicorn` health-check на 5 сек.
  - Результат записать в `DM obs/05-reports/nightly-smoke-<date>.md`. Если падения — `deliver: telegram` (не `origin`, чтобы не спамить CLI).
- [ ] `partsops-sync-on-change` — событийный watchdog через `context_from`:
  - Первая задача: `git -C /Users/user/projects/Danila master diff --name-only HEAD` собирает дельту за час, сохраняет в кэш.
  - Вторая задача: читает кэш, если есть изменения в `partsops-ai-manager/` или `partsops_bot/` — дёргает `scripts/sync_obsidian.sh --stage <из SYSTEM_MANIFEST>`. Подавить если в кэше пусто.
- [ ] `partsops-weekly-audit` — понедельник 10:00:
  - Считает метрики по `database.db`: сколько requests в статусах, сколько failed events, сколько LLM-запросов за неделю.
  - Пишет сводку в `DM obs/05-reports/partsops-audit-<date>.md`. Telegram delivery.

DoD: `cronjob action=list` показывает три новых job’а с правильным `workdir`, `deliver=telegram`. Smoke прогоняется один раз вручную (action='run') и пишет файл.

---

## Phase 4 — Obsidian ↔ Hermes двусторонний мост (≈1 ч)

Сейчас sync односторонний: bash-скрипт → vault. Hermes пока не “видит”, что в vault написано. Сделать зеркало.

- [ ] Создать `partsops-ai-manager/.hermes/project.yaml`:
  ```
  project: PartsOps AI Manager
  root: partsops-ai-manager/
  vault_alias: partsops
  vault_path: ../DM obs
  plan_dir: ../DM obs/01-planning
  report_dir: ../DM obs/05-reports
  memory_dir: ../DM obs/04-memory
  ```
- [ ] Skill `partsops-vault-aware-session` — при старте сэссии в workdir читать `project.yaml`, подсасывать `DM obs/01-planning/current-plan.md` и `roadmap.md` в контекст.
- [ ] Проверить `scripts/sync_status.sh`: сейчас он пишет только `current_stage` в `00-overview.md`. Расширить: добавить ссылки на 3 новых отчёта (`nightly-smoke`, `weekly-audit`, `partsops-repo-audit`).

DoD: новая сэссия в workdir проекта при первом сообщении уже видит план, последний отчёт и знает, что делается в проекте.

---

## Что **не** делаем на этой фазе

Сознательно оставляем за скоупом:
- Рефактор `main.py` в routers/services (вариант 4 из твоего вопроса).
- Реальный file-upload backend (вариант 2) — это самостоятельная задача после Phase 1–2.
- Любые supplements к `partsops_bot/` — это отдельный git, hermes обвязку под него делаем только в Phase 0 (решить судьбу).
- Изменения в cron self-evolution / morning-briefing — это generic Zera, не трогать.

---

## Порядок исполнения

1. Phase 0 → 30 мин, мусор и `.gitignore`.
2. Phase 1 → 45 мин, AGENTS.md + env.
3. Phase 4 (каркас) → 30 мин, `project.yaml` + skill.
4. Phase 2 → 2 ч, два проектных skill‘а.
5. Phase 3 → 1.5 ч, три cron-job‘а.
6. Phase 4 (mirror) → 30 мин финальной доводки.
7. Smoke end-to-end: одна ночная smoke + одна сэссия в workdir проекта с автозагрузкой контекста.

Итого: ~6.5 часов чистой работы. После этой фазы hermes перестаёт быть “агентом, который нужно заново вводить в курс дела”, и становится инструментом, который **знает** PartsOps.
