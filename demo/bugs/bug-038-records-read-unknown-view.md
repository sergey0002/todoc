---
id: doc:bugs/bug-038-records-read-unknown-view.md
title: "BUG-038: records read --view с неизвестным именем молча возвращает всю запись"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
bug_id: BUG-038
status: fixed
severity: minor
agent_impact: [friction, token_overrun]
tokens_extra_est: 1500
component: cli
found: 2026-11-28
tags: [bugs, bug-report, cli, records, projection, view]
---

# BUG-038: records read --view с неизвестным именем молча возвращает всю запись

| Поле | Значение |
|---|---|
| Bug ID | BUG-038 |
| Компонент | cli (`records read --view`) |
| Обнаружено | 2026-11-28 — аудит проекций записи |
| Окружение | todoc 0.1.0 (5e86eb7 + рабочее дерево), Python 3.14.3, Windows 11 + WSL2 Ubuntu |

## Сводка

`records read --id ... --view <неизвестное имя>` не сообщает об ошибке и
возвращает всю запись вместо проекции: `fields` пустой, условие `if fields:`
не срабатывает, `data` остаётся полным. Агент думает, что получил запрошенную
проекцию, и тратит токены на поля, которые не просил.

## Шаги воспроизведения

1. `todoc records read --root demo --id term:data-root --view nope --output json`
2. Сравнить `data` с выводом без `--view`:
   `todoc records read --root demo --id term:data-root --output json`
3. Проверить, что в `diagnostics` нет ошибки о неизвестном view.

## Ожидаемое поведение

Неизвестное имя view — ошибка вызова или диагностика
(`records.view_not_found`) с `next_actions` → `types show term` (список
доступных views). Если view объявлен, но не содержит полей, ответ — пустая
проекция (`data: {}`), а не полная запись. Контракт: «`records read --id ID
[--view NAME]` — запись целиком или проекция» (`README.md:157`).

## Фактическое поведение

- `records_read` берёт `descriptor.get("views")` и при непустом `fields`
  фильтрует `data`; при неизвестном view `fields` пустой и `data` не меняется:
  `src/todoc/cli.py:1934-1938`.
- Ответ `ok: true`, `diagnostics: []`; отличить «view не найден» от «view
  вернул всю запись» невозможно.
- Для `term:data-root` в ответе остаются `definition`, `aliases`, `relations`,
  `mentioned_in` и другие поля, хотя запрошен несуществующий view.

## Доказательства

```
$ todoc records read --root demo --id term:data-root --view nope --output json
{
  "schema_version": 1,
  "ok": true,
  "data": {
    "record_id": "term:data-root",
    "path": "records/terms/data-root.json",
    "data": {
      "record_id": "term:data-root",
      "entity_type": "term",
      "term_type": "concept",
      "title": "DATA_ROOT",
      "definition": "...",
      ...
    },
    "mentioned_in": [...]
  },
  "diagnostics": [],
  "next_actions": []
}
```

Код: `src/todoc/cli.py:1934-1938`.

## Воздействие

- `friction`: агент запрашивает компактную проекцию, получает полную запись и
  либо строит вывод по лишним полям, либо вынужден перечитывать `types show`
  и уточнять имя view.
- `token_overrun`: на записях с `definition`/`relations`/`mentioned_in` ответ
  в разы больше проекции; эпизод ≈ 1–2k токенов лишних.

## Предложение по исправлению

1. Если `view` задан и `descriptor.views` не содержит его — `ValidationError`
   `records.view_not_found` с `next_actions` на `types show <entity_type>`.
2. Если view есть, но `fields` пустой — вернуть `data: {}` и
   `view_fields: []`, явно показывая пустую проекцию.
3. Тест: `--view nope` → `ok: false`/диагностика; `--view <валидный>` —
   только объявленные поля.

## Заметки

Поиск перед созданием (2026-11-28): `docs search --type bug-report --query
"records read view"` — совпадений по корневой причине нет (BUG-018 — docs read
budget, BUG-020 — неймспейс records list). Связанные: BUG-022 (нет обзорной
выборки), BUG-037 (output-контракт).

- 2026-11-28: `fixed` — коммит `7d32813`. Неизвестный `--view` даёт диагностику `view.fallback` с фактическим видом. Проверка: `tools/bug_acceptance.py --only BUG-038` → `fixed`. Тест: `tests/cli/test_unified_failures.py`.
