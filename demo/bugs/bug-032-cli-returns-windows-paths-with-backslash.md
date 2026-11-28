---
id: doc:bugs/bug-032-cli-returns-windows-paths-with-backslash.md
title: "BUG-032: CLI возвращает Windows-пути с backslash в JSON вместо POSIX"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
bug_id: BUG-032
status: open
severity: minor
agent_impact: friction
tokens_extra_est: 800
component: cli
found: 2026-11-28
---

# BUG-032: CLI возвращает Windows-пути с backslash в JSON вместо POSIX

| Поле | Значение |
|---|---|
| Bug ID | BUG-032 |
| Компонент | cli (`src/todoc/cli.py:961`, `src/todoc/application/changes.py:164`) |
| Обнаружено | 2026-11-28 — тест `test_change_open_files_resolve_note` падает на Windows |
| Окружение | todoc 0.1.0, Python 3.14.3, Windows 11 |

## Сводка

CLI возвращает пути в JSON-выводе с нативными разделителями платформы (backslash на Windows), вместо нормализованных POSIX-путей (forward slash). Это ломает кроссплатформенные тесты и усложняет работу агентов, которые ожидают единый формат путей.

## Шаги воспроизведения

1. `python -m pytest tests/cli/test_bugfixes.py::test_change_open_files_resolve_note -v`
2. `python -m pytest tests/cli/test_cli_changes.py::test_open_reports_path_and_status -v`

Оба теста падают из-за несовпадения путей: CLI возвращает `changes\pervoe\change.json`, тест ожидает `changes/pervoe/change.json`.

## Ожидаемое поведение

Все пути в JSON-выводе CLI должны быть в POSIX формате (forward slash), независимо от платформы. Это обеспечивает:
- Кроссплатформенную совместимость тестов
- Детерминированный контракт для агентов
- Корректную работу `explain-path` и других команд, принимающих пути

## Фактическое поведение

CLI использует `Path.relative_to()` который возвращает нативный `Path` с платформенно-зависимым разделителем. На Windows это backslash.

Код в `cli.py:961`:
```python
"path": str(record_path(ctx.root, record["record_id"]).relative_to(ctx.root)),
```

Код в `changes.py:164`:
```python
str(record_path(root, change_id).relative_to(root))
```

## Доказательства

```
$ python -m pytest tests/cli/test_cli_changes.py::test_open_reports_path_and_status -v
...
AssertionError: assert 'changes\\pervoe\\change.json' == 'changes/pervoe/change.json'

$ python -m pytest tests/cli/test_bugfixes.py::test_change_open_files_resolve_note -v
...
AssertionError: ./proposal.md
```

## Воздействие

- Тесты падают на Windows, ломает CI.
- Агенты, парсящие JSON, получают неожиданные пути и должны нормализовывать их сами.
- `severity: minor` — функциональность работает, но контракт API нарушен.
- `agent_impact: friction` — требует обходных путей в тестах и агентах.

## Предложение по исправлению

Нормализовать все пути к POSIX при выводе в JSON. В `cli.py` и `changes.py` использовать `.as_posix()` вместо `str()`:

```python
# cli.py:961
"path": record_path(ctx.root, record["record_id"]).relative_to(ctx.root).as_posix(),

# changes.py:164
record_path(root, change_id).relative_to(root).as_posix()
```

Также проверить другие места в CLI, где пути возвращаются в JSON (например, `docs_read`, `records_create`, `index_status` и др.).

Проверка: после фикса оба теста проходят на Windows и Linux.

## Заметки

- Дублирует по сути BUG-031 (тест падает из-за того же корневого причины).
- BUG-031 — про конкретный тест, BUG-032 — про общий контракт CLI.
- Связан с BUG-028 (Windows runtime контракт) — нормализация путей часть кроссплатформенного контракта.
- Поиск перед созданием: `--type bug-report --query path` → BUG-006/010/012, `--query windows` → BUG-017/018/019/020/028/031, `--query separator` → 0.