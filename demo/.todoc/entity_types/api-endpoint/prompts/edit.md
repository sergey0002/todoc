# Правка: `api-endpoint`

Операция контракта API: method+path, auth, ошибки. Проекция человекочитаемой карты — истина спецификации в репозитории сервиса (spec_url), не копия (D8).

## Как

```bash
todoc records read --root KB --id <record_id> --output json   # прочитать текущее содержимое и схему
# внести изменения напрямую в JSON-файл записи, сохранив record_id и entity_type
todoc sync --root KB <путь-к-файлу.json>                      # обновит историю, индекс и проверит 0 диагностик
```
