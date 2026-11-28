# 13. Демо-датасет

[HOME](../../demo/HOME.md) — карта переносимого DATA_ROOT. Демо содержит 509 файлов в обзоре и 205 типизированных записей. Реестр на момент выпуска содержит 25 типов папок, 31 тип документа, 25 типов записей и 18 типов отношений. Перед использованием счётчиков перепроверьте их командами ниже.

```bash
todoc --root demo validate --all
todoc --root demo index rebuild --preview
todoc --root demo types list
todoc --root demo docs list --type 'plan|idea|bug-report' --fields id,path,title,status
todoc --root demo skills tree
```

| Раздел | Что демонстрирует |
|---|---|
| [Идеи](../../demo/ideas) и [планы](../../demo/plan) | Типизированные Markdown-документы, статусы, метаданные и выборки |
| [Баги](../../demo/bugs) | Воспроизводимость, состояние дефекта и фиксы |
| [Записи](../../demo/records) и [изменения](../../demo/changes) | Типы сущностей, отношения, дельты и проверяемый apply |
| [Скилы](../../demo/skills) | Вложенное хранилище, конфигурация разделов, mute и навигация |
| [Экспорты](../../demo/exports) | Производные артефакты и `derived_from` |
| [Профиль метаданных](../../demo/.todoc/document-metadata.schema.json) | Общие поля Markdown и JSON-документов |

История и артефакты демо не входят в числа командных возможностей. Подробности завершённого плана единого CLI перенесены в [сводку выпуска](../../demo/notes/unified-cli-release.md).

[Схемы](04-config-and-types.md) · [Правила эксплуатации](12-agent-operations.md)
