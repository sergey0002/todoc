# Чтение: `research`

Entity type research.

## Что делать

1. Найти запись: `todoc records list --type research --limit 20`.
2. Прочитать: `todoc records read --id <record_id> --view summary`
   (или `--view full`, когда нужны все поля).
3. Посмотреть связи: `todoc relations graph --id <record_id>`.

## На что смотреть в первую очередь

- Обязательные поля не заданы.
- `relations` — на что запись ссылается; цели проверены валидатором.
- Путь записи определяется шаблоном `records/research/{slug}.json`.

## Чего не делать

- Не угадывать `record_id`: сначала `records list`.
- Не менять запись без чтения текущей: правка идёт через hash-предусловие.
