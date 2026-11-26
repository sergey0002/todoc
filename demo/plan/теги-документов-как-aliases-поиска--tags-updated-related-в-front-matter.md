---
id: doc:plan-doc-tags
title: "Теги документов как aliases поиска (tags/updated/related в front matter)"
doc_type: plan
lang: ru
status: active
tags: [tags, front-matter, search, metadata, obsidian]
updated: 2026-11-25
related: ["[[folder-config]]", "[[agent-state]]"]
created: 2026-11-26
---

# Теги документов как aliases поиска — план реализации

> **Исполнителю (агенту):** план самодостаточен — читай его, а не историю сессии.
> Работай по задачам сверху вниз; шаги отмечаются чекбоксами (`- [ ]`) в том же
> коммите, который делает шаг. Начинай всегда с первого неотмеченного.

**Цель:** каждый md-документ демо несёт **полный набор метаданных** (created/updated,
tags, related-wikilinks) во front matter; даты поддерживает механика движка (`docs new`
ставит, `docs edit` бампит), теги участвуют в `docs search` с весами как aliases у
папок, `related` — нативные Obsidian-ссылки (граф/бэклинки), явный фильтр `--tag`.
**Спека:** `demo/ideas/folder-config.md` (веса Phase A: alias exact 1.0 / пословное
0.3; title = основной поисковый текст); решение сессии 25.11.2026: носитель —
существующий front matter, НЕ второй HTML-comment блок.
**Стек:** Python 3.11, pytest; без новых зависимостей.

**Почему front matter, а не `<!-- meta ... -->`** (решение, не открытое): статус уже
хранится во front matter — второй блок создал бы два источника истины для одного
поля; Obsidian читает YAML front matter как properties (теги видны в UI, поиске и
`tag:#tag`), HTML-комментарии не парсит вообще; движок уже разбирает front matter.
Содержание повторяет kandev-схему: `type` → уже есть `doc_type`, `status` → уже
есть, новыми будут `tags`, `created`, `updated`, `related`.

## Полный набор полей front matter (Obsidian properties)

| Поле | Кто ставит | Правило |
|---|---|---|
| `id`, `title`, `doc_type`, `lang`, `status`, `source`/`copied` | движок (`docs new`) / миграция | уже есть |
| `created` | движок (`docs new`); миграция — дата первого коммита файла (`git log --diff-filter=A --format=%as`) | `YYYY-MM-DD` |
| `updated` | движок: `docs new` = created; **`docs edit --apply` бампит автоматически** (в той же атомарной записи, виден в ответе `updated_bumped`); миграция — последний содержательный коммит | `YYYY-MM-DD` |
| `tags` | агент при создании / миграция | 2–8 тегов, kebab, словарь в Задаче 4 |
| `related` | агент при создании / миграция | список **wikilinks**: `["[[folder-config]]"]` — Obsidian парсит их как ссылки: граф, бэклинки, Dataview; движок v1 валидирует форму, v2 резолвер извлечёт имя из скобок |

Даты руками не пишутся: движок — единственный писатель `created`/`updated`
(промпты CRUD это прямо запрещают) — это делает даты достоверными без опоры
на дисциплину агента.

## 1. Критерии успеха

1. `todoc docs search --root demo --query "tags"` возвращает этот план выше
   нетегированных документов (тег-буст работает); `--tag tags` фильтрует точно.
2. Все md-файлы демо (сейчас 188, аудит 2026-11-26) имеют полный набор: `created`, `updated`, `tags` (2–8),
   `related` — где есть связи; `docs edit --apply` бампит `updated` автоматически.
3. Папка `demo/` открывается в Obsidian как vault: properties видны, `related`
   дают связи в графе, теги — в tag pane; `.obsidian/` вне Git.
4. `todoc validate --root demo --all` — 0 диагностик; битые значения
   (`tags: ["С ЛЮБЫМ!!"]`, `updated: 25.11.2026`, `created: 25.11.2026`) дают
   `markdown.tags_invalid` / `markdown.updated_invalid` / `markdown.created_invalid`;
   `related: ["файл.md"]` без скобок → `markdown.related_invalid` (форма wikilink).
5. Документ **без** этих полей валиден (поля опциональны — конвенция
   folder-config: aliases папок опциональны, теги наследуют её).
6. pytest зелёный (сейчас 1117 + ~15–20 новых), покрытие нового кода 100%;
   метрики README — от замера (урок BUG-003).

## 2. Вне скоупа

- `related` → рёбра графа (авторазрешение в `references`) — v2 за gate, здесь только
  метаданные; риск висячих целей не куплен.
- Теги у JSON-записей (у task уже есть `labels`) и CSV — не трогаем.
- Стемминг/BM25 для тегов — фаза 3b folder-config, отдельный цикл.
- Словарь-реестр тегов (центральный файл всех тегов) — не делаем; словарь = правила
  именования + проверка валидатором.

## 3. Глобальные ограничения

- Носитель — только front matter (Obsidian properties): `created: YYYY-MM-DD`,
  `updated: YYYY-MM-DD`, `tags: [kebab-tag, ...]`,
  `related: ["[[имя-файла]]", ...]` (wikilinks без .md — Obsidian резолвит по имени).
  Всё опционально; absence ≠ ошибка.
- Даты — зона движка: `docs new` ставит `created`+`updated`, `docs edit --apply`
  бампит `updated`; промпты запрещают ручное редактирование дат.
- Формат тега: `^[a-z0-9]+(-[a-z0-9]+)*$`, длина 2–32, латиница/цифры (поиск лексический,
  кириллические теги допустимы — паттерн расширить на `\u0400-\u04ff` — выбрано:
  разрешить кириллицу сразу, словарь демо русскоязычный).
- Веса поиска — согласованы с folder-config. Текущий score (замер 2026-11-26,
  search.py, score-ветка search_documents ~:255): `title_hits×10 + len(matched) +
  cfg-буст (+2 за конфиг-предков)`. Тег-веса добавляются аддитивно поверх:
  `+ tag_exact×8 + tag_partial×3`; документы без тегов — score прежний (включая
  cfg-буст).
- Миграция демо — скриптом-батчами по папкам, validate после каждого батча;
  скрипт одноразовый, в коммит идут только md-файлы.
- Счётчики документов не меняются от миграции (теги не создают документы); свой
  md-документ план уже добавил (в составе 104).

## 4. Архитектура и файловая карта

- **Данные**: front matter каждого md — полный набор опциональных полей
  (created/updated/tags/related); значения валидирует validator рядом с required_sections.
- **Даты**: движок — единственный писатель. Якорь-замер: `docs new` сегодня
  НЕ пишет front matter вовсе (шаблоны без fm, smoke 2026-11-26 — документ
  начинается с `# {title}`); значить движок строит fm-блок сам в
  `create_document_plan` (write.py): `id/doc_type/lang/title/created/updated`
  (lang — `ru` по умолчанию, в dataset.json поля нет). `docs edit --apply`
  бампит `updated` параметром `bump_updated` в `apply_edit_ops` — одна атомарная
  запись, `new_hash` финальный, ответ содержит `updated_bumped`; preview файл
  не меняет.
- **Obsidian**: `related` = wikilinks — граф, бэклинки и properties работают
  нативно; `.obsidian/` уходит в `.gitignore`; vault-чек — шаг Задачи 4.
- **Поиск**: score-ветка `search_documents` в `src/todoc/application/search.py`
  дополняется тег-слагаемыми (exact ×8 / partial ×3 поверх базового score);
  front matter уже разобран одним проходом — `_document_text` парсит файл, doc
  (`MarkdownDoc.front_matter`, markdown.py:78/260) несёт теги: второй парсинг
  запрещён, экстракция уже общая.
- **CLI**: `docs search --tag <tag>` — пост-фильтр выдачи (точное совпадение тега);
  `docs read` в output добавляет `tags`/`updated`/`related` из front matter.
- **Миграция**: одноразовый скрипт (stdin/stdout, не в репо): git log для дат,
  правила тегов ниже.

Файлы:
- Modify: `src/todoc/application/validator.py` (4 кода, рядом с `_check_structure`
  ~:221), `src/todoc/application/search.py` (тег-слагаемые в score-ветке),
  `src/todoc/cli.py` (`--tag` у docs search, поля в docs read, fm в docs new),
  `src/todoc/application/write.py` (fm-сборка в `create_document_plan`,
  `bump_updated` в `apply_edit_ops`)
- Modify: все md демо (~188) — полный набор полей
- Modify: `.gitignore` (`.obsidian/` — замер: отсутствует), промпты CRUD
  doc_types (`prompts/create.md`, `prompts/edit.md` — 22 дира)
- Create: `tests/unit/test_meta_tags.py` (валидатор + поиск + даты),
  `tests/cli/test_meta_tags_cli.py` (CLI-фильтр --tag и поля read — house-конвенция)

## 5. Задачи

### Задача 1: валидация tags/updated/related

**Файлы:**
- Modify: `src/todoc/application/validator.py`
- Test: `tests/unit/test_meta_tags.py`

**Интерфейсы:**
- Consumes: парсер front matter (`MarkdownDoc.front_matter` — один проход,
  adapters/formats/markdown.py:78/260), `_check_structure` в validator.py
  (~:221, required_sections) — рядом добавляется проверка полей.
- Produces: коды `markdown.tags_invalid` (не список / не строка-тег / >8 шт / длина),
  `markdown.updated_invalid` и `markdown.created_invalid` (не YYYY-MM-DD),
  `markdown.related_invalid` (не список строк `[[имя]]` — wikilink-форма).
  Все — только при наличии поля; пустой список допустим.

- [x] **Шаг 1: падающий тест** — fixture-датасет: `tags: ["OK-tag", "ПЛОХОЙ!!"]` →
  `markdown.tags_invalid`; `updated: "25.11.2026"` → `markdown.updated_invalid`;
  `created: "25.11.2026"` → `markdown.created_invalid`;
  `related: ["[[ok]]"]` → формат ок (существование цели v1 не проверяется);
  `related: ["ok.md"]` → `markdown.related_invalid`; нет полей → 0 диагностик.

- [x] **Шаг 2: убедиться, что тест падает**

Run: `python -m pytest tests/unit/test_meta_tags.py -v`
Expected: FAIL — кодов нет

- [x] **Шаг 3: реализовать четыре проверки** в validator.py (паттерны из Produces выше)

- [x] **Шаг 4: прогнать валидатор на демо**

Run: `todoc validate --root demo --all`
Expected: 0 диагностик — в демо уже есть md с полями (замер 2026-11-26: 5 с
`tags` — guide markdown-knowledge-base и планы folder-config/skills-vault/
softdoc/doc-tags, все ≤8 тегов; 5+ с `related`-wikilinks), формы валидны,
остальные поля отсутствуют

- [x] **Шаг 5: коммит**

```bash
git add src/todoc/application/validator.py tests/unit/test_meta_tags.py
git commit -m "feat(tags): валидация tags/updated/related во front matter (markdown.*_invalid)"
```

### Задача 2: теги в поиске с весами + `--tag`

**Файлы:**
- Modify: `src/todoc/application/search.py`, `src/todoc/cli.py`
- Test: `tests/unit/test_meta_tags.py` (второй класс тестов),
  `tests/cli/test_meta_tags_cli.py` (--tag и read-поля — house-конвенция CLI)

**Интерфейсы:**
- Consumes: `_document_text` (возвращает и front_matter — один парсинг), `_terms`,
  score-ветка search_documents (title×10 + len(matched) + cfg-буст); `_emit_ok` cli.py.
- Produces: score с тегами = текущий базовый `title_hits×10 + len(matched) +
  cfg-буст` + `tag_exact×8 + tag_partial×3`; `tag_exact` — токен запроса == тег;
  `tag_partial` — токен совпадает пословно внутри тега (тег из слов); документы
  без тегов — score прежний (включая cfg-буст); CLI: `docs search --tag <tag>` →
  post-фильтр по точному тегу; read-вывод дополняется `tags`/`updated`/`related`
  из `MarkdownDoc.front_matter`.

- [x] **Шаг 1: падающие тесты** — doc A с тегом `search`, doc B без: запрос «search»
  → A выше B; `--tag search` → только A; score A строго больше score B.

- [x] **Шаг 2: убедиться, что тесты падают**

Run: `python -m pytest tests/unit/test_meta_tags.py -v -k search`
Expected: FAIL — теги не матчаются

- [x] **Шаг 3: реализовать** — search.py: теги извлекаются из front matter файла
  (второй раз парсить нельзя → вынести extraction в общую функцию markdown-модуля,
  реюз в validator и search); кли: опция `--tag` у `docs search`, поля в выводе
  `docs read`.

- [x] **Шаг 4: полный прогон поиска**

Run: `python -m pytest tests/unit tests/cli -v`
Expected: PASS — все существующие поисковые тесты не сломаны (score без тегов прежний)

- [x] **Шаг 5: коммит**

```bash
git add src/todoc/application/search.py src/todoc/cli.py tests/unit/test_meta_tags.py \
      tests/cli/test_meta_tags_cli.py
git commit -m "feat(tags): теги в лексическом поиске (exact x8, partial x3) + docs search --tag"
```

### Задача 3: даты в движке + промпты (created/updated без ручной дисциплины)

**Файлы:**
- Modify: `src/todoc/application/write.py` (`create_document_plan` — fm-сборка;
  `apply_edit_ops` — параметр `bump_updated`)
- Modify: `src/todoc/cli.py` (`docs new` — значения дат; `docs edit --apply` — бамп)
- Modify: `.gitignore` (добавить `.obsidian/`)
- Modify: `demo/.todoc/doc_types/*/prompts/create.md`, `edit.md` (22 дира промптов)
- Test: `tests/unit/test_meta_tags.py`, `tests/cli/test_meta_tags_cli.py`

**Интерфейсы:**
- Consumes: `create_document_plan` (write.py: шаблоны БЕЗ fm — движок строит
  fm-блок сам: `id: doc:<path>`, `title`, `doc_type`, `lang: ru`, `created`,
  `updated`; render_template рендерит тело как сейчас); `apply_edit_ops`
  (write.py:164+ — BUG-004 ops).
- Produces: `docs new` пишет fm-блок с `created: <UTC-дата>` = `updated: <UTC-дата>`;
  `docs edit --apply` бампит `updated: <сегодня>` в той же записи
  (`apply_edit_ops(..., bump_updated=True)` — модификация строк до записи,
  `new_hash` финальный), ответ включает `updated_bumped: true`; preview файл
  не меняет и updated не трогает; промпты: create — «created/updated ставит
  движок — руками не заполнять», edit — «updated бампит движок; связал документ —
  добавь/обнови related-wikilink».

- [x] **Шаг 1: падающие тесты** — `docs new` → created==updated==сегодня в файле;
  `docs edit --apply` (правка одной строки) → `updated` = сегодня, `created` не
  изменился, ответ содержит `updated_bumped`; `--preview` — файл байт-в-байт прежний.

- [x] **Шаг 2: убедиться, что тесты падают**

Run: `python -m pytest tests/unit/test_meta_tags.py -v -k dates`
Expected: FAIL — полей created/updated нет, бампа нет

- [x] **Шаг 3: реализовать** — cli.py (docs new: два поля; docs edit: бамп в
  apply-ветке), .gitignore: `.obsidian/`, промпты: строки про даты в каждом
  create.md/edit.md.

- [x] **Шаг 4: полный прогон**

Run: `python -m pytest tests/unit tests/cli -v`
Expected: PASS — включая существующие тесты docs new/edit (обновить фикстуры с
точными сравнениями front matter на два новых поля)

- [x] **Шаг 5: коммит**

```bash
git add src/todoc/application/write.py src/todoc/cli.py .gitignore demo/.todoc \
      tests/unit/test_meta_tags.py tests/cli/test_meta_tags_cli.py
git commit -m "feat(meta): created/updated в docs new, бамп updated в docs edit + промпты CRUD"
```

### Задача 4: миграция демо — полный набор полей во все md

**Файлы:**
- Modify: все md демо (~188, список: `git ls-files 'demo/**/*.md'`; включая `bugs/`,
  `demo/HOME.md` и `demo/README.md`)

**Интерфейсы:**
- Consumes: правила тегов (ниже), `git log --diff-filter=A --format=%as -- <file>`
  (created), `git log -1 --format=%as -- <file>` (updated — последний содержательный
  коммит, служебные правки счётчиков отсечь), правила related-пар.
- Produces: у каждого md `created` + `updated` (YYYY-MM-DD), `tags` (2–8),
  `related` wikilinks — только явные пары (планы → спека-идея, after-планы →
  implementation-plan, идеи → их планы после переходов).

**Правила тегов (словарь миграции):**
1. Обязательный тег папки: plan, ideas, architecture, glossary, guides, research,
   references, notes, inbox, skill, competitors, docs-mirror (для copied:true).
2. Тег doc_type: idea, plan, guide, note, adr, audit, research, reference…
3. 1–3 тематических тега из заголовка (дистинктивные слова, kebab): «Идея: .config.json
   — самоописание папок» → `[ideas, idea, folder-config, self-describing]` —
   исполнитель проверяет читаемость каждого тега.
4. Запрещено: дубли папки/doc_type-тега, теги-общности («doc», «file», «todo» вне
   задач).

**Правила related (пары, wikilinks без .md):**
- план → его спека-идея: `["[[agent-state]]"]`;
- after-план → implementation-plan: `["[[implementation-plan]]"]`;
- copied-доки (docs-mirror) → не заполняются (связь видна в `source`);
- связей нет → поле опускается.

- [x] **Шаг 1: батч plan/ + ideas/** (related заполняется здесь)
  → `todoc validate --root demo --all` = 0 → коммит

- [x] **Шаг 2: батчи architecture/, glossary/, guides/, research/** → validate = 0 → коммит

- [x] **Шаг 3: батчи references/, notes/, inbox/, skill/, competitors/, прочие md** →
  validate = 0 → коммит

- [x] **Шаг 4: сквозная проверка**

Run: `todoc docs search --root demo --query "state" --tag tags` и
`todoc docs search --root demo --query "aliases"`
Expected: тег-буст виден в выдаче; 0 диагностик

- [x] **Шаг 5: Obsidian-чек** — агент проверяет структурно (sandbox: fm каждого
  md парсится движком, related-формы wikilink, `.obsidian/` вне `git status`);
  визуальную часть (properties/граф/tag pane) выполняет пользователь вне сессии —
  Obsidian в sandbox недоступен.

- [x] **Шаг 6: коммиты по батчам** (см. шаги 1–3; последний: `demo(tags): миграция демо — полный набор полей во всех md`)

### Задача 5: синхронизация документации и счётчиков

**Файлы:**
- Modify: `demo/ideas/folder-config.md` (кросс-ссылка: теги документов — doc-уровень
  той же весовой модели), `demo/HOME.md` (строка про теги), `demo/README.md`
  (состав демо; строка types list уже от факта — BUG-003 исправлен PR #56),
  `README.md` (метрики: тесты/покрытие от замера), `demo/references/state/01-overview.md`,
  `demo/references/state/13-demo-dataset.md` (состав, пример поиска),
  `bench/results/benchmark.md` (если метрики упомянуты) — все счётчики от факта
  (замер 2026-11-26: 376 документов / 188 md / 1 csv / 187 json / 15 opaque;
  миграция состав не меняет)

**Интерфейсы:**
- Consumes: фактические числа после миграции.
- Produces: согласованные счётчики; упоминание тегов в гайдах.

- [x] **Шаг 1: обновить 5 файлов счётчиков/доков**
- [x] **Шаг 2: полный прогон**

Run: `todoc validate --root demo --all && coverage run -m pytest && coverage report`
Expected: 0 диагностик, все зелёные, 100%, 0 пропусков

- [x] **Шаг 3: коммит**

```bash
git add README.md demo/references/state demo/ideas/folder-config.md demo/HOME.md \
      demo/README.md bench/results/benchmark.md
git commit -m "docs: счётчики и гайды после введения тегов документов"
```

## 6. Definition of Done

- [x] Задачи 1–5 выполнены; каждая — отдельные коммиты (миграция — по батчам).
- [x] Тег-буст в поиске подтверждён тестами и сквозной проверкой; `--tag` работает.
- [x] Все md демо с created/updated/tags; явные пары — с related-wikilinks; validate 0.
- [x] Даты ведутся движком: `docs new` ставит, `docs edit --apply` бампит (тест),
  промпты запрещают ручное.
- [ ] Obsidian-чек пройден: properties, граф по related, tag pane; `.obsidian/` вне Git.
- [x] pytest 1130 зелёный; новый код — 100% покрытие; метрики README от замера (99% — 5350+1958).
- [x] Счётчики согласованы от факта (`check --root demo`; на 26.11.2026 — 376 документов,
      188 md); folder-config сослался на doc-теги.

## 7. Риски и митигации

| Риск | В×В | Митигация | Владелец |
|---|---|---|---|
| Словарь тегов расползается (синонимы: search/поиск) | В×С | правила именования в Задаче 3; теги = папка+тип+заголовок; синонимы — роль aliases папок, не тегов | агент |
| Миграция 96 файлов одним дифом не ревьюится | С×С | 3 батча-коммита по группам папок; validate после каждого | агент |
| Двойной парсинг front matter (validator+search) рассинхронизируется | Н×В | уже решено: `MarkdownDoc.front_matter` общий (markdown.py:78/260); запрет второго парсинга в поиске — реюз doc из одного прохода | агент |
| Изменение score ломает существующие ожидания поиска | С×Н | тесты «без тегов score прежний»; веса добавляются, не заменяют | агент |
| `related` указывает на переименованные файлы | Н×Н | v1 без проверки существования (заявлено в валидаторе); v2 с резолвером за gate | агент |
| Даты правятся руками в обход движка | С×Н | движок — единственный писатель created/updated; промпты запрещают; валидатор формата ловит битое | агент |
| Wikilinks в related путают будущий резолвер графа | Н×Н | форма `[[имя]]` фиксируется валидатором; v2 извлекает имя из скобок | агент |
| Параллельное исполнение с планами softdoc / скилов-взаимодействия — конфликт в validator.py, cli.py и промптах CRUD | Н×С | задачи независимы по тестам, но три плана правят validator.py: мержить последовательно, pytest после каждого | агент |

## 8. Прогресс и отклонения

- Статус: задачи 1–5 исполнены 2026-11-26 (коммиты З1–З5; статус документа — active,
  снятие по явной фразе пользователя).
- Отклонений нет.
- 2026-11-25 — план дополнен до начала работ (правка содержания): полный набор
  полей — created/updated ставит механика движка (docs new / бамп в docs edit),
  related = wikilinks Obsidian, промпты CRUD о датах, .obsidian/ вне Git,
  Obsidian-чек; задачи перенумерованы (миграция 3→4, синхронизация 4→5).
- 2026-11-25 — финальный аудит перед выполнением: 1) счётчики от факта —
  270 документов / 104 md (было ~97; PR #39, планы softdoc и bug-репорты),
  «pytest 437» → 988; 2) конфликт с будущим валидатором устранён: related этого
  плана и плана softdoc переведены в wikilink-форму (иначе Задача 1 сразу дала
  бы markdown.related_invalid), tags softdoc-плана — 7 ≤ 8; 3) подтверждено
  чтением кода: score title ×10 уже есть (search.py:146-148), .gitignore без
  .obsidian/ (шаг задачи 3 реален), все 8 required_sections плана совместимы
  с будущим fm-правилом plan (проверено списком секций); 4) в Задачу 5 добавлен
  demo/README.md (BUG-003) и риск параллельного мержа трёх планов. Проверено:
  validate — 0 диагностик, plan-документ читается CLI. Готов к выполнению:
  первая задача — Задача 1, шаг 1.

- 2026-11-26 — финальный аудит перед реализацией (якоря сверены с кодом;
  правки уточняющие, шаги не переписывались): (1) числа от замера — md 104→188,
  документов 270→376, json 165→187 (+15 opaque), тестов 988→1117; (2) З1: ветка
  required_sections — `_check_structure` validator.py ~:221 (было ~:197); в демо
  уже 5 md с tags и 5+ с related (замер), все ≤8 тегов, формы валидны — ожидание
  шага 4 переписано; ссылка на коммит `fad36c5` удалена (несуществующий);
  (3) З2: формула Produces уточнена — текущий score = title×10 + len(matched) +
  cfg-буст folder-config (+2), тег-веса аддитивны поверх; CLI-тесты вынесены в
  tests/cli/test_meta_tags_cli.py (house-конвенция); экстракция fm уже общая
  (MarkdownDoc.front_matter) — «вынести extraction» не требуется, риск двойного
  парсинга закрыт констатацией; (4) З3 — главный якорь: `docs new` сегодня НЕ
  пишет fm вовсе (шаблоны без fm, smoke 26.11) → движок строит fm-блок в
  `create_document_plan` (id/doc_type/lang/created/updated; lang: ru — в
  dataset.json поля нет); бамп `updated` — параметр `bump_updated` в
  `apply_edit_ops` (одна запись, new_hash финальный); файлы З3 дополнены
  write.py; (5) З4: «корневые HOME/README» = demo/HOME.md, demo/README.md;
  Obsidian-чек разделён: структурная часть — агент, визуальная — пользователь
  (Obsidian в sandbox недоступен); (6) З5: пути docs/state/* →
  demo/references/state/*, 15-benchmark → bench/results/benchmark.md, строка
  «15 dir_types» уже исправлена (BUG-003 закрыт PR #56) — остаётся состав демо;
  git add-строки приведены к фактическим путям; (7) промпты: 22 дира
  prompts/create.md+edit.md подтверждены; .obsidian/ в .gitignore отсутствует —
  шаг реален. Отклонений семантики нет: 5 задач, DoD полон.
<!-- Формат строки отклонения: `YYYY-MM-DD — задача N, шаг M: что не так → что
     выбрано вместо и почему`. Шаги задним числом не переписывать. -->
- 2026-11-26 — исполнение, отклонения и уточнения:
  1) З1: вызов meta-валидации размещён строго в markdown-ветке validator'а — JSON-записи
  (records) не проверяются на tags/created/updated/related (уточнение скоупа «front matter
  markdown»); парсер держит значения fm строками — кейс `tags: [42]` заменён
  на `["UPPER-Case"]` (заглавные вне kebab-правила).
  2) З3: `apply_edit_ops` возвращает `(new_hash, updated_bumped)` — сигнатура изменена,
  существующие вызов-тесты обновлены; fm у `docs new` строится движком
  (id/title/doc_type/lang/created/updated), tags/related остаются агенту и миграции.
  3) З4: первый проход миграции пропустил 10 файлов с кириллическими именами
  (`git ls-files` экранирует не-ASCII в кавычки — фильтр `endswith(".md")` их отбрасывал);
  обнаружено сверкой `grep -L "tags: ["`, добито вторым идемпотентным проходом —
  все 188 md. Тег `bugs` для bugs/ вне списка правила 1 (сохранён для согласованности).
  Все 6 after-планов — copied:true: related по правилу не заполняется, добавлен
  `docs-mirror`. Идеи получили related → их планы (двусторонние пары с планами);
  устаревший related `[[plan-folder-config]]` идеи folder-config заменён на реальные
  basename'ы. skills-дерево (SKILL.md + внутренние md) мигрировано как «прочие md».
  4) З5: bench/results/benchmark.md не менялся — метрик состава не содержит
  (условие «если упомянуты»); в прозе — 170 записей (файлы records/), поле `records`
  вывода `index rebuild` — 172 (пример обновлён от фактического вывода команды:
  67 папок / 376 документов / 152 отношения).
  5) DoD: структурная часть Obsidian-чека выполнена агентом (fm парсится движком,
  related-формы валидны, `.obsidian/` вне git status); визуальная часть (properties,
  граф по related, tag pane) — за пользователем вне сессии.
