# Чтение: `bounded-context`

Граница модели DDD + свой повсеместный язык. События и эндпоинты принадлежат контексту ребром belongs_to.

## Как читать

```bash
todoc records list --root KB --type bounded-context --output json
todoc records read --root KB --id <record_id> --view summary --output json
todoc records read --root KB --id <record_id> --output json
```

## Что читать в каком случае

- Список — projection `summary`: `title`, `owner`.
- Связи — `relations graph --from <record_id>`; упоминания — `mentioned_in`.
