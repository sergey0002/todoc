---
id: doc:bugs/bug-033-history-revert-line-endings-windows.md
title: "BUG-033: History revert не сохраняет line endings (CRLF на Windows)"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
bug_id: BUG-033
status: open
severity: major
agent_impact: friction
tokens_extra_est: 1000
component: engine
found: 2026-11-28
---

# BUG-033: History revert не сохраняет line endings (CRLF на Windows)

| Поле | Значение |
|---|---|
| Bug ID | BUG-033 |
| Компонент | engine (`src/todoc/application/history.py:359-367`, `src/todoc/adapters/filesystem/scanner.py:atomic_write`) |
| Обнаружено | 2026-11-28 — тест `test_revert_plan_and_byte_exact_restore` падает на Windows |
| Окружение | todoc 0.1.0, Python 3.14.3, Windows 11 |

## Сводка

При откате файла через `history revert` (или `revert_plan` + ручная запись) line endings не сохраняются байт-в-байт. На Windows исходный файл имеет CRLF (`\r\n`), но после revert получает смешанные окончания строк (`\r\r\n` или `\n`). Тест `test_revert_plan_and_byte_exact_restore` проверяет байт-в-байт точность восстановления и падает.

## Шаги воспроизведения

1. `python -m pytest tests/unit/test_history.py::test_revert_plan_and_byte_exact_restore -v`

## Ожидаемое поведение

`revert_plan` должен возвращать содержимое файла **байт-в-байт** идентичным снимку «до» (как обещает название теста `byte_exact_restore`). Line endings должны сохраняться: если файл был CRLF, восстановленный файл должен быть CRLF; если LF — то LF.

## Фактическое поведение

```
AssertionError: assert b'---\r\r\nti...\xb0 20\r\r\n' == b'---\r\ntitl...d0\xb0 20\r\n'
  At index 4 diff: b'\r' != b'\n'
```

Восстановленный файл имеет `\r\r\n` (двойной CR) вместо оригинального `\r\n`.

## Доказательства

Тест: `tests/unit/test_history.py:189`
Код revert: `src/todoc/application/history.py:359-367` (`revert_plan` -> `before_content` -> `objects.read_snapshot`)
Запись: `src/todoc/adapters/filesystem/scanner.py:atomic_write`

Проблема: `before_content` возвращает байты из снапшота, но при записи через `doc.write_text(plan["content"], encoding="utf-8")` в тесте (или через `atomic_write` в продакшене) line endings могут нормализоваться.

В `atomic_write` используется `fh.write(content)` где `content` — строка. На Windows `open(..., "w")` без `newline=""` конвертирует `\n` в `\r\n`. Но если в снапшоте уже есть `\r\n`, получается двойное кодирование.

## Воздействие

- Нарушается контракт "byte-exact restore" для истории.
- Файлы после revert меняют line endings, что создает шум в git diff.
- 10 тестов истории падают на Windows (line endings + file locking).
- `severity: major` — неверные результаты (байт-в-байт восстановление не работает).
- `agent_impact: friction` — тесты не проходят, CI ломается на Windows.

## Предложение по исправлению

Вариант 1: В `atomic_write` открывать файл с `newline=""` (нет конвертации line endings) и писать байты напрямую:
```python
def atomic_write(path: Path, content: str) -> None:
    # content должен быть уже в правильных line endings
    with open(tmp_path, "w", encoding="utf-8", newline="") as fh:
        fh.write(content)
```

Вариант 2: В `revert_plan` / `before_content` возвращать строку с нормализованными `\n`, а при записи всегда использовать `\n` (POSIX style), и договариваться, что line endings в снапшоте хранятся как `\n`.

Вариант 1 лучше — сохраняет исходные line endings пользователя.

Также нужно проверить `objects.write_snapshot` — он должен сохранять байты как есть (уже делает, пишет `before` байты).

Проверка: после фикса `test_revert_plan_and_byte_exact_restore` проходит на Windows.

## Заметки

- 10 тестов истории падают на Windows, большинство из-за line endings.
- Связан с BUG-028 (Windows runtime контракт).
- Поиск перед созданием: `--type bug-report --query history` → BUG-012 (git status), BUG-026 (doctor), `--query revert` → 0, `--query line` → BUG-004/005/018.
- `objects.py` уже работает с байтами корректно — проблема в `atomic_write` / текстовой записи.