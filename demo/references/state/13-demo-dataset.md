---
created: 2026-11-24
updated: 2026-11-28
id: doc:state-demo
title: "Состояние: демо-датасет"
doc_type: reference
lang: ru
source: docs/state/13-demo-dataset.md
copied: true
tags: [references, reference, состояние, датасет]
---

# 13. Демо-датасет

[HOME](../../HOME.md) — карта переносимого DATA_ROOT. Демо содержит 509 файлов в обзоре и 205 типизированных записей. Реестр на момент выпуска содержит 25 типов папок, 31 тип документа, 25 типов записей и 18 типов отношений. Перед использованием счётчиков перепроверьте их командами ниже.

```bash
todoc --root demo validate --all
todoc --root demo index rebuild --preview
todoc --root demo types list
todoc --root demo docs list --type 'plan|idea|bug-report' --fields id,path,title,status
todoc --root demo skills tree
```

| Раздел | Что демонстрирует |
|---|---|
| Идеи и планы | Типизированные Markdown-документы, статусы, метаданные и выборки |
| Баги | Воспроизводимость, состояние дефекта и фиксы |
| Записи и изменения | Типы сущностей, отношения, дельты и проверяемый apply |
| Скилы | Вложенное хранилище, конфигурация разделов, mute и навигация |
| Экспорты | Производные артефакты и `derived_from` |
| Профиль метаданных | Общие поля Markdown и JSON-документов |

История и артефакты демо не входят в числа командных возможностей. Подробности завершённого плана единого CLI перенесены в [сводку выпуска](../../notes/unified-cli-release.md).

[Схемы](04-config-and-types.md) · [Правила эксплуатации](12-agent-operations.md)
