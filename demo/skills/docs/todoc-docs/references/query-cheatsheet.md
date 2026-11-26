---
id: doc:skills/docs/todoc-docs/references/query-cheatsheet.md
title: "Шпаргалка: поиск и чтение KB (todoc)"
doc_type: unknown
lang: ru
created: 2026-11-26
updated: 2026-11-26
tags: [skill, unknown, шпаргалка, чтение]
---

# Шпаргалка: поиск и чтение KB (todoc)

| Задача | Команда |
|---|---|
| Карта датасета | `todoc docs read --root demo --id doc:home` |
| Поиск | `todoc docs search --root demo --query "термины" --limit 5` |
| Секция документа | `todoc docs read --root demo --id <id> --section "8. Прогресс и отклонения"` |
| Диапазон строк | `todoc docs read --root demo --id <id> --line-range 790-805` (дефис!) |
| Список записей | `todoc records list --root demo --type document --limit 20` |
| Фильтр багов | `todoc records query --root demo --query-file demo/.todoc/queries/bugs-agent-friction.json` |
| Чтение записи | `todoc records read --root demo --id <record_id>` |
| Дерево скилов | `todoc skills tree --root demo` |
| Тело скила | `todoc skills read --root demo --path <путь из дерева>` |
| Валидация всего | `todoc validate --root demo --all` |
