# Создание: `task`

Снимок задачи Jira в JSON. Create-only: перезапись запрещена; обновление снимка =
новая версия записи (по конвенции датасета) или новый снимок с новым `fetched_at` в
задаче-коллекции. Ничего не выдумывать: все поля — из ответа трекера.

## Перед созданием

1. Дедуп: `todoc records list --root KB --type task --output json` — задача с этим
   `jira_key` уже есть? Тогда обновлять существующий снимок по ревью, не плодить дубль.
2. Определить проект хранилища (папка `tasks/<project>/` или текущий проект из
   `.todoc/state/current-project.json` — см. идею folder-config).

## Как создавать

1. Взять шаблон: `.todoc/entity_types/task/template.json`.
2. Заполнить поля из ответа API трекера:
   - скаляры — как есть (`status_at_fetch`, `priority`, `assignee`, `story_points`);
   - `description` и `comments[].body` — текст как есть, без пересказа;
   - `fetched_at` — момент захвата UTC, не дата правки;
   - `record_id` — `task:<project>-<key>`, slug = `<project>-<key>`.
3. Вложения: сохранить файлы в `attachments/tasks/<PROJECT>-<key>/<имя>` и указать
   относительный `path`; при отказе от скачивания — только `url` и `mime`.
4. Связи: `belongs_to` на запись проекта, `blocks`/`blocks_by` на другие задачи,
   `documents` на флоу/правила, затронутые задачей.
5. Создать (review-first):

   ```bash
   todoc records create --root KB --type task --input-file draft.json --preview
   todoc records create --root KB --type task --input-file draft.json --apply
   todoc validate --root KB --all   # 0 диагностик: relation.*, record.schema_violation
   ```

## Правила качества

- JSON только строгий: дубли ключей и NaN отклоняются парсером датасета.
- Комментарии не суммаризировать — сохранять как есть (это архив, не выжимка).
- Не хранить секреты/токены из описаний; при обнаружении — маскировать и сообщить.
