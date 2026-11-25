# Создание: `person`

Entity type person.

## Как создавать

1. Взять стартовый шаблон: `.todoc/entity_types/person/template.json`.
2. Подготовить входной файл и создать запись (create-only):
   `todoc records create --type person --input-file <file.json> --preview`,
   затем то же с `--apply`.
3. Путь файла определит тип: `records/person/{slug}.json`.

## Обязательные поля

Обязательные поля не заданы — сверьтесь со схемой `.todoc/entity_types/person/schema.json`.

## После создания

- `todoc validate --all` — 0 диагностик.
- Отношения указывайте существующими `record_id`: иначе будет `relation.dangling_target`.

## Чего не делать

- Не писать JSON прямо в DATA_ROOT: любой `.json` с `record_id` станет записью.
- Не рассчитывать на перезапись: существующий `record_id` даёт `record.duplicate_id` и exit 5.
