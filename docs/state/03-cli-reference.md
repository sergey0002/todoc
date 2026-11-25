# 03. Справочник CLI: 25 команд

Все опции и формы ответа сверены с `--help` и реальными запусками. Точка входа: `todoc`
(или `python -m todoc`).

## Глобальные опции

| Опция | Значение |
|---|---|
| `--root TEXT` | DATA_ROOT; можно повторять для нескольких датасетов. Альтернатива: `TODOC_ROOT` |
| `--output [json\|table\|markdown]` | по умолчанию `json` |
| `--no-input` | запрет интерактива (команды и так не спрашивают) |
| `--version` | `todoc, version 0.1.0` |

## Коды выхода

| Код | Смысл | Класс ошибки |
|---|---|---|
| 0 | успех | — |
| 1 | операционная ошибка | `TodocError` |
| 2 | ошибка использования | `click.ClickException` |
| 3 | ошибка валидации | `ValidationError` |
| 4 | отказ в доступе | `AccessError` |
| 5 | конфликт (хеш/перезапись) | `ConflictError` |
| 6 | незавершённая генерация | `IncompleteError` |

## Конверт ответа

```json
{"schema_version": 1, "ok": true, "data": {}, "diagnostics": [], "next_actions": []}
```

В stdout при `--output json` — ровно один JSON-текст. `next_actions[].argv` — готовые массивы
аргументов следующего шага.

## Команды

### `init --root PATH`
Создаёт `.todoc/` (датасет, правила, каталоги типов; у каждого типа — `type.json`, `template.<ext>`,
`prompts/{read,create,edit,delete}.md`) и `queries/`. Данные пользователя не трогает. Повторный вызов — `config.already_initialized` (exit 3).
`data`: `{dataset_id, root, created}`.

### `check-config`
Загружает конфигурацию и реестр типов. `data.datasets[]`: `{dataset_id, ok, warnings, dir_types, doc_types, entity_types, relation_types, issues}`.
Все находки — ошибки (`config.unknown_field`, `config.invalid_schema`, `config.template_missing`,
`config.prompt_missing`, `config.schema_missing`, `config.duplicate_asset`) и дают exit 3.
Поле `warnings` считает находки с `severity: warning`; сейчас таких кодов нет, поэтому оно равно 0 —
контракт оставлен, чтобы предупреждение можно было добавить, не меняя форму ответа.

### `check [--strict]`
Сводка по датасету. `data.datasets[]`: `{dataset_id, documents, errors, warnings, status}`.
`--strict` превращает предупреждения в провал.

### `scan`
Обход без публикации индекса. `data.datasets[]`: `{dataset_id, folders, documents, diagnostics}`.

### `validate [--all]`
Полная валидация. `data.datasets[]`: `{dataset_id, documents, diagnostics[]}`.
Каждая диагностика: `{dataset_id, id, code, severity, path, location, evidence, message, suggested_fixes[]}`.
Exit 3, если есть ошибки.

### `index status` / `index rebuild`
`status` читает последнее опубликованное поколение: `{dataset_id, generation_id, current}`.
**До первой пересборки возвращает `generation_id: null`** — сначала выполните `index rebuild`.
`rebuild` публикует новое поколение: `{dataset_id, generation_id, folders, documents, records, relations, diagnostics}`.

### `explain-path PATH`
Объясняет типизацию пути: `{dataset_id, path, doc_type, format, rule_source, document_id}`.
`rule_source` показывает, какое правило сработало (`rule:<id>`, `reserved`, `default`, `ambiguous`).

### `docs new --title T [--dir DIR] [--path P] [--type T] [--template NAME]`
Создаёт документ из стартового шаблона типа (create-only, без перезаписи).
`--type` выбирает тип документа; `--template` принимает **id типа или путь к файлу**
(путь должен лежать внутри DATA_ROOT). Плейсхолдеры шаблона подставляются как текст:
`{title}`, `{slug}`, `{date}`, `{type_id}`, `{id}`, `{format}`; неизвестные остаются как есть.
Если тип не объявил шаблон, документ создаётся как `# <заголовок>`.
`data`: `{dataset_id, path, title, doc_type, template, hash}`, где `template` — источник
(`.todoc/doc_types/<id>/template.md`, путь к файлу, `type-without-template` или `none`).
Отказы: `types.unknown`, `types.template_missing`, `types.template_invalid` (шаблон нарушает
структуру своего типа — файл не создаётся), `docs.target_exists` (exit 5),
`access.outside_data_root` (exit 4).

### `docs search --query Q [--type T] [--limit N] [--within PATH] [--budget BYTES] [--cursor C]`
Лексический поиск. `data`: `{dataset_id, total, returned, truncated, cursor, items[]}`,
`items[]`: `{id, path, title, heading_path, rank, relevance{method,matched_by}, matched_terms, snippet{text,line_start,line_end,truncated}}`.
`--cursor` — смещение: вторая страница продолжает выдачу без пересечений с первой.

### `docs read --id ID [--section S | --anchor A | --line-range N-M | --pointer P | --columns C --rows R --where K=V] [--budget BYTES]`
Ограниченное чтение. Поля ответа зависят от формата:
- Markdown без селектора: `{title, headings[], text}` (`text` усекается до `--budget`, по умолчанию 4000 символов);
- Markdown с `--section`/`--anchor`: `{section, heading_path, lines[], text}` — окно до 40 строк от заголовка;
- Markdown с `--line-range`: `{lines[], text}`;
- JSON: `{value}` (с `--pointer` — значение по RFC 6901);
- CSV: `{columns, rows[], total}`.
Общие поля: `{dataset_id, id, path, format, doc_type, hash}`.

### `docs tree [--within PATH] [--max-depth N]`
`data`: `{dataset_id, folders[], documents[], total_folders, total_documents, max_depth}`.

### `docs edit --id ID --patch-file F [--preview] [--apply] [--if-hash H]`
Патч: `{"ops": [{"line": 12, "text": "новая строка"}]}` — замена строк по 1-индексации.
Без `--apply` возвращается `{preview: true, ops}`. С `--apply` — `{applied: true, new_hash}`.
Несовпадение `--if-hash` — exit 5.

### `records create --type T --input-file F [--preview] [--apply] [--if-hash-new]`
Create-only. `--preview`: `{preview: true, plan{target_path, new_content, expected_hash, new_hash, basis, validations}}`.
`--apply`: `{created, new_hash}`. Повторный `record_id` — exit 5; неизвестный тип — exit 3.

### `records list [--type T] [--since D] [--until D] [--relation TYPE=ID] [--limit N]`
`data`: `{dataset_id, total, returned, truncated, items[]}`.

### `records query --query-file F`
QuerySpec: `{entity_type, filters, limit}`; фильтры поддерживают равенство, `$in`, `$gte`, `$lte`.
`data`: `{dataset_id, total, truncated, items[]}`.

### `records aggregate --metric FIELD --type T [--group-by FIELD]`
`data`: `{entity_type, metric, units, formula, groups, incoming_ids, completeness, dataset_id}`.
Смешение единиц измерения в одной агрегации — `query.unit_mismatch` (exit 3).

### `records read --id ID [--view NAME]`
`data`: `{dataset_id, record_id, path, data}`. `--view` берёт список полей из `views` описателя типа.

### `relations graph --from ID [--type T] [--depth N] [--limit N]`
BFS по типизированным рёбрам (обход ненаправленный). `data`: `{dataset_id, from, edges[{type_id, from, to}]}`.

### `types list` / `types show TYPE_ID` / `types prompt TYPE_ID [--op OP]` / `types guide [--format markdown|json] [--out PATH]`
`list`: `{dataset_id, dir_types[], doc_types[], entity_types[], relation_types[]}`.
`show`: `{dataset_id, kind, type{...}, template, prompts, schema}` — `template`, каждый из четырёх
CRUD-промптов (`read`, `create`, `edit`, `delete`) и `schema` дают путь и признак `exists`;
у типов папок и отношений все три пустые. Отсутствующий файл виден как `exists: false`,
а не исчезает из ответа. `schema` равен `null` у любого типа, кроме типа записи, и указывает
на `.todoc/entity_types/<type_id>/schema.json`.
`prompt`: `{dataset_id, type_id, kind, operation, path, prompt, chars}` — текст стартового
промпта одной операции. Отказы: `types.prompt_missing`, `types.unknown` (exit 3);
неизвестная операция — ошибка использования (exit 2).
`guide`: `{dataset_id, guide}` — сгенерированное описание типовой системы.

### `fix --diagnostic ID [--preview] [--apply] [--if-hash H]`
Применяет один предложенный фикс (замена цели ссылки). `--preview`: `{diagnostic, preview: true, fix}`;
`--apply`: `{diagnostic, applied: true, new_hash}`. Неизвестный ID — `fix.diagnostic_not_found` (exit 3).
**ID диагностики живёт только в рамках одного запуска `validate`** — берите его из того же процесса.

### `doctor [--check IDS] [--scope S] [--fix]`
Только чтение: проверки `config`, `index`, `python`. `data.datasets[]`:
`{dataset_id, checks_total, passed, checks[{id,status,message}], fix_mode}`.

### `status`
Быстрый снимок: `data.datasets[]`: `{dataset_id, generation_id, documents, records}`.
Читает опубликованное поколение, не пересобирая индекс.

## Типовые последовательности

```bash
todoc init --root KB && todoc check-config --root KB
todoc index rebuild --root KB && todoc status --root KB
todoc validate --root KB --all          # взять diag id из этого же вывода
todoc fix --root KB --diagnostic diag_0042 --preview
todoc fix --root KB --diagnostic diag_0042 --apply
todoc docs search --root KB --query "refresh token" --limit 3
todoc docs read --root KB --id doc:design --section "Decision"
todoc records create --root KB --type note --input-file note.json --preview
todoc records create --root KB --type note --input-file note.json --apply
```

## Связанные разделы

- [06-validation-and-diagnostics.md](06-validation-and-diagnostics.md) — коды диагностик.
- [07-search-and-read.md](07-search-and-read.md) — детали поиска и чтения.
- [12-agent-operations.md](12-agent-operations.md) — как этим пользоваться агенту.
