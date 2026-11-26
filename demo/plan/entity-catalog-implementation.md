---
id: doc:plan-entity-catalog
title: "Справочник сущностей: term-записи, u-graph ссылок md↔JSON, undo рёбер, витрины флоу (план реализации)"
doc_type: plan
lang: ru
status: active
tags: [plan, entity-catalog, термины, u-graph, mentions, undo]
related: ["[[entity-catalog]]", "[[documentation-system]]", "[[документирование-софта--типовой-профиль---типы--стартовые-промпты--скилы]]", "[[теги-документов-как-aliases-поиска--tags-updated-related-в-front-matter]]"]
created: 2026-11-26
updated: 2026-11-26
---

# Справочник сущностей: term-записи, u-graph, undo рёбер, витрины — план реализации

> **Исполнителю (агенту):** план самодостаточен — читай его, а не историю сессии.
> Работай по задачам сверху вниз; шаги отмечаются чекбоксами (`- [ ]`) в том же
> коммите, который делает шаг. Начинай всегда с первого неотмеченного.

**Цель:** реализовать идею [entity-catalog](../ideas/entity-catalog.md)
(doc:entity-catalog-idea) тремя волнами: **волна 1 (З1–З4, движок)** — u-graph
ссылок md↔JSON (якоря разделов, entity-цели, JSON Pointer-фрагменты), mention-индекс
в кеше, `mentioned_in`, mention-вершины графа, `relations tree`, `records undo-relation`;
**волна 2 (З5–З7, данные)** — entity_type `term`, relation-типы `uses_term`/`part_of`,
миграция 10 терминов глоссария в записи, рёбра пилота, счётчики; **волна 3 (З8–З9)**
— витрины флоу (`docs flow render`/`walk`) и этап 2 (`source_anchor`, фрагментные
вершины). Движок дорабатывается по TDD без новых зависимостей.

**Спека:** [ideas/entity-catalog.md](../ideas/entity-catalog.md) — разделы 1–10
(термин-запись, u-граф §5, edge-undo §6, контракт парсинга/кеша/вывода §7,
обратная адресация §8, реестр инструментов §9, кеш §10) + ресёрч
[decision-tree-formats](../.research/decision-tree-formats.md) (doc:decision-tree-formats)
+ [ideas/documentation-system.md](../ideas/documentation-system.md) (эталон флоу).

**Координация с соседними планами:**

| План | Что даёт этому плану | Что этот план ему уступает |
|---|---|---|
| [документирование-софта](документирование-софта--типовой-профиль---типы--стартовые-промпты--скилы.md) | entity `flow`/`rule`, пилот `flow:order-placement` — потребители `uses_term` и `tree` (З6–З8, gate) | здесь не создаются flow/rule-типы и пилот |
| [теги-документов](теги-документов-как-aliases-поиска--tags-updated-related-в-front-matter.md) | fm `related`-wikilinks — человеческий слой; валидатор fm | mentions — только body-ссылки, fm related не индексируется |
| agent-state (исполнен, PR #59/#60) | `state get context.current_project` — не используется здесь | — |

## 1. Критерии успеха

**Волна 1 (движок, З1–З4):**

1. `[[x#раздел]]` и `[..](x.md#якорь)` валидируются: якорь сверяется со slug'ами
   заголовков цели (slug-генерация уже в markdown.py:62, поддержка кириллицы
   `\u0400-\u04ff`); битый якорь → `markdown.anchor_not_found`; валидный проходит.
2. `[[document:constitution]]` (цель = существующий record_id) — валидна
   (сегодня падала линк-чеком как «файл не найден»); `[[document:no-such]]` →
   `markdown.record_not_found`; `[[document:plan-softdoc-profile#/relations/0]]`
   резолвится JSON Pointer'ом (jsonfmt.py:248); битый pointer →
   `markdown.pointer_invalid`. Порядок резолвинга цели: record → файл → прочее;
   старые коды `markdown.link.*` не переименовываются.
3. `index rebuild` публикует `mentions.json` ({source_file, source_line,
   source_fragment, target, target_kind: doc|record|fragment}); `records read`
   отдаёт `mentioned_in`; `relations graph` включает mention-вершины (edges с
   `via: "mention"`); `relations tree --from X` рисует окружение деревом.
4. `records undo-relation --id X --pointer /relations/N` показывает прежнее
   состояние ребра из ревизий журнала (history.py:162 `content_at`); `--apply
   --expected-hash` восстанавливает/удаляет ребро как обычную ревизию записи;
   нет данных в журнале → `history.revision_missing`.

**Волна 2 (данные, З5–З7):**

5. `todoc types list --root demo`: entity_types 13 → 14 (+`term`),
   relation_types 9 → 11 (+`uses_term`, `part_of`); 10 терминов глоссария —
   записи `term:*` (md-страницы остаются витринами, в теле — `[[term:*]]`);
   validate = 0.
6. Пилотный флоу (после softdoc З2/З5 — gate) несёт `uses_term` на фактические
   термины и поле `tree` (nodes/edges, props `mode`/`default_branch`);
   `relations graph --from term:<X>` показывает флоу и правила.

**Волна 3 (З8–З9):**

7. `docs flow render --id flow:X` выдаёт state machine, таблицу решений
   (с колонкой «Режим»), mermaid, lineage, термины; `--write` материализует md
   с fm `derived_from` и дисклеймером; `stale` ловит дрейф после правки записи;
   `docs flow walk` проходит каждый путь пилота до терминала с props развилок.
8. `source_anchor` у записи резолвится в раздел витрины (валидация якоря);
   mentions-вершины графа несут фрагменты `{id, fragment}`; счётчики README/
   state от факта (`types list`, число команд CLI, тесты от замера).

## 2. Вне скоупа

- **T10 block-refs** (`^block-id`, абзац-уровень) — этап 3 идеи: заметное
  расширение парсера; вводится отдельным планом, когда единицы «раздел»
  перестанет хватать.
- **T12 инкрементальный парс-кеш** — по порогу (полный rebuild > 1–2 c);
  на demo-масштабе (0.6 c / 376 док) смысла не имеет; дизайн готов в §10 идеи.
- Автолинкинг терминов в произвольных текстах (NLP), рендер графов в
  изображения (mermaid-текст достаточен), валидация artifacts-путей
  (репо кода вне KB), `docs flow render` для glossary-md витрин (термины
  рендерятся позже той же командой — отдельное решение при исполнении).
- Миграция записей-документов для идей (долг самоописания 16-leftovers) —
  не здесь.

## 3. Глобальные ограничения

- **TDD движка**: тесты раньше кода; на каждый новый код — 100% покрытие
  (конвенция репо); существующие 1130 тестов остаются зелёными; счётчики
  тестов в README — от замера после каждой волны.
- **Без новых зависимостей** (click, jsonschema, markdown-it-py — как есть);
  JSON Pointer resolver свой (есть), YAML не появляется.
- **Обратная совместимость конверта**: новые ключи (mentions, mentioned_in,
  tree) добавляются, существующие не переименовываются; `--output` сохраняется;
  фрагменты — парами `{id, fragment}`, не строками-суррогатами.
- **Кеш**: mentions.json — derived/rebuildable, в .todoc/index/current/,
  публикуется тем же store.publish, инвалидация — corpus_digest (тройка
  stat-кеш → digest → rebuild не меняется); записи не кешируются.
- **История**: undo строится поверх журнала снапшотов (before/after байты),
  вторая база истории запрещена; undo-apply — обычная ревизия с CAS.
- Данные демо (волна 2) — только через review-first (`records create
  --preview/--apply`); правки md — `docs edit`/файл + обратное чтение.
- База счётчиков (аудит 2026-11-26): тесты 1130, команд 27, документы 376
  (188 md), entity_types 13, relation_types 9. Код-якоря проверены чтением:
  `_WIKILINK_RE` markdown.py:26, slug-якоря markdown.py:62/279–281,
  `build_backlink_index` markdown.py:333, `resolve_pointer` jsonfmt.py:248,
  `_check_markdown_links` validator.py:134, `graph_neighbors` query.py:116,
  `ensure_index` service.py:180, `content_at` history.py:162,
  records-команды cli.py:1535–1648.

## 4. Архитектура и файловая карта

**Слои u-графа (контракт §7 идеи):**

- **Парсинг**: wikilink-цель = `target[#fragment]`; fragment — `#якорь`
  (md-цель) или `#/pointer` (record-цель); inline-ссылка — target с `#якорем`.
  Индекс mentions: `{source_file, source_line, source_fragment, target,
  target_kind: doc|record|fragment}` — строится из parsed links при rebuild.
- **Резолвинг цели** (валидатор, порядок фиксированный):
  1. `target` (до `#`) совпадает с record_id из реестра записей →
     record-семантика: нет записи → `markdown.record_not_found`; fragment
     `#/…` → `resolve_pointer` по данным записи → не резолвится →
     `markdown.pointer_invalid`; без fragment → ок;
  2. иначе файл-семантика (basename/stem, как сегодня): fragment есть →
     якорь против slug'ов заголовков целевого файла → нет такого →
     `markdown.anchor_not_found`;
  3. иначе существующее поведение (внешние URL — мимо, битые — как сегодня).
- **Кеш**: `mentions.json` в snapshot'е (publish/load как relations.json);
  reuse по digest корректен — mentions = f(файлы). Записи не кешируются.
- **Граф**: `graph_neighbors` дополняется mention-рёбрами (`via: "mention"`,
  вершина-md); BFS семантика прежняя (двунаправленный, bounded).
- **Undo**: план = скан событий журнала файла записи (новейшие → старейшие),
  `content_at(rev)` → разбор JSON → сравнение `relations` (идентичность ребра
  = type_id + target.id); первое отличие → прежнее состояние (ребро было
  другим / отсутствовало). Apply: собрать новый текст файла (обратный дифф
  только `relations`), atomic_write + journal event + CAS `--expected-hash`.
- **Витрина** (`flow render`): из записи `flow` (tree) + рёбра `uses_term`
  собирается markdown: stateDiagram-v2, таблица решений («Приоритет | Rule ID |
  условия… | Исход | Код ошибки | Режим»), flowchart TD, lineage, термины;
  `--write` добавляет fm `derived_from` и дисклеймер «сгенерировано, не править».
- **Walk**: обход tree от корня/узла: вопрос, ветви в порядке приоритета,
  props развилки (`mode: ask-user|auto`, `default_branch`, `timeout`), все
  пути до терминалов (`--all-paths`).

**Файловая карта:**

- Modify: `src/todoc/adapters/formats/markdown.py` (Link.fragment, regex),
  `src/todoc/application/validator.py` (_check_markdown_links + новые проверки;
  parsed-docs словарь на прогон), `src/todoc/application/query.py`
  (graph_neighbors + mentions), `src/todoc/application/registry.py`
  (publish/load mentions.json), `src/todoc/service.py` (payload["mentions"]),
  `src/todoc/cli.py` (docs_read fragment, records read mentioned_in,
  `relations tree`, `records undo-relation`, `docs flow` группа),
  `src/todoc/application/history.py` (helpers для undo-плана).
- Create: `tests/unit/test_link_fragments.py`, `tests/unit/test_mentions.py`,
  `tests/unit/test_relations_tree.py`, `tests/unit/test_records_undo.py`,
  `tests/unit/test_flow_render.py` (+ обновления существующих тестов
  markdown/validator).
- Create (волна 2): `demo/.todoc/entity_types/term/` — 7 файлов;
  `demo/.todoc/relation_types/{uses_term,part_of}/type.json`;
  `demo/records/terms/*.json` — 10 записей; tree в запись пилота (после softdoc).
- Modify (волна 2): `demo/glossary/*.md` (+`[[term:*]]` в теле — живые mentions),
  `demo/README.md`, `README.md`, `demo/references/state/01-overview.md`,
  `demo/references/state/03-cli-reference.md`, `demo/references/state/13-demo-dataset.md`,
  `demo/HOME.md`.

## 5. Задачи

### Задача 1 (волна 1): фрагменты ссылок и новые цели — парсер + валидатор (T7)

**Файлы:**
- Modify: `src/todoc/adapters/formats/markdown.py`, `src/todoc/application/validator.py`
- Create: `tests/unit/test_link_fragments.py`

**Интерфейсы:**
- Consumes: `_WIKILINK_RE` (markdown.py:26), slug-генерация (markdown.py:62),
  `_check_markdown_links` (validator.py:134), `resolve_pointer` (jsonfmt.py:248).
- Produces: `Link.fragment: str` (пусто = нет); порядок резолвинга цели
  record → файл → прочее; коды `markdown.anchor_not_found`,
  `markdown.record_not_found`, `markdown.pointer_invalid`.

- [ ] **Шаг 1 (TDD, красные): тесты** — `[[x#раздел]]` валидный/битый якорь;
  `[..](x.md#якорь)`; `[[document:constitution]]` валидна (сегодня красная —
  битая ссылка); `[[document:no-such]]` → record_not_found;
  `[[document:plan-softdoc-profile#/relations/0]]` валидна;
  `[[document:plan-softdoc-profile#/no/such/key]]` → pointer_invalid;
  wikilink с `|alias` и `#fragment` одновременно; кириллический якорь;
  внешние URL и anchor-only не меняют поведения.
- [ ] **Шаг 2: парсер** — `Link.fragment`, обновить `_WIKILINK_RE` (захват
  фрагмента), inline-target сохранить фрагмент; `resolve_link_target`
  нормализует цель без фрагмента (фрагмент — отдельное поле, не в target).
- [ ] **Шаг 3: валидатор** — parsed-docs словарь на прогон валидации
  (P1-3: файл читается один раз); резолвинг по порядку §4; реестр record_id —
  из набора записей прогона; проверка якоря — slug'и заголовков цели из
  parsed-docs; pointer — чтение файла записи + `resolve_pointer`.
- [ ] **Шаг 4: проверить**

Run: `.venv/bin/python -m pytest tests/unit/test_link_fragments.py -q` — все зелёные;
`.venv/bin/python -m pytest -q` — 1130+N зелёных;
`.venv/bin/todoc validate --root demo --all` — 0 диагностик.

- [ ] **Шаг 5: коммит** `feat(links): фрагменты wikilink и record-цели — anchor/record/pointer валидация (T7)`

### Задача 2 (волна 1): mention-индекс (T8) + mentioned_in (T4) + mention-вершины (T6)

**Файлы:**
- Modify: `registry.py`, `service.py`, `query.py`, `cli.py` (records read, relations graph)
- Create: `tests/unit/test_mentions.py`

**Интерфейсы:**
- Consumes: parsed links (З1), store.publish/load_current (registry.py),
  graph_neighbors (query.py:116), ensure_index (service.py:180).
- Produces: `mentions.json` в снапшоте; `payload["mentions"]`;
  `records read` → `mentioned_in: [{file, section?, line}]`; graph-edges с
  `via: "mention"` для md-вершин.

- [ ] **Шаг 1 (TDD, красные): тесты** — rebuild публикует mentions (tmp-датасет:
  md со `[[document:x]]` и `[y.md#sec]`); mentioned_in в records read;
  graph от record-вершины включает md-вершину; reuse-путь (digest не изменился)
  отдаёт те же mentions без пересборки.
- [ ] **Шаг 2: store** — mentions.json в publish/load_current/meta (тот же
  lifecycle; снапшот атомарный, derived).
- [ ] **Шаг 3: построение** — при rebuild из parsed docs: body-ссылки с
  record-целями (записи) и doc-целями (файлы) → плоский список упоминаний;
  fragment сохраняется.
- [ ] **Шаг 4: вывод** — records read: `mentioned_in` из payload (обратный
  индекс по target); relations graph: mention-рёбра с `via: "mention"`
  (вершины `{kind: "doc"|"record"|"fragment", id, fragment?}`).
- [ ] **Шаг 5: проверить**

Run: `.venv/bin/todoc index rebuild --root demo && todoc records read --root demo --id document:constitution` —
mentioned_in (после З5/З7 непусто; сейчас — пусто, ключ есть);
`.venv/bin/python -m pytest -q` — зелёные. Коммит как в З1 шаг 5
`feat(index): mention-индекс + mentioned_in + mention-вершины графа (T8/T4/T6)`.

### Задача 3 (волна 1): fragment в id (T5) + relations tree (T11)

**Файлы:**
- Modify: `cli.py` (docs_read, новая команда), `query.py` (tree-рендер)
- Create: `tests/unit/test_relations_tree.py`

**Интерфейсы:**
- Consumes: docs_read (cli.py), graph_neighbors + mentions (З2).
- Produces: `docs read --id doc:x#раздел` (fragment из id = синоним `--section`);
  `relations tree --from X [--type T] [--depth N]` — вложенное дерево
  (группировка по type_id, направления, mention-вершины помечены).

- [ ] **Шаг 1 (TDD, красные): тесты** — fragment в id читает секцию
  (равен `--section`); конфликт fragment+`--section` → usage.error; tree:
  группировка, стрелки направлений, упоминания помечены, --depth/--limit
  работают.
- [ ] **Шаг 2: docs_read** — разбор id на `{id, fragment}` до выборки.
- [ ] **Шаг 3: tree** — над теми же данными, что graph (relations + mentions);
  текст-рендер в `--output markdown` (компактные строки с отступами), JSON —
  вложенные children.
- [ ] **Шаг 4: проверить**

Run: `todoc docs read --root demo --id "doc:constitution#Принципы"` — секция;
`todoc relations tree --root demo --from document:constitution --depth 2`;
`.venv/bin/python -m pytest -q` — зелёные. Коммит
`feat(cli): fragment в docs read id + relations tree (T5/T11)`.

### Задача 4 (волна 1): records undo-relation (T3)

**Файлы:**
- Modify: `cli.py`, `history.py` (helpers), `write.py` (запись версии файла)
- Create: `tests/unit/test_records_undo.py`

**Интерфейсы:**
- Consumes: журнал (`read_events`, `content_at` history.py:162), CAS-хэши,
  atomic_write (scanner.py), формат relations (validator.py:621+).
- Produces: `records undo-relation --id X --pointer /relations/N [--apply]
  [--expected-hash H]`; коды: `history.revision_missing`, `edit.relation_missing`
  (указатель вне текущего массива), usage-ошибки клика.

- [ ] **Шаг 1 (TDD, красные): тесты** — план: ребро добавлено последней
  ревизией → «до: ребро отсутствовало»; ребро изменено → прежний target;
  рёбер в журнале нет (чистый журнал) → `history.revision_missing`;
  `--pointer /relations/99` → `edit.relation_missing`; apply восстанавливает
  (validate = 0, новая ревизия в журнале, CAS конфликт без expected-hash
  при расхождении).
- [ ] **Шаг 2: план** — скан событий файла записи новейшие→старейшие;
  `content_at` → JSON → массив `relations`; идентичность ребра =
  type_id + target.id; первое отличие от текущего → прежнее состояние
  (значение | отсутствовало).
- [ ] **Шаг 3: apply** — собрать новый текст (обратный дифф только relations,
  остальной JSON байт-в-байт прежнего форматирования сохраняется), atomic_write,
  journal event, CAS по expected-hash; preview без `--apply`.
- [ ] **Шаг 4: проверить**

Run: `todoc records undo-relation --root demo --id < pilot> --pointer /relations/0`
— план; `--apply --expected-hash …` — применено; `validate` = 0;
`.venv/bin/python -m pytest -q` — зелёные. Коммит
`feat(records): undo-relation — точечный откат ребра из ревизий журнала (T3)`.

### Задача 5 (волна 2, без gate): entity_type term + relation-типы + миграция терминов

**Файлы:**
- Create: `demo/.todoc/entity_types/term/` (7 файлов), `demo/.todoc/relation_types/uses_term/type.json`,
  `demo/.todoc/relation_types/part_of/type.json`, `demo/records/terms/*.json` — 10
- Modify: `demo/glossary/*.md` (в теле — `[[term:<slug>]]`), счётчики в
  `demo/README.md`

**Интерфейсы:**
- Consumes: формат `entity_types/task/` (schema/template/prompts ×4);
  record_id-реестр (З1/З2 — mentions живые).
- Produces: `term:<slug>` (^term:[a-z0-9][a-z0-9-]*$; required title/term_type/
  definition; enum term_type: actor|role|system|component|event|rule|field|
  external|concept; aliases[], responsible, source_path (glossary/<slug>.md),
  artifacts[{path, role}], relations[]); `uses_term` (source: flow|rule|
  incident|release|change|api-endpoint|domain-event; target: term);
  `part_of` (term→term).

- [ ] **Шаг 1: дескрипторы** — entity_type + 2 relation-типа по образцу
  соседних; `todoc types list` — entity 13 → 14, relation 9 → 11.
- [ ] **Шаг 2 (TDD, красные→зелёные по данным): схемы** — schema.json с
  additionalProperties: true у корня; превью-валидация каждой записи = 0
  диагностик до apply.
- [ ] **Шаг 3: 10 записей терминов** — `records create --preview/--apply`;
  source_path = соответствующий glossary/<slug>.md; artifacts — из факта
  (у большинства пусто/по смыслу термина); part_of — где очевидно
  (диагностика ∈ glossary-иерархии — от факта, не выдумывать).
- [ ] **Шаг 4: mentions в md-витринах** — в теле каждой glossary-страницы
  wikilink на запись (форма: двойные квадратные скобки вокруг
  `term:<slug>` — валидатор З1 пропускает record-цели; mention-индекс
  после rebuild несёт 10 упоминаний); `records read --id term:<slug>` —
  mentioned_in показывает витрину.
- [ ] **Шаг 5: проверить**

Run: `todoc validate --root demo --all` — 0; `todoc records list --root demo --type term --limit 12` — 10;
`todoc relations tree --root demo --from term:<X>` — витрина в дереве. Коммит
`feat(demo-catalog): entity_type term + uses_term/part_of + 10 терминов-записей (волна 2)`.

### Задача 6 (волна 2, **gate: softdoc З2/З5 исполнены**): uses_term пилота + tree в flow

**Файлы:**
- Modify: `demo/records/flows/order-placement.json` (relations += uses_term;
  поле tree), возможно `demo/records/rules/*.json` (uses_term)

**Интерфейсы:**
- Consumes: entity flow/rule + записи пилота (softdoc З2/З5); схема term (З5).
- Produces: `flow:order-placement` → `uses_term` на фактические термины пилота
  (актор/системы — от факта демо, не выдумывать); `tree` = {nodes[{id, type:
  question|action|terminal, prompt?, props{mode, default_branch?, timeout?}}],
  edges[{from, when?, to, priority}]} — по эталону идеи documentation-system
  (P1 account-blocked → P2 no-funds → P3 gateway-down → happy path).

- [ ] **Шаг 1 (gate-проверка):** `todoc records read --id flow:order-placement`
  существует (иначе — останов, волна 2 ждёт softdoc; отметить в §8).
- [ ] **Шаг 2: tree в запись** — nodes/edges/props по таблице решений пилота;
  превью = 0 диагностик, apply.
- [ ] **Шаг 3: uses_term** — от flow и правил к терминам (потребитель пишет
  ребро); preview/apply.
- [ ] **Шаг 4: проверить**

Run: `todoc relations tree --root demo --from term:<X>` — «правило → флоу → термины»;
`todoc relations graph --from term:<X>` — рёбра uses_term; validate = 0. Коммит
`feat(demo-catalog): tree пилотного флоу + uses_term рёбра (gate softdoc пройден)`.

### Задача 7 (волна 2): счётчики и документация

**Файлы:**
- Modify: `demo/README.md`, `README.md`, `demo/references/state/01-overview.md`,
  `demo/references/state/13-demo-dataset.md`, `demo/HOME.md`

- [ ] **Шаг 1: счётчики от факта** — types list (entity 14 / relation 11
  + вычитать softdoc-надбавку, если он уже исполнен — считать от факта),
  записи/документы (`check --root demo`), тесты (pytest), команды CLI.
- [ ] **Шаг 2: тексты** — HOME: раздел «Справочник сущностей»; state/13: состав
  term-записей + пример `relations tree`; state/03: `records undo-relation`,
  `relations tree`, fragment в `docs read`; demo/README: mentions.
- [ ] **Шаг 3: финальный прогон волны**

Run: `todoc validate --root demo --all` — 0; `python3 tools/linkcheck.py demo` — 0 битых;
`pytest -q` — зелёные. Коммит `docs(demo-catalog): счётчики и справочники волны 2`.

### Задача 8 (волна 3, gate: З6): docs flow render/write (T1) + flow walk (T2)

**Файлы:**
- Modify: `cli.py` (группа `docs flow`), новый `src/todoc/application/flow_view.py`
- Create: `tests/unit/test_flow_render.py`

**Интерфейсы:**
- Consumes: запись flow (tree, states, outcomes), рёбра uses_term (З6),
  derived_from/stale (staleness.py), шаблон «Режим» (softdoc З4).
- Produces: `docs flow render --id flow:X [--section state|table|mermaid|
  lineage|terms] [--write PATH]`; `docs flow walk --id flow:X [--at node:ID]
  [--all-paths]`.

- [ ] **Шаг 1 (TDD, красные): тесты** — render: 4 артефакта + Режим + термины
  из uses_term; walk: корень → ветви по приоритету, props развилки, каждый путь
  до терминала; --write: fm derived_from + дисклеймер, файл валиден;
  повторный --write после правки записи → stale видит дрейф.
- [ ] **Шаг 2: flow_view.py** — чистая сборка markdown из записи (детерминизм);
  --write через atomic_write + journal event.
- [ ] **Шаг 3: cli** — группа `docs flow` (render, walk); конверт `--output`.
- [ ] **Шаг 4: проверить**

Run: `todoc docs flow render --root demo --id flow:order-placement` — витрина;
`--write flows/order-placement.md` → `todoc stale --root demo` — drift виден
после правки записи; `docs flow walk --all-paths` — все пути до терминалов.
Коммит `feat(flow): render/write + walk — витрины и навигатор дерева решений (T1/T2)`.

### Задача 9 (волна 3, этап 2): source_anchor + фрагментные вершины (T9) + финал

**Файлы:**
- Modify: `demo/.todoc/entity_types/term/schema.json` (+source_anchor, опц.),
  `validator.py` (anchor source_anchor при наличии), `query.py`/mentions
  (вершины `{id, fragment}`), счётчики финал

- [ ] **Шаг 1 (TDD):** schema-расширение; валидация: source_anchor задан →
  якорь существует в source_path-документе (anchor_not_found иначе);
  mentions/graph несут фрагменты.
- [ ] **Шаг 2: данные** — заполнить source_anchor у 1–2 терминов с крупными
  витринами (от факта демо; если страницы атомарны — поле остаётся пустым,
  это легально).
- [ ] **Шаг 3: финальные счётчики и прогон**

Run: `todoc validate --root demo --all` — 0; `pytest -q` — от замера;
`todoc types list` / `todoc check --root demo` — от факта; README/state —
синхронизированы; `python3 tools/linkcheck.py demo` — 0 битых. Коммит
`feat(meta): source_anchor + фрагментные mention-вершины (этап 2, T9) + финальные счётчики`.

## 6. Definition of Done

- [ ] Задачи 1–9 исполнены; волны — отдельными коммитами (минимальная
  готовность = волна 1: движок u-graph/undo; полная = волна 3).
- [ ] Критерии успеха §1.1–1.8 выполнены и проверены командами из шагов.
- [ ] `todoc validate --root demo --all` = 0; `check` — ok; linkcheck — 0 битых.
- [ ] pytest зелёный от замера; новый код движка — 100% покрытие; счётчики
  README/state от факта.
- [ ] Критерии приёмки идеи doc:entity-catalog-idea (1–7) закрыты (7 — в
  объёме З8: render/walk/undo/mentioned_in; упоминания в витринах и планах).
- [ ] T10/T12 вне скоупа (зафиксировано §2), стейты статусов планов не меняются
  (снятие `done` — только по явной фразе пользователя).

## 7. Риски и митигации

| Риск | В×В | Митигация | Владелец |
|---|---|---|---|
| Регресс существующих wikilink-тестов при изменении regex | С×Н | фрагмент — новое поле, target без фрагмента байт-в-байт прежний; обновлять тесты только там, где якорь реально отбрасывался | агент |
| `[[document:x]]`-цели путаются с файлами (basename совпадает) | Н×С | порядок резолвинга фиксирован: record первым; конфликт = честная диагностика (ambiguous не вводим) | агент |
| Pointer хрупок к реордерингу массива | С×Н | альтернатива «по индексам» отвергнута в идее; разрешены только ключевые pointer'ы; диагностика pointer_invalid честная | агент |
| Undo при сдвиге индексов массива между ревизиями | С×С | идентичность ребра = type_id+target.id (не индекс); указатель адресует текущее состояние; тест на сдвиг | агент |
| records edit отсутствует — apply-путь undo | С×С | apply через write-путь + journal event (как records create); CAS expected-hash; тест конфликта | агент |
| Gate З6/З8 на softdoc — блокировка волны 2/3 | Н×С | З5 исполняется без gate (термины и mentions живут независимо); З6/З8 честно ждут; §8 фиксирует | агент |
| Mentions.json раздувает снапшот | Н×Н | плоские кортежи; demo-масштаб — килобайты; derived/rebuildable | агент |
| Двойной парс (валидатор+индекс) на больших корпусах | Н×Н | parsed-docs словарь на прогон (один парс на файл); T12 — вне скоупа по порогу | агент |

## 8. Прогресс и отклонения

- Статус: не начат (2026-11-26). Первая задача — Задача 1, шаг 1.
- План составлен по идее doc:entity-catalog-idea (321 строка, 10 разделов) —
  все код-якоря проверены чтением (markdown.py:26/62/333, jsonfmt.py:248,
  validator.py:134/621, query.py:116, service.py:180, history.py:162,
  cli.py:1535–1648); счётчики базы от факта 2026-11-26: тесты 1130, команды 27,
  entity 13 / relation 9, документы 376 (188 md).
- Волна 2 (З6) — gate на softdoc З2/З5: если softdoc не исполнен, З6/З8
  останавливаются на gate-проверке, З1–З5 и З7 (без пилотных рёбер) исполняются.
- Отклонений нет.

<!-- Формат строки отклонения: `YYYY-MM-DD — задача N, шаг M: что не так → что
     выбрано вместо и почему`. Шаги задним числом не переписывать. -->
