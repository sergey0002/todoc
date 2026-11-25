---
id: doc:state-records
title: "Состояние: записи, отношения, запросы"
doc_type: reference
lang: ru
source: docs/state/08-records-and-relations.md
copied: true
---
# 08. Записи, отношения, запросы

## Что считается записью

JSON-файл со статусом `ok`, содержащий поле `record_id`. Из него берутся `entity_type`,
собственные данные (`data`) и список `relations`. В демо-датасете: 157 записей, 138 отношений.

## Создание записи (`records create`)

Create-only: перезапись существующих записей запрещена.

1. Входной файл парсится строгим `parse_json` (дубли ключей и `NaN` отклоняются).
2. Проверяется, что `entity_type` есть в реестре.
3. Проверяются `required_fields` из описателя типа.
4. Целевой путь строится из `path_template` с подстановками `{record_id}` и `{slug}`
   (`slug` — часть `record_id` после последнего `:`).
5. Путь проверяется на выход за корень (`record.unsafe_path`) и на занятость (`record.target_exists`).
6. Без `--apply` возвращается план: `{target_path, new_content, expected_hash, new_hash, basis,
   validations: ["schema", "relations", "no-overwrite"]}`.
7. С `--apply` файл пишется атомарно, возвращается `{created, new_hash}`.

Проверено: `--preview` показал `records/decisions/demo-write-test.json`, `--apply` добавил один
документ при нуле диагностик.

### Переносимость имён файлов

Значения, подставляемые в `path_template`, проходят `portable_name()`: символы
`<>:"/\|?*` и управляющие заменяются на `-`, точки и пробелы по краям отбрасываются,
зарезервированные имена Windows (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`)
получают префикс `_`. Поэтому `record_id: "note:with:colons"` даёт файл
`records/note/note-with-colons.json`, а `/` внутри идентификатора не создаёт подкаталог.
Идентификатор записи при этом сохраняется как есть — санитаризация касается только пути.
Проверено тестами `tests/unit/test_search_write.py`.

## Валидация записей

| Проверка | Код |
|---|---|
| JSON Schema из `.todoc/entity_types/<entity_type>/schema.json` | `record.schema_violation` |
| дубль `record_id` в датасете | `record.duplicate_id` |
| нет `entity_type` | `record.missing_entity_type` |

Нарушение схемы локализуется JSON Pointer: `location: {"pointer": "/volume", "entity_type": "workout"}`.

## Отношения

Каждый элемент `relations` — объект с `type_id` и `target.id`. В индекс попадает ребро
`{type_id, source_id, target_id}`.

| Проверка | Код |
|---|---|
| `type_id` не в реестре типов отношений | `relation.unknown_type` |
| `target.id` не найден среди записей | `relation.dangling_target` |
| нет `target.id` | `relation.missing_target` |
| элемент не объект / поле не список | `relation.malformed` |

Обход графа (`relations graph`) — BFS **по неориентированному представлению** рёбер: ребро видно
с обоих концов. Параметры `--depth` (по умолчанию 1) и `--limit` (по умолчанию 100).

Проверено на демо: `relations graph --from decision:no-lsp --depth 2` вернул рёбра
`documents` к двум документам и далее рёбра этих документов.

## Записи изменений (`entity_type: change`)

Изменение — **обычная запись**, а не отдельная сущность. Поэтому ему бесплатно достаются
валидация схемы, `records query --where status=proposed` и обход графа зависимостей через
`relations graph`. Отдельный механизм не вводился — это прямое использование P9.

```json
{"schema_version": 1, "record_id": "change:add-history", "entity_type": "change",
 "title": "Журнал изменений и откат", "status": "proposed",
 "created_at": "2026-11-25T10:00:00Z", "applied_at": null,
 "artifacts": ["docs/state/09-storage-and-index.md"],
 "relations": [{"type_id": "blocked_by",
                "target": {"kind": "record", "id": "change:index-redesign"}}]}
```

Жизненный цикл: `proposed` → `in_progress` → `blocked` → `applied` → `archived` | `reverted`.
Недопустимый переход отклоняется кодом `change.id_invalid`.

Файл записи живёт не в `records/`, а в `changes/<change-id>/change.json`: рядом с дельтами,
`proposal.md` и `tasks.md`, потому что намерение человека читается целиком. После
`change archive` папка уносится в `changes/archive/<YYYY-MM-DD>-<change-id>/`, и запись
остаётся читаемой по тому же `record_id`.

Отношение `blocked_by` — зависимость между изменениями: `change validate` отказывает кодом
`change.blocked_by_unresolved`, пока зависимость не в `archived` или `applied`.

## Би-темпоральность: время правды и время знания

У отношения (и у самой записи) четыре опциональных поля:

```json
{"type_id": "employs", "target": {"kind": "record", "id": "person:sergei"},
 "valid_from": "2024-01-01", "valid_to": "2026-06-30",
 "observed_at": "2026-11-25T10:00:00Z", "superseded_at": null}
```

| Поле | О чём |
|---|---|
| `valid_from` / `valid_to` | когда факт был правдой **в мире** |
| `observed_at` / `superseded_at` | когда todoc о нём **узнал** и когда **закрыл** |

Точка во времени: `valid_from <= T AND (valid_to IS NULL OR T < valid_to)`. Интервал
полуоткрытый — на день `valid_to` факт уже не правда. Даты сравниваются как
нормализованные к UTC строки ISO-8601, поэтому порядок не зависит от написания
(`2024-01-01T12:00:00+03:00` — это `2024-01-01T09:00:00Z`).

**Инвалидация вместо удаления.** Противоречащий факт закрывает старый через
`superseded_at`, а сам старый остаётся в файле, в `records read` и в `timeline`. Он исчезает
только из выборки «на момент T». Закрытие — всегда явное действие человека (правка записи
или `change`): ядро детерминированное (P5) и противоречия само не угадывает.

Поля опциональны: записи и отношения без них ведут себя точно как раньше и видны в любой
выборке.

## Запросы (`records query`)

QuerySpec — JSON-файл:

```json
{"schema_version": 1, "name": "competitors-portable", "entity_type": "competitor",
 "filters": {"portability": {"$in": ["files-only", "mostly-portable"]}}, "limit": 50}
```

Поддерживаемые операторы фильтров:

| Оператор | Смысл |
|---|---|
| `"field": value` | точное равенство |
| `{"$in": [...]}` | вхождение в список |
| `{"$gte": v, "$lte": v}` | диапазон (можно использовать вместе) |

Пути к полям — через точку (`volume.unit`). Результат сортируется по `record_id`; ответ содержит
`total`, `truncated`, `items[]`. Проверено: запрос `competitors-portable` вернул 21 запись.

Никаких `eval`, SQL и shell: фильтр — декларативная структура.

## Агрегация (`records aggregate`)

Сумма числового поля с обязательной provenance:

```
entity_type: metric   metric: value   formula: sum(value)
groups: {benchmark: 4.473, performance: 10706, tests: 3933, cli: 26,
         docs: 133, types: 209, code: 4032}
group_units: {benchmark: ratio, performance: ms, tests/cli/docs/types/code: count}
units: ""            # пустое, когда единицы в группах различаются
incoming_ids: [24 идентификатора]   completeness: complete
```

Правила:

- значение поля может быть числом либо объектом `{"value": N, "unit": "…"}`;
- единицы берутся из первого такого объекта; расхождение единиц — `query.unit_mismatch`;
- нечисловое поле — `query.unknown_metric`;
- нет записей типа — `query.no_records`;
- `--group-by` группирует по полю; при отсутствии значения группа называется `unknown`;
- `incoming_ids` и `completeness` позволяют проверить, из чего сложилась сумма.

## Проекции (`records read --view`)

Список полей берётся из `views` описателя типа. Проверено: `--view summary` для
`document:constitution` вернул только `record_id`, `title`, `doc_type`, `lang`.

## Связанные разделы

- [04-config-and-types.md](04-config-and-types.md) — описатели типов и схемы.
- [06-validation-and-diagnostics.md](06-validation-and-diagnostics.md) — коды ошибок.
- [13-demo-dataset.md](13-demo-dataset.md) — живые примеры записей.
