---
id: doc:home
title: "HOME: карта содержимого демо-датасета"
doc_type: moc
lang: ru
---

# HOME: карта содержимого

Демо-датасет `todoc`: та же документация проекта, разложенная по типам папок и документов,
с записями, отношениями и схемами. Всё проверяется самим `todoc`.

## Нормативный слой

- [Конституция](plan/constitution.md) — что строить.
- [План реализации](plan/implementation-plan.md) — как строить.
- [Конкурентный анализ](plan/competitive-analysis.md) — ландшафт и C01–C60.
- [Аудит реализации](plan/audit-implementation.md) — что найдено в коде MVP.

### Активные планы (не начаты, 25.11.2026)

- [Документирование софта: типовой профиль — типы, стартовые промпты, скилы](plan/документирование-софта--типовой-профиль---типы--стартовые-промпты--скилы.md) — Фаза 1 идеи documentation-system: 4 doc_types, 6 entity_types, 4 dir_types, 4 relation_types, CRUD-промпты, 5 скилов и приёмочный флоу-документ.
- [Агентский стейт: state.json в движке](plan/агентский-стейт--state-json-в-движке--v1---текущий-проект.md) — `todoc state set/get/list/unset`, файл вне данных.
- [Скилы взаимодействия: захват, план, исполнение, переходы](plan/скилы-взаимодействия--захват--план--исполнение--переходы--жизненный-цикл.md) — статусы в документах/записях, 4 скила, relation `implements`.
- [Теги документов как aliases поиска](plan/теги-документов-как-aliases-поиска--tags-updated-related-в-front-matter.md) — created/updated/tags/related во front matter, веса поиска.
- [Хранилище-движок скилов: skills tree, валидация, мьют, импорт](plan/skills-vault-implementation.md) — vault по стандарту Agent Skills, `todoc skills tree`, коды `skills.*`, мьют `!`, офлайн-импорт; закрывает открытые вопросы идеи [skills-engine](ideas/skills-engine.md).

### Баг-репорты (`bugs/`, doc_type `bug-report`)

Дефекты и недочёты, найденные при эксплуатации системы, **включая фрикцию
агента**: всё, что потребовало повторных вызовов, обходных путей или перерасхода
токенов против прямого взаимодействия с файлами без CLI. Один файл = один баг;
`status`, `severity` и `agent_impact` (`none|friction|token_overrun`) во front
matter; репорты не удаляются. Создание: `todoc docs new --type bug-report
--title "BUG-NNN: суть" --dir bugs` (промпт: `todoc types prompt bug-report
--op create`).

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

## Идеи (`ideas/`)

- [Система документирования кодовой базы через агента](ideas/documentation-system.md) — git-дифы и Jira API → типизированные черновики todoc, очередь сбора, версии правил через `supersedes`.
- [Хранилище-движок скилов на todoc](ideas/skills-engine.md) — скил как dir_type (формат Agent Skills), иерархия-дерево решений, `todoc skills tree` — оглавление с описаниями на лету, мьют через `!`-префикс.
- [`.config.json` — самоописание папок](ideas/folder-config.md) — заголовок, описание и порядок папки для CLI-вывода; описания разделов для дерева скилов.
- [Агентский стейт — state.json в движке](ideas/agent-state.md) — память рабочего состояния между сессиями вне данных; v1: только `context.current_project`.

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

- Записи: `records/documents/`, `records/decisions/`, `records/guides/`, `records/competitors/`, `records/metrics/`.
- CSV-инвентарь: [docs-inventory.csv](attachments/docs-inventory.csv).
- Заметки: [как читать демо](notes/how-to-read-this-demo.md), [token economy](notes/token-economy.md), [контракт CLI](notes/agent-contract.md).
