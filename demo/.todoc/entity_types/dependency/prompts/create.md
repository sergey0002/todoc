# Создание: `dependency`

Внешняя система/сервис/очередь, от которой зависим; направление и критичность — вход в runbook и анализ отказов.

Минимум для создания: `title`, `kind`, `criticality`, `origin`.

```json
{
  "schema_version": 1,
  "record_id": "dep:payment-gateway",
  "entity_type": "dependency",
  "title": "<title>",
  "kind": "<kind>",
  "criticality": "<criticality>",
  "origin": {
    "task": null,
    "project": null,
    "external_id": null
  },
  "relations": []
}
```

## Как создавать

1. Дедуп: `todoc records list --root KB --type dependency --output json`.
2. Review-first:

   ```bash
   todoc records create --root KB --type dependency --input-file draft.json --preview
   todoc records create --root KB --type dependency --input-file draft.json --apply
   todoc validate --root KB --all   # 0 диагностик
   ```

## Правила качества

- criticality — влияние отказа на флоу, не важность вендора.

## Запрещённые заглушки

- TBD/TODO/«как в задаче N». Нет данных — уточни у пользователя.

## Самопроверка

- `validate --all` — 0 диагностик; все required-поля — факты с источниками.
