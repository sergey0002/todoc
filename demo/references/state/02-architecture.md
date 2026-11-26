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
| `cli.py` | 2456 | 63 листовые команды, флаги, конвертация `TodocError` в код выхода |
| `application/validator.py` | 890 | Диагностика: синтаксис, типы, ссылки, схемы, статусы, наборы секций, теги fm |
| `application/changes.py` | 710 | Жизненный цикл изменения, дельты, `validate`/`verify`/`apply`/`archive`/`revert` |
| `application/history.py` | 617 | Журнал событий: `log`/`show`/`diff`/`blame`/`revert`/`tag`, `gc`/`adopt`/`export`, внешние правки |
| `application/write.py` | 455 | WritePlan, create record, фикс ссылки, line-операции правки (insert/delete/replace), undo-relation |
| `adapters/formats/markdown.py` | 439 | Токены markdown-it-py: заголовки, ссылки, front matter (YAML-lite), границы секций |
| `application/interop.py` | 322 | Экспорты: flow→ASL, rule→DMN 1.3, term→Rasa NLU, derived-артефакты (план интероп-экспортов) |
| `typing_system/descriptors.py` | 318 | Описатели типов, `allowed_statuses`, разрешение `template`/`schema`/`prompts`, shape-проверки |
| `typing_system/prompts.py` | 309 | Генерация стартовых шаблонов и CRUD-промптов типа |
| `adapters/formats/jsonfmt.py` | 286 | Строгий JSON, глубина, позиции токенов, JSON Pointer, JSON Schema |
| `application/staleness.py` | 278 | `derived_from` с якорями (поинтер/секция), дрейф хешей, `--ack` |
| `application/folder_config.py` | 277 | `.config.json` папок: метаданные и скоринг Фазы A (план folder-config) |
| `application/registry.py` | 248 | Снимок индекса, `CURRENT.json`, кэш парсинга |
| `application/temporal.py` | 243 | Би-темпоральность: `valid_from`/`valid_to`, `--as-of`, лента фактов |
| `config.py` | 236 | `dataset.json`, правила и типы по умолчанию, `init`, ассеты типов |
| `service.py` | 228 | `DatasetContext`: скан → валидация → документы/записи/отношения → публикация, `HistoryRecorder` |
| `application/flow_view.py` | 221 | Витрина флоу: state machine, таблица решений, mermaid, lineage (план entity-catalog) |
| `application/search.py` | 217 | Лексический поиск, ранжирование, фрагменты, бюджет |
| `application/query.py` | 217 | Фильтры (`$in`/`$gte`…), агрегация с единицами, BFS по графу |
| `domain/models.py` | 205 | Document, Folder, Diagnostic, SuggestedFix, SearchHit, WritePlan |
| `application/context.py` | 164 | `context`: запись → дельты → события → файлы → диффы, в пределах бюджета |
| `application/skills.py` | 162 | Vault скилов: live-scan дерева, чтение с confinement, attach/import (план skills-vault) |
| `typing_system/resolver.py` | 157 | Маски, приоритеты, резолв `dir_type`/`doc_type`, конфликты |
| `adapters/filesystem/scanner.py` | 135 | Обход, hard-excludes, containment, `atomic_write`, хеши |
| `application/state.py` | 123 | Агентский стейт: `.todoc/state.json`, белый список ключей v1 (план агентский-стейт) |
| `adapters/history/journal.py` | 117 | Append-only JSONL, `rev`, чтение, атомарная перезапись |
| `adapters/history/backends.py` | 110 | `embedded` и `git`; единственный `subprocess` в `src/todoc` |
| `adapters/history/objects.py` | 79 | Снимки «до»: zlib-6, имя = sha256 содержимого |
| `adapters/formats/csvfmt.py` | 63 | Заголовки, строки, лимиты CSV |
| `output/envelope.py` | 60 | Конверт и рендер json/table/markdown |
| `errors.py` | 51 | Коды выхода 0–6, иерархия ошибок |
| `ports/history.py` | 39 | Порт бэкенда истории: ядро от git не зависит |
| `__main__.py` | 6 | Точка входа `python -m todoc` |

Итого `src/todoc`: 10 508 строк (проверено `wc -l`, 2026-11-26). Рост от 7 530 — итерации
26.11: жизненный цикл (статусы), vault скилов, агентский стейт, скоринг папок, интероп-экспорты,
каталог сущностей (планы в [13-demo-dataset.md](13-demo-dataset.md)).

Слои: `ports/` объявляет интерфейс бэкенда истории, `adapters/history/backends.py` его
реализует. Единственный `subprocess` во всём `src/todoc` — в `backends.py`, поэтому ядро
остаётся переносимым (P2) и работает без git: при его отсутствии выдаётся предупреждение
`history.backend_unavailable` и происходит деградация в `embedded`.

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
