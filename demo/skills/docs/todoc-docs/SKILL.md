---
id: doc:skill-todoc-docs
title: "Скил: поиск и чтение KB датасета через CLI"
doc_type: agent-skill
lang: ru
updated: 2026-11-25
name: todoc-docs
description: "Ищет и читает knowledge base датасета todoc через CLI: bounded search/read по конвенции. Use when answering from the KB."
---

# Скил: поиск и чтение KB датасета через CLI

## When to Use

- Нужно найти ответ/факт в датасете (планы, идеи, баг-репорты, записи) — вместо ручного обхода файлов.

## Procedure

1. Сначала оглавление карты: `todoc docs read --root demo --id doc:home` (HOME — карта содержимого).
2. Точечный поиск: `todoc docs search --root demo --query "<термины>" --limit 5` — возьми пути из выдачи.
3. Читай bounded, не весь файл: `todoc docs read --root demo --id <id> --section "<заголовок>"` или `--line-range A-B` (дефис, не запятая).
4. Записи: `todoc records list --root demo --type <type> --limit 10`, фильтры — готовые query-файлы в `demo/.todoc/queries/`.
5. Шпаргалка команд: references/query-cheatsheet.md рядом с этим SKILL.md.

## Pitfalls

- `--line-range` с запятой падает JSONDecodeError — только дефис.
- Не читай файлы напрямую, если есть CLI-проекция: CLI даёт bounded + метаданные; прямой cat — только когда CLI-пути нет.

## Verification

- Каждый факт в ответе — с источником (путь/ID и секция), который можно перепроверить той же командой.
