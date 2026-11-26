# Чтение: `dependency`

Внешняя система/сервис/очередь, от которой зависим; направление и критичность — вход в runbook и анализ отказов.

## Как читать

```bash
todoc records list --root KB --type dependency --output json
todoc records read --root KB --id <record_id> --view summary --output json
todoc records read --root KB --id <record_id> --output json
```

## Что читать в каком случае

- Список — projection `summary`: `kind`, `criticality`.
- Связи — `relations graph --from <record_id>`; упоминания — `mentioned_in`.
