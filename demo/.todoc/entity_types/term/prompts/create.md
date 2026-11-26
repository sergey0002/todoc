# Создание: `term`

Термин глоссария — запись-словарная единица. Определение берётся из glossary-страницы
(`source_path`), не выдумывается. Минимум: `title`, `term_type`, `definition`.

## Как создавать

1. Дедуп: `todoc records list --root KB --type term --output json` — нет ли термина
   с тем же slug/алиасом.
2. Черновик в `/tmp`, review-first:

   ```bash
   todoc records create --root KB --type term --input-file draft.json --preview
   todoc records create --root KB --type term --input-file draft.json --apply
   todoc validate --root KB --all   # 0 диагностик
   ```

## Правила качества

- `record_id` — `term:<slug>`; slug совпадает с именем glossary-страницы
  (glossary/<slug>.md), латиница, дефисы, без заглавных.
- `term_type` — из перечня: actor, role, system, component, event, rule, field,
  external, concept.
- `definition` — формулировка из glossary-страницы (сжатая, но та же мысль).
- `aliases` — фактические варианты имени (в т.ч. латинские из заголовка страницы).
- `artifacts` — только файлы, явно названные в определении; нет факта — пустой массив.
- `part_of` — только когда иерархия следует из определений, не достраивать.
