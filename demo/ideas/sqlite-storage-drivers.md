---
id: doc:ideas/sqlite-storage-drivers.md
title: "Идея: переключаемые драйверы хранения кэша поиска и истории (JSON/JSONL vs раздельные базы SQLite + FTS5 BM25 и инкрементальный индекс)"
doc_type: idea
lang: ru
status: captured
created: 2026-11-26
updated: 2026-11-28
tags: [ideas, idea, sqlite, storage, cache, history, bm25, драйверы]
related: ["[[bm25-ranking-python-libs]]", "[[unified-tags-and-tag-graph]]", "[[typed-tree-projection]]", "[[bitemporal-clocks]]", "[[docs-move]]", "[[entity-to-folder]]", "[[todocignore]]", "[[constitution.md]]"]
---

# Идея: переключаемые драйверы хранения кэша поиска и истории (`JSON`/`JSONL` vs раздельные базы `SQLite + FTS5 BM25`)

- Тип: `idea`
- Создан: 2026-11-26
- Идентификатор: `doc:ideas/sqlite-storage-drivers.md`
- Статус: `captured` (идея зафиксирована, не перешла в план)

## Суть

**Уточнение архитектурного аудита 2026-11-28.** [План CLI, З0-S](../plan/unified-cli-output-implementation.md)
выделяет границы хранения и сохраняет действующие JSON/JSONL. Эта идея
описывает возможный второй этап. Рекомендуемый порядок: SQLite-индекс с
прежней семантикой запроса, отдельная оценка FTS5, затем независимая
миграция истории при доказанной пользе. K30 базового JSON-профиля сохраняется.

Выстроить в `todoc` единую плагинную архитектуру **двух независимых драйверов хранения служебных контуров** — **`IndexDriver`** (весь производный кэш индексации, парсинга, графа, тегов, скилов и полнотекстового поиска) и **`HistoryDriver`** (журнал ревизий, метки и снимки файлов):

```text
[Файлы данных — единственная истина в Git]
  *.md, *.json, *.csv, SKILL.md, .config.json, .todocignore, .todoc/{dataset.json, rules/, *_types/}
        │                                                       │
        ▼ (Инкрементальный индексатор O(Δ))                     ▼ (Запись / откат / теги ревизий)
  ┌─────────────────────────────┐                         ┌─────────────────────────────┐
  │   Порт 1: IndexDriver       │                         │   Порт 2: HistoryDriver     │
  ├─────────────────────────────┤                         ├─────────────────────────────┤
  │ • json   (.todoc/index/*.json│                        │ • jsonl  (journal.jsonl +   │
  │           + cache/parse/)   │                         │           refs.json + obj/) │
  │ • sqlite (.todoc/index/     │                         │ • sqlite (.todoc/history/   │
  │           index.sqlite)     │                         │           history.sqlite)   │
  │ • [custom plugin driver...] │                         │ • [custom plugin driver...] │
  └─────────────────────────────┘                         └─────────────────────────────┘
```

1. **Ни один модуль системы не читает и не пишет кэш или историю в обход драйвера** (никаких скрытых обходов диска на лету в `search.py`, `folder_config.py`, `skills.py`, `staleness.py`, `history.py`).
2. **Инкрементальный пересчёт производных данных.** Цель — пересчитывать изменившиеся файлы и затронутые ссылки/якоря. Обнаружение правок, глобальные конфиги и полный запуск CLI измеряются отдельно.
3. **Драйвер поиска/кэша и драйвер истории переключаются независимо друг от друга**, а в режиме `sqlite` физически разнесены по **двум разным базам** (`index.sqlite` ≠ `history.sqlite`).
4. **Открытый реестр драйверов** позволяет легко подключить любой новый бэкенд хранения без правок CLI и бизнес-логики `application/`.

## Проблема

### Фактический аудит текущего кода (`src/todoc/`)

1. **Кэш сейчас размазан и обходится стороной в половине модулей:**
   - `search.py` при каждом вызове `todoc docs search` игнорирует индекс и заново читает и парсит с диска **все `.md`-файлы базы** (`1 094.7 мс` уже на `452` документах `demo/`).
   - `folder_config.py` при каждом `search` / `tree` / `suggest` заново обходит дерево ФС в поисках `.config.json`.
   - `skills.py` при каждом `skills tree` заново сканирует файловую систему без кэша.
   - `staleness.py` и `docs links` перечитывают файлы вместо запроса к индексу ссылок и секций.
   - Кэш разбора `.todoc/cache/parse/<hash>.json` плодит сотни мелких файлов и работает только для Markdown, но не для JSON-записей.
2. **Отсутствие честной инкрементальности снапшота:** при изменении хотя бы 1 байта в 1 файле `ensure_index()` заново парсит 100% JSON-записей, заново строит `mentions` и **полностью перезаписывает все 7 файлов `.todoc/index/current/*.json`**, а каждый из 35 CLI-вызовов делает `json.loads()` всего снапшота целиком в память.
3. **Линейная деградация журнала истории:** `record_write()` в `history.py` при каждой записи линейно читает весь `journal.jsonl` с первой строки (`_last_revision_for`), так же линейно работают `log`, `blame`, `timeline`, а снимки в `.todoc/history/objects/` создают россыпь мелких файлов без сжатия.

### Живой замер скорости (`Python 3.11`, `SQLite 3.40` WAL + `FTS5`)

Цифры ниже описывают исследовательский замер и оценки прототипов.
Для релизного порога нужен сопоставимый end-to-end прогон на одном
корпусе, с одинаковыми фильтрами, ранжированием и требованиями свежести.

| Холодный вызов CLI | Текущий `todoc` (`N=657`) | Оптим. `JSON` (`N=650`) | **`SQLite+FTS5` (`N=650`)** | Оптим. `JSON` (`N=5 000`) | **`SQLite+FTS5` (`N=5 000`)** | Оптим. `JSON` (`N=25 000`) | **`SQLite+FTS5` (`N=25 000`)** |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Фильтр выборки** (`--type`, `--within`, `LIMIT 100`) | `37.7 мс` | `2.90 мс` | **`0.33 мс`** *(×9)* | `29.86 мс` | **`0.92 мс`** *(×32)* | `138.76 мс` | **`0.37 мс`** *(×375)* |
| **Поиск + полевой `BM25`** (`tags`, `title`, `body` + `LIMIT 100`) | **`1 094.7 мс`** | `3.56 мс` | **`1.14 мс`** *(×960!)* | `40.20 мс` | **`6.26 мс`** *(×6.4)* | `189.20 мс` | **`22.64 мс`** *(×8.4)* |
| **Инкрементальный апдейт 1 файла** (`docs edit`, `tags set`) | **`341.8 мс`** | `~50–300 мс` | **`2.81 мс`** *(×120)* | `~500–2500 мс` | **`2.08 мс`** *(O(1))* | `~3 000–12 000 мс` | **`2.66 мс`** *(O(1))* |
| **Полная пересборка с нуля** (`index rebuild --force`) | `341.8 мс` | `~250 мс` | `45.6 мс` | `~1.8 с` | `333.8 мс` | `~9.0 с` | `1.49 с` |

## Принципы

1. **Файлы данных — единственная истина; кэш 100% производный.** Удаление `.todoc/index/` никогда не ведёт к потере знаний и полностью восстанавливается из файлов данных.
2. **Единые ворота для хранилищ.** Выборки индекса идут через порт индекса, операции журнала — через порт истории. Чтение исходного тела, конфигов и vault по необходимости идёт через сервис источников. Драйвер не становится владельцем семантики CLI или источником знаний.
3. **Две физически раздельные БД в режиме `sqlite` (`index.sqlite` ≠ `history.sqlite`).**
   - `.todoc/index/index.sqlite` — **эфемерный пересобираемый кэш** (`synchronous=NORMAL`, можно сносить при `index rebuild --force`);
   - `.todoc/history/history.sqlite` — **персистентное хранилище истории**, с отдельной политикой долговечности/backup и независимым переключением. Поиск по свежему индексу не открывает историю. Операции самой истории могут столкнуться с блокировками.
4. **Инкрементальность по графу зависимостей на всех драйверах.** Дифф сканера выделяет только изменившиеся/удалённые пути `Δ` и узкий круг зависящих от них ссылок `Δ_dep`; неизменившиеся сущности не перепарсиваются и не перестеммируются ни в `sqlite`, ни в `json`.
5. **Расширяемость без переписывания ядра (Plug-and-Play Drivers).** Новый драйвер регистрируется в реестре портов (включая внешние пакеты через Python `entry_points`) и сразу работает со всеми командами CLI.

## Предложение

### 1. Реестр плагинов и независимая конфигурация драйверов

В `src/todoc/ports/storage.py` определяются два контракта `Protocol` (`IndexDriver`, `HistoryDriver`) и реестр фабрик с поддержкой `importlib.metadata.entry_points`:
- группа `todoc.index_drivers`: встроенные `"sqlite"`, `"json"` (+ возможность подключить `"postgres"`, `"duckdb"`, `"opensearch"` и др.);
- группа `todoc.history_drivers`: встроенные `"sqlite"`, `"jsonl"` (+ независимый источник образов «до»: `blob_source: "embedded" | "git"` с правилом gap-filling, который одинаково работает и поверх `jsonl`, и поверх `sqlite`!).

Конфигурация в `.todoc/dataset.json`:

```json
{
  "storage": {
    "index": {
      "driver": "sqlite",
      "options": {}
    },
    "history": {
      "driver": "sqlite",
      "blob_source": "git",
      "fallback_blob_source": "embedded"
    }
  }
}
```

Команды управления и беспотерьной миграции **`todoc storage`**:
- `todoc storage status --root KB` — активные драйверы обоих контуров, размеры кэша/истории, число сущностей, ревизий и сжатых блобов;
- `todoc storage switch --root KB --index sqlite|json` — атомарно перестраивает поисковый кэш на целевом драйвере и переключает `dataset.json`;
- `todoc storage switch --root KB --history sqlite|jsonl [--preview | --apply]` — конвертирует историю (`journal.jsonl + refs.json + objects/ ↔ history.sqlite`) с побитовой проверкой всех `rev` и контрольных сумм снимков.

---

### 2. Единый конвейер инкрементальной индексации `O(Δ)`

Подтверждённая операция записи или явный rebuild может опубликовать
инкрементальное обновление. Read/preview проверяет свежий снимок либо
строит временную проекцию без записи. Для обнаружения кандидатов на
изменение используется обход с учётом каскадных [`.todocignore`](todocignore.md).
`mtime_ns` и size служат оптимизацией, а при строгой свежести нужны хеши
или согласованный механизм доказательства неизменности.

| Что изменилось на диске | Что пересчитывается в драйвере | Сложность |
|---|---|---|
| **0 изменений** (по политике проверенного снимка) | Переиспользуется опубликованный снимок | Стоимость обнаружения зависит от числа просмотренных путей и проверенных байтов |
| **Глобальные правила** (`.todoc/dataset.json`, `rules/*.json`, `*_types/**`, корневой `.todocignore`) | Полный пересчёт `rebuild(full=True)` (с переиспользованием кэша AST/стеммов тех файлов, чей `sha256` не изменился!) | Редкая операция настройки схемы |
| **Локальный `<dir>/.config.json` или `<dir>/.todocignore`** | Обновляется строка папки `<dir>` в `folders`, пересканируется только поддерево `<dir>/**` и обновляется колонка `folder_tokens` в FTS у элементов внутри `<dir>/**` | `O(|поддерева <dir>|)` |
| **Обычные файлы `Δ` (`K` добавленных / изменённых / удалённых `.md`, `.json`, `.csv`, `SKILL.md`)** | 1) Каскадное удаление старых записей `source_path ∈ Δ`;<br>2) Парсинг и стемминг `snowballstemmer` (`RU+EN`) **только для изменившихся файлов** и запись их новых строк;<br>3) Точечный пересчёт перекрёстных ссылок `Δ_dep` (см. ниже) | **`O(K + |входящих ссылок на Δ|)` — `~2–4 мс`!** |

**Как работает точечный пересчёт зависимой части (`Δ_dep`):**
- Пусть у затронутых файлов `Δ` множество старых и новых идентификаторов/имён равно `AffectedKeys = {old_id, new_id, old_stem, new_stem, old_path, new_path}`.
- По индексам `edges(target_id)`, `doc_links(resolved_path, target_stem)` и `derived_deps(target_path)` драйвер за `< 0.5 мс` выбирает **только те соседние документы и записи**, которые ссылались на `AffectedKeys`, и обновляет **только у них** статус разрешения ссылки (`broken` / `ambiguous` / `resolved`), рёбра `mentions`, устаревание `staleness` и перекрёстные диагностики (`scope = 'cross'`). Остальные `99.9%` базы вообще не трогаются!

---

### 3. Оптимальная схема БД №1 — `.todoc/index/index.sqlite` (весь кэш и поиск)

#### Кандидаты настроек для пишущих соединений

На read/preview не переключать режим журнала. Проверить отсутствие записи
и создания WAL/SHM в применимых режимах, поскольку допустимость открытия
read-only WAL зависит от окружения. [Документация SQLite WAL](https://www.sqlite.org/wal.html#read_only_databases).
```sql
PRAGMA journal_mode = WAL;          -- неблокирующее параллельное чтение CLI-процессами
PRAGMA synchronous = NORMAL;        -- максимальная скорость записи (кэш 100% пересобираемый)
PRAGMA foreign_keys = ON;           -- каскадная зачистка всех производных таблиц при правке файла
PRAGMA temp_store = MEMORY;         -- временные сортировки и CTE в ОЗУ
PRAGMA mmap_size = 134217728;       -- 128 МБ memory-mapped I/O без лишних системных вызовов read()
PRAGMA busy_timeout = 5000;
```

#### Полная структура таблиц и индексов `index.sqlite`

1. **`meta` — паспорт и версионирование кэша:**
   - `key TEXT PRIMARY KEY, value TEXT NOT NULL` (`schema_version`, `parser_version`, `stemmer_version`, `dataset_id`, `config_digest`, `corpus_digest`, `generation_id`, `updated_at`). Несовпадение `schema_version` или `parser_version` автоматически запускает прозрачный ребилд.
2. **`files` — физические файлы и сжатый кэш разбора (корень `ON DELETE CASCADE`):**
   - `path TEXT PRIMARY KEY` (относительный POSIX-путь от `DATA_ROOT`),
   - `parent_path TEXT NOT NULL`, `format TEXT NOT NULL` (`markdown|json|csv|folder_config|skill_md`),
   - `mtime_ns INTEGER NOT NULL`, `size INTEGER NOT NULL`, `sha256 TEXT NOT NULL`, `status TEXT NOT NULL`,
   - `parsed_ast_zlib BLOB` — сжатый `zlib` результат первичного парсинга и токенизации (полностью заменяет россыпь `.todoc/cache/parse/*.json`!).
   - Индексы: `idx_files_parent(parent_path)`, `idx_files_sha256(sha256)`.
3. **`folders` — иерархия директорий + встроенный кэш `.config.json`:**
   - `path TEXT PRIMARY KEY`, `folder_id TEXT UNIQUE NOT NULL`, `parent_path TEXT`, `depth INTEGER NOT NULL`,
   - `dir_type TEXT NOT NULL`, `rule_source TEXT NOT NULL`, `muted INTEGER NOT NULL DEFAULT 0`,
   - `has_config INTEGER NOT NULL DEFAULT 0`, `title TEXT`, `description TEXT`, `sort_order INTEGER`, `icon TEXT`, `lang TEXT`, `aliases_json TEXT`, `tags_json TEXT`, `ancestor_tokens TEXT`.
   - Индексы: `idx_folders_type_path(dir_type, path)`, `idx_folders_parent_order(parent_path, sort_order, path)` — обслуживают `docs suggest` и проекцию сжатого дерева [`todoc tree`](typed-tree-projection.md) (`--dir-type`, `--within`, `--lineage-for`) без чтения диска!
4. **`items` — единый унифицированный каталог всех сущностей (`document` + `record` + `folder` + `skill`):**
   - `rowid INTEGER PRIMARY KEY` (целочисленный ключ связки с `FTS5`!),
   - `item_id TEXT UNIQUE NOT NULL` (`doc:...`, `task:...`, `rule:...`, `folder:...`, `skill:...`),
   - `kind TEXT NOT NULL` (`'document' | 'record' | 'folder' | 'skill'`),
   - `sub_type TEXT NOT NULL` (`doc_type` / `entity_type` / `dir_type` в `snake_case`),
   - `source_path TEXT REFERENCES files(path) ON DELETE CASCADE`,
   - `folder_path TEXT NOT NULL` (для мгновенного префиксного фильтра `--within`),
   - `stem TEXT` (имя без расширения — для `O(1)` разрешения `[[wikilink]]` и детекта дублей!),
   - `format TEXT NOT NULL`, `title TEXT NOT NULL DEFAULT ''`, `status TEXT`, `muted INTEGER NOT NULL DEFAULT 0`,
   - `created_at TEXT`, `updated_at TEXT`,
   - **би-темпоральные колонки** ([`bitemporal-clocks`](bitemporal-clocks.md)): `valid_from TEXT`, `valid_to TEXT`, `observed_at TEXT`, `superseded_at TEXT`, `superseded_by TEXT`,
   - `hash TEXT`, `size INTEGER`,
   - `meta_json TEXT` (нормализованный `front_matter` у `.md`, полный объект `data` у `.json`-записи для фильтрации через `json_extract(meta_json, '$.field')`, счётчики `{section, refs, scripts, assets}` у `skill`).
   - Индексы:
     - `idx_items_filter(kind, sub_type, status, folder_path)` — покрывающий индекс основных выборок;
     - `idx_items_folder(folder_path, source_path)` — мгновенный срез `--within`;
     - `idx_items_stem(stem)` — разрешение wikilinks;
     - `idx_items_valid_clock(valid_from, valid_to, superseded_at)` и `idx_items_known_clock(observed_at, superseded_at)` — би-темпоральные выборки `--valid-at` / `--known-at`.
5. **`doc_sections` — оглавление, границы строк и хеши секций Markdown:**
   - `source_path TEXT REFERENCES files(path) ON DELETE CASCADE`, `ord INTEGER NOT NULL`, `level INTEGER NOT NULL`, `heading TEXT NOT NULL`, `anchor_slug TEXT NOT NULL`, `breadcrumb_json TEXT NOT NULL`, `line_start INTEGER NOT NULL`, `line_end INTEGER NOT NULL`, `section_hash TEXT NOT NULL`, `PRIMARY KEY (source_path, ord)`.
   - Индекс: `idx_sections_lookup(source_path, line_start, line_end)` — даёт мгновенные хлебные крошки для сниппетов поиска (без второго парсинга файла!), `docs read --section`, `log/blame --section` и проверку фрагментных якорей `derived_from`.
6. **`doc_links` — все исходящие ссылки и wikilinks с номерами строк:**
   - `link_id INTEGER PRIMARY KEY`, `source_path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE`, `line INTEGER NOT NULL`, `col INTEGER NOT NULL`, `link_kind TEXT NOT NULL` (`'md_rel' | 'wikilink' | 'fm_related'`), `raw_target TEXT NOT NULL`, `resolved_path TEXT`, `target_stem TEXT`, `anchor TEXT`, `state TEXT NOT NULL` (`'ok' | 'broken' | 'ambiguous'`).
   - Индексы: `idx_links_resolved(resolved_path)`, `idx_links_stem(target_stem)` — делают `docs links`, `linkcheck` и переписывание ссылок при [`todoc docs move`](docs-move.md) / [`todoc folderize`](entity-to-folder.md) мгновенными!
7. **`edges` — единый типизированный граф связей (`relations` + `mentions` + `has_tag`):**
   - `edge_id INTEGER PRIMARY KEY`, `source_id TEXT NOT NULL`, `target_id TEXT NOT NULL`, `type_id TEXT NOT NULL`, `via TEXT NOT NULL` (`'relation' | 'mention' | 'tag' | 'related'`), `source_path TEXT REFERENCES files(path) ON DELETE CASCADE`, `pointer TEXT`, `valid_from TEXT`, `valid_to TEXT`, `observed_at TEXT`, `superseded_at TEXT`, `is_dangling INTEGER NOT NULL DEFAULT 0`.
   - Индексы: `idx_edges_out(source_id, type_id, via)` и `idx_edges_in(target_id, type_id, via)` — обслуживают `WITH RECURSIVE` обходы `relations graph` и `relations tree` за `< 1 мс`.
8. **`item_tags` — сквозной индекс тегов всех объектов ([`todoc tags`](unified-tags-and-tag-graph.md)):**
   - `tag TEXT NOT NULL`, `item_rowid INTEGER NOT NULL REFERENCES items(rowid) ON DELETE CASCADE`, `item_id TEXT NOT NULL`, `item_kind TEXT NOT NULL`, `folder_path TEXT NOT NULL`, `source_path TEXT REFERENCES files(path) ON DELETE CASCADE`, `PRIMARY KEY (tag, item_rowid)`.
   - Индексы: `idx_item_tags_rowid(item_rowid)`, `idx_item_tags_folder(folder_path, tag)` — выдают `todoc tags list` и мульти-фильтр `--tag-in "a|b|c"` с подсчётом числа совпавших тегов одним `GROUP BY`!
9. **`derived_deps` и `record_metrics` — устаревание витрин и числовые агрегации:**
   - `derived_deps(source_path REFERENCES files(path) ON DELETE CASCADE, target_path TEXT NOT NULL, selector_kind TEXT, selector TEXT, pinned_hash TEXT, ack_at TEXT, ack_reason TEXT)` с `idx_derived_target(target_path)` для мгновенного `todoc stale`;
   - `record_metrics(item_rowid REFERENCES items(rowid) ON DELETE CASCADE, entity_type TEXT NOT NULL, metric_field TEXT NOT NULL, value REAL NOT NULL, unit TEXT NOT NULL, source_path TEXT REFERENCES files(path) ON DELETE CASCADE)` с `idx_metrics_agg(entity_type, metric_field)` для `records aggregate`.
10. **`diagnostics` — кэш валидации (`file`-локальные + `cross`-перекрёстные):**
    - `diag_id TEXT PRIMARY KEY`, `scope TEXT NOT NULL` (`'file' | 'cross'`), `source_path TEXT REFERENCES files(path) ON DELETE CASCADE`, `target_key TEXT`, `code TEXT NOT NULL`, `severity TEXT NOT NULL`, `line INTEGER`, `col INTEGER`, `evidence TEXT`, `message TEXT NOT NULL`, `fixes_json TEXT`.
11. **`fts_items` + `fts_trigram` — двухуровневый полнотекстовый поиск и ранжирование:**
    ```sql
    -- 1) Полевой индекс с двуязычными стеммами Портера/Snowball (RU+EN) и весами BM25:
    CREATE VIRTUAL TABLE fts_items USING fts5(
        id_tokens,       -- вес ×10.0 (id, slug, код задачи/бага)
        tag_tokens,      -- вес ×8.0  (теги документа/записи/папки)
        title_tokens,    -- вес ×5.0  (заголовок документа / name записи)
        heading_tokens,  -- вес ×2.5  (заголовки H1-H4 / ключевые поля записи)
        folder_tokens,   -- вес ×1.5  (title/aliases/tags папок-предков из .config.json)
        body_tokens,     -- вес ×1.0  (основной текст + стеммы RU/EN)
        tokenize = "unicode61 tokenchars '-_'"
    );

    -- 2) Триграммный индекс для мгновенного нестрогого подстрочного поиска в духе grep:
    CREATE VIRTUAL TABLE fts_trigram USING fts5(
        raw_text,
        tokenize = "trigram"
    );
    ```
    Обе виртуальные таблицы синхронизированы с `items.rowid`. При запросе `-q "запрос 1" -q "запрос 2" --sort relevance --limit 100` фильтр кандидатов строится по B-tree индексам `items` + `item_tags`, а скор релевантности объединяет `bm25(fts_items, 10.0, 8.0, 5.0, 2.5, 1.5, 1.0)` (по точным словам и стеммам `snowballstemmer`) и бонус подстрочного совпадения `fts_trigram`. В режиме пересортировки готовой выборки используется `LEFT JOIN` — элементы без текстовых совпадений получают `score = 0` и сохраняются в хвосте без потери данных!

---

### 4. Оптимальная схема БД №2 — `.todoc/history/history.sqlite` (отдельная БД истории)

#### Настройки движка при открытии соединения
```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = FULL;          -- гарантия сохранности истории даже при сбое питания
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
```

#### Полная структура таблиц и индексов `history.sqlite`

1. **`history_meta`** (`key TEXT PRIMARY KEY, value TEXT NOT NULL`) — `schema_version`, `dataset_id`, `blob_source` (`'embedded' | 'git'`).
2. **`events` — неизменяемый журнал событий записи:**
   - `seq INTEGER PRIMARY KEY AUTOINCREMENT`,
   - `rev TEXT NOT NULL`, обычный индекс по rev. Импорт сохраняет фактическую публичную ревизию и порядок даже при повторе или коллизии. Неоднозначный lookup сообщает ошибку.
   - `at TEXT NOT NULL`, `kind TEXT NOT NULL`, `actor TEXT NOT NULL`, `change_id TEXT`, `basis TEXT`,
   - Исходная запись хранится без потери значимых байтов (при необходимости BLOB исходной строки), а поисковые колонки вычисляются отдельно. Пересериализация может изменить вычисляемый rev.
   - Индексы: `idx_events_at(at DESC, seq DESC)`, `idx_events_change(change_id, seq DESC)`, `idx_events_kind(kind, seq DESC)`.
3. **`event_paths` — затронутые файлы и диапазоны изменённых строк (`1:N` к `events`):**
   - `event_seq INTEGER NOT NULL REFERENCES events(seq) ON DELETE CASCADE`,
   - `ord INTEGER NOT NULL`, `path TEXT NOT NULL`,
   - `before_hash TEXT`, `after_hash TEXT NOT NULL`, `git_head TEXT`,
   - `ranges_json TEXT NOT NULL` (`[[line_start, line_end], ...]` для секционного `log/blame --section`),
   - `extra_json TEXT`, `PRIMARY KEY (event_seq, ord)`.
   - Индекс: `idx_event_paths_file(path, event_seq DESC)` — делает `_last_revision_for(path)` при записи, `todoc log --path`, `blame`, `revert` и `timeline --path` мгновенными `O(1)`!
4. **`refs` — указатель `HEAD` и релизные метки `todoc tag` (замена `refs.json`):**
   - `name TEXT PRIMARY KEY` (`'HEAD'` или имя тега ревизии), `ref_kind TEXT NOT NULL` (`'head' | 'tag'`), `rev TEXT NOT NULL`, `at TEXT NOT NULL`, `message TEXT NOT NULL DEFAULT ''`.
5. **`blobs` — дедуплицированное сжатое хранилище снимков «до» (замена `.todoc/history/objects/`):**
   - `sha256 TEXT PRIMARY KEY`, `raw_size INTEGER NOT NULL`, `compression TEXT NOT NULL DEFAULT 'zlib'`, `data BLOB NOT NULL`, `created_at TEXT NOT NULL`.
   - Текстовые `.md`/`.json` сжимаются в `4–8×`, не создают тысяч мелких файлов в ФС, а сборка мусора `todoc history gc` выполняется одним SQL-запросом по неиспользуемым `sha256`!

---

### 5. Выравнивание `JsonIndexDriver` и `JsonlHistoryDriver` под те же контракты

Чтобы переключение `sqlite ↔ json` было на 100% симметричным:
- `JsonIndexDriver` реализует тот же интерфейс `IndexDriver`: хранит расширенный снапшот в `.todoc/index/current/*.json` (включая секции, ссылки, теги и стеммированный `lexical.json`), при диффе `Δ` обновляет в памяти только затронутые записи словаря (не перепарсивая неизменившиеся файлы!) и применяет ту же логику ранжирования `BM25F` + `snowballstemmer`.
- `JsonlHistoryDriver` оборачивает текущие `journal.jsonl` + `refs.json` + `objects/` под протокол `HistoryDriver`.

## План внедрения

1. **Фаза 1 — Контракты `IndexDriver` / `HistoryDriver`, реестр плагинов и обёртки текущих `json`/`jsonl` драйверов:**
   - Ввести `ports/storage.py` с `entry_points`-регистрацией и перевести все чтения индекса/истории в `application/` и `cli.py` на вызовы драйверов (убрав прямые обходы диска из `search.py`, `folder_config.py`, `skills.py`).
   - *Acceptance:* все 1280 существующих тестов зелёные на `json + jsonl` драйверах.
2. **Фаза 2 — `SqliteIndexDriver` (`index.sqlite`) + инкрементальный координатор `O(Δ)` + `FTS5 BM25` (`snowballstemmer`):**
   - Реализовать полную схему из 11 таблиц + `fts_items`/`fts_trigram`, каскадное обновление диффа `Δ` + `Δ_dep` и сквозные флаги `-q ... -q ... --sort relevance --limit 100` для всех выборок.
   - *Acceptance:* общие тесты JSON/SQLite подтверждают совпадение фильтров, полноты и диагностик. Пока алгоритм один, проверяется одинаковый порядок. FTS5/BM25, токенизация и стемминг требуют отдельной проверки релевантности. Релизные пороги латентности задаются после сопоставимого замера всего CLI. [Документация SQLite FTS5](https://www.sqlite.org/fts5.html).
3. **Фаза 3 — `SqliteHistoryDriver` (`history.sqlite`) и CLI `todoc storage status|switch`:**
   - Реализовать `history.sqlite` (`events`, `event_paths`, `refs`, `zlib`-`blobs`), поддержку `blob_source: git|embedded` и двустороннюю миграцию `jsonl ↔ sqlite` с проверкой всех `rev`.
   - *Acceptance:* параметризованные тесты `@pytest.mark.parametrize("history_driver", ["jsonl", "sqlite"])` проходят на 100% (`100%` branch coverage, `todoc validate --root demo --all` = `0`).

## Открытые вопросы

- **Порог автоматического `PRAGMA optimize` и `wal_checkpoint(TRUNCATE)`:** вызывать лёгкий `PRAGMA optimize;` при закрытии соединения после пишущих команд индексатора и мягкий checkpoint при превышении `WAL`-файлом размера `16 МБ`, чтобы `index.sqlite-wal` не разрастался при тысячах мелких правок.
- **Хранение больших CSV (`> 100 000` строк):** метаданные и заголовки колонок CSV индексируются в `items` и `fts_items`, а построчные выборки `docs read --where` могут опционально кэшироваться во временную таблицу или читаться потоково, чтобы не раздувать `index.sqlite`.

## Связанные документы

- [Ресёрч: Python-библиотеки `BM25`/`BM25F` и двуязычного стемминга (`RU+EN`)](../.research/bm25-ranking-python-libs.md)
- [Идея: сквозная система тегов (`todoc tags`, граф связей и `--tag-in`)](unified-tags-and-tag-graph.md)
- [Идея: `todoc tree` — типизированная проекция дерева в CLI](typed-tree-projection.md)
- [Идея: раздельные часы `valid_at` и `known_at` для би-темпоральных выборок](bitemporal-clocks.md)
- [Идея: `todoc docs move` — транзакционный перенос документа](docs-move.md)
- [Идея: `todoc folderize` — преобразование сущности в папку-домен](entity-to-folder.md)
- [Идея: `.todocignore` — исключение посторонних файлов и папок](todocignore.md)
- [Конституция `todoc` (переносимость данных и отказ от фоновых демонов)](../plan/constitution.md)
