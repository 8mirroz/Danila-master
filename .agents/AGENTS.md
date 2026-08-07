# 🌌 Danila Master Project — Agent Rules

Этот файл содержит правила и инструкции для агентов, работающих в проекте Danila Master.

## 🔄 Obsidian Auto-Sync Rule
Каждый раз, когда вы вносите архитектурные изменения, завершаете задачу или обновляете планы/отчеты:
1. **Запустите синхронизацию Obsidian**:
   Вызовите скрипт `bash scripts/sync_obsidian.sh` (в корне проекта), чтобы автоматически передать последние изменения планов, отчетов и задач в Obsidian Vault.
2. **Синхронизация решений**:
   Если было принято важное архитектурное решение (ADR), передайте его в решения Obsidian:
   `bash scripts/sync_obsidian.sh --decision-note "Название решения или краткое описание"`

При завершении своей работы в этом проекте всегда запускайте синхронизацию.

## 🧹 Code Hygiene Rules
- После рефакторинга TS/TSX: запускать `npx tsc --noEmit`, фиксить все TS2xxx.
- Запрещены `.bak`, `.bak2`, `.backup` файлы — использовать git-ветки.
- Закомментированные переменные не должны иметь живых ссылок в коде.

## 💾 SQLModel & Database Rules
- **Удаление записей**: Запрещено вызывать `.delete()` на результате `session.exec(select(...))`, так как `ScalarResult` не поддерживает метод `delete`. Для удаления записей необходимо использовать конструкцию `delete` из `sqlmodel`:
  ```python
  from sqlmodel import delete
  session.exec(delete(ModelName).where(ModelName.field == value))
  ```

## 📊 Excel Parsing Rule
- **Использование openpyxl**: Для парсинга файлов Excel (XLSX) в Python всегда использовать библиотеку `openpyxl` (`load_workbook(..., data_only=True)`). Запрещено использовать низкоуровневые XML/ZIP парсеры, так как они ломаются при любых изменениях структуры XLSX.

## 🛡 PII Protection & Masking Rules
- **Обезличивание в логах**: Все сообщения логов, которые выводят входящие запросы клиентов или данные профилей, должны быть принудительно отфильтрованы функцией маскирования PII (`mask_for_log` из модуля `pii`).
- **Обезличивание перед внешними LLM**: Любые входящие текстовые запросы от клиентов перед передачей во внешние облачные API LLM (NVIDIA, OpenAI, OpenRouter) должны проходить через предобработку `secure_pre_parse` для автоматического удаления PII и замены их на безопасные плейсхолдеры (`[ТЕЛЕФОН_СКРЫТ]`, `[VIN_СКРЫТ]` и т.д.).

## ⚠️ Ambiguous Tool Names — Ask Before Install

Если имя инструмента/технологии написано с опечаткой, в транслите или фонетически неоднозначно — **не угадывать, спрашивать**.

- Правило: `ambiguous name → ask before install` (особенно: `brew install`, `npm install -g`, системные пакеты).
- Пример: «насм» в тексте → спросить «вы имеете в виду NASM (ассемблер), или другой инструмент?» — не устанавливать.
- Предлагать 2–3 варианта интерпретации, если контекст не ясен однозначно.

## ⚠️ view_file Output ≠ File Content

`view_file` добавляет `<line_number>: ` к каждой строке **для отображения**. Этот вывод **НИКОГДА** не должен использоваться напрямую как содержимое для записи в файл.

- При записи в Python-файлы: проверять синтаксис `python3 -m py_compile <file>` после записи.
- При записи в TS/TSX-файлы: `npx tsc --noEmit -p tsconfig.app.json` после записи.
- Порядок hot-patch процессов: `patch → validate → kill → start`. Никогда `kill → patch → start`.

## 🌐 Multi-Worktree Dev Server Verification Rule
When debugging hot-reload (HMR) failures or un-updated UI changes on running dev servers (e.g. Vite on port 5173):
1. **Verify Running Process Cwd**: Run `lsof -i :<port>` and `ps aux | grep vite` (or dev server process) to check the EXACT working directory of the active process.
2. **Worktree Sync**: If the running process is executing out of a parallel worktree (e.g., `.grok/worktrees/...`), copy/sync updated frontend components to both the main workspace and the active worktree path so HMR updates the live browser immediately.

## 🎨 High-Contrast Theme & GSAP Guard Rule
1. **No Hardcoded Single-Theme Hexes**: Do not hardcode dark mode hex colors (`#F4F7FB`, `#0D131E`) or dark glass borders (`border-white/10`) in reusable components. Use explicit dual-theme Tailwind classes (`text-slate-900 dark:text-slate-100`, `bg-slate-50/50 dark:bg-slate-900/50`).
2. **GSAP Inline Cleanliness**: GSAP `handleMouseEnter` / `handleMouseLeave` callbacks must NEVER mutate `backgroundColor` or `borderColor` to hardcoded dark hex values on hover. Animate only transforms (`y`, `scale`) and theme-neutral shadow tokens.

