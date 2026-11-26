# Создание: `release`

Релиз: версия, дата, сводка. Связывается affects/fixes с флоу, правилами и инцидентами.

Минимум для создания: `version`, `date`, `summary`, `origin`.

```json
{
  "schema_version": 1,
  "record_id": "release:0.1.0",
  "entity_type": "release",
  "version": "<version>",
  "date": "<date>",
  "summary": "<summary>",
  "origin": {
    "task": null,
    "project": null,
    "external_id": null
  },
  "relations": []
}
```

## Как создавать

1. Дедуп: `todoc records list --root KB --type release --output json` — нет ли записи с тем же смыслом.
2. Review-first:

   ```bash
   todoc records create --root KB --type release --input-file draft.json --preview
   todoc records create --root KB --type release --input-file draft.json --apply
   todoc validate --root KB --all   # 0 диагностик
   ```

## Правила качества

- version = semver записи; дата — фактическая дата релиза (UTC).
- Сводка — что изменилось для пользователя, не diff.
- Инциденты связываются ребром fixes, затронутые флоу/правила — affects.

## Запрещённые заглушки

- TBD/TODO/«как в задаче N»/«будем уточнять» — не записывать. Нет данных — уточни у пользователя, не выдумывай.

## Самопроверка

- `todoc validate --root KB --all` — 0 диагностик; `records read --id <record_id>` читает запись.
- Все required-поля заполнены фактами; каждое утверждение имеет источник (origin/ссылка).
