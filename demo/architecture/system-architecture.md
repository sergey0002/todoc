---
id: doc:architecture-system
title: "Архитектура todoc: слои и адаптеры"
doc_type: architecture-doc
lang: ru
---

# Архитектура `todoc`: слои и адаптеры

## Слои

| Слой | Каталог | Ответственность |
|---|---|---|
| CLI | `src/todoc/cli.py` | Тонкий слой Click: парсинг флагов, конвертация ошибок в коды выхода |
| Приложение | `src/todoc/application/` | `validator`, `registry`, `search`, `query`, `write` — бизнес-логика без I/O-деталей |
| Домен | `src/todoc/domain/` | Модели: Document, Folder, Diagnostic, SearchHit, WritePlan |
| Типизация | `src/todoc/typing_system/` | Описатели типов и резолвер `dir_type`/`doc_type` |
| Адаптеры | `src/todoc/adapters/` | `filesystem/scanner`, `formats/markdown`, `formats/jsonfmt`, `formats/csvfmt` |
| Вывод | `src/todoc/output/` | Конверт ответа и рендер json/table/markdown |

## Поток данных

1. `scanner.scan_dataset` обходит DATA_ROOT детерминированно (sorted), применяет hard-excludes и containment.
2. `validator.validate_dataset` парсит каждый файл, присваивает `doc_type`, собирает диагностики.
3. `service.DatasetContext` собирает folders/documents/records/relations и публикует поколение индекса.
4. `search`/`query`/`read` работают поверх опубликованного поколения, ничего не записывая.

## Связи

- [Модель данных](data-model.md) — сущности и их поля.
- [Конституция](../plan/constitution.md) — нормативные принципы P1–P14.
- [Реализация](../plan/implementation-plan.md) — порты E1–E10 и этапы.
