# 13. Демо-датасет `demo/`

`demo/` — полноценный DATA_ROOT, созданный командой `todoc init` и расширенный вручную:
типы, правила, шаблоны, JSON Schema, сохранённые запросы, записи и отношения. Вся документация
проекта лежит в нём **копиями** с добавленным front matter и поправленными относительными ссылками.

## Числа (проверено `todoc validate --root demo --all` и `index rebuild`)

| Показатель | Значение |
|---|---|
| Документов | 248 |
| Записей | 157 |
| Отношений | 138 |
| Папок | 20 |
| Диагностик | 0 |
| `dir_types` / `doc_types` / `entity_types` / `relation_types` | 14 / 19 / 12 / 9 |
| Стартовых шаблонов типов | 31 (19 doc + 12 entity) |
| CRUD-промптов типов | 124 (31 × 4) |

Состав документов: 90 Markdown + 1 CSV + 157 JSON-записей.
Состав записей: `document` 90, `competitor` 30, `metric` 24, `decision` 10, `guide` 3.

У 11 из 19 doc-типов объявлены `required_sections` — они выведены из самого корпуса (заголовки
уровня 2, общие для всех документов типа), поэтому валидация датасета остаётся чистой.

## Структура

| Папка | `dir_type` | Содержимое |
|---|---|---|
| `.todoc/` | — | конфигурация: датасет, правила, 4 каталога типов, шаблоны, схемы, запросы |
| `plan/` | `plan` (reserved) | конституция, план реализации, конкурентный анализ, аудит, `after/` (6 планов) |
| `.research/` | `research` (reserved) | инженерный набросок, исследование MCP/CLI, аудит Agent Skills |
| `architecture/` | `architecture` (reserved) | слои и поток данных, модель данных |
| `glossary/` | `glossary` (reserved) | 10 определений терминов |
| `guides/` | `guides` | 3 гайда (CLI, Markdown KB, MCP) |
| `references/` | `references` | 9 справок по подсистемам + `state/` (16 документов состояния) |
| `competitors/` | `competitors` | 30 карточек конкурентов и Agent Skills |
| `records/` | `records` | типизированные JSON-записи по подпапкам |
| `notes/` | `notes` | 3 заметки: навигация, token economy, контракт CLI |
| `inbox/` | `inbox` | очередь разборки входящих |
| `attachments/` | `attachments` | `docs-inventory.csv` — инвентарь из 91 строки |
| `skill/` | `skill` | копия `SKILL.md` |

Корневые файлы: `README.md` (`doc_type: demo-readme`) и `HOME.md` (`doc_type: moc`).

## Что демонстрирует датасет

1. **Приоритеты резолвера.** Front matter `doc_type` (приоритет 200) перебивает маску папки
   (приоритет 100): `explain-path guides/cli-for-agents.md` показывает `rule_source: rule:fm-guide`.
2. **Зарезервированные имена.** `.research`, `plan`, `architecture`, `glossary` получают `dir_type`
   без явных правил (`rule_source: rule:reserved-*` или `reserved`).
3. **JSON-записи как документы.** У записей `records/documents/*.json` есть поле `doc_type`,
   поэтому правило по front matter присваивает тип и им: `explain-path records/documents/constitution.json`
   → `rule:fm-constitution`.
4. **Схемы записей.** `.todoc/entity_types/<entity_type>/schema.json` применяются ко всем 157 записям;
   ни одна не нарушает схему (0 диагностик).
5. **Отношения.** `documents`, `references`, `analyzes`, `describes`, `supersedes`; все цели
   существуют, все `type_id` есть в реестре.
6. **Единицы измерения и агрегация.** `records/metrics/*.json` хранят `{"value": N, "unit": "count"}`:
   `records aggregate --type metric --metric value --group-by aspect` возвращает
   `{benchmark: 4.473, performance: 10706, tests: 3933, cli: 26, docs: 133, types: 209, code: 4032}`
   с `formula: sum(value)`, `group_units` (единицы различаются, поэтому общий `units` пуст),
   `incoming_ids` и `completeness: complete`.
7. **Ссылки и код.** В `notes/how-to-read-this-demo.md` намеренно есть fenced-блок и инлайновый код
   с «битыми» ссылками — валидатор их игнорирует, а обычная ссылка и wikilink `[[data-root]]` проверяются.
8. **CSV-проекция.** `docs read --columns doc_id,doc_type,lines --rows 75 --where doc_type=guide`
   возвращает три строки гайдов.

## Проверенные команды

```bash
todoc validate --root demo --all                        # 0 диагностик
todoc check --root demo                                 # errors 0, warnings 0, status ok
todoc types list --root demo                            # 14/19/12/9
todoc index rebuild --root demo                         # 20 папок, 248 документов, 157 записей, 138 отношений
todoc docs tree --root demo --max-depth 1               # 20 папок, у 14 назначен dir_type
todoc docs search --root demo --query "портабельность" --limit 3   # total 42
todoc docs read --root demo --id doc:constitution --section "..."
todoc records list --root demo --type decision --limit 3           # total 10
todoc records query --root demo --query-file demo/.todoc/queries/competitors-portable.json   # total 21
todoc records read --root demo --id document:constitution --view summary
todoc relations graph --root demo --from decision:no-lsp --depth 2
todoc doctor --root demo                                # config/index/python: 3 pass
```

Запись проверялась на копии (`records create --preview/--apply`, `docs edit --preview/--apply`),
чтобы не менять зафиксированный датасет.

## Связь с репозиторием

| Источник | Куда скопировано |
|---|---|
| `docs/plan/*.md` | `demo/plan/` (4 документа) |
| `docs/plan/*.after.md` | `demo/plan/after/` (6 документов) |
| `docs/plan/engineering-draft.md`, `docs/research/mcp-cli-agents.md`, `docs/research/knowledge-base-comparative-audit.md` | `demo/.research/` |
| `docs/guides/*.md` | `demo/guides/` |
| `references/*.md` | `demo/references/` |
| `SKILL.md` | `demo/skill/SKILL.md` |
| `docs/research/skills-audit/` (8 снимков) | карточки в `demo/competitors/` |
| `docs/state/*.md` | `demo/references/state/` |

Копии содержат front matter (`id`, `title`, `doc_type`, `lang`, `source`, `copied`) и исправленные
относительные ссылки; текст документов не изменён.

## Как пересобрать

Датасет статичен и зафиксирован в репозитории. Производные каталоги `.todoc/index/` и
`.todoc/cache/` в Git не попадают: достаточно `todoc index rebuild --root demo`.

## Связанные разделы

- [04-config-and-types.md](04-config-and-types.md) — как устроены правила и типы.
- [08-records-and-relations.md](08-records-and-relations.md) — записи и отношения.
