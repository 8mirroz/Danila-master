# Pinterest Scraping via gallery-dl

> **Skill**: Успешно протестировано в OpenCode — `gallery-dl` скачивает оригиналы с Pinterest.
> **Версия**: 1.0 | **Дата**: 2026-07-20

---

## Установка

```bash
# через pip
pip install gallery-dl

# проверка
gallery-dl --version
```

Установлен в системе: `/Users/user/Library/Python/3.9/bin/gallery-dl` (v1.32.7)

---

## Pinterest Экстракторы

`gallery-dl` имеет встроенные Pinterest-экстракторы:

| Экстрактор | Описание | Пример URL |
|-----------|----------|------------|
| **PinterestBoardExtractor** | Изображения с борды | `https://www.pinterest.com/USER/BOARD/` |
| **PinterestAllpinsExtractor** | Все пины пользователя | `https://www.pinterest.com/USER/pins/` |
| **PinterestCreatedExtractor** | Созданные пины | `https://www.pinterest.com/USER/_created/` |

---

## Команды

### Скачать все оригиналы с борды

```bash
gallery-dl -f "/O" -d ./pinterest_output https://www.pinterest.com/USER/BOARD/
```

### Скачать все пины пользователя

```bash
gallery-dl -f "/O" -d ./pinterest_output https://www.pinterest.com/USER/pins/
```

### Массовое скачивание из файла

```bash
# pins.txt — по одному URL на строку
gallery-dl -f "/O" -d ./pinterest_output -i pins.txt
```

---

## Флаги

| Флаг | Назначение |
|------|-----------|
| `-f "/O"` | **Оригинальные имена файлов** (оригиналы, не превью) |
| `-d DIR` | Директория для сохранения |
| `-D DIR` | Точная директория (без подпапок по категориям) |
| `-i FILE` | Читать URL из файла |
| `-x FILE` | Читать URL из файла и удалять их после скачивания |
| `--restrict-filenames` | Заменить спецсимволы в именах файлов на `_` |
| `--cookies FILE` | Файл с cookies для приватных борд |
| `--rate-limit N` | Максимум N запросов в секунду |

---

## Для приватных борд

Если борда приватная, нужны cookies:

```bash
# Экспорт cookies из браузера (через расширение Get cookies.txt)
gallery-dl --cookies ~/pinterest_cookies.txt -f "/O" -d ./output https://www.pinterest.com/USER/BOARD/
```

---

## Проверка доступных экстракторов

```bash
# Список всех Pinterest-экстракторов
gallery-dl --list-extractors | grep -i pinterest

# Детальная информация по экстрактору
gallery-dl -E pinterest 2>&1 | head -40
```

---

## Примечания

- `gallery-dl` сам обрабатывает антибот-защиту Pinterest
- Флаг `-f "/O"` критичен для получения оригиналов (без него — превью/thumbnails)
- Для публичных борд cookies не требуются
