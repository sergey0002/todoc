---
id: doc:skills/process/todoc-execute/SKILL.md
title: "Скил: рабочая сессия по плану или задачам"
doc_type: agent-skill
lang: ru
created: 2026-11-26
updated: 2026-11-27
name: todoc-execute
description: "Use when starting a work session on a plan or task ("continue", "what's next", "work on the plan"). Finds the first unchecked checkbox or open task, executes bite-sized steps with verification, logs deviations to plan section 8, closes tasks only with explicit user confirmation."
---
# Скил: рабочая сессия по плану или задачам

## When to Use

- Начало рабочей сессии по плану или задаче («продолжи», «что дальше», «работай по плану»).
- Не использовать для: смены статусов вне сессии (`todoc-transitions`) и планирования (`todoc-plan`).

## Procedure

1. Старт: план → `todoc docs read --root KB --id doc:<plan> --section "8. Прогресс и отклонения"` и первый неотмеченный `[ ]` в задачах; задачи → `todoc records list --root KB --type task` со статусами open/in_progress.
2. Исполнение шага задачи: тест → код → тест → коммит; чекбокс шага тикается в том же коммите; имена/сигнатуры — только из плана, не импровизировать.
3. Отклонение → добавить строку `YYYY-MM-DD — задача N, шаг M: что не так → что выбрано вместо и почему` напрямую в раздел 8 плана и запустить `todoc sync --root KB <путь-к-плану>`; история не переписывается, шаги задним числом не тикаются.
4. Закрытие задачи: `todoc records status --root KB --id task:<slug> --set done` — ТОЛЬКО после явного подтверждения пользователя.
5. Все задачи плана done → ПРЕДЛОЖИТЬ плану in_progress→done по DoD-чеклисту раздела 6; каскад на идею — тоже предложение, не автоматика.

## Pitfalls

- Терминальные статусы (`done`) — только после явной фразы пользователя; скил предлагает, решает пользователь.
- Не импровизировать имена/сигнатуры вне плана; отклонение фиксируется в разделе 8, не молча.

## Verification

- `todoc docs read --root KB --id doc:<plan> --section "8. Прогресс и отклонения"` — отклонения записаны; `validate --all` — 0; статусы задач соответствуют фактам.
