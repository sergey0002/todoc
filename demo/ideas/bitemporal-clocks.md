---
id: doc:ideas/bitemporal-clocks.md
title: "Идея: раздельные часы valid_at и known_at для би-темпоральных выборок (учёт observed_at и фильтрация закрытых фактов)"
doc_type: idea
lang: ru
status: captured
created: 2026-11-26
updated: 2026-11-28
tags: [ideas, idea, temporal, bitemporal, records, query, timeline, валидация]
related: ["[[constitution.md]]", "[[entity-catalog]]", "[[documentation-system]]"]
---

# Идея: раздельные часы `valid_at` и `known_at` для би-темпоральных выборок

- Тип: `idea`
- Создан: 2026-11-26
- Идентификатор: `doc:ideas/bitemporal-clocks.md`
- Статус: `captured` (идея зафиксирована, не перешла в план)

## Суть

Разделить единый параметр темпорального среза на два ортогональных именованных параметра — **время истинности в мире (`valid_at` / `--valid-at`)** для интервала `[valid_from, valid_to)` и **время знания системы (`known_at` / `--known-at`)** для интервала `[observed_at, superseded_at)`, сохранив `--as-of` как диагональный шорткат `valid_at = known_at = T`. Одновременно включить учёт `observed_at` при проверке видимости, убрать возврат закрытых (`superseded_at != null`) записей/рёбер при вызове без темпоральных аргументов (выделив для аудита явный `include_superseded` / `--include-superseded`) и покрыть тестами позднюю загрузку и правки задним числом.

## Проблема

Проверка текущей реализации `src/todoc/application/temporal.py` и `src/todoc/application/query.py` выявила четыре расхождения между моделью данных и логикой отбора:

1. **`observed_at` вообще не участвует в фильтрации видимости (`temporal.py:131–152`).** Поле хранится в записях и рёбрах (`TEMPORAL_FIELDS`), но в коде есть только проверка правой границы `is_superseded(fields, as_of)` (`superseded_at <= T`). Левая граница знания (`observed_at <= T`) отсутствует: если факт действовал в мире с `2026-05-01`, но система узнала о нём только `2026-06-10`, запрос на `2026-05-15` ошибочно включает его так, будто система уже располагала этим знанием 15 мая.
2. **Два независимых вопроса склеены в один параметр `as_of`.** Одним скаляром `as_of` невозможно различить:
   - *«Что было истинно 15 мая по нашим сегодняшним знаниям (с учётом поздних загрузок и исправлений задним числом)?»* (`valid_at = 15 мая`, `known_at = сейчас`);
   - *«Что система знала 15 мая о состоянии мира на 15 мая?»* (`valid_at = 15 мая`, `known_at = 15 мая`);
   - *«Что система знала 15 мая о состоянии мира на 1 мая?»* (`valid_at = 1 мая`, `known_at = 15 мая`).
3. **Противоречие при вызове без `--as-of`: закрытые записи утекают в выдачу (`temporal.py:145–172`).** Функция `visible_at(fields, None)` возвращает `not is_superseded(fields, None)` с комментарием *«закрытый факт уже не правда о настоящем»*, но обёртки `records_as_of(records, None)` (`temporal.py:163`) и `relations_as_of(relations, None)` (`temporal.py:170`) делают ранний `if as_of is None: return records` до вызова `visible_at`. В итоге `query_records(..., as_of=None)`, `records list` и `relations graph/tree` отдают закрытые (`superseded_at`) факты наравне с действующими (а тест `test_records_query_without_as_of_hides_closed_records` в `tests/cli/test_cli_temporal.py:70` не ловил это только потому, что `superseded_at` в фикстуре стоял на ребре, а не на самой записи).
4. **Неполная валидация интервала знания (`temporal.py:90–108`).** `interval_defect` проверяет только `valid_from` и `valid_to`, пропуская невалидный формат даты в `observed_at` / `superseded_at` и инвертированный интервал знания (`superseded_at <= observed_at`).

## Принципы

1. **Два симметричных полуоткрытых интервала.** И время истинности `[valid_from, valid_to)`, и время знания `[observed_at, superseded_at)` подчиняются единой полуоткрытой семантике `start <= T < end`: в момент замены `t1` старый факт с `superseded_at = t1` уже закрыт, а новый с `observed_at = t1` уже виден — без перекрытия и без дыры.
2. **Keyword-only аргументы в Python API.** Две строковые даты подряд в позиционных аргументах (`fn(records, t1, t2)`) провоцируют перепутывание осей местами. Параметры `valid_at`, `known_at`, `include_superseded` делаются строго именованными (`*`).
3. **Честный дефолт «актуальное знание» + явный флаг архива.** Без флагов выборка скрывает опровергнутые/закрытые факты (`superseded_at != null`); для чтения полной истории вместе с закрытыми версиями передаётся явный `include_superseded=True` (`--include-superseded`).
4. **Обратная совместимость со старыми записями без темпоральных полей.** Отсутствие `valid_from` / `observed_at` трактуется как `-∞`, отсутствие `valid_to` / `superseded_at` — как `+∞`. Опечатка в параметрах вызова (`valid_at` / `known_at` / `as_of`) бросает `InvalidInstant` (`temporal.invalid_instant`, `exit 3`), а не возвращает пустой ответ.

## Предложение

### 1. Сигнатуры функций в `src/todoc/application/temporal.py` и `query.py`

Вводятся два ортогональных предиката и обновлённая сигнатура с keyword-only параметрами:

```python
def is_valid_at(fields: dict[str, Any], valid_at: str | None) -> bool:
    # valid_from <= T_v < valid_to (при valid_at is None -> True)
    ...

def is_known_at(
    fields: dict[str, Any],
    known_at: str | None = None,
    *,
    include_superseded: bool = False,
) -> bool:
    # При known_at = T_k:
    #   (observed_at IS NULL OR observed_at <= T_k)
    #   AND (include_superseded OR superseded_at IS NULL OR T_k < superseded_at)
    # При known_at is None («текущее знание базы»):
    #   True, если include_superseded=True, иначе superseded_at IS NULL
    ...

def visible_at(
    fields: dict[str, Any],
    as_of: str | None = None,
    *,
    valid_at: str | None = None,
    known_at: str | None = None,
    include_superseded: bool = False,
) -> bool:
    # Конфликт as_of одновременно с valid_at/known_at -> InvalidClockUsage
    # Если задан as_of: диагональный срез valid_at = as_of, known_at = as_of
    return is_valid_at(fields, eff_valid) and is_known_at(
        fields, eff_known, include_superseded=include_superseded
    )
```

Аналогичные keyword-only параметры `*, valid_at: str | None = None, known_at: str | None = None, include_superseded: bool = False` принимают:
- `records_as_of(records, as_of=None, *, valid_at=None, known_at=None, include_superseded=False)` — **без раннего `if as_of is None: return records`**, чтобы при дефолтном вызове отсекались записи с `superseded_at != null`;
- `relations_as_of(relations, as_of=None, *, valid_at=None, known_at=None, include_superseded=False)` — аналогично скрывает закрытые рёбра по умолчанию;
- `query_records(records, entity_type=None, filters=None, limit=200, as_of=None, *, valid_at=None, known_at=None, include_superseded=False)`;
- `timeline(root, records, relations, *, as_of=None, valid_at=None, known_at=None, include_superseded=False, path=None, limit=200)` — события журнала `journal.jsonl` режутся по `known_at`, а факты — по паре `(valid_at, known_at)`.

### 2. Таблица поведения на сценариях поздней загрузки и правок задним числом

Пусть факт `F1` действовал с `1 мая` (`valid_from = 2026-05-01`), загружен в систему `10 июня` (`observed_at = 2026-06-10`), а `1 июля` исправлен задним числом: у `F1` проставлен `superseded_at = 2026-07-01`, и добавлен уточнённый факт `F2` (`valid_from = 2026-05-01`, `observed_at = 2026-07-01`, `superseded_at = null`):

| Вопрос | Параметры вызова | Результат |
|---|---|---|
| Текущее актуальное знание (дефолт) | без флагов (`valid_at=None, known_at=None`) | `[F2]` (`F1` скрыт, так как закрыт `superseded_at`) |
| Полный архив со всеми закрытыми версиями | `include_superseded=True` (`--include-superseded`) | `[F1, F2]` |
| «Что было истинно 15 мая по современным знаниям?» (с учётом поздних загрузок и правок) | `--valid-at 2026-05-15` (`known_at=None`) | `[F2]` |
| «Что система знала 15 мая о 15 мая?» (честный аудит прошлого без послезнания) | `--as-of 2026-05-15` *(или `--valid-at 2026-05-15 --known-at 2026-05-15`)* | `[]` (`15 мая` `F1` ещё не был загружен) |
| «Что система знала 20 июня о 15 мая?» (после загрузки `F1`, но до июльской правки) | `--valid-at 2026-05-15 --known-at 2026-06-20` | `[F1]` |
| «Что система знала к 20 июня обо всех периодах?» | `--known-at 2026-06-20` (`valid_at=None`) | `[F1]` |

### 3. Контракт CLI и `QuerySpec`

- Единый набор опций темпорального среза добавляется в команды чтения графа и записей:
  - `todoc records query` (плюс поддержка полей `valid_at`, `known_at`, `as_of`, `include_superseded` в JSON-файле `QuerySpec`, где CLI-флаг переопределяет поле файла);
  - `todoc records list` и `todoc records aggregate`;
  - `todoc relations graph` и `todoc relations tree` (темпоральные поля уже лежат на рёбрах индекса в `service.py:120`, но сейчас граф не фильтрует закрытые рёбра);
  - `todoc timeline`.
- Одновременная передача `--as-of` вместе с `--valid-at` или `--known-at` возвращает ошибку `temporal.conflicting_clocks` (`EXIT_USAGE = 2`), исключая двусмысленность.
- В JSON-ответе команд возвращается блок применённого среза `clocks: {valid_at, known_at, include_superseded}` (и поле `as_of` для обратной совместимости).

### 4. Расширение валидатора (`interval_defect`)

В `temporal.interval_defect` добавляется проверка всех четырёх полей `TEMPORAL_FIELDS`:
- синтаксис ISO-8601 для `observed_at` и `superseded_at` → `temporal.invalid_instant` с точным JSON Pointer виновного поля;
- проверка `observed_at < superseded_at` (нельзя закрыть факт в системе раньше или в ту же секунду, когда система о нём впервые узнала) → `temporal.invalid_interval` на поле `superseded_at`.

## План внедрения

1. **Фаза 1 — Ядро `temporal.py` и валидатор:**
   - Реализовать `is_known_at`, расширить `visible_at`, `records_as_of`, `relations_as_of` и `interval_defect`; убрать ранний возврат закрытых объектов при `None`.
   - *Acceptance:* матрица unit-тестов в `tests/unit/test_temporal.py` на позднюю загрузку (`valid_from < T < observed_at`), ретроактивное исправление задним числом (`F1` → `F2`), граничные равенства `T == observed_at` и `T == superseded_at`, дефолтное скрытие `superseded_at` и флаг `include_superseded=True`, валидацию битых `observed_at`/`superseded_at`.
2. **Фаза 2 — `query.py`, `relations` и CLI:**
   - Прокинуть `--valid-at`, `--known-at`, `--as-of`, `--include-superseded` в `records query/list/aggregate`, `relations graph/tree` и `timeline`, а также в схему `QuerySpec`.
   - *Acceptance:* CLI-тесты в `tests/cli/test_cli_temporal.py` на все 6 строк таблицы сценариев, ошибку `temporal.conflicting_clocks` при смешивании `--as-of` с `--valid-at`/`--known-at`, `100%` branch coverage и `todoc validate --root demo --all` = `0`.

## Открытые вопросы

- **Дефолт для `valid_at` при вызове без флагов:** оставлять `valid_at = None` (видны все не закрытые `superseded_at` записи, включая запланированные будущие и исторические периоды с истёкшим `valid_to`), или добавить в `records list/query` отдельный сахар `--current` (`valid_at = now_utc`)? Оставить `valid_at = None` по умолчанию безопаснее для детерминизма (P5: результат запроса без флагов не меняется сам по себе при смене системных часов).
- **Автозаполнение `observed_at` при `records create`:** должен ли движок автоматически проставлять `observed_at` при создании темпоральной записи через CLI, если автор указал `valid_from`, но опустил `observed_at`, или оставлять поле строго явным?

## Связанные документы

- [Конституция `todoc` (би-темпоральные связи и детерминизм P5)](../plan/constitution.md)
- [Идея: справочник сущностей системы и граф связей](entity-catalog.md)
- [Идея: система документирования кодовой базы (версионирование правил через `supersedes`)](documentation-system.md)

## Связь с выпуском единого CLI

Сохранены темпоральные факты, provenance и лента. Дополнительные часы знания и их политика остаются в объёме идеи.
[Сводка выпуска единого CLI](../notes/unified-cli-release.md).
