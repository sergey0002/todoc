# Правка: `export`

`export` — автособираемая витрина (`"generated": true`), генерируемая командой `todoc interop export --write`.
**Не редактируйте файлы `exports/*.md` вручную** — при следующей пересборке ручные изменения будут перезаписаны, а `todoc sync` заблокирует прямую правку с ошибкой `docs.derived_edited_directly`.

## Как обновлять правильно

1. Посмотрите список записей-источников в поле `derived_from` шапки документа.
2. Отредактируйте исходную JSON-запись напрямую и запустите `todoc sync --root KB <путь-к-записи>`.
3. Пересоберите витрину командой `todoc interop export --root KB --kind <dmn|asl|rasa> [--id <record_id>] --write exports/<name>.md`.
