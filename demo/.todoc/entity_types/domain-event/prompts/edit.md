# Правка: `domain-event`

Факт домена в прошедшем времени (OrderPlaced): producer, payload-схема в репо, consumers; command — отдельно, policy — запись rule (event storming).

## Как

```bash
todoc records read --root KB --id <record_id> --output json   # прочитать текущее содержимое и схему
# внести изменения напрямую в JSON-файл записи, сохранив record_id и entity_type
todoc sync --root KB <путь-к-файлу.json>                      # обновит историю, индекс и проверит 0 диагностик
```
