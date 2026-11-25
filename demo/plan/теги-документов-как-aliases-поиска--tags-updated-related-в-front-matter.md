---
id: doc:plan-doc-tags
title: "Теги документов как aliases поиска (tags/updated/related в front matter)"
doc_type: plan
lang: ru
status: active
tags: [tags, front-matter, search, metadata, obsidian]
updated: 2026-11-25
related: [folder-config.md, agent-state.md]
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
2. Все ~97 md-файлов демо имеют полный набор: `created`, `updated`, `tags` (2–8),
   `related` — где есть связи; `docs edit --apply` бампит `updated` автоматически.
3. Папка `demo/` открывается в Obsidian как vault: properties видны, `related`
   дают связи в графе, теги — в tag pane; `.obsidian/` вне Git.
4. `todoc validate --root demo --all` — 0 диагностик; битые значения
   (`tags: ["С ЛЮБЫМ!!"]`, `updated: 25.11.2026`, `created: 25.11.2026`) дают
   `markdown.tags_invalid` / `markdown.updated_invalid` / `markdown.created_invalid`;
   `related: ["файл.md"]` без скобок → `markdown.related_invalid` (форма wikilink).
5. Документ **без** этих полей валиден (поля опциональны — конвенция «aliases не
   обязательны», коммит `fad36c5`).
6. pytest зелёный (437 + новые), coverage 100%.

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
- Веса поиска — согласованы с folder-config: title ×10 (есть), **tag exact ×8**,
  **tag пословное ×3**, headings/body ×1 (базовая длина совпадений — как сейчас).
- Миграция демо — скриптом-батчами по папкам, validate после каждого батча;
  скрипт одноразовый, в коммит идут только md-файлы.
- Счётчики документов не меняются от миграции (теги не создают документы), но сам
  план добавляет 1 md-документ.

## 4. Архитектура и файловая карта

- **Данные**: front matter каждого md — полный набор опциональных полей
  (created/updated/tags/related); значения валидирует validator рядом с required_sections.
- **Даты**: движок — единственный писатель: `docs new` пишет created+updated,
  `docs edit --apply` бампит updated в той же атомарной записи (ответ содержит
  `updated_bumped`); preview файл не меняет.
- **Obsidian**: `related` = wikilinks — граф, бэклинки и properties работают
  нативно; `.obsidian/` уходит в `.gitignore`; vault-чек — шаг Задачи 4.
- **Поиск**: `_document_text` в `src/todoc/application/search.py` дополняется
  тег-строкой с весовой структурой: вместо одного обогащённого текста — матчинг по
  полям (title, tags, rest) с весами ×10/×8/×3/×1; суммирование как в folder-config
  Phase A; порядок ties не меняется.
- **CLI**: `docs search --tag <tag>` — пост-фильтр выдачи (точное совпадение тега);
  `docs read` в output добавляет `tags`/`updated`/`related` из front matter.
- **Миграция**: одноразовый скрипт (stdin/stdout, не в репо): git log для дат,
  правила тегов ниже.

Файлы:
- Modify: `src/todoc/application/validator.py` (4 кода), `src/todoc/application/search.py`
  (веса), `src/todoc/cli.py` (`--tag`, read-поля, created/updated в `docs new`,
  бамп `updated` в `docs edit`)
- Modify: все md демо (~97) — полный набор полей
- Modify: `.gitignore` (`.obsidian/`), промпты CRUD doc_types (`create.md`/`edit.md`)
- Create: `tests/unit/test_meta_tags.py` (валидатор + поиск + CLI-фильтр + даты)

## 5. Задачи

### Задача 1: валидация tags/updated/related

**Файлы:**
- Modify: `src/todoc/application/validator.py`
- Test: `tests/unit/test_meta_tags.py`

**Интерфейсы:**
- Consumes: парсер front matter (adapters/formats/markdown), ветка required_sections
  (~строка 197 validator.py) — рядом добавляется проверка полей.
- Produces: коды `markdown.tags_invalid` (не список / не строка-тег / >8 шт / длина),
  `markdown.updated_invalid` и `markdown.created_invalid` (не YYYY-MM-DD),
  `markdown.related_invalid` (не список строк `[[имя]]` — wikilink-форма).
  Все — только при наличии поля; пустой список допустим.

- [ ] **Шаг 1: падающий тест** — fixture-датасет: `tags: ["OK-tag", "ПЛОХОЙ!!"]` →
  `markdown.tags_invalid`; `updated: "25.11.2026"` → `markdown.updated_invalid`;
  `created: "25.11.2026"` → `markdown.created_invalid`;
  `related: ["[[ok]]"]` → формат ок (существование цели v1 не проверяется);
  `related: ["ok.md"]` → `markdown.related_invalid`; нет полей → 0 диагностик.

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `python -m pytest tests/unit/test_meta_tags.py -v`
Expected: FAIL — кодов нет

- [ ] **Шаг 3: реализовать четыре проверки** в validator.py (паттерны из Produces выше)

- [ ] **Шаг 4: прогнать валидатор на демо**

Run: `todoc validate --root demo --all`
Expected: 0 диагностик (полей ещё нет в демо, кроме front matter этого плана)

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/validator.py tests/unit/test_meta_tags.py
git commit -m "feat(tags): валидация tags/updated/related во front matter (markdown.*_invalid)"
```

### Задача 2: теги в поиске с весами + `--tag`

**Файлы:**
- Modify: `src/todoc/application/search.py`, `src/todoc/cli.py`
- Test: `tests/unit/test_meta_tags.py` (второй класс тестов)

**Интерфейсы:**
- Consumes: `_document_text`, `_terms`, подсчёт score в search.py; существующий
  API `_emit_ok` в cli.py.
- Produces: score документа с тегами = `title_hits×10 + tag_exact×8 + tag_partial×3
  + len(matched_rest)`; `tag_exact` — токен запроса == тег; `tag_partial` — токен
  совпадает пословно внутри тега (тег из слов); документы без тегов — прежний score;
  CLI: `docs search ... --tag <tag>` → post-фильтр по точному тегу; read-вывод
  дополняется `tags`/`updated`/`related`.

- [ ] **Шаг 1: падающие тесты** — doc A с тегом `search`, doc B без: запрос «search»
  → A выше B; `--tag search` → только A; score A строго больше score B.

- [ ] **Шаг 2: убедиться, что тесты падают**

Run: `python -m pytest tests/unit/test_meta_tags.py -v -k search`
Expected: FAIL — теги не матчаются

- [ ] **Шаг 3: реализовать** — search.py: теги извлекаются из front matter файла
  (второй раз парсить нельзя → вынести extraction в общую функцию markdown-модуля,
  реюз в validator и search); кли: опция `--tag` у `docs search`, поля в выводе
  `docs read`.

- [ ] **Шаг 4: полный прогон поиска**

Run: `python -m pytest tests/unit tests/cli -v`
Expected: PASS — все существующие поисковые тесты не сломаны (score без тегов прежний)

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/search.py src/todoc/cli.py tests/unit/test_meta_tags.py
git commit -m "feat(tags): теги в лексическом поиске (exact x8, partial x3) + docs search --tag"
```

### Задача 3: даты в движке + промпты (created/updated без ручной дисциплины)

**Файлы:**
- Modify: `src/todoc/cli.py` (`docs new`, `docs edit`)
- Modify: `.gitignore` (добавить `.obsidian/`)
- Modify: `demo/.todoc/doc_types/*/prompts/create.md`, `edit.md` (все doc_types с промптами)
- Test: `tests/unit/test_meta_tags.py`

**Интерфейсы:**
- Consumes: шаблонизатор `docs new` (существующий front matter-вывод, переменные
  {title}/{slug}/{date}); `apply_edit_ops` (writer `docs edit`).
- Produces: `docs new` добавляет во front matter `created: <UTC-дата>` и
  `updated: <UTC-дата>`; `docs edit --apply` при успешной замене контента бампит
  `updated: <сегодня>` в той же атомарной записи, ответ включает `updated_bumped: true`;
  preview файл не меняет и updated не трогает; промпты: create — «created/updated
  ставит движок — руками не заполнять», edit — «updated бампит движок; связал
  документ — добавь/обнови related-wikilink».

- [ ] **Шаг 1: падающие тесты** — `docs new` → created==updated==сегодня в файле;
  `docs edit --apply` (правка одной строки) → `updated` = сегодня, `created` не
  изменился, ответ содержит `updated_bumped`; `--preview` — файл байт-в-байт прежний.

- [ ] **Шаг 2: убедиться, что тесты падают**

Run: `python -m pytest tests/unit/test_meta_tags.py -v -k dates`
Expected: FAIL — полей created/updated нет, бампа нет

- [ ] **Шаг 3: реализовать** — cli.py (docs new: два поля; docs edit: бамп в
  apply-ветке), .gitignore: `.obsidian/`, промпты: строки про даты в каждом
  create.md/edit.md.

- [ ] **Шаг 4: полный прогон**

Run: `python -m pytest tests/unit tests/cli -v`
Expected: PASS — включая существующие тесты docs new/edit (обновить фикстуры с
точными сравнениями front matter на два новых поля)

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/cli.py .gitignore demo/.todoc tests/unit/test_meta_tags.py
git commit -m "feat(meta): created/updated в docs new, бамп updated в docs edit + промпты CRUD"
```

### Задача 4: миграция демо — полный набор полей во все md

**Файлы:**
- Modify: все md демо (~97, список: `git ls-files 'demo/**/*.md'`)

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

- [ ] **Шаг 1: батч plan/ + ideas/** (related заполняется здесь)
  → `todoc validate --root demo --all` = 0 → коммит

- [ ] **Шаг 2: батчи architecture/, glossary/, guides/, research/** → validate = 0 → коммит

- [ ] **Шаг 3: батчи references/, notes/, inbox/, skill/, competitors/, прочие md** →
  validate = 0 → коммит

- [ ] **Шаг 4: сквозная проверка**

Run: `todoc docs search --root demo --query "state" --tag tags` и
`todoc docs search --root demo --query "aliases"`
Expected: тег-буст виден в выдаче; 0 диагностик

- [ ] **Шаг 5: Obsidian-чек (ручной)** — открыть `demo/` как vault: properties
  показывают created/updated/status/tags; related дают связи в графе и бэклинках;
  теги — в tag pane; `.obsidian/` не в `git status`.

- [ ] **Шаг 6: коммиты по батчам** (см. шаги 1–3; последний: `demo(tags): миграция демо — полный набор полей во всех md`)

### Задача 5: синхронизация документации и счётчиков

**Файлы:**
- Modify: `demo/ideas/folder-config.md` (кросс-ссылка: теги документов — doc-уровень
  той же весовой модели), `demo/HOME.md` (строка про теги), `README.md` и
  `docs/state/01-overview.md` (256→257 документов, 96→97 md),
  `docs/state/13-demo-dataset.md` (состав, пример поиска), `docs/state/15-benchmark.md`

**Интерфейсы:**
- Consumes: фактические числа после миграции.
- Produces: согласованные счётчики; упоминание тегов в гайдах.

- [ ] **Шаг 1: обновить 5 файлов счётчиков/доков**
- [ ] **Шаг 2: полный прогон**

Run: `todoc validate --root demo --all && coverage run -m pytest && coverage report`
Expected: 0 диагностик, все зелёные, 100%, 0 пропусков

- [ ] **Шаг 3: коммит**

```bash
git add README.md docs/state demo/ideas/folder-config.md demo/HOME.md
git commit -m "docs: счётчики и гайды после введения тегов документов"
```

## 6. Definition of Done

- [ ] Задачи 1–5 выполнены; каждая — отдельные коммиты (миграция — по батчам).
- [ ] Тег-буст в поиске подтверждён тестами и сквозной проверкой; `--tag` работает.
- [ ] Все md демо с created/updated/tags; явные пары — с related-wikilinks; validate 0.
- [ ] Даты ведутся движком: `docs new` ставит, `docs edit --apply` бампит (тест),
  промпты запрещают ручное.
- [ ] Obsidian-чек пройден: properties, граф по related, tag pane; `.obsidian/` вне Git.
- [ ] pytest 437+N зелёный; coverage 100%, 0 пропусков.
- [ ] Счётчики согласованы (257 документов, 97 md); folder-config сослался на doc-теги.

## 7. Риски и митигации

| Риск | В×В | Митигация | Владелец |
|---|---|---|---|
| Словарь тегов расползается (синонимы: search/поиск) | В×С | правила именования в Задаче 3; теги = папка+тип+заголовок; синонимы — роль aliases папок, не тегов | агент |
| Миграция 96 файлов одним дифом не ревьюится | С×С | 3 батча-коммита по группам папок; validate после каждого | агент |
| Двойной парсинг front matter (validator+search) рассинхронизируется | Н×В | extraction в одну функцию markdown-модуля, реюз обеими сторонами (Шаг 3 задачи 2) | агент |
| Изменение score ломает существующие ожидания поиска | С×Н | тесты «без тегов score прежний»; веса добавляются, не заменяют | агент |
| `related` указывает на переименованные файлы | Н×Н | v1 без проверки существования (заявлено в валидаторе); v2 с резолвером за gate | агент |
| Даты правятся руками в обход движка | С×Н | движок — единственный писатель created/updated; промпты запрещают; валидатор формата ловит битое | агент |
| Wikilinks в related путают будущий резолвер графа | Н×Н | форма `[[имя]]` фиксируется валидатором; v2 извлекает имя из скобок | агент |

## 8. Прогресс и отклонения

- Статус: не начат (2026-11-25). Первая задача — Задача 1, шаг 1.
- Отклонений нет.
- 2026-11-25 — план дополнен до начала работ (правка содержания): полный набор
  полей — created/updated ставит механика движка (docs new / бамп в docs edit),
  related = wikilinks Obsidian, промпты CRUD о датах, .obsidian/ вне Git,
  Obsidian-чек; задачи перенумерованы (миграция 3→4, синхронизация 4→5).

<!-- Формат строки отклонения: `YYYY-MM-DD — задача N, шаг M: что не так → что
     выбрано вместо и почему`. Шаги задним числом не переписывать. -->
