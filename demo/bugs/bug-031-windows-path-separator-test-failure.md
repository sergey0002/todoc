---
id: doc:bugs/bug-031-windows-path-separator-test-failure.md
title: "BUG-031: Тест test_open_reports_path_and_status падает на Windows из-за разделителей путей"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
tags: [bugs, bug-report, windows, tests]
bug_id: BUG-031
status: open
severity: minor
agent_impact: friction
tokens_extra_est: 500
component: tests
found: 2026-11-28
---

# BUG-031: Тест test_open_reports_path_and_status падает на Windows из-за разделителей путей

| Поле | Значение |
|---|---|
| Bug ID | BUG-031 |
| Компонент | tests (`tests/cli/test_cli_changes.py:61`) |
| Обнаружено | 2026-11-28 — запуск `python -m pytest tests/cli/test_cli_changes.py -v` |
| Окружение | todoc 0.1.0, Python 3.14.3, Windows 11 |

## Сводка

Тест `test_open_reports_path_and_status` в `tests/cli/test_cli_changes.py:61` ожидает путь с forward slash (`changes/pervoe/change.json`), но на Windows CLI возвращает путь с backslash (`changes\pervoe\change.json`). Тест падает с `AssertionError`.

## Шаги воспроизведения

1. `python -m pytest tests/cli/test_cli_changes.py::test_open_reports_path_and_status -v`

## Ожидаемое поведение

Тест должен проходить на всех платформах. Пути в JSON-выводе CLI должны быть нормализованы к forward slash (POSIX стиль) для кроссплатформенной совместимости, либо тест должен использовать `os.path.normpath` / `Path.as_posix()` для сравнения.

## Фактическое поведение

```
FAILED tests/cli/test_cli_changes.py::test_open_reports_path_and_status - AssertionError: assert 'changes\\pervoe\\change.json' == 'changes/pervoe/change.json'
```

CLI возвращает Windows-пути с backslash, тест ожидает forward slash.

## Доказательства

```
$ python -m pytest tests/cli/test_cli_changes.py::test_open_reports_path_and_status -v
...
tests\cli\test_cli_changes.py:61: in test_open_reports_path_and_status
    assert data["path"] == "changes/pervoe/change.json"
AssertionError: assert 'changes\\pervoe\\change.json' == 'changes/pervoe/change.json'
```

Код теста: `tests/cli/test_cli_changes.py:61`
CLI код: `src/todoc/application/changes.py` (функция `open_change` / `record_path`)

## Воздействие

- Тест падает на Windows, ломает CI на Windows-раннерах.
- Агент не может использовать `pytest` для верификации изменений на Windows без обходных путей.
- `severity: minor` — только тест, функциональность работает корректно.
- `agent_impact: friction` — требует ручного запуска/проверки вместо автоматического теста.

## Предложение по исправлению

Вариант 1 (рекомендуемый): Нормализовать пути в CLI к POSIX (forward slash) в `application/changes.py` при возврате в JSON. Пути в данных должны быть платформонезависимыми.

Вариант 2: Исправить тест, используя `Path(data["path"]).as_posix() == "changes/pervoe/change.json"` или `os.path.normpath`.

Вариант 1 предпочтительнее — он фиксирует контракт CLI: пути в API всегда POSIX.

Проверка: после фикса тест проходит на Windows и Linux.

## Заметки

- Аналогичная проблема может встречаться в других тестах, сравнивающих пути.
- Поиск перед созданием: `--type bug-report --query path` → BUG-006 (cyrillic slug), BUG-010 (unicode escape location), BUG-012 (git status), `--query windows` → BUG-017/018/019/020/028, `--query separator` → 0.
- Связан с BUG-028 (Windows runtime контракт) — нормализация путей часть кроссплатформенного контракта.
