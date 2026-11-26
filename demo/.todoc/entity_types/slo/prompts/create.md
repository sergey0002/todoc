# Создание: `slo`

Целевой уровень сервиса: SLI, цель, окно измерения. Истина — контракт сервиса; запись связывает обязательство с документацией.

Минимум для создания: `title`, `indicator`, `target`, `window`, `origin`.

```json
{
  "schema_version": 1,
  "record_id": "slo:orders-availability",
  "entity_type": "slo",
  "title": "<title>",
  "indicator": "<indicator>",
  "target": "<target>",
  "window": "<window>",
  "origin": {
    "task": null,
    "project": null,
    "external_id": null
  },
  "relations": []
}
```

## Как создавать

1. Дедуп: `todoc records list --root KB --type slo --output json`.
2. Review-first:

   ```bash
   todoc records create --root KB --type slo --input-file draft.json --preview
   todoc records create --root KB --type slo --input-file draft.json --apply
   todoc validate --root KB --all   # 0 диагностик
   ```

## Правила качества

- Цель измерима; окно указано; «стремимся к 99%» без окна — не SLO.

## Запрещённые заглушки

- TBD/TODO/«как в задаче N». Нет данных — уточни у пользователя.

## Самопроверка

- `validate --all` — 0 диагностик; все required-поля — факты с источниками.
