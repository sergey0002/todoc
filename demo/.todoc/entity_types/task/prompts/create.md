# Создание: `task`

Задача — запись-дело. Минимум для создания: заголовок (`title`). Всё остальное —
опционально и добавляется по мере появления. Ничего не выдумывать: нет данных —
поле не пишется.

## Быстрый кейс: TODO из чата

Пользователь сказал «запиши задачу: …» — создаются только:

```json
{
  "schema_version": 1,
  "record_id": "task:<slug>",
  "entity_type": "task",
  "title": "<постановка пользователя>",
  "source": "user",
  "status": "open",
  "relations": []
}
```

`source` — свободный текст об источнике; значение по умолчанию `user` (задача
поставлена пользователем в чате). Для задач из других каналов — `jira`, `telegram`,
`email`, `звонок <дата>` — как сказал пользователь.

## Расширенный кейс: снимок Jira

При выгрузке из трекера заполняются поля Jira (`jira_key`, `issue_type`, `assignee`,
`reporter`, `labels`, `components`, `fix_versions`, `story_points`, `description`,
`updated`, `url`, `fetched_at`, `comments[]`, `attachments[]`). Сопоставление с
REST v3: `summary→title`, `status.name→status`, `duedate→due`, комментарий —
`{author, created, body}` как есть, вложение — `{name, path, mime, url}`
(`path: attachments/tasks/<key>/<имя>` при скачивании).

## Как создавать

1. Дедуп: `todoc records list --root KB --type task --output json` — нет ли задачи
   с тем же заголовком/jira_key.
2. Проект задачи — поле `origin.project` (строка); в пути сейчас не участвует: движок подставляет только `{record_id}`/`{slug}` — группировка по проектам через origin-поле и запросы до расширения path_template.
3. Create-only, review-first:

   ```bash
   todoc records create --root KB --type task --input-file draft.json --preview
   todoc records create --root KB --type task --input-file draft.json --apply
   todoc validate --root KB --all   # 0 диагностик
   ```

## Правила качества

- Заголовок — глагол + объект («Проверить экспорт задач»), не «баг».
- Статусы — по конвенции датасета/проекта (по умолчанию `open`); этапы — `stage`.
- Чек-лист подшагов: `checklist[]` с `{text, done}` — для задач с этапами.
- Секреты из текста — маскировать и сообщить пользователю.
