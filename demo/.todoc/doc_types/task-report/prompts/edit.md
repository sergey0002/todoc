# Правка: `task-report`

Правка — review-first: patch + предпросмотр + hash. Обязательные секции не удаляются:
`## Задача`, `## Зачем`, `## Что изменилось`, `## Как проверялось`, `## Риски и уроки`.

## Как

```bash
todoc docs read --root KB --id doc:<id> --output json       # hash
todoc docs edit --root KB --id doc:<id> --patch-file patch.txt --preview
todoc docs edit --root KB --id doc:<id> --patch-file patch.txt --apply --if-hash <hash>
```

После — `todoc validate --root KB --all` — 0 диагностик; чтение назад — `docs read --section`.
