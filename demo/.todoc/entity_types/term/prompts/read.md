# Чтение: `term`

## Как читать

```bash
todoc records list --root KB --type term --output json              # весь глоссарий
todoc records read --root KB --id term:<slug> --view summary --output json
todoc records read --root KB --id term:<slug> --output json         # целиком
todoc docs read --root KB --path glossary/<slug>.md                 # витрина-страница
todoc relations tree --root KB --from term:<slug>                   # иерархия и uses_term
```

## Что читать в каком случае

- **Что значит слово** — `definition` (+ `source_path` для полной витрины).
- **Как ещё это называют** — `aliases[]`.
- **Где используется** — `mentioned_in` в `records read` (vitрины и упоминания md)
  и рёбра `uses_term` (у flows/rules/incidents/release/change/api-endpoint/domain-event).
- **Над чем стоит** — `part_of` (term → term), дерево `relations tree`.
