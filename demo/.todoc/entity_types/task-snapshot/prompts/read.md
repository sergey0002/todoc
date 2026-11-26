# Чтение: `task-snapshot`

Снимок задачи Jira: живая истина — в трекере; origin.task — поле, не ребро (связки, не копии).

## Как читать

```bash
todoc records list --root KB --type task-snapshot --output json
todoc records read --root KB --id <record_id> --view summary --output json
todoc records read --root KB --id <record_id> --output json
```

## Что читать в каком случае

- Список/поиск — `list` + проекция `summary`: `jira_key`, `status_at_fetch`.
- Детали — полная запись; связи — `relations[]` и `relations graph --from <record_id>`.
- Упоминания в md — `mentioned_in` из `records read`.
