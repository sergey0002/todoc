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
