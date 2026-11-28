---
id: doc:ideas/entity-to-folder.md
title: "Идея: todoc folderize — преобразование любой сущности в папку-домен с .config.json, сохранением связей и поиском внутри раздела"
doc_type: idea
lang: ru
status: captured
created: 2026-11-26
updated: 2026-11-28
tags: [ideas, idea, folderize, folder, config, move, domain, иерархия]
related: ["[[folder-config]]", "[[docs-move]]", "[[agent-state]]", "[[skills-engine]]", "[[constitution.md]]"]
---

# Идея: `todoc folderize` — преобразование любой сущности в папку-домен

- Тип: `idea`
- Создан: 2026-11-26
- Идентификатор: `doc:ideas/entity-to-folder.md`
- Статус: `captured` (идея зафиксирована, не перешла в план)

## Суть

Добавить CLI-команду **`todoc folderize`** (преобразование листа в контейнер — паттерн *Folder Note / Page Bundle*), которая **одной транзакционной операцией** превращает любую сущность датасета (Markdown-документ идеи, плана, флоу, заметки или JSON-запись задачи/проекта) в одноимённую папку на том же месте, автоматически формирует для неё самоописание `.config.json`, переносит саму сущность в корень новой папки с пересчётом всех ссылок и связей (через общее ядро с [`todoc docs move`](docs-move.md)) и открывает возможность вкладывать дочерние артефакты (`plan/`, `tasks/`, исследования) с локализованным поиском внутри получившегося домена (`--within`).

## Проблема

1. **Плоские свалки `ideas/`, `plan/`, `records/tasks/` теряют доменную связность при росте.** Пока идея маленькая — ей достаточно одного файла `ideas/todocignore.md`. Но когда вокруг идеи вырастают ресёрч, 2 плана реализации и 15 задач-записей, они разлетаются по разным корневым папкам (`ideas/`, `plan/`, `.research/`, `records/tasks/`). Нельзя сделать **поиск внутри одной идеи** (`--within`), нельзя окинуть глазом дерево всех материалов этой идеи через `docs tree`, нельзя перенести весь узел целиком в другой проект.
2. **Ручное разворачивание сущности в папку дорого и чревато поломкой графа.** Чтобы превратить `ideas/todocignore.md` в контейнер `ideas/todocignore/`, агенту сейчас нужно вручную создать папку, написать валидный `.config.json` (уложившись в лимиты `_TITLE_MAX = 80`, `_DESCRIPTION_MAX = 500`, формат `aliases` и избежав `alias_collision`), переместить файл на уровень глубже (`+1` сегмент `../` во всех его собственных исходящих ссылках!), переписать все входящие ссылки в `HOME.md` и планах, обновить `source_path`, `derived_from`, пересобрать индекс и прогнать `validate --all`.
3. **Записи (`records`) не умеют скоупиться по папке домена (`--within`).** В `docs search` и `docs tree` уже есть фильтр `--within <folder>`, а в `records list` и `records query` его нет — даже если положить JSON-задачи в дочернюю папку плана внутри идеи (`ideas/todocignore/plan/v1/tasks/`), штатный запрос по записям пока не умеет ограничиваться этим поддеревом.

## Принципы

1. **Плавный рост без преждевременной бюрократии (Leaf → Container).** Любая идея, план или задача рождается простым одиночным файлом. В папку она превращается ровно в тот момент, когда у неё появляются дочерние материалы — одной командой, без потерь.
2. **Папка создаётся ровно там, где лежала сущность, с тем же именем (`<parent>/<stem>/`).** Исходный файл `<parent>/<stem>.<ext>` переезжает в корень папки как `<parent>/<stem>/<stem>.<ext>`. Сохранение исходного `<stem>.<ext>` делает операцию бесшовной для всех wikilinks `[[<stem>]]` и `related: ["[[<stem>]]"]` (они продолжают резолвиться без переписывания и без `markdown.link.ambiguous`) и сохраняет `record_id` у JSON-записей.
3. **Автозаполнение `.config.json` из самой сущности (единый источник метаданных).** Заголовок, краткое описание, язык и теги не придумываются заново, а извлекаются детерминированно из front matter / секции «Суть» документа или полей JSON-записи по контракту [`.config.json`](folder-config.md). Благодаря этому вложенные дочерние планы и задачи сразу получают поисковый буст предка (`cfg_tokens` в `search.py`) и видимость в `docs suggest`.
4. **Общее транзакционное ядро с [`todoc docs move`](docs-move.md).** Перемещение сущности на уровень глубже (`<parent>/<stem>.<ext>` → `<parent>/<stem>/<stem>.<ext>`) выполняется тем же атомарным планировщиком `MovePlan` (пересчёт всех 8 контуров ссылок и связей, предвалидация в памяти, откат при любой ошибке, единый `change_id` в `history`).
5. **Рекурсивная композируемость на любую глубину.** Принцип одинаков для любой сущности: идею можно развернуть в папку идеи (`ideas/<idea>/`), внутри неё положить `plan/`, разросшийся план развернуть в папку плана (`ideas/<idea>/plan/<plan-slug>/`), внутри него положить дочерние `tasks/`, либо перенести задачу между папками проектов через `move`.
6. **Канон CLI `todoc` (`review-first` + экономия контекста).** По умолчанию `--preview`, запись по `--apply`, выход — компактный JSON-конверт `schema_version: 1` (`ok: true|false`, счётчики правок, `generation_id`, `0` диагностик без необходимости вызывать `validate` вторым шагом).

## Предложение

### 1. Контракт команды CLI

Команда верхнего уровня (так как применяется и к документам `docs`, и к записям `records`; при желании — алиасы `todoc docs folderize` и `todoc records folderize`):

```bash
# Предпросмотр преобразования идеи в папку-домен (по умолчанию --preview):
todoc folderize --root KB --id doc:ideas/todocignore.md

# Применение с созданием типовых дочерних подпапок (например, plan и tasks):
todoc folderize --root KB --id doc:ideas/todocignore.md --subdirs plan,tasks --apply --if-hash sha256:...

# То же для любой JSON-записи (задачи, проекта, флоу):
todoc folderize --root KB --id task:shop-0002 --apply
```

Опции:
- `(--id <doc_id|record_id> | --path <rel_path>)` — целевая сущность (Markdown-документ или JSON-запись);
- `--title <str>` / `--description <str>` / `--aliases "a|b"` / `--order <int>` — опциональные переопределения полей `.config.json` (если не переданы — выводятся из самой сущности);
- `--subdirs <comma-list>` — опциональный список пустых типизированных подпапок внутри нового контейнера (например, `plan`, `tasks`, `.research` — валидируются имена сегментов `[a-z0-9._-]+`);
- `--preview` (дефолт) / `--apply`, `--if-hash <sha256>`, `--keep-id`, `--output json|table|markdown`.

### 2. Что происходит внутри операции шаг за шагом

Пусть на входе документ `ideas/todocignore.md` (или запись `records/tasks/auth-refactor.json`):

1. **Проверка предусловий:**
   - Сущность найдена и ещё не является корневым файлом одноимённой папки (`ideas/todocignore/todocignore.md` → идемпотентный отказ `folderize.already_folderized`, `EXIT_CONFLICT = 4`).
   - Целевая папка `<parent>/<stem>/` (`ideas/todocignore/`) ещё не существует (либо пуста); при занятости — `folderize.target_exists` (`EXIT_CONFLICT = 4`).
2. **Формирование `<parent>/<stem>/.config.json` по схеме `folder_config.py`:**
   - `schema_version`: `1`;
   - `title`: из `fm.title` (для документа) или `data.title` / `data.name` (для записи); если строка длиннее лимита `_TITLE_MAX` (`80` симв.), аккуратно усекается по границе слова с `…` (либо берётся короткий H1 / явный `--title`), чтобы гарантированно пройти `validate_folder_configs`;
   - `description`: первая содержательная фраза секции `## Суть` / первого абзаца документа или поля `summary`/`description` записи (до `500` симв.);
   - `lang`: из `fm.lang` / `data.lang` (если есть);
   - `tags`: из `fm.tags` / `data.tags` (список строк `1..80` симв.);
   - `aliases` / `order`: если переданы флагами (с предпроверкой отсутствия `folder.config.alias_collision` по всему датасету).
3. **Транзакционный перенос сущности в корень новой папки через `MovePlan` ([`docs move`](docs-move.md)):**
   - Путь меняется с `<parent>/<stem>.<ext>` на `<parent>/<stem>/<stem>.<ext>`.
   - У Markdown-документа все его собственные исходящие относительные ссылки `[...](../other.md)` автоматически сдвигаются на один уровень глубже (`../../other.md`), а все входящие ссылки из `HOME.md`, планов и отчётов переписываются на `<parent>/<stem>/<stem>.<ext>`.
   - Обновляются `source_path` в `records/documents/*.json`, якоря `derived_from` (с авто-реанкорингом при сдвиге исходящих ссылок), а также `id: doc:<path>` и рёбра `relations` (если не задан кастомный `id` или `--keep-id`).
   - Если `doc_type` раньше выводился только из плоского glob-правила родительской папки (без `**` и без `doc_type` во front matter), `doc_type` материализуется во front matter, чтобы тип не слетел в `unknown`.
4. **Создание опциональных дочерних папок (`--subdirs`):**
   - Например, `ideas/todocignore/plan/` (которая благодаря существующему правилу `"glob": "**/plan"` в `.todoc/rules/directory-rules.json` **автоматически** получает `dir_type: "plan"`!) и `ideas/todocignore/tasks/`.
5. **Предвалидация в памяти, атомарная запись, история и индекс:**
   - Проверяются `validate_dataset`, `validate_relations` и `validate_folder_configs` до коммита на диск.
   - Записываются `.config.json` + обновлённые файлы под единым `change_id` (`kind: "folderize"`) в `history/journal.jsonl`, публикуется новое поколение индекса.

### 3. Итоговая иерархия домена и доменный поиск (`--within`)

После применения на идее и дочернем плане структура выглядит самоподобно на любом уровне:

```text
ideas/
└── todocignore/                         ← бывший ideas/todocignore.md, теперь домен идеи
    ├── .config.json                     ← title, description, tags идеи (буст поиска + docs tree --meta)
    ├── todocignore.md                   ← сама идея в корне своей папки
    └── plan/                            ← дочерние планы этой идеи (dir_type: plan по правилу **/plan)
        └── v1-core/                     ← план, тоже развёрнутый через todoc folderize
            ├── .config.json             ← метаданные плана
            ├── v1-core.md               ← документ плана
            └── tasks/                   ← задачи конкретно этого плана
                ├── task-01-matcher.json
                └── task-02-scanner.json
```

Что это сразу даёт агенту и человеку:
- **Поиск строго внутри идеи (со всеми её планами, заметками и задачами):**
  - `todoc docs search --root KB --within ideas/todocignore --query "can_prune_dir"` (уже работает в `search.py`!);
  - **расширение в рамках этой идеи:** добавить симметричный фильтр `--within <folder>` в `todoc records list` и `todoc records query` (по префиксу `record["path"]`), чтобы одной опцией искать и все задачи `task:*`, лежащие внутри `ideas/todocignore/` или папки конкретного проекта!
- **Карта домена одной командой:** `todoc docs tree --root KB --within ideas/todocignore --meta`.
- **Навигация «куда положить новый план/задачу»:** `todoc docs suggest --root KB --query "todocignore"` сразу находит папку идеи по её `.config.json`.
- **Перенос задачи или целого узла в другой проект:** в паре с расширением [`docs move`](docs-move.md) на папки и записи любую задачу (`task-02.json`) или ветку плана можно перенести в папку другого проекта с автообновлением всех связей.

### 4. Формат ответа CLI

```json
{
  "schema_version": 1,
  "ok": true,
  "data": {
    "dataset_id": "dataset-80c70868",
    "applied": true,
    "folderized": {
      "id": "doc:ideas/todocignore/todocignore.md",
      "kind": "document",
      "from": "ideas/todocignore.md",
      "folder": "ideas/todocignore",
      "root_entity": "ideas/todocignore/todocignore.md",
      "config_path": "ideas/todocignore/.config.json",
      "subdirs_created": ["ideas/todocignore/plan", "ideas/todocignore/tasks"]
    },
    "rewrites": {
      "outbound_links": 5,
      "inbound_docs": 2,
      "inbound_links": 2,
      "records": 0,
      "derived_from": 0
    },
    "index": {
      "generation_id": "c41e9082ba11",
      "diagnostics": 0
    },
    "change_id": "chg_91b20e44"
  },
  "diagnostics": [],
  "next_actions": [
    {
      "argv": ["todoc", "--root", "demo", "docs", "tree", "--within", "ideas/todocignore", "--meta"],
      "purpose": "Посмотреть структуру созданного домена"
    },
    {
      "argv": ["todoc", "--root", "demo", "docs", "search", "--within", "ideas/todocignore", "--query", "<запрос>"],
      "purpose": "Искать документы внутри домена сущности"
    }
  ]
}
```

## План внедрения

1. **Фаза 1 — Скоуп `--within` для записей (`records list` / `records query`):**
   - Добавить фильтр `--within <dir>` (и поле `within` в `QuerySpec`) по префиксу `record["path"]` с поддержкой дефолта из `context.current_project` ([агентский стейт](agent-state.md)).
   - *Acceptance:* `records list --within ideas/foo` возвращает только записи внутри поддерева `ideas/foo/`.
2. **Фаза 2 — Ядро `folderize` поверх планировщика `MovePlan` ([`docs move`](docs-move.md)):**
   - Генератор `.config.json` из метаданных документа или JSON-записи с соблюдением всех ограничений `folder_config.py` (`title <= 80`, `description <= 500`, проверка `alias_collision`).
   - Построение единого транзакционного плана: создание `<parent>/<stem>/`, запись `.config.json`, перенос `<stem>.<ext>` в корень папки с пересчётом всех ссылок/связей, создание `--subdirs`, предвалидация в памяти.
   - *Acceptance:* 100% branch coverage; идемпотентный отказ `folderize.already_folderized`; откат без следов при конфликте или ошибке схемы; работа и на `.md`, и на `.json`-записях.
3. **Фаза 3 — CLI `todoc folderize` (`--preview` / `--apply`) и интеграция со скилами жизненного цикла:**
   - Подключение команды в `src/todoc/cli.py`, поддержка `revert` по `change_id` (схлопывание папки обратно в одиночный файл, если в ней ещё нет дочерних файлов).
   - Обновление скила `todoc-plan`: при создании плана по крупной идее агент может развернуть идею через `todoc folderize --subdirs plan` и складывать планы и задачи прямо внутрь домена идеи.

## Открытые вопросы

- **Имя корневого файла внутри созданной папки:** всегда сохранять `<stem>.<ext>` (`ideas/todocignore/todocignore.md` — лучший вариант для сохранности wikilinks `[[todocignore]]` и уникальности имён во всём датасете) или дать опциональный флаг `--index-name index.md` для тех, кто предпочитает `index.md`? Рекомендация по умолчанию — строго `<stem>.<ext>`, так как десяток файлов `index.md` в разных папках создаст массовую неоднозначность wikilinks `[[index]]`.
- **Обратная операция (`todoc unfolderize` / `flatten`):** нужна ли отдельная команда схлопывания пустой папки-домена обратно в одиночный файл (если дочерние планы/задачи были удалены или перенесены), или на старте достаточно `todoc revert`?
- **Перенос существующих связанных артефактов при `--adopt-children`:** стоит ли во 2-й итерации добавить флаг `--with-related`, который при `folderize` идеи сразу предлагает перенести внутрь `ideas/<idea>/plan/` уже существующие планы со связью `derived_from` на эту идею?

## Связанные документы

- [Идея: `.config.json` — самоописание папок](folder-config.md)
- [Идея: `todoc docs move` — транзакционный перенос документа с автоправкой ссылок и связей](docs-move.md)
- [Идея: агентский стейт — `state.json` и скоуп текущего проекта](agent-state.md)
- [Идея: хранилище-движок скилов на `todoc` (паттерн «скил = папка»)](skills-engine.md)
- [Конституция `todoc` (прогрессивное раскрытие и правила типов)](../plan/constitution.md)

## Связь с выпуском единого CLI

Выборки сохраняют пути и identity, деревья показывают родителей. Folderize и перенаправление существующих объектов остаются открытыми.
[Сводка выпуска единого CLI](../notes/unified-cli-release.md).
