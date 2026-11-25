---
id: doc:state-architecture
title: "Состояние: архитектура, слои и модули"
doc_type: reference
lang: ru
source: docs/state/02-architecture.md
copied: true
---
# 02. Архитектура: слои, модули, поток данных

## Слои

```
CLI (click)  →  application  →  domain / typing_system
                     ↓
              adapters (filesystem, formats)   output (envelope)
```

Правило направления зависимостей: CLI знает приложение, приложение знает домен и порты,
адаптеры реализуют детали. CLI не работает с файлами напрямую, кроме чтения патчей и запросов,
которые ему передал пользователь.

## Модули и их размер (проверено `wc -l`)

| Модуль | Строк | Ответственность |
|---|---|---|
| `cli.py` | 945 | 26 листовых команд, флаги, конвертация `TodocError` в код выхода |
| `application/validator.py` | 452 | Диагностика: синтаксис, типы, ссылки, схемы записей, отношения |
| `adapters/formats/markdown.py` | 351 | Токены markdown-it-py: заголовки, ссылки, front matter, backlinks |
| `typing_system/prompts.py` | 309 | Генерация стартовых шаблонов и CRUD-промптов типа |
| `typing_system/descriptors.py` | 279 | Загрузка и проверка описателей типов, разрешение `template`/`schema`/`prompts` |
| `domain/models.py` | 205 | Document, Folder, Diagnostic, SuggestedFix, SearchHit, WritePlan |
| `config.py` | 197 | `dataset.json`, правила и типы по умолчанию, `init`, ассеты типов |
| `application/write.py` | 188 | WritePlan, create record, фикс ссылки, line-операции правки |
| `application/search.py` | 146 | Лексический поиск, ранжирование, фрагменты, бюджет |
| `typing_system/resolver.py` | 143 | Маски, приоритеты, резолв `dir_type`/`doc_type`, конфликты |
| `adapters/formats/jsonfmt.py` | 142 | Строгий JSON, глубина, JSON Pointer, JSON Schema |
| `service.py` | 124 | `DatasetContext`: скан → валидация → документы/записи/отношения → публикация |
| `application/registry.py` | 123 | Поколения индекса, `CURRENT.json`, кэш парсинга |
| `application/query.py` | 123 | Фильтры, агрегация с единицами, BFS по графу |
| `adapters/filesystem/scanner.py` | 123 | Обход, hard-excludes, containment, `atomic_write`, хеши |
| `adapters/formats/csvfmt.py` | 63 | Заголовки, строки, лимиты CSV |
| `output/envelope.py` | 60 | Конверт и рендер json/table/markdown |
| `errors.py` | 51 | Коды выхода 0–6, иерархия ошибок |
| `__main__.py` | 6 | Точка входа `python -m todoc` |

Итого `src/todoc`: 4100 строк (4030 в 19 модулях из таблицы + 70 в `__init__.py`).
Пустые порты-заглушки: `ports/`, `adapters/indexes/`,
`adapters/cache/`, `adapters/search/` — зарезервированы под пост-MVP (см. план E1–E10).

## Поток данных команды чтения

1. `cli` разбирает флаги, строит `DatasetContext(root)`.
2. Контекст загружает `dataset.json` и правила, строит `TypeRegistry`, проверяет ссылки правил на типы.
3. `scan_dataset` обходит DATA_ROOT отсортированно, исключает `.todoc`, `.git`, `__pycache__`,
   `node_modules`, `.obsidian`, `.venv`, `venv`; symlink не проходят по умолчанию.
4. `validate_dataset` парсит файлы, присваивает типы, собирает диагностики и `doc_info`.
5. `service` собирает folders/documents/records/relations и публикует поколение индекса.
6. Команда читает из опубликованного поколения и ничего не записывает.

**Важно для агента:** команды `docs read`, `docs search`, `records list/query/read/aggregate`,
`relations graph`, `fix`, `docs edit` вызывают пересборку индекса на каждый запуск. Это делает
результат свежим, но дорогим на больших датасетах (известная проблема, см.
[11-known-issues.md](11-known-issues.md)).

## Поток данных команды записи

1. Читается вход (JSON-запись или файл патча) — только из пути, который передал пользователь.
2. Строится `WritePlan`: целевой путь, новое содержимое, ожидаемый и новый хеши, список проверок.
3. Без `--apply` возвращается план (`preview: true`) — файл не трогается.
4. С `--apply` план применяется через `atomic_write` (временный файл + `fsync` + `os.replace`).
5. Индекс пересобирается, возвращается новый хеш.

## Расширяемость

| Точка расширения | Как |
|---|---|
| Новый тип папки/документа/записи/отношения | файл `type.json` в соответствующем каталоге `.todoc/` |
| Новая схема записи | `.todoc/entity_types/<entity_type>/schema.json` (JSON Schema 2020-12) |
| Новое правило маршрутизации | запись в `rules/directory-rules.json` или `rules/document-rules.json` |
| Новый шаблон записи | `.todoc/entity_types/<entity_type>/template.json` |
| Сохранённый запрос | `.todoc/queries/<name>.json` + `records query --query-file` |
| Новый формат файла | адаптер в `adapters/formats/` + суффикс в `FORMAT_BY_SUFFIX` |

## Связанные разделы

- [04-config-and-types.md](04-config-and-types.md) — содержимое `.todoc/`.
- [05-formats.md](05-formats.md) — адаптеры форматов.
- [09-storage-and-index.md](09-storage-and-index.md) — поколения и кэш.
