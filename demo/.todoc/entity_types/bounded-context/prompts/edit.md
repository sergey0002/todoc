# Правка: `bounded-context`

Граница модели DDD + свой повсеместный язык. События и эндпоинты принадлежат контексту ребром belongs_to.

## Как

```bash
todoc records read --root KB --id <record_id> --output json
todoc docs edit --root KB --id <document_id> --patch-file patch.txt --preview
todoc docs edit --root KB --id <document_id> --patch-file patch.txt --apply --if-hash <hash>
```

Одна правка = один патч; после — `validate --all` — 0 диагностик.
