---
id: doc:skills/process/todoc-plan/SKILL.md
title: "Скил: идея → план → задачи"
doc_type: agent-skill
lang: ru
created: 2026-11-26
updated: 2026-11-28
name: todoc-plan
description: "Use when the user approves an idea for implementation («make a plan», «let's do it») or asks to break an approved plan into tasks. Checks the idea readiness (open questions), creates a plan doc of type plan with spec link and derived_from edge, sets idea status planned, creates task records with implements edges and subtask_of for children."
---
# Скил: идея → план → задачи

## When to Use

- Пользователь одобрил идею к реализации («делаем план», «берём в работу») — создание плана.
- Просит разбить одобренный план на задачи — task-записи с рёбрами.
- Не использовать для: захвата новой идеи (`todoc-capture`) и исполнения существующего плана (`todoc-execute`).

## Procedure

0. Перед новым планом найти существующие по компоненту и симптому через `docs search --type plan --query ...`; читать нужные разделы. Сопоставить требования с задачами. Если они покрыты — дополнить критерии приёмки и дать ссылку, не создавать параллельный backlog. Пробелы включить в задачи владельца; новый план нужен для самостоятельного результата или явно выбранной отдельной поставки.
   Пример: BUG‑022 закрыт в [выпуске единого CLI](../../../notes/unified-cli-release.md). Исследование metadata-overview имеет статус superseded.
1. Проверка готовности: статус идеи `captured` (`todoc docs status --root KB --id doc:<idea>`) и открытые вопросы закрыты; иначе — стоп и вопрос пользователю «делаем как есть?».
2. Создание плана: `todoc docs new --apply --root KB --type plan --title "<Название>" --path plan/<slug>.md` → напрямую заполнить 8 секций шаблона; в шапке `Спека:` = id идеи; в fm плана — `status: active` и `derived_from` на файл идеи (якорь `путь@sha256`), затем выполнить `todoc sync --apply --root KB plan/<slug>.md`.
3. Статус идеи: `todoc docs status --root KB --id doc:<idea> --set planned`.
4. Задачи (по запросу пользователя): одна `records create --type task` на задачу раздела 5 плана; в relations — ребро `implements` на document-запись плана (records/documents/<plan-slug>.json); крупные задачи → родитель + дети с рёбрами `subtask_of`; каждая задача — review-first: --preview → --apply.
5. `todoc validate --root KB --all` — 0 диагностик после каждого шага.

## Pitfalls

- Без явного подтверждения пользователя не переходить идею в `planned`.
- Терминальные статусы (`done`) — только после явной фразы пользователя.
- Ребро `implements` целятся в record_id document-записи плана (машино-рёбра — между record_id), не в путь файла.

## Verification

- `todoc relations graph --root KB --from task:<slug> --depth 1` — ребро `implements` на план.
- `todoc docs status --root KB --id doc:<idea>` → `planned`; `validate --all` — 0 диагностик.
