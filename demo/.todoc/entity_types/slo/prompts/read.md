# Чтение: `slo`

Целевой уровень сервиса: SLI, цель, окно измерения. Истина — контракт сервиса; запись связывает обязательство с документацией.

## Как читать

```bash
todoc records list --root KB --type slo --output json
todoc records read --root KB --id <record_id> --view summary --output json
todoc records read --root KB --id <record_id> --output json
```

## Что читать в каком случае

- Список — projection `summary`: `indicator`, `target`.
- Связи — `relations graph --from <record_id>`; упоминания — `mentioned_in`.
