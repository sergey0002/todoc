---
id: doc:skills/process/todoc-capture/SKILL.md
title: "Скил: захват идеи, TODO или заметки"
doc_type: agent-skill
lang: ru
created: 2026-11-26
updated: 2026-11-26
name: todoc-capture
description: "Use when the user says "save this idea / put it as a todo / take a note" in chat. Routes the request to idea (docs new --type idea), task (records create --type task, minimal title+source:user), or note; checks duplicates via docs search first; always ends with validate --all = 0."
---
# Скил: захват идеи, TODO или заметки

## When to Use

- Пользователь просит сохранить идею («придумал…», «идея:») — маршрутизация в идею.
- Поставить TODO («сделать…», «не забыть…») — в задачу.
- Записать заметку («запиши…», «заметка:») — в note.
- Не использовать для: смены статуса существующего (это `todoc-transitions`) и планирования (это `todoc-plan`).

## Procedure

2. Проверка дублей: `todoc docs search --root KB --query "<тема>" --type idea` — топ-3 выдачи; совпадение есть → уточнить у пользователя: новая запись или дополнить существующую (docs edit).
3. Создание идеи: `todoc docs new --root KB --type idea --title "<Название>" --path ideas/<slug>.md` → заполнить Суть/Проблема/Предложение по шаблону и вписать `status: captured` в front matter (docs edit --patch-file: --preview → --apply; docs new не пишет статус, а docs status --set не добавляет поле молча).
4. Создание TODO: минимальный payload — `title` + `source: user` + `status: open`, без выдуманных полей; `todoc records create --root KB --type task --input-file draft.json --preview` → `--apply`.
5. Финал: `todoc validate --root KB --all` — 0 диагностик; ответить пользователю id созданного (doc:… / task:…).

## Pitfalls

- Не выдумывать поля записей — только required схемы и известные поля типа.
- Заголовок дела — глагол («Проверить кеш индекса»), не «Кеш индекса».
- Дубли не плодить: поиск перед созданием обязателен.

## Verification

- `todoc validate --root KB --all` — 0 диагностик.
- `todoc docs search --root KB --query "<тема>"` находит созданное; id назван в ответе пользователю.
