# 01. Обзор: что такое `todoc` и в каком он состоянии

## Суть продукта

`todoc` — переносимый типизированный слой знаний поверх обычных файлов. Истина живёт в DATA_ROOT
(Markdown, CSV, JSON); индекс, кэш и граф — производные и пересобираемые. Продукт не является
клоном Obsidian, не является hosted-сервисом, не является general RAG и не является таск-менеджером.

Основной потребитель — **агент**: команды возвращают машиночитаемый конверт, ошибки типизированы,
чтение ограничено бюджетом, запись возможна только через предпросмотр.

## Статус на 2026-11-26

| Показатель | Значение | Как проверено |
|---|---|---|
| Версия пакета | `0.1.0` | `todoc --version` |
| Листовых команд CLI | 63 (28 верхнеуровневых) | обход дерева Click |
| Строк в `src/todoc` | 10 508 | `wc -l` по модулям |
| Тестов | 1280 проходят, 18 пропущено | `pytest tests` |
| Покрытие | 100% — 6291 инструкций, 2354 веток, 0 пропусков (гейт CI восстановлен 26.11) | `coverage run --branch` + `coverage report -m` |
| Зависимости | `click`, `jsonschema`, `markdown-it-py` | `pyproject.toml` |
| Python | 3.11.2 | `todoc doctor` |
| Демо-датасет | 442 документа, 205 записей, 0 диагностик | `todoc validate --root demo --all` |

## Что реализовано (проверено прогоном)

- **Инициализация и конфигурация**: `init`, `check-config`; `dataset.json`, правила, четыре каталога типов.
- **Сканирование**: детерминированный обход, hard-excludes, containment для symlink, лимит размера файла.
- **Валидация**: синтаксис Markdown/JSON/CSV, типы папок и документов, ссылки (включая wikilinks),
  записи по JSON Schema, отношения; точные локации `line`/`column`/`end_column`.
- **Поиск и чтение**: лексический поиск с фрагментами и ранжированием; чтение по разделу, строкам,
  JSON Pointer, колонкам CSV; ограничение по байтам.
- **Записи**: создание create-only через WritePlan, списки, декларативные запросы, агрегация с
  единицами и формулой, проекции `views`.
- **Отношения**: типизированный граф, BFS до заданной глубины, проверка целей и типов.
- **Индекс**: один снимок в `.todoc/index/current/`, инвалидация по дайджесту корпуса, кэш парсинга.
- **Ремонт**: `fix --preview/--apply` по одной диагностике, `doctor` с отдельным режимом ремонта.
- **История**: журнал событий записи `.todoc/history/`, снимки «до», `log`/`show`/`diff`/`blame`/
  `revert`/`tag`, лента по разделу, внешние правки в режиме `observed`, бэкенды `embedded`/`git`.
- **Устаревание**: `derived_from` с якорями (JSON Pointer и `section:`), `stale`, `stale --ack`.
- **Изменения**: `entity_type: change`, дельты `ADDED`/`MODIFIED`/`REMOVED`,
  `change open/show/validate/verify/apply/archive/revert`, атомарное применение «всё или ничего».
- **Контекст**: `context --change|--tag` — весь контекст задачи одним вызовом, в пределах бюджета байт.
- **Би-темпоральность**: `valid_from`/`valid_to` и `observed_at`/`superseded_at` у записей и
  отношений, `records query --as-of`, `timeline`; инвалидация вместо удаления.
- **Закрытые наборы статусов** (план [скилы-взаимодействия](../../demo/plan/скилы-взаимодействия--захват--план--исполнение--переходы--жизненный-цикл.md)):
  `allowed_statuses` у doc_type, `docs status`/`records status` с enum схемы, `docs.status_not_allowed`.
- **Отношения implements/subtask_of** (там же, З3): задачи → план, подзадачи → задача.
- **Хранилище скилов** (план [skills-vault](../../demo/plan/skills-vault-implementation.md)):
  `skills tree/read/attach/import`, формат Agent Skills, диспетчер-скил — [17-skills-and-vault.md](17-skills-and-vault.md).
- **Витрины флоу и u-graph** (план [entity-catalog](../../demo/plan/entity-catalog-implementation.md)):
  `docs flow render/walk`, `docs suggest/links`, `records undo-relation`.
- **Скоринг папок** (план [folder-config](../../demo/plan/folder-config-implementation.md)):
  `.config.json`, `docs tree --match`, `docs suggest`, плоские меты в `explain-path`.
- **Агентский стейт** (план [агентский-стейт v1](../../demo/plan/агентский-стейт--state-json-в-движке--v1---текущий-проект.md)):
  `state get/set/list/unset`, `.todoc/state.json` вне данных — [18-agent-state-and-context.md](18-agent-state-and-context.md).
- **Интероп-экспорты** (план [интероп-экспорты](../../demo/plan/interop-exports-dmn-asl-rasa.md)):
  `interop export` → DMN 1.3 / ASL / Rasa NLU, derived-артефакты — [19-interop-exports.md](19-interop-exports.md).

## Что сознательно НЕ реализовано в MVP

| Не реализовано | Где описано как будущее |
|---|---|
| MCP-сервер | [mcp-adapter.after.md](../plan/mcp-adapter.after.md) |
| Векторный/гибридный поиск, эмбеддинги | [search-embeddings-vector.after.md](../plan/search-embeddings-vector.after.md) |
| Профиль памяти LLM (Task/Plan/Idea, claim ledger) | [memory-llm-wiki.after.md](../plan/memory-llm-wiki.after.md) |
| Веб-интерфейс | [web-ui.after.md](../plan/web-ui.after.md) |
| Импорт PDF/DOCX/HTML, плагины форматов | [plugins-formats-import.after.md](../plan/plugins-formats-import.after.md) |
| Синхронизация, совместная работа, экспорт | [sync-collab-export.after.md](../plan/sync-collab-export.after.md) |
| LSP-сервер | решение зафиксировано: offline CLI-контракт важнее |

## Границы, которые важно не нарушать

1. Никаких фоновых процессов и демонов: каждая команда — отдельный процесс.
2. Никакого `eval`, SQL-конкатенации и shell-вызовов из текста модели.
3. Запись только через план и явное подтверждение; перезапись существующих записей запрещена.
4. Всё производное удаляемо: `.todoc/index/` и кэш можно стереть и пересобрать.

## Связанные разделы

- [02-architecture.md](02-architecture.md) — как устроен код.
- [03-cli-reference.md](03-cli-reference.md) — чем это управляется.
- [11-known-issues.md](11-known-issues.md) — что пока сломано.
