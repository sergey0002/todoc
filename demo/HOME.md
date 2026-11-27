---
id: doc:home
title: "HOME: карта содержимого демо-датасета"
doc_type: moc
lang: ru
created: 2026-11-26
updated: 2026-11-27
tags: [moc, содержимого, датасета]
---

# HOME: карта содержимого

Демо-датасет `todoc`: та же документация проекта, разложенная по типам папок и документов,
с записями, отношениями и схемами. Всё проверяется самим `todoc`.
У каждого документа во front matter есть `created`/`updated`/`tags` (папка + тип + тематические),
а `docs search --tag <тег>` фильтрует выдачу по тегу.

## Нормативный слой

- [Конституция](plan/constitution.md) — что строить.
- [План реализации](plan/implementation-plan.md) — как строить.
- [Конкурентный анализ](plan/competitive-analysis.md) — ландшафт и C01–C60.
- [Аудит реализации](plan/audit-implementation.md) — что найдено в коде MVP.

### Планы (статусы от 26.11.2026)

- [Документирование софта: типовой профиль](plan/документирование-софта--типовой-профиль---типы--стартовые-промпты--скилы.md) — **исполнена волна 1** (задачи 1–7: dir_types flows/reports/specs/changes, entity flow/rule/incident/release/task-snapshot/change, doc_types flow-doc/spec-doc/task-report/release-note + промпты, relation belongs_to/affects/fixes/blocked_by, пилот «оформление заказа», 5 скилов документирования) **и волна 2** (задачи 8–10: api-endpoint/domain-event/bounded-context/slo/dependency + depends_on, api-contract/runbook/postmortem + contracts/ops, событийный срез пилота). Он же gate задач 6/8 [entity-catalog](plan/entity-catalog-implementation.md) — gate закрыт (З6/З8 исполнены). fm **done** (закрыт по явной фразе пользователя, 2026-11-26).
- [Конфиг папок](plan/folder-config-implementation.md) — **исполнен** (38/38): `folder.*`, `folder_meta`, `docs suggest`, буст search. fm **done** (закрыт по явной фразе пользователя, 2026-11-26).
- [Агентский стейт](plan/агентский-стейт--state-json-в-движке--v1---текущий-проект.md) — **исполнен** (20/20): `todoc state set/get/list/unset`, файл вне данных. fm **done** (закрыт по явной фразе пользователя, 2026-11-26).
- [Скилы взаимодействия](plan/скилы-взаимодействия--захват--план--исполнение--переходы--жизненный-цикл.md) — **исполнен** (35/35; **done**): `docs status`/`records status`, allowed_statuses + enum task, 4 скила жизненного цикла в `skills/process/`, relations `implements`/`subtask_of`, сквозной сценарий «идея → план → задачи» на реальном пункте backlog (интероп-экспорты).
- [Entity-catalog: справочник сущностей](plan/entity-catalog-implementation.md) — **исполнен полностью** (43/43; **done**): фрагменты ссылок, mention-индекс, relations tree, undo-relation, тип `term` + 10 терминов, source_anchor, tree пилотного флоу + uses_term, flow render/walk, DoD закрыт.
- [Теги документов как aliases поиска](plan/теги-документов-как-aliases-поиска--tags-updated-related-в-front-matter.md) — created/updated/tags/related во front matter, веса поиска.
- [Хранилище-движок скилов: skills tree, валидация, мьют, импорт, диспетчер](plan/skills-vault-implementation.md) — vault по стандарту Agent Skills (11 демо-скилов), `todoc skills tree/read`, коды `skills.*`, мьют `!`, офлайн-импорт + диспетчер-скил `todoc` (`skills attach`) — одна точка входа для любого агента; закрывает открытые вопросы идеи [skills-engine](ideas/skills-engine.md). **Исполнен 25.11.2026** (7 задач; проба пакета obra/superpowers: 15/15 одной командой). fm **done** (закрыт по явной фразе пользователя, 2026-11-26).
- [Интероп-экспорты: DMN, ASL, Rasa](plan/interop-exports-dmn-asl-rasa.md) — **исполнен** (Задачи 1–2, DoD 3/3; **done**): конвертеры `interop export` реализованы, витрины демо экспортированы в `exports/` (ASL-машина флоу, 3 DMN-таблицы, Rasa-глоссарий на 10 интентов); 2 задачи-записи open (пересмотр форматов, CLI-конвертеры из других витрин).
- [Пакет скилов волнового планирования без переделок (`BMAD v6/v7` + `GSD` + `Spec Kit` + `OpenSpec`) и CLI-механика волн](plan/bmad-wave-planning-skills.md) — **активен** (`status: active`, 9 задач): `doc_type: roadmap`, CLI-команды `todoc stale anchor/reanchor`, `todoc plan portfolio/bind`, секционный `docs edit` и 6 скилов `process/bmad/*` со связкой из `todoc-plan`.
- [Самодокументируемый CLI: единые виды вывода и фильтры — план реализации](plan/unified-cli-output-implementation.md) — целевой контракт `--view flat|tree|graph`, read-only чистота выборок и модульный CLI.
- [Прямое редактирование файлов, команда финализации `todoc sync` и отказ от обязательного `docs edit` в правилах и промптах](plan/direct-edit-and-sync.md) — **активен** (`status: active`, 5 задач, прошёл предреализационный аудит): ядро `sync_files` и команда `todoc sync`, защита автособираемых витрин (`"generated": true` + `guidance` `P15`), скрытие `.todoc/history/` из Git (`BUG-012`) и перевод всех правил, скилов и 56 типов на прямую правку.

### Хранилище скилов (`skills/`)

30 скилов / 3 раздела (coding, docs, process) / 1 мьют (`!legacy-deploy`) —
открытый стандарт Agent Skills: 15 каноничных демо-скилов (в т.ч. жизненный цикл
`todoc-capture` / `todoc-plan` / `todoc-execute` / `todoc-transitions`) + 15 из пакета
[obra/superpowers](https://github.com/obra/superpowers) в
`process/superpowers/` (импорт 25.11.2026 одной командой `todoc skills
import`, оставлен на постоянку). Разделы описаны файлами `.config.json`
(`Процессы` → `Документы и KB` → `Скилы кодинга` — порядок `order`), заголовки
видны в дереве. Оглавление: `todoc skills tree --root demo`;
тело: `todoc skills read --root demo --path <из дерева>`; диспетчер для
платформ: `todoc skills attach`; импорт чужих: копия папки + validate или
`todoc skills import`. Канон: [agent-contract → «Скилы»](notes/agent-contract.md).

### Баг-репорты (`bugs/`, doc_type `bug-report`)

Дефекты и недочёты, найденные при эксплуатации системы, **включая фрикцию
агента**: всё, что потребовало повторных вызовов, обходных путей или перерасхода
токенов против прямого взаимодействия с файлами без CLI. Один файл = один баг;
`status`, `severity` и `agent_impact` (`none|friction|token_overrun`) во front
matter; репорты не удаляются. **Перед созданием — поиск дубликата** (`--type
bug-report` по симптому и компоненту); нашли — сослайтесь на `BUG-NNN`, не
плодите дубль (канон: `notes/agent-contract.md` → «Баг-репорты», промпт:
`todoc types prompt bug-report --op create`). Создание: `todoc docs new --type
bug-report --title "BUG-NNN: суть" --dir bugs`.

Конвенция именования (2026-11-25): русский заголовок — в поле `title`
(метаданные md/json), имя файла — на английском; канон —
[Контракт CLI → «Именование документов»](notes/agent-contract.md).

Фильтрация: `todoc records query --root demo --query-file demo/.todoc/queries/bugs-agent-friction.json`
(фрикция) · `…/bugs-token-overrun.json` (перерасход токенов) ·
`docs search --type bug-report --query "agent_impact friction"` (ранжирующе).

- [BUG-001: Явный doc_type без fm-правила резолвится в unknown](bugs/bug-001--явный-doc_type-без-fm-правила-резолвится-в-unknown.md) — `major`, triaged, friction
- [BUG-002: change open создаёт файлы с doc_type note без правила](bugs/bug-002--change-open-создаёт-файлы-с-doc_type-note-без-правила---резолвится-в-unknown.md) — `major`, triaged, friction
- [BUG-003: Счётчики демо в README разошлись с фактом](bugs/bug-003--счётчики-демо-в-readme-разошлись-с-фактом.md) — `major`, triaged, friction
- [BUG-004: docs edit не умеет вставку и удаление строк](bugs/bug-004--docs-edit-не-умеет-вставку-и-удаление-строк.md) — `major`, open, friction + token_overrun
- [BUG-005: docs read --section игнорирует --budget](bugs/bug-005--docs-read---section-игнорирует---budget.md) — `minor`, open, friction + token_overrun
- [BUG-006: docs new создаёт кириллические имена файлов](bugs/bug-006--docs-new-создаёт-кириллические-имена-файлов-из-кириллического-заголовка.md) — `minor`, open, friction + token_overrun

## Пост-MVP направления (`plan/after/`)

- [MCP-адаптер](plan/after/mcp-adapter.after.md)
- [Память LLM и wiki-профиль](plan/after/memory-llm-wiki.after.md)
- [Поиск, эмбеддинги, векторы](plan/after/search-embeddings-vector.after.md)
- [Плагины форматов и импорт](plan/after/plugins-formats-import.after.md)
- [Синхронизация и экспорт](plan/after/sync-collab-export.after.md)
- [Веб-интерфейс](plan/after/web-ui.after.md)

## Исследования и срезы (`.research/`)

- [Инженерный набросок](.research/engineering-plan.md)
- [Исследование MCP и CLI](.research/mcp-cli-agents-research.md)
- [Сравнительный аудит Agent Skills](.research/comparative-audit.md)
- [Лучшие паки скилов и скриптов для мозговых штурмов и ресёрча](.research/agent-brainstorming-and-research-packs.md)
- [Python-библиотеки BM25/BM25F и двуязычного стемминга (`RU+EN`) для ранжирования выборок](.research/bm25-ranking-python-libs.md)
- [Скилы волнового синтеза идей и защиты от переделок (`BMAD Method v6.12.4/v7`, `GSD`, `Evolutionary Seams`)](.research/bmad-v6-wave-planning-skills.md)

## Идеи (`ideas/`)

- [Система документирования кодовой базы через агента](ideas/documentation-system.md) — git-дифы и Jira API → типизированные черновики todoc, очередь сбора, версии правил через `supersedes`. **Реализована** (fm done, 2026-11-26).
- [Хранилище-движок скилов на todoc](ideas/skills-engine.md) — скил как dir_type (формат Agent Skills), иерархия-дерево решений, `todoc skills tree` — оглавление с описаниями на лету, мьют через `!`-префикс. **Запланирована** (25.11.2026) → [план](plan/skills-vault-implementation.md). **Реализована** (fm done, 2026-11-26).
- [`.config.json` — самоописание папок](ideas/folder-config.md) — заголовок, описание и порядок папки для CLI-вывода; описания разделов для дерева скилов. **Реализована** (fm done, 2026-11-26).
- [Агентский стейт — state.json в движке](ideas/agent-state.md) — память рабочего состояния между сессиями вне данных; v1: только `context.current_project`. **Реализована** (fm done, 2026-11-26).

- [Интероп-экспорты: DMN, ASL, Rasa](ideas/interop-exports.md) — конвертеры flow→ASL, rule→DMN 1.3, term→Rasa NLU без новых зависимостей. **Реализована** (fm done, 2026-11-26) — [план](plan/interop-exports-dmn-asl-rasa.md) исполнен (DoD 3/3), витрины в `exports/`.
- [`.todocignore` — исключение посторонних файлов и папок по синтаксису gitignore](ideas/todocignore.md) — пакет `pathspec` (`GitIgnoreSpec`) и каскадные `.todocignore` вместо жёстких списков в коде; сквозной учёт в сканере, валидаторе, поиске, скилах, `explain-path` и `linkcheck`. **Зафиксирована** (fm captured, 2026-11-26).
- [`todoc docs move` — транзакционный перенос документа с автоправкой ссылок и связей](ideas/docs-move.md) — перенос/переименование одной командой (`--preview`/`--apply`) с пересчётом всех входящих/исходящих ссылок, wikilinks, `relations`/`source_path` записей, `derived_from` и индекса. **Зафиксирована** (fm captured, 2026-11-26).
- [Раздельные часы `valid_at` и `known_at` для би-темпоральных выборок](ideas/bitemporal-clocks.md) — учёт `observed_at`, разделение времени истинности (`--valid-at`) и времени знания (`--known-at`), скрытие закрытых `superseded_at` по умолчанию (`--include-superseded`). **Зафиксирована** (fm captured, 2026-11-26).
- [`todoc folderize` — преобразование любой сущности в папку-домен с `.config.json`](ideas/entity-to-folder.md) — разворачивание документа или записи в одноимённую папку на том же месте, автогенерация `.config.json`, перенос сущности в корень с автоправкой ссылок и вложенный поиск `--within` по идее/плану/задачам. **Зафиксирована** (fm captured, 2026-11-26).
- [Настраиваемое логирование действий и вызовов CLI (`error` / `warning` / `notice` / `all`)](ideas/action-logging.md) — структурированный JSONL-лог вне данных (`~/.local/state/todoc/logs/`) с ротацией, метриками всех вызовов для отладки и группой `todoc trace`. **Зафиксирована** (fm captured, 2026-11-26).
- [Стандарт именования типов (`1–2` слова `snake_case`) и тип папки `state` (`AS-IS`)](ideas/type-naming-and-state-dir.md) — жёсткий формат `^[a-z][a-z0-9]*(?:_[a-z0-9]+)?$` для всех `dir_type`/`entity_type`/`doc_type` и триада `idea → plan → state` для реальной картины мира. **Зафиксирована** (fm captured, 2026-11-26).
- [Сквозная система тегов (`todoc tags`, граф `has_tag` и фильтр `--tag-in`)](ideas/unified-tags-and-tag-graph.md) — единые теги для документов, записей и папок, двухшаговая разметка (`tags list` → `tags set`, порог `200` тегов), рёбра связей по тегам и выборки `--tag-in "x|y|z"` во всех командах. **Зафиксирована** (fm captured, 2026-11-26).
- [`todoc tree` — типизированная проекция дерева в CLI со схлопыванием промежуточных папок](ideas/typed-tree-projection.md) — выборка в директории по `--dir-type`, `--doc-type`, `--entity-type`, `--format` через `|` со сжатием папок других типов и сохранением иерархии (`--within` / `--lineage-for`). **Зафиксирована** (fm captured, 2026-11-26).
- [Переключаемые драйверы хранения кэша поиска и истории (`SQLite + FTS5 BM25` vs `JSON`/`JSONL`)](ideas/sqlite-storage-drivers.md) — раздельные БД `index.sqlite` (инкрементальный кэш `O(Δ)`, `FTS5 bm25()` + стемминг `RU+EN`, ранжирование выборок `-q ... --sort relevance --limit 100`) и `history.sqlite` с независимым переключением контуров. **Зафиксирована** (fm captured, 2026-11-26).
- [Отключаемые правила харнеса (`doc_type: rules`, `enable`/`disable` и фильтр `--include-disabled`)](ideas/toggleable-rules.md) — замыкание триады `skills + flows + rules`: тип файла и папки `rules` с переключателем `enabled: true|false` и скрытием отключённых правил/флоу/скилов во всех CLI-выборках без спецфлага. **Зафиксирована** (fm captured, 2026-11-26).
- [Мульти-проектное рабочее пространство (`projects/*`, системный проект `core` и параллельный скоуп CLI через `state.json`)](ideas/multi-project-workspace.md) — единая структура `projects/<slug>/` с всегда доступным на чтение ядром `projects/core/`, параллельной работой над связкой проектов (`context.projects = "core|billing|auth"`), каскадным харнесом и разбором 12 архитектурных подводных камней. **Зафиксирована** (fm captured, 2026-11-26).
- [CLI-команды волнового планирования (`todoc stale anchor/reanchor`, `todoc plan portfolio` и пакетный `todoc plan bind`)](ideas/wave-planning-cli-helpers.md) — детерминированная механика якорей свежести, рентгена сирот/дублей/файловых коллизий волн, секционных правок `docs edit` и сверки `git diff → state/`. **В плане** (fm planned, покрыта [bmad-wave-planning-skills](plan/bmad-wave-planning-skills.md), 2026-11-27).
- [Самодокументируемое поле `guidance` для моделей во всех выводах CLI и переключаемый `i18n`-каталог подсказок](ideas/cli-model-guidance-and-hint-catalog.md) — принцип Конституции `P15`: коды ситуаций в коде, рекомендации со ссылками на скилы/доки в переключаемом каталоге (`JSON` + `CSV`), минимальный шум на успехе и подробная опора при ошибках. **В плане** (fm planned, покрыта [bmad-wave-planning-skills](plan/bmad-wave-planning-skills.md), 2026-11-27).
- [Самодокументируемый CLI: единые виды вывода и фильтры](ideas/unified-cli-output.md) — единые виды `flat/tree/graph`, предсказуемые умолчания и подсказки в ответе CLI.
- [Прямое редактирование файлов без дорогого `docs edit`, короткая команда финализации `todoc sync <path>` и замена правил/промптов](ideas/direct-edit-and-git-sync.md) — отказ от принудительного построчного `docs edit --patch-file` во всех правилах/скилах/`prompts/edit.md` (`56` типов) в пользу прямой правки и одной короткой команды `todoc sync <path>` (`updated:`, `history`, `parse_cache`, защита витрин + `guidance` `P15`, исключение `.todoc/history/` из Git). **В плане** (fm planned, покрыта [direct-edit-and-sync](plan/direct-edit-and-sync.md), 2026-11-27).
- [Агентные флоу (`agent_flow`) — исполняемые деревья решений для агента поверх `flow`, квиз из рёбер и скил `flow-runner`](ideas/agent-flows.md) — специализированный исполняемый наследник `flow` (в любой папке по `P4`, с `enabled: bool` и `todoc flows clone`), пошаговый навигатор `todoc flows step` (`~100` токенов/шаг), стандартный квиз `ask-user` прямо из рёбер `edges` и универсальный скил `flow-runner` для любых доменов (ТРИЗ, Карпаты, ресёрч, штурм, разработка). **Зафиксирована** (fm captured, 2026-11-27).
- [Сквозной флоу разработки на базе `agent_flow` и папок-доменов `folderize` (от идеи до петли аудита полноты)](ideas/dev-lifecycle-flow.md) — модульный граф `agent_flow:dev-lifecycle` с превращением идеи и плана в изолированные папки-домены (`todoc folderize` + `--within`), двойным аудитом свежести против мира, четырёхтактным циклом задачи (`task-exec`) и обязательной обратной петлёй аудита полноты перед `done`. **Зафиксирована** (fm captured, 2026-11-27).

## Гайды

- [CLI для агентов](guides/cli-for-agents.md)
- [Markdown knowledge base для агентов](guides/markdown-knowledge-base.md)
- [MCP для агентов](guides/mcp-for-agents.md)
- [SKILL.md](skill/SKILL.md)

## Справка (`references/`)

- [Workflow](references/workflow.md)
- [Data roots и конфиг](references/data-roots-and-config.md)
- [Типы и валидация](references/types-and-validation.md)
- [Форматы CSV/JSON/Markdown](references/formats-csv-json-markdown.md)
- [Сущности, отношения и запросы](references/entities-relations-and-queries.md)
- [Безопасное чтение/запись](references/safe-read-write.md)
- [Типовая система (сгенерировано)](references/type-system.generated.md)
- [Ingest/query/write/lint](references/ingest-query-lint.md)
- [Шаблоны страниц](references/page-templates.md)

## Состояние системы (`docs/state/` → `references/state/`)

- [Оглавление](references/state/README.md)
- [Обзор и статус MVP](references/state/01-overview.md)
- [Архитектура](references/state/02-architecture.md)
- [Справочник CLI](references/state/03-cli-reference.md)
- [Конфигурация и типы](references/state/04-config-and-types.md)
- [Форматы](references/state/05-formats.md)
- [Валидация и диагностики](references/state/06-validation-and-diagnostics.md)
- [Поиск и чтение](references/state/07-search-and-read.md)
- [Записи и отношения](references/state/08-records-and-relations.md)
- [Индекс и кэш](references/state/09-storage-and-index.md)
- [Тесты и качество](references/state/10-testing-and-quality.md)
- [Известные проблемы](references/state/11-known-issues.md)
- [Работа агента](references/state/12-agent-operations.md)
- [Демо-датасет](references/state/13-demo-dataset.md)
- [Глоссарий](references/state/14-glossary.md)

## Архитектура

- [Слои и адаптеры](architecture/system-architecture.md)
- [Модель данных](architecture/data-model.md)

## Карточки конкурентов

Полный список — в папке `competitors/`; примеры: [QMD](competitors/qmd.md),
[Basic Memory](competitors/basic-memory.md), [OKF](competitors/okf.md),
[OpenKB](competitors/openkb.md), [mdkb](competitors/mdkb.md).

## Глоссарий

[DATA_ROOT](glossary/data-root.md) · [doc_type](glossary/doc-type.md) · [dir_type](glossary/dir-type.md) ·
[entity_type](glossary/entity-type.md) · [relation_type](glossary/relation-type.md) ·
[Диагностика](glossary/diagnostic.md) · [Конверт ответа](glossary/envelope.md) ·
[Поколение индекса](glossary/generation.md) · [WritePlan](glossary/write-plan.md) ·
[Зарезервированное имя](glossary/reserved-basename.md)

## Записи и данные

- Записи: `records/documents/`, `records/decisions/`, `records/guides/`, `records/competitors/`, `records/metrics/`, `records/terms/`.
- **Справочник сущностей** — 10 терминов глоссария (`term:<slug>`, витрины `glossary/*.md`,
  определение и алиасы в записи): [term:envelope](records/terms/envelope.json),
  [term:dir-type](records/terms/dir-type.json), [term:doc-type](records/terms/doc-type.json),
  [term:entity-type](records/terms/entity-type.json), [term:relation-type](records/terms/relation-type.json),
  [term:data-root](records/terms/data-root.json), [term:diagnostic](records/terms/diagnostic.json),
  [term:generation](records/terms/generation.json), [term:reserved-basename](records/terms/reserved-basename.json),
  [term:write-plan](records/terms/write-plan.json). `records read --id term:<slug>` —
  запись с `mentioned_in`; `relations tree --from term:<slug>` — витрина и `part_of`.
- CSV-инвентарь: [docs-inventory.csv](attachments/docs-inventory.csv).
- Заметки: [как читать демо](notes/how-to-read-this-demo.md), [token economy](notes/token-economy.md), [контракт CLI](notes/agent-contract.md).
