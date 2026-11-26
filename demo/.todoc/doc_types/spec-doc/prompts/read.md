# Чтение: `spec-doc`

Capability-спека в нотации OpenSpec: SHALL-требования и WHEN/THEN-сценарии; дельта требований — в записи change (requirements_delta).

## Как читать

```bash
todoc docs read --root KB --id doc:<путь или id> --section "<секция>"
todoc docs read --root KB --id doc:<id>          # целиком (с бюджетом)
```

Обязательные секции: `## Требования`, `## Сценарии`, `## Открытые вопросы`.
