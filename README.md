# todoc

Переносимый типизированный слой знаний поверх обычных файлов: source-native валидатор,
типизированные записи, ограниченный поиск и чтение. CLI-first и agent-first.

Файлы — источник истины. Индекс и кэш — производные и пересобираемые.

| Показатель | Значение |
|---|---|
| Команд CLI | 25 |
| Тестов | 300 (все проходят) |
| Покрытие | 100% — 2025 инструкций, 662 ветки |
| Зависимости | `click`, `jsonschema`, `markdown-it-py` |
| Демо-датасет | [`demo/`](demo/README.md): 205 документов, 130 записей, 0 диагностик |

## Установка

```bash
pip install -e .          # editable (разработка)
pip install .             # wheel
todoc --version           # todoc, version 0.1.0
```

## Быстрый старт

```bash
# 1. Создать датасет (создаёт только .todoc/, данные не трогает)
todoc init --root ./knowledge

# 2. Проверить конфигурацию и состояние
todoc check-config --root ./knowledge
todoc index rebuild --root ./knowledge
todoc status --root ./knowledge

# 3. Найти и прочитать
todoc docs search --root ./knowledge --query "refresh token" --limit 3
todoc docs read --root ./knowledge --id doc:notes/design.md --section "Decision"

# 4. Валидировать всё
todoc validate --root ./knowledge --all
```

Корень можно задать один раз через переменную окружения: `export TODOC_ROOT=./knowledge`.

## Все команды

### Датасет и проверка

| Команда | Назначение |
|---|---|
| `init --root PATH` | создать `.todoc/`: датасет, правила, типы, шаблоны |
| `check-config` | загрузить конфигурацию и реестр типов |
| `check [--strict]` | сводка: документы, ошибки, предупреждения |
| `scan` | обход датасета без публикации индекса |
| `validate [--all]` | полная валидация с точными локациями |
| `index status` / `index rebuild` | состояние и пересборка поколения индекса |
| `explain-path PATH` | почему путь получил свой тип (`rule_source`) |
| `doctor [--check IDS]` | диагностика окружения (только чтение) |
| `status` | снимок последнего поколения |

### Документы

| Команда | Назначение |
|---|---|
| `docs new --title T [--dir D] [--template N]` | создать черновик (create-only) |
| `docs search --query Q [--type T] [--limit N] [--within P] [--budget B]` | лексический поиск с фрагментами |
| `docs read --id ID [--section S\|--anchor A\|--line-range N-M\|--pointer P\|--columns C --rows R --where K=V]` | чтение с проекцией |
| `docs tree [--within P] [--max-depth N]` | дерево папок и документов с типами |
| `docs edit --id ID --patch-file F [--preview\|--apply] [--if-hash H]` | построчная правка после предпросмотра |

### Записи и отношения

| Команда | Назначение |
|---|---|
| `records create --type T --input-file F [--preview\|--apply]` | создать запись (create-only) |
| `records list [--type T] [--since D] [--until D] [--relation TYPE=ID] [--limit N]` | список с фильтрами |
| `records query --query-file F` | декларативный запрос (`$in`, `$gte`, `$lte`) |
| `records aggregate --metric FIELD --type T [--group-by F]` | сумма с единицами, формулой и provenance |
| `records read --id ID [--view NAME]` | запись целиком или проекция |
| `relations graph --from ID [--type T] [--depth N] [--limit N]` | обход типизированного графа |

### Типы и ремонт

| Команда | Назначение |
|---|---|
| `types list` | все типы датасета |
| `types show TYPE_ID` | описатель типа |
| `types guide [--format markdown\|json] [--out PATH]` | сгенерированное описание типовой системы |
| `fix --diagnostic ID [--preview\|--apply] [--if-hash H]` | применить один предложенный фикс |

### Глобальные опции

| Опция | Значение |
|---|---|
| `--root TEXT` | DATA_ROOT (повторяется для нескольких датасетов) или `TODOC_ROOT` |
| `--output [json\|table\|markdown]` | по умолчанию `json` |
| `--no-input` | запрет интерактива |
| `--version` | версия |

## Контракт вывода

Каждая команда возвращает конверт:

```json
{"schema_version": 1, "ok": true, "data": {}, "diagnostics": [], "next_actions": []}
```

В stdout при `--output json` — ровно один JSON-текст. `next_actions[].argv` — готовые массивы
аргументов следующего шага.

| Код выхода | Смысл |
|---|---|
| 0 | успех |
| 1 | операционная ошибка |
| 2 | ошибка использования |
| 3 | ошибка валидации |
| 4 | отказ в доступе |
| 5 | конфликт (хеш/перезапись) |
| 6 | незавершённая генерация |

## Типовые сценарии

```bash
# Ремонт битой ссылки: ID берём из того же вывода validate
todoc validate --root KB --all
todoc fix --root KB --diagnostic diag_0042 --preview
todoc fix --root KB --diagnostic diag_0042 --apply

# Запись с предпросмотром
todoc records create --root KB --type note --input-file note.json --preview
todoc records create --root KB --type note --input-file note.json --apply

# Агрегация с единицами измерения
todoc records aggregate --root KB --type metric --metric value --group-by aspect

# Сохранённый запрос
todoc records query --root KB --query-file KB/.todoc/queries/decisions-accepted.json
```

## Демо-датасет

[`demo/`](demo/README.md) — готовый DATA_ROOT со всей документацией проекта, разложенной по типам
папок и документов: 14 `dir_types`, 19 `doc_types`, 12 `entity_types`, 9 `relation_types`,
130 записей, 125 отношений, JSON Schema для каждого типа записи, сохранённые запросы и CSV-инвентарь.

```bash
todoc validate --root demo --all                       # 0 диагностик
todoc types list --root demo
todoc docs search --root demo --query "портабельность" --limit 3
todoc records aggregate --root demo --type metric --metric value --group-by aspect
todoc relations graph --root demo --from decision:no-lsp --depth 2
```

## Структура репозитория

```
src/todoc/            код: cli, application, domain, adapters, typing_system, output
tests/                300 тестов: unit, cli, integration
demo/                 демо-датасет (DATA_ROOT) — живой пример всех возможностей
.doc/
├── plan/             конституция, план реализации, конкурентный анализ, аудит, AFTER-планы
└── state/            документация текущего состояния системы (14 разделов)
references/           справка по подсистемам (входит в Skill)
SKILL.md              точка входа Agent Skill
guides (корень)       гайды для агентов: CLI, MCP, Markdown KB
assets/               шаблон DATA_ROOT для Skill
```

## Документация

| Что читать | Где |
|---|---|
| Текущее состояние системы | [`.doc/state/README.md`](.doc/state/README.md) |
| Справочник CLI для агента | [`.doc/state/03-cli-reference.md`](.doc/state/03-cli-reference.md) |
| Как агенту работать безопасно | [`.doc/state/12-agent-operations.md`](.doc/state/12-agent-operations.md) |
| Известные проблемы | [`.doc/state/11-known-issues.md`](.doc/state/11-known-issues.md) |
| Норматив (что строить) | [`.doc/plan/constitution.md`](.doc/plan/constitution.md) |
| План реализации (как строить) | [`.doc/plan/implementation-plan.md`](.doc/plan/implementation-plan.md) |
| Конкурентный анализ | [`.doc/plan/competitive-analysis.md`](.doc/plan/competitive-analysis.md) |
| Аудит реализации | [`.doc/plan/audit-implementation.md`](.doc/plan/audit-implementation.md) |
| Пост-MVP направления | `.doc/plan/*.after.md` (MCP, память, векторный поиск, веб, импорт, синхронизация) |
| Гайды для агентов | `guide_cli_for_agents_ru.md`, `guide_mcp_for_agents_ru.md`, `guide_markdown_knowledge_for_agents_ru.md` |
| Справка Skill | [`SKILL.md`](SKILL.md) и [`references/`](references/) |

## Тесты

```bash
PYTHONPATH=src python3 -m pytest tests
PYTHONPATH=src python3 -m coverage run -m pytest tests
PYTHONPATH=src python3 -m coverage report -m
```

## Ограничения MVP

Нет MCP-сервера, векторного поиска, веб-интерфейса, импорта PDF/DOCX, синхронизации и LSP.
Всё это описано как отдельные AFTER-планы в [`.doc/plan/`](.doc/plan/).
