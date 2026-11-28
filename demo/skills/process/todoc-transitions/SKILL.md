---
id: doc:skills/process/todoc-transitions/SKILL.md
title: "Скил: переходы статуса"
doc_type: agent-skill
lang: ru
created: 2026-11-26
updated: 2026-11-28
tags: [skill, agent-skill, status, transitions]
name: todoc-transitions
description: "Use when any entity changes state — idea realized without a plan, guide outdated, decision cancelled, version replaced. Runs the consistency check first (edge exists, status stale), changes status via docs status / records status, keeps edge+status in one commit, never sets done/rejected/superseded without an explicit user phrase."
---
# Скил: переходы статуса с проверкой консистентности

## When to Use

- Любая смена состояния сущности: идея реализована без плана, справочник устарел, решение отменено, версия заменена.
- Не использовать для: создания нового (`todoc-capture`) и рабочей сессии по плану (`todoc-execute`).

## Procedure

1. Консистентность ДО: `todoc relations graph --root KB --from <id> --depth 1` — ребро есть, статус старый → довести переход; статус поменяли, ребра нет → добавить. Пары «ребро+статус» — одним коммитом.
2. Смена статуса: md → `todoc docs status --root KB --id doc:<id> --set <value>`; JSON → `todoc records status --root KB --id <record_id> --set <value>`; набор — из allowed_statuses/enum типа, чужой статус не выдумывать.
3. Замена версии: новый документ + ребро `supersedes` на старого → старому `--set superseded`.
4. Терминальные статусы (`done`/`rejected`/`superseded`) — только после явной фразы пользователя; справочники без статуса не трогать; сомнение → спросить пользователя.

## Pitfalls

- Статус и ребро меняются одним коммитом — расхождение «статус новый, связь старая» недопустимо.
- Не ставить `done`/`rejected`/`superseded` без явной фразы пользователя.

## Verification

- `todoc relations graph --root KB --from <id> --depth 1` — ребро соответствует статусу; `validate --all` — 0 диагностик.
