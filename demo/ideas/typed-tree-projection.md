---
id: doc:ideas/typed-tree-projection.md
title: "Идея: todoc tree — типизированная проекция дерева в CLI со схлопыванием промежуточных папок"
doc_type: idea
lang: ru
status: captured
created: 2026-11-26
updated: 2026-11-28
tags: [ideas, idea, tree, hierarchy, cli, skills, navigation, иерархия]
related: ["[[folder-config]]", "[[skills-engine]]", "[[entity-to-folder]]", "[[type-naming-and-state-dir]]", "[[unified-tags-and-tag-graph]]"]
---

# Идея: `todoc tree` — типизированная проекция дерева в CLI со схлопыванием промежуточных папок

- Тип: `idea`
- Создан: 2026-11-26
- Идентификатор: `doc:ideas/typed-tree-projection.md`
- Статус: `captured` (идея зафиксирована, не перешла в план)

## Суть

Ввести на уровне CLI универсальный механизм **типизированной выборки и проекции дерева со схлопыванием промежуточных директорий (Tree Contraction)** — команду **`todoc tree`** с фильтрами через `|` по типам папок (`--dir-type`), типам документов (`--doc-type`), типам записей (`--entity-type`) и форматам файлов (`--format`) в двух режимах обхода файловой иерархии:
1. **Вниз по поддереву (`--within <dir>`)** — строит сжатое дерево целевых сущностей внутри выбранной папки, вырезая транзитные папки «чужих» типов, но **сохраняя вложенность `предок → потомок`** (`dir_type_1 / dir_type_2 / dir_type_3 / dir_type_1` сжимается в `dir_type_1 → dir_type_1`);
2. **Вдоль ветки предков к указанной папке (`--lineage-for <dir>`)** — возвращает по тем же фильтрам упорядоченную цепочку узлов от корня датасета до указанной директории (`root → ... → <dir>`), также пропуская промежуточные папки неподходящих типов.

Сама идея задаёт **чистую механику выборки на уровне CLI** (без зашивания бизнес-правил о том, какие типы документов агент обязан интерпретировать особо).

## Проблема

1. **Промежуточные технические папки рвут логическую иерархию разделов и скилов.** В живой базе папки целевого типа (например, вложенные `skill`, домены `project` или `state`) разделены служебными папками других типов (`notes/`, `research/`, `references/`, `scripts/`, `archive/`). Обычный обход ФС либо тонет в десятках промежуточных уровней, либо обрезается по `--max-depth`, не доходя до вложенных целевых папок.
2. **Нынешний `todoc docs tree` не строит иерархическую проекцию и не фильтрует по типам.** Сейчас `docs tree` возвращает два плоских среза `folders[:50]` и `documents[:50]`, не умеет фильтровать по `dir_type`, `doc_type`, `entity_type` или `format` через `|` и не включает JSON-записи `records`.
3. **Запросы выборок слабо скоупятся папкой.** Указать подпапку через `--root` нельзя (`missing .todoc/dataset.json`), а единого способа выбрать внутри директории только нужные типы папок и сущностей с сохранением их взаимной вложенности сейчас нет.

## Принципы (утверждённые правила механики)

1. **Строгость по `--dir-type` (ищем только в папках указанных типов).** Если передан `--dir-type "t1|t2"`, то целевые документы и записи выбираются **только внутри папок этих типов** (плюс стартовая папка, если она сама подходит по типу). Файлы даже подходящего `doc_type` / `entity_type`, лежащие в промежуточных папках других типов, в выборку **не попадают**. Если `--dir-type` не указан — учитываются папки всех типов.
2. **Схлопывание промежуточных папок с сохранением отношения `предок → потомок`.** Если папка `A` (`dir_type_1`) содержит `B` (`dir_type_2`) → `C` (`dir_type_3`) → `D` (`dir_type_1`), то при фильтре `--dir-type "dir_type_1"` узлы `B` и `C` вырезаются, а `D` поднимается и становится **прямым дочерним узлом `A`** в возвращаемом дереве. При этом у `D` и её файлов сохраняется их настоящий физический `path` от корня датасета (плюс счётчик `skipped_dirs: 2`).
3. **Скрытие пустых веток по умолчанию (`--keep-empty` по запросу).** Папка подходящего `--dir-type`, в которой нет ни одного искомого документа/записи и нет непустых дочерних веток подходящего типа, по умолчанию **отсекается**. Флаг `--keep-empty` оставляет все папки целевых `--dir-type` в дереве (полезно, когда нужен чистый каркас папок заданного типа).
4. **Нейтральность механизма.** Команда решает задачу структурной выборки для любых типов папок и сущностей (вложенные скилы, планы, стейты, задачи, правила и любые будущие иерархические типы), не привязываясь к конкретной предметной семантике документа.

## Предложение

### 1. Алгоритм схлопывания дерева (Tree Contraction)

Физическая структура на диске:

```text
platform/                          [dir_type = project]    <-- входит в --dir-type
├── overview.md                    [doc_type = state_doc]  <-- входит в --doc-type
├── scratch.md                     [doc_type = note]       (отброшен по doc_type)
└── notes/                         [dir_type = notes]      (промежуточный чужой тип)
    └── drafts/                    [dir_type = notes]      (промежуточный чужой тип)
        ├── stray-state.md         [doc_type = state_doc]  (игнорируется: папка чужого dir_type!)
        └── experiments/           [dir_type = research]   (промежуточный чужой тип)
            ├── billing/           [dir_type = project]    <-- входит в --dir-type!
            │   ├── billing.md     [doc_type = state_doc]  <-- входит в --doc-type!
            │   └── task-01.json   [entity_type = task]    (отброшен по типу)
            └── empty-subproject/  [dir_type = project]    (пустая ветка -> скрыта без --keep-empty)
```

Вызов проекции:

```bash
todoc tree --root KB --within platform --dir-type "project" --doc-type "state_doc"
```

Сжатое дерево на выходе (`notes/drafts/experiments` схлопнуты, `empty-subproject` скрыт, иерархия сохранена):

```text
platform/ [project] (path: "platform")
├── doc:platform/overview.md — «Обзор платформы»
└── billing/ [project] (path: "platform/notes/drafts/experiments/billing", skipped_dirs: 3)
    └── doc:platform/notes/drafts/experiments/billing/billing.md — «Состояние биллинга»
```

### 2. Интерфейс CLI (`todoc tree`)

```bash
todoc tree --root KB   [--within <dir> | --lineage-for <dir>]   [--dir-type "type1|type2"]   [--doc-type "doc1|doc2"]   [--entity-type "ent1|ent2"]   [--format "markdown|json|csv"]   [--tag-in "tag1|tag2"]   [--keep-empty]   [--max-depth <N>]   [--output json|table|markdown]
```

**Параметры мульти-выборки (через `|`):**
- `--within <dir>` — искать только в указанной директории и её поддереве (режим обзора сверху вниз).
- `--lineage-for <dir>` — режим выборки по ветке предков: рассмотреть только путь от корня `.` до указанной папки `<dir>` включительно и вернуть сжатую цепочку подходящих узлов сверху вниз (`root → ... → <dir>`).
- `--dir-type "t1|t2"` — фильтр типов папок (`dir_type`); папки не из списка схлопываются, файлы внутри них не выбираются.
- `--doc-type "d1|d2"` — один или несколько типов документов (`skill|agent_skill`, `idea|plan|state_doc`, `guide|reference` и др.).
- `--entity-type "e1|e2"` — один или несколько типов JSON-записей (`task|rule|flow`). *(Если указаны и `--doc-type`, и `--entity-type`, возвращается объединение обоих в узлах дерева; если не указан ни один — возвращаются все сущности подходящего `--format`).*
- `--format "markdown|json|csv"` — фильтр по формату файла-носителя через `|`.
- `--tag-in "x|y|z"` — дополнительный срез по тегам (см. [единую систему тегов](unified-tags-and-tag-graph.md)).
- `--keep-empty` — не отсекать подходящие по `--dir-type` папки, в которых нет совпавших файлов.
- `--max-depth <N>` — глубина считается **по сжатому дереву** (по числу пройденных целевых папок, а не физических сегментов пути!), чтобы промежуточные прослойки не «съедали» лимит глубины.

### 3. Формат JSON-ответа

```json
{
  "schema_version": 1,
  "ok": true,
  "data": {
    "dataset_id": "dataset-80c70868",
    "mode": "subtree",
    "scope": "platform",
    "filters": {
      "dir_type": ["project"],
      "doc_type": ["state_doc"],
      "entity_type": [],
      "format": []
    },
    "nodes": [
      {
        "path": "platform",
        "dir_type": "project",
        "title": "Платформа",
        "skipped_dirs": 0,
        "items": [
          {
            "kind": "document",
            "id": "doc:platform/overview.md",
            "path": "platform/overview.md",
            "doc_type": "state_doc",
            "format": "markdown",
            "title": "Обзор платформы"
          }
        ],
        "children": [
          {
            "path": "platform/notes/drafts/experiments/billing",
            "dir_type": "project",
            "title": "Биллинг",
            "skipped_dirs": 3,
            "items": [
              {
                "kind": "document",
                "id": "doc:platform/notes/drafts/experiments/billing/billing.md",
                "path": "platform/notes/drafts/experiments/billing/billing.md",
                "doc_type": "state_doc",
                "format": "markdown",
                "title": "Состояние биллинга"
              }
            ],
            "children": []
          }
        ]
      }
    ],
    "total_folders": 2,
    "total_items": 2
  },
  "diagnostics": [],
  "next_actions": []
}
```

### 4. Примеры использования механики

1. **Вложенные скилы (`parent skill → child skills`):**
   - `todoc tree --root KB --within .todoc/skills --dir-type "skill" --doc-type "skill|agent_skill"`
   - Промежуточные каталоги `references/`, `scripts/`, `assets/` внутри родительского скила автоматически схлопываются, но если глубже лежит дочерний скил со своим `dir_type: skill`, он отображается прямым дочерним узлом родительского скила.
2. **Срез состояния (`state`) и планов (`plan`) внутри проекта без шума:**
   - `todoc tree --root KB --within projects/shop --dir-type "state|plan" --doc-type "state_doc|plan"` — строит чистое дерево `AS-IS` и `TO-BE` по подсистемам проекта, пропуская черновики, вложения и заметки.
3. **Сбор любых наследуемых по папкам сущностей вдоль пути (`--lineage-for`):**
   - `todoc tree --root KB --lineage-for projects/shop/checkout --dir-type "skill" --doc-type "skill"` — одним вызовом отдаёт родительские и локальные сущности заданного типа вдоль ветки до целевой папки.

## План внедрения

1. **Фаза 1 — Ядро сжатия дерева (`application/tree_projection.py`):**
   - Чистая функция поверх снапшота индекса (`folders` + `documents` + `records` + `folder_configs`): парсинг `|`-фильтров, фильтрация файлов строго по принадлежности к разрешённым `dir_type` (когда `--dir-type` задан), post-order сжатие промежуточных папок с подсчётом `skipped_dirs`, обрезка пустых веток (кроме `--keep-empty`) и расчёт `--max-depth` по сжатой глубине.
   - Режим `--lineage-for <dir>` по префиксной цепочке папок от `.` до `<dir>`.
   - *Acceptance:* unit-тесты на цепочку `type1 -> type2 -> type2 -> type3 -> type1`, отбрасывание файла в промежуточной папке `type2`, обрезку пустых листьев и `--keep-empty`.
2. **Фаза 2 — Команда CLI `todoc tree` и рендеры (`json` / `table` / `markdown`):**
   - Подключить `todoc tree` со всеми флагами (`--within`, `--lineage-for`, `--dir-type`, `--doc-type`, `--entity-type`, `--format`, `--tag-in`, `--keep-empty`, `--max-depth`); в `--output markdown|table` рендерить наглядное дерево с отступами и пометкой `(skipped N dirs)`.
   - Сделать `todoc docs tree` обратной обёрткой над тем же движком проекции.
   - *Acceptance:* `100%` branch coverage, `todoc validate --root demo --all` = `0` диагностик.

## Открытые вопросы

- **Учёт самой корневой папки датасета (`.`):** если у `DATA_ROOT` нет собственного `.config.json` с `dir_type`, должен ли фильтр `--dir-type` проверять только вложенные папки, или корневой уровень включается только при явном совпадении `dir_type` в корневом `.config.json`? Явное правило (только при совпадении `dir_type`) проще и предсказуемее.

## Связанные документы

- [Идея: `.config.json` — самоописание папок](folder-config.md)
- [Идея: движок скилов (`skills-engine`) и дерево скилов](skills-engine.md)
- [Идея: `todoc folderize` — преобразование сущности в папку-домен](entity-to-folder.md)
- [Идея: стандарт именования типов (`snake_case`) и тип папки `state`](type-naming-and-state-dir.md)
- [Идея: сквозная система тегов и фильтр `--tag-in`](unified-tags-and-tag-graph.md)

## Связь с выпуском единого CLI

Обычное дерево и плоская страница сохраняют полные пути, глубину и контекст предков. Типизированное сжатое дерево и lineage остаются в объёме идеи.
[Сводка выпуска единого CLI](../notes/unified-cli-release.md).
