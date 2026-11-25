# todoc

Переносимый типизированный слой знаний поверх обычных файлов: source-native валидатор,
типизированные записи, ограниченный поиск и чтение. CLI-first и agent-first.

Файлы — источник истины. Индекс и кэш — производные и пересобираемые.

| Показатель | Значение |
|---|---|
| Команд CLI | 26 |
| Тестов | 437 (все проходят) |
| Покрытие | 100% — 2491 инструкция, 868 веток |
| Зависимости | `click`, `jsonschema`, `markdown-it-py` |
| Демо-датасет | [`demo/`](demo/README.md): 248 документов, 157 записей, 0 диагностик |

## Установка

Нужен Python **3.11+**. Полное руководство — [`docs/installation.md`](docs/installation.md).

```bash
pip install -e .          # editable (разработка)
pip install .             # обычная установка
pip install -e ".[dev]"   # + pytest и coverage
todoc --version           # todoc, version 0.1.0
```

Без установки: `PYTHONPATH=src python3 -m todoc --version`.

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
| `docs new --title T [--dir D\|--path P] [--type T] [--template T\|FILE]` | создать документ из шаблона типа (create-only) |
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
| `types show TYPE_ID` | описатель типа + пути шаблона, CRUD-промптов и схемы записи |
| `types prompt TYPE_ID [--op read\|create\|edit\|delete]` | стартовый промпт типа под операцию |
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

# Документ из шаблона типа: промпт операции → создание → проверка структуры
todoc types prompt --root KB guide --op create
todoc docs new --root KB --type guide --title "Как читать конверт" --dir guides
todoc validate --root KB --all

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
157 записей, 138 отношений, JSON Schema для каждого типа записи, сохранённые запросы и CSV-инвентарь.

```bash
todoc validate --root demo --all                       # 0 диагностик
todoc types list --root demo
todoc docs search --root demo --query "портабельность" --limit 3
todoc records aggregate --root demo --type metric --metric value --group-by aspect
todoc relations graph --root demo --from decision:no-lsp --depth 2
```

## Структура репозитория

```
SKILL.md              точка входа Agent Skill
README.md             этот файл
pyproject.toml        пакет, зависимости, console entry point
src/todoc/            код: cli, application, domain, adapters, typing_system, output
tests/                437 тестов: unit, cli, integration (покрытие 100%)
docs/
├── README.md         индекс всей документации
├── installation.md   установка, проверка, первый датасет
├── plan/             конституция, план реализации, конкурентный анализ, аудит, AFTER-планы,
│                     engineering-draft.md — инженерный набросок §1–§18
├── state/            документация текущего состояния системы (15 разделов)
├── guides/           гайды для агентов: CLI, MCP, Markdown KB
└── research/         исследования и аудиты, skills-audit/ — материалы аудита
references/           справка по подсистемам (входит в Skill)
assets/               шаблон DATA_ROOT для Skill
bench/                бенчмарк качества: 30 критериев, скрипт, результаты
tools/                служебные скрипты репозитория: пересборка demo-копий state, линкчекер
demo/                 демо-датасет (DATA_ROOT) — живой пример всех возможностей
```

В корне нет отдельных документов: план — в `docs/plan/`, состояние — в `docs/state/`,
гайды — в `docs/guides/`, исследования — в `docs/research/`.

## Документация

| Что читать | Где |
|---|---|
| Установка и первый запуск | [`docs/installation.md`](docs/installation.md) |
| Индекс всей документации | [`docs/README.md`](docs/README.md) |
| Текущее состояние системы | [`docs/state/README.md`](docs/state/README.md) |
| Справочник CLI для агента | [`docs/state/03-cli-reference.md`](docs/state/03-cli-reference.md) |
| Как агенту работать безопасно | [`docs/state/12-agent-operations.md`](docs/state/12-agent-operations.md) |
| Известные проблемы | [`docs/state/11-known-issues.md`](docs/state/11-known-issues.md) |
| Бенчмарк качества и сравнение с конкурентами | [`docs/state/15-benchmark.md`](docs/state/15-benchmark.md) |
| Норматив (что строить) | [`docs/plan/constitution.md`](docs/plan/constitution.md) |
| План реализации (как строить) | [`docs/plan/implementation-plan.md`](docs/plan/implementation-plan.md) |
| Конкурентный анализ | [`docs/plan/competitive-analysis.md`](docs/plan/competitive-analysis.md) |
| Аудит реализации | [`docs/plan/audit-implementation.md`](docs/plan/audit-implementation.md) |
| Пост-MVP направления | `docs/plan/*.after.md` (MCP, память, векторный поиск, веб, импорт, синхронизация) |
| Гайды для агентов | `docs/guides/cli-for-agents.md`, `docs/guides/mcp-for-agents.md`, `docs/guides/markdown-knowledge-for-agents.md` |
| Справка Skill | [`SKILL.md`](SKILL.md) и [`references/`](references/) |

## Тесты

```bash
PYTHONPATH=src python3 -m pytest tests
PYTHONPATH=src python3 -m coverage run -m pytest tests
PYTHONPATH=src python3 -m coverage report -m
```

## Бенчмарк качества

Качество измеримо: 30 критериев (контракт, корректность, детерминизм, безопасность записи,
ограниченное чтение, поиск, устойчивость, производительность, покрытие, портабельность)
проверяются скриптом на копии демо-датасета с 9 намеренно внесёнными дефектами как ground truth.

```bash
python3 bench/run_benchmark.py                     # только todoc
python3 bench/run_benchmark.py --venv /tmp/comp    # + конкуренты (obsidiantools, open-knowledge)
```

Текущий результат: **29.5 из 30**, F1 детекции дефектов 1.00, MRR поиска 1.00,
437 тестов и покрытие 100%. Критерии — [`bench/criteria.md`](bench/criteria.md),
результаты — [`bench/results/benchmark.md`](bench/results/benchmark.md),
разбор и план улучшений — [`docs/state/15-benchmark.md`](docs/state/15-benchmark.md).

## Ограничения MVP

Нет MCP-сервера, векторного поиска, веб-интерфейса, импорта PDF/DOCX, синхронизации и LSP.
Всё это описано как отдельные AFTER-планы в [`docs/plan/`](docs/plan).
