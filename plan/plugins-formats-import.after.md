# Перспектива (НЕ сейчас): Плагины, форматы, импорт, watch, AI enrichment

**Статус:** FUTURE — не реализуется в MVP. Этот файл описывает, **как** расширения вставятся через малые контракты без монолитного parser и без исполнения кода из DATA_ROOT.
**Дата:** 24 ноября 2026 года.
**Связанные документы:** [`implementation-plan.md`](implementation-plan.md) §2 (порты E1/E8), §4 Этап 4; [`constitution.md`](constitution.md) §6.3, FR-4.5, FR-12, C34–C35, C41, C43, C51; [`competitive-analysis.md`](competitive-analysis.md) §4.2 (QMD processors), §4.3 (OpenKB intake), §4.5 (AnythingLLM sync), §6 C34–C35, C41, C43, C51.

---

## 1. Что это и зачем

- **Плагины:** установленные Python entry points для новых форматов/операций (allowlist, версия API). Референс: `pluggy`/pytest plugins.
- **Форматы:** YAML, Excel (XLSX), PDF, SQLite (read-only source adapter) — через малые `FormatReader`/`FormatWriter` контракты.
- **Импортёры:** PDF/DOCX/XLSX/URL/Notion → Markdown/JSON (preview-first copy/adopt, без обязательной конвертации).
- **Watch mode / auto-ingest:** наблюдение за папкой + авто-компиляция/индексация новых файлов.
- **AI enrichment:** LLM-выжимки/теги/связи как предложения (draft), не факты до валидации/подтверждения.
- **Scheduled agents:** фоновые агенты обслуживания (enrich loop, refresh, lint).

**Ценность:** шире вход (PDF/Excel/URL) + автоматизация обслуживания. **Цена:** парсеры, безопасность (макросы/формулы), приватность (сеть/LLM), сложность (фоновые процессы).

**Конкуренты-референсы:** QMD processors (доверенный код, не sandbox), OpenKB intake (PDF/Word/MD/PPTX/HTML/Excel/CSV/text/URL + `watch` + `recompile`), AnythingLLM Live Document Sync beta (наблюдает отдельные файлы, не целые папки; re-embedding hourly/10 min), bholmesdev enrich loop/refresh-wiki (scheduled/cloud), Khoj (Notion/Word/PDF/OCR). Все показывают: широкий input + watch + enrichment — зрелые фичи, но с trade-off «автоматическая компиляция vs source-native deterministic проверки».

## 2. Почему НЕ сейчас

1. **MVP — MD/CSV/JSON source-native.** YAML/XLSX/PDF/SQLite — только по подтверждённой боли (конституция §6.3, FR-4.5). Без use case — не вводить parser/plugin без privacy/benchmark/security tests.
2. **Плагины — граница доверия.** Entry point загружает исполняемый Python-код. Без allowlist/версии API — это RCE из DATA_ROOT (нарушение P10).
3. **Watch/scheduled — скрытые фоновые действия.** Без consent/лимитов — нарушение P5/P12/NFR-7 (никакого background job по умолчанию).
4. **Import/AI enrichment — риск молчаливой конвертации/перезаписи.** Без preview/валидации — нарушение P6.

## 3. Архитектурные хуки в MVP (уже заложены)

| Хук | Что уже есть в MVP | Как переиспользуется |
|---|---|---|
| **E1 `FormatReader`/`FormatWriter`** | Три drivers (MD/CSV/JSON) + `dict[FormatId, FormatDriver]` + contract tests | Новый driver + одна регистрация; без `if/elif` в слоях. Read-only типу не нужен фиктивный writer (I) |
| **E8 `WorkflowLookup`** | Whitelisted `workflow_id` | Новые `workflow_id` для import/enrichment (trusted Skills); DATA_ROOT не может ввести произвольный workflow |
| **E9 write safety** | `WritePlan` + `expected_hash` + preview/apply | Import/enrichment — только preview/draft + явный apply; AI draft не считается фактом до валидации |
| **E6 generations/cache** | Atomic generations + per-doc cache | Новые форматы — те же generations/cache с parser version в cache key |
| **Config** | `dataset.json` + `enabled_formats` | Добавить `enabled_formats` (YAML/XLSX/PDF/SQLite) + `plugins` allowlist + `watch`/`enrichment` opt-in секции |

**Инвариант:** DATA_ROOT никогда не содержит исполняемого кода. Плагин — только из установленной среды по allowlist с проверкой API version и конфликта registry. `pluggy` — только если появится реальная потребность в hooks (не ради абстрактной «расширяемости»).

## 4. Пошаговый план внедрения (когда gate пройден)

### Шаг 1 — Gate на каждую перспективу (до кода)

Для каждой фичи отдельно: конкретная подтверждённая боль, тестовый набор/план безопасности, privacy/egress/resource limits, benchmark, fallback. Без этого — не вводить.

### Шаг 2 — Плагины (entry points + allowlist)

1. Зафиксировать plugin API version + hooks (если нужны). Референс: `pluggy`/pytest.
2. Реализовать загрузку только из установленной среды по локальной allowlist (ID/distro), с проверкой дубликатов/совместимости. Не искать модули в DATA_ROOT.
3. Добавить `todoc plugins list/enable/disable` (или конфиг-секцию) + diagnostics для неизвестных/несовместимых плагинов.
4. Тесты: plugin contract tests; конфликт registry; DATA_ROOT с `.py` файлом не исполняется.

### Шаг 3 — Форматы (по одному, с contract tests)

1. **YAML:** отдельный parser с безопасной загрузкой (без доверенных constructors/tags). Markdown front matter ≠ произвольные `.yaml` файлы.
2. **Excel (XLSX):** отдельный adapter с явной политикой по формулам, макросам, hidden sheets, dependency/size. Formula injection — как в CSV.
3. **PDF:** в MVP — opaque asset (path/size/hash, без парсинга). Парсинг — opt-in adapter (например, через Marker/poppler как в contractor-bid, или OCR как в Khoj) с preview.
4. **SQLite:** либо read-only source adapter для таблиц с ограничениями запросов, либо metadata/search backend. Не назначать файлу тип `sqlite` вместо семантического типа документа.
5. Каждый — `FormatReader`/`FormatWriter` + общие contract tests (diagnostics, locations, limits, encoding, round-trip).

### Шаг 4 — Импортёры (preview-first)

1. Реализовать `todoc import --plan/--preview/--apply` (отдельная операция, не часть `scan`): plan → preview copy/adopt → explicit confirmation. Индексирование никогда не изменяет исходные файлы.
2. Импортёры: PDF/DOCX/XLSX/URL/Notion → Markdown/JSON. CSV→Markdown — отдельный opt-in import с preview (Obsidian Importer делает такую конвертацию; `todoc` не делает её молча).
3. Тесты: preview не пишет; apply — с `expected_hash`; исходники не меняются без apply.

### Шаг 5 — Watch mode (opt-in)

1. Реализовать `todoc watch --root …` (наблюдение + авто-индексация новых файлов). Референс: OpenKB `watch` (`raw/` → auto-compile), AnythingLLM Live Sync beta (отдельные файлы, не целые папки).
2. Watch — только derived index/cache (не source files). Запись в source — только через те же write-контракты (preview/apply).
3. Тесты: add/delete/rename → инвалидация cache; crash → recovery; без watch — всё работает как в MVP.

### Шаг 6 — AI enrichment + scheduled agents (opt-in)

1. Реализовать enrichment как предложение: LLM-выжимка/теги/связи → draft → schema validation → пользовательское подтверждение → create-only запись. До валидации/подтверждения — не факт.
2. Реализовать scheduled agents (enrich loop, refresh, lint) только с явным consent + лимитами + audit log. Никакого auto-save всей беседы.
3. Тесты: draft не считается фактом; scheduled не пишет без consent; audit log полон.

### Шаг 7 — External fetch для `link` capture (opt-in, v1)

1. Реализовать `external_fetch_policy` для типа `link` (FR-6.3, C51): allowlisted fetch (URL → title/описание/ключевые пункты/теги) + preview. Без скрытой сети по умолчанию (P12).
2. Тесты: fetch только для allowlisted URL; preview перед записью; offline fallback (запись без выжимки).

## 5. Данные и миграции

- **Schema:** добавить `enabled_formats`, `plugins` allowlist, `watch`/`enrichment`/`fetch` секции в `dataset.json` (`schema_version` bump + migrate/check). Старые конфиги без секций → выключено по умолчанию.
- **Cache:** новые parsers — новые cache key компоненты (parser/version/options). Старые generations остаются валидны.
- **Миграция:** импорт — preview-first copy/adopt; без обязательной конвертации существующих файлов.

## 6. Безопасность / приватность / производительность

- **Безопасность:** плагин — исполняемый код (доверять дистрибутиву/установке, не директории данных). Excel/PDF — политика по макросам/формулам/embedded objects. Watch/scheduled — лимиты + audit.
- **Приватность:** сеть (URL fetch, Notion API, cloud LLM) — только opt-in с consent + documented data flow. Local-first default (P12, NFR-7).
- **Производительность:** парсинг больших PDF/XLSX — с лимитами (bytes/rows/depth/время/память). Watch — incremental (mtime+size fast-path + hash).

## 7. Benchmark / gate критерии

- На каждую фичу: подтверждённая боль + тестовый набор + privacy/egress/resource limits + benchmark + fallback.
- Плагины: allowlist + API version + contract tests пройдены; DATA_ROOT с кодом не исполняется.
- Форматы: contract tests (diagnostics/locations/limits/round-trip) пройдены.
- Импорт/watch/enrichment: preview-first + consent + audit проверены.

## 8. Что НЕ делать

- НЕ исполнять код из DATA_ROOT (P10). Плагин — только установленный + allowlist.
- НЕ делать `pluggy` ради абстрактной «расширяемости» без use case.
- НЕ делать watch/scheduled default без consent (P5, P12).
- НЕ делать import/AI enrichment молчаливой конвертацией/перезаписью (P6).
- НЕ копировать QMD processors как sandbox (это доверенный код, не sandbox).
- НЕ делать PDF/XLSX парсинг обязательным для MVP (opaque asset в MVP).

## 9. Связи

- Зависит от: MVP Этап 4 (E1 drivers + contract tests) + Этап 6 (write safety).
- Блокирует: ничего в MVP. `search-embeddings-vector.after.md` может использовать импортированные PDF/DOCX как источники, но не требует их.
- Связано с: `memory-llm-wiki.after.md` (enrichment/scheduled — часть memory-профиля), `sync-collab-export.after.md` (cloud importers/sync).
