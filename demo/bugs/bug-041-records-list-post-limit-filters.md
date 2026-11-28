---
id: doc:bugs/bug-041-records-list-post-limit-filters.md
title: "BUG-041: records list --until/--relation фильтруют после limit — total и truncated врут"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
bug_id: BUG-041
status: fixed
severity: minor
agent_impact: [friction, token_overrun]
tokens_extra_est: 1000
component: cli
found: 2026-11-28
tags: [bugs, bug-report, cli, records, filters, pagination]
---

# BUG-041: records list --until/--relation фильтруют после limit — total и truncated врут

| Поле | Значение |
|---|---|
| Bug ID | BUG-041 |
| Компонент | cli (`records list`) |
| Обнаружено | 2026-11-28 — аудит фильтров записей |
| Окружение | todoc 0.1.0 (5e86eb7 + рабочее дерево), Python 3.14.3, Windows 11 + WSL2 Ubuntu |

## Сводка

`records list` применяет `--until` и `--relation` **после** `query_records`,
то есть уже к усечённой `--limit` странице. Если подходящие записи не попали в
первые `limit`, команда возвращает `total: 0`, `truncated: false` — «совпадений
нет», хотя они есть. `--since` при этом фильтрует до среза и ведёт себя верно.

## Шаги воспроизведения

В отдельном временном датасете (чтобы не зависеть от состава демо):

1. `todoc init --root "$KB" --dataset-id audit-ds`
2. Создать три записи типа `note` с `record_id` `note:a` (date `2024-01-01`),
   `note:b` (`2020-01-01`), `note:c` (`2021-01-01`) через
   `records create --type note --apply`.
3. `todoc records list --root "$KB" --type note --limit 1 --until 2020-12-31 --output json`
4. Контроль: `todoc records list --root "$KB" --type note --output json`.

## Ожидаемое поведение

Фильтры `--until`/`--relation` — часть выборки, а не пост-обработка страницы:
они должны применяться до `limit`, а `total`/`truncated` описывать весь
отфильтрованный набор. Контракт `records list` — «список с фильтрами»
(`README.md:154`), как у `records query` (`$gte/$lte/$in`).

## Фактическое поведение

- `query_records(..., limit)` возвращает страницу и `total` по фильтру `--since`
  (`src/todoc/cli.py:1800-1803`).
- `--until` фильтрует уже полученные `items` и при непустом результате
  перезаписывает `total = len(items)` и `truncated = False`
  (`src/todoc/cli.py:1804-1812`).
- `--relation` — так же: фильтрация по странице, а не по всему набору.
- Итог: `--limit 1 --until 2020-12-31` возвращает `total: 0`, хотя `note:b`
  (date `2020-01-01`) удовлетворяет условию и находится в полном наборе.

## Доказательства

```
$ todoc records list --root "$KB" --type note --limit 1 --until 2020-12-31 --output json
    "total": 0,
    "returned": 0,
    "truncated": false,

$ todoc records list --root "$KB" --type note --output json
    "total": 3,
        "record_id": "note:a",
        "record_id": "note:b",
        "record_id": "note:c",
```

Код: `src/todoc/cli.py:1800-1812`.

## Воздействие

- `friction`: агент делает вывод «записей до 2020 нет» и пропускает данные;
  чтобы получить правду, он вынужден поднимать `--limit` до размера датасета
  и фильтровать вручную.
- `token_overrun`: обходной путь — `--limit 200` + клиентская фильтрация;
  на больших наборах это лишние килобайты ответа. Эпизод ≈ 1k токенов.
- `truncated: false` усиливает ложный вывод: агент не знает, что страница
  была усечена до фильтра.

## Предложение по исправлению

1. Перенести `--until`/`--relation` в `query_records` (или в общий слой
   фильтров) до `selected[:limit]`, чтобы `total`/`truncated` считались по
   отфильтрованному набору.
2. Либо явно документировать, что фильтры пост-страничные, и возвращать
   `truncated: true`/`filtered_out`, когда `--until` отбросил элементы страницы.
3. Тест: три записи, `--limit 1 --until 2020-12-31` → `total: 1` (note:b),
   `returned: 1`; `--relation` с целью за пределами первой страницы — находит.

## Заметки

Поиск перед созданием (2026-11-28): `docs search --type bug-report --query
"records list until limit"` — совпадений по корневой причине нет (BUG-020 —
неймспейс, BUG-016 — документация фильтров query). Связанные: BUG-039
(скрытый дефолт aggregate), BUG-041.

- 2026-11-28: `fixed` — коммит `7d32813`. Фильтры применяются до `--limit`: `total=3 returned=1`. Тест: `tests/cli/test_unified_docs.py`.
