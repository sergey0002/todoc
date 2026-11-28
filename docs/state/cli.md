# Полный справочник CLI

Справочник сгенерирован из дерева Click. Листовых команд: 67.

Порядок опций, форматы ответа и примеры описаны в [контракте CLI](03-cli-reference.md).

## Указатель

- [`todoc`](#todoc)
- [`blame`](#blame)
- [`change`](#change)
- [`change apply`](#change-apply)
- [`change archive`](#change-archive)
- [`change list`](#change-list)
- [`change open`](#change-open)
- [`change revert`](#change-revert)
- [`change show`](#change-show)
- [`change validate`](#change-validate)
- [`change verify`](#change-verify)
- [`check`](#check)
- [`check-config`](#check-config)
- [`context`](#context)
- [`diff`](#diff)
- [`docs`](#docs)
- [`docs edit`](#docs-edit)
- [`docs flow`](#docs-flow)
- [`docs flow render`](#docs-flow-render)
- [`docs flow walk`](#docs-flow-walk)
- [`docs links`](#docs-links)
- [`docs list`](#docs-list)
- [`docs new`](#docs-new)
- [`docs read`](#docs-read)
- [`docs search`](#docs-search)
- [`docs status`](#docs-status)
- [`docs suggest`](#docs-suggest)
- [`docs tree`](#docs-tree)
- [`doctor`](#doctor)
- [`explain-path`](#explain-path)
- [`fix`](#fix)
- [`history`](#history)
- [`history adopt`](#history-adopt)
- [`history export`](#history-export)
- [`history gc`](#history-gc)
- [`index`](#index)
- [`index rebuild`](#index-rebuild)
- [`index status`](#index-status)
- [`init`](#init)
- [`interop`](#interop)
- [`interop export`](#interop-export)
- [`log`](#log)
- [`records`](#records)
- [`records aggregate`](#records-aggregate)
- [`records create`](#records-create)
- [`records edit`](#records-edit)
- [`records list`](#records-list)
- [`records query`](#records-query)
- [`records read`](#records-read)
- [`records status`](#records-status)
- [`records undo-relation`](#records-undo-relation)
- [`relations`](#relations)
- [`relations graph`](#relations-graph)
- [`relations tree`](#relations-tree)
- [`revert`](#revert)
- [`scan`](#scan)
- [`show`](#show)
- [`skills`](#skills)
- [`skills attach`](#skills-attach)
- [`skills import`](#skills-import)
- [`skills read`](#skills-read)
- [`skills tree`](#skills-tree)
- [`stale`](#stale)
- [`state`](#state)
- [`state get`](#state-get)
- [`state list`](#state-list)
- [`state set`](#state-set)
- [`state unset`](#state-unset)
- [`status`](#status)
- [`sync`](#sync)
- [`tag`](#tag)
- [`timeline`](#timeline)
- [`types`](#types)
- [`types guide`](#types-guide)
- [`types list`](#types-list)
- [`types metadata`](#types-metadata)
- [`types prompt`](#types-prompt)
- [`types show`](#types-show)
- [`validate`](#validate)

## Команды

### todoc

```text
Usage: todoc [OPTIONS] [COMMAND] [ARGS]...

  todoc — portable typed knowledge substrate (validator + bounded search/read).

Options:
  --root TEXT                     DATA_ROOT (repeatable). Or set TODOC_ROOT.
  --output [json|table|markdown]  [default: json]
  --no-input                      Non-interactive mode (never prompts).
  --version                       Show the version and exit.
  --help                          Show this message and exit.

Commands:
  blame         List changes to a file or one of its sections.
  change        Записи изменений: жизненный цикл, проверка применимости, bundle-применение.
  check         Short health summary + general diagnostics (multi-root isolated).
  check-config  Validate dataset configs before use.
  context       Весь контекст задачи одним вызовом, в пределах бюджета в символах.
  diff          Разница между двумя ревизиями файла; без rev_b — против текущего состояния.
  docs          Document operations.
  doctor        Report checks and optionally repair the derived index.
  explain-path  Show resolved type/rule for a path — документы И папки (с .config.json-метой...
  fix           Preview/apply a supported fix (review-first).
  history       Обслуживание истории: сборка мусора, миграция, бэкап.
  index         Index status/rebuild (derived, rebuildable).
  init          Create portable .todoc/ control files (never scans/moves user data).
  interop       Экспорт витрин во внешние форматы (DMN 1.3 / ASL / Rasa NLU YML).
  log           List matching history events in reverse journal order.
  records       Typed records operations.
  relations     Typed relations.
  revert        Откат файла к ревизии.
  scan          Deterministic traversal without writing indexes.
  show          Содержимое файла на ревизии (или текущее, если rev не задан).
  skills        Skills vault (open Agent Skills standard): tree/read/attach/import.
  stale         Report documents whose dependencies drifted, or acknowledge a drift.
  state         Агентский стейт сессии (v1): state.json вне данных, XDG_STATE_HOME.
  status        Quick state snapshot (distinct from doctor).
  sync          Finalize direct file edits: bump updated, record history, refresh index, and...
  tag           Метка на ревизии: привязка истории к релизу.
  timeline      List journal events and fact intervals in chronological order.
  types         Type catalog.
  validate      Detailed file/rule/location report.
```

### blame

```text
Usage: todoc blame [OPTIONS]

  List changes to a file or one of its sections.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --path TEXT                     [required]
  --section TEXT
  --fields TEXT
  --exclude-fields TEXT
  --limit INTEGER RANGE           [default: 50; 1<=x<=1000]
  --cursor TEXT
  --view TEXT
  --help                          Show this message and exit.
```

### change

```text
Usage: todoc change [OPTIONS] [COMMAND] [ARGS]...

  Записи изменений: жизненный цикл, проверка применимости, bundle-применение.

Options:
  --root TEXT                     Dataset root (repeatable).
  --output [json|table|markdown]
  --no-input
  --help                          Show this message and exit.

Commands:
  apply     Bundle-транзакция: без --apply показывает план, с --apply пишет всё или ничего.
  archive   Показывает план архивации и применяет его по --apply.
  list      List active and archived changes, with filters applied before pagination.
  open      Открывает изменение и снимает базовую линию.
  revert    Откат применения к базовой линии изменения.
  show      Запись изменения и её дельты.
  validate  Применимость дельт к живому состоянию: цель, якорь, base_hash, структура после.
  verify    Completeness / correctness / coherence — детерминированно, без модели.
```

### change apply

```text
Usage: todoc change apply [OPTIONS] CHANGE_ID

  Bundle-транзакция: без --apply показывает план, с --apply пишет всё или ничего.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --preview
  --apply
  --if-hash TEXT                  PATH=sha256:… — отказ, если файл ушёл.
  --help                          Show this message and exit.
```

### change archive

```text
Usage: todoc change archive [OPTIONS] CHANGE_ID

  Показывает план архивации и применяет его по --apply.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --tag TEXT
  --preview
  --apply
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### change list

```text
Usage: todoc change list [OPTIONS]

  List active and archived changes, with filters applied before pagination.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --status TEXT
  --view TEXT
  --fields TEXT
  --exclude-fields TEXT
  --limit INTEGER RANGE           [default: 50; 1<=x<=1000]
  --cursor TEXT
  --help                          Show this message and exit.
```

### change open

```text
Usage: todoc change open [OPTIONS]

  Открывает изменение и снимает базовую линию.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --title TEXT                    [required]
  --blocked-by TEXT
  --artifact TEXT
  --preview
  --apply
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### change revert

```text
Usage: todoc change revert [OPTIONS] CHANGE_ID

  Откат применения к базовой линии изменения. Без --apply — только план.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --preview
  --apply
  --help                          Show this message and exit.
```

### change show

```text
Usage: todoc change show [OPTIONS] CHANGE_ID

  Запись изменения и её дельты.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --help                          Show this message and exit.
```

### change validate

```text
Usage: todoc change validate [OPTIONS] CHANGE_ID

  Применимость дельт к живому состоянию: цель, якорь, base_hash, структура после.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --help                          Show this message and exit.
```

### change verify

```text
Usage: todoc change verify [OPTIONS] CHANGE_ID

  Completeness / correctness / coherence — детерминированно, без модели.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --help                          Show this message and exit.
```

### check

```text
Usage: todoc check [OPTIONS]

  Short health summary + general diagnostics (multi-root isolated).

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --strict                        Warnings become failures.
  --help                          Show this message and exit.
```

### check-config

```text
Usage: todoc check-config [OPTIONS]

  Validate dataset configs before use.

  Reports unknown descriptor fields, malformed structure rules and declared template/prompt files
  that are missing on disk — a config that silently accepts a rule it never enforces is worse than
  one that refuses it.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --help                          Show this message and exit.
```

### context

```text
Usage: todoc context [OPTIONS]

  Весь контекст задачи одним вызовом, в пределах бюджета в символах.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --change TEXT
  --tag TEXT
  --budget INTEGER RANGE          [default: 8000; x>=1]
  --with-diff
  --help                          Show this message and exit.
```

### diff

```text
Usage: todoc diff [OPTIONS] [REV_A] [REV_B]

  Разница между двумя ревизиями файла; без rev_b — против текущего состояния.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --path TEXT                     [required]
  --context INTEGER RANGE         [x>=0]
  --budget INTEGER RANGE          [x>=1]
  --help                          Show this message and exit.
```

### docs

```text
Usage: todoc docs [OPTIONS] [COMMAND] [ARGS]...

  Document operations.

Options:
  --root TEXT                     Dataset root (repeatable).
  --output [json|table|markdown]
  --no-input
  --help                          Show this message and exit.

Commands:
  edit     Review-first patch edit (preview default, --apply to write).
  flow     Витрина и навигатор дерева решений флоу (entity-catalog T1/T2).
  links    Audit broken local Markdown links with source coordinates.
  list     List current document metadata.
  new      Create a document from its type's starter template (create-only, no-overwrite).
  read     Bounded projection read (section/pointer/columns).
  search   Search document text or apply metadata filters with --attr-NAME 'value1|value2'.
  status   Чтение/смена статуса md-документа: fm `status`, набор — allowed_statuses его doc_type.
  suggest  Rank folders using their declared titles, tags and aliases.
  tree     Compact derived outline (folders + documents).
```

### docs edit

```text
Usage: todoc docs edit [OPTIONS]

  Review-first patch edit (preview default, --apply to write).

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --id TEXT                       [required]
  --patch-file TEXT               [required]
  --if-hash TEXT
  --preview
  --apply
  --help                          Show this message and exit.
```

### docs flow

```text
Usage: todoc docs flow [OPTIONS] [COMMAND] [ARGS]...

  Витрина и навигатор дерева решений флоу (entity-catalog T1/T2).

Options:
  --root TEXT                     Dataset root (repeatable).
  --output [json|table|markdown]
  --no-input
  --help                          Show this message and exit.

Commands:
  render  Витрина флоу из записи: state machine, таблица решений (Режим), mermaid, lineage,...
  walk    Пройти дерево решений флоу: ветви по приоритету, props развилок, пути до терминалов.
```

### docs flow render

```text
Usage: todoc docs flow render [OPTIONS]

  Витрина флоу из записи: state machine, таблица решений (Режим), mermaid, lineage, термины.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --id TEXT                       [required]
  --section [state|table|mermaid|lineage|terms]
                                  Одна секция витрины вместо полного markdown.
  --write TEXT                    Материализовать витрину в файл (fm derived_from).
  --preview
  --apply
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### docs flow walk

```text
Usage: todoc docs flow walk [OPTIONS]

  Пройти дерево решений флоу: ветви по приоритету, props развилок, пути до терминалов.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --id TEXT                       [required]
  --at TEXT                       Старт обхода с узла дерева (id узла).
  --all-paths                     Все ациклические пути до терминалов вместо основного.
  --help                          Show this message and exit.
```

### docs links

```text
Usage: todoc docs links [OPTIONS]

  Audit broken local Markdown links with source coordinates.

Options:
  --root TEXT
  --output [json|table|markdown]
  --limit INTEGER RANGE           [1<=x<=1000]
  --no-input
  --within TEXT
  --cursor TEXT
  --fields TEXT
  --exclude-fields TEXT
  --help                          Show this message and exit.
```

### docs list

```text
Usage: todoc docs list [OPTIONS]

  List current document metadata. Filter with --attr-NAME 'value1|value2'.

Options:
  --root TEXT
  --output [json|table|markdown]
  --no-input
  --type TEXT                     Effective document type; separate alternatives by |.
  --within TEXT
  --tag TEXT
  --tag-in TEXT                   Match at least one tag, separated by |.
  --tag-all TEXT                  Match every tag, separated by |.
  --file-format [markdown|json|csv|opaque]
  --filter-file FILE
  --filter-fields                 List declared and observed metadata fields in this scope.
  --status TEXT
  --status-missing
  --fields TEXT
  --exclude-fields TEXT
  --fields-help
  --view TEXT
  --limit INTEGER RANGE           [default: 50; 1<=x<=1000]
  --cursor TEXT
  --help                          Show this message and exit.
```

### docs new

```text
Usage: todoc docs new [OPTIONS]

  Create a document from its type's starter template (create-only, no-overwrite).

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --title TEXT                    [required]
  --dir TEXT
  --path TEXT                     Явный относительный путь вместо --dir + slug.
  --type TEXT                     Тип документа: шаблон и структура из папки типа.
  --template TEXT                 Тип документа или путь к файлу шаблона.
  --attributes-file TEXT          JSON object with custom document metadata.
  --preview                       Show the write plan without creating the file.
  --apply
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### docs read

```text
Usage: todoc docs read [OPTIONS]

  Bounded projection read (section/pointer/columns).

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --id TEXT
  --section TEXT
  --anchor TEXT
  --line-range TEXT
  --pointer TEXT
  --columns TEXT
  --rows INTEGER RANGE            [x>=1]
  --where TEXT
  --budget INTEGER RANGE          Maximum number of Unicode characters of text content.  [x>=1]
  --fields TEXT
  --exclude-fields TEXT
  --help                          Show this message and exit.
```

### docs search

```text
Usage: todoc docs search [OPTIONS]

  Search document text or apply metadata filters with --attr-NAME 'value1|value2'.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --type TEXT                     Effective document type; separate alternatives by |.
  --query TEXT
  --budget INTEGER RANGE          Maximum number of Unicode characters across result snippets.
                                  [x>=1]
  --limit INTEGER RANGE           [1<=x<=1000]
  --within TEXT
  --cursor TEXT
  --tag TEXT                      Match one exact tag.
  --tag-in TEXT                   Match at least one tag, separated by |.
  --tag-all TEXT                  Match every tag, separated by |.
  --file-format [markdown|json|csv|opaque]
  --filter-file FILE
  --fields TEXT
  --exclude-fields TEXT
  --view TEXT
  --help                          Show this message and exit.
```

### docs status

```text
Usage: todoc docs status [OPTIONS]

  Чтение/смена статуса md-документа: fm `status`, набор — allowed_statuses его doc_type.

  План «скилы-взаимодействия» З2: точечная замена строки статуса без перестройки документа,
  `updated:` бампается (единый писатель created/updated), history-ревизия. Документ без поля status
  не получает его молча — set отказ (docs.no_status_field).

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --id TEXT                       [required]
  --set TEXT                      Новое значение статуса (без --set — чтение).
  --preview
  --apply
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### docs suggest

```text
Usage: todoc docs suggest [OPTIONS]

  Rank folders using their declared titles, tags and aliases.

Options:
  --root TEXT
  --query TEXT                    Search for a place to file or find documents.
  --limit INTEGER RANGE           [1<=x<=1000]
  --output [json|table|markdown]
  --no-input
  --within TEXT
  --fields TEXT
  --exclude-fields TEXT
  --cursor TEXT
  --help                          Show this message and exit.
```

### docs tree

```text
Usage: todoc docs tree [OPTIONS]

  Compact derived outline (folders + documents).

Options:
  --root TEXT
  --output [json|table|markdown]
  --no-input
  --within TEXT
  --depth, --max-depth INTEGER RANGE
                                  [x>=0]
  --limit INTEGER RANGE           [1<=x<=1000]
  --cursor TEXT
  --view TEXT
  --fields TEXT
  --exclude-fields TEXT
  --match TEXT                    Фильтр папок Фазой A скоринга (.config.json): score ≥ 0.25,
                                  порядок score → order → путь.
  --help                          Show this message and exit.
```

### doctor

```text
Usage: todoc doctor [OPTIONS]

  Report checks and optionally repair the derived index.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --check TEXT                    Comma-separated check ids.
  --scope TEXT                    Группа проверок: dataset | environment | all.
  --fix                           Preview rebuilding a missing, stale, or corrupt index.
  --preview
  --apply
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### explain-path

```text
Usage: todoc explain-path [OPTIONS] PATH

  Show resolved type/rule for a path — документы И папки (с .config.json-метой предка).

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --help                          Show this message and exit.
```

### fix

```text
Usage: todoc fix [OPTIONS]

  Preview/apply a supported fix (review-first).

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --diagnostic TEXT               [required]
  --preview
  --apply
  --if-hash TEXT
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### history

```text
Usage: todoc history [OPTIONS] [COMMAND] [ARGS]...

  Обслуживание истории: сборка мусора, миграция, бэкап.

Options:
  --root TEXT                     Dataset root (repeatable).
  --output [json|table|markdown]
  --no-input
  --help                          Show this message and exit.

Commands:
  adopt   Миграция: снимок текущего состояния как базовая линия журнала.
  export  Preview a backup manifest and export it into a new directory.
  gc      Удаляет события и снимки согласно плану очистки.
```

### history adopt

```text
Usage: todoc history adopt [OPTIONS]

  Миграция: снимок текущего состояния как базовая линия журнала.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --preview
  --apply
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### history export

```text
Usage: todoc history export [OPTIONS]

  Preview a backup manifest and export it into a new directory.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --to TEXT                       [required]
  --preview
  --apply
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### history gc

```text
Usage: todoc history gc [OPTIONS]

  Удаляет события и снимки согласно плану очистки.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --keep-objects INTEGER RANGE    [x>=0]
  --purge-before TEXT
  --dry-run, --preview            Preview without modifying history.
  --apply                         Apply history cleanup.
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### index

```text
Usage: todoc index [OPTIONS] [COMMAND] [ARGS]...

  Index status/rebuild (derived, rebuildable).

Options:
  --root TEXT                     Dataset root (repeatable).
  --output [json|table|markdown]
  --no-input
  --help                          Show this message and exit.

Commands:
  rebuild  Preview or publish a rebuilt index.
  status
```

### index rebuild

```text
Usage: todoc index rebuild [OPTIONS]

  Preview or publish a rebuilt index.

Options:
  --root TEXT
  --force                         Recompute even when the corpus digest is unchanged.
  --output [json|table|markdown]  [default: json]
  --no-input
  --preview
  --apply
  --help                          Show this message and exit.
```

### index status

```text
Usage: todoc index status [OPTIONS]

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --help                          Show this message and exit.
```

### init

```text
Usage: todoc init [OPTIONS]

  Create portable .todoc/ control files (never scans/moves user data).

Options:
  --root TEXT                     DATA_ROOT to initialize.  [required]
  --dataset-id TEXT               Идентификатор датасета. По умолчанию случаен; явное значение
                                  делает демо-датасет и фикстуры воспроизводимыми.
  --output [json|table|markdown]  [default: json]
  --no-input
  --document-metadata             Install the shared schema for managed documents.
  --preview
  --apply
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### interop

```text
Usage: todoc interop [OPTIONS] [COMMAND] [ARGS]...

  Экспорт витрин во внешние форматы (DMN 1.3 / ASL / Rasa NLU YML).

Options:
  --root TEXT                     Dataset root (repeatable).
  --output [json|table|markdown]
  --no-input
  --help                          Show this message and exit.

Commands:
  export  Запись-источник → артефакт внешнего формата (derived-артефакт, review-first).
```

### interop export

```text
Usage: todoc interop export [OPTIONS]

  Запись-источник → артефакт внешнего формата (derived-артефакт, review-first).

  Без --write артефакт печатается в stdout; с --write — markdown-документ в exports/ с fm
  derived_from на записи-источники (дрейф ловит `todoc stale`). Перезапись поверх CAS разрешена
  только для derived-целей; записи не трогаются.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --kind [dmn|asl|rasa]           [required]
  --id TEXT                       record_id источника (для rasa можно опустить — весь глоссарий).
  --write PATH                    Путь экспорта относительно корня (только exports/…); без него
                                  артефакт печатается в stdout.
  --preview
  --apply
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### log

```text
Usage: todoc log [OPTIONS]

  List matching history events in reverse journal order.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --path TEXT
  --section TEXT                  Только события, пересекающие этот заголовок.
  --change TEXT
  --history-tag, --tag TEXT
  --kind TEXT
  --since TEXT
  --until TEXT
  --limit INTEGER RANGE           [1<=x<=1000]
  --cursor TEXT
  --fields TEXT
  --exclude-fields TEXT
  --view TEXT
  --help                          Show this message and exit.
```

### records

```text
Usage: todoc records [OPTIONS] [COMMAND] [ARGS]...

  Typed records operations.

Options:
  --root TEXT                     Dataset root (repeatable).
  --output [json|table|markdown]
  --no-input
  --help                          Show this message and exit.

Commands:
  aggregate      Sum a numeric field with units and source records for each group.
  create         Create-only new JSON record (preview default).
  edit           Preview or apply a structured patch to a typed record.
  list           List records with optional filters.
  query          Run a saved QuerySpec and optional metadata conditions.
  read           Read one record and its source references.
  status         Чтение/смена статуса JSON-записи: меняется ТОЛЬКО поле `status`.
  undo-relation  Точечный откат ребра из ревизий журнала (preview по умолчанию).
```

### records aggregate

```text
Usage: todoc records aggregate [OPTIONS]

  Sum a numeric field with units and source records for each group.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --metric TEXT                   [required]
  --group-by TEXT
  --type TEXT                     [required]
  --view TEXT
  --fields TEXT
  --exclude-fields TEXT
  --limit INTEGER RANGE           [default: 50; 1<=x<=1000]
  --cursor TEXT
  --help                          Show this message and exit.
```

### records create

```text
Usage: todoc records create [OPTIONS]

  Create-only new JSON record (preview default).

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --type TEXT                     [required]
  --input-file TEXT               [required]
  --preview
  --apply
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### records edit

```text
Usage: todoc records edit [OPTIONS]

  Preview or apply a structured patch to a typed record.

Options:
  --root TEXT
  --output [json|table|markdown]
  --id TEXT                       [required]
  --patch-file TEXT               [required]
  --if-hash TEXT
  --preview
  --apply
  --help                          Show this message and exit.
```

### records list

```text
Usage: todoc records list [OPTIONS]

  List records with optional filters.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --type TEXT
  --since TEXT
  --until TEXT
  --relation TEXT
  --limit INTEGER RANGE           [1<=x<=1000]
  --filter-file FILE
  --tag-in TEXT                   Match at least one tag, separated by |.
  --tag-all TEXT                  Match every tag, separated by |.
  --view TEXT
  --fields TEXT
  --exclude-fields TEXT
  --cursor TEXT
  --help                          Show this message and exit.
```

### records query

```text
Usage: todoc records query [OPTIONS]

  Run a saved QuerySpec and optional metadata conditions.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --query-file TEXT
  --as-of TEXT                    Только записи, бывшие правдой на этот момент.
  --filter-file FILE
  --tag-in TEXT                   Match at least one tag, separated by |.
  --tag-all TEXT                  Match every tag, separated by |.
  --view TEXT
  --fields TEXT
  --exclude-fields TEXT
  --cursor TEXT
  --help                          Show this message and exit.
```

### records read

```text
Usage: todoc records read [OPTIONS]

  Read one record and its source references.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --id TEXT                       [required]
  --view TEXT
  --record-view TEXT
  --help                          Show this message and exit.
```

### records status

```text
Usage: todoc records status [OPTIONS]

  Чтение/смена статуса JSON-записи: меняется ТОЛЬКО поле `status`.

  План «скилы-взаимодействия» З2: записи иначе create-only; набор — enum статуса из схемы
  entity_type (до записи — records.status_not_allowed, файл не трогается); атомарная запись поверх
  CAS-хэша, history-ревизия.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --id TEXT                       [required]
  --set TEXT                      Новое значение статуса (без --set — чтение).
  --preview
  --apply
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### records undo-relation

```text
Usage: todoc records undo-relation [OPTIONS]

  Точечный откат ребра из ревизий журнала (preview по умолчанию).

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --id TEXT                       [required]
  --pointer TEXT                  Путь ребра: /relations/N  [required]
  --preview
  --apply
  --if-plan-hash TEXT
  --expected-hash TEXT
  --help                          Show this message and exit.
```

### relations

```text
Usage: todoc relations [OPTIONS] [COMMAND] [ARGS]...

  Typed relations.

Options:
  --root TEXT                     Dataset root (repeatable).
  --output [json|table|markdown]
  --no-input
  --help                          Show this message and exit.

Commands:
  graph  Browse directed typed relations and source mentions.
  tree   Return a page of relation traversal with ancestor context.
```

### relations graph

```text
Usage: todoc relations graph [OPTIONS]

  Browse directed typed relations and source mentions.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --from TEXT                     [required]
  --type TEXT
  --depth INTEGER RANGE           [0<=x<=100]
  --limit INTEGER RANGE           [1<=x<=1000]
  --cursor TEXT
  --view TEXT
  --fields TEXT
  --exclude-fields TEXT
  --help                          Show this message and exit.
```

### relations tree

```text
Usage: todoc relations tree [OPTIONS]

  Return a page of relation traversal with ancestor context.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --from TEXT                     [required]
  --type TEXT
  --depth INTEGER RANGE           [default: 1; 0<=x<=100]
  --limit INTEGER RANGE           [default: 100; 1<=x<=1000]
  --cursor TEXT
  --help                          Show this message and exit.
```

### revert

```text
Usage: todoc revert [OPTIONS] REV

  Откат файла к ревизии. Без --apply — только план (review-first).

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --path TEXT                     [required]
  --preview
  --apply
  --expected-hash TEXT
  --help                          Show this message and exit.
```

### scan

```text
Usage: todoc scan [OPTIONS]

  Deterministic traversal without writing indexes.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --help                          Show this message and exit.
```

### show

```text
Usage: todoc show [OPTIONS] [REV]

  Содержимое файла на ревизии (или текущее, если rev не задан).

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --path TEXT                     [required]
  --budget INTEGER RANGE          [x>=1]
  --help                          Show this message and exit.
```

### skills

```text
Usage: todoc skills [OPTIONS] [COMMAND] [ARGS]...

  Skills vault (open Agent Skills standard): tree/read/attach/import.

Options:
  --root TEXT                     Dataset root (repeatable).
  --output [json|table|markdown]
  --no-input
  --help                          Show this message and exit.

Commands:
  attach  Диспетчер-скил todoc → одна точка входа для любого агента.
  import  Офлайн-импорт чужих скилов: папки со SKILL.md, обвязка пакетов не переносится.
  read    Read one bounded skill source and its metadata.
  tree    Оглавление хранилища скилов на лету (live-scan, без индекса — P1).
```

### skills attach

```text
Usage: todoc skills attach [OPTIONS]

  Диспетчер-скил todoc → одна точка входа для любого агента.

  Копирует пакетную папку `todoc/` в платформенный каталог скилов, подставляя DATA_ROOT вместо
  {ROOT}. Витрина скилов в платформу НЕ монтируется — L1-контекст несёт ровно один скил (~100
  токенов) при vault любого размера.

Options:
  --to TEXT                       Каталог скилов платформы (.claude/skills/, .agents/skills/,
                                  .cursor/skills/, ...).  [required]
  --root TEXT                     DATA_ROOT, вшиваемый в тело диспетчера ({ROOT}).
  --force                         Перезаписать существующий скил todoc.
  --output [json|table|markdown]  [default: json]
  --no-input
  --preview
  --apply
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### skills import

```text
Usage: todoc skills import [OPTIONS]

  Офлайн-импорт чужих скилов: папки со SKILL.md, обвязка пакетов не переносится.

Options:
  --root TEXT
  --src TEXT                      Локальная папка-скил или репо-пакет (**/SKILL.md).  [required]
  --skill TEXT                    Копировать один скил (по имени папки).
  --into TEXT                     Раздел vault, куда класть (напр. coding/review).  [required]
  --vault TEXT                    [default: skills]
  --dry-run, --preview            Показать план без записи.
  --adopt                         Источник уже в vault: валидировать и отчитаться без копии.
  --output [json|table|markdown]  [default: json]
  --no-input
  --apply
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### skills read

```text
Usage: todoc skills read [OPTIONS]

  Read one bounded skill source and its metadata.

Options:
  --root TEXT
  --vault TEXT                    [default: skills]
  --path TEXT                     Skill folder or relative path to SKILL.md.
  --line-range TEXT               Inclusive line range A-B.
  --budget INTEGER RANGE          Maximum Unicode characters of skill content.  [default: 4000;
                                  x>=1]
  --output [json|table|markdown]
  --no-input
  --help                          Show this message and exit.
```

### skills tree

```text
Usage: todoc skills tree [OPTIONS]

  Оглавление хранилища скилов на лету (live-scan, без индекса — P1).

Options:
  --root TEXT
  --vault TEXT                    Vault dir relative to DATA_ROOT.  [default: skills]
  --within TEXT                   Срез раздела: префикс пути секции (напр. coding/git).
  --query TEXT                    Lowercase-подстрока по name+description+пути (кириллица работает).
  --all                           Показать мьютнутые (!-папки) с пометкой [!].
  --limit INTEGER RANGE           Bounded output (P7).  [default: 100; 1<=x<=1000]
  --max-depth, --depth INTEGER RANGE
                                  Глубина печатаемого дерева.  [default: 6; x>=0]
  --view TEXT                     [default: tree]
  --fields TEXT
  --exclude-fields TEXT
  --cursor TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --help                          Show this message and exit.
```

### stale

```text
Usage: todoc stale [OPTIONS]

  Report documents whose dependencies drifted, or acknowledge a drift.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --path TEXT                     Only this owner document/record.
  --severity TEXT                 Filter diagnostics by severity.
  --ack TEXT                      Acknowledge staleness of this owner.
  --reason TEXT                   Why the drift is not relevant (required with --ack).
  --preview
  --apply                         Write the acknowledgement (default: preview).
  --expected-hash TEXT
  --help                          Show this message and exit.
```

### state

```text
Usage: todoc state [OPTIONS] [COMMAND] [ARGS]...

  Агентский стейт сессии (v1): state.json вне данных, XDG_STATE_HOME.

Options:
  --root TEXT                     Dataset root (repeatable).
  --output [json|table|markdown]
  --no-input
  --help                          Show this message and exit.

Commands:
  get    Прочитать переменную стейта (value: null — не установлена).
  list   List dataset-scoped session variables.
  set    Показать или применить изменение переменной стейта.
  unset  Показать или применить удаление переменной стейта.
```

### state get

```text
Usage: todoc state get [OPTIONS] KEY

  Прочитать переменную стейта (value: null — не установлена).

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --help                          Show this message and exit.
```

### state list

```text
Usage: todoc state list [OPTIONS]

  List dataset-scoped session variables.

Options:
  --root TEXT
  --output [json|table|markdown]
  --no-input
  --prefix TEXT
  --fields TEXT
  --exclude-fields TEXT
  --limit INTEGER RANGE           [1<=x<=1000]
  --cursor TEXT
  --view TEXT
  --help                          Show this message and exit.
```

### state set

```text
Usage: todoc state set [OPTIONS] KEY VALUE

  Показать или применить изменение переменной стейта.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --preview
  --apply
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### state unset

```text
Usage: todoc state unset [OPTIONS] KEY

  Показать или применить удаление переменной стейта.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --preview
  --apply
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### status

```text
Usage: todoc status [OPTIONS]

  Quick state snapshot (distinct from doctor).

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --help                          Show this message and exit.
```

### sync

```text
Usage: todoc sync [OPTIONS] [PATHS]...

  Finalize direct file edits: bump updated, record history, refresh index, and validate.

Options:
  --root TEXT                     Dataset root directory.
  --output [json|table|markdown]  [default: json]
  --out TEXT                      Write envelope inside DATA_ROOT.
  --no-input
  --dirty                         Synchronize all locally modified/created/deleted data files.
  --if-hash TEXT                  Optimistic precondition hash before direct edit.
  --allow-derived                 Allow syncing generated views despite derived_from.
  --no-history                    Skip writing local history snapshot/journal event.
  --preview
  --apply
  --help                          Show this message and exit.
```

### tag

```text
Usage: todoc tag [OPTIONS] NAME

  Метка на ревизии: привязка истории к релизу.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --rev TEXT                      По умолчанию — последнее событие журнала.
  --message TEXT
  --preview
  --apply
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### timeline

```text
Usage: todoc timeline [OPTIONS]

  List journal events and fact intervals in chronological order.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --as-of TEXT                    Состояние на этот момент (ISO-8601).
  --path TEXT                     Только события и факты этого файла.
  --limit INTEGER RANGE           [default: 200; 0<=x<=1000]
  --cursor TEXT
  --fields TEXT
  --exclude-fields TEXT
  --view TEXT
  --help                          Show this message and exit.
```

### types

```text
Usage: todoc types [OPTIONS] [COMMAND] [ARGS]...

  Type catalog.

Options:
  --root TEXT                     Dataset root (repeatable).
  --output [json|table|markdown]
  --no-input
  --help                          Show this message and exit.

Commands:
  guide     Generated type reference (stdout or --out).
  list      List registered types with their kind and descriptor summary.
  metadata  Preview adoption of the common document metadata schema.
  prompt    Starter prompt of a type for one CRUD operation (read/create/edit/delete).
  show
```

### types guide

```text
Usage: todoc types guide [OPTIONS]

  Generated type reference (stdout or --out).

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --format [markdown|json]
  --out TEXT
  --preview
  --apply
  --if-plan-hash TEXT
  --help                          Show this message and exit.
```

### types list

```text
Usage: todoc types list [OPTIONS]

  List registered types with their kind and descriptor summary.

Options:
  --root TEXT
  --output [json|table|markdown]
  --no-input
  --kind [dir_type|doc_type|entity_type|relation_type]
  --fields TEXT
  --exclude-fields TEXT
  --limit INTEGER RANGE           [1<=x<=1000]
  --cursor TEXT
  --view TEXT
  --help                          Show this message and exit.
```

### types metadata

```text
Usage: todoc types metadata [OPTIONS]

  Preview adoption of the common document metadata schema.

Options:
  --root TEXT
  --output [json|table|markdown]
  --limit INTEGER RANGE           [1<=x<=1000]
  --cursor TEXT
  --help                          Show this message and exit.
```

### types prompt

```text
Usage: todoc types prompt [OPTIONS] TYPE_ID

  Starter prompt of a type for one CRUD operation (read/create/edit/delete).

Options:
  --kind [doc_type|entity_type]
  --op [read|create|edit|delete]  [default: create]
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --help                          Show this message and exit.
```

### types show

```text
Usage: todoc types show [OPTIONS] TYPE_ID

Options:
  --kind [dir_type|doc_type|entity_type|relation_type]
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --help                          Show this message and exit.
```

### validate

```text
Usage: todoc validate [OPTIONS]

  Detailed file/rule/location report.

Options:
  --root TEXT
  --output [json|table|markdown]  [default: json]
  --no-input
  --all
  --help                          Show this message and exit.
```
