---
id: doc:bugs/bug-040-skills-read-invalid-range.md
title: "BUG-040: skills read падает traceback на некорректном --line-range и принимает --budget -1"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
bug_id: BUG-040
status: fixed
severity: minor
agent_impact: friction
tokens_extra_est: 500
component: cli
found: 2026-11-28
tags: [bugs, bug-report, cli, skills, validation, p11]
---

# BUG-040: skills read падает traceback на некорректном --line-range и принимает --budget -1

| Поле | Значение |
|---|---|
| Bug ID | BUG-040 |
| Компонент | cli (`skills read`) |
| Обнаружено | 2026-11-28 — аудит валидации числовых опций |
| Окружение | todoc 0.1.0 (5e86eb7 + рабочее дерево), Python 3.14.3, Windows 11 + WSL2 Ubuntu |

## Сводка

`skills read` разбирает `--line-range` через `int()` без обработки ошибок:
`--line-range abc` роняет команду Python-traceback (`ValueError`) вместо
usage-ошибки. Дополнительно `--budget -1` не отклоняется и обрезает ровно один
последний байт (`encoded[:-1]`), а `--line-range 5-2` возвращает пустой успех.

## Шаги воспроизведения

1. `todoc skills read --root demo --path process/todoc-plan --line-range abc --output json`
2. `todoc skills read --root demo --path process/todoc-plan --line-range 5-2 --output json`
3. `todoc skills read --root demo --path process/todoc-plan --budget -1 --output json`

## Ожидаемое поведение

- Некорректный `--line-range` — `usage.error` (exit 2) с сообщением
  «expected N or N-M», как у `docs read` (`_parse_line_range`,
  `src/todoc/cli.py:138-150`).
- `--budget` — неотрицательное целое; отрицательное значение — `usage.error`.
- Диапазон с `start > end` или за концом файла — явная ошибка/пустая выдача с
  `truncated`/`line_total`, а не молчаливый `content: ""`.

## Фактическое поведение

- `skills_read` делает `lo, hi = max(1, int(a or 1)), int(b or 10**9)` без
  `try/except` (`src/todoc/cli.py:461-465`); `abc` → `ValueError: invalid literal
  for int() with base 10: 'abc'` и traceback.
- `--budget -1`: `len(encoded) > -1` истинно, `content = encoded[:-1]` — весь
  файл без последнего байта, `truncated: true`; отрицательный бюджет не отвергнут
  (`src/todoc/cli.py:466-470`).
- `--line-range 5-2`: `lines[4:2]` — пустая строка, `ok: true`,
  `truncated: false`.

## Доказательства

```
$ todoc skills read --root demo --path process/todoc-plan --line-range abc --output json
  File "...\src\todoc\cli.py", line 463, in skills_read
    lo, hi = max(1, int(a or 1)), int(b or 10**9)
ValueError: invalid literal for int() with base 10: 'abc'

$ todoc skills read --root demo --path process/todoc-plan --line-range 5-2 --output json
  "ok": true,
    "content": "",
    "truncated": false

$ todoc skills read --root demo --path process/todoc-plan --budget -1 --output json
  "ok": true,
    "content": "---\nid: doc:skills/process/todoc-plan/SKILL.md\n..."   # весь файл без последнего байта
    "truncated": true,
```

Код: `src/todoc/cli.py:461-470`.

## Воздействие

- `friction`: агент получает traceback вместо машинно-читаемого конверта и
  вынужден повторять вызов/обходить `--line-range` другим способом.
- Отрицательный бюджет молча портит содержимое (теряется последний байт), а не
  сообщает об ошибке — риск неверного чтения скила.
- Цена эпизода: 1–2 повторных вызова ≈ 500 токенов.

## Предложение по исправлению

1. Переиспользовать `_parse_line_range` из `docs read` (или общий helper) для
   `skills read`; ошибки — `ValidationError("usage.invalid_line_range")`.
2. Проверять `budget >= 0`; при отрицательном — `usage.error`.
3. Для `start > end` и `start > len(lines)` — явная диагностика
   (`skills.line_range_invalid`) с `line_total`.
4. Тест: `--line-range abc` → exit 2, без traceback; `--budget -1` → exit 2;
   `--line-range 5-2` → ошибка диапазона.

## Заметки

Поиск перед созданием (2026-11-28): `docs search --type bug-report --query
"skills read line-range"` — совпадений по корневой причине нет (BUG-018 —
docs read budget, BUG-005 — section budget). Связанные: BUG-018 (бюджет),
BUG-042 (docs read --line-range вне файла).

- 2026-11-28: `fixed` — коммит `7d32813`. Невалидный `--line-range` даёт `usage.invalid_line_range` (exit 3), `--budget -1` — `usage.error` (exit 2), без traceback. Тест: `tests/cli/test_unified_failures.py::test_skill_line_range_past_end_is_rejected`.
