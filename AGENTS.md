# AGENTS.md — правила работы агентов с этим репозиторием

> **Временный файл** — на время тестирования и эксплуатации в этом чекауте.
> Канонические правила системы живут в самой системе (датасете) и переносятся
> с ней: [demo/notes/agent-contract.md](demo/notes/agent-contract.md),
> стартовые промпты типов (`todoc types prompt <тип> --op create`),
> [demo/HOME.md](demo/HOME.md), [SKILL.md](SKILL.md). Этот файл — сжатая
> шпаргалка поверх них, не второй источник истины.

> Файл для кодинг-агентов (Codex, Claude Code, Cursor и др.). Здесь — как
> работать с системой `todoc` и её демо-датасетом: железные правила сессии,
> команды, границы. Для людей — [README.md](README.md), карта демо —
> [demo/HOME.md](demo/HOME.md).

## Что это за проект

`todoc` — переносимый типизированный слой знаний поверх обычных файлов
(Markdown/CSV/JSON): source-native валидатор, типизированные записи,
ограниченный поиск и чтение. CLI-first и agent-first. **Файлы — источник
истины; индекс и кэш — производные и пересобираемые.**

## Запуск CLI

**Основной маршрут (проверен, работает без установки)** — системный Python в WSL
с `PYTHONPATH=src`:

```bash
wsl -d Ubuntu -- bash -lc "cd ~/projects/todoc && env PYTHONPATH=src python3 -m todoc --version"
# todoc, version 0.1.0
```

Зависимости (`click`, `jsonschema`, `markdown-it-py`, `pytest`) уже стоят в
системном Python 3.14 WSL — ставить ничего не нужно. Внутри WSL-шелла это
просто `PYTHONPATH=src python3 -m todoc …`; из харнесса (PowerShell на Windows) —
обёртка `wsl -d Ubuntu -- bash -lc "cd ~/projects/todoc && …"` выше.

Дальше в документе запись `todoc <аргументы>` означает именно этот запуск
(`env PYTHONPATH=src python3 -m todoc <аргументы>`); из харнесса — та же
команда в обёртке `wsl -d Ubuntu -- bash -lc "cd ~/projects/todoc && …"`.

**`.venv` для гейта покрытия (проверено 2026-11-28).** В Ubuntu нет пакета
`python3.14-venv`, поэтому `.venv` создан без `pip`. Ставить `coverage` в
системный Python не нужно: dev-зависимости кладутся в проектный `.venv`
системным pip через `--python`:

```bash
wsl -d Ubuntu -- bash -lc "cd ~/projects/todoc && python3 -m pip --python .venv/bin/python install -e '.[dev]'"
wsl -d Ubuntu -- bash -lc "cd ~/projects/todoc && .venv/bin/python -m coverage --version"
```

После этого гейт покрытия идёт через `.venv/bin/python` (см. правило 6).
Маршрут без установки для обычных вызовов CLI остаётся прежним:
`env PYTHONPATH=src python3 -m todoc …`.

**Гейты (из WSL)** — тот же префикс, без установки пакета:

```bash
wsl -d Ubuntu -- bash -lc "cd ~/projects/todoc && env PYTHONPATH=src python3 -m pytest tests/cli/test_unified_e2e.py"
wsl -d Ubuntu -- bash -lc "cd ~/projects/todoc && env PYTHONPATH=src python3 -m todoc validate --root demo --all"
```

Python 3.11+. Запуск из Windows-Python тоже возможен
(`$env:PYTHONPATH="src"; python -m todoc …`), но он отдаёт UNC-пути
(`\\wsl.localhost\…`) и другую кодировку stdout — для контрактных проверок
используй WSL-маршрут.

## Железные правила сессии

1. **Навигация и шаблоны — через CLI, редактирование — напрямую + `todoc sync`.**
   Поиск, оглавление и чтение секций (`docs search/read/tree`, `records list/read/query`),
   а также создание новых каркасов по шаблонам (`docs new`, `records create`) выполняй
   через CLI `todoc`. **Существующие файлы датасета (`.md`, `.json`, `.csv`) редактируй
   напрямую штатным инструментом редактора, сразу после чего обязательно запускай короткую
   команду финализации `todoc sync --root demo <path>`** (она обновит `updated:`, историю,
   кэш индекса и проверит валидность). Не правь руками даты `created`/`updated` и
   автособираемые витрины (`export`, рендеры `flow render --write`).

2. **Перепроверяй каждый шаг.** После мутации — обратное чтение результата
   (`docs read`, `records read`, `explain-path`); после изменений данных —
   `todoc validate --root demo --all` = 0 диагностик. Для read-only обзора
   достаточно проверить `complete`/`truncated`/`next_cursor` и не дублировать
   чтение (иначе каждый обзор удваивает вызовы). Не переходи к следующему шагу,
   пока проверка не прошла. Сломалось — фиксируй баг-репорт (правило 3), чини,
   повторяй проверку.

3. **Фиксируй баги сразу.** Баг — это не только сломанное поведение: **любой
   дефект или недочёт эксплуатации, который потребовал повторных вызовов,
   обходных путей, доставил агенту неудобство или перерасходовал токены по
   сравнению с прямым взаимодействием с файлами без CLI**. Система обязана
   быть дешевле прямого доступа — каждый эпизод обратного фиксируй:

   ```bash
   todoc docs new --root demo --type bug-report --title "BUG-NNN: суть" --dir bugs
   todoc types prompt bug-report --op create --root demo   # инструкция по заполнению
   ```

   (Из харнесса — в обёртке `wsl -d Ubuntu -- bash -lc "cd ~/projects/todoc && …"`,
   см. «Запуск CLI»; голый `todoc …` в PowerShell не запускается.)

   Один документ = один баг, **перед созданием — поиск дубликата**
   (`docs search --type bug-report` по симптому и компоненту; нашёл — сослайся
   на `BUG-NNN`, не создавай; канон: `demo/notes/agent-contract.md` → «Баг-репорты»).
   Заполни все секции шаблона: шаги воспроизведения
   с точными командами, ожидание против факта, доказательства — выводы CLI и
   `файл:строка`. Статус (`open|triaged|in_progress|fixed|wontfix|duplicate`),
   `severity` и **`agent_impact`** (`none | friction | token_overrun`, можно
   списком; при перерасходе — `tokens_extra_est`) — во front matter. Номер NNN
   продолжай по папке `bugs/`. Репорт не удаляется: закрытие — смена статуса
   с датой и коммитом в «Заметках».

   Фильтрация репортов для анализа:
   `todoc records query --root demo --query-file demo/.todoc/queries/bugs-agent-friction.json`
   (фрикция) и `…/bugs-token-overrun.json` (перерасход токенов);
   быстрый ранжирующий вариант — `docs search --type bug-report --query "agent_impact friction"`.

4. **Создание по шаблонам и финализация правок (`todoc sync`).** Новые записи —
   `records create --preview` → `--apply` (create-only: дубль отклоняется), новые
   документы — `docs new`. Правки существующих файлов — напрямую в файле + сразу
   `todoc sync --root demo <path>` (при конкуренции — `--if-hash <hash>`). Команда
   `docs edit` сохранена для внешних скриптов, но не навязывается агенту.

5. **Счётчики — от факта.** Источник истины — `todoc types list --root demo`
   и фактический вывод команд, не числа в README. Обнаружил расхождение —
   обнови документ и/или заведи баг-репорт (см. BUG-003 как пример).

6. **Гейты перед коммитом.** Изменения данных: `validate --root demo --all`
   = 0 диагностик + `tools/linkcheck.py` (0 битых). Изменения кода `src/`:
   полный `pytest` и гейт покрытия 100% (`coverage run --branch …`,
   `coverage report --fail-under=100`) — это проектное правило, падение
   останавливает CI.

   В текущем окружении гейт покрытия идёт через проектный `.venv`
   (установка — см. «Запуск CLI»):
   `env PYTHONPATH=src .venv/bin/python -m coverage run --branch --source=src/todoc -m pytest -q`
   и `.venv/bin/python -m coverage report -m --fail-under=100`.
   Проверено 2026-11-28: `TOTAL 100%` (8817 строк, 3300 ветвей). Обычный
   `env PYTHONPATH=src python3 -m pytest` остаётся быстрым прогоном без покрытия.

7. **Прогрессивная опора и самодокументация ошибок для моделей (`P15`).**
   На старте флоу модель получает общий компактный скил без лишних рамок;
   если модель падает на тесте или валидации CLI, стандартное поле `guidance`
   (обязательное в любом ошибочном и неошибочном выводе `json/table/markdown`)
   выдаёт ей подробную рекомендацию и ссылки на развёрнутый скил (`--mode guided`)
   и документы. В Python-коде зашиваются только коды ситуаций (`code`), а сами
   подсказки и ссылки хранятся в переключаемом `i18n`-каталоге и покрываются
   контрактными тестами CLI.

## Именование: русский заголовок — в метаданных, файл — на английском

Канон — в системе: `demo/notes/agent-contract.md` → «Именование документов»
и раздел «Именование файла» в каждом стартовом промпте
(`todoc types prompt <тип> --op create`). Коротко:

- **Заголовок — на русском, в поле `title`** (front matter md / поле записи json);
  поле `name` для заголовка не вводится — `title` уже стандарт.
- **Файл — на английском** (латиница, kebab-case); при кириллическом заголовке —
  явный путь: `todoc docs new --path <dir>/<english-slug>.md` (слаг наследует
  кириллицу — BUG-006).
- Существующие кириллические имена (`plan/`, `bugs/`) — legacy, не размножать.

## Скилы: подключение движка к агенту

Канон — в системе: `demo/notes/agent-contract.md` → «Скилы: хранилище,
диспетчер, мьют, импорт». Коротко: перед нетривиальной задачей —
`todoc skills tree --root demo` → выбрать скил по описанию →
`todoc skills read --root demo --path <путь>` → следовать SKILL.md.
Платформам с нативными скилами — только диспетчер:
`todoc skills attach --to <каталог скилов платформы> --root demo`
(витрина в платформы не монтируется). В этом чекауте диспетчер уже смонтирован
в `.kilo/skills/todoc/SKILL.md`; после `git pull` его нужно обновлять той же
командой с `--apply`.

## Быстрая шпаргалка

**Правило запуска.** Из харнесса (PowerShell на Windows) голая строка `todoc …`
не работает. Все команды ниже даны в полном виде: внешние кавычки — двойные,
значения с пробелами — в одинарных (такая форма работает и в PowerShell, и в
POSIX-шелле). Внутри WSL-шелла обёртку `wsl -d Ubuntu -- bash -lc "…"`
отбрасывай и оставляй `env PYTHONPATH=src python3 -m todoc …` после
`cd ~/projects/todoc`. Если в аргументе есть `$`, внешние двойные кавычки
PowerShell его подставят — экранируй обратным апострофом.

**Не используй внешние одинарные кавычки** (`wsl … -- bash -lc '…'` с
внутренними двойными): такой argv молча теряет хвост — всё после первого
значения с пробелом, а `\n` съедается (BUG-028). Ошибки не будет, результат
выглядит правдоподобно. Перед мутирующей командой проверь обёртку:

```bash
wsl -d Ubuntu -- bash -lc "printf '[%s]' 'a b' --limit 5 --fields path,title"
# ожидается: [a b][--limit][5][--fields][path,title]
```

```bash
# обзор документов типа и статуса — одна команда (вместо N чтений тел)
wsl -d Ubuntu -- bash -lc "cd ~/projects/todoc && env PYTHONPATH=src python3 -m todoc docs list --root demo --type bug-report --status open --fields id,path,title,status --limit 1000"

# найти документы; в ответе поле id — его передавай в docs read
wsl -d Ubuntu -- bash -lc "cd ~/projects/todoc && env PYTHONPATH=src python3 -m todoc docs search --root demo --query 'лимит' --limit 5"

# прочитать секцию: --section — точный текст заголовка без '#'
wsl -d Ubuntu -- bash -lc "cd ~/projects/todoc && env PYTHONPATH=src python3 -m todoc docs read --root demo --id 'doc:bug-001-fm-doc-type-unknown' --section 'Сводка'"

# карта папок; по умолчанию отдаёт 50 узлов — смотри truncated/next_cursor
wsl -d Ubuntu -- bash -lc "cd ~/projects/todoc && env PYTHONPATH=src python3 -m todoc docs tree --root demo --max-depth 2 --limit 200"

# записи entity_type (json); здесь --type — entity_type, не doc_type
wsl -d Ubuntu -- bash -lc "cd ~/projects/todoc && env PYTHONPATH=src python3 -m todoc records list --root demo --type task"

# все объявленные типы: doc_type / entity_type / dir_type / relation_type
wsl -d Ubuntu -- bash -lc "cd ~/projects/todoc && env PYTHONPATH=src python3 -m todoc types list --root demo"

# стартовый промпт типа — инструкция, как заполнять запись/документ
wsl -d Ubuntu -- bash -lc "cd ~/projects/todoc && env PYTHONPATH=src python3 -m todoc types prompt bug-report --op create --root demo"

# финализация прямой правки файла: updated, история, индекс, валидация
wsl -d Ubuntu -- bash -lc "cd ~/projects/todoc && env PYTHONPATH=src python3 -m todoc sync --root demo demo/bugs/bug-023-cli-not-reachable-from-harness.md"

# гейт данных: 0 диагностик
wsl -d Ubuntu -- bash -lc "cd ~/projects/todoc && env PYTHONPATH=src python3 -m todoc validate --root demo --all"
```

Подводные камни (проверено на этом чекауте):

- `--section` принимает точный текст заголовка без `#`; при промахе —
  `docs.section_not_found`. Если сообщение обрезало имя до первого слова,
  виновата потеря кавычек в обёртке, а не CLI: перейди на форму с внешними
  двойными кавычками (см. выше).
- Без `--budget` секция ограничена 40 строками; ответ даёт честные
  `section_total_lines` и `truncated` (BUG-005 исправлен) — дочитывай
  `--line-range` или задавай `--budget`.
- `docs tree` усекает вывод (default `--limit 50`), но честно сообщает
  `truncated`/`next_cursor`; сужай `--within` или поднимай `--limit` (≤1000).
- `records …` работает только с `entity_type`; для документов — `docs …`.
  `records list --type bug-report` теперь даёт `query.namespace_mismatch`
  (BUG-020 исправлен), а неизвестное имя — `query.unknown_type`. Для обзора
  документов используй
  `docs list --type bug-report --status open --fields id,path,title,status`.
- `docs search` отдаёт `status` и `doc_type` в проекции (BUG-022/057 исправлены),
  но `docs search --type <t>` дополнительно считает JSON-зеркала из
  `records/documents/`, поэтому `total` больше числа md-файлов. Для обзора
  бери `docs list --type <t> --status <s> --origin document`; отсутствие
  статуса проверяй через `--status-missing` (это и есть зеркала без fm `status`).
- Неизвестные `--type`/`--status` в `docs list` теперь дают диагностику
  `docs.unknown_type`/`docs.unknown_status` с guidance (BUG-055 закрыт для list);
  `docs search` по-прежнему отвечает пустым результатом — сверяй имя типа с
  `todoc types list --root demo`.
- После прямой правки любого файла датасета обязательно `sync` — иначе
  индекс/`validate` разойдутся с файлом.
- Явный `doc_type` во front matter резолвится в себя
  (`rule_source: front-matter`), `unknown` больше не появляется (BUG-001
  исправлен). Чтобы тип получил правила и шаблоны, объяви его в `.todoc/`.
- По умолчанию `--output json`; для человека — `--output table` или
  `--output markdown`.

## Границы

- Не менять `.todoc/` руками без необходимости: типы и правила — данные,
  правятся осознанно, каждый шаг — через `check-config`/`validate`.
- Никаких фоновых процессов, скрытой сети и `eval`; каждый шаг воспроизводим.
- Не удалять и не переименовывать репорт-документы и журналы; история —
  это часть знания (append-only для версий и репортов).
- Обновлённые счётчики и HOME-карта (`demo/HOME.md`) — часть любого PR,
  меняющего структуру демо.
