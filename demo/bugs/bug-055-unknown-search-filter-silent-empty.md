---
id: doc:bugs/bug-055-unknown-search-filter-silent-empty.md
title: "BUG-055: Неизвестный --type/--within в docs search даёт тихий пустой результат"
doc_type: bug-report
lang: ru
bug_id: BUG-055
status: fixed
severity: major
agent_impact: friction
tokens_extra_est: 3000
created: 2026-11-28
updated: 2026-11-28
---

# BUG-055: Неизвестный `--type`/`--within` в `docs search` даёт тихий пустой результат

| Поле | Значение |
|---|---|
| Bug ID | BUG-055 |
| Компонент | cli |
| Обнаружено | 2026-11-28 — сессия по идее `archive` (проверка фильтров поиска) |
| Окружение | todoc 0.1.0, Python 3.14, WSL Ubuntu (Windows 11) |

## Сводка

`docs search` не валидирует значения `--type` и `--within`: неизвестный `doc_type` или путь вне датасета возвращают `ok: true, total: 0` без единой диагностики. Агент не может отличить «совпадений нет» от опечатки в фильтре и делает вывод, что знания в датасете отсутствуют.

## Шаги воспроизведения

1. `PYTHONPATH=src python3 -m todoc docs search --root demo --query "archive" --type no-such-type --limit 1 --output json`
2. `PYTHONPATH=src python3 -m todoc docs search --root demo --query "archive" --within no/such/dir --limit 1 --output json`
3. Для контраста — валидный тип: `… --type bug-report` → `total: 76`.

## Ожидаемое поведение

1. Неизвестный `--type` — ошибка уровня `usage`/`types.unknown` с подсказкой ближайшего типа или списком известных (`types list`), как это уже делает `docs new` для `--type` (`src/todoc/cli.py:1204`–`:1206`, код `types.unknown`).
2. `--within` с несуществующим путём — диагностика `usage.path_not_found` (аналогично `explain.path_not_found`), а не пустая выдача.
3. Если поддержка OR (`--type "a|b"`) не заявлена — значение с `|` должно отклоняться явной ошибкой, а не молча сравниваться как литерал.

## Фактическое поведение

1. `--type no-such-type` → `{"ok": true, "total": 0, "items": [], "diagnostics": []}`.
2. `--within no/such/dir` → то же самое: `ok: true`, `total: 0`, диагностик нет.
3. `--type "idea|bug-report"` и `--within "ideas|plan"` → `total: 0` без диагностики (значение сравнивается как строка).
4. Повторный флаг перекрывает предыдущий (last wins): `--within ideas` = 3, `--within plan` = 7, `--within ideas --within plan` = 7.

## Доказательства

```
$ todoc docs search --root demo --query "archive" --type no-such-type --limit 1 --output json
{
  "schema_version": 1,
  "ok": true,
  "data": {"dataset_id": "dataset-80c70868", "total": 0, "returned": 0,
           "truncated": false, "cursor": null, "items": []},
  "diagnostics": [],
  "next_actions": []
}

$ todoc docs search --root demo --query "archive" --within no/such/dir --limit 1 --output json
{"ok": true, "data": {"total": 0, "returned": 0, "items": []}, "diagnostics": []}
```

Код: сравнение без проверки реестра — `src/todoc/application/search.py:147` (`doc.get("doc_type") != doc_type`) и `:149`–`:152` (префикс пути); опции объявлены без валидации — `src/todoc/cli.py:1258` (`--type`) и `:1262` (`--within`).

## Воздействие

Агент задаёт уточняющий фильтр (например, `--type bug-report` при поиске дубликата репорта) и получает пустую выдачу. Без диагностики это читается как «таких документов нет», после чего агент создаёт дубль или отвечает пользователю «не найдено» — неверный результат. Обход: ручная сверка с `types list` и повторный вызов (в этой сессии потребовалось 3 дополнительных вызова: проверка `--type`, `--within`, сравнение с валидным типом), ~3k токенов.

## Предложение по исправлению

1. В `docs_search` (и общий слой для `docs tree`/`records list`) валидировать `--type` против `ctx.registry_types.doc_types`, `--within` — против существующих папок индекса; неизвестное значение — `ValidationError` с кодом `usage.unknown_value`/`usage.path_not_found` и `suggested_fixes`.
2. Либо реализовать `|`-списки с OR-семантикой (см. идею [archive-dir-type](../ideas/archive-dir-type.md)), либо явно отклонять `|` как неподдерживаемый синтаксис.
3. Повторный флаг: оставить last wins для совместимости или отклонять как `usage.conflicting_filters` — зафиксировать в справке.
4. Тесты: неизвестный тип, путь вне датасета, `|`-значение, повтор флага; проверить, что валидные фильтры не меняют выдачу.

## Заметки

- Связано с идеей [«Тип папки `archive` и семантика поиска по архиву»](../ideas/archive-dir-type.md) — там же предложены `--dir-type`/`--scope` и общий парсер `|`-фильтров.
- Пересечение по теме: BUG-022 (обзор знаний одним запросом), BUG-054 (дрейф справки поиска).
- Закрытие: смена `status` во front matter с датой и коммитом.

- 2026-11-28: `fixed` — коммит `9895249`. `docs search` отклоняет неизвестный `--type` (`docs.unknown_type`) и несуществующую папку в `--within` (`usage.path_not_found`, exit 2); существующая папка без совпадений остаётся чистым пустым результатом, OR и повторяемые `--type` сохранены. Проверка: `tools/bug_acceptance.py --only BUG-055` → `fixed`. Тесты: `tests/cli/test_unified_docs.py::test_search_rejects_unknown_type_and_missing_scope`, `test_search_keeps_or_and_repeated_type_flags`.
