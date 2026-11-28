---
id: doc:bugs/bug-067-stale-ack-line-endings.md
title: "BUG-067: stale --ack перезаписывает CRLF и завершающий newline тела"
doc_type: bug-report
lang: ru
status: fixed
severity: major
component: engine
agent_impact: friction
created: 2026-11-28
updated: 2026-11-28
tags: [bugs, bug-report, staleness, ack, line-endings]
---

# BUG-067: `stale --ack` перезаписывает CRLF и завершающий newline тела

| Поле | Значение |
|---|---|
| Bug ID | BUG-067 |
| Компонент | engine (`application/staleness.py::plan_ack`) |
| Обнаружено | 2026-11-28 — аудит остатка CLI, R-D |
| Окружение | todoc 0.1.0, Python 3.14.4, Ubuntu (WSL) |

## Сводка

`plan_ack` читал документ через `read_text` (универсальные переводы строк) и
собирал тело через `"\n".join(...)`. Любое подтверждение переводило весь файл
на LF и добавляло завершающий newline, даже если его не было.

## Шаги воспроизведения

1. Документ с CRLF и якорем `derived_from`, у которого изменился источник.
2. `env PYTHONPATH=src python3 -m todoc --root <root> stale --ack docs/state/10-testing.md --reason x --apply`
3. Сравнить байты тела до и после.

## Ожидаемое поведение

Меняется только блок front matter; тело сохраняет байты, переводы строк и
отсутствие/наличие завершающего newline.

## Фактическое поведение

До исправления тело переписывалось на LF, а завершающий newline добавлялся.

## Доказательства

После исправления:

```
$ # тело до: b"# Body\r\n\r\nline\r\n"
$ # тело после: b"# Body\r\n\r\nline\r\n"
```

Тесты: `tests/unit/test_staleness.py::test_plan_ack_preserves_crlf_and_trailing_newline`,
`test_plan_ack_keeps_no_trailing_newline`,
`tests/cli/test_cli_stale.py::test_stale_ack_preserves_crlf_body_bytes`
(проверяет `applied: true` и побайтовое тело).

## Воздействие

`major`/`friction`: подтверждение устаревания незаметно переписывало файл
целиком, создавая шум в истории и конфликты с CRLF-репозиториями. Тот же класс
дефекта, что BUG-033, но другой код-путь (`stale --ack`, не `history revert`).

## Предложение по исправлению

`plan_ack` читает байты, сохраняет исходный разделитель строк front matter и
присоединяет тело без изменений; `lines[0]` определяет CRLF или LF.

## Заметки

- 2026-11-28: `fixed` — коммит `fe0efbd`. Связанные: BUG-033 (revert),
  BUG-066 (граница derived_from).
