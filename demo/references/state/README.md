---
id: doc:state-readme
title: "Состояние системы todoc: оглавление"
doc_type: reference
lang: ru
source: .doc/state/README.md
copied: true
---
# Состояние системы `todoc` — документация

Каталог `docs/state/` описывает **фактическое текущее состояние** реализации: что работает,
как устроено, как проверяется и что известно как дефект. Каждый факт здесь получен прогоном
кода или CLI; непроверенные утверждения помечены явно.

Дата снимка: 2026-11-24. Ветка: `arena/bdea7538-todoc`.

## Разделы

| Файл | Аспект | Для кого |
|---|---|---|
| [01-overview.md](01-overview.md) | Что такое `todoc`, границы продукта, статус MVP | человек + агент |
| [02-architecture.md](02-architecture.md) | Слои, модули, поток данных, порты | человек + агент |
| [03-cli-reference.md](03-cli-reference.md) | Все 25 команд: флаги, вход, выход, коды выхода | агент (основной) |
| [04-config-and-types.md](04-config-and-types.md) | `dataset.json`, правила, типы, резолвер | человек + агент |
| [05-formats.md](05-formats.md) | Адаптеры Markdown/JSON/CSV | человек + агент |
| [06-validation-and-diagnostics.md](06-validation-and-diagnostics.md) | Каталог диагностик, фиксы | агент |
| [07-search-and-read.md](07-search-and-read.md) | Поиск, ранжирование, бюджетное чтение | агент |
| [08-records-and-relations.md](08-records-and-relations.md) | Записи, отношения, запросы, агрегация | человек + агент |
| [09-storage-and-index.md](09-storage-and-index.md) | Поколения индекса, кэш парсинга, атомарность | человек |
| [10-testing-and-quality.md](10-testing-and-quality.md) | Тесты, покрытие, как запускать | человек |
| [11-known-issues.md](11-known-issues.md) | Подтверждённые дефекты с воспроизведением | человек + агент |
| [12-agent-operations.md](12-agent-operations.md) | Как агенту работать с системой безопасно | агент (основной) |
| [13-demo-dataset.md](13-demo-dataset.md) | Устройство демо-датасета `demo/` | человек + агент |
| [14-glossary.md](14-glossary.md) | Термины | человек + агент |

## Связанные документы

- Норматив: [конституция](../../plan/constitution.md), [план реализации](../../plan/implementation-plan.md).
- Аудит с полным списком находок: [аудит реализации](../../plan/audit-implementation.md).
- Живой пример: [`demo/`](../../README.md) — полноценный DATA_ROOT, проверяемый тем же CLI.
- Точка входа навыка: [SKILL.md](../../skill/SKILL.md) и [`references/`](../workflow.md).

## Как обновлять этот каталог

1. Любой факт (число, код, поведение) добавляется только после проверки командой.
2. Числа в [10-testing-and-quality.md](10-testing-and-quality.md) обновляются при каждом изменении кода.
3. Новый дефект попадает в [11-known-issues.md](11-known-issues.md) с командой воспроизведения.
4. Изменение контракта CLI обязательно отражается в [03-cli-reference.md](03-cli-reference.md).
