# Чтение: `document`

Документ датасета: метаданные файла с типом и связями.

## Что делать

1. Найти запись: `todoc records list --type document --limit 20`.
2. Прочитать: `todoc records read --id <record_id> --view summary`
   (или `--view full`, когда нужны все поля).
3. Посмотреть связи: `todoc relations graph --id <record_id>`.

## На что смотреть в первую очередь

- Обязательные поля: `record_id`, `entity_type`, `title`, `source_path`, `doc_type`.
- `relations` — на что запись ссылается; цели проверены валидатором.
- Путь записи определяется шаблоном `records/documents/{slug}.json`.

## Чего не делать

- Не угадывать `record_id`: сначала `records list`.
- Не менять запись без чтения текущей: правка идёт через hash-предусловие.
