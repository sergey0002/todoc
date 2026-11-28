---
id: doc:bugs/bug-039-records-aggregate-hidden-default.md
title: "BUG-039: records aggregate без --type молча выбирает тип workout"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
bug_id: BUG-039
status: open
severity: minor
agent_impact: friction
tokens_extra_est: 800
component: cli
found: 2026-11-28
tags: [bugs, bug-report, cli, records, aggregate, defaults]
---

# BUG-039: records aggregate без --type молча выбирает тип workout

| Поле | Значение |
|---|---|
| Bug ID | BUG-039 |
| Компонент | cli (`records aggregate`) |
| Обнаружено | 2026-11-28 — аудит умолчаний records-команд |
| Окружение | todoc 0.1.0 (5e86eb7 + рабочее дерево), Python 3.14.3, Windows 11 + WSL2 Ubuntu |

## Сводка

`records aggregate` объявляет `--type` необязательным и при отсутствии
подставляет скрытый тип `workout`: `resolved_type = entity_type or "workout"`.
В демо-датасете такого типа нет, поэтому команда с корректным `--metric value`
падает с `No records of type 'workout'`, хотя метрики существуют под типом
`metric`. Пользователь не видит, откуда взялся `workout`.

## Шаги воспроизведения

1. `todoc records aggregate --root demo --metric value --output json`
2. Контроль с явным типом:
   `todoc records aggregate --root demo --type metric --metric value --group-by aspect --output json`
3. `todoc types list --root demo` — проверить, есть ли `workout` среди `entity_types`.

## Ожидаемое поведение

`--type` обязателен (как в README: «`records aggregate --metric FIELD --type T
[--group-by F]`», `README.md:156`) либо отсутствие типа — ошибка вызова
`usage.error` со списком доступных `entity_types`. Скрытого дефолта
`workout` быть не должно: он не документирован и не следует из данных.

## Фактическое поведение

- `resolved_type = entity_type or "workout"` — жёстко зашитый дефолт:
  `src/todoc/cli.py:1908`.
- В демо `workout` отсутствует, поэтому `aggregate_records` поднимает
  `ValidationError("No records of type 'workout'")` (`src/todoc/application/query.py:69-71`).
- Ответ — error-envelope с `ok: false` и сообщением про `workout`, без
  подсказки, что нужен `--type metric`.
- `--type metric` работает и возвращает группы.

## Доказательства

```
$ todoc records aggregate --root demo --metric value --output json
{
  "schema_version": 1,
  "ok": false,
  "data": {},
  "diagnostics": [
    {
      "code": "query.no_records",
      "message": "No records of type 'workout'",
      ...
    }
  ]
}

$ todoc records aggregate --root demo --type metric --metric value --group-by aspect --output json
  "ok": true,
  "data": { "entity_type": "metric", "metric": "value", ... }
```

Код: `src/todoc/cli.py:1908`; `src/todoc/application/query.py:69-71`.

## Воздействие

- `friction`: агент, читающий README, ожидает обязательный `--type`, но CLI
  принимает вызов и отвечает про несуществующий `workout`; нужен повторный
  вызов и догадка о правильном типе.
- Ошибка выглядит как «в датасете нет метрик», хотя они есть; это неверная
  модель мира, а не только неудобство.
- Цена эпизода: 1 неудачный вызов + `types list`/повтор ≈ 800 токенов.

## Предложение по исправлению

1. Сделать `--type` обязательным (`required=True`) — как в README.
2. Либо оставить необязательным, но при отсутствии возвращать `usage.error`
   с `next_actions` → `types list` и перечнем доступных `entity_types`.
3. Тест: `aggregate --metric value` без `--type` → exit 2 и подсказка;
   `--type metric` — без изменений.

## Заметки

Поиск перед созданием (2026-11-28): `docs search --type bug-report --query
"records aggregate workout"` — совпадений по корневой причине нет (BUG-020 —
неймспейс `records list`, BUG-016 — фильтры query не документированы).
Связанные: BUG-022 (нет обзорной выборки по типу).
