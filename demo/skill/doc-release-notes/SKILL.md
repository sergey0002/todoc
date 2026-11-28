---
id: "doc:skill/doc-release-notes/SKILL.md"
title: "Сборка release-note"
name: doc-release-notes
description: >
  Сборка релизной сводки release-note из существующих данных: release-запись + task-snapshot'и + affected flow/rule + incident/fixes. Применять при выпуске версии.
doc_type: agent-skill
lang: ru
created: 2026-11-26
updated: 2026-11-28
tags: [skill, documentation, agent]
---

# Сборка release-note

## Когда применять

- Релиз выпущен (или готовится) и нужна сводка для KB.

## Шаги

1. Эталон: `todoc types prompt release-note --op create --root KB`.
2. Данные: `records read --id release:<semver>` (version/date/summary; нет записи —
   создать по `todoc types prompt release --op create`), task-snapshot'и релиза,
   затронутые `flow:`/`rule:` (рёбра affects), `incident:` + fixes.
3. Черновик: `docs new --root KB --type release-note --title "Релиз <semver>" --path reports/release-<semver>.md`
   (fm `doc_type: release-note` ставится docs new автоматически); 4 секции заполняются
   проекцией записей, ничего руками не сочиняется.
4. Рёбра: затронутые флоу/правила — `affects` от release; фиксы — `fixes` от release на incident.
5. Проверка: `validate --all` — 0 диагностик; linkcheck — 0 битых.

## Стоп-условия

- Нет release-записи и данных релиза — не выдумывай сводку, спроси.
