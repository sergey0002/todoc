# 03. Справочник CLI: 36 команд

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

### `index status` / `index rebuild [--force]`
`data.datasets[]`. `status` читает опубликованный снимок:
`{dataset_id, generation_id, current, corpus_digest, created_at}`.
**До первой пересборки возвращает `generation_id: null`** — сначала выполните `index rebuild`.
`rebuild` публикует снимок: `{dataset_id, generation_id, corpus_digest, reused, folders, documents, records, relations, diagnostics}`.
Без `--force` валидный снимок переиспользуется и возвращается `reused: true`; `--force`
пересчитывает всегда. Снимок один и перезаписывается на месте — размер `.todoc/index/` не
растёт от числа запусков.

### `stale [--path P] [--severity S]` / `stale --ack P --reason R [--apply] [--expected-hash H]`
Сравнивает хеши фрагментов, объявленных в `derived_from`, с фактическими.
`data`: `{dataset_id, path, stale}`; диагностики `staleness.dependency_changed` и
`staleness.dependency_missing` (severity `warning`).

Якорь зависимости — `путь[#фрагмент]@sha256:…`, где фрагмент либо JSON Pointer (`/meta/date`),
либо `section:<заголовок>`. Хеш считается от фрагмента, поэтому правка несвязанного поля не
помечает документ устаревшим.

`--ack` подтверждает, что дрейф не релевантен: без `--apply` команда показывает план и ничего
не пишет, с `--apply` — дописывает во front matter `stale_acknowledged_at`,
`stale_ack_reason`, `stale_ack_hashes`. Подтверждение хранит хеши на момент подтверждения и
сбрасывается, когда любой из них меняется снова.

### История: `log` / `show` / `diff` / `blame` / `revert` / `tag` / `history …`

Журнал живёт в `.todoc/history/` и пишется **по одному событию на запись файла**, а не на
запуск команды: команда чтения на неизменном корпусе не добавляет в него ничего. Событие
несёт `rev` (первые 12 знаков SHA-256 от строки журнала), `kind`, `actor`, `change_id`,
`basis` и по каждому пути `{path, before, after, git_head, ranges}`. `ranges` —
1-based включительные диапазоны изменённых строк, из них собирается лента по разделу.

`kind` — один из `doc.create`, `doc.edit`, `doc.fix`, `record.create`, `record.edit`,
`snapshot` (базовая линия `history adopt`) и `external.change` (правка мимо todoc,
обнаруженная сканированием в режиме `observed`).

| Команда | Что возвращает |
|---|---|
| `log [--path P] [--section S] [--kind K] [--change C] [--tag T] [--since D] [--until D] [--limit N] [--cursor C]` | `{events[], total, truncated, next_cursor}`, свежие первыми. `--section` требует `--path` |
| `show [REV] --path P [--budget B]` | содержимое файла **на** ревизии (без REV — текущее): `{path, rev, content}` |
| `diff REV_A [REV_B] --path P [--context N] [--budget B]` | `{changed, lines, diff[]}`; без `REV_B` — против текущего состояния |
| `blame --path P [--section S]` | кто и когда менял файл или раздел: `{entries[]}` с `rev`, `at`, `kind`, `actor`, `ranges` |
| `revert REV --path P [--apply] [--expected-hash H]` | без `--apply` — план `{applied: false, current_hash, new_hash}`; с `--apply` пишет файл и своё событие |
| `tag NAME [--rev R] [--message M]` | метка на событие (по умолчанию последнее); имя разрешается вместо `rev` |
| `history gc [--keep-objects N] [--purge-before D] [--dry-run]` | `{removed_events, kept_events, objects_before, objects_referenced, orphans_removed, dry_run}` |
| `history adopt` | снимает текущее состояние как базовую линию: `{rev, paths}` |
| `history export --to PATH` | копирует `.todoc/history/` целиком: `{exported, to}`. Путь только внутри DATA_ROOT |

Семантика `show` и `revert` намеренно расходится на один шаг и повторяет git: `show REV` —
состояние **после** события (как `git show <c>:<path>`), а `revert REV` — образ **до** него
(как `git revert <c>`). Откат события создания файла или базовой линии невозможен: состояния
«до» не существует, команда отвечает `history.revision_unknown` с объяснением.

Хранится только образ «до», поэтому `history gc` удаляет сирот и лишние снимки, не трогая
события, на которые есть ссылки. `--purge-before` стирает события старше даты: «удалил» в
истории не равно «удалил» на диске.

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
ID диагностики — SHA-256 от `path + code + message`, поэтому он одинаков в каждом запуске и `fix`
находит его заново своим сканом. Действителен, пока не изменён файл с дефектом; после правки
прежний ID даёт `fix.diagnostic_not_found`.

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
