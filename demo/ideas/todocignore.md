---
id: doc:ideas/todocignore.md
title: "Идея: .todocignore — исключение посторонних файлов и папок из индексации по синтаксису gitignore"
doc_type: idea
lang: ru
status: captured
created: 2026-11-26
updated: 2026-11-26
tags: [ideas, idea, todocignore, gitignore, pathspec, scanner, индексация]
related: ["[[folder-config]]", "[[skills-engine]]", "[[constitution.md]]", "[[agent-brainstorming-and-research-packs]]"]
---

# Идея: `.todocignore` — исключение посторонних файлов и папок из индексации

- Тип: `idea`
- Создан: 2026-11-26
- Идентификатор: `doc:ideas/todocignore.md`
- Статус: `captured` (идея зафиксирована, не перешла в план)

## Суть

Ввести служебные файлы **`.todocignore`** со стандартным синтаксисом `.gitignore` (на базе Python-библиотеки `pathspec` и класса `GitIgnoreSpec`) в корне `DATA_ROOT` и в подпапках датасета вместо захардкоженных в Python-коде списков игнорируемых директорий. Единый матчер `.todocignore` сквозным образом учитывается во **всех** подсистемах кода — при сканировании, инвалидации индекса, чтении `.config.json`, валидации, поиске, сканировании скилов, записи новых документов, объяснении путей (`explain-path`) и проверке ссылок (`tools/linkcheck.py`).

## Проблема

1. **Правила исключения зашиты в код движка, а не в данные датасета.** Сейчас `src/todoc/adapters/filesystem/scanner.py` жёстко хранит `HARD_EXCLUDE_DIRS = {".todoc", ".git", "__pycache__", "node_modules", ".obsidian", ".venv", "venv"}`, а `tools/linkcheck.py` — отдельный `SKIP_DIRS` (куда пришлось вручную вписывать `"skills-audit"`, `"index"`, `"cache"`). Два списка уже разошлись, а любое новое исключение (`dist/`, `.pytest_cache/`, `tmp/`, черновики, дампы исследований) требует правки исходников Python.
2. **Посторонние файлы раздувают индекс и зашумляют поиск.** В `demo/` из `443` документов индекса `96` лежат внутри `skills/` (`15` файлов скриптов `.cjs`/`.js`/`.sh`/`.html` со статусом `format: opaque` и `51` вспомогательный `.md` промптов/референсов с `doc_type: unknown`). Код, HTML-шаблоны и служебные промпты попадают в общий счётчик `documents` и конкурируют с документами базы знаний в выдаче `todoc docs search`.
3. **Ложные падения `todoc validate --all` при импорте внешних паков и хранении артефактов рядом с KB.** У пакетов скилов из открытой экосистемы (см. [обзор готовых паков](../.research/agent-brainstorming-and-research-packs.md)) внутри `templates/`, `references/`, `scripts/`, `evals/` регулярно встречаются ссылки-заглушки в шаблонах (`markdown.link.target_missing`), нестандартные поля `tags`/`updated` во front matter (`markdown.tags_invalid`), `tsconfig.json` с комментариями или негативные тест-фикстуры `.json`/`.csv`. Без декларативного игнора такой пакет роняет валидацию всего датасета.
4. **Разрозненные обходчики дерева в коде.** `scanner.py` (`scan_dataset`), `folder_config.py` (`_folders_under`), `skills.py` (`scan_skills` через `rglob`), `cli.py` (`explain-path`, `skills import`) и `tools/linkcheck.py` обходят файловую систему независимо — единого фильтра путей в кодовой базе нет.

## Принципы

1. **Стандартный синтаксис `.gitignore` без собственного диалекта.** Разбор правил делегируется библиотеке `pathspec` (`GitIgnoreSpec`), повторяющей реальную семантику Git: `*`, `**`, `?`, диапазоны `[...]`, корневой якорь `/foo`, признак директории `foo/`, комментарии `#`, экранирование `\#`/`\!` и правила отрицания `!`.
2. **Точка истины рядом с данными и иерархический каскад (P1).** Корневой `<DATA_ROOT>/.todocignore` задаёт базовые правила датасета, а вложенный `<folder>/.todocignore` действует относительно своей папки и переопределяет родительские правила — по аналогии с `.gitignore` в Git и `.config.json` в [folder-config](folder-config.md). При копировании папки раздела её правила игнорирования переносятся вместе с ней.
3. **Разделение системного инварианта `todoc` и пользовательских правил.** Безусловно зарезервированными в коде остаются только собственные служебные артефакты движка: директория `.todoc/`, контейнер `.git/` и служебные файлы `.todocignore`, `.config.json`, `.todoc.json` (они никогда не становятся документами индекса, даже если `.todocignore` отсутствует или содержит `!*`). Все окруженческие и проектные маски (`__pycache__/`, `node_modules/`, `.venv/`, `venv/`, `.obsidian/`, `dist/`, `skills/**/scripts/` и др.) переезжают из хардкода в `.todocignore`.
4. **Единый источник истины во всех модулях («везде в коде»).** Ни один модуль не хранит собственный список `SKIP_DIRS` / `HARD_EXCLUDE_DIRS` для пользовательского мусора — все обходчики вызывают общий матчер.
5. **Наблюдаемость вместо «тихого исчезновения» ([Конституция, FR-5.1](../plan/constitution.md)).** Исключённый путь не попадает в `documents`/`records`, но `todoc explain-path` явно сообщает `ignored: true` с указанием файла `.todocignore` и номера строки сработавшего правила.

## Предложение

### 1. Зависимость и матчер (`pathspec` / `GitIgnoreSpec`)

- В `pyproject.toml` (`[project].dependencies`) добавляется `pathspec>=1.0` (`0` обязательных транзитивных зависимостей, чистый Python, лицензия `MPL-2.0`).
- Используется именно класс `pathspec.GitIgnoreSpec` (а не упрощённый `PathSpec`), чтобы краевые случаи Git с исключёнными директориями (`dir/` против `dir/*` + `!dir/keep.md`) работали предсказуемо.
- Создаётся единый модуль `src/todoc/adapters/filesystem/ignore.py`:
  - `IgnoreRuleHit(ignored: bool, source_path: str, line: int, pattern: str)` — диагностический след сработавшего правила.
  - `IgnoreMatcher` — стек правил `(base_rel_dir, GitIgnoreSpec, rules_meta)` от корня `DATA_ROOT` к текущей подпапке:
    - `is_ignored(rel_path: str, is_dir: bool = False) -> bool`;
    - `explain(rel_path: str, is_dir: bool = False) -> IgnoreRuleHit | None` — возвращает последнее совпавшее правило в каскаде (включая `!`-размьют, если файл был явно возвращён);
    - `can_prune_dir(rel_dir: str) -> bool` — возвращает `True`, если директория заигнорена и в активном стеке нет `!`-паттернов, способных вернуть файлы внутри неё (позволяет `os.scandir` не спускаться в `node_modules/` и `.venv/`).

### 2. Замена жёстких правил и стартовый шаблон

- В `scanner.py` константа `HARD_EXCLUDE_DIRS` заменяется на узкий системный инвариант:
  - `SYSTEM_RESERVED_DIRS = {".todoc", ".git"}`;
  - `SYSTEM_CONTROL_FILES = {".todoc.json", ".config.json", ".todocignore"}`.
- Команда `todoc init` создаёт стартовый `<DATA_ROOT>/.todocignore` с типовыми правилами окружения (`.obsidian/`, `__pycache__/`, `*.py[cod]`, `node_modules/`, `.venv/`, `venv/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `dist/`, `build/`, `.DS_Store`), которые владелец датасета может свободно редактировать и дополнять.
- Читается **только** `.todocignore` (репозиторный `.gitignore` автоматически не подхватывается, так как границы Git и границы индекса знаний различаются: `scripts/` внутри скила хранятся в Git, но могут исключаться из индекса `todoc`, и наоборот).

### 3. Сквозной учёт во всех подсистемах кода

| Модуль / инструмент | Как учитывается `.todocignore` |
|---|---|
| `src/todoc/adapters/filesystem/ignore.py` | Новый единый загрузчик и каскадный матчер всех `.todocignore` внутри `DATA_ROOT` (детерминированный обход, UTF-8, учёт вложенных файлов). |
| `src/todoc/adapters/filesystem/scanner.py` | `scan_dataset` передаёт каждый путь через `SYSTEM_RESERVED_*` + `IgnoreMatcher`; при `can_prune_dir` отсекает поддерево до чтения файлов; считает число пропущенных заигноренных входов. |
| `src/todoc/application/registry.py`, `service.py` | Хеши всех найденных `.todocignore` включаются в `config_digest`: любая правка, добавление или удаление `.todocignore` автоматически инвалидирует кеш индекса в `ensure_index()`. |
| `src/todoc/application/folder_config.py` | `_folders_under` использует общий обходчик с `IgnoreMatcher` вместо собственного цикла с `HARD_EXCLUDE_DIRS`: `.config.json` внутри заигноренных папок не читаются и не попадают в `docs tree` / `docs suggest`. |
| `src/todoc/application/validator.py`, `mentions.py` | Заигноренные `.md`/`.json`/`.csv` не попадают в `scanned_files`, `documents`, `records`, `relations`, `mentions` и не вызывают ошибок схем и метаданных. Для относительных ссылок из индексируемых документов (например, `SKILL.md` → `scripts/start-server.sh`): если цель внутри `DATA_ROOT` заигнорена в `.todocignore`, но физически существует на диске, ссылка не считается битой (`markdown.link.target_missing` не репортуется; `#anchor` и mention-рёбра для заигноренной цели не строятся). |
| `src/todoc/application/search.py` | `docs search` и `docs list` работают только по неигнорируемым документам индекса — код скриптов, шаблоны и фикстуры перестают засорять выдачу. |
| `src/todoc/application/skills.py` | `scan_skills` пропускает `SKILL.md`, лежащие в заигноренных ветках (например, внутри архивов, тест-фикстур или `node_modules/`). При этом для активного скила (чей `SKILL.md` не заигнорен) счётчики ресурсов `scripts`/`refs`/`assets` на диске продолжают отображаться в `todoc skills tree`, даже если папка `scripts/` исключена из документного индекса. |
| `src/todoc/application/history.py`, `service.py` | `observe_history` и `history adopt` не фиксируют `external.change` на заигноренных файлах; изменения самих `.todocignore` корректно видны как конфигурационные правки. |
| `src/todoc/cli.py` (`explain-path`, `status`, мутации) | `todoc explain-path` для заигноренного пути вместо `explain.path_not_found` возвращает `{path, ignored: true, rule_source: "<rel>/.todocignore:<line>", pattern: "..."}`. `todoc status` показывает счётчик `ignored`. Мутирующие команды (`docs new`, `records create`) при попытке записи в заигноренный путь возвращают ошибку `write.path_ignored`, защищая агента от создания «невидимого» документа. |
| `tools/linkcheck.py` | Заменяет захардкоженный `SKIP_DIRS` на вызов общего `IgnoreMatcher` от корня проверки (с сохранением базовой защиты на `.git/` и `.todoc/`). |

### 4. Пример использования в датасете

Корневой `demo/.todocignore`:

```gitignore
# Окружение и кэши инструментов
.obsidian/
__pycache__/
*.py[cod]
node_modules/
.venv/
venv/
.pytest_cache/
.ruff_cache/

# Внутренние скрипты и тестовые прогоны скилов не индексируем как документы KB
skills/**/scripts/
skills/**/evals/
```

Локальный `demo/skills/process/superpowers/.todocignore` (переносится вместе с пакетом при копировании):

```gitignore
# Вспомогательные промпты субагентов и референсы пакета не индексируем в общий поиск KB,
# оставляя в индексе только точки входа SKILL.md
*/*
!*/SKILL.md
```

## План внедрения

1. **Фаза 1 — Ядро матчера и зависимость (`pathspec`):**
   - Добавить `pathspec>=1.0` в `pyproject.toml`.
   - Реализовать `src/todoc/adapters/filesystem/ignore.py` (`IgnoreMatcher`, каскад корневого и вложенных `.todocignore`, `explain`, `can_prune_dir`).
   - *Acceptance:* 100% branch coverage на unit-тестах: корневые и вложенные `.todocignore`, `*`/`**`/`?`, `/root-only`, `dir/`, `!`-отрицания, комментарии `#`, экранирование `\#`/`\!`, пустые файлы и невалидные последовательности байт (диагностика `ignore.unreadable` без падения сканера).
2. **Фаза 2 — Интеграция в сканер, инвалидацию индекса, валидатор и `folder_config`:**
   - Перевести `scanner.py` и `folder_config.py` с `HARD_EXCLUDE_DIRS` на `SYSTEM_RESERVED_*` + `IgnoreMatcher`.
   - Включить хеши `.todocignore` в `config_digest` (`registry.py`).
   - Обновить `_check_markdown_links` в `validator.py` для валидных локальных ссылок на физически существующие заигноренные ресурсы внутри `DATA_ROOT`.
   - *Acceptance:* правка `.todocignore` автоматически пересобирает индекс при следующем чтении; заигноренные `.md`/`.json`/`.csv` не попадают в `documents`/`records`; ссылки из `SKILL.md` на `scripts/*` не роняют `validate --all`.
3. **Фаза 3 — Скилы, CLI-наблюдаемость, write-guard и `linkcheck`:**
   - Подключить `IgnoreMatcher` в `skills.py`, `explain-path`, `status`, `docs new` / `records create` (`write.path_ignored`) и `tools/linkcheck.py`.
   - Добавить создание дефолтного `.todocignore` в `todoc init` и положить каноничный `demo/.todocignore`.
   - *Acceptance:* `explain-path` на заигноренном файле возвращает `ignored: true` и `rule_source` с номером строки; `docs new --path tmp/ignored.md` при правиле `tmp/` отказывает с `write.path_ignored`; `todoc validate --root demo --all` = `0` диагностик, `tools/linkcheck.py` = `0` broken.

## Открытые вопросы

- **Ссылки из обычных документов KB на заигноренные файлы:** разрешать любые относительные ссылки на существующие на диске файлы под `.todocignore` без диагностик (удобно для `SKILL.md` → `scripts/run.py` и отчётов → сырых дампов), или вне `skills/` выдавать `warning` о ссылке на неиндексируемый артефакт?
- **Граница системного инварианта для `.git/`:** держать `.git/` в безусловном `SYSTEM_RESERVED_DIRS` вместе с `.todoc/` (чтобы случайное удаление `.todocignore` никогда не проиндексировало `.git/objects/`), или оставить безусловным только `.todoc/`? Рекомендуемый вариант — держать оба (`.todoc`, `.git`) в системном инварианте.
- **Поведение при импорте чужого пакета (`todoc skills import`):** должен ли `skills import` автоматически генерировать дефолтный локальный `.todocignore` (например, игнорирующий `scripts/`, `evals/`, `templates/` для общего индекса документов) или оставлять это на усмотрение корневого `demo/.todocignore`?
- **Отдельная CLI-команда диагностики:** достаточно ли расширенного `todoc explain-path <path>` (аналог `git check-ignore -v`), или нужна отдельная команда `todoc ignore check <path>` для пакетной проверки списка путей?

## Связанные документы

- [Конституция `todoc` (FR-4.6, FR-5.1)](../plan/constitution.md)
- [Инженерный набросок (§7.1–7.3: границы сканирования и грамматика масок)](../.research/engineering-plan.md)
- [Идея: `.config.json` — самоописание папок](folder-config.md)
- [Идея: хранилище-движок скилов на `todoc`](skills-engine.md)
- [Обзор готовых паков скилов и скриптов для мозговых штурмов и ресёрча](../.research/agent-brainstorming-and-research-packs.md)
