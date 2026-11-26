# Создание: `bounded-context`

Граница модели DDD + свой повсеместный язык. События и эндпоинты принадлежат контексту ребром belongs_to.

Минимум для создания: `title`, `language`, `owner`.

```json
{
  "schema_version": 1,
  "record_id": "context:orders",
  "entity_type": "bounded-context",
  "title": "<title>",
  "language": [
    "<термин>"
  ],
  "owner": "<owner>",
  "relations": []
}
```

## Как создавать

1. Дедуп: `todoc records list --root KB --type bounded-context --output json`.
2. Review-first:

   ```bash
   todoc records create --root KB --type bounded-context --input-file draft.json --preview
   todoc records create --root KB --type bounded-context --input-file draft.json --apply
   todoc validate --root KB --all   # 0 диагностик
   ```

## Правила качества

- language — термины, которые в этом контексте значат ровно одно; расхождения между контекстами фиксируются здесь.
- Граница — по языку и владению данными, не по оргструктуре.

## Запрещённые заглушки

- TBD/TODO/«как в задаче N». Нет данных — уточни у пользователя.

## Самопроверка

- `validate --all` — 0 диагностик; все required-поля — факты с источниками.
