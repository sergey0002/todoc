---
id: doc:bugs/bug-044-status-next-actions-contract.md
title: "BUG-044: status отдаёт next_actions с ключами action/reason вместо argv/purpose"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
bug_id: BUG-044
status: fixed
severity: minor
agent_impact: friction
tokens_extra_est: 500
component: cli
found: 2026-11-28
tags: [bugs, bug-report, cli, output, contract, next-actions]
---

# BUG-044: status отдаёт next_actions с ключами action/reason вместо argv/purpose

| Поле | Значение |
|---|---|
| Bug ID | BUG-044 |
| Компонент | cli (`status`, `output/envelope.py`) |
| Обнаружено | 2026-11-28 — аудит контракта next_actions |
| Окружение | todoc 0.1.0 (5e86eb7 + рабочее дерево), Python 3.14.3, Windows 11 + WSL2 Ubuntu |

## Сводка

`todoc status` на датасете без индекса кладёт в `next_actions` объект
`{"action": "todoc index rebuild", "reason": "..."}` вместо контрактного
`{"argv": [...], "purpose": "..."}`. JSON-потребитель, ожидающий `argv`,
получает пустой массив; table-режим печатает `next:  (reason)` — команда
теряется.

## Шаги воспроизведения

1. `todoc init --root "$KB" --dataset-id status-ds` (индекс ещё не собран).
2. `todoc status --root "$KB" --output json`
3. `todoc status --root "$KB" --output table`

## Ожидаемое поведение

Все элементы `next_actions` — `{"argv": ["todoc", "index", "rebuild"], "purpose":
"..."}`, как в README («`next_actions[].argv` — готовые массивы аргументов
следующего шага», `README.md:189-190`) и во всех остальных командах
(`src/todoc/cli.py:71-72`, `1248-1251` и т.д.). Рендер `envelope.emit` тоже
рассчитан на `argv`/`purpose` (`src/todoc/output/envelope.py:52-54`).

## Фактическое поведение

- `status()` формирует `next_actions` с ключами `action`/`reason`:
  `src/todoc/cli.py:2359-2361`.
- В JSON: `"next_actions": [{"action": "todoc index rebuild", "reason": "..."}]`.
- В table/markdown `emit` делает `" ".join(action.get("argv", []))` — пустая
  строка, и печатает `next:  (Индекс ещё не опубликован: ...)`.
- Агент, исполняющий `next_actions[].argv`, не получает команду.

## Доказательства

```
$ todoc status --root "$KB" --output json
  "next_actions": [
    {
      "action": "todoc index rebuild",
      "reason": "Индекс ещё не опубликован: считать документы не по чему."
    }
  ]

$ todoc status --root "$KB" --output table
ok: True
...
next:  (Индекс ещё не опубликован: считать документы не по чему.)
```

Код: `src/todoc/cli.py:2359-2361`; `src/todoc/output/envelope.py:52-54`.

## Воздействие

- `friction`: машинный потребитель `next_actions` ломается на единственной
  команде; агент вынужден вручную собирать `todoc index rebuild`.
- В table-режиме команда следующего шага вообще не видна — только причина.
- Цена эпизода: 1 лишний вызов/догадка ≈ 500 токенов.

## Предложение по исправлению

1. Заменить объект на `{"argv": ["todoc", "index", "rebuild"], "purpose":
   "Индекс ещё не опубликован: считать документы не по чему."}`.
2. Добавить контрактный тест: каждый `next_actions[]` во всех командах имеет
   `argv` (list) и `purpose` (str).
3. По желанию — валидация конверта в `emit` (fail-fast на неверной форме).

## Заметки

Поиск перед созданием (2026-11-28): `docs search --type bug-report --query
"next_actions status"` — совпадений по форме next_actions нет (BUG-021 —
guidance, BUG-013 — output-контракты). Связанные: BUG-037 (глобальный
`--output`), BUG-013.

- 2026-11-28: `fixed` — коммит `7d32813`. `status` без индекса отдаёт `next_actions` в форме `{argv, purpose}`. Тест: `tests/cli/test_unified_e2e.py`.
