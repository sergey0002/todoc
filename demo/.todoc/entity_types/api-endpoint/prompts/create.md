# Создание: `api-endpoint`

Операция контракта API: method+path, auth, ошибки. Проекция человекочитаемой карты — истина спецификации в репозитории сервиса (spec_url), не копия (D8).

Минимум для создания: `title`, `method`, `path`, `auth`, `errors`.

```json
{
  "schema_version": 1,
  "record_id": "api-endpoint:orders:post:/orders",
  "entity_type": "api-endpoint",
  "title": "<title>",
  "method": "<method>",
  "path": "<path>",
  "auth": "<auth>",
  "errors": [
    {
      "code": "<код>"
    }
  ],
  "relations": []
}
```

## Как создавать

1. Дедуп: `todoc records list --root KB --type api-endpoint --output json`.
2. Review-first:

   ```bash
   todoc records create --root KB --type api-endpoint --input-file draft.json --preview
   todoc records create --root KB --type api-endpoint --input-file draft.json --apply
   todoc validate --root KB --all   # 0 диагностик
   ```

## Правила качества

- Связки, не копии: при наличии репо сервиса spec_url обязателен; машинную схему читают из источника.
- record_id: api-endpoint:<сервис>:<method>:<path> — path маленькими, плейсхолдеры в {}.
- errors — фактические коды контракта, не пожелания.

## Запрещённые заглушки

- TBD/TODO/«как в задаче N». Нет данных — уточни у пользователя.

## Самопроверка

- `validate --all` — 0 диагностик; все required-поля — факты с источниками.
