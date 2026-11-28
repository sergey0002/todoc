---
id: doc:skills/docs/todoc-docs/references/query-cheatsheet.md
title: "Шпаргалка: поиск и чтение KB (todoc)"
doc_type: reference
lang: ru
created: 2026-11-26
updated: 2026-11-28
tags: [skill, reference, шпаргалка, чтение, обзор, статус]
---

# Шпаргалка: поиск и чтение KB (todoc)

| Задача | Команда |
|---|---|
| Карта датасета | `todoc docs read --root demo --id doc:home` |
| Обзор по типу и статусу | `todoc docs list --root demo --type bug-report --status open --fields id,path,title,status --limit 1000` |
| Только md, без JSON-зеркал | `todoc docs list --root demo --type bug-report --origin document` |
| Поля типа | `todoc docs list --root demo --type bug-report --filter-fields` |
| Документы без статуса (JSON-зеркала) | `todoc docs list --root demo --type bug-report --status-missing` |
| Поиск | `todoc docs search --root demo --query "термины" --limit 5` |
| Секция документа | `todoc docs read --root demo --id <id> --section "8. Прогресс и отклонения"` |
| Диапазон строк | `todoc docs read --root demo --id <id> --line-range 790-805` (дефис!) |
| Список записей | `todoc records list --root demo --type task --limit 20` (только `entity_type`, не `doc_type`) |
| Фильтр багов | `todoc records query --root demo --query-file demo/.todoc/queries/bugs-agent-friction.json` |
| Чтение записи | `todoc records read --root demo --id <record_id>` |
| Дерево скилов | `todoc skills tree --root demo` |
| Тело скила | `todoc skills read --root demo --path <путь из дерева>` |
| Финализация правки | `todoc sync --apply --root demo <path>` |
| Валидация всего | `todoc validate --root demo --all` |

Замечания:

- `docs search` отдаёт `status`/`doc_type`, но для полного обзора используй
  `docs list` (пагинация и фильтр по статусу).
- `docs list` без `--origin` включает JSON-зеркала `records/documents/`;
  `--origin document` оставляет только md, `--status-missing` показывает зеркала.
- `records list --type bug-report` — пустой `ok` (неймспейс), не «нет данных».
- Неизвестные `--type`/`--status` в `docs list` дают `docs.unknown_type`/`docs.unknown_status`.
