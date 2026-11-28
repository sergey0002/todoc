# 03. Справочник CLI: 63 листовые команды

Перечень сверен машинным обходом click-групп 2026-11-26 (итерация 26.11 добавила 17 команд:
статусы, undo-relation, витрины флоу, links/suggest, skills ×4, state ×4, interop export —
происхождение каждой указано в разделе). Команды итерации 2026-11-25 описаны ниже как есть;
команды итерации 2026-11-26 собраны в блоке «Команды итерации 26.11».

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

### `init --root PATH [--dataset-id ID] [--apply]`
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

### `index status` / `index rebuild [--force] [--apply]`
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
| `log [--path P] [--section S] [--kind K] [--change C] [--history-tag T] [--since D] [--until D] [--limit N] [--cursor C]` | Свежие события в `data.result.items`, курсор в `data.meta.next_cursor`. `--section` требует `--path` |
| `show [REV] --path P [--budget B]` | Содержимое файла после события `REV`. Без `REV` возвращает текущий файл. `content` ограничивается `B` символами, `truncated` отмечает обрезку. |
| `diff REV_A [REV_B] --path P [--context N] [--budget B]` | `{changed, lines, diff[], truncated}`. Без `REV_B` сравнивает с текущим файлом. `B` включает переводы строк внутри diff. |
| `blame --path P [--section S] [--limit N] [--cursor C]` | События по файлу или разделу в `data.result.items`. |
| `revert REV --path P [--preview\|--apply] [--expected-hash H]` | По умолчанию показывает `{applied: false, current_hash, new_hash, range_conflict}`. `--apply` пишет файл и событие. Изменения после `REV` отмечаются предупреждением `history.range_conflict`. |
| `tag NAME [--rev R] [--message M] [--preview\|--apply] [--if-plan-hash H]` | Показывает план для выбранного события. Без `--rev` выбирает последнее событие. `--apply` записывает метку. |
| `history gc [--keep-objects N] [--purge-before D] [--preview\|--apply] [--if-plan-hash H]` | Показывает план удаления событий и снимков. `--dry-run` равнозначен `--preview`. `--apply` очищает историю. |
| `history adopt [--preview\|--apply] [--if-plan-hash H]` | Показывает число файлов в базовой линии. `--apply` записывает базовую линию и возвращает `rev`. |
| `history export --to PATH [--preview\|--apply] [--if-plan-hash H]` | Показывает число файлов истории. `--apply` копирует их в новый каталог внутри DATA_ROOT. |

Команды истории возвращают результат в `data.result`. Метаданные конверта не входят в `--budget`. `tag`, `history gc`, `history adopt` и `history export` возвращают `plan_hash`. Его можно передать при применении плана с `--if-plan-hash`.

Семантика `show` и `revert` намеренно расходится на один шаг и повторяет git: `show REV` —
состояние **после** события (как `git show <c>:<path>`), а `revert REV` — образ **до** него
(как `git revert <c>`). Откат события создания файла или базовой линии невозможен: состояния
«до» не существует, команда отвечает `history.revision_unknown` с объяснением.

Хранится только образ «до». `history gc --apply` применяет план удаления сирот и лишних снимков.
`--purge-before` выбирает события старше даты. Очистка отклоняется, если удаляемое событие используется меткой. Исходные документы сохраняются.

Потолки обслуживания берутся из `limits` датасета и не влияют на запись в журнал — иначе
целостность файлов (P1) зависела бы от размера служебной папки:

| Лимит | По умолчанию | Что ограничивает |
|---|---|---|
| `max_journal_bytes` | 8388608 | `gc` подрезает самые старые события; счёт — в `trimmed_for_size` |
| `max_history_objects` | 20000 | значение по умолчанию для `--keep-objects`; счёт — в `objects_trimmed` |
| `max_diff_lines` | 2000 | строк на один diff в `context --with-diff` |

Явный `--keep-objects` важнее лимита. Обрезка снимков настоящая: у затёртой ревизии `show`
и `revert` честно отвечают `history.object_missing`, а не выдумывают содержимое.

### `timeline [--as-of D] [--path P] [--limit N] [--cursor C]`

Единая лента: события журнала (время знания) и интервалы фактов (время правды) в одном
хронологическом порядке. Строки в `data.result.items`, область, счётчик и курсор в `data.meta`. `--limit 0` показывает только счётчик.

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
| `change list [--status S] [--limit N] [--cursor C]` | Фильтр применяется до пагинации. Строки в `data.result.items`, счётчики и курсор в `data.meta`. |
| `change open --title T [--blocked-by ID]… [--artifact P]… [--apply]` | Показывает базовую линию и `plan_hash`. С `--apply` создаёт запись и папку. |
| `change show ID` | запись и её дельты: `{record, deltas[]}` |
| `change validate ID` | **применимость к живому состоянию**: `{applicable, errors}` + диагностики в конверте |
| `change verify ID` | три измерения без модели: `{found, status, findings[], clean}` |
| `change apply ID [--apply] [--if-hash PATH=sha256:…]` | без `--apply` — план; с `--apply` — bundle-транзакция «всё или ничего» |
| `change archive ID [--tag T] [--apply]` | Показывает план. С `--apply` переносит изменение в `changes/archive/` и при наличии `--tag` ставит метку. |
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

Один вызов собирает контекст задачи. `--budget` измеряется в символах Unicode, по умолчанию 8000.
Лимит учитывает фрагменты контекста. Поля конверта и служебные счётчики исключены из расчёта.


`data.result` содержит `change_id`, `tag`, `budget`, `truncated`, `record`, `deltas`, `events`,
`files`, `used_chars` и при `--with-diff` массив `diffs`. Порядок заполнения: запись →
дельты → события → файлы → диффы. Если фрагмент превышает оставшийся лимит, `truncated` равен `true`.
Для каждого diff также применяется `limits.max_diff_lines`.

Дифф считается от образа «до» первого события по файлу до текущего содержимого; без
базового хеша сравнивать не с чем, и вместо шума `revision_unknown` путь просто
пропускается.

### `explain-path PATH [--match Q]`
Объясняет типизацию пути — документы **и папки** (с `.config.json`-метой предка):
`{dataset_id, path, doc_type|dir_type, format, rule_source, document_id|folder_id}`.
`rule_source` показывает, какое правило сработало (`rule:<id>`, `reserved`, `default`, `ambiguous`).
`--match Q` — как в `docs tree --match`: путь участвует в скоринге Фазы A (план folder-config).

### `docs new --title T [--path P] [--type T] [--apply] [--if-plan-hash H]`
По умолчанию показывает план создания. `--apply` создаёт новый документ из шаблона.
`--type` выбирает тип документа; `--template` принимает **id типа или путь к файлу**
(путь должен лежать внутри DATA_ROOT). Плейсхолдеры шаблона подставляются как текст:
`{title}`, `{slug}`, `{date}`, `{type_id}`, `{id}`, `{format}`; неизвестные остаются как есть.
Если тип не объявил шаблон, документ создаётся как `# <заголовок>`.
`data.result` содержит `plan_hash`. После применения результат включает путь, хеш файла и источник шаблона
(`.todoc/doc_types/<id>/template.md`, путь к файлу, `type-without-template` или `none`).
Отказы: `types.unknown`, `types.template_missing`, `types.template_invalid` (шаблон нарушает
структуру своего типа — файл не создаётся), `docs.empty_title` (заголовок из одних пробелов,
exit 3), `docs.target_exists` (exit 5), `access.outside_data_root` (exit 4).

`docs.unsafe_path` (exit 3) — второй эшелон защиты внутри `write.py`: срабатывает, если целевой
путь начинается с `../` или `/` либо содержит `/../`. Через CLI до него обычно не доходит —
containment-проверка слоя команд отвечает раньше тем же `access.outside_data_root` (проверено
на `--path ../evil.md` и `--dir ../out`).

### `docs list [--type T] [--status S] [--status-missing] [--within PATH]`

Lists current document metadata for one DATA_ROOT. Use `--fields` or
`--exclude-fields` to project fields, and `--fields-help` to discover the
available fields without opening a dataset. The result keeps `id` and `path`.
For example:

```bash
todoc docs list --root KB --type idea --fields id,path,title,status --limit 100
```

Repeated statuses match any listed value; `--status-missing` matches a null
lifecycle status. Combine the status filter with an exact case-insensitive
`--tag`, a document type or a directory scope. The default limit is 50.
`data.result.items` contains the rows and `data.meta.next_cursor` advances the
same selection. A modified snapshot invalidates the cursor. A failed source
read yields an incomplete result and exit 6. A fully read empty selection
has `complete: true` and `total: 0`. Technical parsing state is `parse_status`.

### Поиск по метаданным

```bash
todoc docs list --root KB --type 'plan|idea|agent-skill' --attr-status 'active|draft'
todoc docs search --root KB --file-format markdown --tag-in 'cli|search'
todoc docs list --root KB --type plan --filter-fields
todoc records list --root KB --type task --attr-status planned
```

`--type` в команде документов проверяет эффективный тип, `--attr-doc_type` —
значение, объявленное в файле. Значения одного атрибута через `|` образуют
ИЛИ, разные атрибуты — И. Кавычки сохраняют `|` внутри аргумента.
`--tag-in` проверяет любой тег, `--tag-all` — все. У записей поле можно
переопределить в схеме типа локальным ключом `x-todoc-tag-field`.

`--filter-file` принимает JSON с версией 1. Пример диапазона дат и проверки
наличия свойства:

```json
{
  "schema_version": 1,
  "conditions": [
    {"field": "updated", "op": "gte", "value": "2026-01-01"},
    {"field": "status", "op": "exists", "value": true}
  ]
}
```

Поддерживаются `eq`, `in`, `has_any`, `has_all`, `exists`, `gte`, `lte`.
Пути к вложенным полям разделяются точками. Для `eq` с `null` совпадает
явный null. Проекция `--fields attributes` у `docs list/read` выдаёт
атрибуты источника.

### Общая схема документов

Датасет включает проверку общей схемы при наличии
`.todoc/document-metadata.schema.json` с JSON Schema Draft 2020-12.
`todoc init --apply --document-metadata --root KB` устанавливает стартовую схему.
`todoc types metadata --root KB` показывает, какие файлы требуют миграции.
Markdown хранит атрибуты во front matter, JSON-документ — в объекте
`meta`. Для legacy JSON поддерживаются плоские атрибуты. Типизированная
запись сохраняет собственную схему. Схема типа документа действует
вместе с общей. Посмотреть их поля и обязательность можно через
`todoc types show plan --kind doc_type --root KB`. При включении схемы
на существующем датасете сначала проверьте её на рабочей копии через
`check-config` и `validate --all`.

`docs new --path item.json` создаёт JSON-документ с `meta`. Для обоих
форматов атрибуты передаются через `--attributes-file F`, а `--preview`
выдаёт план создания.

### Правка метаданных

`docs edit` и `records edit` принимают один формат patch:

```json
{"metadata":[
  {"op":"set","field":"priority","value":2},
  {"op":"add_item","field":"tags","value":"cli"},
  {"op":"remove","field":"retired_attribute"}
]}
```

Доступны `set`, `remove`, `add_item`, `remove_item`. Просмотр показывает
изменения, значения и `data.result.expected_hash`. Передайте этот хеш в
`--apply --if-hash HASH`. Схема проверяется до записи. Удаление поля из
схемы само по себе не меняет сохранённые файлы.

### `docs search [--query Q] [--type T] [--limit N] [--within PATH] [--budget CHARS] [--cursor C]`

Лексический поиск с фильтрацией до ранжирования. С фильтром запрос
`--query` можно опустить. `data.result.items` содержит результаты,
`data.meta.next_cursor` — курсор, связанный со снимком и параметрами
отбора. `--budget` ограничивает сумму символов Unicode в сниппетах.

### `docs read --id ID [--section S | --anchor A | --line-range N-M | --pointer P | --columns C --rows R --where K=V] [--budget CHARS]`
Ограниченное чтение. Полезные поля в `data.result` зависят от формата:
- Markdown без селектора: `{title, headings[], text}` (`text` усекается до `--budget`, по умолчанию 4000 символов);
- Markdown с `--section`/`--anchor`: `{section, heading_path, lines[], text}` — окно до 40 строк от заголовка;
- Markdown с `--line-range`: `{lines[], text}`;
- JSON: `{value}` (с `--pointer` — значение по RFC 6901);
- CSV: `{columns, rows[], total, matched, truncated}`. `--where` применяется **до** `--rows`:
  `--rows 3 --where k=v` возвращает три подходящие строки, а не три первые с последующей
  фильтрацией (P1-5). `matched` — сколько строк подошло под условие, `total` — сколько их в файле.
Общие поля: `{dataset_id, id, path, format, doc_type, hash}`.
Бюджет считает символы полезного текста, включая переводы строк. Метаданные
не входят в лимит. Для JSON и CSV используются селекторы их формата.
Некорректный `--line-range` — `usage.invalid_line_range` (exit 3).

Поля текущей формы ответа можно выбрать через `--fields a,b` или исключить
через `--exclude-fields a,b`. Для чтения секции с одним текстовым
представлением используйте `--exclude-fields lines`. ID, путь, хеш и
координаты секции сохраняются.

### `docs tree [--within PATH] [--depth N] [--match Q] [--limit N] [--cursor C]`
`--match Q` — фильтр папок скорингом Фазы A (`.config.json`, score ≥ 0.25, порядок
score → order → путь; план [folder-config](../../demo/plan/folder-config-implementation.md),
fm done). Папки получают плоские поля `title/description/order` из ближайшего СВОЕГО конфига.
`--max-depth` — прежнее имя `--depth`. Глубина считается относительно
`--within` (по умолчанию `.`). Область имеет глубину 0, её непосредственные
потомки — глубину 1. Лимит применяется к общей странице папок и документов
(по умолчанию 50). По умолчанию выдаётся `data.result.root` с вложенными
`children`. Для таблицы плоских строк используйте `--view flat`;
результат находится в `data.result.items`. Счётчики и курсор находятся
в `data.meta`. Изменение области, фильтра или снимка инвалидирует курсор.

### `docs edit --id ID --patch-file F [--preview] [--apply] [--if-hash H]`
Патч: `{"ops": [{"line": 12, "text": "новая строка"}]}` — замена строк по 1-индексации.
Без `--apply` возвращается `{preview: true, ops}`. С `--apply` — `{applied: true, new_hash}`.
Несовпадение `--if-hash` — exit 5.

### `records create --type T --input-file F [--preview|--apply] [--if-plan-hash H]`
По умолчанию `data.result` содержит `preview`, `plan_hash` и `plan` с путём, содержимым, хешами и результатами проверок.
Для записи укажите `--apply`. При наличии `--if-plan-hash` команда отклоняет изменившийся план с кодом выхода 5.
Успешная запись возвращает `created` и `new_hash`. Повторный ID (`record.duplicate_id`) и занятый путь (`record.target_exists`) дают код 5. Неизвестный тип даёт код 3.

Флага `--if-hash-new` больше нет (P1-4): он принимался и ничего не делал, а гарантию
«только создание» команда даёт безусловно — ещё в preview. Флаг, намекающий, что guarantee
включается по желанию, вводил в заблуждение; вызов с ним теперь `usage.error` (exit 2).

### `records list [--type T] [--since D] [--until D] [--relation TYPE=ID] [--limit N] [--cursor C]`
Строки в `data.result.items`, счётчики и курсор в `data.meta`.

### `records query [--query-file F] [--filter-file F] [--as-of D] [--cursor C]`
QuerySpec: `{entity_type, filters, limit}`; фильтры поддерживают равенство, `$in`, `$gte`, `$lte`.
Строки в `data.result.items`, `data.meta.as_of` и `data.meta.next_cursor` описывают выборку.

`--as-of` срезает выборку по **времени правды**: остаются записи, для которых
`valid_from <= T < valid_to` и которые ещё не закрыты `superseded_at`. Интервал полуоткрытый,
поэтому на день `valid_to` записи в выборке уже нет. Записи без темпоральных полей видны
всегда — обратная совместимость. Неразбираемое значение `--as-of` — это
`temporal.invalid_instant` (exit 3), а не пустая выборка: отличить опечатку от правды
должно быть возможно.

### `records aggregate --type T --metric FIELD [--group-by FIELD] [--limit N] [--cursor C]`
`data.result.items` содержит группы с суммой, единицей измерения и ID источников. Формула в `data.result.formula`, курсор в `data.meta.next_cursor`.
Смешение единиц измерения в одной агрегации — `query.unit_mismatch` (exit 3).

### `records read --id ID [--view NAME]`
`data`: `{dataset_id, record_id, path, data}`. `--view` берёт список полей из `views` описателя типа.

### `relations graph --from ID [--type T] [--depth N] [--limit N]`
Обход учитывает входящие и исходящие рёбра. `data.result.edges` сохраняет исходное направление, кратность и происхождение.
`--view flat` выдаёт `data.result.items`, Markdown умеет выводить Mermaid.

### `types list` / `types show TYPE_ID` / `types prompt TYPE_ID [--kind K] [--op OP]` / `types guide [--out PATH] [--apply]`
`list`: строки типов в `data.result.items`, счётчики по видам в `data.meta.counts`.
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

### `doctor [--check IDS] [--scope S] [--fix] [--apply] [--if-plan-hash H]`
Проверяет `config`, `index` и `python`. `--fix` показывает план восстановления индекса.
Для восстановления укажите `--apply`. Результаты лежат в `data.result.datasets`, хеш плана в `repair.plan_hash`.

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

## Команды итерации 26.11 (после MVP-справки 25.11)

Все секции ниже сверены с `--help` и реальными запусками; происхождение — планы
и задачи из [13-demo-dataset.md](13-demo-dataset.md).

### `docs status --id ID [--set V]`
Чтение/смена статуса md-документа (план [«скилы-взаимодействия»](../../demo/plan/скилы-взаимодействия--захват--план--исполнение--переходы--жизненный-цикл.md), З2).
Набор статуса — `allowed_statuses` doc_type (`docs.status_not_allowed`, exit 3); документ
без поля `status` не получает его молча (`docs.no_status_field`); set — точечная замена
строки fm + бамп `updated:` (единый писатель created/updated), CAS + history-ревизия.
Ошибки: `docs.not_found`, `docs.no_status_field`, `usage.error` (обрамляющие пробелы).

### `records status --id ID [--set V]`
Чтение/смена статуса JSON-записи; меняется ТОЛЬКО `status` (см. `--help`).
Набор — enum статуса из schema.json entity_type (`records.status_not_allowed`, pre-check —
файл не трогается); атомарно поверх CAS, history-ревизия. Ошибки: `records.not_found`,
`records.status_not_allowed`, `usage.error`.

### `records undo-relation --id ID --pointer /relations/N [--apply] [--expected-hash H]`
Точечный откат ребра из ревизий журнала (план [entity-catalog](../../demo/plan/entity-catalog-implementation.md),
u-graph): preview по умолчанию, с `--apply` — CAS-запись. Подходит для отката ошибочного
`implements`/`subtask_of`/`belongs_to` (план «скилы-взаимодействия» З3 добавил типы).

### `docs flow render --id FLOW_ID [--section state|table|mermaid|lineage|terms] [--write PATH]`
Витрина флоу из записи (план entity-catalog): state machine, таблица решений («Режим»),
mermaid, lineage, термины. `--write PATH` материализует витрину в md с fm `derived_from`
на фрагменты записи (`/states`, `/outcomes`, `/tree`, `/relations`); перезапись — только
derived-целей (`docs.flow_render_not_derived`), дрейф ловит `stale`.

### `docs flow walk --id FLOW_ID [--at NODE] [--all-paths]`
Пройти дерево решений: ветви по приоритету, props развилок (`mode`/`default_branch`);
`--all-paths` — все ациклические пути до терминалов.

### `docs links [--limit N]`
Инвентаризация локальных ссылок: `{total, broken[]}` (BUG-007 fixed; тот же резолв, что в validate).

### `docs suggest --query Q [--limit N]`
Куда положить/где искать: скоринг папок по `.config.json` (Фаза A, детерминированно;
план folder-config). Кирилица работает.

### `relations tree --from ID [--type T] [--depth N] [--limit N]`
Вложенное дерево связей (группировка по `type_id`, mention помечен) — план entity-catalog.

### `skills tree [--vault V] [--within P] [--query Q] [--all] [--limit N] [--depth N] [--view tree|flat] [--fields F] [--exclude-fields F] [--cursor C]` / `skills read --path P [--line-range A-B] [--budget B]` / `skills attach --to DIR [--force]` / `skills import --src S --into SEC [--skill N] [--dry-run] [--adopt]`
Хранилище-движок скилов (план [skills-vault](../../demo/plan/skills-vault-implementation.md), идея
[skills-engine](../../demo/ideas/skills-engine.md)). Полное описание — [17-skills-and-vault.md](17-skills-and-vault.md):
формат Agent Skills, confinement, диспетчер-скил, мьют через `!`.
Список скилов фильтруется в пределах vault до пагинации. `--depth` (`--max-depth`)
считает глубину от `--within`. Путь и ID сохраняются при любой проекции.
`tree` возвращает иерархию в `data.result.root`, `flat` возвращает строки в
`data.result.items`. Курсор действует в обоих видах для той же выборки.
Неизвестный вид возвращает `tree` с диагностикой `view.fallback`. Каталог `!`
скрывает также скилы в дочерних папках, пока не передан `--all`.

### `state get KEY`, `state list`, `state set KEY VALUE [--apply]`, `state unset KEY [--apply]`
Агентский стейт хранится в `$XDG_STATE_HOME/todoc/state-<dataset_id>.json` (план [агентский-стейт v1](../../demo/plan/агентский-стейт--state-json-в-движке--v1---текущий-проект.md)):
Допустимый ключ — `context.current_project`. Неизвестный ключ даёт `state.unknown_key`.
Запись и удаление требуют `--apply`. Подробнее — [18-agent-state-and-context.md](18-agent-state-and-context.md).

### `interop export --kind dmn|asl|rasa --id ID [--write exports/…md]`
Экспорт витрин во внешние форматы (план [интероп-экспорты](../../demo/plan/interop-exports-dmn-asl-rasa.md),
DoD 3/3): flow→ASL, rule→DMN 1.3 (decision table), term→Rasa NLU YML; derived-артефакт
с fm `derived_from` на записи-источники; `--write` только внутри `exports/`, перезапись
только derived-целей; записи не трогаются. Контракт маппинга и коды ошибок —
[19-interop-exports.md](19-interop-exports.md).

## Типовые последовательности

```bash
todoc init --apply --root KB && todoc check-config --root KB
todoc index rebuild --apply --root KB && todoc status --root KB
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
