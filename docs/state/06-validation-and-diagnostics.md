# 06. Валидация и каталог диагностик

## Форма диагностики

```json
{
  "dataset_id": "dataset-80c70868",
  "id": "diag_00854",
  "code": "markdown.link.target_missing",
  "severity": "error",
  "path": "notes/broken.md",
  "location": {"line": 3, "column": 1, "end_column": 17, "is_wikilink": false},
  "evidence": "[typo](runbok.md)",
  "message": "Локальная цель ссылки не найдена.",
  "suggested_fixes": [
    {"kind": "replace_link_target", "replacement": "ops/runbook.md",
     "basis": "Найден ближайший кандидат по имени файла.",
     "autofixable": true, "requires_review": true}
  ]
}
```

**`id` стабилен только внутри одного запуска** (см. [11-known-issues.md](11-known-issues.md)).
Для `fix` берите ID из того же вывода `validate`.

## Каталог кодов

Всего 66 кодов: 59 в литералах и 7 в f-строках адаптеров (проверено поиском по `src/todoc`).

### Конфигурация и типы

| Код | Когда |
|---|---|
| `config.missing_dataset` | нет `.todoc/dataset.json` |
| `config.unreadable` | файл конфигурации не читается |
| `config.invalid_json` | конфигурация не является JSON |
| `config.invalid_schema` | описатель типа malformed |
| `config.unsupported_version` | `schema_version != 1` |
| `config.duplicate_type` | два описателя с одним `type_id` |
| `config.unknown_type` | правило присваивает несуществующий тип |
| `config.already_initialized` | `init` в уже инициализированный корень |
| `config.ambiguous_rule` | ничья правил с разными результатами (warning) |
| `config.unknown_field` | поле описателя не входит в список допустимых для вида типа |
| `config.template_missing` | объявлен `template`, файла в папке типа нет |
| `config.prompt_missing` | объявлен CRUD-промпт, файла нет |
| `config.schema_missing` | объявлена `schema` у типа записи, файла в папке типа нет |
| `config.duplicate_asset` | на роль схемы претендуют два файла: объявленная `schema` и `schema.json` |
| `types.unknown` | `types show`/`docs new --type` для несуществующего типа |
| `types.template_missing` | `docs new` не нашёл шаблон (файл или объявленный шаблоном) |
| `types.template_invalid` | шаблон нарушает структуру своего типа — файл не создаётся |
| `types.prompt_missing` | `types prompt` для отсутствующего файла промпта |

### Файлы

| Код | Когда |
|---|---|
| `file.unreadable` | файл не читается как UTF-8 |
| `file.permission_denied` | нет прав на чтение |
| `file.unsupported` | размер больше `limits.max_file_bytes` |
| `markdown.unreadable` | Markdown не читается при проверке ссылок |

### Markdown

| Код | Когда |
|---|---|
| `markdown.link.target_missing` | локальная цель ссылки не найдена в датасете |
| `markdown.front_matter.yaml_unsafe` | front matter не разбирается строгим YAML-парсером (warning) |
| `markdown.section.missing` | нет раздела из `required_sections` типа документа |
| `markdown.section.empty` | у заголовка меньше подразделов, чем требует `section_rules` |

Правила структуры применяются только к документам, у которых resolved `doc_type` объявил
`required_sections`/`section_rules` (см. [04-config-and-types.md](04-config-and-types.md)).
Локация `markdown.section.missing` — начало документа (`line: 1`): указывать не на что,
раздела нет. Локация `markdown.section.empty` — строка самого заголовка.

Локация содержит `line`, `column`, `end_column`, `is_wikilink`.Wikilinks резолвятся по имени
файла в любом месте датасета; обычные ссылки — относительно файла-источника.

### JSON

| Код | Когда |
|---|---|
| `json.syntax_error` | синтаксическая ошибка |
| `json.duplicate_key` | повторяющийся ключ объекта |
| `json.invalid_constant` | `NaN`/`Infinity`/`-Infinity` |
| `json.too_deep` | глубина больше `limits.max_json_depth` |

### CSV

| Код | Когда |
|---|---|
| `csv.empty` | пустой файл |
| `csv.missing_header` | нет заголовков |
| `csv.duplicate_header` | дубль заголовка |
| `csv.wrong_width` | строка другой ширины |
| `csv.too_many_rows` | превышен лимит строк |
| `csv.parse_error` | ошибка разбора |

### Записи

| Код | Когда |
|---|---|
| `record.schema_violation` | нарушение JSON Schema (`location.pointer` — RFC 6901) |
| `record.duplicate_id` | `record_id` уже занят |
| `record.missing_entity_type` | нет `entity_type` |
| `record.missing_id` | нет `record_id` |
| `record.missing_field` | нет обязательного поля из описателя |
| `record.unknown_entity_type` | тип не в реестре |
| `record.target_exists` | целевой путь уже существует |
| `record.unsafe_path` | `path_template` выводит путь за корень |
| `record.invalid_json` / `record.invalid_input` / `record.unreadable_input` | проблемы входного файла |
| `records.not_found` | `records read` для несуществующего ID |

### Отношения

| Код | Когда |
|---|---|
| `relation.unknown_type` | `type_id` не в реестре типов отношений |
| `relation.dangling_target` | `target.id` не найден среди записей |
| `relation.missing_target` | у отношения нет `target.id` |
| `relation.malformed` | элемент `relations` не объект или поле не список |

### Документы, чтение, правки

| Код | Когда |
|---|---|
| `docs.not_found` | документ с таким `document_id` не найден |
| `docs.section_not_found` | раздел/якорь не найден |
| `docs.pointer_not_found` | JSON Pointer не разрешается |
| `docs.target_exists` | `docs new` в занятый путь |
| `edit.invalid_patch` | патч не JSON |
| `edit.file_missing` | файл пропал между индексацией и правкой |
| `edit.line_out_of_range` | номер строки вне файла |
| `explain.path_not_found` | `explain-path` для неизвестного пути |

### Запросы и агрегация

| Код | Когда |
|---|---|
| `query.invalid_file` | файл запроса не читается/не JSON |
| `query.no_records` | нет записей указанного типа |
| `query.unknown_metric` | поле метрики не числовое |
| `query.unit_mismatch` | смешение единиц в одной агрегации |

### Ремонт и запись

| Код | Когда |
|---|---|
| `fix.diagnostic_not_found` | неизвестный `--diagnostic` |
| `fix.no_fixes` | у диагностики нет предложенных фиксов |
| `fix.cannot_apply` | из диагностики не вывести старую/новую цель |
| `fix.file_missing` / `fix.target_not_found` | файл или цель пропали |
| `write.hash_mismatch` | `--if-hash` не совпал (exit 5) |
| `write.target_exists` / `write.target_missing` | конфликт цели (exit 5) |

### Общее

| Код | Когда |
|---|---|
| `operation.error` | базовая операционная ошибка (exit 1) |
| `validation.error` | базовая ошибка валидации (exit 3) |
| `access.denied` | отказ в доступе (exit 4) |
| `generation.incomplete` | поколение индекса не опубликовано целиком (exit 6) |
| `usage.missing_root` | не указан `--root` и `TODOC_ROOT` (exit 2) |
| `usage.error` | Click отклонил вызов: неизвестная команда или опция, неверный аргумент (exit 2) |

## Предложенные фиксы

Сейчас поддерживается один вид: `replace_link_target` — замена цели ссылки.

Правила выбора кандидата (проверено тестами):

1. единственное совпадение по имени файла → предлагается оно;
2. иначе нечёткое совпадение по **имени файла** с порогом 0.8; реальные опечатки дают 0.92+,
   посторонние имена — около 0.67, поэтому порог высокий;
3. кандидатов несколько или нет — фикс не предлагается (лучше ничего, чем неверная правка).

`fix --preview` показывает фикс, `fix --apply` применяет его атомарно и возвращает новый хеш.

## Связанные разделы

- [05-formats.md](05-formats.md) — откуда берутся ошибки форматов.
- [03-cli-reference.md](03-cli-reference.md) — `validate`, `fix`, `check`.
