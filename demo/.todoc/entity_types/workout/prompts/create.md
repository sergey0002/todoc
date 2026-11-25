# Создание: `workout`

Entity type workout.

## Как создавать

1. Взять стартовый шаблон: `.todoc/entity_types/workout/template.json`.
2. Подготовить входной файл и создать запись (create-only):
   `todoc records create --type workout --input-file <file.json> --preview`,
   затем то же с `--apply`.
3. Путь файла определит тип: `records/workout/{slug}.json`.

## Обязательные поля

Обязательные поля не заданы — сверьтесь с JSON Schema в `.todoc/schemas/records/`.

## После создания

- `todoc validate --all` — 0 диагностик.
- Отношения указывайте существующими `record_id`: иначе будет `relation.dangling_target`.

## Чего не делать

- Не писать JSON прямо в DATA_ROOT: любой `.json` с `record_id` станет записью.
- Не рассчитывать на перезапись: существующий `record_id` даёт `record.duplicate_id` и exit 5.
