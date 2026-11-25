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

**Цель:** каждый md-документ демо несёт `tags`/`updated`/`related` во front matter;
теги участвуют в `docs search` с весами как aliases у папок; явный фильтр `--tag`.
**Спека:** `demo/ideas/folder-config.md` (веса Phase A: alias exact 1.0 / пословное
0.3; title = основной поисковый текст); решение сессии 25.11.2026: носитель —
существующий front matter, НЕ второй HTML-comment блок.
**Стек:** Python 3.11, pytest; без новых зависимостей.

**Почему front matter, а не `<!-- meta ... -->`** (решение, не открытое): статус уже
хранится во front matter — второй блок создал бы два источника истины для одного
поля; Obsidian читает YAML front matter как properties (теги видны в UI, поиске и
`tag:#tag`), HTML-комментарии не парсит вообще; движок уже разбирает front matter.
Содержание повторяет kandev-схему: `type` → уже есть `doc_type`, `status` → уже
есть, новыми будут `tags`, `updated`, `related`.

## 1. Критерии успеха

1. `todoc docs search --root demo --query "tags"` возвращает этот план выше
   нетегированных документов (тег-буст работает); `--tag tags` фильтрует точно.
2. Все ~96 md-файлов демо имеют `tags:` (1–8 тегов) и `updated:`; у связанных
   документов заполнен `related:`.
3. `todoc validate --root demo --all` — 0 диагностик; битые значения
   (`tags: ["С ЛЮБЫМ!!"]`, `updated: 25.11.2026`) дают
   `markdown.tags_invalid` / `markdown.updated_invalid`.
4. Документ **без** этих полей валиден (поля опциональны — конвенция «aliases не
   обязательны», коммит `fad36c5`).
5. pytest зелёный (437 + новые), coverage 100%.

## 2. Вне скоупа

- `related` → рёбра графа (авторазрешение в `references`) — v2 за gate, здесь только
  метаданные; риск висячих целей не куплен.
- Теги у JSON-записей (у task уже есть `labels`) и CSV — не трогаем.
- Стемминг/BM25 для тегов — фаза 3b folder-config, отдельный цикл.
- Словарь-реестр тегов (центральный файл всех тегов) — не делаем; словарь = правила
  именования + проверка валидатором.

## 3. Глобальные ограничения

- Носитель — только front matter: `tags: [kebab-tag, ...]`, `updated: YYYY-MM-DD`,
  `related: [имя-файла.md, ...]`. Всё опционально; absence ≠ ошибка.
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

- **Данные**: front matter каждого md — 3 новых опциональных поля; значения валидирует
  validator рядом с required_sections.
- **Поиск**: `_document_text` в `src/todoc/application/search.py` дополняется
  тег-строкой с весовой структурой: вместо одного обогащённого текста — матчинг по
  полям (title, tags, rest) с весами ×10/×8/×3/×1; суммирование как в folder-config
  Phase A; порядок ties не меняется.
- **CLI**: `docs search --tag <tag>` — пост-фильтр выдачи (точное совпадение тега);
  `docs read` в output добавляет `tags`/`updated`/`related` из front matter.
- **Миграция**: одноразовый скрипт (stdin/stdout, не в репо): git log для дат,
  правила тегов ниже.

Файлы:
- Modify: `src/todoc/application/validator.py` (3 кода), `src/todoc/application/search.py`
  (веса), `src/todoc/cli.py` (`--tag`, read-поля)
- Modify: все md демо (`git ls-files 'demo/**/*.md' | wc -l` — фактическое число,
  ~96) — теги/даты/related
- Create: `tests/unit/test_meta_tags.py` (валидатор + поиск + CLI-фильтр)

## 5. Задачи

### Задача 1: валидация tags/updated/related

**Файлы:**
- Modify: `src/todoc/application/validator.py`
- Test: `tests/unit/test_meta_tags.py`

**Интерфейсы:**
- Consumes: парсер front matter (adapters/formats/markdown), ветка required_sections
  (~строка 197 validator.py) — рядом добавляется проверка полей.
- Produces: коды `markdown.tags_invalid` (не список / не строка-тег / >8 шт / длина),
  `markdown.updated_invalid` (не YYYY-MM-DD), `markdown.related_invalid` (не список
  строк *.md). Все три — только при наличии поля; пустой список допустим.

- [ ] **Шаг 1: падающий тест** — fixture-датасет: `tags: ["OK-tag", "ПЛОХОЙ!!"]` →
  `markdown.tags_invalid`; `updated: "25.11.2026"` → `markdown.updated_invalid`;
  `related: ["нет-такого.md"]` → формат ок (существование цели v1 не проверяется);
  нет полей → 0 диагностик.

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `python -m pytest tests/unit/test_meta_tags.py -v`
Expected: FAIL — кодов нет

- [ ] **Шаг 3: реализовать три проверки** в validator.py (паттерны из Produces выше)

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

### Задача 3: миграция демо — теги/даты/related во все md

**Файлы:**
- Modify: все md демо (~96, список: `git ls-files 'demo/**/*.md'`)

**Интерфейсы:**
- Consumes: правила тегов (ниже), `git log --diff-filter=A --format=%as -- <file>`
  для даты создания.
- Produces: у каждого md `tags` (2–5), `updated` (дата последнего содержательного
  коммита файла), `related` — только явные пары (планы → их спека-идея;
  after-планы → implementation-plan).

**Правила тегов (словарь миграции):**
1. Обязательный тег папки: plan, ideas, architecture, glossary, guides, research,
   references, notes, inbox, skill, competitors, docs-mirror (для copied:true).
2. Тег doc_type: idea, plan, guide, note, adr, audit, research, reference…
3. 1–3 тематических тега из заголовка (дистинктивные слова, kebab): «Идея: .config.json
   — самоописание папок» → `[ideas, idea, folder-config, self-describing]` —
   исполнитель проверяет читаемость каждого тега.
4. Запрещено: дубли папки/doc_type-тега, теги-общности («doc», «file», «todo» вне
   задач).

- [ ] **Шаг 1: батч plan/ + ideas/** (самые связанные, related заполняется здесь)
  → `todoc validate --root demo --all` = 0 → коммит

- [ ] **Шаг 2: батчи architecture/, glossary/, guides/, research/** → validate = 0 → коммит

- [ ] **Шаг 3: батчи references/, notes/, inbox/, skill/, competitors/, прочие md** →
  validate = 0 → коммит

- [ ] **Шаг 4: сквозная проверка**

Run: `todoc docs search --root demo --query "state" --tag tags` и
`todoc docs search --root demo --query "aliases"`
Expected: тег-буст виден в выдаче; 0 диагностик

- [ ] **Шаг 5: коммиты по батчам** (см. шаги 1–3; последний: `demo(tags): миграция демо — теги/updated/related во всех md`)

### Задача 4: синхронизация документации и счётчиков

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

- [ ] Задачи 1–4 выполнены; каждая — отдельные коммиты по батчам.
- [ ] Тег-буст в поиске подтверждён тестами и сквозной проверкой; `--tag` работает.
- [ ] Все md демо с `tags`+`updated`; явные пары — с `related`; validate 0.
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

## 8. Прогресс и отклонения

- Статус: не начат (2026-11-25). Первая задача — Задача 1, шаг 1.
- Отклонений нет.

<!-- Формат строки отклонения: `YYYY-MM-DD — задача N, шаг M: что не так → что
     выбрано вместо и почему`. Шаги задним числом не переписывать. -->
