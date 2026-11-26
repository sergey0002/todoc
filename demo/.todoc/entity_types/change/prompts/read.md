# Чтение: `change`

Изменение живёт в `changes/<slug>/`: запись + proposal/tasks (fm note) + deltas/.

## Как читать

```bash
todoc change list --root KB --output json
todoc change show --root KB --id change:<slug> --output json
todoc docs read --root KB --path changes/<slug>/proposal.md
```

## Что читать в каком случае

- «что в работе» — `change list` + `status` (proposed/in_progress/blocked).
- «почему» — `proposal.md`; «что делать» — `tasks.md`; «дельта требований» —
  `requirements_delta` записи и файлы `deltas/`.
