# 18. Агентский стейт и контекст: state.json, context, би-темпоральность

Реализовано (v1). Источники: идея [«Агентский стейт — state.json в движке»](../../demo/ideas/agent-state.md)
→ план [агентский-стейт v1](../../demo/plan/агентский-стейт--state-json-в-движке--v1---текущий-проект.md)
(20/20, fm done, PR #84). Модули: `application/state.py` (123 строки),
`application/context.py` (164), `application/temporal.py` (243).

## state.json (v1: только текущий проект)

Файл `.todoc/state.json` — **вне данных** (память рабочего состояния между сессиями,
не часть корпуса документов). Белый список ключей v1: `context.current_project`;
другой ключ → `state.key_not_allowed` (карта остальных значений — задел на будущее,
не реализуется). Файл атомарно перезаписывается, формат `{schema_version, vars}`.

| Команда | Поведение |
|---|---|
| `state get KEY` | значение или `value: null` (не установлена) |
| `state set KEY VALUE` | запись (белый список v1) |
| `state list [--prefix P]` | переменные датасета, сортировка по ключу |
| `state unset KEY` | удаление; `removed: false` — не была установлена |

`state set --apply context.current_project <проект>` используется workflow-скилами и демо
(см. `demo/.todoc/state.json`). Наличие/значение не влияет на validate: это стейт,
не данные.

## context: контекст задачи одним вызовом

`todoc context --change ID \| --tag NAME [--budget N] [--with-diff]` — запись изменения
→ дельты → события → файлы → диффы, в пределах бюджета байт (по умолчанию 8000,
считается по сериализованному объёму кусков). Когда кусок не влезает — `truncated: true`,
ответ никогда не превышает бюджет. Дифф — от образа «до» первого события до текущего
содержимого; без базового хеша путь пропускается (`revision_unknown`, не шум).

## Би-темпоральность

`application/temporal.py`: интервалы фактов (`valid_from`/`valid_to`) поверх
журнальных ревизий (transaction time); `--as-of D` в `records query`, `timeline`
(`todoc timeline --as-of D --path P --limit N`) — единая лента событий записи и
интервалов фактов. Агрегация и query могут фильтроваться по «правде на дату».

## Связанные разделы

- [08-records-and-relations.md](08-records-and-relations.md) — query/`--as-of`.
- [09-storage-and-index.md](09-storage-and-index.md) — что ещё живёт в `.todoc/`.
- [17-skills-and-vault.md](17-skills-and-vault.md) — workflow-скилы используют state.
