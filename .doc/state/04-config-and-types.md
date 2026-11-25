# 04. Конфигурация и типовая система

## `dataset.json`

Создаётся `todoc init`. Поля (проверено по `config.default_dataset`):

| Поле | Значение по умолчанию | Смысл |
|---|---|---|
| `schema_version` | `1` | единственная поддерживаемая версия |
| `dataset_id` | `dataset-<8 hex>` | идентификатор датасета |
| `enabled_formats` | `["csv","json","markdown"]` | разрешённые форматы |
| `directory_rules` | `rules/directory-rules.json` | путь к правилам папок |
| `document_rules` | `rules/document-rules.json` | путь к правилам документов |
| `directory_types` / `document_types` / `entity_types` / `relation_types` | `dir_types` и т.д. | каталоги описателей |
| `queries` / `templates` | `queries`, `templates` | сохранённые запросы и шаблоны |
| `trusted_workflows` | `record-capture-v1` | объявление доверенного внешнего навыка |
| `follow_symlinks` | `false` | не следовать по symlink |
| `limits.max_file_bytes` | `10485760` | больше — статус `unsupported` |
| `limits.max_json_depth` | `128` | глубже — `json.too_deep` |
| `limits.max_csv_rows` | `1000000` | больше — `csv.too_many_rows` |
| `limits.max_query_results` | `200` | потолок выборки |
| `limits.max_record_create_path` | `512` | потолок длины пути записи |

## Что создаёт `init`

```
.todoc/
├── dataset.json
├── rules/{directory-rules.json, document-rules.json}
├── dir_types/{research, plan, architecture, constitution, harness, glossary}/type.json
├── doc_types/{adr, glossary-entry, research-note, note}/
│   ├── type.json
│   ├── template.md              # стартовый шаблон документа
│   └── prompts/{read,create,edit,delete}.md
├── entity_types/{note, research, link, plan, product, person, workout}/
│   ├── type.json
│   ├── template.json            # стартовая запись
│   └── prompts/{read,create,edit,delete}.md
├── relation_types/{performed_by, derived_from, supports, contradicts}/type.json
├── templates/records/note.json
├── schemas/records/          # пусто: схемы добавляет пользователь
├── queries/
└── generated/
```

Git не отслеживает пустые каталоги, поэтому `schemas/records/` и `queries/` после клонирования
могут отсутствовать — их создаёт `init` или пользователь.

Каждый тип документа и записи получает стартовый шаблон и четыре CRUD-промпта: `init` пишет
66 таких файлов (4 doc-типа + 7 entity-типов по 6 файлов).

## Описатель типа (`type.json`)

Обязательные поля: `schema_version: 1`, `type_id`. Остальные — по виду типа.

| Поле | Для кого | Как используется |
|---|---|---|
| `description`, `version`, `kind` | все | документация и `types guide` |
| `format` | doc_type, entity_type | ожидаемый формат |
| `required_fields` | entity_type | проверяется в `records create` |
| `path_template` | entity_type | целевой путь; подстановки `{record_id}`, `{slug}` |
| `views` | entity_type | проекции для `records read --view` |
| `metric_fields` | entity_type | единицы и формула (документативно) |
| `endpoints` | relation_type | допустимые концы ребра (документативно) |
| `template` | doc_type, entity_type | имя стартового шаблона в папке типа |
| `prompts` | doc_type, entity_type | переопределение путей CRUD-промптов |
| `required_sections` | doc_type | разделы, обязательные в документе |
| `section_rules` | doc_type | сколько подразделов нужно у заголовка |

Ошибка загрузки: `config.invalid_schema`, `config.unsupported_version`, `config.duplicate_type`,
`config.unknown_type` (правило ссылается на несуществующий тип — проверяется при загрузке контекста).

### Папка типа: шаблон и CRUD-промпты

```.todoc/doc_types/<id>/
├── type.json
├── template.md                  # или template.json для entity_type
└── prompts/
    ├── read.md                  # как читать документ/запись этого типа
    ├── create.md                # как создать
    ├── edit.md                  # как править (review-first, hash-предусловие)
    └── delete.md                # как безопасно снять с публикации
```

Промпты — инструкции для агента под конкретную операцию, а не общий текст: агент берёт
`types prompt <тип> --op <операция>` и получает ровно тот порядок действий, который нужен.
Пути по умолчанию не обязательны: `check-config` требует существования только явно объявленных
в `prompts` файлов.

### Правила структуры документа

`required_sections` — список заголовков. Селектор задаётся строкой: `"## Purpose"` (уровень +
текст) или `"Purpose"` (любой уровень). Сопоставление идёт по **разобранному** тексту заголовка,
поэтому инлайн-разметка не мешает: `` ## Пробел относительно `todoc` `` совпадает с `## Пробел относительно todoc`.

`section_rules` — список правил вида
`{"heading": "### Requirement:", "min_children": 1, "child_level": 4, "severity": "error"}`.
Заголовок, оканчивающийся на `:`, считается префиксом: правило применяется к каждому
`### Requirement: <название>`. `child_level` по умолчанию — уровень заголовка + 1.

Проверяется в `validate` (коды `markdown.section.missing`, `markdown.section.empty`) и
**до записи** в `docs new`: шаблон, нарушающий структуру своего типа, отклоняется кодом
`types.template_invalid`, и файл не создаётся.

### Строгость `check-config`

Неизвестные поля больше не принимаются молча — конфигурация, которая «приняла» правило и
никогда его не применяет, хуже отказавшей. `check-config` возвращает exit 3 и диагностики:

| Код | Что значит |
|---|---|
| `config.unknown_field` | поле не входит в список допустимых для этого вида типа |
| `config.invalid_schema` | поле есть, но форма неверная (не список, не целое, не `error`/`warning`) |
| `config.template_missing` | объявлен `template`, файла нет |
| `config.prompt_missing` | объявлен промпт операции, файла нет |

## Правила маршрутизации

Форма правила:

```json
{"id": "glob-guides", "match": {"kind": "file", "glob": "guides/**"},
 "assign": {"doc_type": "guide"}, "priority": 100}
```

Виды `match`:

| `kind` | Ключ | Специфичность |
|---|---|---|
| `directory` | `basename` | 100 |
| `directory` | `glob` | число литеральных сегментов |
| `file` | `glob` | число литеральных сегментов |
| `file` | `front_matter` | 200 |

### Грамматика масок (v1)

- `*` и `?` не пересекают `/`;
- `**/` отдельным сегментом — ноль или более сегментов;
- ведущий `/` привязывает к корню;
- совпадение считается по полной относительной POSIX-пути.

### Приоритеты резолва

Победитель — максимум по паре `(priority, специфичность)`. Если на первом месте несколько правил
с **разными** результатами, тип не присваивается: возвращается `ambiguous` и предупреждение
`config.ambiguous_rule` со списком ID правил. Молчание правил → зарезервированное имя →
`unknown`/`default`.

Зарезервированные имена папок: `.research`, `architecture`, `constitution`, `harness`, `glossary`,
`plan`. Алиас `harnes` → `harness` применяется только через явную конфигурацию.

### Правила по умолчанию

| ID | Совпадение | Присваивает | Приоритет |
|---|---|---|---|
| `reserved-research` | basename `.research` | dir_type `research` | 100 |
| `reserved-plan` | glob `**/plan` | dir_type `plan` | 100 |
| `reserved-architecture` | basename `architecture` | dir_type `architecture` | 100 |
| `reserved-constitution` | basename `constitution` | dir_type `constitution` | 100 |
| `reserved-harness` | basename `harness` | dir_type `harness` | 100 |
| `reserved-glossary` | basename `glossary` | dir_type `glossary` | 100 |
| `adr-markdown` | glob `**/adr/*.md` | doc_type `adr` | 50 |
| `glossary-by-front-matter` | front matter `doc_type: glossary-entry` | doc_type `glossary-entry` | 200 |

Практический вывод: **явное объявление в front matter (200) перебивает маску папки (100)**.
Это видно в `explain-path` через `rule_source: rule:fm-<type>`.

## Схемы записей

`.todoc/schemas/records/<entity_type>.json` — JSON Schema (Draft 2020-12). Применяются к каждой
записи соответствующего типа; нарушения дают `record.schema_violation` с JSON Pointer в
`location.pointer`. Некорректный файл схемы игнорируется (не роняет валидацию).

## Связанные разделы

- [05-formats.md](05-formats.md) — front matter и форматы.
- [08-records-and-relations.md](08-records-and-relations.md) — записи и отношения.
- [13-demo-dataset.md](13-demo-dataset.md) — рабочий пример конфигурации.
