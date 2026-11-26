# Правка: `spec-doc`

Правка — review-first: patch + предпросмотр + hash. Обязательные секции не удаляются:
`## Требования`, `## Сценарии`, `## Открытые вопросы`.

## Как

```bash
todoc docs read --root KB --id doc:<id> --output json       # hash
todoc docs edit --root KB --id doc:<id> --patch-file patch.txt --preview
todoc docs edit --root KB --id doc:<id> --patch-file patch.txt --apply --if-hash <hash>
```

После — `todoc validate --root KB --all` — 0 диагностик; чтение назад — `docs read --section`.
