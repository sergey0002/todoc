# Удаление: `term`

Удаление термина — операция с последствиями: glossary-страница-витрина остаётся,
а рёбра `part_of`/`uses_term` и упоминания md теряют цель.

## Как

```bash
todoc records read --root KB --id term:<slug> --output json   # hash + mentioned_in
todoc records create --root KB --type term --input-file draft.json --preview
```

Прямой команды `records delete` нет; удаление — review-first операция уровня
датасета: убрать файл записи из `records/terms/<slug>.json` (вручную, одним
изменением), затем `todoc validate --root KB --all` — 0 диагностик.

## Правила

- Перед удалением — проверить `mentioned_in` и рёбра `uses_term`/`part_of`:
  consumers сначала перевести на другой термин или удалить ребро.
- Витрина `glossary/<slug>.md` удаляется/обновляется тем же изменением:
  глоссарий без записи или запись без витрины — рассинхрон.
