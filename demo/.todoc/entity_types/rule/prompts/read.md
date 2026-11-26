# Чтение: `rule`

Бизнес-правило с примерами-тестами: проверяемая формулировка {given/when/then}; версии append-only (supersedes).

## Как читать

```bash
todoc records list --root KB --type rule --output json
todoc records read --root KB --id <record_id> --view summary --output json
todoc records read --root KB --id <record_id> --output json
```

## Что читать в каком случае

- Список/поиск — `list` + проекция `summary`: `statement`, `status`.
- Детали — полная запись; связи — `relations[]` и `relations graph --from <record_id>`.
- Упоминания в md — `mentioned_in` из `records read`.
