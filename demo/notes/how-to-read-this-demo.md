---
id: doc:note-how-to-read
title: Как читать этот демо-датасет
doc_type: note
lang: ru
created: 2026-11-26
updated: 2026-11-26
tags: [notes, note, датасет, читать]
---

# Как читать этот демо-датасет

## Точки входа

- [HOME](../HOME.md) — оглавление по разделам.
- [README датасета](../README.md) — команды для быстрой проверки.
- [Конституция](../plan/constitution.md) — что считать нормой.

## Примеры ссылок, которые валидатор обрабатывает по-разному

Обычная Markdown-ссылка проверяется: [план реализации](../plan/implementation-plan.md).

Wikilink в стиле Obsidian резолвится по имени файла в любом месте датасета: [[data-root]].

Ссылка на раздел: [Конкурентный анализ](../plan/competitive-analysis.md).

Код внутри fenced-блока ссылками **не считается**, поэтому эта строка не даёт диагностики:

```text
[example](missing-in-code.md)
```

Инлайновый код тоже не считается: `[fake](also-missing.md)`.

## Что проверить руками

1. `todoc validate --root demo --all` — ноль диагностик.
2. `todoc docs search --root demo --query "портабельность"` — лексический поиск с фрагментами.
3. `todoc docs read --root demo --id doc:constitution --section "Принципы"` — чтение раздела.
4. `todoc records aggregate --root demo --type metric --metric value --group-by aspect` — агрегация с единицами.