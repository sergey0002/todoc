# Создание: `rule`

Бизнес-правило с примерами-тестами: проверяемая формулировка {given/when/then}; версии append-only (supersedes).

Минимум для создания: `title`, `statement`, `examples`, `status`, `origin`.

```json
{
  "schema_version": 1,
  "record_id": "rule:<имя>-v<N>",
  "entity_type": "rule",
  "title": "<title>",
  "statement": "<statement>",
  "examples": [
    {
      "given": "<контекст>",
      "when": "<условие>",
      "then": "<результат>"
    }
  ],
  "status": "<status>",
  "origin": {
    "task": null,
    "project": null,
    "external_id": null
  },
  "relations": []
}
```

## Как создавать

1. Дедуп: `todoc records list --root KB --type rule --output json` — нет ли записи с тем же смыслом.
2. Правило версионное: меняется активное правило — новая запись `-vN+1` + ребро `supersedes` (см. Правила качества).
3. Review-first:

   ```bash
   todoc records create --root KB --type rule --input-file draft.json --preview
   todoc records create --root KB --type rule --input-file draft.json --apply
   todoc validate --root KB --all   # 0 диагностик
   ```

## Правила качества

- Формулировка проверяемая: условия и результат, не «держи консистентно».
- Версия append-only: новая версия = новая запись -vN+1 + ребро supersedes; существующую не редактировать.
- Минимум один пример {given, when, then}; с кодом ошибки — если правило даёт отказ.

## Запрещённые заглушки

- TBD/TODO/«как в задаче N»/«будем уточнять» — не записывать. Нет данных — уточни у пользователя, не выдумывай.

## Самопроверка

- `todoc validate --root KB --all` — 0 диагностик; `records read --id <record_id>` читает запись.
- Все required-поля заполнены фактами; каждое утверждение имеет источник (origin/ссылка).
