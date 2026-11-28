---
id: doc:bugs/bug-043-docs-read-line-range-out-of-bounds.md
title: "BUG-043: docs read --line-range вне файла возвращает пустой успех"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
bug_id: BUG-043
status: fixed
severity: minor
agent_impact: friction
tokens_extra_est: 500
component: cli
found: 2026-11-28
tags: [bugs, bug-report, cli, docs, read, line-range, validation]
---

# BUG-043: docs read --line-range вне файла возвращает пустой успех

| Поле | Значение |
|---|---|
| Bug ID | BUG-043 |
| Компонент | cli (`docs read --line-range`) |
| Обнаружено | 2026-11-28 — аудит границ чтения |
| Окружение | todoc 0.1.0 (5e86eb7 + рабочее дерево), Python 3.14.3, Windows 11 + WSL2 Ubuntu |

## Сводка

`docs read --line-range 9999-10000` на документе короче 9999 строк возвращает
`ok: true`, `lines: []`, `text: ""` без `truncated`, `line_total` или ошибки.
Агент не может отличить «в файле нет таких строк» от «файл пуст/не прочитан»,
хотя диапазон заведомо вне документа.

## Шаги воспроизведения

1. `todoc docs read --root demo --id doc:ideas/action-logging.md --line-range 9999-10000 --output json`
2. Контроль с валидным диапазоном:
   `todoc docs read --root demo --id doc:ideas/action-logging.md --line-range 1-5 --output json`
3. Сравнить `ok`, `lines`, `text`, наличие `truncated`.

## Ожидаемое поведение

Диапазон за пределами файла — ошибка вызова (`usage.line_range_out_of_bounds`
или `docs.line_range_out_of_bounds`) с указанием `line_total`, либо пустой
ответ с явными `line_start`/`line_end`/`line_total` и `truncated: true`.
Контракт bounded-read требует объявлять неполноту/отсутствие данных, а не
возвращать неотличимый пустой успех (P7).

## Фактическое поведение

- `docs_read` для `line_range` парсит `N-M` (`_parse_line_range` проверяет
  только `N >= 1`, `M >= N`) и делает `lines[start - 1:end]`
  (`src/todoc/cli.py:1356-1360`).
- Python-срез за концом списка даёт `[]`; `data["lines"] = []`,
  `data["text"] = ""`, никаких метаданных о полном размере нет.
- `truncated` в этой ветке не выставляется вообще; `line_total`/`line_start`
  отсутствуют.

## Доказательства

```
$ todoc docs read --root demo --id doc:ideas/action-logging.md --line-range 9999-10000 --output json
  "ok": true,
    "lines": [],
    "text": "",

$ todoc docs read --root demo --id doc:ideas/action-logging.md --line-range 1-5 --output json
  "ok": true,
    "lines": ["---", "id: doc:ideas/action-logging.md", ...],
```

Код: `src/todoc/cli.py:1356-1360`.

## Воздействие

- `friction`: агент получает пустой успех и вынужден повторно читать документ
  целиком/через `--section`, чтобы понять, что диапазон неверный.
- Нет `line_total` — нельзя скорректировать диапазон без полного чтения.
- Цена эпизода: 1–2 повторных вызова ≈ 500 токенов.

## Предложение по исправлению

1. Сравнивать `start`/`end` с `len(lines)`; при `start > len(lines)` —
   `ValidationError("docs.line_range_out_of_bounds")` с `line_total`.
2. В успешном ответе всегда отдавать `line_start`, `line_end`, `line_total`
   и `truncated` (обрезано ли справа).
3. Тест: `9999-10000` → exit 3 и `line_total`; `1-5` — без изменений.

## Заметки

Поиск перед созданием (2026-11-28): `docs search --type bug-report --query
"docs read line-range"` — совпадений по границам диапазона нет (BUG-018 —
бюджет полного чтения, BUG-005 — бюджет секции). Связанные: BUG-018,
BUG-040 (skills read range).

Исправление (2026-11-28, рабочее дерево): `docs read` и `skills read`
отклоняют начало `--line-range` за концом файла с `usage.invalid_line_range`;
диапазон с допустимым началом и концом за EOF обрезается. Успешный
Markdown-ответ с `--line-range` теперь содержит `line_total`, поэтому диапазон
можно скорректировать без полного чтения. Тесты: `tests/cli/test_cli_extra.py`,
`tests/cli/test_unified_failures.py`. Коммит не создан; после коммита статус
меняется на `fixed` с его ссылкой.

- 2026-11-28: `fixed` — коммит `7d32813`. Начало `--line-range` за концом файла даёт `usage.invalid_line_range` с `line_total`. Тест: `tests/cli/test_cli_extra.py::test_docs_read_line_range`.
