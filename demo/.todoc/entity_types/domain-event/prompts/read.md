# Чтение: `domain-event`

Факт домена в прошедшем времени (OrderPlaced): producer, payload-схема в репо, consumers; command — отдельно, policy — запись rule (event storming).

## Как читать

```bash
todoc records list --root KB --type domain-event --output json
todoc records read --root KB --id <record_id> --view summary --output json
todoc records read --root KB --id <record_id> --output json
```

## Что читать в каком случае

- Список — projection `summary`: `past_tense_name`, `producer`.
- Связи — `relations graph --from <record_id>`; упоминания — `mentioned_in`.
