# 17. Скилы: хранилище-движок, формат Agent Skills, жизненный цикл

Реализовано полностью. Источники: идея [«Хранилище-движок скилов»](../../demo/ideas/skills-engine.md)
→ план [skills-vault-implementation](../../demo/plan/skills-vault-implementation.md) (44/44, fm done)
и план [«скилы-взаимодействия»](../../demo/plan/скилы-взаимодействия--захват--план--исполнение--переходы--жизненный-цикл.md)
(35/35, fm done, PR #82/#83). Модули: `application/skills.py` (162 строки), CLI-группа `skills`.

## Формат скила

Скил = папка с `SKILL.md` (формат открытого стандарта Agent Skills): front matter
`name` + `description` (англ., «Use when…»), тело — инструкции (When to Use /
Procedure / Pitfalls / Verification). Vault — папка `skills/` внутри DATA_ROOT
(по умолчанию; `--vault` переопределяет). Секции vault — префиксы путей
(`process/`, `coding/git/…`). Мьют скила — `!`-префикс имени папки.

## Команды

| Команда | Поведение | Коды ошибок |
|---|---|---|
| `skills tree [--vault V] [--within P] [--query Q] [--all] [--limit N] [--max-depth N]` | оглавление на лету (live-scan, без индекса — P1); `--query` — lowercase-подстрока по name+description+пути (кириллица работает); `--all` показывает мьютнутые с пометкой `[!]`; счётчик секций — только свои файлы (BUG-008 fixed) | — |
| `skills read --path P [--line-range A-B] [--budget B] [--vault V]` | содержимое SKILL.md; путь резолвится **только внутри vault** (confinement) | `skills.not_found`, `skills.path_escape`, `skills.not_a_skill` |
| `skills attach --to DIR [--force]` | диспетчер-скил `todoc/` → платформенный каталог (`.claude/skills/`, `.agents/skills/`, `.cursor/skills/…`), `{ROOT}` подставляется DATA_ROOT; витрина в платформу не монтируется — L1-контекст несёт один скил ~100 токенов | `skills.attach_exists` (без `--force`) |
| `skills import --src S --into SECTION [--skill NAME] [--dry-run] [--adopt] [--vault V]` | офлайн-импорт чужих скилов (папки со SKILL.md, обвязка пакетов не переносится); `--adopt` — источник уже в vault: валидация без копии | `skills.import_*` |

## Хранилище демо

30 скилов: 15 каноничных (в т.ч. 4 скила жизненного цикла `skills/process/todoc-{capture,plan,execute,transitions}`)
+ 15 superpowers (импортированы `skills import`). Диспетчер `todoc/` приаттачится
командой `skills attach --to <платформа>`. Дерево: `todoc skills tree --root demo`.

## Жизненный цикл через скилы (процедурный, не движковый)

1. **capture**: идея из диалога → `docs new --type idea` + fm-статус `captured` (fm-статус
   вписывается docs edit-патчем — `docs new` статусов не пишет, BUG-011/013 контекст).
2. **plan**: аудит идеи → план `docs new --type plan`, fm `status: active` +
   `derived_from` на хеш идеи; задачи — `records create --type task` с `implements`
   (и `subtask_of` у подзадач).
3. **execute**: работа по плану сверху вниз, тики чекбоксов в коммите шага;
   `records status --set …` для задач; **терминальные статусы (`done`) — только по
   явной фразе пользователя** (конвенция, не движковый guard — DESIGN-Q01).
4. **transitions**: `docs status --set` плана/идеи (allowed_statuses), re-anchor
   `derived_from` при дрейфе (BUG-011), stale = 0 как гейт.

## Связанные разделы

- [03-cli-reference.md](03-cli-reference.md) — сигнатуры команд.
- [12-agent-operations.md](12-agent-operations.md) — как агенты применяют скилы.
- [13-demo-dataset.md](13-demo-dataset.md) — состав vault демо.
