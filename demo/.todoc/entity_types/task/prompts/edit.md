# Правка: `task`

Задача — живой объект (в отличие от снимков-архивов): статусы, этапы, чек-лист
меняются по ходу работы. Правка — review-first: patch + предпросмотр + hash.

## Типичные правки

- **Смена статуса/этапа**: `status` (`open → in_progress → done` — конвенция
  проекта), `stage`. Одна правка = один патч.
- **Чек-лист**: переключение `done` у подшага, добавление новых `text`.
- **Дозаполнение Jira-полей**: после фетча из трекера (`jira_key`, `comments[]`,
  `attachments[]`, `fetched_at`).

## Как

```bash
todoc records read --root KB --id <record_id> --output json      # текущий hash/содержимое
# подготовить patch-file с построчными заменами
todoc docs edit --root KB --id <document_id> --patch-file patch.txt --preview
todoc docs edit --root KB --id <document_id> --patch-file patch.txt --apply --if-hash <hash>
todoc validate --root KB --all   # 0 диагностик
```

## Запрещено

- Менять `record_id`, `jira_key`, `source` задним числом.
- Переписывать `title` до неузнаваемости — переименование согласуется с пользователем.
- Удалять чужие комментарии и вложения.
- Закрывать задачу (`status: done`) без явного подтверждения пользователя.
