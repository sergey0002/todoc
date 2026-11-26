# Чтение: `release`

Релиз: версия, дата, сводка. Связывается affects/fixes с флоу, правилами и инцидентами.

## Как читать

```bash
todoc records list --root KB --type release --output json
todoc records read --root KB --id <record_id> --view summary --output json
todoc records read --root KB --id <record_id> --output json
```

## Что читать в каком случае

- Список/поиск — `list` + проекция `summary`: `version`, `date`.
- Детали — полная запись; связи — `relations[]` и `relations graph --from <record_id>`.
- Упоминания в md — `mentioned_in` из `records read`.
