---
created: 2026-11-24
updated: 2026-11-28
id: doc:state-search-read
title: "Состояние: поиск и чтение"
doc_type: reference
lang: ru
source: docs/state/07-search-and-read.md
copied: true
---

# 07. Обзор, поиск и чтение

`docs list` возвращает карточки документов. `docs search` ранжирует лексические совпадения и возвращает сниппет с путём и координатами. При наличии фильтров запрос можно опустить. Пустой вызов `docs search` возвращает discovery. Ранжирование учитывает структуру Markdown и теги. `docs suggest` оценивает папки по их `.config.json`. `docs tree` возвращает иерархию или плоскую страницу, `docs links` находит недоступные локальные цели.

Обе выборки отдают `doc_type` и `status` (статус жизненного цикла из front matter; `null`, если его нет). `docs list` дополнительно различает `origin`: `document` — авторский файл, `record` — JSON-зеркало из `records/documents/`. Фильтр `--origin document` оставляет только md; `--status-missing` показывает зеркала без статуса. Неизвестные `--type`/`--status` в `docs list` дают `docs.unknown_type`/`docs.unknown_status` с подсказкой.

## Фильтры метаданных

- `--type 'idea|plan'` отбирает вычисленный тип. `--file-format` отбирает формат.
- `--tag`, `--tag-in` и `--tag-all` задают совпадение тега, хотя бы одного или всех тегов. В `records list/query` доступны `--tag-in` и `--tag-all`.
- `--attr-status 'captured|planned'` и `--attr-<имя>` отбирают по полям. Внутри одного поля альтернативы объединяются. Условия по разным полям пересекаются. Неизвестный атрибут или неподходящий тип даёт `filter.invalid`.
- `--filter-file` поддерживает JSON с `schema_version: 1` и массивом `conditions`. Условие содержит `field`, `op` и `value`. Для пути подходят точечная запись и JSON Pointer. Операторы: `eq`, `in`, `has_any`, `has_all`, `exists`, `gte`, `lte`.

```json
{"schema_version":1,"conditions":[
  {"field":"created","op":"gte","value":"2026-11-01"},
  {"field":"tags","op":"has_all","value":["cli","metadata"]}
]}
```

## Чтение части источника

`docs read --id ID` разрешает идентификатор из метаданных либо `doc:<path>`. У Markdown можно использовать `--section`, `--anchor` или `--line-range A-B`. Фрагмент в ID служит альтернативой `--section`. У JSON и CSV свои селекторы формата. `--fields text` оставляет текст и обязательные координаты и хеш. Для текстового ответа `--budget N` ограничивает символы Unicode. `truncated` показывает обрезку. У `docs search` `--budget N` считает UTF-8 байты элементов результата без конверта и отдаёт `data.meta.budget` с `limit`, `used_bytes`, `exhausted`; слишком малый лимит даёт пустой список с `exhausted: true`. Начало `--line-range` за концом файла даёт `usage.invalid_line_range`; конец за концом обрезается. Ответ с `--line-range` содержит `line_total`. `docs flow render` строит текстовую витрину, а `docs flow walk` выдаёт прохождение дерева.

`data.meta.complete` позволяет отличить пустую выборку от неполной. `next_cursor` связан с запросом и отпечатком источников. После изменения корпуса начните с первой страницы.

[Контракт CLI](03-cli-reference.md) · [Форматы](05-formats.md) · [Снимок индекса](09-storage-and-index.md)
