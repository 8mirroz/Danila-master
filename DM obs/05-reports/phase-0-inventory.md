# Phase 0 — Inventory & Hygiene

Дата: 2026-07-05
Статус: в процессе (decision gates висят)

## 🔍 Snapshot timestamp

```
$ ls -la /Users/user/projects/Danila master
total 2176
drwxr-xr-x  29 user  staff     928 Jul  5 01:47 .
drwxr-xr-x@ 44 user  staff   1408 Jul  4 21:18 ..
.DS_Store (8196b)
.agents/AGENTS.md (1199b)
.github/workflows/  (empty)
.git/hooks/  ← пустой, см. surprise #1
.playwright-cli/
.playwright-mcp/
.pytest_cache/
.vscode/settings.json (6459b)
DM obs/  (Obsidian vault)
RightPanel.tsx (78b)
ai_assistant_operational_control.html (30022b)
get_app_tsx.py (1662b)
get_app_tsx_v2.py (1405b)
llm.py (96b)
partsops-ai-manager/  (главное приложение)
partsops_agent_os_devpack.zip (31124b)
partsops_agent_os_devpack/  (devpack)
partsops_bot/  (отдельный git)
partsops_structure_logic_patch.diff (25070b)
partsops_structure_logic_patch.safe.diff (21490b)
recover_app.py (2083b)
refcode.html (155824b)
refcode.html.bak (146935b)
scripts/{sync_obsidian.py, sync_obsidian.sh, sync_status.sh}
triageStats.value (47b)
uml.txt (0b)
webui.db (651264b)
```

## ⚠ Surprise #1 — ноль git в Danila master

`.git/` директория существует, но **внутри только `hooks/` и ничего больше**:
```
.git/hooks/   ← пустая
.git/HEAD     ← не существует
.git/config   ← не существует
```

`git status` → `fatal: not a git repository`.

В корне Danila master **нет git-репозитория**. Только `.git/hooks/` (видимо, осталась от давней инициализации).

Проект `partsops_bot/` у себя имеет полноценный `.git` (с HEAD, FETCH_HEAD, actual commits).

Webhook в Phase 4 (cron `partsops-sync-on-change` через `git diff`) **нельзя строить, пока нет git в Danila master**. Нужно явное решение пользователя.

## ⚠ Surprise #2 — нет ни одного `.gitignore`

Подтверждено: ни в корне, ни в `partsops-ai-manager/`. Это значит:
- `__pycache__/`, `*.pyc` — индексируются как обычные файлы.
- `webui.db`, `database.db` — обычные файлы.
- `refcode.html`, `refcode.html.bak` — обычные файлы.
- `.bak`-версии `database.py`, `event_store.py`, `rbac.py`, `main.py` — обычные файлы, легко перепутать с каноном.

## 🔎 Классификация “мусора” из плана

| Файл | Размер | Происхождение | Вердикт |
|---|---|---|---|
| `RightPanel.tsx` | 78b | Заметка-paste, НЕ из проекта | мусор (можно удалить, но не критично) |
| `triageStats.value` | 47b | Артефакт какой-то сессии | мусор |
| `llm.py` | 96b | Содержит только `cd "..." && patch -p0 < /path/to/...` — не модуль, заметка про патч | мусор |
| `uml.txt` | 0b | Пустой | мусор |
| `partsops_structure_logic_patch.diff` | 25k | Прошлый неприменённый патч (48% content) | RECYCLE: перенести в `partsops-ai-manager/.patch/2026-07-04.diff` |
| `partsops_structure_logic_patch.safe.diff` | 21k | То же, вторая итерация | RECYCLE: если применим — оставить рядом с первым, поместить в git-плашку |
| `refcode.html` | 156k | `!!!saved html!!!` справочный (refcode) | KEEP+CLASSIFY: использовать как reference, или удалить (~150k) |
| `refcode.html.bak` | 147k | Копия refcode | мусор (если refcode нужен — .bak не нужен) |
| `ai_assistant_operational_control.html` | 30k | Очень похоже на playground | мусор |
| `get_app_tsx.py` (v1, v2) | 1.7k/1.4k | Утилиты вытащить App.tsx из HTML | RECYCLE или мусор |
| `recover_app.py` | 2k | Восстановление | мусор |
| `partsops_agent_os_devpack.zip` + `partsops_agent_os_devpack/` | 31k+ | Devpack, есть развёрнутая копия рядом | DELETE zip |
| `webui.db` | 651k | Локальная БД | MUST IGNORE (добавить в .gitignore) |

## 🎯 Decision Gates (нужен ответ пользователя)

Всё ниже я НЕ делаю, пока не согласовано.

### Gate A — репозиторий

Создать `git init` в `/Users/user/projects/Danila master`?

- (A1) Да, простой init + initial commit + .gitignore
- (A2) Да, но сначала сделать `partsops-ai-manager/` отдельным репо
- (A3) Нет, оставить без git, переписать Phase 4 под watcher на mtime
- (A4) Только `partsops_bot/` git, остальное в git не идёт

### Gate B — корневой мусор

Что удаляем сейчас?

- (B1) Удалить всё перечисленное в столбце “мусор”: `RightPanel.tsx`, `triageStats.value`, `llm.py`, `uml.txt`, `refcode.html.bak`, `ai_assistant_operational_control.html`, `get_app_tsx*.py`, `recover_app.py`, `partsops_agent_os_devpack.zip`.
- (B2) Только самое однозначное (`.bak`, пустые, заметка-патч). Остальное оставить как playground.
- (B3) Ничего не удалять, только собрать в `__TRASH__/` для возможного отката.

### Gate C — `.bak` файлы внутри partsops-ai-manager

Файлы `database.db.bak`, `event_store.py.bak`, `rbac.py.bak`, `main.py.bak` появились из прошлой правки (`patch` сохранил копии). Сравнить бак и канон, удалить если канон ≠ бак.

- (C1) Удалить все `.bak` после сравнения.
- (C2) Оставить (если пользователь — “пока потревожь”).

### Gate D — `refcode.html`

Самый крупный файл (155k). Что с ним?

- (D1) Удалить полностью.
- (D2) Сохранить как `_references/2026-07-05_save-snippet.html` и внести в .gitignore.
- (D3) Без изменений.
