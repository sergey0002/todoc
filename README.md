# todoc

Переносимый типизированный слой знаний поверх обычных файлов: source-native валидатор,
типизированные записи, ограниченный поиск и чтение. CLI-first и agent-first.

Файлы — источник истины. Индекс и кэш — производные и пересобираемые.

| Показатель | Значение |
|---|---|
| Команд CLI | 64 листовых (29 верхнего уровня, 10 групп) |
| Тестов | 1316 |
| Покрытие | 100% — 6481 инструкций, 2432 веток |
| Зависимости | `click`, `jsonschema`, `markdown-it-py` |
| Демо-датасет | [`demo/`](demo/README.md): 465 документов, 205 записей, 0 диагностик |

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
todoc init --apply --root ./knowledge

# 2. Проверить конфигурацию и состояние
todoc check-config --root ./knowledge
todoc index rebuild --apply --root ./knowledge
todoc status --root ./knowledge

# 3. Найти и прочитать
todoc docs search --root ./knowledge --query "refresh token" --limit 3
todoc docs read --root ./knowledge --id doc:notes/design.md --section "Decision"

# 4. Валидировать всё
todoc validate --root ./knowledge --all
```

Корень можно задать один раз через переменную окружения: `export TODOC_ROOT=./knowledge`.

## Работа агентов с системой

Канонические правила — в самой системе и переносятся с датасетом:
`demo/notes/agent-contract.md` (контракт CLI и конвенции, включая именование),
стартовые промпты типов (`todoc types prompt <тип> --op create`), карта
`demo/HOME.md`, скил [SKILL.md](SKILL.md). Сжатая шпаргалка поверх них —
в [AGENTS.md](AGENTS.md) (временный файл на время тестирования). Кратко:

```bash
todoc docs search --root demo --query "…" --limit 5          # найти
todoc docs read --root demo --id doc:… --section "…"          # прочитать (bounded)
todoc records create --root demo --type … --input-file F --preview  # создать запись (review-first)
todoc sync --root demo <путь>                                # финализировать прямую правку файла (updated, history, index, validate)
todoc types prompt <тип> --op create --root demo              # стартовый промпт типа
todoc validate --root demo --all                              # 0 диагностик — обязательный гейт
```

Дефекты и недочёты, найденные при эксплуатации, фиксируются баг-репортами
в `demo/bugs/` (один документ = один баг, статус и критичность во front matter,
репорты не удаляются): `todoc docs new --type bug-report --title "BUG-NNN: суть" --dir bugs`.

### Скилы (открытый стандарт Agent Skills)

Хранилище — `demo/skills/`: папка со SKILL.md = скил (опционально `references/`,
`scripts/`); иерархия разделов = дерево решений. Канон правил —
`demo/notes/agent-contract.md` → «Скилы».

```bash
todoc skills tree --root demo                    # оглавление на лету (live-scan, bounded)
todoc skills tree --root demo --all              # + мьютнутые (!-папки) с пометкой [!]
todoc skills read --root demo --path <из дерева> # тело скила (path-confinement, --budget)
todoc skills attach --apply --to .claude/skills --root demo   # диспетчер-скил todoc платформе
todoc skills import --apply --root demo --src <папка/репо> --into <раздел>   # офлайн-импорт
```

- **Подключение к любому агенту:** платформам с нативными скилами — одна папка
  диспетчера `todoc` (`skills attach`); остальным — строка роутинга в AGENTS.md.
  Витрина в платформы **не монтируется** — L1-контекст несёт ровно один скил
  (~100 токенов) при vault любого размера.
- **Чужой скил — «просто закинул папку»:** скопировать папку в vault →
  `todoc validate --root demo --all` (live-скан подхватит); целые пакеты — только
  папки со SKILL.md, плагинная обвязка (hooks/, манифесты) не переносится; либо
  одной командой `skills import`. Чужие скрипты — аудировать (скил
  `coding/review/security-review`).
- После мьюта/импорта: `todoc index rebuild --apply --root demo`.

## Все команды

### Датасет и проверка

| Команда | Назначение |
|---|---|
| `init --root PATH` | создать `.todoc/`: датасет, правила, типы, шаблоны |
| `check-config` | загрузить конфигурацию и реестр типов |
| `check [--strict]` | сводка: документы, ошибки, предупреждения |
| `scan` | обход датасета без публикации индекса |
| `sync [PATHS...] [--dirty] [--if-hash H] [--allow-derived] [--no-history]` | финализация после прямой правки файлов: бамп `updated:`, фиксация ревизии в `history`, защита автособираемых витрин (`guidance`), пересборка индекса и валидация |
| `validate [--all]` | полная валидация с точными локациями |
| `index status` / `index rebuild` | состояние и пересборка поколения индекса |
| `explain-path PATH` | почему путь получил свой тип (`rule_source`) |
| `doctor [--check IDS]` | диагностика окружения (только чтение) |
| `status` | снимок последнего поколения |

### Документы

| Команда | Назначение |
|---|---|
| `docs new --title T [--dir D\|--path P] [--type T] [--template T\|FILE]` | создать документ из шаблона типа (create-only) |
| `docs search --query Q [--type T] [--limit N] [--within P] [--budget B]` | лексический поиск с фрагментами; слова из конфига папки-предка дают буст +2 |
| `docs read --id ID[#раздел] [--section S\|--anchor A\|--line-range N-M\|--pointer P\|--columns C --rows R --where K=V]` | чтение с проекцией; fragment в id — синоним `--section` (конфликт — usage.error) |
| `docs tree [--within P] [--match Q] [--max-depth N]` | дерево папок и документов с типами; `--match` фильтрует папки скорингом конфигов |
| `docs suggest --query Q [--limit N]` | «куда положить / где искать»: скоринг папок по `.config.json` (score ≥ 0.25, reason у каждого кандидата) |
| `docs edit --id ID --patch-file F [--preview\|--apply] [--if-hash H]` | построчная правка после предпросмотра |
| `docs flow render --id flow:X [--section state\|table\|mermaid\|lineage\|terms] [--write PATH]` | витрина флоу из записи: state machine, таблица решений (колонка «Режим»), mermaid, lineage, термины по `uses_term`; `--write` — материализация с fm `derived_from` (дрейф ловит `stale`; ручной файл без `derived_from` не перезаписывается) |
| `docs flow walk --id flow:X [--at NODE] [--all-paths]` | проход дерева решений: ветви по приоритету, props развилок (`mode`/`default_branch`), все ациклические пути до терминалов |
| `docs status --id ID [--set V]` | чтение/смена статуса md-документа: fm `status`, набор — `allowed_statuses` doc_type; set бампает `updated:` и пишет ревизию; документ без поля статуса не получает его молча |
| `records status --id ID [--set V]` | чтение/смена поля `status` JSON-записи (набор — enum схемы entity_type); меняется только `status`, атомарно, с ревизией |
| `interop export --kind dmn|asl|rasa --id ID [--write exports/…md]` | экспорт витрины во внешний формат: derived-артефакт с fm `derived_from` на записи-источники (дрейф ловит `stale`); перезапись только derived-целей; без `--write` — артефакт в stdout |

#### Конфиги папок (`.config.json`)

Папка (в т.ч. раздел vault скилов) может описать себя файлом `.config.json`.
Конфиг — не документ: сканер исключает его из индекса, поиска и счётчиков;
неизвестные поля игнорируются с диагностикой, битый JSON/тип/порядок даёт
коды `folder.config.*` в `validate`, но вывод продолжает работать (fail-open).

| Поле | Тип | Смысл |
|---|---|---|
| `schema_version` | int (1) | версия схемы конфига |
| `title` | строка ≤80 | заголовок (русский — по конвенции демо) |
| `aliases` | строка, разделитель `\|` | точные синонимы: совпадение подстрокой даёт максимальный score в `docs suggest` |
| `description` | строка ≤500 | описание папки |
| `order` | int | порядок сортировки разделов (меньше — выше) |
| `tags` | список строк ≤80 | тематические теги; слово запроса из тега даёт буст в `docs search` |
| `icon`, `lang` | строки ≤50 / ≤10 | опциональные украшения |

```bash
todoc docs suggest --root demo --query "идея про релиз"   # → skills/process через alias «релиз»
todoc explain-path --root demo plan                        # папка: dir_type + мета конфига-предка
```

### Записи и отношения

| Команда | Назначение |
|---|---|
| `records create --type T --input-file F [--preview\|--apply]` | создать запись (create-only) |
| `records list [--type T] [--since D] [--until D] [--relation TYPE=ID] [--limit N]` | список с фильтрами |
| `records query --query-file F` | декларативный запрос (`$in`, `$gte`, `$lte`) |
| `records aggregate --metric FIELD --type T [--group-by F]` | сумма с единицами, формулой и provenance |
| `records read --id ID [--view NAME]` | запись целиком или проекция; `mentioned_in{file,line,fragment}` — витрины и упоминания md |
| `relations graph --from ID [--type T] [--depth N] [--limit N]` | обход типизированного графа; упоминания md — рёбра `via:mention` |
| `relations tree --from ID [--type T] [--depth N] [--limit N]` | вложенное дерево: группировка по type_id, out/in, cycle-защита, mention помечен |
| `records undo-relation --id ID --pointer /relations/N [--apply] [--expected-hash H]` | точечный откат ребра из ревизий журнала (preview по умолчанию) |

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
папок и документов: 24 `dir_types`, 31 `doc_types`, 25 `entity_types`, 18 `relation_types`,
205 записей, 169 отношений, JSON Schema для каждого типа записи, сохранённые запросы и CSV-инвентарь.

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
src/todoc/            код: cli, application, domain, ports, adapters, typing_system, output
tests/                1316 тестов: unit, cli, integration (покрытие 100%)
docs/
├── README.md         индекс всей документации
├── installation.md   установка, проверка, первый датасет
├── plan/             конституция, план реализации, конкурентный анализ, аудит, AFTER-планы,
│                     engineering-draft.md — инженерный набросок §1–§18
├── state/            документация текущего состояния системы (16 разделов)
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
| Отчёт по остаткам: что открыто и в каком порядке | [`docs/state/16-leftovers-report.md`](docs/state/16-leftovers-report.md) |
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

Текущий результат: **30.0 из 30**, F1 детекции дефектов 1.00, MRR поиска 1.00,
1316 тестов и покрытие 100%. Критерии — [`bench/criteria.md`](bench/criteria.md),
результаты — [`bench/results/benchmark.md`](bench/results/benchmark.md),
разбор и план улучшений — [`docs/state/15-benchmark.md`](docs/state/15-benchmark.md).

## Ограничения MVP

Нет MCP-сервера, векторного поиска, веб-интерфейса, импорта PDF/DOCX, синхронизации и LSP.
Всё это описано как отдельные AFTER-планы в [`docs/plan/`](docs/plan).
