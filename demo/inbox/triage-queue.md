---
id: doc:inbox-triage
title: Очередь разборки входящих
doc_type: note
lang: ru
---

# Очередь разборки входящих

Папка `inbox/` — место для неотсортированных материалов: `dir_type` присваивается правилом по basename,
`doc_type` остаётся `note`, пока материал не получит явное объявление в front matter.

## Правила разборки

1. Дать документу `doc_type` в front matter.
2. Перенести в целевую папку (типы папок не перемещают файлы сами).
3. Завести запись-документ в `records/documents/` и связать её отношением `references`.

## Связи

- [Справка: workflow](../references/workflow.md).
- [Как читать этот демо-датасет](../notes/how-to-read-this-demo.md).
