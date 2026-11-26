# Чтение: `agent-skill`

## Как читать

```bash
todoc docs search --root KB --query "<тема>" --limit 5      # найти скил по description
todoc docs read --root KB --path skill/<имя>/SKILL.md       # целиком
todoc skills tree --root KB                                  # хранилище скилов
```

## Что читать в каком случае

- «как выполнить работу X» — поиск по теме, чтение найденного SKILL.md, следование шагам.
- Ссылки на типовые промпты внутри скила раскрывать по мере необходимости
  (`todoc types prompt <T> --op create`) — progressive disclosure.
