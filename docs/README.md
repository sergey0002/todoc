# Документация `todoc`

Документация разделена по назначению: **что строить** (норматив), **что построено**
(фактическое состояние), **как пользоваться** (гайды и установка) и **что изучали**
(исследования).

Дата снимка состояния: 2026-11-25.

## С чего начать

| Вы хотите… | Читайте |
|---|---|
| Установить и запустить | [installation.md](installation.md) |
| Понять, что это за продукт | [state/01-overview.md](state/01-overview.md) |
| Команду и её флаги | [state/03-cli-reference.md](state/03-cli-reference.md) |
| Работать с DATA_ROOT из агента | [state/12-agent-operations.md](state/12-agent-operations.md) |
| Узнать, что сломано | [state/11-known-issues.md](state/11-known-issues.md) |
| Посмотреть живой пример | [`demo/`](../demo/README.md) |

## Разделы документации

### Установка и быстрый старт

| Файл | О чём |
|---|---|
| [installation.md](installation.md) | Требования, установка из исходников, проверка, первый датасет, устранение неполадок |
| [`../README.md`](../README.md) | Быстрый старт, все 26 команд, контракт вывода, коды выхода |
| [`../SKILL.md`](../SKILL.md) | Точка входа Agent Skill: короткий сценарий работы агента |

### `state/` — фактическое состояние системы

Описывает то, что **реально работает сейчас**; каждый факт получен прогоном кода или CLI.
Индекс разделов — [`state/README.md`](state/README.md).

| Файл | Аспект |
|---|---|
| [01-overview.md](state/01-overview.md) | Продукт, границы, статус MVP |
| [02-architecture.md](state/02-architecture.md) | Слои, модули, поток данных |
| [03-cli-reference.md](state/03-cli-reference.md) | Все 26 команд: флаги, вход, выход, коды выхода |
| [04-config-and-types.md](state/04-config-and-types.md) | `dataset.json`, правила, типы, резолвер |
| [05-formats.md](state/05-formats.md) | Адаптеры Markdown/JSON/CSV |
| [06-validation-and-diagnostics.md](state/06-validation-and-diagnostics.md) | Каталог диагностик, фиксы |
| [07-search-and-read.md](state/07-search-and-read.md) | Поиск, ранжирование, бюджетное чтение |
| [08-records-and-relations.md](state/08-records-and-relations.md) | Записи, отношения, запросы, агрегация |
| [09-storage-and-index.md](state/09-storage-and-index.md) | Поколения индекса, кэш парсинга, атомарность |
| [10-testing-and-quality.md](state/10-testing-and-quality.md) | Тесты, покрытие, как запускать |
| [11-known-issues.md](state/11-known-issues.md) | Подтверждённые дефекты с воспроизведением |
| [12-agent-operations.md](state/12-agent-operations.md) | Как агенту работать безопасно |
| [13-demo-dataset.md](state/13-demo-dataset.md) | Устройство демо-датасета |
| [14-glossary.md](state/14-glossary.md) | Термины |
| [15-benchmark.md](state/15-benchmark.md) | Бенчмарк качества, сравнение с конкурентами |
| [16-leftovers-report.md](state/16-leftovers-report.md) | Отчёт по остаткам: что открыто и в каком порядке |

### `plan/` — норматив и планы

| Файл | О чём |
|---|---|
| [constitution.md](plan/constitution.md) | Конституция: требования FR/NFR, что обязательно |
| [implementation-plan.md](plan/implementation-plan.md) | План реализации по этапам |
| [engineering-draft.md](plan/engineering-draft.md) | Инженерный набросок §1–§18 |
| [competitive-analysis.md](plan/competitive-analysis.md) | Сравнение с аналогами |
| [audit-implementation.md](plan/audit-implementation.md) | Аудит реализации: находки и их статус |

Пост-MVP направления — шесть планов `*.after.md`:
[MCP-адаптер](plan/mcp-adapter.after.md),
[память и LLM-wiki](plan/memory-llm-wiki.after.md),
[векторный поиск](plan/search-embeddings-vector.after.md),
[веб-интерфейс](plan/web-ui.after.md),
[форматы и импорт](plan/plugins-formats-import.after.md),
[синхронизация и экспорт](plan/sync-collab-export.after.md).

### `guides/` — гайды для агентов

| Файл | О чём |
|---|---|
| [cli-for-agents.md](guides/cli-for-agents.md) | Как агенту работать через CLI |
| [mcp-for-agents.md](guides/mcp-for-agents.md) | Требования к MCP-интеграции |
| [markdown-knowledge-for-agents.md](guides/markdown-knowledge-for-agents.md) | Работа с markdown-базой знаний |

### `research/` — исследования

| Файл | О чём |
|---|---|
| [knowledge-base-comparative-audit.md](research/knowledge-base-comparative-audit.md) | Сравнительный аудит баз знаний |
| [mcp-cli-agents.md](research/mcp-cli-agents.md) | MCP и CLI-агенты |
| [skills-audit/](research/skills-audit) | Материалы аудита навыков |

## Связанные каталоги вне `docs/`

| Где | Что |
|---|---|
| [`../demo/`](../demo/README.md) | Демо-датасет: живой DATA_ROOT со всей документацией проекта |
| [`../references/`](../references/) | Справка по подсистемам, входит в Skill |
| [`../bench/`](../bench/criteria.md) | Бенчмарк качества: 30 критериев, скрипт, результаты |
| [`../tools/`](../tools/) | Служебные скрипты: пересборка demo-копий, линкчекер |

## Правила ведения документации

1. Факт (число, код, поведение) добавляется только после проверки командой.
2. Числа, которые растут сами по себе (поколения индекса, размер кэша), не фиксируются —
   описывается механизм.
3. Новый дефект попадает в [state/11-known-issues.md](state/11-known-issues.md)
   с командой воспроизведения.
4. Изменение контракта CLI отражается в [state/03-cli-reference.md](state/03-cli-reference.md).
5. Копии разделов `state/` в демо-датасете пересобираются скриптом
   [`tools/refresh_demo_state.py`](../tools/refresh_demo_state.py), а не правятся вручную.
6. Ссылки проверяются скриптом [`tools/linkcheck.py`](../tools/linkcheck.py): он считает
   только те ссылки, которые реально обходит рендерер, — примеры внутри блоков кода,
   inline-кода и снимки сторонних репозиториев в `research/skills-audit/` не проверяются.
