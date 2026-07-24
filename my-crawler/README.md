# PartsOps Crawler — Руководство

> **Что это:** Playwright-краулер для сбора цен и информации о запчастях с маркетплейсов exist.ru, autodoc.ru и rossko.ru.
>
> **Зачем:** Собрать реальные рыночные цены по артикулам, чтобы потом сопоставить их с каталогом поставщиков PartsOps.

---

## 1. Быстрый старт

```bash
# 1. Установка
cd my-crawler
pip install -r requirements.txt
playwright install chromium

# Test tooling
python -m pip install -e '.[test]'

# 2. Подготовка артикулов
echo "34116852253" >> articles.txt
echo "04465-33471" >> articles.txt

# 3. Запуск
.venv/bin/python -m my_crawler.main

# 4. Результат
cat results/aggregated_parts.json
```

Проверка crawler: `.venv/bin/python -m pytest -q`.

Для Contract Operations список позиций можно получить из backend endpoint
`/api/contracts/{request_id}/crawler-manifest`, сохранить по одному артикулу
в файл и запустить `ARTICLES_FILE=/path/to/articles.txt .venv/bin/python -m my_crawler.main`.
Каждая положительная цена содержит `source_url`, UTC `captured_at` и
`screenshot_path`. JSON импортируется в backend скриптом
`scripts/import_contract_crawler_results.py`; screenshots копируются в
tenant-scoped evidence storage и не попадают в каталог поставщиков.

---

## 2. Настроенные краулеры

Система имеет **3 настроенных краулера** — по одному на каждый маркетплейс. Все они запускаются из одного файла `main.py`, который для каждого артикула из `articles.txt` создаёт 3 задачи.

| Краулер | Сайт | Тип данных | Сложность парсинга |
|---------|------|-----------|-------------------|
| **Exist.ru** | exist.ru | Оригиналы + аналоги, цены, доставка | Средняя — каталоги и строки с ценами |
| **Autodoc.ru** | autodoc.ru | Цены, наличие, доставка | Высокая — JS-поиск, динамический рендер |
| **Rossko.ru** | rossko.ru | Цены, бренды, доставка | Средняя — CSS-классы с хэшами |

---

## 3. Как работает каждый краулер

### 3.1 Exist.ru (`handle_exist`)

**URL:** `https://www.exist.ru/Price/?pcode={article}`

**Логика:**

```
[Страница поиска]
    │
    ├── Есть каталоги (ul.catalogs a)? 
    │     └── Да → Добавить каждый каталог в очередь как новый запрос exist
    │                   (чтобы перейти на страницу с ценами)
    │
    └── Нет каталогов → Это страница с ценами
          │
          ├── Найти .row-container (строки с деталями)
          ├── Для каждой строки:
          │     ├── Бренд: .name-container b или span
          │     ├── Артикул: .partno
          │     ├── Описание: полный текст минус бренд + артикул
          │     └── Цены: .pricerow, .pricerow--direct
          │           ├── Срок доставки: .statis
          │           └── Цена: .price (очищается от мусора)
          │
          └── Сохранить: context.push_data(...)
```

**Особенности:**
- Обрабатывает два типа страниц: каталог (выбор категории) и цены
- Каждая строка `.row-container` может содержать несколько ценовых предложений (разные поставщики)
- Собирает оригиналы и аналоги в одном цикле
- Если строк не найдено — сохраняет скриншот `exist_no_rows_debug.png`

**Что парсит:**
```json
{
  "site": "exist.ru",
  "search_article": "34116852253",
  "brand": "TRW",
  "article": "34116852253",
  "description": "Тормозные колодки передние BMW X5",
  "delivery": "1-2 дня",
  "price": "4500 ₽"
}
```

---

### 3.2 Autodoc.ru

Autodoc использует **два хендлера**: поиск и цену.

#### Этап 1: Поиск (`handle_autodoc`)

**URL:** `https://www.autodoc.ru/`

```
[Страница autodoc.ru]
    │
    ├── Дождаться `input[type="search"]:visible`
    ├── Кликнуть в поле
    ├── Ввести артикул
    ├── Нажать Enter
    ├── Если `/price/...` не появились → fallback на кнопку поиска
    │
    └── Извлечь и дедуплицировать все ссылки /price/... из предложений
          └── Каждую → добавить в очередь как autodoc_price
```

**Особенность:** `Autodoc` гидратирует search input с задержкой, поэтому fixed sleep недостаточен. Хендлер ждет целевой видимый search input до 12 секунд.

#### Этап 2: Цена (`handle_autodoc_price`)

```
[Страница товара autodoc.ru]
    │
    ├── Найти result rows `.pgoods`
    ├── Для каждой строки:
    │     ├── Заголовок: `.card__title`
    │     ├── Цена: `.offers__price` (fallback: текст строки)
    │     ├── Доставка: `.offers__delivery*` (fallback: regex по тексту)
    │     └── Наличие: `31 шт` / `Unavailable` (fallback: regex + class flags)
    └── Выбрать лучшую строку по score: бренд + артикул + наличие цены
```

**Автолечение:** Если `Autodoc` снова сдвинет микроразметку внутри строки, парсер все равно может извлечь цену/доставку/stock из текстового fallback без немедленного падения.

**Что парсит:**
```json
{
  "site": "autodoc.ru",
  "search_article": "34116852253",
  "brand": "TRW",
  "article": "34116852253",
  "description": "Тормозные колодки передние",
  "delivery": "Самовывоз: сегодня (Stock: В наличии)",
  "price": "4500 ₽"
}
```

---

### 3.3 Rossko.ru (`handle_rossko`)

**URL:** `https://sochi.rossko.ru/search?q={article}&text={article}&type=all`

```
[Страница результатов rossko.ru]
    │
    ├── Ожидание загрузки (5 сек)
    ├── Поиск ссылок: a[class*="result-item-"][class*="link"]
    │
    ├── Если не найдено → Проверить "Ничего не найдено"
    │     └── Если нет → Подождать ещё 5 сек → Повторить поиск
    │
    └── Для каждой ссылки:
          ├── Бренд: [class*="brand__"]
          ├── Артикул: [class*="articleNumbers__"]
          ├── Цена: [class*="priceWrapper__"] или [class*="price__"]
          ├── Доставка: [class*="delivery__"] или [class*="deliver__"]
          └── Описание: полный текст минус бренд/артикул/цена
                └── Чистка: удалить "~Завтра...", "Партнёрский склад..."
```

**Особенности:**
- CSS-классы на Rossko используют CSS Modules (хэшированные имена), поэтому селекторы используют `*=` (contains)
- Есть проверка на "Ничего не найдено" — если результатов нет, краулер не падает
- Описание очищается от лишнего текста регулярками

**Что парсит:**
```json
{
  "site": "rossko.ru",
  "search_article": "34116852253",
  "brand": "TRW",
  "article": "34116852253",
  "description": "Тормозные колодки передние",
  "delivery": "Доставка: 1-2 дня",
  "price": "4890 ₽"
}
```

---

## 4. Технические детали

### 4.1 Запуск и режимы

```bash
# Обычный режим — открывается браузер, можно выбрать регион / решить капчу вручную.
# Сессия сохраняется в .browser-profile и затем применяется в headless-прогонах.
.venv/bin/python -m my_crawler.main

# Headless-режим — браузера не видно, использует сохранённую сессию.
HEADLESS=1 .venv/bin/python -m my_crawler.main

# Через proxy (только fallback, если persistent profile недостаточен)
PROXY_URL=http://user:pass@host:port .venv/bin/python -m my_crawler.main

# С автоочисткой старых скриншотов
CLEAN_SCREENSHOTS=1 .venv/bin/python -m my_crawler.main

# Комбинированный (headless + proxy + clean)
HEADLESS=1 PROXY_URL=socks5://user:pass@host:1080 CLEAN_SCREENSHOTS=1 .venv/bin/python -m my_crawler.main
```

**Параметры браузера:**
- User-Agent: Chrome 120 на macOS
- Viewport: 1920×1080 (полноэкранный режим)
- Max requests: 100 (на всю сессию)
- Browser: Chromium
- Retry: 3 попытки на страницу (при таймаутах/ошибках)
- Timeout: 30s на навигацию, 60s на обработку страницы
- Persistent session: shared `.browser-profile` по умолчанию или site-specific overrides через env vars
- Concurrency: 2 вкладки по умолчанию, чтобы не терять marketplace session
- Proxy: опциональный fallback через `PROXY_URL`

**Production recipe для mixed profiles:**

1. По умолчанию crawler все еще поддерживает один shared `BROWSER_PROFILE_DIR`.
2. Для production лучше задавать отдельные профили по сайтам:
   - `EXIST_BROWSER_PROFILE_DIR`
   - `AUTODOC_BROWSER_PROFILE_DIR`
   - `ROSSKO_BROWSER_PROFILE_DIR`
3. Каждый marketplace теперь запускается отдельным crawler run с изолированным storage, так что `Rossko` может жить в своем профиле и при этом итоговый `aggregated_parts.json` остается общим.
4. Если `Rossko` перестал отдавать result rows, включите согласованный proxy через секрет `ROSSKO_PROXY_URL`; значение proxy не логируется.

```bash
# Общий shared профиль, если он вам действительно подходит
BROWSER_PROFILE_DIR="$HOME/Library/Application Support/partsops/marketplaces-profile" \
  .venv/bin/python -m my_crawler.main

# Production-ready вариант: отдельные persistent profiles
EXIST_BROWSER_PROFILE_DIR="$HOME/Library/Application Support/partsops/exist-profile" \
AUTODOC_BROWSER_PROFILE_DIR="$HOME/Library/Application Support/partsops/autodoc-profile" \
ROSSKO_BROWSER_PROFILE_DIR="$HOME/Library/Application Support/partsops/rossko-profile" \
HEADLESS=1 CRAWLER_MAX_CONCURRENCY=2 .venv/bin/python -m my_crawler.main

# Rossko fallback proxy только для этого сайта
EXIST_BROWSER_PROFILE_DIR="$HOME/Library/Application Support/partsops/exist-profile" \
AUTODOC_BROWSER_PROFILE_DIR="$HOME/Library/Application Support/partsops/autodoc-profile" \
ROSSKO_BROWSER_PROFILE_DIR="$HOME/Library/Application Support/partsops/rossko-profile" \
ROSSKO_PROXY_URL="$PARTSOPS_ROSSKO_PROXY_URL" \
HEADLESS=1 CRAWLER_MAX_CONCURRENCY=2 .venv/bin/python -m my_crawler.main
```

**Переменные окружения:**

| Переменная | Значение | Эффект |
|-----------|----------|--------|
| `HEADLESS` | `1`/`true` | Без видимого браузера |
| `PROXY_URL` | `http://user:pass@host:port` | Общий proxy для всех источников |
| `ROSSKO_PROXY_URL` | `http://user:pass@host:port` | Proxy override только для Rossko |
| `BROWSER_PROFILE_DIR` | `...` | Shared persistent profile для всех источников |
| `EXIST_BROWSER_PROFILE_DIR` | `...` | Persistent profile только для Exist |
| `AUTODOC_BROWSER_PROFILE_DIR` | `...` | Persistent profile только для Autodoc |
| `ROSSKO_BROWSER_PROFILE_DIR` | `...` | Persistent profile только для Rossko |
| `CRAWLER_MAX_CONCURRENCY` | `1`–`4` | Одновременные вкладки; default: `2` |
| `CLEAN_SCREENSHOTS` | `1`/`true` | Удалить старые `*_debug.png` перед стартом |

### 4.2 Входные данные: `articles.txt`

Формат — простой список артикулов, по одному на строку:
```
34116852253      # OEM номер
04465-33471      # Toyota номер
90915-YZZD4      # Масляный фильтр
# Строки с # игнорируются (комментарии)
```

### 4.3 Выходные данные: `results/`

После завершения краулер сохраняет:
- `aggregated_parts.csv` — таблица (можно открыть в Excel)
- `aggregated_parts.json` — структурированные данные

**JSON — схема:**
```json
[
  {
    "site": "exist.ru | autodoc.ru | rossko.ru",
    "search_article": "34116852253",
    "brand": "TRW",
    "article": "34116852253",
    "description": "Тормозные колодки передние BMW X5",
    "delivery": "1-2 дня",
    "price": "4500 ₽"
  },
  ...
]
```

### 4.4 Обработка цен (`clean_price`)

Функция `clean_price()` преобразует сырые строки с ценами (исправленная версия, v2):

| Вход | Выход | Стратегия |
|------|-------|-----------|
| `"4 500 ₽"` | `"4500 ₽"` | Цифры рядом с ₽ |
| `"1 200.50 ₽"` | `"1200.50 ₽"` | Цифры рядом с ₽ |
| `"1 200,50 ₽"` | `"1200.50 ₽"` | Замена `,` на `.` |
| `"471,15 ₽  1 418 20"` | `"471.15 ₽"` | Только первая группа с ₽ |
| `"3820514182 ₽"` | `"3820 ₽"` | Исправлено: больше не склеивает цифры |
| `"——"` | `"——"` | Нет цены |
| `""` или `None` | `"——"` | Пустое значение |

> **Важно:** Цена сохраняется как строка с символом ₽. Числовой парсинг происходит на стороне скрипта импорта (`scripts/import_crawler_results.py`).

#### Тесты `clean_price` (`tests/test_routes.py`):

```bash
cd my-crawler
pip install pytest
python -m pytest tests/test_routes.py -v
```

Проверяет 14+ кейсов: простые цены, десятичные, с мусором, пустые, None, rossko-формат.

### 4.5 Скриншоты для отладки

Если что-то пошло не так, краулер сохраняет скриншоты в корень `my-crawler/`:
- `exist_no_rows_debug.png` — Exist.ru не нашёл строк с ценами
- `autodoc_no_input_debug.png` — Autodoc не нашёл поле поиска
- `autodoc_no_suggestions_debug.png` — Autodoc не показал подсказки
- `autodoc_price_load_failed.png` — Autodoc не загрузил цену
- `rossko_no_rows_debug.png` — Rossko не нашёл результаты
- `rossko_card_not_rendered_debug.png` — Rossko открыл internal product page, но не отрисовал цену; evidence не создан
- `default_handler_fallback.png` — Неизвестный тип страницы

---

## 5. Типичные проблемы и решения

| Проблема | Причина | Решение |
|----------|---------|---------|
| Браузер открылся, но ничего не происходит | Сайт заблокировал запрос | Войти вручную в браузере, решить капчу. Или добавить `PROXY_URL` |
| "No price rows found on Exist.ru" | Артикул не найден на exist | Проверить articles.txt |
| Exist.ru: brand = "Unknown" | Селектор бренда не совпал | Исправлено — fallback по словарю из 80+ брендов |
| Autodoc не находит поле поиска | Изменение структуры сайта | Обновить JS-селектор в `handle_autodoc` |
| Autodoc: пустой URL (#search-xxx) | Hash-фрагменты игнорируются | Исправлено — теперь навигация на `https://www.autodoc.ru/` |
| Rossko: цена "3820514182 ₽" | Склейка всех цифр (цена+дата) | Исправлено — `clean_price` ищет цифры рядом с ₽ |
| Rossko: бренд с переносом строки | `inner_text()` включает вложенные элементы | Исправлено — `split("\n")[0]` |
| Rossko: "Ничего не найдено" | Артикул не существует | Проверить артикул на rossko.ru вручную |
| `aggregated_parts.json` пустой | Ни один запрос не вернул данных | Проверить интернет, запустить `HEADLESS=0` для отладки |
| Rossko не отдаёт result rows | Не прогрета session, выбран другой регион или сработал anti-bot | Запустить разовый headed bootstrap с тем же `BROWSER_PROFILE_DIR`; затем включить согласованный `PROXY_URL` fallback |
| Блокировка сайтом | Частые запросы или новый IP/profile | Снизить `CRAWLER_MAX_CONCURRENCY`, прогреть persistent profile; затем подключить `PROXY_URL` |

---

## 6. Интеграция с остальной системой

```
articles.txt
      │
      ▼
┌─────────────────┐     ┌──────────────────────────────┐
│  my-crawler/     │────▶│  results/aggregated_parts.json │
│  (Playwright)    │     └──────────────┬───────────────┘
└─────────────────┘                    │
                                       ▼
                          ┌──────────────────────────────┐
                          │  partsops-ai-manager/         │
                          │  scripts/import_crawler_results.py │
                          │  --dry-run / --supplier-id   │
                          └──────────────┬───────────────┘
                                         │
                                         ▼
                          ┌──────────────────────────────┐
                          │  SupplierCatalogItem (БД)     │
                          │  ← сюда попадают данные      │
                          └──────────────┬───────────────┘
                                         │
                                         ▼
                          ┌──────────────────────────────┐
                          │  matcher.py                   │
                          │  (поиск по каталогу)          │
                          └──────────────────────────────┘
```

**Полный пайплайн:**
```bash
# 1. Скраппинг
cd my-crawler
echo "34116852253" >> articles.txt
HEADLESS=1 python -m my_crawler.main

# 2. Импорт в каталог
cd ../partsops-ai-manager
python -m scripts.import_crawler_results --dry-run   # предпросмотр
python -m scripts.import_crawler_results              # реальный импорт

# 3. Поиск матчером
python -c "
from matcher import match_part_from_db
from database import engine
from sqlmodel import Session
with Session(engine) as s:
    r = match_part_from_db('34116852253', s, limit=5)
    for m in r:
        print(m['item']['name'], m['score'])
"
```

---

## 7. Файловая структура

```
my-crawler/
├── README.md              ← это файл
├── articles.txt           ← входные артикулы
├── requirements.txt       ← зависимости
├── my_crawler/
│   ├── __init__.py
│   ├── main.py            ← точка входа, создание запросов
│   └── routes.py          ← хендлеры exist/autodoc/rossko
├── results/               ← результаты (создаётся при запуске)
│   ├── aggregated_parts.csv
│   └── aggregated_parts.json
├── exist_no_rows_debug.png     ← скриншоты ошибок
├── autodoc_no_input_debug.png
├── autodoc_no_suggestions_debug.png
├── autodoc_price_load_failed.png
├── rossko_no_rows_debug.png
└── default_handler_fallback.png
```

---

*Документ создан 20.07.2026. Актуальная версия краулера — v3 (HEADLESS + PROXY + Retry + CleanPrice v2 + Brand fallback).*
