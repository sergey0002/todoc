# Правка: `runbook`

Правка — review-first: patch + предпросмотр + hash. Обязательные секции не удаляются:
`## Симптом`, `## Воздействие`, `## Диагностика`, `## Митигация`, `## Проверка`, `## Эскалация`, `## Не делать`.

## Как

```bash
todoc docs read --root KB --id doc:<id> --output json
todoc docs edit --root KB --id doc:<id> --patch-file patch.txt --preview
todoc docs edit --root KB --id doc:<id> --patch-file patch.txt --apply --if-hash <hash>
```

После — `validate --all` — 0 диагностик; чтение назад — `docs read --section`.
