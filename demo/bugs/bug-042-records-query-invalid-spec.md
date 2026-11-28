---
id: doc:bugs/bug-042-records-query-invalid-spec.md
title: "BUG-042: records query падает traceback на некорректном QuerySpec"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
bug_id: BUG-042
status: fixed
severity: major
agent_impact: friction
tokens_extra_est: 700
component: cli
found: 2026-11-28
tags: [bugs, bug-report, cli, records, query, validation, p11]
---

# BUG-042: records query падает traceback на некорректном QuerySpec

| Поле | Значение |
|---|---|
| Bug ID | BUG-042 |
| Компонент | cli (`records query`, `application/query.py`) |
| Обнаружено | 2026-11-28 — аудит устойчивости декларативных запросов |
| Окружение | todoc 0.1.0 (5e86eb7 + рабочее дерево), Python 3.14.3, Windows 11 + WSL2 Ubuntu |

## Сводка

`records query` не валидирует содержимое QuerySpec: `"limit": "abc"` роняет
команду `ValueError`, а фильтр с несовместимым типом (`{"title": {"$gte": 5}}`)
роняет `TypeError` из `_matches`. Вместо error-envelope с `ok: false` агент
получает Python-traceback; это нарушает P11 («ошибки не должны быть
трейсбеками интерпретатора»).

## Шаги воспроизведения

1. Создать `bad-limit.json`: `{"entity_type": "term", "limit": "abc"}`
2. `todoc records query --root demo --query-file bad-limit.json --output json`
3. Создать `bad-filter.json`: `{"entity_type": "term", "filters": {"title": {"$gte": 5}}}`
4. `todoc records query --root demo --query-file bad-filter.json --output json`

## Ожидаемое поведение

QuerySpec — входной контракт: `limit` обязан быть неотрицательным целым,
`filters` — объектом с поддерживаемыми операторами (`$in`, `$gte`, `$lte`) и
сравнимыми типами. Некорректный spec — `validation.error`/`query.invalid_file`
с указанием поля, без traceback. Для чтения файла — общий `parse_json`
(BOM, дубликаты ключей), как у остальных входов.

## Фактическое поведение

- `records_query` делает `int(spec.get("limit", 200))` без проверки:
  `src/todoc/cli.py:1886-1889` → `ValueError` для `"abc"`.
- `_matches` сравнивает `actual >= expected["$gte"]` без проверки типов:
  `src/todoc/application/query.py:28-31` → `TypeError` для строки и числа.
- `spec` читается `json.loads(Path(...).read_text("utf-8"))`
  (`src/todoc/cli.py:1882-1885`), поэтому UTF-8 BOM отвергается как
  `query.invalid_file`, хотя `parse_json` BOM снимает.
- Ни один из случаев не превращается в конверт: traceback уходит в stderr,
  exit code — 1 от интерпретатора, `ok: false` в stdout отсутствует.

## Доказательства

```
$ todoc records query --root demo --query-file bad-limit.json --output json
  File "...\src\todoc\cli.py", line 1888, in records_query
    spec.get("filters"), int(spec.get("limit", 200)),
ValueError: invalid literal for int() with base 10: 'abc'

$ todoc records query --root demo --query-file bad-filter.json --output json
  File "...\src\todoc\application\query.py", line 28, in _matches
    if "$gte" in expected and not (actual is not None and actual >= expected["$gte"]):
TypeError: '>=' not supported between instances of 'str' and 'int'
```

Код: `src/todoc/cli.py:1886-1889`, `src/todoc/application/query.py:21-34`.

## Воздействие

- `major`: входной файл (данные, а не код) может уронить CLI; для агента это
  потеря машинно-читаемого результата и необходимость разбирать traceback.
- Ошибка типа в фильтре не отличается от «нет совпадений»: без traceback агент
  мог бы принять пустой результат за правду.
- `friction`: 1–2 повторных вызова + чтение кода ≈ 700 токенов.

## Предложение по исправлению

1. Валидировать QuerySpec: `limit` — целое ≥ 0; `filters` — объект; операторы —
   из белого списка; типы значений сравнимы с полем (или явно приводить даты).
2. `_matches` при несравнимых типах возвращать `False` и диагностику
   `query.filter_type_mismatch`, а не исключение.
3. Читать query-file через `parse_json` (BOM, duplicate keys) и сообщать
   `query.invalid_file` с позицией.
4. Тест: `limit: "abc"` → exit 3/2 и `ok: false`; `$gte` на строке → диагностика
   без traceback; BOM-файл читается.

## Заметки

Поиск перед созданием (2026-11-28): `docs search --type bug-report --query
"records query invalid"` — найден только BUG-016 (фильтры не документированы),
другой корень. Связанные: BUG-016 (документация фильтров), BUG-041
(пост-лимитные фильтры).

Исправление (2026-11-28, рабочее дерево): QuerySpec проверяется до чтения
индекса. Принимаются `schema_version: 1`, `name`, `entity_type`, `filters`,
`limit` и `sort_hint`; неизвестные ключи, операторы, версия и неверные типы
дают `query.invalid_file` без traceback. Несравнимые операнды по-прежнему
превращаются в `query.invalid_file`, а не в исключение. Файл читается через
`parse_json`, поэтому BOM снимается. Тесты: `tests/cli/test_unified_failures.py`.
Коммит не создан; после коммита статус меняется на `fixed` с его ссылкой.

- 2026-11-28: `fixed` — коммит `7d32813`. QuerySpec валидируется до чтения индекса; невалидная спецификация даёт `query.invalid_file` без traceback. Тест: `tests/cli/test_unified_failures.py::test_invalid_query_spec_is_rejected_before_index_read`.
