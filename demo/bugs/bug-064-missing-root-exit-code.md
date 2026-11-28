---
id: doc:bugs/bug-064-missing-root-exit-code.md
title: "BUG-064: usage.missing_root отдаёт exit 3 вместо обещанных 2"
doc_type: bug-report
lang: ru
status: fixed
severity: minor
component: cli
agent_impact: friction
tokens_extra_est: 300
found: 2026-11-28
created: 2026-11-28
updated: 2026-11-28
tags: [bugs, bug-report, cli, exit-codes, contract]
---

# BUG-064: `usage.missing_root` отдаёт exit 3 вместо обещанных 2

| Поле | Значение |
|---|---|
| Bug ID | BUG-064 |
| Компонент | cli |
| Обнаружено | 2026-11-28 — аудит остатка CLI, R-H |
| Окружение | todoc 0.1.0, Python 3.14.4, Ubuntu (WSL) |

## Сводка

Команда без `--root` и без `TODOC_ROOT` завершалась кодом 3 (`validation`), хотя
`usage.missing_root` относится к группе `usage.*` и документация обещает код 2.
Скрипт, различающий usage-ошибки по коду выхода, принимал отсутствие корня за
ошибку данных.

## Шаги воспроизведения

1. `env -u TODOC_ROOT env PYTHONPATH=src python3 -m todoc check`
2. Посмотреть код выхода процесса.

## Ожидаемое поведение

Exit 2, как в `docs/installation.md:145` и таблице кодов `src/todoc/errors.py`
(`usage.*` → usage error). Диагностика остаётся `usage.missing_root` с guidance.

## Фактическое поведение

До исправления `service.resolve_roots` бросал `ValidationError`, который даёт
exit 3. Конверт и код диагностики были верными, расходился только код выхода.

## Доказательства

До: `rc=3`. После исправления:

```
$ env -u TODOC_ROOT env PYTHONPATH=src python3 -m todoc check >/dev/null 2>&1; echo rc=$?
rc=2
```

Диагностика остаётся прежней: `{"code": "usage.missing_root", "severity": "error"}`
с подсказкой «Передайте --root с путём к датасету».

## Воздействие

`minor`/`friction`: агент или скрипт, ветвящийся по коду выхода, неверно
классифицировал отсутствие корня и тратил лишний вызов на уточнение. Обхода два:
проверять `diagnostics[].code` вместо кода выхода или явно передавать `--root`.

## Предложение по исправлению

`resolve_roots` бросает `TodocError(..., EXIT_USAGE, "usage.missing_root")`;
`TODOC_ROOT` только из разделителей трактуется как отсутствующий. Тесты
`tests/cli/test_cli.py::test_missing_root` и
`tests/cli/test_unified_failures.py::test_separators_only_todoc_root_is_missing`
фиксируют exit 2.

## Заметки

- 2026-11-28: `fixed` — коммит `e7ee441`. Решение D1 плана
  `plan/open-bug-backlog-closure.md` (exit 2). Проверка: `check` без root → `rc=2`;
  профильные тесты зелёные.
