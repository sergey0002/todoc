# Правка: `change`

Статусы ведёт движок (`change apply/close/blocked`); ручная правка — для
`requirements_delta`, описательных полей и `artifacts`.

## Как

```bash
todoc records read --root KB --id change:<slug> --output json   # hash/содержимое
todoc docs edit --root KB --id <document_id> --patch-file patch.txt --preview
todoc docs edit --root KB --id <document_id> --patch-file patch.txt --apply --if-hash <hash>
```

Одна правка = один патч; после — `todoc validate --root KB --all` — 0 диагностик.
`created_at`/`applied_at` руками не трогаются — их ведут команды движка.
