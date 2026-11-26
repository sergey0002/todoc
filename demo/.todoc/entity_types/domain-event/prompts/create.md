# Создание: `domain-event`

Факт домена в прошедшем времени (OrderPlaced): producer, payload-схема в репо, consumers; command — отдельно, policy — запись rule (event storming).

Минимум для создания: `title`, `past_tense_name`, `producer`, `payload_ref`, `origin`.

```json
{
  "schema_version": 1,
  "record_id": "event:order-placed-v1",
  "entity_type": "domain-event",
  "title": "<title>",
  "past_tense_name": "<past_tense_name>",
  "producer": "<producer>",
  "payload_ref": "<payload_ref>",
  "origin": {
    "task": null,
    "project": null,
    "external_id": null
  },
  "relations": []
}
```

## Как создавать

1. Дедуп: `todoc records list --root KB --type domain-event --output json`.
2. Review-first:

   ```bash
   todoc records create --root KB --type domain-event --input-file draft.json --preview
   todoc records create --root KB --type domain-event --input-file draft.json --apply
   todoc validate --root KB --all   # 0 диагностик
   ```

## Правила качества

- Имя события в прошедшем времени — факт, не команда; command — отдельное поле.
- policy («когда событие → реакция») фиксируется записью rule с supersedes-версионированием.
- payload_ref обязателен: полные схемы против галлюцинаций.

## Запрещённые заглушки

- TBD/TODO/«как в задаче N». Нет данных — уточни у пользователя.

## Самопроверка

- `validate --all` — 0 диагностик; все required-поля — факты с источниками.
