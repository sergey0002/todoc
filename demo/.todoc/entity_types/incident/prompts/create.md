# Создание: `incident`

Разрешённый баг: симптом, причина, урок. Блеймлесс: причины — системные факторы; документ-разбор живёт отдельно (postmortem).

Минимум для создания: `title`, `symptom`, `root_cause`, `lesson`, `origin`.

```json
{
  "schema_version": 1,
  "record_id": "incident:<slug>",
  "entity_type": "incident",
  "title": "<title>",
  "symptom": "<symptom>",
  "root_cause": "<root_cause>",
  "lesson": "<lesson>",
  "origin": {
    "task": null,
    "project": null,
    "external_id": null
  },
  "relations": []
}
```

## Как создавать

1. Дедуп: `todoc records list --root KB --type incident --output json` — нет ли записи с тем же смыслом.
2. Review-first:

   ```bash
   todoc records create --root KB --type incident --input-file draft.json --preview
   todoc records create --root KB --type incident --input-file draft.json --apply
   todoc validate --root KB --all   # 0 диагностик
   ```

## Правила качества

- Симптом наблюдаем, причина системна («не хватает проверки X в CI», не «забыл Вася»).
- Урок — действие/правило, а не сожаление.
- Фикс связывается ребром fixes от release-записи, когда релиз выйдет.

## Запрещённые заглушки

- TBD/TODO/«как в задаче N»/«будем уточнять» — не записывать. Нет данных — уточни у пользователя, не выдумывай.

## Самопроверка

- `todoc validate --root KB --all` — 0 диагностик; `records read --id <record_id>` читает запись.
- Все required-поля заполнены фактами; каждое утверждение имеет источник (origin/ссылка).
