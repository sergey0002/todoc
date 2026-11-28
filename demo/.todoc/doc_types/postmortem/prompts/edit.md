# Правка: `postmortem`

Правка — прямая правка файла с обязательной финализацией `todoc sync`. Обязательные секции не удаляются:
`## Summary`, `## Impact`, `## Timeline`, `## Contributing factors`, `## What went well`, `## Action items`.

## Как

```bash
todoc docs read --root KB --id doc:<id> --output json   # при необходимости прочитать секцию/hash
# внести изменения напрямую в .md-файл (не трогая created и updated)
todoc sync --apply --root KB <путь-к-файлу.md>                  # обновит updated, историю, индекс и проверит 0 диагностик
```

> **Даты и связи:** поле `updated` во front matter бампит движок при `todoc sync` — руками не трогать. Связал документ с другим — добавь/обнови `related`-wikilink (`[[имя-без-.md]]`).
