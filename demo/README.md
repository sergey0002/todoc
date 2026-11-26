---
id: doc:demo-readme
title: README демо-датасета todoc
doc_type: demo-readme
lang: ru
created: 2026-11-26
updated: 2026-11-26
tags: [demo-readme, датасета, readme]
---

# Демо-датасет `todoc`

Готовый DATA_ROOT, в котором вся документация проекта разложена по типам папок и документов,
а метаданные лежат в типизированных JSON-записях. Датасет создан командой `todoc init` и затем
расширен: добавлены типы, правила, шаблоны, JSON Schema и сохранённые запросы. Во front matter
каждого markdown-документа ведутся `created`/`updated`/`tags` (и `related`-wikilinks для явных
пар) — их ставит и бампит движок, поиск бустует совпадения по тегам (`docs search --tag`).

## Структура

| Папка | `dir_type` | Что внутри |
|---|---|---|
| `.todoc/` | — | Конфигурация: датасет, правила, типы, шаблоны, схемы, запросы |
| `plan/` | `plan` (reserved) | Конституция, план реализации, конкурентный анализ, аудит, `after/` |
| `.research/` | `research` (reserved) | Инженерный набросок, исследование MCP/CLI, аудит снимков |
| `architecture/` | `architecture` (reserved) | Слои, поток данных, модель данных |
| `glossary/` | `glossary` (reserved) | Определения терминов |
| `guides/` | `guides` | Гайды с постулатами и чек-листами |
| `references/` | `references` | Справка по подсистемам, включая `state/` — документацию состояния |
| `competitors/` | `competitors` | Карточки конкурентов и Agent Skills |
| `records/` | `records` | Типизированные JSON-записи |
| `notes/` | `notes` | Заметки со свободными связями |
| `ideas/` | `idea` | Идеи, не перешедшие в планы |
| `inbox/` | `inbox` | Неотсортированные материалы |
| `attachments/` | `attachments` | CSV-инвентарь документов |
| `skill/` | `skill` | Копия `SKILL.md` |

## Быстрая проверка

```bash
todoc validate --root demo --all          # ожидается 0 диагностик
todoc check --root demo                    # сводка по датасету
todoc types list --root demo               # 18 dir_types, 23 doc_types, 13 entity_types, 9 relation_types
todoc docs tree --root demo --max-depth 2  # дерево папок с типами
todoc docs search --root demo --query "портабельность" --limit 3
todoc docs read --root demo --id doc:constitution --section "Принципы"
todoc records list --root demo --type decision --limit 5
todoc records query --root demo --query-file demo/.todoc/queries/decisions-accepted.json
todoc records aggregate --root demo --type metric --metric value --group-by aspect
todoc relations graph --root demo --from decision:no-lsp --depth 2
```

## Что демонстрирует датасет

1. **Приоритеты резолвера**: front matter `doc_type` (приоритет 200) побеждает маску папки (приоритет 100);
   зарезервированные имена дают `dir_type`, когда правила молчат.
2. **Записи с единицами измерения**: `records/metrics/*.json` → `records aggregate` возвращает `units` и `formula`.
3. **Валидация по JSON Schema**: `.todoc/entity_types/<entity_type>/schema.json` применяются к записям;
   нарушение даёт `record.schema_violation` с JSON Pointer.
4. **Отношения**: `documents`, `references`, `analyzes`, `describes`, `supersedes` — цель обязана существовать.
5. **Ссылки**: обычные Markdown-ссылки проверяются, wikilinks резолвятся по имени файла,
   код в fenced-блоках и инлайновый код ссылками не считаются.
6. **CSV**: `attachments/docs-inventory.csv` читается через `docs read --columns/--rows/--where`.

## Связь с репозиторием

Документы в демо — **копии** файлов репозитория (`docs/plan/`, `docs/state/`, `references/`, гайды,
исследования, `SKILL.md`) с добавленным front matter и поправленными относительными ссылками.
Исходники остаются на месте; демо можно пересобрать заново.