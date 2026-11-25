# Чтение: `task`

Задача может быть простым TODO (только заголовок) или полным снимком Jira.
Формат читается по наличию полей.

## Как читать

```bash
todoc records list --root KB --type task --output json            # список дел
todoc records query --root KB --query-file KB/.todoc/queries/tasks-by-project.json
todoc records read --root KB --id task:<slug> --view summary --output json
todoc records read --root KB --id task:<slug> --output json        # целиком
```

## Что читать в каком случае

- **TODO-list**: список → `title`, `status`, `source` (проекция `summary`).
- **Снимок Jira**: поля `jira_*`/`comments`/`attachments` заполнены →
  `fetched_at` — момент снимка; живой статус — в трекере по `jira_key`, не из записи.
- Комментарии и вложения — внутри записи; путь вложения валиден в том же корне.

## Типичные вопросы

- «что в работе?» → list + фильтр по `status` (конвенция проекта);
- «откуда задача?» → поле `source` (`user` — поставлена в чате);
- «что внутри?» → `description` + `checklist[]` (подшаги с `done`).
