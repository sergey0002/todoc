---
title: Журнал проверок аудита todoc
date: 2026-11-28
status: completed_with_limitations
---

# Журнал проверок аудита todoc

Протокол фиксирует команды, окружение и наблюдаемые результаты, на которые
ссылаются [README аудита](../README.md), тематические исследования и
[баг-репорты](../bugfixes/README.md), а также канонические `demo/bugs/BUG-*`.

## Окружение и базовая точка

| Параметр | Значение |
|---|---|
| Хост | Windows 11 → WSL Ubuntu |
| Python | 3.14.4 |
| pytest | 9.2.0 |
| Базовая точка аудита | `5e86eb72d56e41129c8050492422927c52c900e9` |
| Текущее дерево при записи протокола | `60b9f2932f1a8717e6ee7cac00036f9b06254d84` |
| `reproduce.py` SHA-256 | `571ea729a843805a3d42a80fe29a39fe59e6f4899b76978236e2d4c63301d8f6` |

Команда воспроизведения (из корня репозитория):

~~~bash
PYTHONPATH=src python3 .doc/codexaudit/evidence/reproduce.py
~~~

Скрипт работает только во временных каталогах (`tempfile.TemporaryDirectory`)
и не изменяет рабочее дерево. Полный JSON-вывод сохранён рядом:
[`reproduce-output.json`](reproduce-output.json).

## Базовые гейты

| Проверка | Команда | Результат |
|---|---|---|
| Полный pytest | `PYTHONPATH=src .venv/bin/python -m pytest` | 1279 passed, 21 skipped, 95.75 с |
| Валидация demo | `PYTHONPATH=src .venv/bin/python -m todoc validate --root demo --all` | 0 диагностик, 476 документов на момент первого запуска |
| Проверка ссылок | `python3 tools/linkcheck.py` | 1085 ссылок, 0 битых на базовой точке |
| Wheel без сети | `python -m build --wheel --no-isolation` | успех, `todoc-0.1.0-py3-none-any.whl`, пакетный `SKILL.md` присутствует |
| Покрытие 100% | `coverage run --branch -m pytest` | не измерено: `coverage` отсутствует в доступных Python |

При повторной записи протокола в текущем дереве полный pytest был запущен
через системный `python3` (pytest 9.2.0). Наблюдается один провал
`tests/unit/test_metadata_predicates.py::test_common_schema_reports_invalid_definition_and_disables_remote_references`:
системный `jsonschema`/`referencing` разрешает удалённую ссылку и бросает
`Unresolvable: https://example.invalid/schema` вместо ожидаемого
`ValidationError`. Это расхождение версий зависимости, а не следствие правок
аудита; в окружении с зависимостями проекта тест проходит.

## Сценарии `reproduce.py`

### 1. `delta_outside_validate` / `delta_outside_apply` / `delta_outside_content`

Дельта `changes/traversal/deltas/audit.md` с `target: ../outside.md`.

| Вызов | Наблюдение |
|---|---|
| `change validate traversal` | exit 0, `applicable: true`, `errors: 0`, `warnings: 0` |
| `change apply traversal --apply` | exit 0, `applied: true`, `status: applied`, файл `../outside.md` в списке |
| содержимое `outside.md` | изменено на `Audit content.` (`outside_modified: true`) |

Воспроизводит существующий BUG-034: запись за пределы выбранного корня
проходит валидацию и применяется. Полный путь данных —
`.doc/codexaudit/04-security.md`.

### 2. `malformed_relation`

Запись `bad.json` с `relations: [{"type_id": "references", "target": "bad-target"}]`.

| Вызов | Наблюдение |
|---|---|
| `validate --all` | exit 1, конверт отсутствует, исключение `AttributeError("'str' object has no attribute 'get'")` |

Воспроизводит BUG-047: строка вместо объекта в `target` обрушивает валидацию
трассировкой вместо диагностики.

### 3. `invalid_utf8_validate` / `invalid_utf8_search`

Файл `bad.md` содержит байты `b"# bad\n\xff"`.

| Вызов | Наблюдение |
|---|---|
| `validate --all` | exit 3, `ok: false`, диагностика `file.unreadable` |
| `docs search --query bad` | exit 1, конверт отсутствует, `UnicodeDecodeError` |

Воспроизводит BUG-048: валидация сообщает о нечитаемом файле, но поиск падает
трассировкой на том же файле.

### 4. `invalid_patch_preview` / `invalid_patch_apply`

Патч `{"ops": [{"line": "not-an-integer", "text": "new"}]}`.

| Вызов | Наблюдение |
|---|---|
| `docs edit --preview` | exit 0, `ok: true`, ops повторены без проверки |
| `docs edit --apply` | exit 1, конверт отсутствует, `ValueError: invalid literal for int() ...` |

Воспроизводит BUG-049: preview одобряет неисполнимый патч, apply падает
трассировкой.

### 5. `zero_limit_search` / `zero_limit_search_again`

`docs search --query test --limit 0`, затем тот же вызов с `--cursor 0`.

| Вызов | Наблюдение |
|---|---|
| первый | exit 0, `total: 1`, `returned: 0`, `truncated: true`, `cursor: "0"` |
| повтор с `--cursor 0` | exit 0, идентичный ответ, `cursor: "0"` |

Курсор не продвигается: воспроизводит BUG-050. Позитивный контроль с
`--limit 1` и курсорами `0`/`1` возвращает обе записи и корректно завершает
пагинацию (`truncated: false`, `cursor: null`).

### 6. `csv_filter_before_limit`

`docs read --id doc:data.csv --rows 1 --where key=yes` на CSV
`key,value\nno,first\nyes,second`.

| Наблюдение | Значение |
|---|---|
| `rows` | `[{"key": "yes", "value": "second"}]` |
| `total` / `matched` / `truncated` | `2` / `1` / `false` |

Фильтр применяется до ограничения строк; поведение соответствует BUG-054.

### 7. `create_only_race`

`apply_write_plan` с `expected_hash=None`; второй писатель создаёт путь между
проверкой существования и `atomic_write` (детерминированная подмена, без
реальных параллельных процессов).

| Наблюдение | Значение |
|---|---|
| `returned` | `"unused"` |
| итоговое содержимое | `first writer\n` |
| `competing_content_lost` | `true` |

Воспроизводит BUG-051: гарантия create-only нарушается, запись второго
участника теряется.

### 8. `snapshot_failure`

Публикация снимка реестра с внедрённым `OSError` на `Path.rename` для
`.tmp-current`.

| Наблюдение | Значение |
|---|---|
| `before_readable` | `true` |
| `failure` | `audit injected rename failure` |
| `after_readable` | `false` |
| `current_dir_exists` | `false` |

Воспроизводит BUG-052: сбой rename при публикации уничтожает предыдущий
читаемый снимок.

### 9. `contract_inventory`

Обход дерева Click-команд против инвентаря контрактных тестов.

| Наблюдение | Значение |
|---|---|
| фактических листовых команд | 63 |
| записей в инвентаре контрактов | 62 |
| пропущены | `docs flow render`, `docs flow walk` |
| нелистовые записи | `docs flow` |

Воспроизводит BUG-053: контрактные тесты не покрывают вложенные листья `flow`.

## Проверка ссылок после сохранения протокола

На момент первого запуска `tools/linkcheck.py` в `.doc/codexaudit` было
четыре битых ссылки: `evidence/verification.md` (в `04-security.md` и дважды в
`README.md`) и `bugfixes/README.md`. Оба файла созданы этим протоколом; demo
отдельно обязана иметь 0 битых ссылок. Итоговый прогон `tools/linkcheck.py`
приведён в отчёте о финализации.
