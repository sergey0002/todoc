---
created: 2026-11-24
updated: 2026-11-28
id: doc:state-config-types
title: "Состояние: конфигурация и типовая система"
doc_type: reference
lang: ru
source: docs/state/04-config-and-types.md
copied: true
tags: [references, reference, конфигурация, состояние]
---

# 04. Конфигурация, типы и общая схема

`todoc init --root DIR --preview` показывает план, `--apply` создаёт управляющие файлы. Данные и конфигурация лежат в DATA_ROOT. `.todoc/dataset.json` задаёт `dataset_id`, доступные форматы, пути к правилам и хранилищам типов, настройку симлинков и пределы. Файл имеет `schema_version: 1`. Актуальный объявленный набор основных параметров формируется `default_dataset()` в `src/todoc/config.py`.

| Назначение | Путь по умолчанию |
|---|---|
| Типы папок и документов | `.todoc/dir_types/`, `.todoc/doc_types/` |
| Типы записей и отношений | `.todoc/entity_types/`, `.todoc/relation_types/` |
| Правила | `.todoc/rules/directory-rules.json`, `.todoc/rules/document-rules.json` |
| Запросы | `.todoc/queries/` |
| Общая схема метаданных | `.todoc/document-metadata.schema.json` |

`type.json` описывает `type_id`, разновидность, версию и параметры типа. Дополнительные файлы могут задавать схему, шаблон и CRUD-промпты. Тип документа вычисляется по правилам и текущим данным. Явное поле `doc_type` участвует в маршрутизации при соответствующем правиле. `explain-path` показывает назначенный тип и источник решения. `types list/show/prompt/guide` читают реестр и ассеты. `types metadata` показывает нарушения общей схемы среди управляемых документов и пригоден для предпросмотра миграции.

## Изменяемый контракт документов

При `init --document-metadata --apply` устанавливается общая JSON Schema Draft 2020‑12. В демо она включена. Базовая схема требует `id`, `title`, `lang`, `created` и `updated`. `status`, `tags` и `related` объявлены отдельно. Даты имеют формат `YYYY-MM-DD`. `doc_type` является также вычисляемым селектором `--type`.

В `properties` можно добавить пользовательское поле и изменить его тип. В `required` указываются обязательные поля. Markdown и JSON-документы проверяются по этой схеме и по схеме своего типа, если она задана. Для Markdown значения YAML-lite нормализуются согласно объявленным типам. Типизированные JSON-записи с `record_id` по-прежнему используют схемы сущностей. После изменения схемы выполните `check-config`, `types metadata` и `validate --all`. `docs list --filter-fields` показывает объявленные и наблюдаемые поля нужной выборки.

[Форматы](05-formats.md) · [Запросы](07-search-and-read.md) · [Диагностики](06-validation-and-diagnostics.md)
