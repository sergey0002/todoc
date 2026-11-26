# Создание: `flow`

Бизнес-флоу: актор, состояния, исходы. Истина процесса — таблица решений флоу-дока и записи правил (md — витрина).

Минимум для создания: `title`, `actor`, `states`, `outcomes`.

```json
{
  "schema_version": 1,
  "record_id": "flow:<slug>",
  "entity_type": "flow",
  "title": "<title>",
  "actor": "<actor>",
  "states": [
    "<...>"
  ],
  "outcomes": [
    "<...>"
  ],
  "relations": []
}
```

## Как создавать

1. Дедуп: `todoc records list --root KB --type flow --output json` — нет ли записи с тем же смыслом.
2. Review-first:

   ```bash
   todoc records create --root KB --type flow --input-file draft.json --preview
   todoc records create --root KB --type flow --input-file draft.json --apply
   todoc validate --root KB --all   # 0 диагностик
   ```

## Правила качества

- Актор — роль, исполняющая флоу, не система («покупатель», не «API»).
- Состояния — существительные состояния процесса; первый элемент — старт.
- Исходы покрывают и успех, и коды ошибок из таблицы решений.

## Запрещённые заглушки

- TBD/TODO/«как в задаче N»/«будем уточнять» — не записывать. Нет данных — уточни у пользователя, не выдумывай.

## Самопроверка

- `todoc validate --root KB --all` — 0 диагностик; `records read --id <record_id>` читает запись.
- Все required-поля заполнены фактами; каждое утверждение имеет источник (origin/ссылка).
