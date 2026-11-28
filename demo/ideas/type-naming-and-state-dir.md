---
id: doc:ideas/type-naming-and-state-dir.md
title: "Идея: стандарт именования типов (1–2 слова snake_case) и тип папки state как реальная картина мира (AS-IS)"
doc_type: idea
lang: ru
status: captured
created: 2026-11-26
updated: 2026-11-28
tags: [ideas, idea, types, naming, snake-case, dir-type, state, таксономия]
related: ["[[constitution.md]]", "[[documentation-system]]", "[[agent-state]]", "[[entity-to-folder]]", "[[docs-move]]"]
---

# Идея: стандарт именования типов (`1–2` слова `snake_case`) и тип папки `state` (реальная картина мира `AS-IS`)

- Тип: `idea`
- Создан: 2026-11-26
- Идентификатор: `doc:ideas/type-naming-and-state-dir.md`
- Статус: `captured` (идея зафиксирована, не перешла в план)

## Суть

1. **Единый машинно-проверяемый стандарт именования всех типов:** идентификатор любого типа папки (`dir_type`), типа сущности (`entity_type`) и типа файла/документа (`doc_type`) — наравне с `relation_type` — задаётся **только строчной английской латиницей из одного или максимум двух слов, разделённых нижним подчёркиванием `_`** (`^[a-z][a-z0-9]*(?:_[a-z0-9]+)?$`).
2. **Новый базовый тип папки `state` (`dir_type: state`) для реальной картины мира (`AS-IS`):** замкнуть триаду временны́х слоёв знания — **`idea`** (замыслы и гипотезы) → **`plan`** (утверждённые планы и ход работ) → **`state`** (то, что реально реализовано и действует в системе прямо сейчас).

## Проблема

1. **Разнобой разделителей в типах метамодели ломает предсказуемость для агента.** Сейчас в самом `demo/.todoc/` типы связей (`relation_types`) уже названы в `snake_case` из 1–2 слов (`belongs_to`, `derived_from`, `uses_term`, `subtask_of`), тогда как `doc_types` и `entity_types` названы через дефис (`bug-report`, `flow-doc`, `api-endpoint`, `task-snapshot`), а в `src/todoc/typing_system/descriptors.py:55` вообще нет валидации формата `type_id` (проверяется лишь `isinstance(type_id, str) and bool(type_id)` и даже не сверяется совпадение `type_id` с именем папки дескриптора). В результате агент путает `--type bug-report` и `--type bug_report`, `derived_from` и `derived-from`, а ничто не мешает завести кириллический или пятисловный тип.
2. **В триаде знания отсутствует канонический слой «что реально реализовано» (`state`).** В `todoc` есть `dir_type: idea` (`ideas/`) для будущих идей и `dir_type: plan` (`plan/`) для планов работ, но **нет `dir_type: state`**. Из-за этого:
   - актуальные срезы состояния самого движка (`01-overview.md` … `19-interop-exports.md`) вынужденно лежат в `demo/references/state/` с `dir_type: unknown` и размытым `doc_type: reference`;
   - закрытые планы (`status: done`) накапливаются в `plan/`, и чтобы узнать, как система реально работает **сегодня**, агенту приходится перечитывать цепочку старых планов и отделять прошлые намерения от фактически построенной реальности.

## Принципы

1. **Чёткое визуальное различие между типом метамодели и именем файла данных:**
   - **Имена типов** (`dir_type`, `entity_type`, `doc_type`, `relation_type`) — строго `1–2` английских слова через `_` (`bug_report`, `flow_doc`, `state_doc`, `api_endpoint`, `state`);
   - **Имена файлов и папок данных** в корпусе — латинский `kebab-case` (`ideas/entity-to-folder.md`, `skills/process/todoc-capture/`, по стандарту Agent Skills и конвенции `notes/agent-contract.md`).
2. **Лаконичность таксономии (не больше двух слов).** Ограничение в `1–2` слова не даёт превращать `type_id` в длинные предложения (`legacy_customer_onboarding_spec_v2`): род объекта живёт в типе (`spec_doc`, `state_doc`), а подтипы, домены и статусы — в полях, папках и тегах.
3. **Триада `idea → plan → state` как фундамент жизненного цикла знания:**
   - `idea` — *возможное будущее* («что придумали / обсуждаем»);
   - `plan` — *переход и стройка* («как меняем систему, шаги и задачи»);
   - `state` — *актуальная реальность `AS-IS`* («что уже реализовано и является фактом в системе сегодня»).
4. **Не путать предметную папку `state/` с сессионным `state.json`.** Папка `state/` (`dir_type: state`) внутри `DATA_ROOT` хранит версионируемое в Git знание о реальном устройстве продукта/домена (`AS-IS`), тогда как CLI `todoc state` ([агентский стейт](agent-state.md)) хранит вне данных летучие курсоры текущей сессии агента (`~/.local/state/todoc/state-<id>.json`).

## Предложение

### 1. Правило именования типов и валидация в движке

В `src/todoc/typing_system/descriptors.py` (`TypeRegistry` и `descriptor_diagnostics`) закрепляется единый контракт для `dir_type`, `entity_type`, `doc_type` и `relation_type`:

```python
TYPE_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)?$")
TYPE_ID_MAX = 40
```

- **Разрешено:** ровно 1 слово (`state`, `idea`, `plan`, `note`, `flow`, `task`, `term`, `skill`, `moc`, `adr`, `slo`) или 2 слова через одно нижнее подчёркивание (`bug_report`, `state_doc`, `flow_doc`, `api_contract`, `agent_skill`, `api_endpoint`, `domain_event`, `bounded_context`, `task_snapshot`, `derived_from`).
- **Запрещено (ошибка `config.invalid_type_id` в `check-config` и `validate`):** дефисы (`bug-report`), 3 и более слов (`a_b_c`), прописные буквы (`BugReport`), не-ASCII символы (`отчёт`), ведущие/хвостовые/двойные подчёркивания (`_state`, `a__b`).
- **Согласованность с папкой типа (`config.type_dir_mismatch`):** имя каталога `.todoc/<kind_dir>/<dir_name>/` обязано побайтово совпадать с полем `type_id` в `type.json`.

Таблица нормализации существующих дефисных типов `demo/.todoc/` при миграции:

| Семейство | Было (kebab-case) | Станет (1–2 слова `snake_case`) |
|---|---|---|
| `doc_type` | `after-plan`, `agent-skill`, `api-contract`, `architecture-doc`, `audit-report`, `bug-report`, `competitive-analysis`, `competitor-card`, `demo-readme`, `flow-doc`, `glossary-entry`, `implementation-plan`, `release-note`, `research-note`, `research-report`, `spec-doc`, `task-report` | `after_plan`, `agent_skill`, `api_contract`, `architecture_doc`, `audit_report`, `bug_report`, `competitive_analysis`, `competitor_card`, `demo_readme`, `flow_doc`, `glossary_entry`, `implementation_plan`, `release_note`, `research_note`, `research_report`, `spec_doc`, `task_report` |
| `entity_type` | `api-endpoint`, `bounded-context`, `domain-event`, `task-snapshot` | `api_endpoint`, `bounded_context`, `domain_event`, `task_snapshot` |
| `dir_type` | все текущие уже 1 слово (`idea`, `plan`, `skill`, `flows`, `notes`…) + новый `state` | без переименований + добавляется `state` |
| `relation_type` | все 18 уже в `1–2` слова `snake_case` (`belongs_to`, `derived_from`, `uses_term`…) | уже соответствуют стандарту на 100% |

### 2. Тип папки `state` и документ реальности `state_doc`

1. **Зарезервированный `dir_type: state`:**
   - В `.todoc/dir_types/state/type.json` создаётся дескриптор типа папки `state` (*«Актуальная картина мира (AS-IS): что реально реализовано и действует в системе сейчас»*).
   - В `src/todoc/typing_system/resolver.py` (`RESERVED_DIR_TYPES`) и `.todoc/rules/directory-rules.json` добавляется правило `"glob": "**/state"` → `"dir_type": "state"`. Благодаря маске `**/state` папка `state/` работает и в корне датасета (`<DATA_ROOT>/state/`), и внутри любого проекта или развёрнутого через [`todoc folderize`](entity-to-folder.md) домена (`projects/shop/state/`, `ideas/auth/state/`).
2. **Парный тип документа `state_doc` (`doc_type`):**
   - Описывает живой срез реализованной подсистемы/фичи (обязательные секции, например: `## Назначение`, `## Реализованное поведение`, `## Контракты и инварианты`).
   - Допустимые статусы (`allowed_statuses`): `active`, `deprecated`, `superseded` (никаких `draft`/`planned` — в `state/` лежит только то, что уже в строю).
   - Поддерживает `derived_from` / связь `implements` от закрытых планов и задач, чтобы было видно, какой план породил или обновил текущее состояние.
3. **Жизненный цикл «кристаллизации» (`idea → plan → state`):**
   - Идея рождается в `ideas/` (`status: captured`).
   - При утверждении создаётся план в `plan/` (`status: in_progress`).
   - Когда план выполнен и переводится в `done` (скил `todoc-transitions` / финал `todoc-execute`), итоговая выжимка *«как это теперь реально работает»* создаётся или обновляется в `state/` (`dir_type: state`), а в демо-датасете существующие 19 файлов `references/state/*.md` переезжают на своё законное место в корневую папку `demo/state/` (одной командой через [`todoc docs move`](docs-move.md)).
   - Для агента при ответе на вопросы о текущем поведении системы поиск по `--within state` (или фильтр `--dir-type state` в `docs search`) становится главным источником правды, не замусоренным нереализованными идеями и архивными планами.

## План внедрения

1. **Фаза 1 — Валидатор именования типов (`TYPE_ID_RE`) и миграция `demo/.todoc/`:**
   - Добавить проверку `^[a-z][a-z0-9]*(?:_[a-z0-9]+)?$` и `folder_name == type_id` в `descriptors.py` (`check-config` и `validate`).
   - Мигрировать дескрипторы типов, `document-rules.json`, поля `doc_type:` во front matter документов и `entity_type:` в `demo/records/` с дефисов на `_` (включая обновление ссылок в промптах и скилах).
   - *Acceptance:* `todoc check-config --root demo` = `0` ошибок; попытка создать тип `bad-name` или `three_word_type` возвращает `config.invalid_type_id`; `100%` branch coverage.
2. **Фаза 2 — Введение `dir_type: state`, `doc_type: state_doc` и фильтр `--dir-type`:**
   - Добавить `state` в `RESERVED_DIR_TYPES`, создать `.todoc/dir_types/state/` и `.todoc/doc_types/state_doc/`.
   - Перенести актуальные срезы состояния в `demo/state/` с самоописанием `demo/state/.config.json` и обновить `HOME.md`.
   - Обновить скилы `todoc-execute` и `todoc-transitions` правилом актуализации `state/` при закрытии плана в `done`.
   - *Acceptance:* `todoc explain-path --root demo state` возвращает `dir_type: "state"`; `todoc validate --root demo --all` = `0` диагностик; `tools/linkcheck.py` = `0` broken.

## Открытые вопросы

- **Единственное или множественное число для однословных `dir_type`:** сейчас в `dir_types` смешаны единственное (`idea`, `plan`, `skill`, `state`, `research`, `glossary`, `inbox`) и множественное число (`bugs`, `notes`, `tasks`, `flows`, `guides`, `specs`, `reports`). Оба варианта проходят правило «1 английское слово», но стоит ли при миграции Фазы 1 заодно унифицировать все `dir_type` в единственное число (`bug`, `note`, `task`, `flow`), оставив имена самих папок на диске прежними (`bugs/`, `notes/`) через `directory-rules.json`?
- **Обратная совместимость для внешних пользовательских датасетов:** делать нарушение `TYPE_ID_RE` сразу жёстким `error` в `check-config`/`validate`, или дать команду автомиграции `todoc fix --type-ids` для перевода старых kebab-case типов в `snake_case`?

## Связанные документы

- [Конституция `todoc` (§5: типовая система, дескрипторы и зарезервированные папки)](../plan/constitution.md)
- [Идея: система документирования кодовой базы (жизненный цикл дельт и спецификаций)](documentation-system.md)
- [Идея: агентский стейт — `state.json` вне данных (отличие сессионного стейта от предметной папки `state/`)](agent-state.md)
- [Идея: `todoc folderize` — преобразование сущности в папку-домен (вложенные `plan/` и `state/`)](entity-to-folder.md)
- [Идея: `todoc docs move` — транзакционный перенос документов (переезд `references/state/` → `state/`)](docs-move.md)

## Связь с выпуском единого CLI

Сохранены разные классы типов, существующие идентификаторы и отдельное XDG-состояние. Переименование типов остаётся в объёме идеи.
[Сводка выпуска единого CLI](../notes/unified-cli-release.md).
