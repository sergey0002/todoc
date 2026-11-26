---
id: doc:state-cli
title: "Состояние: справочник CLI, 27 команд"
doc_type: reference
lang: ru
source: docs/state/03-cli-reference.md
copied: true
created: 2026-11-26
updated: 2026-11-26
tags: [references, reference, справочник, состояние]
---

# 03. Справочник CLI: 46 листовых команд

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

### `init --root PATH [--dataset-id ID]`
Создаёт `.todoc/` (датасет, правила, каталоги типов; у каждого типа — `type.json`, `template.<ext>`,
`prompts/{read,create,edit,delete}.md`) и `queries/`. Данные пользователя не трогает. Повторный вызов — `config.already_initialized` (exit 3).
`data`: `{dataset_id, root, created}`.
Без `--dataset-id` идентификатор случаен (`dataset-` + 8 шестнадцатеричных); явное значение делает
демо-датасеты и фикстуры воспроизводимыми. Значение обрезается от пробелов; пустое отклоняется
как `config.invalid_schema` (exit 3).

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
`change.open`, `change.apply`, `change.archive`, `change.revert`,
`snapshot` (базовая линия `history adopt`) и `external.change` (правка мимо todoc,
обнаруженная сканированием в режиме `observed`).

| Команда | Что возвращает |
|---|---|
| `log [--path P] [--section S] [--kind K] [--change C] [--tag T] [--since D] [--until D] [--limit N] [--cursor C]` | `{events[], total, truncated, next_cursor}`, свежие первыми. `--section` требует `--path` |
| `show [REV] --path P [--budget B]` | содержимое файла **на** ревизии (без REV — текущее): `{path, rev, content}` |
| `diff REV_A [REV_B] --path P [--context N] [--budget B]` | `{changed, lines, diff[]}`; без `REV_B` — против текущего состояния |
| `blame --path P [--section S]` | кто и когда менял файл или раздел: `{entries[]}` с `rev`, `at`, `kind`, `actor`, `ranges` |
| `revert REV --path P [--apply] [--expected-hash H]` | без `--apply` — план `{applied: false, current_hash, new_hash, range_conflict}`; с `--apply` пишет файл и своё событие. Если файл менялся после `REV`, в конверте появляется предупреждение `history.range_conflict`: откат сотрёт более поздние правки |
| `tag NAME [--rev R] [--message M]` | метка на событие (по умолчанию последнее); имя разрешается вместо `rev` |
| `history gc [--keep-objects N] [--purge-before D] [--dry-run]` | `{removed_events, kept_events, objects_before, objects_referenced, orphans_removed, trimmed_for_size, objects_trimmed, dry_run}` |
| `history adopt` | снимает текущее состояние как базовую линию: `{rev, paths}` |
| `history export --to PATH` | копирует `.todoc/history/` целиком: `{exported, to}`. Путь только внутри DATA_ROOT |

Семантика `show` и `revert` намеренно расходится на один шаг и повторяет git: `show REV` —
состояние **после** события (как `git show <c>:<path>`), а `revert REV` — образ **до** него
(как `git revert <c>`). Откат события создания файла или базовой линии невозможен: состояния
«до» не существует, команда отвечает `history.revision_unknown` с объяснением.

Хранится только образ «до», поэтому `history gc` удаляет сирот и лишние снимки.
`--purge-before` стирает события старше даты: «удалил» в истории не равно «удалил» на диске.

Потолки обслуживания берутся из `limits` датасета и не влияют на запись в журнал — иначе
целостность файлов (P1) зависела бы от размера служебной папки:

| Лимит | По умолчанию | Что ограничивает |
|---|---|---|
| `max_journal_bytes` | 8388608 | `gc` подрезает самые старые события; счёт — в `trimmed_for_size` |
| `max_history_objects` | 20000 | значение по умолчанию для `--keep-objects`; счёт — в `objects_trimmed` |
| `max_diff_lines` | 2000 | строк на один дифф в `diff` и `context --with-diff` |

Явный `--keep-objects` важнее лимита. Обрезка снимков настоящая: у затёртой ревизии `show`
и `revert` честно отвечают `history.object_missing`, а не выдумывают содержимое.

### `timeline [--as-of D] [--path P] [--limit N]`

Единая лента: события журнала (время знания) и интервалы фактов (время правды) в одном
хронологическом порядке. `data`: `{dataset_id, as_of, path, count, truncated, entries[]}`.

У записи `entry` есть `kind` (`"fact"` или вид события) и `entry` (`"fact"` | `"event"`);
у факта — `valid_from`, `valid_to`, `observed_at`, `superseded_at`, `source_id`, `target_id`,
`type_id`, у события — `at`, `rev`, `path`, `change_id`.

`--as-of` срезает обе половины одним моментом: события позже T ещё не произошли, факты
позже T ещё не правда. Это ответ на «что было известно на дату T» — то, чего не даёт
ни `git log` (нет времени правды), ни `git bisect` (нет фактов).

Закрытый `superseded_at` факт **остаётся в ленте и в файле**: инвалидация вместо удаления.
Сортировка детерминированная — по времени, затем по виду записи и идентификатору.

### Изменения: `change list` / `open` / `show` / `validate` / `verify` / `apply` / `archive` / `revert`

Запись изменения — обычный `entity_type: change`, поэтому ей бесплатно достаются валидация
схемы, `records query --where status=…` и обход графа `blocked_by`. Папка изменения живёт
в DATA_ROOT, а не в `.todoc/`: намерение человека должно версионироваться git'ом и читаться
в Obsidian.

```
changes/<change-id>/
├── change.json          # машиночитаемое состояние
├── proposal.md          # зачем это изменение
├── tasks.md             # пункты `- [ ] …`, их считает verify
└── deltas/<target>.md   # дельты: что именно меняется в целевых файлах
changes/archive/<YYYY-MM-DD>-<change-id>/   # после `change archive`
```

`change-id` выводится из заголовка транслитерацией (`«Обновить суть»` → `change:obnovit-sut`),
при неудаче — `change-<8 знаков sha256>`. Статусы: `proposed` → `in_progress` → `blocked`
→ `applied` → `archived` | `reverted`.

Дельта — markdown с front matter и операциями по якорям-заголовкам:

```markdown
---
target: docs/state/09-storage-and-index.md
base_hash: sha256:aa…      # опционально, для строгой проверки
order: 1                   # опционально, порядок при нескольких дельтах на один файл
---

## MODIFIED: ## Поколение индекса
…новое тело раздела…

## ADDED: ## Журнал событий
…

## REMOVED: ## Устаревшее
```

| Команда | Что возвращает |
|---|---|
| `change list [--status S]` | `{changes[]}` — активные и архивные |
| `change open --title T [--blocked-by ID]… [--artifact P]…` | создаёт запись и папку, снимает базовую линию (хеши артефактов и список диагностик): `{change_id, path, status, artifacts}` |
| `change show ID` | запись и её дельты: `{record, deltas[]}` |
| `change validate ID` | **применимость к живому состоянию**: `{applicable, errors}` + диагностики в конверте |
| `change verify ID` | три измерения без модели: `{found, status, findings[], clean}` |
| `change apply ID [--apply] [--if-hash PATH=sha256:…]` | без `--apply` — план; с `--apply` — bundle-транзакция «всё или ничего» |
| `change archive ID [--tag T]` | статус `archived`, папка уносится в `changes/archive/`, `--tag` ставит метку истории |
| `change revert ID [--apply]` | возврат артефактов к базовой линии изменения |

`change validate` проверяет не формат дельты, а применимость: целевой файл существует
(`change.delta_target_missing`), якорь найден (`change.delta_anchor_missing`), `base_hash`
совпадает (`change.base_hash_mismatch`), зависимости закрыты (`change.blocked_by_unresolved`),
порядок применения однозначен (`change.apply_order_ambiguous`), а пробное применение не
ломает структуру документа и схему его `doc_type` (`change.post_apply_invalid`).

`change apply --apply` атомарен: сначала считаются все новые содержимые и проверяются все
дельты, и только затем идёт запись. Если запись не удалась, уже записанные файлы возвращаются
к исходным байтам — частичного применения не остаётся.

`change verify` — детерминированный аналог `converge`, поэтому результат воспроизводим и
может быть гейтом в CI:

- **completeness** — все пункты `tasks.md` закрыты, артефакты действительно изменены;
- **correctness** — текущее состояние файлов соответствует дельтам (проверяется только для
  `applied`/`in_progress`: до применения документ и должен отличаться);
- **coherence** — `validate --all` не даёт новых диагностик относительно базовой линии.

`change revert` восстанавливает артефакты по базовой линии, а не по обратным дельтам:
обратной дельты для `REMOVED` не существует, а базовый хеш существует всегда.

### `context --change ID \| --tag NAME [--budget N] [--with-diff]`

Весь контекст задачи одним вызовом, в пределах бюджета байт (по умолчанию 8000). Бюджет
считается по сериализованному объёму добавляемых кусков, а не по числу строк: агенту важно,
сколько байт он получит.

Возвращает `{dataset_id, change_id, tag, budget, truncated, record, deltas[], events[],
files[], used_bytes}` и, с `--with-diff`, ещё `diffs[]`. Порядок заполнения: запись →
дельты → события → файлы → диффы; когда кусок не влезает, взводится `truncated`, и ответ
никогда не превышает бюджет. Дифф обрезается также по `limits.max_diff_lines`.

Дифф считается от образа «до» первого события по файлу до текущего содержимого; без
базового хеша сравнивать не с чем, и вместо шума `revision_unknown` путь просто
пропускается.

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
структуру своего типа — файл не создаётся), `docs.empty_title` (заголовок из одних пробелов,
exit 3), `docs.target_exists` (exit 5), `access.outside_data_root` (exit 4).

`docs.unsafe_path` (exit 3) — второй эшелон защиты внутри `write.py`: срабатывает, если целевой
путь начинается с `../` или `/` либо содержит `/../`. Через CLI до него обычно не доходит —
containment-проверка слоя команд отвечает раньше тем же `access.outside_data_root` (проверено
на `--path ../evil.md` и `--dir ../out`).

### `docs search --query Q [--type T] [--limit N] [--within PATH] [--budget BYTES] [--cursor C]`
Лексический поиск. `data`: `{dataset_id, total, returned, truncated, cursor, items[]}`,
`items[]`: `{id, path, title, heading_path, rank, relevance{method,matched_by}, matched_terms, snippet{text,line_start,line_end,truncated}}`.
`--cursor` — смещение: вторая страница продолжает выдачу без пересечений с первой.
Нецелое значение — `usage.invalid_cursor` (exit 3), а не traceback.

### `docs read --id ID[#раздел] [--section S | --anchor A | --line-range N-M | --pointer P | --columns C --rows R --where K=V] [--budget BYTES]`

Fragment в `--id` (`doc:x#раздел`) — синоним `--section`; задавать оба — `usage.error` (exit 2).
Ограниченное чтение. Поля ответа зависят от формата:
- Markdown без селектора: `{title, headings[], text}` (`text` усекается до `--budget`, по умолчанию 4000 символов);
- Markdown с `--section`/`--anchor`: `{section, heading_path, lines[], text}` — окно до 40 строк от заголовка;
- Markdown с `--line-range`: `{lines[], text}`;
- JSON: `{value}` (с `--pointer` — значение по RFC 6901);
- CSV: `{columns, rows[], total, matched, truncated}`. `--where` применяется **до** `--rows`:
  `--rows 3 --where k=v` возвращает три подходящие строки, а не три первые с последующей
  фильтрацией (P1-5). `matched` — сколько строк подошло под условие, `total` — сколько их в файле.
Общие поля: `{dataset_id, id, path, format, doc_type, hash}`.
Некорректный `--line-range` — `usage.invalid_line_range` (exit 3).

### `docs tree [--within PATH] [--max-depth N]`
`data`: `{dataset_id, folders[], documents[], total_folders, total_documents, max_depth}`.

### `docs edit --id ID --patch-file F [--preview] [--apply] [--if-hash H]`
Патч: `{"ops": [{"line": 12, "text": "новая строка"}]}` — замена строк по 1-индексации.
Без `--apply` возвращается `{preview: true, ops}`. С `--apply` — `{applied: true, new_hash}`.
Несовпадение `--if-hash` — exit 5.

### `records create --type T --input-file F [--preview] [--apply]`
Create-only. `--preview`: `{preview: true, plan{target_path, new_content, expected_hash, new_hash, basis, validations}}`.
`--apply`: `{created, new_hash}`. Повторный `record_id` — `record.duplicate_id`, занятый путь —
`record.target_exists`, оба с exit 5; неизвестный тип — exit 3.

Флага `--if-hash-new` больше нет (P1-4): он принимался и ничего не делал, а гарантию
«только создание» команда даёт безусловно — ещё в preview. Флаг, намекающий, что guarantee
включается по желанию, вводил в заблуждение; вызов с ним теперь `usage.error` (exit 2).

### `records list [--type T] [--since D] [--until D] [--relation TYPE=ID] [--limit N]`
`data`: `{dataset_id, total, returned, truncated, items[]}`.

### `records query --query-file F [--as-of D]`
QuerySpec: `{entity_type, filters, limit}`; фильтры поддерживают равенство, `$in`, `$gte`, `$lte`.
`data`: `{dataset_id, as_of, total, truncated, items[]}`.

`--as-of` срезает выборку по **времени правды**: остаются записи, для которых
`valid_from <= T < valid_to` и которые ещё не закрыты `superseded_at`. Интервал полуоткрытый,
поэтому на день `valid_to` записи в выборке уже нет. Записи без темпоральных полей видны
всегда — обратная совместимость. Неразбираемое значение `--as-of` — это
`temporal.invalid_instant` (exit 3), а не пустая выборка: отличить опечатку от правды
должно быть возможно.

### `records aggregate --metric FIELD --type T [--group-by FIELD]`
`data`: `{entity_type, metric, units, formula, groups, incoming_ids, completeness, dataset_id}`.
Смешение единиц измерения в одной агрегации — `query.unit_mismatch` (exit 3).

### `records read --id ID [--view NAME]`
`data`: `{dataset_id, record_id, path, data, mentioned_in}`. `--view` берёт список полей из
`views` описателя типа. `mentioned_in` — упоминания записи из md (`{file, line, fragment}`;
`fragment` — часть после `#` у цели).

### `records undo-relation --id ID --pointer /relations/N [--apply] [--expected-hash H]`
Точечный откат ребра из ревизий журнала (план entity-catalog З4, T3). Без `--apply` — план:
`{mode: restore|remove, current, previous, previous_present, rev, at}` (ребро добавлено
последней ревизией → «до: отсутствовало»; изменено → прежний target). Идентичность ребра —
`type_id + target.id`. Apply — сплайс элемента JSON байт-в-байт + событие журнала; CAS по
`--expected-hash` (расхождение — `write.hash_mismatch`, exit 5). Отказы: чистый журнал —
`history.revision_missing` (exit 1); указатель вне массива/не вида `/relations/N` —
`edit.relation_missing` (exit 3) / `usage.error` (exit 2).

### `relations graph --from ID [--type T] [--depth N] [--limit N]`
BFS по типизированным рёбрам (обход ненаправленный). `data`: `{dataset_id, from, edges[{type_id, from, to}]}`.
Упоминания цели в md — рёбра `type_id: mention` с `via: "mention"` у корня; вершины-md в BFS не вовлекаются.

### `relations tree --from ID [--type T] [--depth N] [--limit N]`
Вложенное дерево над теми же данными, что graph (план entity-catalog З3, T11). `data`:
`{root, groups[{type_id, edges[{direction: out|in, id, fragment?, via?, cycle?, children[...]}]}], truncated}`.
JSON — вложенные `children`; `markdown`/`table` — компактный текст-рендер (`→`/`←`, `[mention]`,
`(cycle)`, «… (обрезано)» при усечении).

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
`{dataset_id, scope, checks_total, passed, checks[{id,status,message}], fix_mode}`.

`--scope` отбирает группу проверок: `dataset` (`config`, `index`), `environment` (`python`)
или `all`. Неизвестное значение — `usage.error` (exit 2), а не молчаливый полный прогон:
раньше флаг принимался и игнорировался (P1-4). `--scope` и `--check` сочетаются: сначала
группа, затем конкретные id.

### `status`
Быстрый снимок: `data.datasets[]`:
`{dataset_id, index_built, generation_id, documents, records}`.
Читает опубликованное поколение, не пересобирая индекс.

До первой пересборки `index_built: false`, а `documents`/`records` — `null`, не `0`: нули
читались как «в датасете ничего нет» (P1-6). В этом случае конверт несёт `next_actions`
с `todoc index rebuild`.

### `state set KEY VALUE` / `state get KEY` / `state list [--prefix P]` / `state unset KEY`

Агентский стейт сессии: `{XDG_STATE_HOME|~/.local/state}/todoc/state-<dataset_id>.json`
— вне данных и Git. v1 — белый список ключей `context.current_project`; значение —
строка 1–256 символов. Конверты: set → `{ok, key, value, updated_at}`; get →
`{ok, key, value|null}`; list → `{ok, vars}`; unset → `{ok, key, removed}`.
Коды ошибок: `state.unknown_key` (ключ вне whitelist), `state.invalid_value`,
`state.limit_exceeded` (>200 ключей или файл >64 КБ), `state.file_unavailable`.
Запись атомарная (tmp+rename); параллельные записи — «последний выигрывает».

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