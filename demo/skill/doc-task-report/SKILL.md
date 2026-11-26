---
name: doc-task-report
description: >
  Отчёт по выполненной задаче из фактов: task-snapshot/задача + change (proposal) + дифф + вывод проверок. Применять после закрытия задачи или изменения.
doc_type: agent-skill
lang: ru
created: 2026-11-26
updated: 2026-11-26
tags: [skill, documentation, agent]
---

# Отчёт по задаче

## Когда применять

- Задача/изменение закрыто и нужен человекочитаемый отчёт в KB.

## Шаги

1. Эталон: `todoc types prompt task-report --op create --root KB`.
2. Проект: `todoc state get --root KB --key context.current_project` (план agent-state).
3. Данные: задача (`task-snapshot:<KEY>` или постановка), `change:<slug>` → proposal.md
   («Зачем»), дифф файлов («Что изменилось»), команды и вывод («Как проверялось»).
4. Черновик: `docs new --root KB --type task-report --title "<Название>" --path reports/<имя>.md`;
   секция «Риски и уроки» — только если есть фактические.
5. Проверка: `validate --all` — 0 диагностик; каждый факт со ссылкой на источник.

## Стоп-условия

- «Что изменилось» без диффа — не пишется; остановись и собери факты.
