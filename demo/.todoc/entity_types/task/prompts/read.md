# Чтение: `task`

Снимок задачи трекера. Снимок фиксирует состояние на момент захвата (`fetched_at`);
живая истина — в трекере. Не называть статус из снимка «текущим».

## Как читать

1. Ограничиться проектом и типом — bounded, не весь датасет:

   ```bash
   todoc records list --root KB --type task --output json
   todoc records query --root KB --query-file KB/.todoc/queries/tasks-by-project.json
   ```

2. Прочитать целиком или проекцию:

   ```bash
   todoc records read --root KB --id task:<project>-<key> --output json
   todoc records read --root KB --id task:<project>-<key> --view summary --output json
   ```

3. Комментарии и вложения — внутри записи (`comments[]`, `attachments[]`);
   даты — на момент захвата. Для актуального статуса — трекер (MCP/REST) по `jira_key`.

## Перед использованием

- `fetched_at` старше пары недель → помни, что статус/назначенец могли измениться;
  при споре — переполучить снимок из трекера.
- Вложения читаются по `path` (файл в датасете) или `url` (внешняя ссылка) —
  путь валиден только в том же корне хранилища.
