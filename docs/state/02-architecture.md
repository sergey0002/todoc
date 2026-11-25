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
| `cli.py` | 1494 | 46 листовых команд, флаги, конвертация `TodocError` в код выхода |
| `application/changes.py` | 706 | Жизненный цикл изменения, дельты, `validate`/`verify`/`apply`/`archive`/`revert` |
| `application/history.py` | 565 | Журнал событий: `log`/`show`/`diff`/`blame`/`revert`/`tag`, `gc`, внешние правки |
| `application/validator.py` | 522 | Диагностика: синтаксис, типы, ссылки, схемы записей и документов, отношения |
| `adapters/formats/markdown.py` | 378 | Токены markdown-it-py: заголовки, ссылки, front matter, границы секций |
| `typing_system/prompts.py` | 309 | Генерация стартовых шаблонов и CRUD-промптов типа |
| `typing_system/descriptors.py` | 282 | Загрузка и проверка описателей типов, разрешение `template`/`schema`/`prompts` |
| `application/temporal.py` | 243 | Би-темпоральность: `valid_from`/`valid_to`, `--as-of`, лента фактов |
| `application/staleness.py` | 278 | `derived_from` с якорями, расхождение хешей, `--ack` |
| `application/write.py` | 251 | WritePlan, create record, фикс ссылки, line-операции правки |
| `config.py` | 225 | `dataset.json`, правила и типы по умолчанию, `init`, ассеты типов |
| `service.py` | 218 | `DatasetContext`: скан → валидация → документы/записи/отношения → публикация, `HistoryRecorder` |
| `domain/models.py` | 205 | Document, Folder, Diagnostic, SuggestedFix, SearchHit, WritePlan |
| `application/registry.py` | 197 | Снимок индекса, `CURRENT.json`, кэш парсинга |
| `application/context.py` | 164 | `context`: запись → дельты → события → файлы → диффы, в пределах бюджета |
| `application/search.py` | 146 | Лексический поиск, ранжирование, фрагменты, бюджет |
| `typing_system/resolver.py` | 143 | Маски, приоритеты, резолв `dir_type`/`doc_type`, конфликты |
| `adapters/formats/jsonfmt.py` | 142 | Строгий JSON, глубина, JSON Pointer, JSON Schema |
| `adapters/filesystem/scanner.py` | 135 | Обход, hard-excludes, containment, `atomic_write`, хеши |
| `application/query.py` | 130 | Фильтры, агрегация с единицами, BFS по графу |
| `adapters/history/journal.py` | 117 | Append-only JSONL, `rev`, чтение, атомарная перезапись |
| `adapters/history/backends.py` | 110 | `embedded` и `git`; единственный `subprocess` в `src/todoc` |
| `adapters/history/objects.py` | 79 | Снимки «до»: zlib-6, имя = sha256 содержимого |
| `adapters/formats/csvfmt.py` | 63 | Заголовки, строки, лимиты CSV |
| `output/envelope.py` | 60 | Конверт и рендер json/table/markdown |
| `errors.py` | 51 | Коды выхода 0–6, иерархия ошибок |
| `ports/history.py` | 39 | Порт бэкенда истории: ядро от git не зависит |
| `__main__.py` | 6 | Точка входа `python -m todoc` |

Итого `src/todoc`: 7329 строк.

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
