---
id: doc:bugs/bug-019-docs-search-empty-query.md
title: "BUG-019: docs search с пустым --query возвращает ok:true и total 0"
doc_type: bug-report
lang: ru
bug_id: BUG-019
status: fixed
severity: minor
agent_impact: friction
tokens_extra_est: 1000
component: cli
found: 2026-11-28
created: 2026-11-27
updated: 2026-11-28
tags: [bugs, bug-report, cli, search, validation, empty-query]
---

# BUG-019: docs search с пустым --query возвращает ok:true и total 0

| Поле | Значение |
|---|---|
| Bug ID | BUG-019 |
| Компонент | cli (`docs search`) |
| Обнаружено | 2026-11-28 — попытка выбрать все документы типа без текстового запроса |
| Окружение | todoc 0.1.0 (5e86eb7), Python 3.14.4, Windows 11 + WSL2 Ubuntu |

## Сводка

`docs search --query ""` (и строка из пробелов) возвращает `ok: true`,
`total: 0`, `items: []` без диагностики. Тот же пустой ввод в `docs suggest`
даёт `usage.error`, то есть валидация в CLI непоследовательна.

## Шаги воспроизведения

1. `todoc docs search --root demo --type idea --query "" --output json`
2. Контроль: `todoc docs suggest --root demo --query "" --output json`
3. Сравнить `ok`, `total` и наличие диагностик.

## Ожидаемое поведение

Пустой запрос — ошибка использования, а не успешный пустой результат.
Прецедент в этом же CLI: `docs suggest` валидирует ввод и падает
`usage.error` с сообщением «Пустой запрос: укажите --query.»
(`src/todoc/cli.py:1404-1406`). Для выбора по типу без текста должна
существовать отдельная команда/флаг (см. BUG-022), а не пустой `--query`.

## Фактическое поведение

- `docs search` не валидирует запрос: `src/todoc/cli.py:1265-1278`.
- `search_documents` при пустом наборе термов возвращает успешный пустой
  результат: `if not terms: return [], 0, False`
  (`src/todoc/application/search.py:126-128`).
- Ответ: 233 байта, `"ok": true`, `"total": 0`, `diagnostics: []`.

## Доказательства

```
$ todoc docs search --root demo --type idea --query "" --output json
233             # размер ответа
"total": 0
"ok": true
```

```python
# src/todoc/application/search.py:126-128
terms = _terms(query)
if not terms:
    return [], 0, False
```

```python
# src/todoc/cli.py:1404-1406 (docs suggest — правильное поведение)
if not q.strip():
    raise TodocError("Пустой запрос: укажите --query.", EXIT_USAGE, "usage.error")
```

## Воздействие

Агент читает `ok: true, total: 0` как «таких документов нет» и делает неверный
вывод о содержимом базы. В сессии это создало ложное впечатление, что идеи
не индексируются, и потребовало повторного запроса с другим текстом
(`--query "идея"`), то есть лишний цикл и потеря доверия к `total`.

## Предложение по исправлению

- В `docs_search` (`src/todoc/cli.py:1265`) добавить проверку
  `if not query.strip(): raise TodocError(..., "usage.empty_query")` — по образцу
  `docs_suggest`.
- В `search_documents` оставить пустой результат только для внутренних вызовов
  (например, фильтра по тегу), но не для пользовательского `--query`.
- Проверка: `docs search --query ""` → `ok: false`, `code: usage.empty_query`,
  `suggested_fixes` с примером.

## Заметки

Поиск перед созданием (2026-11-28): `--type bug-report --query "пустой query"` — совпадений нет.
Связанные: BUG-022 (отсутствие выборки по типу — истинная потребность, породившая пустой запрос),
BUG-021 (usage-ошибки без подсказок).

- 2026-11-28: `fixed` — коммит `7d32813`. Пустой `--query` даёт `usage.error`, exit 2, а не пустой успех. Проверка: `tools/bug_acceptance.py --only BUG-019`. Тест: `tests/cli/test_unified_failures.py`.
