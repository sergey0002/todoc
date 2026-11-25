---
id: doc:state-glossary
title: "Состояние: глоссарий"
doc_type: reference
lang: ru
source: docs/state/14-glossary.md
copied: true
---
# 14. Глоссарий

| Термин | Определение | Где смотреть |
|---|---|---|
| **DATA_ROOT** | Корень переносимой папки данных: ordinary files + `.todoc/`. Всё производное пересобирается из него | [02](02-architecture.md) |
| **Skill** | Каталог навыка: `SKILL.md` + `references/` + `assets/`. Отделён от данных | [SKILL.md](../../skill/SKILL.md) |
| **`dataset_id`** | Идентификатор датасета из `dataset.json`; генерируется при `init` | [04](04-config-and-types.md) |
| **`dir_type`** | Тип папки; присваивается правилами или зарезервированным именем | [04](04-config-and-types.md) |
| **`doc_type`** | Тип документа; front matter важнее маски папки | [04](04-config-and-types.md) |
| **`entity_type`** | Тип JSON-записи с обязательными полями, шаблоном пути и проекциями | [08](08-records-and-relations.md) |
| **`relation_type`** | Тип направленного ребра между записями | [08](08-records-and-relations.md) |
| **Маска (glob v1)** | `*`/`?` не пересекают `/`, `**/` — ноль или более сегментов, ведущий `/` — якорь | [04](04-config-and-types.md) |
| **Специфичность** | Число литеральных сегментов маски; `basename` = 100, front matter = 200 | [04](04-config-and-types.md) |
| **`rule_source`** | Отметка о происхождении типа: `rule:<id>`, `reserved`, `default`, `ambiguous` | `explain-path` |
| **Конверт** | `{schema_version, ok, data, diagnostics, next_actions}` | [03](03-cli-reference.md) |
| **Диагностика** | `{code, severity, path, location, evidence, suggested_fixes}` | [06](06-validation-and-diagnostics.md) |
| **`location`** | `{line, column, end_column, is_wikilink}` или `{pointer}` для схем | [06](06-validation-and-diagnostics.md) |
| **`evidence`** | Фрагмент источника, например `[текст](цель)` | [06](06-validation-and-diagnostics.md) |
| **`suggested_fix`** | `{kind, replacement, basis, autofixable, requires_review}` | [06](06-validation-and-diagnostics.md) |
| **Поколение индекса** | Атомарно публикуемый снимок: folders/documents/records/relations/diagnostics | [09](09-storage-and-index.md) |
| **`CURRENT.json`** | Указатель на текущее поколение и `config_digest` | [09](09-storage-and-index.md) |
| **Кэш парсинга** | `.todoc/cache/parse/<key>.json`; ключ из хеша содержимого и версии парсера | [09](09-storage-and-index.md) |
| **WritePlan** | План записи: цель, содержимое, хеши, список проверок | [08](08-records-and-relations.md) |
| **`atomic_write`** | Временный файл → `fsync` → `os.replace` | [09](09-storage-and-index.md) |
| **`document_id`** | Адрес документа для `docs read --id`; из front matter `id:` либо `doc:<path>` | [07](07-search-and-read.md) |
| **`record_id`** | Идентификатор записи, например `decision:no-lsp` | [08](08-records-and-relations.md) |
| **Wikilink** | `[[Страница]]`; резолвится по имени файла в любом месте датасета | [05](05-formats.md) |
| **Front matter** | YAML-lite блок между `---`; `key: value`, булевы, инлайновые списки | [05](05-formats.md) |
| **Якорь (anchor)** | Slug заголовка с устранением дублей: `setup`, `setup-1` | [05](05-formats.md) |
| **JSON Pointer** | RFC 6901: `""` — документ, `"/a/0"` — элемент, `~0`/`~1` — экранирование | [05](05-formats.md) |
| **QuerySpec** | Декларативный запрос: `{entity_type, filters, limit}` | [08](08-records-and-relations.md) |
| **Бюджет** | Ограничение байт ответа (`--budget`); не отменяет пересборку индекса | [07](07-search-and-read.md) |
| **`relevance_method`** | Всегда `lexical` в MVP | [07](07-search-and-read.md) |
| **Hard-excludes** | `.todoc`, `.git`, `__pycache__`, `node_modules`, `.obsidian`, `.venv`, `venv` | [02](02-architecture.md) |
| **Containment** | Требование не выходить за пределы DATA_ROOT (пока нарушается, см. P0-2) | [11](11-known-issues.md) |
| **AFTER-план** | Пост-MVP план направления: `*.after.md` | [AFTER-планы](../../plan/after/mcp-adapter.after.md) |

## Сокращения

| Сокращение | Значение |
|---|---|
| MVP | минимальный жизнеспособный продукт (валидатор + записи + поиск + чтение) |
| MOC | Map of Content, страница-оглавление |
| ADR | запись архитектурного решения |
| RFC 6901 / 6902 | JSON Pointer / JSON Patch |
| P0/P1/P2 | приоритеты дефектов: критичный / важный / незначительный |
