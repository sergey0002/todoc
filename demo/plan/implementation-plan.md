---
id: doc:implementation-plan
title: "Implementation plan: план реализации MVP"
doc_type: implementation-plan
lang: ru
source: .doc/plan/implementation-plan.md
copied: true
---

# todoc — Пошаговый план реализации (MVP сейчас + перспективы в `.after.md`)

**Статус:** план реализации. При конфликте с [`constitution.md`](constitution.md) приоритет имеет конституция; этот файл — **как** строить, конституция — **что** строить.
**Дата:** 24 ноября 2026 года. **Версия:** 0.3 (до реализации; §13–§15 — финальный аудит и ресерч по референсам, §16 — лучшие традиции MCP и хранилища памяти по корневому гайду MCP, research MCP/CLI, гайдам CLI/Markdown и аудиту Skills, дополнено 24 ноября 2026).
**Связанные документы:** [`constitution.md`](constitution.md) — требования FR/NFR, принципы P1–P14, сценарии S1–S12, CLI-контракт, структура файлов; [`competitive-analysis.md`](competitive-analysis.md) — CLI вход/выход конкурентов, мастер-список C01–C60, сравнительные таблицы, портабельность; [`../plan.md`](../.research/engineering-plan.md) — инженерный набросок (§15 — этапы, §14 — тесты, §17 — открытые вопросы); [`../todoc_knowledge_base_comparative_audit.md`](../.research/comparative-audit.md) — аудит Skills.

> **Как читать.** Слова **MUST / SHOULD / MAY** — нормативные (см. конституцию). **MVP** — то, что строится сейчас (Этап 0 → Этап 7 ниже). Всё, помеченное «перспектива», **не реализуется сейчас** и вынесено в отдельные файлы с постфиксом **`.after.md`** (см. §9). Архитектура MVP спроектирована так, чтобы каждая перспектива вставлялась **без переписывания ядра** — через заранее заложенные порты и точки расширения (§2).

---

## 0. Цели проекта (что строим и зачем)

### 0.1. Миссия

Дать человеку и его агенту **одну переносимую папку знаний**, где пользователь сам описывает типы объектов, а агент **предсказуемо и проверяемо** сохраняет, связывает, проверяет и находит их — без сервера, облака и скрытых LLM-вызовов в ядре. (Конституция §1.)

### 0.2. JTBD (задачи, которые закрывает MVP)

| JTBD | Сценарий конституции | Этапы MVP |
|---|---|---|
| «Сохрани ссылку/заметку/ресерч/план так, чтобы нашлось и было связано» | S1, S2, S3 | Этап 4–7 (capture) |
| «Проверь папку: где битые ссылки, неверные схемы, дубли ID — с точным местом» | S5 | Этап 4, 6 |
| «Найди все X, где поле Y = Z и связано с W, и покажи только нужное» | S6, S7 | Этап 5 |
| «Посчитай агрегат по моим записям — с формулой, единицами и источниками» | S7, S8 | Этап 5 |
| «Перенеси папку на другой путь/машину — и всё работает» | S4 | Этап 2–3, 5 |
| «Открой папку в Obsidian и посмотри как человек» | S9 | Этап 7 |

### 0.3. Не-цели MVP (явно не делаем сейчас)

- НЕ клон Obsidian / RAG-чат / hosted-сервис / task manager / CRM / календарь.
- НЕ автономная LLM-компиляция базы (нет скрытого ingest/synthesis).
- НЕ graph DB / vector DB / embeddings / reranker как обязательная инфраструктура.
- НЕ веб-интерфейс, MCP-сервер, cloud sync, multi-user, плагины, YAML/XLSX/PDF-парсинг, watch mode, scheduled agents.
- Всё перечисленное — в `.after.md` файлах (§9). Попытка «впихнуть всё в MVP» — нарушение конституции (P5, P12, §6.10).
- MCP в MVP не реализуется, но его лучшие традиции (stateless, tools/resources/prompts, `structuredContent`/`outputSchema`, `resultType`/`isError`, progressive disclosure, `next_actions` как hints) **закладываются в контракты CLI** (§16, `mcp-adapter.after.md` M1–M26), чтобы MCP вставился без переписывания ядра. Традиции хранилища памяти (слои docs/knowledge/memory/raw/logs/indexes, процедуры ingest/query/write/lint, provenance, trust/authority/freshness/access, ступени поиска, протокол benchmark-а) фиксируют границу MVP: `todoc` в MVP — не memory-система (аудит §2, §5), а memory-профиль — отдельный scope в `memory-llm-wiki.after.md`.

### 0.4. Рабочая гипотеза ценности (проверяется Этапом 0)

> «Опиши свои знания как переносимые типизированные файлы; подключи к типам проверяемые workflows; сохрани записи, связи и схемы в обычной папке; используй общий CLI для безопасного capture, validate, query, aggregate и bounded read».

Это гипотеза о **связке**, а не об уникальности компонентов. Доказательство — только discovery gate на реальных папках (§4, Этап 0).

---

## 1. Принципы реализации (конституция P1–P14 → инженерные правила)

| Принцип | Инженерное правило в MVP |
|---|---|
| P1 Файлы — истина | Source files — единственный source of truth. Индексы/кэш/граф — derived, удаляемые, пересобираемые. Запрещено: истина в SQLite/векторной БД |
| P2 Портабельность | Только relative paths в конфигах/индексах; `dataset_id` переживает move; cold-rebuild без фикса. Тест: перенести root + удалить `.todoc/index` + `.todoc/cache` → всё работает |
| P3 Декларативность | Типы/схемы/шаблоны/отношения/queries — JSON. Никакого Python/shell/prompt-кода в DATA_ROOT. Валидация конфигов до использования |
| P4 Разделение измерений | `format` ≠ `doc_type` ≠ `dir_type` ≠ `entity_type` ≠ `relation_type` ≠ query/view. Отдельные резолверы, отдельные каталоги типов |
| P5 Детерминированное ядро | Scan/check/validate/search/read/query — без LLM/сети. Модель — только в Skill-диалоге и opt-in адаптерах (`.after.md`) |
| P6 Review-first запись | Existing sources read-only. Разрешены: `docs new`, `records create` (новый JSON), preview/diff + `--apply` с `expected_hash`. Нет auto-save беседы |
| P7 Bounded context | counts/outline → snippets → fragment; `--budget`, `truncated`, cursor, provenance/hash обязательны в каждом ответе |
| P8 Точные locations | Каждая диагностика/хит: root-relative path + row/column / JSON Pointer / line/column/anchor + hash + severity |
| P9 Явные связи | Typed edges в источнике, валидация endpoint/cardinality, derived graph/backlinks. Нет дрейфующей graph DB |
| P10 Доверие — установленному коду | Исполняемый код — только из пакета/Skill. DATA_ROOT — недоверенные данные. Workflow — только whitelisted `workflow_id` |
| P11 CLI — контракт, Skill — диалог | CLI владеет валидацией/правами/записью. Skill выбирает тип, задаёт вопросы, вызывает CLI. MCP/веб — тонкие адаптеры (`.after.md`) |
| P12 Offline-first | Default — offline lexical/path/metadata. Сеть/модель — opt-in с consent/benchmark/fallback (`.after.md`) |
| P13 Объяснимость | `explain-path`, `types guide`, `next_actions` (argv-массив). Неоднозначность → diagnostic/clarify, не догадка |
| P14 Совместимость без зависимости | DATA_ROOT открывается как Obsidian vault; Obsidian/OKF — опциональные профили, не зависимости |

---

## 2. Архитектура и точки расширения (чтобы перспективы вставлялись легко)

### 2.1. Слои (SOLID, без избыточной иерархии)

```
CLI (Click, тонкий) ─┐
Skill (SKILL.md) ────┼─→ Application / Use cases ─→ Ports (Protocol) ─→ Adapters
MCP (будущее) ───────┤         (domain без CLI/filesystem)
Web (будущее) ───────┘
```

- **Domain:** `DatasetId`, `DocumentId`, `RecordId`, `ObjectRef`, `TypedRecord`, `RelationRef`, `QuerySpec`, `Projection`, `Diagnostic`, `ValidationReport`, `SearchHit`, `WritePlan`. Без Click/`pathlib`/search provider/структуры `.todoc`.
- **Application:** `ScanDataset`, `ResolveProfiles/Types`, `CreateRecord`, `ValidateRecord`, `ResolveRelations`, `QueryRecords`, `AggregateRecords`, `SearchObjects`, `ReadProjection`, `ApplyReviewedWrite`, `GenerateTypeReference`.
- **Ports:** см. §2.2. **Adapters:** Click CLI, `pathlib`/`os.scandir`, JSON/CSV/Markdown codecs, JSON Schema validator, file-backed record store, JSON snapshots, optional SQLite FTS (MVP) + будущие QMD/vector/graph bridges (`.after.md`).
- **Composition root:** собирает приложение из adapters, передаёт явно. Глобальных singleton-ов и импорта CLI из business logic нет.

**Запрещено:** классы `CsvResearchDocument`/`JsonResearchDocument`/… (матрица наследования). Форматный driver даёт parse/serialize; типовая политика и validator — смысл.

### 2.2. Порты и точки расширения E1–E10

Каждый порт в MVP имеет **одну** реализацию. Будущие перспективы подключаются **новой** реализацией + регистрацией, без изменения use cases и `SearchHit`/`Diagnostic` контрактов.

| ID | Порт (Protocol) | MVP-реализация | Будущая перспектива (`.after.md`) | Как вставить без переписывания |
|---|---|---|---|---|
| **E1** | `FormatReader` / `FormatWriter` | `markdown`, `csv`, `json` drivers | YAML/XLSX/PDF/SQLite (`plugins-formats-import.after.md`) | Новый driver + одна регистрация в `dict[FormatId, FormatDriver]` + contract tests. Без `if/elif` в слоях |
| **E2** | `TypeRegistry` / `ProfileResolver` | JSON descriptors + rules + inheritance | Memory/domain профили (`memory-llm-wiki.after.md`) | Новые `entity_type`/`relation_type` descriptors + schemas; core не меняется |
| **E3** | `Validator` (syntax/schema/relation/business) | JSON Schema 2020-12 + built-in business validators | Claim/evidence validators, semantic lint (`memory-llm-wiki.after.md`) | Новый validator + регистрация; `Diagnostic` contract не меняется |
| **E4** | `CandidateRetriever` | Offline lexical/path/metadata (FTS5 или минимальная альтернатива) | Vector/hybrid/graph/QMD bridge (`search-embeddings-vector.after.md`) | Новый retriever + fusion; `SearchHit` contract не меняется |
| **E5** | `Ranker` / `Reranker` / `Renderer` | Deterministic rank + bounded projection renderer | Hybrid fusion, model reranker (`search-embeddings-vector.after.md`) | Новые ranker/reranker + регистрация; fallback на lexical при недоступности |
| **E6** | `RecordStorage` / `GenerationStore` | File-backed records + atomic JSON generations (`CURRENT.json`) | Bundle-транзакции, sync (`memory-llm-wiki.after.md`, `sync-collab-export.after.md`) | Новый store поверх тех же `RecordId`/`ObjectRef`; generations остаются derived |
| **E7** | `QueryEngine` (safe declarative AST) | Allowlisted operators + units/formula/provenance | Расширенные metrics, Dataview-like DQL (`memory-llm-wiki.after.md`) | Новые versioned operators + тесты; запрет Python/SQL/`eval` сохраняется |
| **E8** | `WorkflowLookup` | Whitelisted `workflow_id` → trusted Skill | MCP tools/resources/prompts, веб-действия (`mcp-adapter.after.md` M1–M3, M15, M23; `web-ui.after.md`) | Новый adapter поверх application-слоя; CLI остаётся authority. MCP tools — thin wrappers над use cases; resources — адресуемый контекст по URI; prompts — шаблоны capture/query/lint |
| **E9** | `Hashing` / `Locking` / `AtomicWrite` | SHA-256 + dataset-level lock + temp+replace | Multi-writer/sync (`sync-collab-export.after.md`) | Тот же `WritePlan`/`expected_hash` контракт; single-writer policy поверх |
| **E10** | `OutputSerializer` | JSON envelope + table/markdown | MCP `structuredContent` + `TextContent` + `outputSchema`/`resultType`/`isError` (M9, M12), веб JSON API, SARIF (`mcp-adapter.after.md`, `web-ui.after.md`, `sync-collab-export.after.md`) | Новый serializer поверх тех же `data`/`diagnostics`/`next_actions`. CLI `next_actions` (argv-массив) → MCP `next_actions` (tool hints, M25); CLI envelope → MCP `structuredContent` без буквального копирования |

**Правила расширения (MUST):**
1. Новый формат/поиск/профиль — **новая реализация порта + регистрация**, не правка use cases.
2. `SearchHit`, `Diagnostic`, `ValidationReport`, `WritePlan`, JSON envelope — **стабильные контракты**. Будущие адаптеры их не меняют (только добавляют optional поля с `schema_version` bump).
3. Все будущие сетевые/модельные адаптеры — **opt-in** (конфиг-флаг + consent + benchmark + fallback на offline). Ядро никогда не требует сети/модели (P5, P12).
4. Все будущие схемы данных — **versioned** (`schema_version` в каждом JSON). Миграции — явные `migrate/check` команды, не «примерно совместимо».
5. Плагины (если появятся) — только **установленные entry points по allowlist** с проверкой API version. Никогда — код из DATA_ROOT (P10).

### 2.3. Поисковый pipeline (MVP + будущие вставки)

```
filter/scope → candidate retrieval (E4: lexical MVP; позже vector/graph) → fusion/rank (E5) → optional rerank (E5) → bounded projection (E5 Renderer)
```

MVP: только lexical/path/metadata + deterministic rank + bounded projection. Будущее (`search-embeddings-vector.after.md`): vector/graph retriever + hybrid fusion + reranker — как **дополнительные** реализации E4/E5, с fallback на lexical.

### 2.4. Write pipeline (MVP + будущие вставки)

```
WritePlan (target/template, patch/new content, expected/new hash, preview diff, writer E1, validations E3) → preview (default) → --apply (expected_hash + temp + atomic replace/create E9) → re-parse + re-validate (E3) → new generation (E6)
```

MVP: 1 новый файл (`docs new` / `records create`) или 1 review-first patch. Будущее (`memory-llm-wiki.after.md`, `sync-collab-export.after.md`): многофайловые bundle-транзакции и sync — как **надстройка** над тем же `WritePlan`/`expected_hash`, не замена.

---

## 3. Решения по умолчанию и конкурентные находки

### 3.1. Решения по умолчанию (подтвердить на Этапе 0.5)

| Решение | Default | Альтернатива | Почему |
|---|---|---|---|
| Python | `>=3.12` | `>=3.11` (обход через `os.scandir`, без `Path.walk`) | Современный typing/API; 3.11 — только если нужна совместимость + CI на 3.11 |
| CLI framework | **Click** | Typer | Композиция вложенных команд, help, exit codes, `CliRunner`; core не зависит от framework |
| Layout | `pyproject.toml` + `src/todoc/` + тесты отдельно | Flat layout | Не импортировать код из checkout; wheel тестируется вне repo; `todoc = "todoc.cli:main"` |
| Config | JSON в `<DATA_ROOT>/.todoc/`; override `<folder>/.todoc.json` | `todoc/` / `.agentdocs/` | Переносимость; переименование — только до первого schema version |
| Schemas | JSON Schema 2020-12 + `jsonschema` | — | Draft зафиксирован; локальные `$ref` только внутри корня; без сети |
| Markdown parser | `markdown-it-py` (CommonMark) + `obsidian-compatible` profile | — | Token stream для headings/links/locations; не regex |
| CSV | Python `csv` (`newline=''`, explicit dialect) | — | Dialect/encoding/header/quoting — из конфига, не угадываются |
| Lexical backend | SQLite FTS5 (если доступен в builds) или минимальная альтернатива | QMD bridge (`.after.md`) | Benchmark на корпусе; FTS5 — возможный производный индекс, не `doc_type` |
| Generated guide | Общая справка — в Skill `references/`; per-dataset — stdout или явный `--out` в `.todoc/generated/` | — | Не загрязнять общий Skill dataset-specific данными |
| `harness` spelling | Каноническое `harness`; `harnes` — только alias | — | Не делать fuzzy match |
| Search backend | Встроенный deterministic lexical/metadata | Thin integration с QMD | Benchmark + порты E4/E5; external vector/graph/reranker — только `.after.md` |

### 3.2. Конкурентные находки → инженерное решение

| Находка (competitive analysis) | Решение в MVP |
|---|---|
| **mdkb:** `--root`, `--json` goldens, `--dry-run`, `--allow-write`, disposable cache, git commit per write | **Копировать контракт:** явный `--root`, `--json` на чтениях, `--dry-run`/`--preview`, read-only MCP по умолчанию (будущий MCP), disposable cache + cold-rebuild тест |
| **QMD:** `search/vsearch/query/get/multi-get/status/mcp`, `--json`, metadata-фильтры, processors→MD в индексе | **Копировать имена/флаги** для `docs search/read`; processors не копировать (доверенный код в индексе противоречит P10). QMD bridge — только `.after.md` |
| **Open Knowledge:** `setup/check/validate/search/view/eval`, plan-before-write diff, file/line/hash, MRR/Recall/nDCG | **Копировать:** `check` (сводка) vs `validate` (детали), `eval` (retrieval benchmark), plan-before-write. Markdown-only не копировать — `todoc` source-native MD/CSV/JSON |
| **okf:** `validate/lint/index/list/show/search/backlinks/graph`, SARIF, `--fail-on`, NDJSON | **Копировать:** `validate` vs `lint` разделение, SARIF/CI-gate как v1 (Этап 7.5), NDJSON для больших листингов. OKF-формат — опциональный профиль, не требование |
| **Basic Memory:** MD canonical + SQLite/PG проекция, watcher, stable id survives move, MCP tools, SessionStart brief | **Копировать для MVP:** MD canonical + rebuildable индекс, stable IDs. Watcher/SessionStart — только в `memory-llm-wiki.after.md` / `plugins-formats-import.after.md` |
| **Obsidian CLI:** `search:context` (path:line), `backlinks/unresolved/orphans`, `format=json`, `vault=` | **Копировать subset:** path:line snippets, backlinks/unresolved, JSON output. Не копировать зависимость от запущенного приложения и `eval` (JS в приложении) |
| **Tana/Capacities/Dataview:** supertags/objects/DQL, live queries, units | **Копировать идею:** `entity_type` + safe query/aggregate с units/formula/provenance. Не копировать cloud/app реализацию |
| **OpenKB:** `add/query/chat/visualize/skill/deck`, LLM compile + overwrite | **Не копировать** (кроме `lint`/`visualize` как идей). LLM compile + overwrite противоречит P5/P6 |
| **AnythingLLM/Khoj/Open Notebook/RAGFlow:** app-owned storage, vector DB — истина | **Не копировать.** Интегрироваться как opt-in adapter только в `.after.md` при доказанной боли |
| **Mem0/Zep/Letta:** vector/graph/state — истина, LLM on write | **Не копировать** в core. Только в `memory-llm-wiki.after.md` как opt-in |
| **obsidian-second-brain:** 40+ команд, task/idea/project, scheduled agents | **Не копировать** как есть. Task/idea схемы — референс для `memory-llm-wiki.after.md` |
| **Karpathy LLM Wiki:** `raw/wiki/index/log`, ingest/query/lint | **Не копировать** в core. Отдельный профиль в `memory-llm-wiki.after.md` |
| **Лучшие традиции MCP** (guide MCP 1–26, research §3–§9, редакция 2026-07-28) | **Копировать как контракты:** tools/resources/prompts по назначению (M1); имена `todoc.<verb>_<object>` + стабильный каталог (M3); `inputSchema`/`outputSchema` + `structuredContent`/`TextContent` (M5, M9); `resultType` vs `isError` (M12); stateless + явный handle (M13); `ttlMs`/`cacheScope` private/public (M14); deferred loading `<20` tools эвристика (M15); progressive disclosure summary→outline→ветвь (M21); `next_actions` как bounded hints (M25); server-side authz при каждом вызове (M8, M26). Полный список M1–M26 — в `mcp-adapter.after.md` §3, сводка — §16 |
| **Традиции хранилища памяти** (guide MD-KB §I, §V–§XI; аудит §5–§6) | **Копировать как границы:** слои docs/knowledge/memory/raw/logs/indexes (§16.2); процедуры ingest/query/write/lint (R16); provenance `утверждение → scope/версия/время → свидетельство → оригинал`; trust/authority/freshness/scope/access (R17); ступени поиска от дешёвого точного к дорогому; протокол benchmark-а (§16.2). Не копировать: Task/Plan/Idea lifecycle, claim ledger, session bootstrap, LLM Wiki синтез — только `memory-llm-wiki.after.md` |

---

## 4. Пошаговый план MVP (Этап 0 → Этап 7)

Каждый этап: **цель → шаги → deliverables (файлы) → тесты → gate**. Следующий этап не начинается, пока не пройден gate предыдущего. Оценка объёма — в задачах, не в датах (даты ставятся после Этапа 0).

### Этап 0 — Discovery: проверить проблему и сузить scope (до производственной реализации)

**Цель:** подтвердить, что source-native QA + typed records реально экономят время на реальных папках, и выбрать один vertical slice. Без этого — не писать полный CLI.

**Шаги:**
1. Собрать 3–5 реальных/обезличенных папок (Markdown + CSV/JSON рядом, или только Markdown, или только записи). Записать повторяющиеся задачи владельцев.
2. Провести 8–12 problem interviews: как добавляют материал, исправляют битые ссылки/схемы, сколько раз в неделю теряют время, чем довольны в Obsidian/QMD/Open Knowledge/OpenKB. Записать конкретные инциденты, не абстрактные оценки идеи.
3. Для каждого набора собрать 20–30 реальных поисковых вопросов + отдельно набор намеренно внесённых дефектов: missing links, wrong front matter, schema errors, duplicate IDs/headers, malformed CSV/JSON, stale/missing metadata. Согласовать с владельцем правильный источник и ожидаемую location.
4. Сделать сравнительный benchmark по одинаковым задачам: `rg`/ручной workflow (baseline); Obsidian search/CLI (Markdown); QMD (retrieval); Open Knowledge CLI (Markdown validation/context/eval); OpenKB (добавление/компиляция/Obsidian-view + `lint`); `todoc`-прототип (выбранная cross-format боль). Khoj/AnythingLLM — только если target workflow включает natural-language chat/RAG. Отделять self-reported результаты авторов от независимого теста.
5. Измерить: top-k source/section recall + reciprocal rank; время выполнения задачи; размер context (bytes + tokens при заданном tokenizer); доля найденных issues с верной location; precision полезных fixes, false-positive rate, доля принятых предложений; clean relocation + время cold rebuild; латентность на зафиксированном корпусе.
6. Выбрать **один** проверяемый vertical slice (см. §5) и зафиксировать baseline. Если выбран memory/domain профиль — закрыть отдельный scope gate (§9, `memory-llm-wiki.after.md`) до проектирования публичного API.

**Deliverables:** `plan/discovery-report.md` (или раздел в этом файле): персона, повторяющиеся проблемы, выбранный slice, baseline-метрики, go/no-go решение.

**Gate (предварительные пороги, уточнить после baseline):** (a) 100% synthetic defects с точными locations; (b) ≥90% actionable diagnostics признаны реальными проблемами; (c) retrieval не хуже лучшего baseline в бюджете вывода; (d) перенос root + удаление cache/index без ручного фикса; (e) ≥3 pilot users возвращаются в течение 2 недель с повторяющейся выгодой.

**Stop criteria:** если Markdown-only поиск закрывается QMD/Obsidian/Open Knowledge и cross-format checks не оказываются регулярной болью — **остановить широкий scope**, оставить тонкий validator/adapter/Skill. Если location-aware diagnosis/repair реально экономит время — развивать эту узкую часть первой.

### Этап 0.5 — Design contracts (только после gate)

**Цель:** зафиксировать решения, влияющие на layout/API, до кода.

**Шаги:**
1. Утвердить: минимальную версию Python, Click/Typer, `.todoc` + relative-path contract, document vs entity/record boundary, ID/file policy, Obsidian/OKF profiles, `harness` alias, generated docs location, diagnostic/fix/query contract, search backend choice, write permission model, vertical-slice fixtures.
2. Зафиксировать JSON Schemas для `dataset.json`, rule files, folder/doc/entity/relation/query descriptors, templates, identity-map, local `.todoc.json` (черновики, не финальные).
3. Зафиксировать CLI-контракт (§8 конституции): команды, флаги, envelope, exit codes, `next_actions` как `argv`. Одновременно зафиксировать **MCP-готовность контрактов** (без реализации MCP): стабильные use cases (`SearchObjects`, `ReadProjection`, `QueryRecords`, `AggregateRecords`, `ValidateDataset`, `CreateRecord` preview), отображение envelope → `structuredContent`/`TextContent`, `next_actions` argv → tool hints, stateless-модель (явный `dataset_id`/`id`/`cursor`, без сессионного состояния), URI-схема resources (`todoc://<dataset_id>/doc/<id>` и т.д., `mcp-adapter.after.md` §5.4). Это не реализация MCP, а условие, чтобы MCP вставился без переписывания ядра (E8/E10).
4. Зафиксировать diagnostic codes для поддержанных классов ошибок (CSV/JSON/Markdown/records/relations/queries). Для MCP-готовности: стабильные `finding_id` + `code`/`severity`/`location`/`evidence`, чтобы `get_finding`/`run_diagnostics` (M19) мапились без смены контракта.
5. Ответить на Q1–Q13 конституции (§14) для тех вопросов, которые влияют на layout/API; остальные — по defaults (§3.1). Дополнительно для MCP-готовности: редакция MCP (2026-07-28), транспорт v1 (stdio), целевые клиенты/SDK, каталог tools v1 (`<20` эвристика, M15) — зафиксировать как **черновик gate** в `mcp-adapter.after.md` Шаг 1, не как реализацию.

**Deliverables:** ADR/решения в `plan.md` или design note + черновики schemas + fixtures для vertical slice.

**Gate:** код после подтверждения layout/API-вопросов.

### Этап 1 — Устанавливаемый скелет Skill/CLI

**Цель:** минимальный устанавливаемый пакет, который запускается вне repo.

**Шаги:**
1. Создать `SKILL.md` (front matter `name: todoc`, короткое тело, прямые links на `references/*.md`), `references/*.md` (заглушки), `pyproject.toml` (`project.scripts`, зависимости, tooling), `src/todoc/` (`__init__.py`, `__main__.py`, `cli.py` с Click root, `domain/`, `application/`, `ports/`, `adapters/`, `typing_system/`, `output/` — пустые модули с интерфейсами), `tests/` (unit/contract/integration/cli/fixtures).
2. Реализовать `todoc --help`, `todoc --version`, `todoc init --root` (только создаёт пустой `.todoc/dataset.json` шаблон + валидирует путь; не сканирует root автоматически).
3. Настроить tooling: pytest, Ruff lint/format, mypy или Pyright, build/install check. Зафиксировать версии.
4. Добавить тонкий `scripts/todoc` launcher только если целевой агент может запускать только bundled scripts (только вызывает пакет).

**Deliverables:** устанавливаемый wheel, валидный Skill front matter, CLI help/exit codes.

**Тесты:** wheel устанавливается в чистый environment и запускается вне checkout; нет imports из CWD/data root; `CliRunner`/subprocess: `--help`, JSON stdout-only, stderr, exit codes.

**Gate:** установленный wheel запускается вне repo; skill front matter валиден.

### Этап 2 — Data schema и portable `init`

**Цель:** версионированные JSON-контракты + переносимый `init`.

**Шаги:**
1. Закрепить JSON Schema 2020-12 для `dataset.json`, `directory-rules.json`, `document-rules.json`, `dir_types/*/type.json`, `doc_types/*/type.json`, `entity_types/*/type.json`, `relation_types/*/type.json`, `queries/*.json`, `templates/`, `identities.json`, local `.todoc.json`. Все файлы — с `schema_version`.
2. Реализовать `todoc init --root` полностью: создаёт `.todoc/` + каталоги типов/rules/templates/queries + `dataset.json` + системные schemas; не создаёт Skill/code; не сканирует root без команды.
3. Реализовать `todoc check-config` (валидация конфигов до использования) + `todoc types list/show/guide` (каталог + generated-справка; per-dataset guide — stdout или явный `--out` в `.todoc/generated/`).
4. Реализовать config loader с containment (resolve от зафиксированной базы, проверка на выход за root, без сети для `$ref`).

**Deliverables:** schemas + `init`/`check-config`/`types` команды + `assets/data-root-template/`.

**Тесты:** schema positive/negative; relative paths в configs; root создаётся в temp, перемещается целиком и снова открывается; неизвестные поля/версии → diagnostic + предложение migrate/check; дубликаты имён/ID → ошибка.

**Gate:** schema validation есть; data-root можно создать, переместить и снова открыть.

### Этап 3 — Scanner и resolver

**Цель:** детерминированный обход + объяснимое разрешение типов.

**Шаги:**
1. Реализовать recursive scan (`os.scandir` или `pathlib`): сортировка entries, hard-excludes (`.todoc/`, VCS/build/cache, секреты по конфигу), не следовать symlinks/junctions по умолчанию, не выходить за канонический root, не читать бинарные файлы как текст (opaque assets: path/size/optional hash), регистрировать `unsupported`/`ignored`/`parse_error`/`permission_denied`.
2. Реализовать resolver: explicit config → nearest config (field-wise merge вниз) → dataset rules (exact path → exact basename → glob, `priority` + literal-segments tie-break; равный результат разных правил — error) → reserved-name defaults → document type (front matter/identity → explicit rule → единственный `default_doc_type` папки → `unknown`). Format никогда не выбирает смысл.
3. Реализовать грамматику масок v1 (`*`/`?` не пересекают `/`; `**` как отдельный segment = ноль или больше сегментов; exact basename — отдельный matcher; без `!`; исключённый каталог не обходится) + тесты zero-depth/nested для `**/name/`.
4. Реализовать reserved defaults: `architecture/`, `constitution/`, `harness/`, `glossary/`, `plan/` (как `**/plan/`), `.research/`. Каноническое `harness`; `harnes` — только alias.
5. Реализовать `<subfolder>/.todoc.json` (декларативные параметры, по JSON Schema; не может включать `python`/`shell`/`import`/`exec`/URL и не может расширять доступ сверх root policy).
6. Реализовать `todoc explain-path PATH` (выбранная папка/документ, `format`, `dir_type`, `doc_type`, matched rule, inherited fields, исключения, конфликты) + `todoc scan` (детерминированный обход без записи индексов или с записью черновика — зафиксировать в ADR).
7. Реализовать nested-root policy (`inherit`/`separate`/`stop`); двойная индексация одного файла запрещена или диагностируется.

**Deliverables:** scanner + resolver + `explain-path`/`scan` + fixtures (`.research`, `plan/` на разной глубине, architecture/constitution/harness/glossary, glossary-документы вне `glossary/`, user entity types).

**Тесты:** все приоритеты; двусмысленность → diagnostic; symlink/path traversal не выходит за root; `.todoc/` и `.todoc.json` не индексируются как content; deterministic sorting; permissions; broken links; path separators/case collisions.

**Gate:** fixtures подтверждают приоритеты; symlink/traversal безопасны.

### Этап 4 — Три format adapters и validation

**Цель:** CSV/JSON/Markdown readers + schema/entity/relation validator + error envelope.

**Шаги:**
1. Реализовать `FormatReader` Protocol + три drivers (E1):
   - **Markdown:** `markdown-it-py` (CommonMark) + `obsidian-compatible` profile (YAML front matter, relative links, headings/anchors, subset wikilinks/embeds). Headings из tokens, не regex. Outline: `title`/`level`/line/span/anchor/parent. Outgoing links/backlinks; unresolved/ambiguous → exact location. Неизвестный синтаксис сохраняется как текст.
   - **CSV:** explicit encoding/dialect/delimiter/quote/header policy из конфига; `newline=''`; rows с номером строки; заголовки; truncation. Cell — строка по умолчанию.
   - **JSON:** строгий, UTF-8 policy, size/depth limits, reject duplicate keys, JSON Pointer/locations. Для records — извлечение `record_id`/`entity_type`/relations.
2. Реализовать `Validator` (E3): syntax/status → schema (JSON Schema 2020-12, локальные `$ref` только внутри корня, без сети) → record field/units/date normalization → required relation targets/cardinality → deterministic business checks → security/write policy. `ValidationReport` с `status`, parser/schema/type version, path, digest, issues.
3. Реализовать `Diagnostic` contract: стабильный `{id, code, severity, message, location, evidence}` + optional `suggested_fixes[]` (kind, patch/value, rationale, `autofixable`, confidence, `requires_review`). Location: CSV row+column (+ physical line range), JSON Pointer + line/column, Markdown line/column + heading/anchor.
4. Реализовать `FormatWriter` Protocol (E1) + atomic write (E9: temp + flush/close + validate + replace/create, сохранение прав/encoding/newline). Existing writes — за feature flag до safety gate (Этап 6).
5. Реализовать `todoc validate --all` (подробный файл/правило/location отчёт) + `todoc check` (короткий health summary + общие diagnostics). Human и JSON output — одни и те же machine facts.
6. Реализовать Obsidian-совместимость (базовая): `.md` + YAML + relative links + вложения; неизвестные YAML-поля round-trip не теряются; `.obsidian/` исключается и не редактируется; vault не вкладывается в vault.

**Deliverables:** три drivers + validator + `validate`/`check` + diagnostic codes + fixtures (valid/invalid для каждого формата).

**Тесты (contract, одинаковые для всех drivers):** diagnostics, source locations, limits, encoding, deterministic behavior. CSV: comma/semicolon/tab, quoted separators/newline, BOM, duplicate headers, missing header, wrong width, null/empty, conversion boundaries, formula-injection policy. JSON: invalid syntax, duplicate keys, large/deep, pointer escaping, invalid `$ref`/schema, unsupported keywords. Markdown: ATX/Setext, skipped levels, duplicate names, code fences с `#`, front matter malformed/large, tables/extensions, broken anchors/links, YAML properties, relative attachments, wikilinks/embeds ambiguous/unresolved, `glossary-entry` вне `glossary/`. Diagnostic contracts: stable codes, exact ranges, evidence, severity, 0/1/multiple fixes, false positives на valid fixtures. Writers: round-trip fixtures; неизвестные поля/comments/formatting не пропадают без предупреждения.

**Gate:** driver contract tests проходят; parser versions/options указаны; недопустимый файл/record/query не объявляется valid и не пропадает без diagnostic.

### Этап 5 — Portable registry/cache + bounded search/read + records query/aggregate

**Цель:** атомарные индексы + прогрессивное чтение + безопасные запросы.

**Шаги:**
1. Реализовать registry generations (E6): `folders.json`/`documents.json`/`records.json`/`relations.json`/`diagnostics.json` с `schema_version`, `dataset_id`, `generation_id`, timestamp, `config_digest`, root-relative paths, hashes, parser/type versions. Атомарная публикация: temp generation → validate (все JSON/schema/hash refs + полнота обхода) → rename → atomic `replace` `CURRENT.json`. При ошибке старое поколение остаётся `CURRENT`; incomplete не выдаётся как полный. Dataset-level lock для параллельных writers.
2. Реализовать identity-map (`identities.json`): stable document IDs из front matter (`id`) или versioned map; path — location, не identity. Для JSON records — явные `record_id`/`entity_type` в теле файла.
3. Реализовать per-doc JSON parse cache (E6): cache key — `dataset_id` + path + content hash + parser/version/options/dialect + type/relation/query schema digest + relation target generation + validator/query engine version. `mtime_ns+size` — только fast-path. JSON shards (не один гигантский `cache.json`). Повреждённый кэш → диагностировать и пересоздать.
4. Реализовать `todoc index status/rebuild` + `todoc --root … --root … check/scan` (multi-root изоляция: отдельные configs/IDs, каждый результат с `dataset_id`; объединённый поиск — явный режим) + `todoc doctor` (read-only диагностика окружения: стабильные ID/категория/уровень проверок, `--check`/`--scope`, по умолчанию ничего не исправляет; `--fix` — отдельный режим с dry-run; см. §13 F1, §15.1) + `todoc docs tree` (оглавление как derived компактный индекс) + `todoc status` (быстрый снимок состояния, отличная от `doctor`). Корневой `todoc` без аргументов показывает короткое оглавление (discovery).
5. Выбрать deterministic lexical/metadata backend через benchmark (in-process FTS5 или минимальная альтернатива): проверка доступности FTS5 в builds, размера/латентности, переносимости, сравнение с QMD на frozen queries. Сохранить порты E4/E5 (retriever/ranker/reranker/renderer), но не делать embeddings/graph DB обязательными.
6. Реализовать `docs search/read` (E4/E5): progressive disclosure (counts/outline → snippets → fragment) как многоуровневый отчёт (0 итог/счётчики → 1 оглавление групп/путей → 2 выбранная группа/ID/поддерево → 3 подробная запись/исходный лог) с селекторами `--section`/`--id`/`--path`/`--max-depth`/`--fields`/`--limit`/`--cursor`/`--report-file` (см. §13 F2, §15.1); фильтры `format`/`doc_type`/`dir_type`/project/scope/path mask/metadata/status/limit + `--within <path|section-id>` (охватывает подкаталог/раздел с дочерними заголовками по умолчанию; только сам узел — явный режим); Markdown `--section/--anchor/--line-range`; JSON `--pointer`/projection; CSV `--columns/--rows`/bounded `--where` (без `eval`/SQL); `--budget`/`--limit`/cursor/`truncated`/hash/provenance + `matched_count`/`total`/`returned` (не выдавать top-N за полный результат) + `path` + `heading_path` (breadcrumb) + стабильный `id` для следующего `read` + `snippet_truncated` (если лимит обрезал предложение). Группировка многочисленных ошибок: итоги по severity/category, порог показа (эвристика 5 findings, калибруется), `total`/`shown`/`truncated`/cursor/путь к деталям; группировать только общую причину. Прогресс/время/отмена для длинных scan/index rebuild (не портят результат); framing потоков: `--output json` — один валидный JSON на вызов, `--report-file` для больших отчётов; `--details`/`--fields` для раскрытия деталей; повторный `--apply` с тем же patch — no-op (идемпотентность). Links/backlinks — для навигации, не deep traversal по умолчанию.
7. Реализовать `records list/query/aggregate/read` + `relations graph` (E7): safe declarative filter/project/aggregate над schema-known полями и relation traversal; allowlisted JSON AST; запрещены Python/SQL/`eval`/import/shell/network. Агрегация возвращает metric definition, единицы, формулу, timezone/date policy, входящие IDs/paths/pointers, статус полноты. `relations graph --from … --type … --depth … --limit …` — явные typed edges + краткие neighbours; cross-dataset refs запрещены.
8. Реализовать JSON envelope + `next_actions` (E10): `{schema_version, ok, data, diagnostics, next_actions}`; `next_actions` — только `argv`-массив + purpose (не auto-execution); large listing — `total`/`items`/`truncated`/`cursor`; `--output json`: stdout — только JSON, progress/help — stderr; stable exit codes. **MCP-готовность (без реализации MCP):** envelope спроектирован так, чтобы мапился на MCP `structuredContent` + `TextContent` (M9) без смены семантики: `data` → `structuredContent`, краткий summary → `TextContent`, `next_actions` argv → tool hints (M25), `truncated`/`cursor` → прикладной opaque cursor (M11), `issues_found` → успешный result, не `isError` (M20). См. §16, `mcp-adapter.after.md` §7.

**Deliverables:** generations + cache + lexical backend + `index`/`docs search/read`/`records …`/`relations graph` + envelope.

**Тесты:** перескан без изменений воспроизводим; изменение config/parser/content/type/relation/query сбрасывает правильный cache; повреждённый/incomplete generation не подменяет предыдущий полный; большие результаты paginated; reference aggregate возвращает units/formula/provenance; retrieval benchmark на frozen queries (Recall@k/MRR/nDCG, попадание source section, bytes/tokens, latency) не хуже target baseline; два независимых DATA_ROOT с одноимёнными типами/ID не пересекаются; cross-dataset relations отклоняются; удаление всех derived index/cache → cold-rebuild из перемещённого root без absolute paths.

**Gate:** перескан воспроизводим; cache инвалидируется правильно; retrieval benchmark пройден; reference aggregate корректен.

### Этап 6 — Review-first diagnostics и ограниченные fixes

**Цель:** structured issues + preview/diff, затем безопасный `--apply` только для проверенных операций.

**Шаги:**
1. Реализовать `todoc fix --diagnostic <id> --preview` (preview/diff, ничего не применяет) для поддержанных правил. Каждое предложение — `suggested_fixes[]` с rationale/evidence; неоднозначное исправление не применяется автоматически.
2. Реализовать `todoc fix --diagnostic <id> --if-hash sha256:… --apply` + `todoc docs edit --id … --patch-file … [--if-hash …] --apply`: проверка `expected_hash`, temp + atomic replace/create, повторный parse + schema + type + relation validation, обновление индекса. Concurrent update → конфликт + перечитывание. Невалидная запись оставляет оригинал нетронутым.
3. Реализовать `todoc docs new --title … --dir … --template …` (новый Markdown draft в выбранной/типизированной папке) + `todoc records create --type … --input-file … --preview/--apply` (create-only новый JSON record по validated entity type/path template: проверка отсутствия target/`record_id` collision, required fields, units/date normalization, relation existence/type/cardinality, naming/template constraints; неоднозначное обязательное значение/единица/target → structured clarification error, не запись).
4. Реализовать `WritePlan` (E9): target selector/template, minimal patch/new content, expected/new hash, preview diff, основание/уверенность, writer, validations. Default — dry-run/preview. Advisory/LLM suggestion никогда не получает auto-apply. Если драйвер не умеет без потерь — `unsupported_write`, не fallback к полной перезаписи.
5. Зафиксировать write capabilities: разрешены `docs new` + `records create` (новый JSON); существующие CSV/JSON/Markdown — review-first patch, gated later (многофайловые bundle-транзакции — только в `memory-llm-wiki.after.md`).

**Deliverables:** `fix`/`docs new`/`docs edit`/`records create` + `WritePlan` + safety gate.

**Тесты:** каждый supported issue — stable code + точное местоположение; no-op не меняет hash/байты; record create соблюдает no-overwrite/path-template/relation validation; неоднозначный fix/недостающие units/target не auto-apply; concurrent update обнаруживается; невалидная запись оставляет оригинал нетронутым; реальные пользователи считают suggestions/capture полезными (критерии Этапа 0).

**Gate:** safety gate пройден (preview/hash/post-validation для всех заявленных auto-fix правил).

### Этап 7 — Obsidian/profile, Skill и capture workflow

**Цель:** минимальный Obsidian-compatible profile + короткий Skill + type-directed capture.

**Шаги:**
1. Проверить минимальный Obsidian-compatible Markdown profile + типовые vault link patterns (обычные Markdown links + отдельно используемый subset wikilinks/embeds). Папка открывается как vault без runtime plugin; обещанный subset проходит smoke tests в реальном Obsidian (compatibility smoke test, не требование устанавливать Obsidian в CI каждого пользователя).
2. Заполнить короткий parent `SKILL.md` (выбор `--root`, `check/validate`, budgeted search/query, bounded read, capture: уточнение обязательных полей/targets, preview/create, preview/diff + `expected_hash` + повторная `validate` + явный `--apply`) + дочерние справочники `references/*.md` (включая `entities-relations-and-queries.md`, `ingest-query-lint.md` с процедурами ingest/query/write/lint, `page-templates.md` с шаблонами страниц, `formats-*.md` с forced-learning правилами) + общий generated `type-system.generated.md` + команду `types guide` + trusted record-capture workflow reference (whitelisted `workflow_id`; отсутствующий/неизвестный workflow — warning, не блок generic CLI). **Forced learning (MUST):** перед обработкой формата Skill обязан прочитать соответствующий `references/formats-*.md` (аналог ConardLi «сначала прочитай `pdf_reading.md`/`excel_reading.md`»); без чтения — обработка запрещена. **Иерархическая навигация:** generated `index.md` (оглавление root) + per-dir `data_structure.md`-аналог (用途/файлы/диапазон, derived из `folders.json`/`documents.json`, не ручной source) + append-only `log.md` (операции, derived из generations/diagnostics) — только как derived навигация/аудит, не как source of truth (см. §13 F6, §14 R12).
3. Реализовать type-directed capture end-to-end (FR-6): Skill выбирает `entity_type`, показывает поля/шаблон, уточняет только отсутствующие обязательные данные, разрешает relation targets, вычисляет путь/имя из шаблона, просит подтверждение для неоднозначного маршрута; CLI валидирует и создаёт новый файл; перечитывание + индекс.
4. Реализовать `ui`/`agent_instructions` metadata как неисполняемые данные (FR-3.6): type descriptors допускают `ui` (цвет/иконка/вид) и `agent_instructions` (структура разделов, правила извлечения, capture-подсказки) без поломки schema validation. Skill/UI-адаптер читает их как данные, не как код/prompt authority.
5. Проверить Skill: все `SKILL.md` через validator; relative file refs и links на существование (включая `entities-relations-and-queries.md`); generated файлы с marker/version/reproducible diff. Parent Skill пользуется явным `--root`, читает только выбранную проекцию/fragment, не запускает действия автоматически.

**Deliverables:** Obsidian profile + Skill + references + `types guide` + capture workflow.

**Тесты:** vault smoke test; Skill validator; reference e2e slice (см. §5); agent evaluation (см. §6).

**Gate:** папка открывается как vault без plugin; Skill уточняет обязательные поля/targets и вызывает CLI preview/create; references прямые/валидны/кратки.

### Этап 7.5 — v1-совместимость и CI (после MVP, до `.after.md`)

**Цель:** interchange и CI без расширения scope.

**Шаги:**
1. Реализовать OKF v0.2 profile (опциональный): `validate`/`lint` для OKF bundles, сохранение неизвестных YAML-полей, без требования OKF для обычных заметок. Референс: okfcli/okf, Open Knowledge.
2. Реализовать CI-gate: `validate --strict` (warnings → отказ), SARIF output для `validate`/`lint` (референс okf), `eval` для retrieval (референс Open Knowledge: MRR/Recall@k/nDCG@k).
3. Реализовать `link` external fetch policy как opt-in (FR-6.3, C51): allowlisted fetch + извлечение title/описания/фактов/тегов + preview. Без скрытой сети по умолчанию (P12).

**Gate:** OKF profile не ломает обычные заметки; CI-gate работает на fixtures; fetch — только opt-in с consent.

---

## 5. Vertical slice (один сквозной сценарий до большой реализации)

Выбрать **один** на Этапе 0 и довести end-to-end до Этапа 7. Остальные сценарии — после gate.

| Slice | Сценарий | Что доказывает |
|---|---|---|
| **A. Source QA/search** | Смешанные документы: `check/validate → search → read` с точными locations | Ниша source-native QA vs QMD/Open Knowledge |
| **B. Typed records** | `link` capture **или** `research → product → plan` **или** `workout` capture → aggregate | Главная гипотеза (типы + workflows + query) |
| **C. Memory profile** | Task/Plan/Idea lifecycle + session continuity | Отдельный scope (см. `memory-llm-wiki.after.md`), не MVP |
| **D. LLM Wiki** | `raw/ → wiki/` synthesis | Отдельный scope (см. `memory-llm-wiki.after.md`), не MVP |

**Рекомендация:** начать с **B** (`link` capture с выжимкой сайта **или** `research` по конкурентам → typed `product` → `plan`), потому что он покрывает S1+S2+S3+S6+S7 одним сценарием и проверяет типы/workflows/связи/поиск. Если discovery покажет, что главная боль — битые ссылки/схемы в смешанных папках, выбрать **A**.

**Reference e2e (пример B):** пользователь/агент просит «сохрани тренировку» (или «сохрани ссылку») → Skill уточняет обязательные поля → CLI создаёт JSON record по path template → aggregate возвращает ожидаемый результат с units/formula/provenance и без двойного счёта compound упражнений при выбранной политике. Fixtures: `person`, `workout`/`link`/`research`/`product`/`plan` типы, typed relations, saved queries.

---

## 6. Тестирование и качество (на каждом этапе)

| Уровень | Что покрывает | Инструменты/критерии |
|---|---|---|
| **Unit + contract** | Resolver (приоритеты, tie, unknown type, reserved names, `harness`/alias); scanner (nested roots, hard exclude, deterministic sorting, permissions, broken links, symlink escape/cycle, separators/case, traversal); format drivers (общие contract tests); entity/relation types (missing fields/units/dates, unknown units, invalid targets, cardinality, ID collision, path template traversal/overwrite, ambiguous/dangling); query/aggregate (safe grammar, unknown field/metric, unit mismatch, timezone/period, multi-muscle, pagination, limits, provenance); Markdown (ATX/Setext, skipped levels, duplicates, fences, front matter, tables, broken anchors/links, wikilinks/embeds, `glossary-entry` вне папки); diagnostics (stable codes, ranges, evidence, severity, 0/1/multiple fixes, false positives); writers (atomic create no-overwrite, minimal patch, preserved bytes, `expected_hash` conflict, disk error, revalidation); registry/cache (invalidate, add/delete/rename, corruption, crash before swap, concurrent scan/read, cold rebuild) | pytest, coverage по critical modules, Ruff, mypy/Pyright, fixture validation. Зафиксировать версии tooling/dependencies |
| **Integration / Skill / packaging** | Fixture project (`.research`, `plan/` на разной глубине, architecture/constitution/harness/glossary, glossary вне `glossary/`, user entity types, typed relations, saved queries); relocate root в другой абсолютный путь (+ другая ОС если заявлено) + перескан/поиск/query; два независимых DATA_ROOT с одноимёнными типами/ID (изоляция, cross-dataset отклоняется); reference e2e slice (§5); `CliRunner`/subprocess (`--help`, JSON stdout-only, stderr, exit codes, pagination, `next_actions`); wheel в чистом environment вне checkout; Obsidian smoke test (vault, `.md`/attachments, links/headings/backlinks для обещанного subset); Skill validator + relative refs; generated marker/version/diff | CI: pytest + coverage + Ruff + mypy/Pyright + build/install check + fixture validation. Без plugin auto-discovery в тестах без причины |
| **Agent evaluation** | На зафиксированном corpus + held-out задачах: выбор `--root`/workflow, не принятие prompt-injected instructions; различение capture vs search vs query/aggregate, не путать format/doc_type/entity_type; чтение только нужного bounded projection/fragment, замечание `truncated`; provenance path/ID/hash/status/units; уточнение обязательных полей/единиц/targets при capture, не додумывание; abstain при invalid/stale/ambiguous/unknown-metric; минимальный корректный new record/patch без изменения unrelated data; лишние действия/неправильные selections/избыточные чтения; полностью локально/детерминированно без скрытых model/network calls по умолчанию | Сравнить с baseline `rg` + ручное чтение, Obsidian native search, QMD, Open Knowledge CLI. На самой слабой поддерживаемой модели + целевом budget: model/harness (или `none`), версии Skill/config/parser, N, split, scoring, bytes/tokens, latency, все failure cases. Не обещать фиксированное снижение затрат/безошибочность. Протокол benchmark-а — §16.2 (guide MD-KB §XI): классы задач, метрики retrieval/answer/safety/editing/operations, ablations, blind review |
| **MCP evaluation (когда будет MCP)** | Held-out многошаговые задачи с проверяемым outcome и допустимыми альтернативами (не только совпадение JSON); самая слабая модель + тесный бюджет; реальные клиенты/SDK/версии протокола; empty/large/partial results, cursor, приватный кэш, expired handle, prompt injection, timeout, повтор side effect, конкурентные вызовы; для diagnostics/tree — 0/1/около порога/много findings, `isError` vs `issues_found`, truncation/cursor, отсутствие side effect; сравнение summary→ветвь и с/без `next_actions` по task success/calls/latency/tokens/cache hit-miss | Метрики research §11.3: результат, использование инструментов, контекст/стоимость, скорость, надёжность, безопасность. См. `mcp-adapter.after.md` §15. В MVP не реализуется; в MVP тестируется только MCP-готовность контрактов (envelope мапится на `structuredContent` без смены семантики) |

**Только если выбран отдельный memory-profile:** добавить agent-behavior cases для capture/triage, поиска существующей Task/Idea/Project перед дубликатом, точных status/due/owner queries, связей, завершения/перевода состояния, продвижения идеи в проект, session bootstrap, безопасного отказа/abstain. Не засчитывать правильный ответ из model memory без чтения root.

---

## 7. Definition of Done (MVP)

Релиз пригоден для пилота, если **все** пункты выполнены, пройден product gate (Этап 0) и выбран product scope:

- [ ] `/todoc` содержит валидный родительский Skill и installable package; данные не лежат в package, Skill не лежит в DATA_ROOT.
- [ ] В release description ясно сказано, что `todoc` — проверяемая гипотеза file-native typed knowledge substrate, не доказанно уникальный продукт и не automatic memory magic; `doc_type`/`entity_type` сами по себе не создают полноценный Task/Plan/Idea/workout manager без явных schemas/queries/workflows.
- [ ] `todoc init --root <PATH>` создаёт переносимые JSON config/type/relation/query templates; scan/check не подразумевают фиксированный путь или неявный CWD.
- [ ] Повторяемый `--root` принимает несколько переносимых roots; scan/check/validate/query изолируют и помечают отчёт каждого DATA_ROOT; read/fix/create всегда однозначно привязаны к dataset.
- [ ] Root config, folder-local `.todoc.json`, relative masks, tie/error policy и reserved basenames задокументированы и протестированы, включая `**/plan/` и `glossary-entry` вне специальной папки.
- [ ] `harness` spelling зафиксирован; `harnes` — только при явной конфигурации/alias.
- [ ] `format`/`doc_type`/`dir_type`/`entity_type`/`relation_type` раздельны; CSV/JSON/Markdown readers проходят contract tests; config/types/queries/templates в DATA_ROOT не загружают произвольный код/prompt; type descriptors допускают необязательные `ui` и `agent_instructions` как неисполняемые данные.
- [ ] Для поддержанных классов ошибок есть stable diagnostic codes, severity и точные locations с unit fixtures.
- [ ] Suggestion отделён от факта (rationale/evidence); неоднозначное исправление не применяется автоматически. Для заявленных auto-fix правил — preview, `expected_hash`, post-validation, тест сохранности исходника. Существующие CSV/JSON/Markdown — review-first; create-only новые Markdown/JSON records проходят validation и no-overwrite.
- [ ] Reference record slice работает end-to-end (Skill уточняет обязательные поля, CLI создаёт новый JSON record по template/path и валидирует schema/relations, aggregate возвращает проверенный результат с units/formula/provenance).
- [ ] Markdown headings/links/backlinks дают outline через parser; обещанный subset Obsidian wikilinks/attachments проходит fixture и smoke-test в Obsidian; никаких обязательных Obsidian runtime/plugin.
- [ ] DATA_ROOT перемещается в другой путь; после удаления всего derived index/cache он повторно открывается и пересобирает индекс без ручного исправления абсолютных путей.
- [ ] Folder/document/record/relation index/cache — versioned, derived, rebuildable; пути root-relative; datasets/IDs не смешиваются; атомарная публикация и incomplete state протестированы.
- [ ] CLI поддерживает constrained docs search/read и records query/aggregate, bounded projections, context/byte budget, pagination, JSON envelope, `truncated`/cursor и `next_actions` как массив `argv`; retrieval качество сравнено с заранее объявленным baseline на held-out запросах; внешние embeddings/vector/graph/rerankers не обязательны для MVP.
- [ ] `check`/`search` работают локально и без скрытого сетевого/LLM-вызова; version/parser/config/tokenizer (если есть) видны в отчёте.
- [ ] Skill resources и executable plugins — только из trusted installation; dataset documents/config values не являются инструкциями/permissions.
- [ ] Tests запускаются на temporary roots, разных путях/ОС edge cases, установленном wheel; оценка контекста/агентского workflow использует зафиксированный benchmark и описывает failure cases.
- [ ] MCP-готовность (без реализации MCP): use cases стабильны и мапятся на MCP tools/resources без смены семантики; envelope → `structuredContent`/`TextContent`, `next_actions` argv → tool hints, `issues_found` → успешный result (не `isError`); stateless (явный `dataset_id`/`id`/`cursor`); URI-схема resources зафиксирована черновиком. См. §16, `mcp-adapter.after.md`.

---

## 8. Что НЕ делаем сейчас (явный defer)

| Не делаем | Куда вынесено | Почему не сейчас |
|---|---|---|
| Embeddings, vector search, hybrid fusion, reranking, external vector/graph adapters | `search-embeddings-vector.after.md` | Нужен benchmark/privacy gate; lexical закрывает MVP; порты E4/E5 уже заложены |
| Веб-интерфейс, static publishing, visualize | `web-ui.after.md` | Нужны стабильные JSON-контракты CLI; веб — отдельный adapter |
| Task/Plan/Idea lifecycle, session memory, LLM Wiki synthesis, claim ledger, tag registry, daily/calendar, boards, bundle-транзакции | `memory-llm-wiki.after.md` | Отдельный scope с собственными схемами; `doc_type` ≠ task manager |
| MCP server (tools/resources/prompts) | `mcp-adapter.after.md` | CLI — первичный контракт; MCP — тонкий транспорт после стабилизации CLI |
| Плагины, YAML/XLSX/PDF/SQLite, importers, watch mode, AI enrichment, scheduled agents | `plugins-formats-import.after.md` | Только по подтверждённой боли; без use case/privacy/benchmark — не вводить |
| Cloud sync, multi-user/ACL, export HTML/slides, backup/restore как фича | `sync-collab-export.after.md` | Нужны single-writer/conflict policy; Git-friendly уже есть в MVP |

---

## 9. Карта `.after.md` файлов (перспективы)

| Файл | Возможности (Cxx) | Требования (FR) | Входной gate |
|---|---|---|---|
| `search-embeddings-vector.after.md` | C11, C12 | FR-5.9, §5.3 | Lexical недостаточен на benchmark; privacy/egress review; fallback доказан |
| `web-ui.after.md` | C30, C31, C56 | FR-9, S10, S12 | CLI стабилен; JSON-контракты для нужных операций есть; UI добавляет ценность |
| `memory-llm-wiki.after.md` | C25–C28, C47–C49 | FR-6.10 | Отдельный scope gate: schemas/lifecycle/queries/acceptance-тесты утверждены |
| `mcp-adapter.after.md` | C21 | FR-10, S11 | CLI стабилен; use cases + envelope мапятся на MCP без смены семантики (§16); редакция 2026-07-28 + транспорт (stdio v1) + целевые клиенты/SDK зафиксированы; каталог tools v1 (`<20` эвристика, M15) + input/output schemas + URI resources + кэш/лимиты зафиксированы; read-only default + consent на write; eval на слабейшей модели пройден |
| `plugins-formats-import.after.md` | C34, C35, C41, C43, C51 | FR-4.5, FR-12 | Конкретная боль + тестовый набор/план безопасности |
| `sync-collab-export.after.md` | C32 (cloud), C33, C50 | FR-12 | Single-writer/conflict policy; export-форматы выбраны |

Каждый `.after.md` содержит: что/зачем, почему не сейчас, архитектурные хуки в MVP, пошаговый план внедрения, данные/миграции, безопасность/приватность, benchmark/gate, что НЕ делать.

---

## 10. Риски и митигации

| Риск | Митигация (этап) |
|---|---|
| Generic framework без сценария | Этап 0 gate + один vertical slice (§5); stop criteria |
| Схема валидирует форму, но не смысл | Units/timezone/formula в type metadata + versioned query contract; unknown → abstain/clarify (Этап 4–5) |
| Skill/agent writes слишком доверенные | Skill — диалог; CLI — authority; allowlist, containment, no-overwrite, validator (Этап 6–7) |
| Links теряются при rename/delete, graph дрейфует | Stable IDs, explicit typed refs, dangling diagnostics, пересоздаваемый индекс (Этап 5) |
| Агрегация считает не то | Units/timezone/formula/rounding/multi-category + provenance; unknown metric → abstain (Этап 5) |
| Search adapters — privacy/операционные сюрпризы | Offline default; внешние stores/models — opt-in с review/benchmark/budget/fallback (`.after.md`) |
| Тип/файл/формат неверно определяется | Явное type ID — authority; path/front matter объяснимы; inference — только предложение (Этап 3) |
| Переносимость обещана, а config/индекс содержит старые пути | Relative paths, cold-rebuild тесты (Этап 2, 5) |
| Преимущество над имеющимся стеком не подтверждается | Сравнить end-to-end с привычным toolchain; если надо — тонкий adapter (Этап 0) |
| FTS5 недоступен в builds / lexical недостаточен | Benchmark на Этапе 5; минимальная альтернатива; QMD bridge — только `.after.md` |
| Obsidian subset шире обещанного | Фиксировать subset на Этапе 7; unsupported extensions сохраняются, но не обещаются |

---

## 11. Открытые вопросы (Q1–Q13, defaults из конституции §14)

Полный список — в конституции §14. Здесь — только те, которые блокируют Этап 0.5: Q1 (Python), Q2 (`.todoc/`), Q3 (generated guide), Q4 (запись/исправления + первый slice), Q5/Q5a (ID/granularity + relations/graph), Q6 (`harness`), Q7 (multi-root), Q8 (персона), Q9 (Obsidian subset), Q10 (capture vs import), Q11 (search backend), Q12 (go/no-go пороги), Q13 (главная цель: QA/search vs records/aggregate vs memory). Defaults — в §3.1 выше; отклонения фиксируются в ADR на Этапе 0.5.

---

## 12. Источники

- Конституция: [`constitution.md`](constitution.md) (§0–§16).
- Конкурентный анализ: [`competitive-analysis.md`](competitive-analysis.md) (§1–§12, особенно §5 CLI, §6 C01–C60, §7 таблицы, §8 портабельность, §10 копировать/не копировать).
- Инженерный набросок: [`../plan.md`](../.research/engineering-plan.md) (§1–§18, особенно §3 аналоги, §3.6 аудит Skills, §5–§16 архитектура/CLI/этапы).
- Аудит Skills: [`../todoc_knowledge_base_comparative_audit.md`](../.research/comparative-audit.md).
- Принципы CLI/MCP/Markdown (корень репозитория, срез 24 ноября 2026): `guide_cli_for_agents_ru.md` (постулаты 1–26, часть II — безопасный вызов агентом, часть III — оценка + pre-release чек-лист), `guide_mcp_for_agents_ru.md` (постулаты 1–26, часть II — вызов агентом/клиентом, часть III — оценка + чек-лист; редакция MCP 2026-07-28), `guide_markdown_knowledge_for_agents_ru.md` (§I слои и LLM Wiki, §II диалекты, §III архитектура хранилища, §IV структура/ID/front matter/шаблоны, §V provenance/конфликты/свежесть, §VI ссылки/граф, §VII процедуры ingest/query/write/lint, §VIII ступени поиска, §IX docs-as-code/CI, §X trust/authority/freshness/access, §XI сравнение качества/токенов/времени + протокол benchmark-а, §XII план внедрения, §XIII Python CLI-каталог), `research_mcp_cli_agents_ru.md` (§1 как читать рекомендации, §2 базовая модель, §3 набор tools, §4 входы, §5 выходы, §6 CLI-входы, §7 CLI-выходы, §8 экономия контекста, §9 безопасность, §10 практическая карта MCP/CLI, §11 проверка качества, §12 анти-паттерны, §13 чек-лист).
- Первичные спецификации: Agent Skills specification, PyPA (src layout, `pyproject.toml`, entry points), Click, Python `typing.Protocol`, `pluggy`, JSON Schema 2020-12 + `jsonschema`, Python `csv`, `markdown-it-py`/CommonMark, `pathlib`, OWASP Input Validation, SQLite FTS5. Полные ссылки — в `plan.md` §18 и `competitive-analysis.md` §12.

> **Граница применимости.** Этот план — спецификация, не гарантия рыночного успеха. Конкурентные таблицы — feature audit, не benchmark. Всё надо проверять на закреплённых версиях реальных инструментов, одинаковых данных и пользовательских задачах (Этап 0).

---

## 13. Финальный аудит плана (24 ноября 2026)

### 13.1. Метод

Проверены: конституция (§0–§16), конкурентный анализ (§1–§12), `plan.md` (§1–§18), статический аудит Skills (`todoc_knowledge_base_comparative_audit.md`), гайды `guide_cli_for_agents_ru.md` (постулаты 1–26 + pre-release чек-лист), `guide_mcp_for_agents_ru.md` (1–26), `guide_markdown_knowledge_for_agents_ru.md` (§I–§XII), `research_mcp_cli_agents_ru.md` (§1–§13), README ConardLi rag-skill (единственный локально доступный референс из `tmp_kb_skills_audit/`; остальные 7 папок — пустые submodule-заглушки, их содержимое сверено по аудиту + веб-поиску конкурентного анализа). Аудит — статический (документы и описанные контракты), не runtime-тест и не benchmark.

### 13.2. Находки F1–F12 и где исправлено

| ID | Находка | Серьёзность | Исправление в плане |
|---|---|---|---|
| **F1** | Нет команды `doctor` (guide CLI постулат 17: read-only диагностика окружения с `--check`/`--scope`, `--fix` отдельно с dry-run). План имел `check`/`validate`/`status`, но не `doctor` | Средняя | Этап 5 шаг 4: добавлен `todoc doctor` + `todoc status` (быстрый снимок) + корневой discovery. Правило R1 в §14, чек-лист §15.1 |
| **F2** | Нет многоуровневого отчёта (0 итог → 1 оглавление → 2 группа/ID → 3 деталь) и группировки ошибок с порогом (guide CLI 19–20). План имел `truncated`/cursor, но не уровни и не группировку | Средняя | Этап 5 шаг 6: уровни + селекторы `--section/--id/--path/--max-depth/--fields/--limit/--cursor/--report-file` + группировка по severity/category + порог 5 (эвристика). R2–R3 |
| **F3** | Нет `docs tree` как derived компактного индекса (guide CLI 22). План имел `status/list/tree` упоминанием, но не команду | Низкая | Этап 5 шаг 4: `todoc docs tree`. R4 |
| **F4** | Поиск без `--within`, breadcrumb, `snippet_truncated`, `matched_count` (guide CLI 23). План имел snippets, но не эти поля/семантику | Средняя | Этап 5 шаг 6: `--within`, `heading_path`, `snippet_truncated`, `matched_count`/`total`/`returned`. R5–R6 |
| **F5** | Нет прогресса/отмены, framing потоков, `--details`, идемпотентности, discovery (guide CLI 12–16, 18). План имел stdout/stderr и preview/apply, но не эти детали | Средняя | Этап 5 шаг 6: прогресс/отмена, `--report-file`, `--details`/`--fields`, no-op при повторе, корневой discovery. R7–R11 |
| **F6** | Нет иерархической навигации `data_structure.md` + `index.md`/`log.md` (ConardLi, Karpathy). План имел `folders.json`/`CURRENT.json`, но не человекочитаемые derived индексы | Средняя | Этап 7 шаг 2: generated `index.md` + per-dir `data_structure.md`-аналог + append-only `log.md` как derived навигация/аудит (не source). R12 |
| **F7** | Нет forced learning (ConardLi: «перед PDF/Excel — обязательно прочитай `references/pdf_reading.md`»). Skill мог обрабатывать формат без чтения гайда | Средняя | Этап 7 шаг 2: MUST-правило forced learning + `references/formats-*.md`. R13 |
| **F8** | Нет явных процедур ingest/query/write/lint (guide MD-KB §VII). План имел capture/write, но не процедуры «добавить источник не загрязнив базу» / «найти ответ с основанием» / «lint для надёжности» | Средняя | Этап 7 шаг 2: `references/ingest-query-lint.md`. R16 |
| **F9** | Нет разделения trust/authority/freshness/access (guide MD-KB §X). План имел P10 (доверенные данные), но не 4-стороннее разделение | Средняя | §15.3: 4-стороннее правило + safe data policy. R17 |
| **F10** | Нет шаблонов страниц (guide MD-KB §IV: Contract/facts, Boundaries, Related, When to use, Preconditions, Steps, Check result, Rollback, Evidence, Decision/Alternatives/Consequences, Sources/Supersedes, Original location, Scope/version, Exact excerpts). План имел `templates/`, но не эти форматы | Низкая | Этап 7 шаг 2: `references/page-templates.md`. R18 |
| **F11** | Нет ablation, анти-паттернов, pre-release чек-листа (guides). План имел тесты/benchmark, но не чек-лист и не список запретов | Средняя | §15.4–15.5: чек-лист + анти-паттерны. R20 |
| **F12** | Skills-аудит подтверждает: memory/LLM Wiki — отдельный scope, не MVP (G1–G4). План уже так и делает; новых пробелов нет | — | Подтверждено без изменения scope. `.after.md` без изменений, только cross-refs на §14 |

### 13.3. Вердикт

План **готов к MVP** с дополнениями F1–F11 (все — уточнения контрактов, не расширение scope). Scope не меняется: MVP остаётся source-native validator + typed records + bounded search/read CLI; memory/LLM Wiki, embeddings/vector, веб, MCP, плагины, sync — в `.after.md`. Ни один Skill не берётся «целиком как есть» (см. §14.1) — все находки берутся как правила/паттерны с CLI-исполнением, а не как промпт-workflows.

---

## 14. Что взять из референсов: скиллы целиком или удачные решения/правила

### 14.1. Принцип: ни один Skill не берётся целиком

**Ни один Skill не берётся полностью как есть.** Причины (MUST):
1. Skills — **промпт-workflows** (инструкции агенту), а не CLI-контракты. Правила Skill ≠ технически принудительная транзакция/валидация (аудит §4). Копирование Skill как кода нарушило бы P10/P11 (доверенный код — только из пакета; CLI — authority).
2. ConardLi rag-skill **архивный** (README: «проект остановлен, новые Skills — в garden-skills»); Karpathy gist — **idea file**, не исполняемый Skill/CLI; Astro-Han/vanillaflava/bholmesdev/claude-obsidian/second-brain — **неофициальные реализации** с привязкой к Obsidian/конкретным агентам.
3. Skills используют `grep`/`read_file`/`pdftotext` напрямую (ConardLi) или многосторонние правки vault/hooks/scheduled agents (second-brain) — без containment/hash/post-validation, которые требует `todoc`.

**Ближайшее к «целиком»:** контракты **mdkb** (`--root`, `--json` goldens, `--dry-run`, `--allow-write`, disposable cache) и **okf** (`validate`/`lint`/`index`/`list`/`show`/`search`/`backlinks`/`graph`, SARIF, `--fail-on`) — берутся как **контракты** (имена/флаги/форматы), не как код. Всё остальное — как **правила/паттерны** (R1–R28 ниже).

### 14.2. По каждому референсу: взять целиком / как правило / не брать

| Референс | Целиком? | Взять как правило/паттерн | Не брать | Куда в плане |
|---|---|---|---|---|
| **Karpathy gist** (idea file) | Нет | `raw/wiki/index/log` как идея derived навигации; ingest/query/lint как разделение операций; `index.md` + append-only `log.md` | Синтез в MVP; gist как «ядро» | MVP: R12 (derived `index.md`/`log.md`); синтез — `memory-llm-wiki.after.md` |
| **Astro-Han karpathy-llm-wiki** | Нет | Read-only evidence script (`check_evidence.py`) как идея для `doctor`/`validate` evidence-проверки; статусы disputed/outdated | Skill как код/промпты; claim freshness в MVP | MVP: R22 (evidence check); статусы — `memory-llm-wiki.after.md` |
| **vanillaflava llm-wiki-skills** | Нет | Разделение config/ingest/query/lint/integrate/crystallize; `crystallize` (сессия → durable note, обновление hub); domain-home как session bootstrap | Page types как lifecycle задач; Skill как код | `memory-llm-wiki.after.md`: R23 |
| **obsidian-second-brain** (33–47 команд) | Нет | Каталог команд как референс для memory-профиля; task/idea/project схемы (status/due/priority/project/person; idea lifecycle; graduate idea→project); `/obsidian-health` (contradictions/gaps/stale/orphans) как lint-расширение; `/obsidian-retrieval-eval` (recall@k/MRR) как benchmark | Auto-writes/hooks/scheduled agents без транзакций; привязка к Obsidian; Skill как код | MVP: R26 (eval); memory — `memory-llm-wiki.after.md`: R27 |
| **claude-obsidian** | Нет | Transaction bundle + hash preconditions + inspect/apply/recovery + immutable captures + source/claim ledgers + egress границы + read-only retrieval | Крупная/специфичная архитектура целиком | `memory-llm-wiki.after.md`: R24 (bundle); egress — `search-embeddings-vector.after.md` |
| **bholmesdev skills** | Нет | Enrich-note (tags/source/backlinks) как AI enrichment draft; enrich loop/refresh-wiki как maintenance; tag registry | Облачный schedule в MVP; Skill как код | `plugins-formats-import.after.md` (enrich draft), `memory-llm-wiki.after.md` (tag registry): R25, R28 |
| **ConardLi rag-skill** (archived) | Нет | Иерархические `data_structure.md` (用途/файлы/диапазон) как derived навигация; forced learning (сначала прочитай `references/*.md`); progressive retrieval (grep → local read limit 200–500, max 5 rounds, termination condition); `pdftotext` в файл, не stdout; pandas `nrows` лимит; `data_structure.md` шаблон | `grep`/`read_file` напрямую как CLI; архивный проект как зависимость; PDF/Excel в MVP | MVP: R12–R15; PDF/Excel — `plugins-formats-import.after.md` |
| **Open Knowledge Wiki Skill** | Нет | Дисциплина shipped vs planned (держать wiki в соответствии с реальным shipped behavior, отделять planned от implemented, проверять документацию) | Skill как memory/Task model | MVP: R21 (docs discipline) |
| **Гайды CLI/MCP/MD-KB/research** | Нет (это правила, не скиллы) | Постулаты 1–26 как MUST-правила (см. §15) | — | MVP: R1–R11, R16–R20; MCP — `mcp-adapter.after.md` |
| **QMD / mdkb / okf / Basic Memory / Obsidian** | Нет (контракты, не код) | CLI/MCP-контракты, `doctor`, SARIF, watcher/stable id, `search:context`/backlinks (см. §3.2) | QMD processors (доверенный код); Obsidian `eval`; Basic Memory cloud sync в MVP | MVP: §3.2; watcher/cloud — `.after.md` |
| **Tana/Capacities/Dataview** | Нет | Supertags/objects/DQL как идея `entity_type`/query | Cloud/app реализация | MVP: E2/E7; cloud — не брать |
| **OpenKB / AnythingLLM / Khoj / Mem0 / Zep / Letta** | Нет | `lint`/`visualize` как идеи; hybrid как идея | LLM compile+overwrite; app-owned storage; vector/graph как истина | `.after.md` или не брать (см. §3.2) |

### 14.3. Удачные решения/правила R1–R32 (нормативные)

| ID | Правило | Источник | Реализация |
|---|---|---|---|
| **R1** | `todoc doctor` — read-only диагностика окружения (стабильные ID/категория/уровень, `--check`/`--scope`, по умолчанию ничего не исправляет; `--fix` отдельно с dry-run). `status` — быстрый снимок, `doctor` — набор проверок с scope и восстановлением | Guide CLI 17 (npm/Homebrew doctor) | MVP Этап 5 |
| **R2** | Многоуровневый отчёт: 0 итог/счётчики → 1 оглавление → 2 группа/ID/поддерево → 3 деталь/исходный лог; селекторы `--section/--id/--path/--max-depth/--fields/--limit/--cursor/--report-file` | Guide CLI 20 | MVP Этап 5 |
| **R3** | Группировка многочисленных ошибок: итоги по severity/category, порог показа (эвристика 5, калибруется), `total`/`shown`/`truncated`/cursor/путь к деталям; группировать только общую причину | Guide CLI 19 (CLIG) | MVP Этап 5 |
| **R4** | `docs tree` — оглавление как derived компактный индекс; `docs search` — короткий ранжированный список; `docs read` — полный выбранный раздел по ID | Guide CLI 22 | MVP Этап 5 |
| **R5** | Поиск: сначала фильтры `--within`/тип/версия, затем ранжирование **разделов** с `path` + `heading_path` (breadcrumb) + стабильный `id` + source line range; `--within` охватывает подкаталог/раздел с дочерними заголовками по умолчанию | Guide CLI 23 | MVP Этап 5 |
| **R6** | Snippets: предложение целиком + минимум контекста; при обрезке — `snippet_truncated`; `matched_count`/`total`/`returned`/`truncated`/cursor; не выдавать top-N за полный результат; не возвращать embeddings/сырые scores по умолчанию | Guide CLI 11, 23 | MVP Этап 5 |
| **R7** | Прогресс/время/отмена для длинных операций (scan/index rebuild), не портят результат | Guide CLI 15 | MVP Этап 5 |
| **R8** | Framing потоков: `--output json` — один валидный JSON на вызов; `--report-file` для больших отчётов; human summary и verbose — отдельные режимы, не текст для парсинга | Guide CLI 10, 12 | MVP Этап 5 |
| **R9** | `--details`/`--fields` для раскрытия деталей; debug/trace/backend internals — по запросу; секреты/PII — никогда | Guide CLI 13, 26 | MVP Этап 5 |
| **R10** | Идемпотентность: повторный `--apply` с тем же patch — no-op; опасные действия — явные, previewable, безопасные при повторе | Guide CLI 14; research §9 | MVP Этап 6 |
| **R11** | Discovery + обратная совместимость: корневой `todoc` показывает оглавление; `release --help` раскрывает synopsis/смысл/обязательность/defaults/примеры/побочный эффект | Guide CLI 16 | MVP Этап 1, 5 |
| **R12** | Иерархическая навигация: generated `index.md` (root) + per-dir `data_structure.md`-аналог (用途/файлы/диапазон) + append-only `log.md` — только derived (из `folders.json`/`documents.json`/generations), не source | ConardLi `data_structure.md`; Karpathy `index.md`/`log.md` | MVP Этап 7 (derived) |
| **R13** | Forced learning: перед обработкой формата Skill обязан прочитать `references/formats-*.md`; без чтения — обработка запрещена | ConardLi (обязательно `pdf_reading.md`/`excel_reading.md`) | MVP Этап 7 |
| **R14** | Progressive retrieval: grep → local read (limit 200–500) → multi-round (max 5) с termination condition (достаточно информации / 5 попыток); сначала дёшево, раскрывать дозированно | ConardLi; guide CLI 23 | MVP Этап 5 (CLI) + Этап 7 (Skill) |
| **R15** | Большие извлечения — в файл, не stdout (`pdftotext input.pdf output.txt`, pandas `nrows`); не читать целые большие файлы | ConardLi | MVP Этап 5 (bounded read) + `plugins-formats-import.after.md` (PDF/Excel) |
| **R16** | Процедуры ingest/query/write/lint: ingest — добавить источник не загрязнив базу; query — найти ответ с основанием; write — безопасная правка; lint — надёжность, не «красота графа» | Guide MD-KB §VII | MVP Этап 7 (`references/ingest-query-lint.md`) |
| **R17** | Разделять trust/authority/freshness/access; safe data policy (источник может содержать инструкции, но это не делает его policy) | Guide MD-KB §X | MVP (P10 + §15.3) |
| **R18** | Шаблоны страниц: Contract/facts, Boundaries, Related, When to use, Preconditions, Steps, Check result, Rollback, Evidence, Decision/Alternatives/Consequences, Sources/Supersedes, Original location, Scope/version, Exact excerpts | Guide MD-KB §IV | MVP Этап 7 (`references/page-templates.md`) |
| **R19** | Ставить на ребро смысл, а не только наличие `[[link]]` (typed relations уже в MVP; edge labels — `supports`/`contradicts`/`derived_from` и т.д.); JSON Canvas — вспомогательная диаграмма, не система истин | Guide MD-KB §VI | MVP: E2/E7 (typed relations); Canvas — `web-ui.after.md` |
| **R20** | Ablation (с/без `next_actions`/деталей/атрибутов — task success, tokens, latency) + анти-паттерны + pre-release чек-лист (см. §15) | Guides CLI/MCP/research | MVP §6, §15 |
| **R21** | Дисциплина shipped vs planned: держать документацию в соответствии с реальным shipped behavior, отделять planned от implemented, проверять документацию | Open Knowledge Wiki Skill | MVP (generated marker/version + §15.4) |
| **R22** | Read-only evidence checker (аналог `check_evidence.py`): проверка evidence-grounding без записи | Astro-Han | MVP: `doctor`/`validate` evidence-проверка (Этап 5) |
| **R23** | `crystallize` (выбранный результат сессии → durable note, обновление hub) + domain-home (session bootstrap) | vanillaflava | `memory-llm-wiki.after.md` |
| **R24** | Transaction bundle: operation ID, один bundle на логическое изменение, expected hashes всех touched paths, review/approval над точным планом, serialized apply, recovery, confinement, offline-by-default + egress consent | claude-obsidian | `memory-llm-wiki.after.md` (до широких writes) |
| **R25** | Enrich-note (tags/source/backlinks) как draft-предложение; enrich loop/refresh-wiki как maintenance | bholmesdev | `plugins-formats-import.after.md` (enrich draft) |
| **R26** | Retrieval-eval: recall@k + MRR на natural-language вопросах с конкретными failures и ranked fixes | obsidian-second-brain `/obsidian-retrieval-eval`; Open Knowledge `eval` | MVP Этап 5 (benchmark) |
| **R27** | Graduate (idea → project с задачами) + task/idea/project схемы как референс | obsidian-second-brain | `memory-llm-wiki.after.md` |
| **R28** | Tag/alias registry, duplicate-resolution, freshness/review_due, claim ledger (source + claim, valid-time vs recorded-time, не разрешать конфликт автоматически) | bholmesdev; guide MD-KB §V; claude-obsidian | `memory-llm-wiki.after.md` |
| **R29** | MCP-контракт как традиции M1–M26: tools/resources/prompts по назначению; имена `todoc.<verb>_<object>` + стабильный каталог; `inputSchema`/`outputSchema` + `structuredContent`/`TextContent`; `resultType` vs `isError`; stateless + явный handle; `ttlMs`/`cacheScope` private/public; deferred loading; progressive disclosure; `next_actions` как bounded hints; server-side authz при каждом вызове | Guide MCP 1–26; research §3–§9 | MCP-готовность в MVP (Этап 0.5, 5); реализация — `mcp-adapter.after.md` |
| **R30** | MCP vs CLI vs Skill по дереву решения: capability вне контекста → tool/resource; локальный repo/filesystem → CLI; обоим — одна domain implementation + тонкие adapters. Не оборачивать каждый endpoint; не делать `do_anything` | Guide MCP 23; CLI 24; research §2 | MVP: CLI первичен (P11); MCP — `mcp-adapter.after.md` §1.1 |
| **R31** | Слои хранилища памяти: docs/knowledge/memory/raw/logs/indexes как различимые слои с разными читателями/критериями; сырьё неизменно; индексы — derived; LLM Wiki — идея, не продукт; папки и граф — разные задачи | Guide MD-KB §I, §III; аудит §3, §5 | MVP: границы слоёв в E6/generations; синтез — `memory-llm-wiki.after.md` |
| **R32** | Протокол benchmark-а: held-out задачи (exact/single-doc/cross-doc/temporal/conflict/change-impact/editing/privacy), метрики retrieval/answer/safety/editing/operations, ablations, blind review, публикация N/split/scope/model/metrics/ограничений | Guide MD-KB §XI; research §11 | MVP §6 (agent evaluation); MCP eval — `mcp-adapter.after.md` §15 |

---

## 15. Правила-чек-лист (из гайдов, нормативные для реализации)

### 15.1. CLI-правила (MVP, `guide_cli_for_agents_ru.md`)

1. CLI — стабильный контракт, не текстовый экран для парсинга; машинный интерфейс документирован (грамматика, входы, выход, exit codes, побочные эффекты).
2. Одна предсказуемая команда на действие (`noun verb`/`verb noun`); одинаковые флаги для одинакового смысла; неизвестная команда — не catch-all.
3. Входы явные, типизированные по смыслу, ограниченные (формат, единицы, timezone, допустимые значения, дефолты, пределы); `--` для операндов с `-`.
4. Параметры команды ≠ содержимое данных: stdin/`-` для больших данных; не требовать временный файл, если безопасно stdin.
5. Не требовать интерактивного ввода от automation: prompt только при TTY; `--no-input` + явные параметры; в неинтерактивном режиме — полезная ошибка, не зависание.
6. Не передавать секреты в argv (history/process list/логи); credential store/защищённый prompt/ограниченный stdin/файл с правами.
7. Не конструировать shell-команду из текста модели/пользователя: библиотека/API или фиксированная allowlist executable + argv по отдельности; quoting не защищает от argument injection.
8. stdout — данные; stderr — диагностика/предупреждения/прогресс; `0` — успех, ненулевой — ошибка; числовая карта кодов — часть контракта.
9. Явный машинный формат (`--json`, при полезности `--plain`); human-first по умолчанию — рекомендация, не стандарт; default выбирается по основному сценарию.
10. В машинном режиме stdout чистый (один валидный JSON на вызов, без баннера/цвета/прогресса/prose); единая политика ошибок (JSON envelope + exit code).
11. Минимум достаточных данных, но не терять смысл/полноту: статус + основное значение; стабильный ID + понятное имя для follow-up; только свойства, меняющие выбор/ответ; scope/единицы/время/source, если без них смысл неполон; `matched_count`/`truncated`/cursor.
12. Framing потоков: `--report-file` для больших отчётов; human summary и verbose — отдельные режимы.
13. Ошибка сообщает причину и исправление; детали — по режиму (`--details`/`--fields`).
14. Опасные действия — явные, previewable, безопасные при повторе (идемпотентность, no-op при повторе).
15. Прогресс/время/отмена для длинных операций, не портят результат.
16. Discovery + обратная совместимость: корневой `todoc` — оглавление; `--help` раскрывает synopsis/смысл/обязательность/defaults/примеры/побочный эффект.
17. `doctor` — read-only диагностика (стабильные ID/категория/уровень, `--check`/`--scope`, по умолчанию ничего не исправляет; `--fix` отдельно с dry-run). `status` — быстрый снимок.
18. Подтверждение успешного действия кратко, но не непрозрачный `OK` (что именно изменилось).
19. Группировка многочисленных ошибок: итоги по severity/category, порог показа (эвристика 5), `total`/`shown`/`truncated`/cursor/путь к деталям; группировать только общую причину.
20. Многоуровневый отчёт: 0 итог → 1 оглавление → 2 группа/ID/поддерево → 3 деталь/лог; селекторы `--section/--id/--path/--max-depth/--fields/--limit/--cursor/--report-file`.
21. Кэш prompt — бонус, не основание для лишних вызовов; не проектировать вывод в расчёте на кэш-хит; измерять `cached_tokens`/usage/latency.
22. Дерево документации как derived компактный индекс (`docs tree`/`docs search`/`docs show`).
23. Искать сначала дёшево, раскрывать дозированно, усложнять ранжирование по eval; `--within`, breadcrumb, `snippet_truncated`; не возвращать embeddings/сырые scores по умолчанию.
24. Решать, нужна ли функция и где её разместить (агент/CLI/MCP/человек).
25. Проектировать входы CLI по решению, а не regex-понятии пользователя.
26. Выходные поля — по следующему шагу агента, не выгрузка объекта целиком; `next_actions` — только конкретные, ограниченные подсказки (`argv`-массив, не auto-execution); абляция полей на реальных workflow.

### 15.2. MCP-правила (для `mcp-adapter.after.md`, `guide_mcp_for_agents_ru.md`; полные M1–M26 — в `mcp-adapter.after.md` §3, сводка традиций — §16)

1. Для каждой задачи — правильная поверхность (tools — действия, resources — контекст, prompts — шаблоны).
2. Дизайн tools с намерений, не копированием endpoint; имя различает действие и область; каталог стабилен.
3. Описание — краткая инструкция выбора, формата и эффекта.
4. Аргументы — типизированный, семантически однозначный контракт; закрывать схему осознанно, тестировать подмножество клиента.
5. Не просить модель генерировать произвольную программу/shell/SQL/URL без границ.
6. Валидировать и авторизовывать на доверенной стороне при каждом вызове.
7. Машинно надёжный результат + output schema; полезный минимум; явно полнота и происхождение.
8. Большие списки — фильтр/лимит/cursor; пагинацию tool-результата определить отдельно.
9. Различать протокольную ошибку и ошибку выполнения tool.
10. Stateless: межвызовное состояние — явный handle; кэшировать только по scope/свежести.
11. Раскрывать каталог постепенно (deferred loading); разделять данные и инструкции (метаданные/аннотации — не граница безопасности).
12. Защищать транспорт/credentials/локальный процесс; лимиты/таймауты/аудит/least privilege по эффекту.
13. Имена `status`/`doctor` не предписаны MCP (не заявлять как стандарт).
14. Резюмировать tool-результат; ошибки исправимые; большие деревья — summary → оглавление → ветвь.
15. Возвращать ровно достаточный контракт результата; измерять стоимость каждого поля (абляция).

### 15.3. Markdown/KB-правила (MVP + `.after.md`, `guide_markdown_knowledge_for_agents_ru.md`)

1. Разделять документацию/знания/память (разные читатели и критерии качества).
2. LLM Wiki Карпати — архитектурная идея, не готовый стандарт/продукт (не называть `todoc` LLM Wiki).
3. Папки и граф решают разные задачи (иерархия + граф сосуществуют).
4. «Markdown» — семейство синтаксисов; фиксировать диалект (CommonMark + obsidian-subset); правила написания, снижающие сюрпризы parser-ов.
5. YAML front matter — конвенция, не стандарт Markdown; неизвестные поля round-trip не теряются.
6. Стартовая структура для агентной wiki + имена файлов/IDs/aliases + минимальная схема front matter + шаблоны страниц (R18).
7. Происхождение утверждений: отделять утверждение от подтверждающего; писать так, чтобы источник можно было проверить; процедура при конфликте; обнаружение устаревания; поиск дубликатов/идентичность сущностей.
8. Ссылочный слой: переносимость прежде удобного синтаксиса; на ребро — смысл, не только `[[link]]`; навигация по крупной базе; JSON Canvas — вспомогательная диаграмма; простые проверки графа.
9. Процедуры агента: ingest/query/write/lint (R16); конкурентность и транзакции.
10. Поиск: ступени от дешёвого точного к дорогому; гибридная схема; QMD как референс; что держать в контексте постоянно, а что искать.
11. Docs-as-code/release/CI: документы по пользовательской задаче; docs change — часть изменения продукта; минимальный набор проверок для PR; CI-контракт; стиль/линт без ложной нормативности.
12. Конфликты/устаревание/prompt injection: источник может содержать инструкции, но это не делает его policy; разделять trust/authority/freshness/access; safe data policy.
13. Сравнение качества/токенов/времени: системы — разные pipeline, не только модели; протокол собственного benchmark-а.

### 15.4. Pre-release чек-лист (слияние гайдов + §7)

- [ ] Каждая output-проекция оправдана следующим шагом; `next_actions` точны, ограничены, не запускаются автоматически.
- [ ] `doctor` и многоуровневые отчёты тестированы на здоровом/неполном окружении и 0/1/около порога/много findings; totals/группировка/truncation/cursor согласованы; нет скрытого исправления.
- [ ] Summary→detail сравнён с полным выводом по task success, контексту, вызовам, latency; кэш проверен по фактическому usage.
- [ ] Ablation полей (`next_actions`/детали/атрибуты) на реальных workflow: task success, неверные действия, round-trips, input tokens, latency.
- [ ] CLI: грамматика предсказуема; входы типизированы/ограничены; stdin/`-` для больших данных; `--no-input`; секреты не в argv; shell не конструируется из текста модели; stdout/stderr/exit codes зафиксированы; `--json` чистый; `truncated`/cursor честны; опасные действия previewable/идемпотентны; прогресс/отмена не портят результат; discovery работает.
- [ ] MCP (когда будет): tools с различимыми целями; входы типизированы; schema закрыта осознанно; валидация/авторизация на доверенной стороне; output schema соблюдена; stateless; каталог раскрывается постепенно; данные ≠ инструкции; лимиты/таймауты/аудит/least privilege.
- [ ] Markdown/KB: диалект зафиксирован; front matter минимален; шаблоны страниц используются; provenance/конфликты/устаревание обрабатываются; ссылки переносимы; ingest/query/write/lint процедуры соблюдаются; поиск ступенчатый; docs-as-code/CI проверки пройдены; prompt injection не исполняется.
- [ ] Безопасность: containment, limits до buffer/parse, allowlist команд/типов, отдельная политика чтения/записи; валидный файл ≠ безопасный/доверенный/разрешённый к записи.
- [ ] Тесты: unit/contract/integration/CLI/packaging/agent-eval (§6); wheel вне checkout; Obsidian smoke test; Skill validator; generated marker/version/diff.
- [ ] Документация: shipped vs planned разделены (R21); generated файлы с marker/version/reproducible diff.

### 15.5. Анти-паттерны (из `research_mcp_cli_agents_ru.md` §12 + гайдов)

- Парсить меняющуюся human-таблицу как контракт.
- Непредсказуемые команды/флаги, скрытый catch-all, угадывание сокращений.
- Пользовательский ввод в `eval`/SQL/shell/regex без лимитов и безопасной грамматики.
- Секреты в argv; shell-команда из текста модели/пользователя.
- Интерактивный ввод, зависающий automation.
- Выгрузка объекта целиком / «все колонки БД» в stdout.
- Top-N за полный результат; `truncated` скрыт.
- `next_actions` как auto-execution или перечисление всех команд.
- Скрытые LLM/сетевые вызовы в ядре; embeddings/rerank default без gate.
- Исполнение кода/prompt из DATA_ROOT; `workflow` из данных как authority.
- Молчаливая перезапись существующих источников; auto-save всей беседы.
- Истина в SQLite/векторной БД/graph DB; абсолютные пути в конфигах/индексах.
- `doc_type: plan`/`idea` как task management без lifecycle/queries.
- LLM-выводы как истина без evidence workflow.
- Копирование Skill как кода; QMD processors как sandbox; Obsidian `eval` как CLI.
- Проектирование вывода в расчёте на prompt cache-хит.
- Реклама цифр без frozen corpus/tokenizer/versions/benchmark.
- Отображение всех endpoint API как MCP tools; несколько tools с почти одинаковым назначением без объяснения выбора.
- Считать, что схема валидирует права/бизнес-условия; принимать `readOnlyHint`/описание за доказательство безопасности.
- Возвращать успешный статус при частичном выполнении или пустой результат при сбое; не отличать protocol error от ошибки tool.
- Передавать полный документ через контекст между двумя tools вместо ссылки/ID внутри orchestration.

---

## 16. Лучшие традиции MCP и хранилища памяти (обогащение 0.3)

> **Статус:** нормативные традиции для MCP-готовности MVP и для будущей реализации MCP. MCP в MVP не реализуется; традиции закладываются в контракты CLI (E8/E10), чтобы MCP вставился без переписывания ядра. Полные формулировки M1–M26 — в [`mcp-adapter.after.md`](after/mcp-adapter.after.md) §3; здесь — сводка и привязка к этапам MVP.

### 16.1. Традиции MCP (M1–M26, сводка)

| Группа | Традиции | Привязка к MVP |
|---|---|---|
| **Поверхности** | Tools — model-controlled операции; resources — адресуемые данные/контекст; prompts — повторяемые шаблоны (M1). Дизайн с намерений, не копированием endpoint; не `do_everything`/`execute_query` (M2, M23). Дерево решения MCP vs CLI vs Skill (§16.1.1) | Этап 0.5: зафиксировать use cases + URI-схему resources черновиком. Реализация — `mcp-adapter.after.md` §5 |
| **Имена/описания** | Уникальные имена `todoc.<verb>_<object>`, 1–128 символов, ASCII/`_`/`-`/`.` [STD]; стабильный детерминированный каталог (M3). Описание — инструкция выбора: цель, когда/когда не использовать, scope, аргументы, формат/единицы/timezone, эффект, limit/полнота/продолжение (M4) | Этап 0.5: черновик каталога tools v1 (`<20` эвристика, M15). CLI-команды уже следуют `noun verb`/`verb noun` (P11) |
| **Вход** | `inputSchema` JSON Schema 2020-12; required/optional, absent vs `null`, формат/единицы/диапазон/enum/длины, default явно реализуется сервером (M5). `additionalProperties: false` осознанно; OpenAI strict — не требование MCP (M6). Без произвольной программы/shell/SQL/URL (M7). Контракт под явное решение агента: `verb + object`, конечные типы, `query` ≠ `instructions`, regex — форма, не смысл (M24) | Этап 0.5 + Этап 5: CLI-флаги уже типизированы/ограничены (P7, P8); query AST allowlisted (E7). MCP `inputSchema` мапится из тех же контрактов |
| **Выход** | `outputSchema` + `structuredContent` (MUST соответствовать), `TextContent` дубль — проверить на двойное попадание в контекст (M9). Полезный минимум + полнота/происхождение; пустой — штатный, частичный — явно (M10). `next_actions` — bounded hints на существующие tools, не вызов и не стандарт (M25). Дочерняя сущность vs атрибут — по ID/жизненному циклу (M25). Progressive disclosure summary→outline→ветвь (M21) | Этап 5 шаг 8: envelope спроектирован для мапинга на `structuredContent` без смены семантики. `issues_found` — успешный result (M20) |
| **Ошибки** | Протокольная ошибка (JSON-RPC) ≠ ошибка выполнения tool (`isError: true`) (M12). `resultType` (complete/input-required) ≠ `isError`. Ошибка — причина + исправимый шаг + стабильная категория, без секретов/stack trace | Этап 5: CLI exit codes + envelope уже различают успех/ошибку; MCP мапинг — `mcp-adapter.after.md` §7 |
| **Состояние/кэш/пагинация** | Stateless; межвызовное состояние — явный непрозрачный handle с TTL, права заново (M13). `ttlMs`/`cacheScope`: `private` не шарить между auth-контекстами, `public` — только неперсональное; кэш — не авторизация (M14). Cursor-пагинация list-методов ≠ пагинация `tools/call`; для tool-результата — отдельный `limit`/opaque cursor или resource; нет snapshot consistency (M11). Prompt caching — бонус, не основание для лишних вызовов (M22) | Этап 5: CLI уже stateless по `--root`/`dataset_id`/`id`/`cursor`; MCP наследует ту же модель |
| **Каталог** | Постепенное раскрытие: короткие подсказки + малый набор частых tools → поиск/отложенная загрузка → полный schema для кандидатов (M15). `<20` tools на старте — эвристика, не стандарт | Этап 0.5: черновик каталога v1. Реализация deferred loading — `mcp-adapter.after.md` §5 |
| **Безопасность** | Данные ≠ инструкции; аннотации — не граница безопасности; sensitive/destructive — контроль снаружи (M16). Валидация/авторизация на доверенной стороне при каждом вызове; валидный ID ≠ авторизация (M8, M26). Транспорт: TLS + `Origin` (403), localhost bind, stdio stdout — только framing, без секретов в `x-mcp-header` (M17). Лимиты/таймауты/аудит/least privilege по эффекту (M18) | P10/P11 уже требуют: доверенный код только из пакета, CLI — authority, DATA_ROOT — недоверенные данные. MCP наследует те же инварианты |
| **Диагностика** | `status`/`doctor` не предписаны MCP (M19). Паттерн: `get_status` (снимок) + `run_diagnostics` (`scope`/`checks`) + `get_finding` (по ID). `issues_found` — успех, не `isError` (M20) | Этап 5: CLI `status`/`doctor`/`check` уже следуют этому паттерну (R1). MCP tools мапятся 1:1 |
| **Оценка** | Held-out многошаговые задачи с проверяемым outcome; слабейшая модель + тесный бюджет; реальные клиенты/SDK/версии; empty/large/partial, cursor, кэш, expired handle, injection, timeout, повтор side effect; метрики research §11.3; pre-release чек-лист `mcp-adapter.after.md` §15.3 | §6: MCP evaluation строка (когда будет MCP). В MVP — только MCP-готовность контрактов |

#### 16.1.1. Дерево решения MCP vs CLI vs Skill (для `todoc`)

```text
Достаточно ли агенту контекста для ответа без риска?
├─ Да → не вызывать MCP/CLI ради формальности.
└─ Нет → нужны данные или операция?
   ├─ Адресуемое содержимое → resource (MCP) / docs read (CLI).
   ├─ Поиск/проверка/изменение, выбранная моделью → tool (MCP) / команда (CLI).
   └─ Объёмная детерминированная обработка → tool/команда с фильтром/лимитом/cursor.
         ↓
Есть неоднозначность или рискованный выбор?
├─ Да → ограниченные варианты/evidence; агент уточняет у пользователя.
└─ Нет → валидировать/авторизовать, выполнить точный контракт, вернуть итог.
```

**Правило:** локальный repo/filesystem → CLI (первичный контракт, P11); capability через MCP-host с серверными правами → tool/resource; обоим — одна domain implementation + тонкие adapters. Не добавлять интерфейс из-за ярлыка «для агента».

### 16.2. Традиции хранилища памяти (сводка)

| Традиция | Суть | Привязка к MVP |
|---|---|---|
| **Слои** (guide MD-KB §I) | Документация / знания-wiki / память проекта / сырьё / журналы сессий / индексы — различимые слои с разными читателями/критериями. Сырьё неизменно; индексы — derived. `AGENTS.md`/`CLAUDE.md` — маршрут, не хранилище знаний | MVP: E6 generations + derived индексы уже следуют слоям. Синтез/wiki — `memory-llm-wiki.after.md`. Не называть `todoc` LLM Wiki |
| **LLM Wiki** (guide MD-KB §I.2) | Идея (raw/wiki/schema + ingest/query/lint + `index.md`/`log.md`), не стандарт/продукт. Брать разделение ролей и цикл, не названия каталогов буквально | MVP: R12 derived `index.md`/`log.md` (навигация/аудит, не source). Синтез — `memory-llm-wiki.after.md` |
| **Папки и граф** (guide MD-KB §I.3) | Папки — расположение/доступ; ссылки/backlinks — связи; индекс/поиск — текст по запросу; properties — тип/версия/статус/источник; MOC — вход в предмет. Не заменять один другим | MVP: E2/E7 typed relations + backlinks (R19). Canvas — `web-ui.after.md` |
| **Процедуры** (guide MD-KB §VII) | Ingest (не загрязнив базу) → Query (с основанием) → Write (минимальный дифф, не raw) → Lint (надёжность, не «красота графа»). Конкурентность: один владелец на page/source, append-only журналы с `run_id`, lock/transaction/version check | Этап 7: `references/ingest-query-lint.md` (R16). MCP tools обслуживают процедуры, не заменяют их |
| **Provenance** (guide MD-KB §V) | `утверждение → scope/версия/время → свидетельство → оригинал/снимок`. Цитата/пересказ/наблюдение/вывод/гипотеза — раздельно. Конфликт — `disputed`, не «среднее». Свежесть — `verified_at`/`review_after` + cadence по риску. Дубликаты — canonical ID + aliases/redirect | MVP: P8 locations + hash/provenance уже есть. Claim ledger/freshness — `memory-llm-wiki.after.md` (R28) |
| **Ссылки/граф** (guide MD-KB §VI) | Переносимость прежде удобного синтаксиса (обычные Markdown-ссылки шире wikilinks). На ребро — смысл (`supports`/`contradicts`/`derived_from`), не только `[[link]]`. Навигация: HOME → MOC → сущность → backlinks → поиск → ограниченный traversal (1–2 перехода) → первоисточники. Canvas — диаграмма, не истина. Проверки графа в CI | MVP: R19 typed relations. HOME/MOC — derived `index.md` (R12) |
| **Ступени поиска** (guide MD-KB §VIII) | От дешёвого точного (`rg`/exact) → BM25/FTS → vector+BM25 hybrid (RRF) → reranker по shortlist. Baseline — лексический; BEIR: BM25 — сильная робастная база. Heading path + provenance в каждом chunk. QMD — необязательный локальный hybrid слой. Индекс/embeddings/cache — derived | Этап 5: lexical baseline + benchmark (R26). Vector/hybrid/rerank — `search-embeddings-vector.after.md` |
| **Trust** (guide MD-KB §X) | Источник может содержать инструкции, но это не policy. Разделять authority/freshness/scope/trust/access; одна relevance score не сворачивает их. Safe data policy: секреты не в Markdown, corpus по access boundary, redaction PII, не индексировать `.git`/build/secrets по умолчанию | MVP: P10 + R17. Egress consent — `search-embeddings-vector.after.md` |
| **Benchmark** (guide MD-KB §XI) | Системы — разные pipeline, не только модели. Held-out набор (40–100 задач старт, затем по покрытию/риску); классы: exact/single-doc/cross-doc/temporal/conflict/change-impact/editing/privacy. Метрики: retrieval/answer/safety/editing/operations. Ablations A–F. Blind review. Публикация N/split/scope/model/metrics/ограничений | §6 agent evaluation. Практический критерий wiki: curated layer только при надёжном выигрыше на cross-document/update задачах |
| **Python CLI-каталог** (guide MD-KB §XIII) | Разводить format / doc_type / dir_type / backend. Конвейер: scan → resolve → parse → validate → derived catalog/cache/index → bounded search/read/validate/edit. Config — данные, не исполняемый код; hard-exclude до классификации; приоритеты с `explain-path`; реестры `folders.json`/`documents.json` + per-doc cache; `expected_hash` для edits | MVP: Этапы 2–5 уже следуют этому конвейеру. XIII — инженерный референс для Этапов 2–4 |

**Coverage matrix аудита (§5) — что традиции памяти не закрывают в MVP:** Task/Plan/Idea/Decision/Person/Project со статусами/сроками/исполнителями/приоритетами/повторяемостью; типы отношений с валидацией; capture/triage/dedupe; immutable raw → compiled wiki; source + claim ledgers; session bootstrap/кристаллизация; task-oriented запросы; семантическая проверка claims; tag registry/aliases; transaction bundle; sensitivity/retention/scopes. Всё это — `memory-llm-wiki.after.md` (аудит §6 рекомендации 1–9).

### 16.3. Предпросмотр каталога MCP для `todoc` (черновик gate, не реализация)

| Tool | Назначение | Почему отдельный tool (M2, M23) |
|---|---|---|
| `todoc.search_docs` | Поиск по docs с фильтрами/лимитом/cursor | Поиск ≠ чтение: разные права/объём |
| `todoc.read_doc` | Bounded projection по ID/selector | Чтение фрагмента ≠ поиск |
| `todoc.query_records` | Declarative query по `entity_type` | Query ≠ aggregate: разные операции |
| `todoc.aggregate_records` | Агрегат с units/formula/provenance | Вычисление с собственной семантикой |
| `todoc.check` | Сводка validate (groups/findings/page) | Сводка ≠ детали (M20) |
| `todoc.get_status` / `todoc.run_diagnostics` / `todoc.get_finding` | Диагностика по паттерну M19 | Снимок ≠ набор проверок ≠ раскрытие |
| `todoc.inspect_tree` | Оглавление/ветвь (M21) | Дерево ≠ список |
| `todoc.list_types` / `todoc.show_type` | Каталог типов для capture-диалога | Справочник ≠ операция |
| `todoc.records_create_preview` / `todoc.records_create_apply` (v2, opt-in) | Preview + apply за consent | Preview (read-only) ≠ apply (side effect) |
| `todoc.fix_preview` / `todoc.fix_apply` (v2, opt-in) | Preview + apply исправления | Аналогично |

Resources: `todoc://<dataset_id>/doc/<id>`, `todoc://<dataset_id>/record/<id>`, `todoc://<dataset_id>/type/<type>`, `todoc://<dataset_id>/tree`. Prompts: `capture-record`, `query-aggregate`, `lint-report`. Полные контракты — `mcp-adapter.after.md` §5–§7.

### 16.4. Что изменено в версии 0.3

- `mcp-adapter.after.md` переписан с 105 до 511 строк: M1–M26, архитектура (один domain + тонкие adapters), каталог tools/resources/prompts с контрактами входа/выхода, stateless/кэш/пагинация, безопасность, традиции памяти (§10), пошаговый план, eval + pre-release чек-лист + анти-паттерны.
- `implementation-plan.md`: §0.3 (MCP-готовность без реализации + граница memory), §2.2 E8/E10 (M-привязка), §3.2 (две новые строки: традиции MCP + традиции памяти), Этап 0.5 (MCP-готовность контрактов + черновик gate), Этап 5 шаг 8 (envelope → `structuredContent`), §6 (MCP evaluation строка), §7 (MCP-готовность в DoD), §9 (gate MCP), §12 (полные источники по разделам), §14.3 R29–R32, §15.2 (ссылка на §16), §15.5 (MCP анти-паттерны), §16 (этот раздел).
- Scope не меняется: MVP — source-native validator + typed records + bounded search/read CLI; MCP, memory/LLM Wiki, embeddings/vector, веб, плагины, sync — в `.after.md`.
