---
id: doc:bugs/bug-030-unicode-encode-error-windows-stdout.md
title: "BUG-030: UnicodeEncodeError на Windows при выводе JSON/table с не-ASCII символами"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
bug_id: BUG-030
status: open
severity: major
agent_impact: [friction, token_overrun]
tokens_extra_est: 1500
component: cli
found: 2026-11-28
---

# BUG-030: UnicodeEncodeError на Windows при выводе JSON/table с не-ASCII символами

| Поле | Значение |
|---|---|
| Bug ID | BUG-030 |
| Компонент | cli (`src/todoc/output/envelope.py:43,60`, `src/todoc/cli.py:61`) |
| Обнаружено | 2026-11-28 — сессия из Windows PowerShell 5.1, рабочая папка UNC-путь `\\wsl.localhost\Ubuntu\home\newuser\projects\todoc` |
| Окружение | todoc 0.1.0, Python 3.14.3, Windows 11 + WSL2 Ubuntu |

## Сводка

CLI падает с `UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'` при выводе JSON или table режима, если в данных есть не-ASCII символы (кириллица, стрелки → и др.). На Windows `sys.stdout` использует кодировку `cp1251`, которая не поддерживает большинство Unicode символов. JSON-режим падает в `envelope.py:43`, table/markdown — в `envelope.py:60`.

## Шаги воспроизведения

1. `python -m todoc docs search --root demo --type bug-report --query "баг" --limit 5`
2. `python -m todoc docs search --root demo --type bug-report --query "баг" --limit 5 --output table`
3. `python -m todoc docs read --root demo --id doc:bug-019-docs-search-empty-query.md --output json`

Все три команды падают с `UnicodeEncodeError` в `envelope.py` при попытке записи в `sys.stdout`.

## Ожидаемое поведение

CLI должен корректно выводить Unicode в stdout на Windows. Согласно контракту (BUG-028, BUG-026), stdout должен быть в UTF-8. Возможные решения:
- Принудительно установить `sys.stdout.reconfigure(encoding="utf-8")` на старте CLI (Python 3.7+)
- Использовать `sys.stdout.buffer.write(text.encode("utf-8"))` вместо `sys.stdout.write(text)`
- Обернуть stdout в `io.TextIOWrapper` с UTF-8

## Фактическое поведение

```
UnicodeEncodeError: 'charmap' codec can't encode character '\u2192' in position 2817: character maps to <undefined>
  File "...\todoc\output\envelope.py", line 43, in emit
    sys.stdout.write(text + "\n")
```

Ошибка воспроизводится детерминированно для любых данных с не-ASCII символами в режимах `json` и `table`/`markdown`.

## Доказательства

```
$ python -m todoc docs search --root demo --type bug-report --query "баг" --limit 5
Traceback (most recent call last):
  ...
  File "...\todoc\output\envelope.py", line 43, in emit
    sys.stdout.write(text + "\n")
  File "C:\Python314\Lib\encodings\cp1251.py", line 19, in encode
    return codecs.charmap_encode(input,self.errors,encoding_table)[0]
UnicodeEncodeError: 'charmap' codec can't encode character '\u2192' in position 2817: character maps to <undefined>

$ python -m todoc docs search --root demo --type bug-report --query "баг" --limit 5 --output table
Traceback (most recent call last):
  ...
  File "...\todoc\output\envelope.py", line 60, in emit
    sys.stdout.write(text)
  File "C:\Python314\Lib\encodings\cp1251.py", line 19, in encode
    return codecs.charmap_encode(input,self.errors,encoding_table)[0]
UnicodeEncodeError: 'charmap' codec can't encode character '\u2192' в position 2015: character maps to <undefined>
```

Код: `src/todoc/output/envelope.py:43` (JSON), `src/todoc/output/envelope.py:60` (table/markdown).

## Воздействие

- Агент не может использовать CLI в Windows напрямую — каждый вызов с не-ASCII данными падает.
- Приходится обходить через WSL (`wsl -e bash -lc "..."`) или перенаправление в файл (`--out`), что требует дополнительных вызовов и чтений (~1.5k токенов за эпизод).
- Нарушает контракт CLI как agent-first инструмента: агент не может полагаться на stdout JSON.
- `severity: major` — неверные результаты (падение вместо данных), обход системы обязателен.

## Предложение по исправлению

В `src/todoc/__main__.py` или в начале `cli.py` добавить переконфигурацию stdout на UTF-8:

```python
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="surrogateescape")
else:
    # Python < 3.7 fallback
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="surrogateescape")
```

Альтернатива — в `envelope.py:emit` использовать `sys.stdout.buffer.write(text.encode("utf-8"))` для JSON и аналогично для human modes. Это надёжнее, так как не зависит от глобального состояния stdout.

Проверка: после фикса все три команды из «Шаги воспроизведения» должны отдавать корректный JSON/table без ошибок.

## Заметки

- Пересекается с BUG-028 (runtime-контракт Windows/WSL) и BUG-026 (doctor не проверяет кодировку stdout).
- Связан с BUG-023 (CLI недоступен из харнесса без venv/entrypoint) — фикс кодировки нужен для работы entrypoint.
- Не затрагивает `--out` (файл пишется в UTF-8 корректно, см. `envelope.py:40-41`).
- Поиск перед созданием: `--type bug-report --query unicode` → BUG-010 (unicode-escape в location), `--query stdout` → BUG-013/026/028, `--query charmap` → 0.