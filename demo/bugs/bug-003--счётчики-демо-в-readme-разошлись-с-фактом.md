---
id: doc:bug-003-readme-counters-stale
title: "BUG-003: Счётчики демо в README разошлись с фактом"
doc_type: bug-report
lang: ru
bug_id: BUG-003
status: triaged
severity: major
agent_impact: friction
tokens_extra_est: 2000
component: docs
found: 2026-11-25
---

# BUG-003: Счётчики демо в README разошлись с фактом

| Поле | Значение |
|---|---|
| Bug ID | BUG-003 |
| Компонент | docs (demo/README.md, README.md, docs/state/13) |
| Обнаружено | 2026-11-25 — сверка при составлении плана `doc:plan-softdoc-profile` |
| Окружение | todoc 0.1.0 (4b6ae47) |

## Сводка

`demo/README.md` заявляет «15 dir_types, 21 doc_types, 13 entity_types,
9 relation_types», фактический вывод `todoc types list --root demo` —
**17** dir_types (после PR #38 добавлены `tasks`, `projects`, `harness`).
Агент, сверяющий систему по README, получает ложные ожидания.

## Шаги воспроизведения

1. `grep -i "dir_types" demo/README.md` → «15 dir_types, 21 doc_types, …»
2. `todoc types list --root demo` → dir_types: 17.

## Ожидаемое поведение

Счётчики в README совпадают с фактическим выводом команд; при изменении
типовой системы в том же PR обновляются все места со счётчиками
(demo/README.md, README.md, docs/state/01, docs/state/13).

## Фактическое поведение

- demo/README.md: 15 dir_types — фактических 17 (drift после PR #38).
- Корневой README: «Команд CLI | 26», docs/state/01: «46 листовых
  (25 верхнеуровневых)» — 26 не сверяется с 25/46 без уточнения, какую метрику
  считает (требует пересчёта при следующей правке; не заявляется как ошибка).

## Доказательства

```
$ todoc types list --root demo   (2026-11-25)
dir_types: architecture, attachments, competitors, constitution, glossary,
guides, harness, idea, inbox, notes, plan, projects, records, references,
research, skill, tasks   ← 17
```

```
$ grep -o "15 dir_types[^|]*" demo/README.md
15 dir_types, 21 doc_types, 13 entity_types, 9 relation_types
```

## Воздействие

- Агент верит README → при `types list` видит «лишние» типы или ищет
  несуществующие; первые минуты сессии уходят на сверку.
- Тот же класс дефекта, что P1-2 (рост индекса без чистки): счётчики —
  ручные производные, деградируют без принуждения.
- Обходимо (источник истины — `types list`), но README — первая точка входа.
Цена для агента за эпизод: пересчёт `types list` + сверка пяти файлов и grep-вызовы — несколько тысяч токенов сверки, которых не было бы при верном README.

## Предложение по исправлению

1. Пересчитать все счётчики от фактического `types list` и обновить пять
   файлов (demo/README.md, README.md, docs/state/01, docs/state/13, HOME.md
   при наличии) — внесено в план `doc:plan-softdoc-profile`, задача 7 (D7:
   «счётчики — от факта»).
2. Системно: рассматривать счётчики в README как производные; при изменении
   `.todoc/` в PR — чек-лист «обнови счётчики» в шаблоне PR.

## Заметки

- После исполнения плана softdoc (волны 1–2) счётчики изменятся ещё раз —
  сверять в задаче 7/10 плана.
