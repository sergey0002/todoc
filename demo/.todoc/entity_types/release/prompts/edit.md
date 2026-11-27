# Правка: `release`

Релиз: версия, дата, сводка. Связывается affects/fixes с флоу, правилами и инцидентами.

## Как

```bash
todoc records read --root KB --id <record_id> --output json   # прочитать текущее содержимое и схему
# внести изменения напрямую в JSON-файл записи, сохранив record_id и entity_type
todoc sync --root KB <путь-к-файлу.json>                      # обновит историю, индекс и проверит 0 диагностик
```
