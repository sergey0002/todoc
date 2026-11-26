# Чтение: `flow`

Бизнес-флоу: актор, состояния, исходы. Истина процесса — таблица решений флоу-дока и записи правил (md — витрина).

## Как читать

```bash
todoc records list --root KB --type flow --output json
todoc records read --root KB --id <record_id> --view summary --output json
todoc records read --root KB --id <record_id> --output json
```

## Что читать в каком случае

- Список/поиск — `list` + проекция `summary`: `title`, `actor`.
- Детали — полная запись; связи — `relations[]` и `relations graph --from <record_id>`.
- Упоминания в md — `mentioned_in` из `records read`.
