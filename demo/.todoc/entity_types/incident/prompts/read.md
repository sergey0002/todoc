# Чтение: `incident`

Разрешённый баг: симптом, причина, урок. Блеймлесс: причины — системные факторы; документ-разбор живёт отдельно (postmortem).

## Как читать

```bash
todoc records list --root KB --type incident --output json
todoc records read --root KB --id <record_id> --view summary --output json
todoc records read --root KB --id <record_id> --output json
```

## Что читать в каком случае

- Список/поиск — `list` + проекция `summary`: `title`, `verification`.
- Детали — полная запись; связи — `relations[]` и `relations graph --from <record_id>`.
- Упоминания в md — `mentioned_in` из `records read`.
