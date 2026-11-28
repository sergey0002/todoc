---
id: doc:skill-todoc-docs
title: "Скил: поиск и чтение KB датасета через CLI"
doc_type: agent-skill
lang: ru
updated: 2026-11-28
name: todoc-docs
description: "Ищет и читает knowledge base датасета todoc через CLI: bounded search/read по конвенции. Use when answering from the KB."
created: 2026-11-26
tags: [skill, agent-skill, датасета, чтение]
---

# Скил: поиск и чтение KB датасета через CLI

## When to Use

- Нужно найти ответ/факт в датасете (планы, идеи, баг-репорты, записи) — вместо ручного обхода файлов.

## Procedure

1. Для списка идей по статусу начни с `todoc docs list --root demo --type idea --fields id,path,title,status --limit 100`. Используй `data.result.items`, проверь `data.meta.complete` и дочитай страницы по `next_cursor`. Пустой статус укажи отдельно. HOME открывай для навигации по незнакомой области.
   Для нескольких типов используй `--type 'plan|idea|agent-skill'`.
   Условия по записанным полям передавай как `--attr-<имя> 'значение1|значение2'`.
   Список полей выбранного типа узнай одним вызовом `docs list --type <тип> --filter-fields`.
2. Для поиска по содержимому используй `docs search --query "<термины>" --limit 5`. При наличии фильтра по метаданным `--query` можно опустить.
3. Читай нужный фрагмент через `docs read --section` или `--line-range A-B`. Поля фрагмента находятся в `data.result`. `--budget` ограничивает символы текста.
4. Записи читай через `records list/query`. Используй сохранённый `--query-file` или общий `--filter-file`. Строки находятся в `data.result.items`.
5. Метаданные редактируй через `docs edit` или `records edit`. Проверь `--preview`, затем передай из него `expected_hash` в `--apply --if-hash`. Для правки тела используй `docs edit` или документированный `todoc sync`.
6. Шпаргалка команд: references/query-cheatsheet.md рядом с этим SKILL.md.

## Pitfalls

- Проверь один вызов перед тем, как повторять форму команды для многих документов. При ошибке останови зависимый пакет и используй подсказку команды.
- `--line-range` принимает `A-B`. При `usage.invalid_line_range` поправь диапазон и повтори вызов.
- Не читай файлы напрямую, если есть CLI-проекция: CLI даёт bounded + метаданные; прямой cat — только когда CLI-пути нет.

## Verification

- Каждый факт в ответе — с источником (путь/ID и секция), который можно перепроверить той же командой.
