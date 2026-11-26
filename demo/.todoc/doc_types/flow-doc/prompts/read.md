# Чтение: `flow-doc`

Эталон бизнес-флоу: state machine + таблица решений (истина) + flowchart + lineage. md — витрина; истина — записи flow/rule (см. entity-catalog).

## Как читать

```bash
todoc docs read --root KB --id doc:<путь или id> --section "<секция>"
todoc docs read --root KB --id doc:<id>          # целиком (с бюджетом)
```

Обязательные секции: `## Жизненный цикл`, `## Таблица решений`, `## Диаграмма исходов`, `## Lineage`.
