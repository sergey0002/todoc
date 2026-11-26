# Чтение: `api-endpoint`

Операция контракта API: method+path, auth, ошибки. Проекция человекочитаемой карты — истина спецификации в репозитории сервиса (spec_url), не копия (D8).

## Как читать

```bash
todoc records list --root KB --type api-endpoint --output json
todoc records read --root KB --id <record_id> --view summary --output json
todoc records read --root KB --id <record_id> --output json
```

## Что читать в каком случае

- Список — projection `summary`: `method`, `path`, `auth`.
- Связи — `relations graph --from <record_id>`; упоминания — `mentioned_in`.
