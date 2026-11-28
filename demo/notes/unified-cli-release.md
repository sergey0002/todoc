---
id: doc:notes/unified-cli-release.md
title: "Единый CLI: выпуск и результаты приёмки"
doc_type: note
lang: ru
created: 2026-11-28
updated: 2026-11-28
tags: [notes, note, cli, release]
---

# Единый CLI: выпуск и результаты приёмки

- Тип: `note`
- Создан: 2026-11-28
- Идентификатор: `doc:notes/unified-cli-release.md`

## Суть

<!-- ЗАПОЛНИ: одна-две фразы, о чём документ. -->

## Что вошло в выпуск

- Конверт v2 с `data.meta`, `data.result`, `diagnostics`, `next_actions` и `guidance`. Виды `flat`, `tree` и `graph` зависят от команды. Форматы `json`, `table` и `markdown` выбираются независимо.
- Обзор и поиск по типу и общим метаданным. Markdown и JSON-документы используют одну схему в `.todoc/document-metadata.schema.json`. Текстовый `--budget` считает символы Unicode.
- Проекции и курсоры, проверяемые планы записи и чтение без публикации производных данных.
- `IndexRead`/`IndexWrite`, `ParseCache` и `HistoryStore`. Индекс читает нужные коллекции. JSON/JSONL и in-memory реализации проверены в четырёх комбинациях.

## Приёмка

Слияние `2c0085a`. 1699 тестов прошли со 100% покрытия строк и ветвей.
Все 30 критериев бенчмарка прошли. Строгая проверка демо дала 509 документов
и 0 диагностик. Для BUG‑022 обзор 20 идей занял 3654 байта и 1077 токенов
`o200k_base`. Путь PowerShell → WSL проверен.

- [Исходная идея](../ideas/unified-cli-output.md)
- [BUG‑022 и доказательства](../bugs/bug-022-no-type-overview-query.md)
- [Справочник CLI](../references/state/03-cli-reference.md)
- [Закрытый план в истории Git](https://github.com/sergey0002/todoc/blob/2c0085a0440f06148e9edc574e274c686e5b0259/demo/plan/unified-cli-output-implementation.md)

## Связанные работы

- [Подсказки](../ideas/cli-model-guidance-and-hint-catalog.md): русский каталог
  и автоматический режим ошибок работают. Переключение профилей остаётся в идее.
- [Логирование действий](../ideas/action-logging.md): в выпуск не входит и
  отложено до отдельного плана; идея сохраняет статус `captured` и собственные
  критерии приёмки.
- [Драйвер SQLite](../ideas/sqlite-storage-drivers.md): порты готовы. SQLite и FTS
  остаются отдельной реализацией.
- [Граф тегов](../ideas/unified-tags-and-tag-graph.md): отбор по тегам работает.
  Каталог и граф тегов остаются открытыми.
- [Волновое планирование](../ideas/wave-planning-cli-helpers.md),
  [агентные флоу](../ideas/agent-flows.md), [жизненный цикл разработки](../ideas/dev-lifecycle-flow.md),
  [мультипроектность](../ideas/multi-project-workspace.md) и [отключаемые правила](../ideas/toggleable-rules.md)
  используют общий контракт CLI и сохраняют собственные условия приёмки.
