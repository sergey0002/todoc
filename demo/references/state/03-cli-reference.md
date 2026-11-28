---
created: 2026-11-24
updated: 2026-11-28
id: doc:state-cli
title: "Состояние: справочник CLI, 27 команд"
doc_type: reference
lang: ru
source: docs/state/03-cli-reference.md
copied: true
---

# 03. Контракт CLI и примеры

Полный справочник из Click перечисляет 69 листовых (включая скрытый alias `docs mv`) команд, группы, опции, позиционные аргументы и значения по умолчанию.

## Вызов и ответ

`--root`, `--output` и `--no-input` поддерживаются на уровнях корня и групп и в реализующих их листовых командах. Для корня и формата наследуется ближайшее явное значение. Повторяемые корни сохраняются на выбранном уровне. `TODOC_ROOT` используется при отсутствии `--root`. Корень и группы показывают discovery, а листовые команды с недостающими обязательными аргументами могут возвращать описание входа и `data.executed=false`. `--help` и `--version` выводят справочный текст.

JSON-ответы команд используют `schema_version: 2`, `ok`, `data`, `diagnostics`, `next_actions` и `guidance`. У результатов есть `data.meta` и `data.result`. У страниц в `meta` указаны полнота, счётчики, обрезка и курсор. `next_actions` содержит argv для следующего шага. HTTP-сервиса CLI не запускает. Ошибки тоже приходят конвертом с `ok: false` и диагностикой в `diagnostics`, а человеку дублируются в stderr: потребитель обязан проверять `ok`, иначе `2>/dev/null` превращает ошибку в похожий на пустой успех ответ. `docs new --apply` возвращает `id` созданного документа и `record_id` его JSON-зеркала (`null`, если зеркала нет); `docs read --id` принимает и id записи, разрешая его через `source_path` (поле `resolved_from`).

| Код | Значение |
|---|---|
| 0 | Успех или discovery |
| 1 | Ошибка операции |
| 2 | Ошибка синтаксиса или параметров |
| 3 | Ошибка валидации |
| 4 | Доступ за пределы разрешённой области |
| 5 | Конфликт записи или предусловия |
| 6 | Неполные данные или частично завершённая операция |

## Фильтры и выбор ответа

```bash
todoc --root demo docs list --type 'idea|plan|bug-report' --attr-lang ru --fields id,path,title,status
todoc --root demo docs list --type idea --status 'captured|planned' --status-missing
todoc --root demo docs list --type bug-report --status open --origin document
todoc --root demo docs list --type idea --filter-fields
todoc --root demo docs search --query 'единый cli' --tag-in 'cli|metadata' --limit 5
todoc --root demo docs read --id doc:home --fields text --budget 500
todoc --root demo skills --output markdown tree --view flat --fields name,path --limit 10
```

`--output json|table|markdown` выбирает сериализацию. `table` и `markdown` печатают таблицу для коллекций (`data.result.items` и строки дерева скилов), а для остальных результатов — пары `key: value`; у `flow render` и графов есть отдельный Mermaid-вывод. Это гибрид, а не единый формат. `--view` выбирает доступное для команды представление. Например, `skills tree` и `docs tree` поддерживают `tree/flat`, а `relations graph` поддерживает `graph/flat`. Для неизвестного вида использующие этот контракт команды возвращают `view.fallback` и фактический вид. `--fields` и `--exclude-fields` взаимоисключающие, структурные ключи сохраняются. Курсор получайте из ответа и используйте с теми же фильтрами и состоянием источников.

Перегруженные по смыслу флаги: `validate --all` сохранён для совместимости и не расширяет объём проверки (эквивалент `validate` без флага), а `skills tree --all` действительно включает замьюченные скилы (`!имя`). `--path`/`--section`/`--type` означают разное в разных командах — сверяйтесь со справкой конкретной команды.

## Подтверждение записи

```bash
todoc --root demo docs edit --id doc:home --patch-file edit.json --preview
todoc --root demo docs edit --id doc:home --patch-file edit.json --if-hash "$hash" --apply
todoc --root demo index rebuild --preview
todoc --root demo index rebuild --apply
todoc --root demo validate --all
```

Для команд с `--if-plan-hash` используйте полученный при preview `plan_hash`. Для структурированной правки метаданных `--if-hash` обязателен при применении. `docs edit --preview` возвращает `numbered` — итоговые строки с номерами после всех операций, `result_lines` и diff; `op` с полем `expect` отклоняет замену при несовпадении строки (`edit.expect_mismatch`, файл не меняется). `--budget` текстовых проекций считает символы Unicode полезного содержимого. Объём сериализованных метаданных может быть больше. У `docs search --budget N` единица другая — UTF-8 байты сериализованных элементов `data.result.items` без конверта; `data.meta.budget` содержит `limit`, `used_bytes` и `exhausted`.

[Формы документов](05-formats.md) · [Поиск](07-search-and-read.md) · [Рабочий цикл агента](12-agent-operations.md)

## Перенос и обратный перенос документа

`docs move --from old.md --to notes/new.md` (или `--id ID`) возвращает read-only preview и `plan_hash`; применить можно только с `--apply --if-plan-hash H`. Опции `--keep-id`, `--pin-type`, `--if-hash`, `--verbose`. Алиас `docs mv` скрыт из меню. Проверяется весь DATA_ROOT, а не только поисковая видимость. Первые 20 file-summary ограничены честным `files_truncated`; полный diff доступен явно по `--verbose`.

`revert --change move:ID` показывает отдельный план; его hash нужен для `--apply`. Последующие изменения затронутых файлов или новые битые ссылки при обратном переносе блокируют откат. Старый `revert REV --path P [--expected-hash H]` сохранён.

Точка коммита — одно multi-path событие истории. Exit 6 с `applied=true, committed=true, index_published=false` означает, что данные сохранены, а индекс нужно пересобрать (`index rebuild --apply` с тем же `--root`). `recovery_required=true` перечисляет пути незавершённого rollback. До коммита обрабатываемая ошибка восстанавливает байты. Это не crash-atomic гарантия при отключении питания и не блокировка внешних редакторов.

v1: один Markdown в существующую папку, без case-only rename; error-free baseline; затронутые reference/autolinks и неподтверждённые span, SKILL.md и change-дельты отклоняются. Старый drift не подтверждается автоматически, вторичный новый stale возвращается отдельно. `related`, `covers`, record source paths и `derived_from` обновляются по семантике, не произвольной заменой текста.
