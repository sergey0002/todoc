---
id: doc:bugs/bug-023-cli-not-reachable-from-harness.md
title: "BUG-023: CLI недоступен из харнеса — нет venv и entrypoint"
doc_type: bug-report
lang: ru
bug_id: BUG-023
status: open
severity: major
agent_impact: [friction, token_overrun]
tokens_extra_est: 4000
component: engine
found: 2026-11-28
created: 2026-11-27
updated: 2026-11-28
tags: [bugs, bug-report, harness, environment, entrypoint, wsl]
---

# BUG-023: CLI недоступен из харнеса — нет venv и entrypoint

| Поле | Значение |
|---|---|
| Bug ID | BUG-023 |
| Компонент | engine / окружение (точка входа CLI) |
| Обнаружено | 2026-11-28 — первый вызов `todoc` в сессии агента |
| Окружение | Windows 11, PowerShell 5.1, WSL2 Ubuntu, Python 3.14.4, todoc 0.1.0 (5e86eb7) |

## Сводка

В чекауте нет `.venv` и нет исполняемого `todoc`; в харнесе (PowerShell на
Windows, данные в WSL) команда не находится. `AGENTS.md` описывает только
POSIX-установку (`.venv/bin/todoc`), поэтому каждый вызов приходится вручную
оборачивать в `wsl -e bash -lc 'cd … && PYTHONPATH=src python3 -m todoc …'`, а
тройное квотирование (PowerShell → `wsl.exe` → bash) ломает регулярки и пайпы.

## Шаги воспроизведения

1. В харнес-шелле: `todoc --version`
2. В WSL: `command -v todoc`, `ls .venv`, `ls .venv/bin/todoc`
3. Прочитать раздел «Установка» в `AGENTS.md`.
4. Попробовать обёртку с пайпом/регуляркой:
   `wsl -e bash -lc 'cd ~/projects/todoc && rg -e action-logging -e "todoc trace" demo/plan'`

## Ожидаемое поведение

После документированной установки (или из коробки в чекауте) агент вызывает
`todoc …` одной командой в своём шелле. `AGENTS.md` даёт рабочую для этой среды
команду либо shim-скрипт. `todoc doctor` сообщает, что entrypoint найден.

## Фактическое поведение

- `todoc --version` → `CommandNotFoundException` (PowerShell).
- `command -v todoc` → не найдено; `.venv` отсутствует; `.venv/bin/todoc` отсутствует.
- Единственный рабочий путь — `PYTHONPATH=src python3 -m todoc`, то есть каждый
  вызов пишется вручную и длиннее в ~4 раза.
- Обёртка `wsl -e bash -lc '…'` искажает кавычки и пайпы: регулярка
  `-e a -e b` внутри двойных кавычек приводит к `docs: command not found`,
  цикл `for q in …` — к `syntax error: unexpected end of file`, heredoc — к
  `here-document at line 1 delimited by end-of-file`.

## Доказательства

```
PS> todoc docs tree --root demo --max-depth 2
todoc : Имя "todoc" не распознано как имя командлета...
+ FullyQualifiedErrorId : CommandNotFoundException

$ command -v todoc || echo "todoc: NOT FOUND"
todoc: NOT FOUND
$ ls .venv/bin/todoc
.venv/bin/todoc: NOT FOUND
$ ls -d .venv
.venv: NOT FOUND
```

```
# AGENTS.md, раздел «Установка»
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/todoc --version             # todoc, version 0.1.0
```

```
# искажение пайпа/кавычек в обёртке
$ wsl -e bash -lc 'cd ~/projects/todoc && rg -l -e action-logging -e "todoc trace" demo/plan'
logging|todoc: line 1: action: command not found
```

## Воздействие

Первый же вызов в сессии падает, и агент вынужден изобретать обёртку. Это
порождает три класса потерь: (1) 4+ неудачных вызовов на старте; (2) постоянный
перерасход на удлинение каждой команды; (3) тихие искажения команд с пайпами и
кавычками, из-за которых результаты поиска оказываются неполными без явной
ошибки. Суммарно в сессии — около 4k токенов и несколько ложных «пустых»
результатов.

## Предложение по исправлению

- Добавить `tools/todoc` (bash: `exec python3 -m todoc` с `PYTHONPATH=src`) и
  `tools/todoc.cmd`/`tools/todoc.ps1`, которые принимают аргументы как есть, без
  пересборки строки.
- Добавить `tools/bootstrap.sh`: venv → `pip install -e ".[dev]"` → `todoc --version`
  → `todoc doctor`, идемпотентно.
- В `AGENTS.md` — раздел «Среда исполнения»: ОС/шелл, точная форма вызова, запрет
  `grep -R` по корню, `rg -e a -e b src tests` вместо пайпов.
- `todoc doctor` — печатать найден ли entrypoint, версию Python, root и
  `next_actions` с командой установки.
- Проверка: в чистом клоне после `tools/bootstrap.sh` команда `todoc --version`
  работает в шелле харнеса; `todoc doctor` не содержит ошибок окружения.

## Заметки

Поиск перед созданием (2026-11-28): `--type bug-report --query "entrypoint PATH venv"` — совпадений нет.
Связанные: BUG-012 (гигиена `git status`), идея
[`ideas/action-logging.md`](../ideas/action-logging.md) (отладка сессий агента
невозможна без рабочего entrypoint).
