# Создание: `plan`

Entity type plan.

## Как создавать

1. Взять стартовый шаблон: `.todoc/entity_types/plan/template.json`.
2. Подготовить входной файл и создать запись (create-only):
   `todoc records create --type plan --input-file <file.json> --preview`,
   затем то же с `--apply`.
3. Путь файла определит тип: `records/plan/{slug}.json`. Дальнейшие точечные правки созданного
   JSON-файла можно делать напрямую в файле с последующим `todoc sync --root KB <путь>`.

## Обязательные поля

Обязательные поля не заданы — сверьтесь со схемой `.todoc/entity_types/plan/schema.json`.

## После создания

- `todoc validate --all` — 0 диагностик.
- Отношения указывайте существующими `record_id`: иначе будет `relation.dangling_target`.

## Чего не делать

- Не рассчитывать на перезапись при `records create`: существующий `record_id` даёт `record.duplicate_id` и exit 5.
