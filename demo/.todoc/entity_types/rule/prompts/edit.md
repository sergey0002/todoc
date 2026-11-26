# Правка: `rule`

Бизнес-правило с примерами-тестами: проверяемая формулировка {given/when/then}; версии append-only (supersedes).

- **Запись версионная/снимок**: не редактируется. Новая версия — новая запись (`-vN+1` + `supersedes` у правила; новый fetched_at у снимка).

## Как

```bash
todoc records read --root KB --id <record_id> --output json   # hash/содержимое
todoc docs edit --root KB --id <document_id> --patch-file patch.txt --preview
todoc docs edit --root KB --id <document_id> --patch-file patch.txt --apply --if-hash <hash>
```

Одна правка = один патч; после — `todoc validate --root KB --all` — 0 диагностик.
