---
id: doc:bugs/bug-020-records-list-wrong-namespace.md
title: "BUG-020: records list по doc_type возвращает пустой успех вместо диагностики неймспейса"
doc_type: bug-report
lang: ru
bug_id: BUG-020
status: fixed
severity: minor
agent_impact: friction
tokens_extra_est: 800
component: cli
found: 2026-11-28
created: 2026-11-27
updated: 2026-11-28
tags: [bugs, bug-report, cli, records, types, namespace]
---

# BUG-020: records list по doc_type возвращает пустой успех вместо диагностики неймспейса

| Поле | Значение |
|---|---|
| Bug ID | BUG-020 |
| Компонент | cli (`records list` + `types list`) |
| Обнаружено | 2026-11-28 — попытка перечислить идеи как записи |
| Окружение | todoc 0.1.0 (5e86eb7), Python 3.14.4, Windows 11 + WSL2 Ubuntu |

## Сводка

`records list --type idea` возвращает `ok: true`, `total: 0`, без диагностик,
хотя `idea` — существующий тип, но в другом неймспейсе (`doc_type`, а не
`entity_type`). `types list` отдаёт четыре неймспейса, но CLI не проверяет, что
переданный `--type` относится к нужному.

## Шаги воспроизведения

1. `todoc records list --root demo --type idea --output json`
2. Контроль с корректным `entity_type`: `todoc records list --root demo --type task --output json`
3. `todoc types list --root demo --output json` — проверить, где лежит `idea`.

## Ожидаемое поведение

CLI знает каталог типов (`dir_types`, `doc_types`, `entity_types`,
`relation_types` — `types list`). Неизвестный в неймспейсе `entity_type` должен
давать диагностику с подсказкой, куда смотреть: `usage.wrong_type_namespace` и
`next_actions` → `docs search --type idea`. Пустой успех недопустим, потому что
он неотличим от «таких записей нет».

## Фактическое поведение

- `records_list` передаёт `entity_type` в `query_records` без валидации против
  каталога: `src/todoc/cli.py:1795-1814`.
- `--type idea` → `total: 0`, `diagnostics: []`, `ok: true`.
- `--type task` → `total: 4` (контроль: механизм работает, проблема только в
  неймспейсе).

## Доказательства

```
$ todoc records list --root demo --type idea --output json
"total": 0
"ok": true
no diagnostics

$ todoc records list --root demo --type task --output json
"total": 4
```

```
$ todoc types list --root demo
dir_types, doc_types, entity_types, relation_types   # idea находится в doc_types
```

```python
# src/todoc/cli.py:1795-1814 (нет проверки entity_type)
def records_list(roots, output, no_input, entity_type, since, until, relation, limit):
    ...
    items, total, truncated = query_records(payload["records"], entity_type, filters, limit)
    _emit_ok({"dataset_id": ctx.dataset_id, "total": total, ...}, output, None)
```

## Воздействие

Агент делает вывод «идей в базе нет» и переключается на другой способ
(перебор `docs search`), теряя вызов и доверие к `records list`. Отдельно
вводит в заблуждение `types list`: он перечисляет типы, но не говорит, какой
командой выбирать каждый неймспейс.

## Предложение по исправлению

- Валидировать `--type` в `records_list` против `registry.entity_types`;
  при попадании в другой неймспейс — `usage.wrong_type_namespace` с
  `suggested_fixes` («`idea` — doc_type; используйте `docs search --type idea`»).
- В `types list` добавить к каждому неймспейсу готовую команду выборки
  (`doc_types` → `docs search`, `entity_types` → `records list`, …).
- Проверка: `records list --type idea` → `ok: false` + подсказка;
  `records list --type task` — без изменений.

## Заметки

Поиск перед созданием (2026-11-28): `--type bug-report --query "records list неймспейс"` — совпадений нет.
Связанные: BUG-022 (нет выборки по типу), BUG-021 (usage-ошибки без guidance),
BUG-013 (неоднородные id/контракты).

Исправление (2026-11-28, рабочее дерево): `records list` и `records query`
проверяют `entity_type` до чтения индекса. Тип из другого пространства имён
даёт `query.namespace_mismatch` с guidance, неизвестный — `query.unknown_type`;
известный тип без записей остаётся пустым успехом. Тесты:
`tests/cli/test_unified_failures.py`. Коммит не создан; после коммита статус
меняется на `fixed` с его ссылкой.

- 2026-11-28: `fixed` — коммит `7d32813`. `records list` по `doc_type` даёт `query.namespace_mismatch` до чтения индекса, с guidance. Тест: `tests/cli/test_unified_failures.py::test_records_type_namespace_is_checked_before_index`.
