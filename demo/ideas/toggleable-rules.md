---
id: doc:ideas/toggleable-rules.md
title: "Идея: отключаемые правила харнеса (doc_type rules, переключатель enable/disable и скрытие отключённых в выборках без --include-disabled)"
doc_type: idea
lang: ru
status: captured
created: 2026-11-26
updated: 2026-11-26
tags: [ideas, idea, rules, harness, skills, flows, cli, правила]
related: ["[[skills-engine]]", "[[typed-tree-projection]]", "[[type-naming-and-state-dir]]", "[[unified-tags-and-tag-graph]]", "[[sqlite-storage-drivers]]", "[[entity-catalog]]"]
---

# Идея: отключаемые правила харнеса (`doc_type: rules`, переключатель `enable`/`disable` и скрытие отключённых в CLI-выборках)

- Тип: `idea`
- Создан: 2026-11-26
- Идентификатор: `doc:ideas/toggleable-rules.md`
- Статус: `captured` (идея зафиксирована, не перешла в план)

## Суть

Замкнуть триаду исполняемого агентского харнеса **`skills` + `flows` + `rules`**:
1. добавить недостающий документный тип **`doc_type: rules`** (и тип папки **`dir_type: rules`**) для операционных правил, политик и ограничений агента/домена;
2. сделать `rules` (а вместе с ними унифицированно `flows` и `skills`) **отключаемыми (`enabled: true | false`)** через атомарные команды CLI (`enable` / `disable`), не ломающие пути и ссылки;
3. закрепить единое правило фильтрации во **всех поисковых и списочных выборках CLI**: отключённые сущности **скрыты по умолчанию** (агент их не видит и не исполняет в харнесе) и отображаются **только при передаче специального флага `--include-disabled`** (или `--disabled-only`).

## Проблема

1. **В харнесе есть `skills` и `flows`, но нет документного типа `rules`.** Сейчас в системе есть отключаемые скилы (`skill` — пошаговые процедуры «как делать») и флоу (`flow` / `flow_doc` — маршруты и деревья решений), но `rule` существует только как JSON-запись предметной бизнес-логики для DMN-таблиц (`records/rules/*.json` со схемой `given/when/then`). Операционные правила работы агента (стиль кода, запреты, политики ревью, правила домена — аналог `.cursor/rules` / `.claude/rules`) класть некуда: они растворяются в обычных `note` или `guide`.
2. **Нет чистого способа временно выключить и снова включить правило или флоу без поломки ссылок.** У скилов сейчас мьют работает только через переименование папки в `!<name>` (`skills.py:137`), что меняет физический путь файла на диске и ломает относительные ссылки. Для одиночного файла правила или записи флоу переключателя в CLI нет вообще.
3. **Нет сквозного контракта скрытия отключённых элементов во всех выборках CLI.** Сейчас `!-папки` отсекаются в `skills tree` (флаг `--all`) и `docs search`, но в `docs tree`, `records list`, `records query` и будущем `todoc tree` единого механизма фильтрации выключенных объектов харнеса и единого спецфлага их показа нет.

## Принципы

1. **Полная триада харнеса (`skills` + `flows` + `rules`).**
   - `skills` — *процедуры и инструменты* («как выполнить задачу»);
   - `flows` — *маршруты и развилки* («по какому сценарию идти»);
   - `rules` — *инварианты и ограничения* («какие правила соблюдать при работе в корне или домене»).
2. **Включение/выключение — метаданное состояния (`enabled: bool`), а не переименование файла.** Поле `enabled: true | false` во front matter `.md` (и в JSON-записи `flow`) по умолчанию равно `true`. Переключение `enable` / `disable` не меняет `id` и `path` документа, поэтому ни одна ссылка в базе не бьётся. Существующий мьют папки `!<folder>` у скилов продолжает поддерживаться и в индексе сводится к тому же единому признаку `enabled = false`.
3. **Fail-safe по умолчанию для агента: выключенное невидимо без спецфлага.** В обычном рабочем цикле агент вызывает поиск, `tree` или выборку правил домена и получает **только включённые (`enabled: true`)** правила, флоу и скилы — не тратя токены на отключённые инструкции и случайно не применяя устаревшие/экспериментальные правила.
4. **Разведение с предметным `entity_type: rule`.** Имя нового типа файла и папки — **`rules`** (`1` слово в строгом соответствии со стандартом [`type-naming-and-state-dir`](type-naming-and-state-dir.md)), чтобы не конфликтовать с JSON-записями предметных бизнес-правил `entity_type: rule`.

## Предложение

### 1. Новый тип документа `doc_type: rules` и папки `dir_type: rules`

Файлы правил размещаются в корневой папке `rules/` или внутри любого домена/проекта (`projects/shop/rules/*.md`) и автоматически получают `dir_type: rules` и `doc_type: rules`:

```markdown
---
id: doc:rules/strict-sql-migrations.md
title: "Правила: безопасные миграции схемы SQLite"
doc_type: rules
lang: ru
enabled: true
priority: must
created: 2026-11-26
updated: 2026-11-26
tags: [rules, sqlite, migrations, safety]
---

# Правила: безопасные миграции схемы SQLite

## Область действия

Применяется при изменении таблиц и индексов в `src/todoc/adapters/`.

## Правила

- **MUST:** любая смена структуры `index.sqlite` увеличивает `schema_version` в таблице `meta`.
- **MUST NOT:** запрещено удалять данные из `history.sqlite` при пересборке поискового индекса.
```

- **Поля front matter `doc_type: rules`:**
  - `enabled` (`boolean`, опционально, дефолт `true`) — активен ли набор правил;
  - `priority` (`must | should`, опционально, дефолт `must`) — жёсткость правил при сборке контекста харнеса;
  - `tags` — для точной выборки правил по теме через `--tag-in` (например, `--tag-in "sqlite|testing"`).
- **Обязательные секции шаблона (`required_sections`):** компактные `## Область действия` и `## Правила` (без лишней бюрократии, чтобы файлы правил были короткими и дешёвыми по токенам).

### 2. Команды CLI для управления и переключения (`enable` / `disable`)

Добавляется группа **`todoc rules`** (плюс универсальная поддержка `--enabled` / `enable` / `disable` для `flows` и `skills`):

```bash
# Выбрать все АКТИВНЫЕ правила (в корне или в домене/проекте, с фильтром по тегам):
todoc rules list --root KB [--within projects/shop] [--tag-in "sqlite|cli"] [-q "миграции"]

# Выключить и снова включить правило одной атомарной командой CLI:
todoc rules disable --root KB --id doc:rules/strict-sql-migrations.md
todoc rules enable  --root KB --id doc:rules/strict-sql-migrations.md

# Аналогично для любого отключаемого объекта харнеса (rules / skill / flow):
todoc docs disable --root KB --id doc:flows/checkout-v1.md
todoc records disable --root KB --id flow:checkout-v1
```

- Команды `enable` / `disable` атомарно обновляют `enabled: true|false` во front matter или JSON-записи, бампят `updated`, пишут событие в историю и за `O(1)` (`~2–3 мс` в `index.sqlite`, см. [`sqlite-storage-drivers`](sqlite-storage-drivers.md)) обновляют колонку `enabled` в индексе.

### 3. Поведение всех выборок и поиска CLI (`--include-disabled` / `--disabled-only`)

В единой таблице `items` индекса (и в JSON-снапшоте) хранится булево поле `enabled` (`1` по умолчанию; `0`, если `enabled: false` в метаданных или если путь содержит мьют-сегмент `!<folder>`):

| Режим вызова CLI (`docs search`, `tree`, `docs tree`, `rules list`, `records list/query`, `skills tree`, `context`) | Что попадает в выдачу |
|---|---|
| **По умолчанию (без спецфлага)** | **Только включённые (`enabled == true`)!** Отключённые `rules`, `flows` и `skills` полностью отфильтрованы и не шумят в поиске и дереве. |
| **`--include-disabled`** *(в `skills tree` алиас `--all` сохраняется)* | Возвращаются и активные, и отключённые элементы; у отключённых в JSON стоит `"enabled": false`, а в `table`/`markdown` выводится префикс `[disabled]`. |
| **`--disabled-only`** | Возвращаются **только отключённые** элементы — удобно для ревизии («какие правила или флоу сейчас выключены и можно ли включить готовое?»). |
| **Прямое чтение по ID (`docs read --id ...`, `records read --id ...`)** | Читается всегда (чтобы человек или агент мог изучить выключенное правило перед включением), но в метаданных ответа явно возвращается `"enabled": false`. |

### 4. Совместная работа с `todoc tree` в харнесе домена

В связке с [`todoc tree`](typed-tree-projection.md) агент при старте задачи в папке проекта `projects/shop/checkout` может одной командой собрать все **активные** правила вдоль ветки папок или внутри поддерева:

```bash
todoc tree --root KB --lineage-for projects/shop/checkout --doc-type "rules"
todoc tree --root KB --within projects/shop --doc-type "rules|flow_doc|skill"
```

Все выключенные правила (`enabled: false`) автоматически пропускаются, а включённые приходят в чистой иерархии без мусорных промежуточных папок.

## План внедрения

1. **Фаза 1 — Типы `dir_type: rules` и `doc_type: rules` + валидация поля `enabled`:**
   - Зарегистрировать зарезервированное правило папки `**/rules → dir_type: rules` и дескриптор `doc_type: rules` (шаблон, промпты, проверка `enabled: bool` и `priority: must|should` в `validator.py`); поддержать опциональное поле `enabled: bool` у `flow`, `flow_doc`, `skill` и `agent_skill`.
   - *Acceptance:* `todoc types show rules` возвращает схему и шаблон; `validate --all` проверяет тип `enabled`.
2. **Фаза 2 — Индексация `enabled` и сквозной фильтр `--include-disabled` / `--disabled-only`:**
   - Добавить атрибут `enabled` (с учётом как `enabled: false`, так и `!<folder>`) в индекс (`items` в `SqliteIndexDriver` и `JsonIndexDriver`) и прокинуть дефолтное скрытие `enabled == true` + флаги `--include-disabled` и `--disabled-only` в `docs search`, `tree`, `docs tree`, `records list/query`, `skills tree`, `context`.
   - *Acceptance:* выключенное правило/флоу/скил не возвращается ни в одной выборке без флага и мгновенно появляется с `--include-disabled`.
3. **Фаза 3 — Команды CLI `todoc rules` (`list`, `enable`, `disable`) и переключатели для `flows`/`skills`:**
   - Реализовать `todoc rules list|enable|disable` и универсальное переключение `enable`/`disable` по `--id` с записью в историю и `100%` branch coverage.
   - *Acceptance:* переключение `disable → search (пусто) → search --include-disabled (видно) → enable → search (видно)`; `todoc validate --root demo --all` = `0`.

## Открытые вопросы

- **Отключение целой папки правил (`.config.json` с `"enabled": false`):** стоит ли разрешить `"enabled": false` прямо в `<dir>/.config.json`, чтобы одним флагом временно гасить целый пакет правил или скилов раздела без правки каждого файла? Да — в индексе это естественно наследуется всеми элементами внутри `<dir>/**` аналогично `!<dir>`.
- **Поведение графа связей (`relations graph/tree`) для отключённых узлов:** по умолчанию помечать узлы с `enabled: false` в графе полем `"enabled": false` или скрывать их без `--include-disabled`? В `relations` лучше скрывать рёбра к выключенным объектам харнеса по умолчанию и показывать с `--include-disabled` — единообразно со всеми выборками.

## Связанные документы

- [Идея: движок скилов (`skills-engine`) и мьют скилов](skills-engine.md)
- [Идея: `todoc tree` — типизированная проекция дерева в CLI](typed-tree-projection.md)
- [Идея: стандарт именования типов (`snake_case`) и тип папки `state`](type-naming-and-state-dir.md)
- [Идея: сквозная система тегов (`todoc tags` и `--tag-in`)](unified-tags-and-tag-graph.md)
- [Идея: переключаемые драйверы хранения (`index.sqlite` и `history.sqlite`)](sqlite-storage-drivers.md)
- [Идея: справочник сущностей и витрины `flow`](entity-catalog.md)
