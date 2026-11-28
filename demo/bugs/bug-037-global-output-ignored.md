---
id: doc:bugs/bug-037-global-output-ignored.md
title: "BUG-037: глобальный --output игнорируется подкомандами"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
bug_id: BUG-037
status: open
severity: minor
agent_impact: [friction, token_overrun]
tokens_extra_est: 1000
component: cli
found: 2026-11-28
tags: [bugs, bug-report, cli, output, contract]
---

# BUG-037: глобальный --output игнорируется подкомандами

| Поле | Значение |
|---|---|
| Bug ID | BUG-037 |
| Компонент | cli (глобальная опция `--output` и локальные копии в подкомандах) |
| Обнаружено | 2026-11-28 — аудит контракта вывода |
| Окружение | todoc 0.1.0 (5e86eb7 + рабочее дерево), Python 3.14.3, Windows 11 + WSL2 Ubuntu |

## Сводка

`--output` объявлен на группе (`todoc --output table validate ...`), но каждая
подкоманда объявляет свою копию с `default="json"`. Click передаёт в callback
значение подкоманды, поэтому глобальный `--output table|markdown` молча
игнорируется, а вывод остаётся JSON. Глобальная опция при этом документирована
в README как рабочая.

## Шаги воспроизведения

1. `todoc --output table validate --root demo` — глобальная опция перед командой.
2. `todoc validate --root demo --output table` — та же опция после команды.
3. Сравнить формат вывода: в п. 1 — JSON, в п. 2 — `ok: True` и строки `key: value`.

## Ожидаемое поведение

`--output` — одна опция с одним значением на вызов. Если она задана на группе,
подкоманда не должна перекрывать её значением по умолчанию; приоритет:
явная опция подкоманды → явная опция группы → `json`. Контракт README:
«Глобальные опции → `--output [json|table|markdown]`» (`README.md:172-179`).

## Фактическое поведение

- Группа объявляет `--output` с `default="json"` и сохраняет его в
  `_group_output` (`src/todoc/cli.py:153-166`).
- Каждая подкоманда объявляет свою `--output` с тем же `default="json"`
  (например, `src/todoc/cli.py:190`, `268`, `294`, `329`), поэтому callback
  получает `json`, даже если на группе передано `table`.
- `_group_output` используется только для error-envelope (`src/todoc/cli.py:2369-2382`),
  а не для успешного вывода.
- В результате `todoc --output table validate` печатает JSON; `todoc --output
  table --help` и справка подкоманд обещают обратное.

## Доказательства

```
$ todoc --output table validate --root demo
{
  "schema_version": 1,
  "ok": true,
  "data": {
    "datasets": [
      {
        "dataset_id": "dataset-80c70868",
        ...

$ todoc validate --root demo --output table
ok: True
datasets: [{'dataset_id': 'dataset-80c70868', 'documents': 476, 'diagnostics': []}]
```

Код: `src/todoc/cli.py:155` (группа), `src/todoc/cli.py:190/268/294` (локальные
копии с `default="json"`), `src/todoc/cli.py:162-164` (`_group_output`).

## Воздействие

- `friction`: агент/человек, следующий README, получает JSON вместо table и
  вынужден повторять вызов с опцией после команды (или парсить JSON).
- `token_overrun`: JSON-конверт `validate` на демо — десятки килобайт; table-режим
  в разы короче. Один лишний вызов + повторное чтение ≈ 1k токенов за эпизод.
- Ошибки при этом всегда печатаются в формате `_group_output`, то есть формат
  успеха и ошибки может расходиться в одном вызове.

## Предложение по исправлению

1. Оставить `--output` только на группе, а в подкомандах использовать
   `default=None` и `_effective_output(local or _group_output or "json")`.
2. Либо убрать глобальную опцию из README, если поддерживается только локальная.
3. Тест: `todoc --output table validate` печатает table; `todoc --output table
   validate --output json` печатает JSON (явная локальная опция важнее).

## Заметки

Поиск перед созданием (2026-11-28): `docs search --type bug-report --query
"global output option"` — совпадений по корневой причине нет (BUG-013 —
неоднородные id/envelope, BUG-021 — guidance). Связанные: BUG-040
(`status.next_actions`), BUG-013 (output-контракты).
