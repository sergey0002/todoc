# Удаление: `incident`

Прямой команды `records delete` нет; удаление — review-first операция уровня датасета: убрать файл
`records/incidents/<slug>.json` одним изменением, затем `todoc validate --root KB --all` — 0 диагностик.

## Правила

- Перед удалением проверить `mentioned_in` и `relations graph --from <record_id>`: consumers перевести раньше.
- У правила — только при `status: rejected` или подмене новой версией; активное правило не удаляется.
