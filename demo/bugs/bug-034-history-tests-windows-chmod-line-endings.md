---
id: doc:bugs/bug-034-history-tests-windows-chmod-line-endings.md
title: "BUG-034: Тесты истории падают на Windows из-за chmod и line endings"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
tags: [bugs, bug-report, history, tests]
bug_id: BUG-034
status: open
severity: minor
agent_impact: friction
tokens_extra_est: 1200
component: tests
found: 2026-11-28
---

# BUG-034: Тесты истории падают на Windows из-за chmod и line endings

| Поле | Значение |
|---|---|
| Bug ID | BUG-034 |
| Компонент | tests (`tests/unit/test_history.py`: 10 тестов) |
| Обнаружено | 2026-11-28 — запуск `python -m pytest tests/unit/test_history.py` на Windows |
| Окружение | todoc 0.1.0, Python 3.14.3, Windows 11 |

## Сводка

10 тестов в `tests/unit/test_history.py` падают на Windows из-за двух классов проблем:
1. **chmod не работает на Windows** (4 теста): `chmod(0)` не делает файл нечитаемым, `chmod(0o555)` не предотвращает удаление.
2. **Line endings CRLF vs LF** (6 тестов): Git и файловые операции на Windows возвращают CRLF, тесты ожидают LF.

## Шаги воспроизведения

```bash
python -m pytest tests/unit/test_history.py -v
```

## Падающие тесты

### chmod проблемы:
1. `test_content_at_unreadable_file` (line 522) — `chmod(0)` не блокирует чтение на Windows
2. `test_remove_object_survives_locked_directory` (line 697) — `chmod(0o555)` не блокирует удаление
3. `test_trim_objects_survives_locked_directory` (line 709) — то же
4. `test_trim_objects_reports_locked_orphan` (line 832) — то же

### Line endings проблемы:
5. `test_revert_plan_and_byte_exact_restore` (line 189) — см. BUG-033
6. `test_git_backend_read_at` (line 455) — `git show` возвращает CRLF
7. `test_content_at_falls_back_to_git` (line 535) — то же
8. `test_before_content_falls_back_to_git` (line 543) — то же
9. `test_section_bounds_on_unreadable_file` (line 607) — связано с chmod
10. `test_events_bytes_matches_journal_on_disk` (line 936) — журнал на диске с CRLF, расчёт с LF

## Ожидаемое поведение

Тесты должны проходить на всех платформах. Либо тесты должны быть адаптированы под Windows (пропускать chmod-тесты, нормализовать line endings), либо код должен обрабатывать кроссплатформенные различия.

## Фактическое поведение

10 тестов падают с `AssertionError` из-за несовпадения байтов или того, что chmod не работает.

## Доказательства

```
FAILED tests/unit/test_history.py::test_content_at_unreadable_file - AssertionError: assert (b'...' is None)
FAILED tests/unit/test_history.py::test_remove_object_survives_locked_directory - AssertionError: assert 0 == 1
FAILED tests/unit/test_history.py::test_trim_objects_survives_locked_directory - AssertionError: assert 0 >= 1
FAILED tests/unit/test_history.py::test_trim_objects_reports_locked_orphan - AssertionError: assert 0 >= 1
FAILED tests/unit/test_history.py::test_revert_plan_and_byte_exact_restore - diff: b'\r' != b'\n'
FAILED tests/unit/test_history.py::test_git_backend_read_at - diff: b'\r' != b'\n'
FAILED tests/unit/test_history.py::test_content_at_falls_back_to_git - diff: b'\r' != b'\n'
FAILED tests/unit/test_history.py::test_before_content_falls_back_to_git - diff: b'\r' != b'\n'
FAILED tests/unit/test_history.py::test_section_bounds_on_unreadable_file - AssertionError: assert (1, 1) is None
FAILED tests/unit/test_history.py::test_events_bytes_matches_journal_on_disk - AssertionError: assert 686 == 688
```

## Воздействие

- CI на Windows ломается.
- Агент не может использовать `pytest` для верификации изменений истории на Windows.
- `severity: minor` — только тесты, функциональность работает (кроме BUG-033).
- `agent_impact: friction` — требует обходных путей (WSL, пропуск тестов).

## Предложение по исправлению

### Для chmod тестов:
Добавить `@pytest.mark.skipif(sys.platform == "win32", reason="chmod doesn't work on Windows")` к 4 тестам, или использовать `os.access` / `pathlib.Path.is_file()` проверки вместо chmod.

### Для line endings:
1. В `journal.events_bytes` считать байты с CRLF на Windows (открывать файл в бинарном режиме и считать реальный размер).
2. В git backend тестах нормализовать line endings к LF перед сравнением: `.replace(b'\r\n', b'\n')`.
3. В `atomic_write` (BUG-033) исправить сохранение line endings.

Проверка: после фикса все тесты истории проходят на Windows и Linux.

## Заметки

- Пересекается с BUG-033 (history revert line endings) — корневая причина одна.
- Связан с BUG-028 (Windows runtime контракт).
- Поиск перед созданием: `--type bug-report --query history` → BUG-012/026/033, `--query test` → BUG-031, `--query windows` → BUG-017/018/019/020/028/031/032/033.
- 10 из 111 тестов истории падают на Windows (~9%).
