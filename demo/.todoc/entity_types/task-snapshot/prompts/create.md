# Создание: `task-snapshot`

Снимок задачи Jira: живая истина — в трекере; origin.task — поле, не ребро (связки, не копии).

Минимум для создания: `title`, `jira_key`, `status_at_fetch`, `url`, `fetched_at`, `origin`.

```json
{
  "schema_version": 1,
  "record_id": "task-snapshot:KEY-1",
  "entity_type": "task-snapshot",
  "title": "<title>",
  "jira_key": "<jira_key>",
  "status_at_fetch": "<status_at_fetch>",
  "url": "<url>",
  "fetched_at": "<fetched_at>",
  "origin": {
    "task": null,
    "project": null,
    "external_id": null
  },
  "relations": []
}
```

## Как создавать

1. Дедуп: `todoc records list --root KB --type task-snapshot --output json` — нет ли записи с тем же смыслом.
2. Review-first:

   ```bash
   todoc records create --root KB --type task-snapshot --input-file draft.json --preview
   todoc records create --root KB --type task-snapshot --input-file draft.json --apply
   todoc validate --root KB --all   # 0 диагностик
   ```

## Правила качества

- Снимок не редактируется: изменился трекер — новый снимок с новым fetched_at.
- status_at_fetch — статус в момент снимка, не «живой» статус.
- Связь с задачей-оригиналом — origin.task, не ребро.

## Запрещённые заглушки

- TBD/TODO/«как в задаче N»/«будем уточнять» — не записывать. Нет данных — уточни у пользователя, не выдумывай.

## Самопроверка

- `todoc validate --root KB --all` — 0 диагностик; `records read --id <record_id>` читает запись.
- Все required-поля заполнены фактами; каждое утверждение имеет источник (origin/ссылка).
