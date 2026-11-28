---
id: doc:bugs/design-q02-review-first-dvoynoy-vyzov-stoimost-dlya-agenta-protiv-kontrolya.md
title: "DESIGN-Q02: review-first двойной вызов — стоимость для агента против контроля"
doc_type: bug-report
lang: ru
created: 2026-11-26
updated: 2026-11-28
tags: [bugs, bug-report, design-question, review-first]
bug_id: DESIGN-Q02
status: open
severity: docs
agent_impact: none
component: cli
found: 2026-11-26
---

# DESIGN-Q02: review-first двойной вызов — стоимость для агента против контроля

| Поле | Значение |
|---|---|
| ID | DESIGN-Q02 |
| Компонент | cli (records create / docs edit — preview/apply) |
| Обнаружено | 2026-11-26 — триаж повторных команд сессии |
| Окружение | todoc 0.1.0 (master a34068b), Python 3.11.2, Linux |

## Сводка

**Дизайн-вопрос, не дефект** (review-first — осознанная конвенция README,
«записать — только review-first»): каждая запись = минимум 2 вызова
(`--preview` → `--apply`). За сессию — десятки пар; полная стоимость контроля
не оценивалась и не сопоставлялась с альтернативами.

## Шаги воспроизведения

1. `todoc records create … --preview` → прочитать WritePlan.
2. `todoc records create … --apply` → повторная передача тех же аргументов.
3. Паттерн повторяется на каждой записи (в сессии — 11 записей = 22 вызова
   только create/status).

## Ожидаемое поведение

Вопрос решения (варианты): (a) оставить как есть — контроль дороже токенов;
(b) `--apply --plan-file` (apply по сохранённому плану без повторного ввода);
(c) batch-режим (`--input-file` со списком записей). Требует явного решения
с оценкой рисков потери review-свойства.

## Фактическое поведение

Парная форма обязательна; без планирования аргументы повторяются целиком.

## Доказательства

```
$ todoc records create --type document --input-file /tmp/r.json --preview
$ todoc records create --type document --input-file /tmp/r.json --apply
                                                 # те же аргументы; ×11 за сессию
```

## Воздействие

- Систематический повтор аргументов; при длинных input-файлах — перерасход,
  но контроль WritePlan сохраняется (ценность конвенции признана).

## Предложение по исправлению

1. ADR: стоимость/польза review-first для агентских сценариев.
2. Если принято: `--plan-file` (сохранённый WritePlan → apply без повторного
   ввода) — контроль сохраняется, ввод не дублируется.

## Заметки

- Сознательно `agent_impact: none`: не попадает в реестр friction.
- Связан с BUG-013 (output-контракты) — экономия на повторе ввода.
