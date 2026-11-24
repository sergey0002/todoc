---
id: doc:architecture-data-model
title: Модель данных todoc
doc_type: architecture-doc
lang: ru
---

# Модель данных `todoc`

## Сущности

| Сущность | Ключ | Источник | Комментарий |
|---|---|---|---|
| Folder | `folder:<rel_path>` | обход папок | `dir_type`, `rule_source`, родитель |
| Document | `document_id` из front matter `id` либо `doc:<rel_path>` | файлы .md/.csv/.json | `doc_type`, `format`, `hash`, `size`, `title`, `status` |
| Record | `record_id` | JSON с полем `record_id` | `entity_type`, `data`, `hash` |
| Relation | `type_id` + `source_id` + `target_id` | поле `relations` записи | тип обязан существовать, цель обязана быть найдена |
| Diagnostic | `diag_*` | валидация | `code`, `severity`, `location`, `evidence`, `suggested_fixes` |

## Идентичность

- `document_id` — адрес документа для `docs read --id`. Задаётся front matter `id:`.
- `record_id` — идентификатор сущности, например `document:constitution`.
- Это разные пространства имён: документ может описывать запись, не совпадая с ней по ID.

## Связи

- [Архитектура](system-architecture.md) — слои и поток данных.
- [Справка: сущности, отношения и запросы](../references/entities-relations-and-queries.md).
