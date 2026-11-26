# Правка: `dependency`

Внешняя система/сервис/очередь, от которой зависим; направление и критичность — вход в runbook и анализ отказов.

## Как

```bash
todoc records read --root KB --id <record_id> --output json
todoc docs edit --root KB --id <document_id> --patch-file patch.txt --preview
todoc docs edit --root KB --id <document_id> --patch-file patch.txt --apply --if-hash <hash>
```

Одна правка = один патч; после — `validate --all` — 0 диагностик.
