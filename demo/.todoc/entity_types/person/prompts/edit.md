# Правка: `person`

Entity type person.

## Как править

1. `todoc records read --id <record_id> --view full` — запомнить текущее содержимое и `hash`.
2. Изменить копию JSON, сохранив `record_id` и `entity_type`.
3. Удалить старый файл и создать новый через
   `todoc records create --type person --input-file <file.json> --preview`, затем `--apply`.
   Записи создаются, а не перезаписываются — это намеренно.

## Что нельзя ломать

- Обязательные поля не заданы.
- `record_id`: на него ссылаются отношения других записей.
- Единицы измерений в числовых полях: смешение единиц ломает `records aggregate`.

## После правки

- `todoc validate --all` — 0 диагностик.
- `todoc relations graph --id <record_id>` — связи не оборвались.
