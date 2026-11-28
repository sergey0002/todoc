---
id: doc:bugs/bug-065-change-id-grammar.md
title: "BUG-065: change_id без валидации грамматики строит путь из сырого идентификатора"
doc_type: bug-report
lang: ru
status: fixed
severity: critical
component: engine
agent_impact: friction
created: 2026-11-28
updated: 2026-11-28
tags: [bugs, bug-report, change, containment, ids]
---

# BUG-065: `change_id` без валидации грамматики строит путь из сырого идентификатора

| Поле | Значение |
|---|---|
| Bug ID | BUG-065 |
| Компонент | engine (`application/changes.py`, `cli.py`) |
| Обнаружено | 2026-11-28 — аудит остатка CLI, R-C |
| Окружение | todoc 0.1.0, Python 3.14.4, Ubuntu (WSL) |

## Сводка

`change_dir` брал `change_id.split(":", 1)[-1]` и присоединял результат к
`changes/` без проверки формы. Идентификаторы с `/`, `..` или абсолютным путём
уходили в файловые операции, а `change show/apply/archive/revert/validate/verify`,
`log --change` и `context --change` отвечали `change.not_found` вместо usage-ошибки.

## Шаги воспроизведения

1. `env PYTHONPATH=src python3 -m todoc --root demo change show change:../../etc/passwd`
2. До исправления — `change.not_found` (exit 6); путь уже построен из сырого ID.
3. То же для `change:../sentinel.md`, `change:a/b`, `/etc/passwd`.

## Ожидаемое поведение

Некорректный публичный идентификатор отклоняется до любых операций с ФС:
`usage.invalid_id`, exit 2. Отсутствующий, но корректный ID остаётся
`change.not_found`.

## Фактическое поведение

До исправления путь строился из непроверенного слага, а диагностика смешивала
«нет такого изменения» и «такая форма невозможна».

## Доказательства

После исправления:

```
$ env PYTHONPATH=src python3 -m todoc --root demo change show change:../../etc/passwd
{"ok": false, "diagnostics": [{"code": "usage.invalid_id", ...}], ...}
rc=2
```

Контроль: `change:absent` → `change.not_found` (exit 6), форма сохранена.
Тесты: `tests/unit/test_changes.py::test_require_change_id_rejects_malformed_ids`,
`tests/cli/test_cli_changes.py::test_change_commands_reject_malformed_ids`,
`test_log_rejects_malformed_change_filter`,
`test_malformed_id_does_not_touch_outside_paths`.

## Воздействие

`critical`/`friction`: идентификатор приходит из внешнего ввода (CLI, скрипты,
агент), поэтому без валидации путь мог выйти за `changes/` и за DATA_ROOT.
Обходной путь — вручную проверять форму до вызова, что лишние вызовы и риск.

## Предложение по исправлению

`require_change_id` проверяет `change:<[A-Za-z0-9][A-Za-z0-9._-]*>` и запрещает
`..`; вызывается в `change_dir` (единая точка построения пути) и в CLI-фильтрах
`log --change` / `context --change`. Guidance `usage.invalid_id` и таблица
диагностик обновлены.

## Заметки

- 2026-11-28: `fixed` — коммит `22db1df`. Связанные: BUG-034 (граница цели
  дельты), BUG-035 (путь истории).
