# Правка: `flow`

Бизнес-флоу: актор, состояния, исходы. Истина процесса — таблица решений флоу-дока и записи правил (md — витрина).

## Как

```bash
todoc records read --root KB --id <record_id> --output json   # hash/содержимое
todoc docs edit --root KB --id <document_id> --patch-file patch.txt --preview
todoc docs edit --root KB --id <document_id> --patch-file patch.txt --apply --if-hash <hash>
```

Одна правка = один патч; после — `todoc validate --root KB --all` — 0 диагностик.
