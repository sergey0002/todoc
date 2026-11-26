---
id: doc:bugs/bug-016-filtry-records-query-ne-dokumentirovany-v-spravkah.md
title: "BUG-016: фильтры records query не документированы в справках"
doc_type: bug-report
lang: ru
created: 2026-11-26
updated: 2026-11-26
bug_id: BUG-016
status: open
severity: docs
agent_impact: friction
component: docs
found: 2026-11-26
---

# BUG-016: фильтры records query не документированы в справках

| Поле | Значение |
|---|---|
| Bug ID | BUG-016 |
| Компонент | docs (references/ — справка query; синтаксис фильтров) |
| Обнаружено | 2026-11-26 — триаж реестров bug-репортов |
| Окружение | todoc 0.1.0 (master a34068b), Python 3.11.2, Linux |

## Сводка

Query-файлы датасета используют операторы `$in`/`$gte` с вложенными списками
(«значение совпадает с любым из элементов вложенного списка»), но синтаксис
фильтров не описан ни в одной справке — форма выясняется чтением готовых
query-JSON (в демо 8 файлов).

## Шаги воспроизведения

1. `grep -rn '\$in\|\$gte' docs/references demo/references` → 0 совпадений.
2. Открыть `demo/.todoc/queries/bugs-agent-friction.json` → фильтр
   `"agent_impact": {"$in": [["friction"], ["friction", "token_overrun"]]}` —
   вложенность списков неочевидна без чтения кода query.py.

## Ожидаемое поведение

Справка `references/` (или `todoc records query --help`/`docs read` гайда)
документирует: поддерживаемые операторы (`$in`, `$gte`, `$lte`, `contains`),
семантику вложенных списков для списочных полей, пример query-файла.

## Фактическое поведение

Документации нет; единственный источник — код `application/query.py` и примеры.

## Доказательства

```
$ grep -rn '\$in' docs/references demo/references   # без совпадений
$ cat demo/.todoc/queries/bugs-agent-friction.json  # форма выясняется по образцу
```

## Воздействие

- Составление нового query требует чтения кода/образцов (~600 токенов
  на эпизод); риск неверного фильтра без диагностики.

## Предложение по исправлению

1. Раздел в `references/` (справка records): операторы и семантика фильтров.
2. `records query --help`: краткая форма + ссылка на справку.
3. Тест-пример в докстроках query.py.

## Заметки

- Связан с реестрами демо (bugs-agent-friction, tasks-by-project) — они
  де-факто единственная документация синтаксиса.
