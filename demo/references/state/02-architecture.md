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
| `cli.py` | 688 | 25 листовых команд, флаги, конвертация `TodocError` в код выхода |
| `adapters/formats/markdown.py` | 331 | Токены markdown-it-py: заголовки, ссылки, front matter, backlinks |
| `application/validator.py` | 303 | Диагностика: синтаксис, типы, ссылки, схемы записей, отношения |
| `domain/models.py` | 205 | Document, Folder, Diagnostic, SuggestedFix, SearchHit, WritePlan |
| `config.py` | 164 | `dataset.json`, правила по умолчанию, `init` |
| `typing_system/resolver.py` | 143 | Маски, приоритеты, резолв `dir_type`/`doc_type`, конфликты |
| `service.py` | 123 | `DatasetContext`: скан → валидация → документы/записи/отношения → публикация |
| `application/registry.py` | 123 | Поколения индекса, `CURRENT.json`, кэш парсинга |
| `adapters/filesystem/scanner.py` | 123 | Обход, hard-excludes, containment, `atomic_write`, хеши |
| `application/write.py` | 120 | WritePlan, create record, фикс ссылки, line-операции правки |
| `application/search.py` | 118 | Лексический поиск, ранжирование, фрагменты, бюджет |
| `adapters/formats/jsonfmt.py` | 118 | Строгий JSON, глубина, JSON Pointer, JSON Schema |
| `application/query.py` | 111 | Фильтры, агрегация с единицами, BFS по графу |
| `typing_system/descriptors.py` | 83 | Загрузка и проверка описателей типов |
| `adapters/formats/csvfmt.py` | 63 | Заголовки, строки, лимиты CSV |
| `output/envelope.py` | 60 | Конверт и рендер json/table/markdown |
| `errors.py` | 51 | Коды выхода 0–6, иерархия ошибок |

Итого `src/todoc`: 3003 строки. Пустые порты-заглушки: `ports/`, `adapters/indexes/`,
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
