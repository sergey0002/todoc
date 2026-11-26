# Правка: `api-endpoint`

Операция контракта API: method+path, auth, ошибки. Проекция человекочитаемой карты — истина спецификации в репозитории сервиса (spec_url), не копия (D8).

## Как

```bash
todoc records read --root KB --id <record_id> --output json
todoc docs edit --root KB --id <document_id> --patch-file patch.txt --preview
todoc docs edit --root KB --id <document_id> --patch-file patch.txt --apply --if-hash <hash>
```

Одна правка = один патч; после — `validate --all` — 0 диагностик.
