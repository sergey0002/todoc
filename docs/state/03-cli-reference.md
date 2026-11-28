# 03. Контракт CLI и примеры

[Полный справочник из Click](cli.md) перечисляет 67 листовых команд, группы, опции, позиционные аргументы и значения по умолчанию.

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

`--output json|table|markdown` выбирает сериализацию. `--view` выбирает доступное для команды представление. Например, `skills tree` и `docs tree` поддерживают `tree/flat`, а `relations graph` поддерживает `graph/flat`. Для неизвестного вида использующие этот контракт команды возвращают `view.fallback` и фактический вид. `--fields` и `--exclude-fields` взаимоисключающие, структурные ключи сохраняются. Курсор получайте из ответа и используйте с теми же фильтрами и состоянием источников.

## Подтверждение записи

```bash
todoc --root demo docs edit --id doc:home --patch-file edit.json --preview
todoc --root demo docs edit --id doc:home --patch-file edit.json --if-hash "$hash" --apply
todoc --root demo index rebuild --preview
todoc --root demo index rebuild --apply
todoc --root demo validate --all
```

Для команд с `--if-plan-hash` используйте полученный при preview `plan_hash`. Для структурированной правки метаданных `--if-hash` обязателен при применении. `--budget` текстовых проекций считает символы Unicode полезного содержимого. Объём сериализованных метаданных может быть больше. У `docs search --budget N` единица другая — UTF-8 байты сериализованных элементов `data.result.items` без конверта; `data.meta.budget` содержит `limit`, `used_bytes` и `exhausted`.

[Формы документов](05-formats.md) · [Поиск](07-search-and-read.md) · [Рабочий цикл агента](12-agent-operations.md)
