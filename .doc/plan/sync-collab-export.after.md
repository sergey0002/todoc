# Перспектива (НЕ сейчас): Sync, collaboration, export, backup

**Статус:** FUTURE — не реализуется в MVP. Этот файл описывает, **как** sync/collab/export вставятся поверх Git-friendly файлов без превращения `todoc` в hosted-сервис.
**Дата:** 24 ноября 2026 года.
**Связанные документы:** [`implementation-plan.md`](implementation-plan.md) §2 (порты E6/E9/E10), §4 Этап 5–6; [`constitution.md`](constitution.md) §6.13, FR-12, C32–C33, C46, C50, C55; [`competitive-analysis.md`](competitive-analysis.md) §4.1 (Obsidian Sync, SiYuan sync), §4.5 (AnythingLLM Live Sync), §6 C32–C33, C46, C50, C55, §8 портабельность.

---

## 1. Что это и зачем

- **Sync/backup:** Git (уже бесплатно в MVP) + cloud sync / LiveSync / S3/WebDAV (opt-in) + backup/restore как фича.
- **Collaboration:** multi-user, ACL/permissions, real-time co-editing, conflict handling.
- **Export:** JSON (уже в CLI) + Markdown view/projection + OKF bundle / static HTML / slides.
- **CI gates:** `validate --strict`, SARIF output, `eval` для retrieval (референс okf/Open Knowledge).

**Ценность:** совместное ведение базы, облачный бэкап, публикация, CI-проверки качества знаний. **Цена:** single-writer/conflict policy, ACL-модель, hosted-инфраструктура, форматы экспорта.

**Конкуренты-референсы:** Obsidian Sync ($8/mo, vault sync), SiYuan sync (one-time $64 или S3/WebDAV), AnythingLLM Live Document Sync beta (наблюдает отдельные файлы, re-embedding hourly/10 min), Open Knowledge Knowledge CI (GitHub Action, source baseline, starter eval, gates), okf SARIF + `--fail-on`, OpenKB `visualize`/`deck` (HTML/slides). Все показывают: sync/collab — отдельная сложная задача, не «включённая папка».

## 2. Почему НЕ сейчас

1. **MVP уже Git-friendly.** Текстовые файлы diff-ятся в Git; `todoc` не требует Git, но не мешает ему (FR-12.1). Cloud sync без single-writer/conflict policy — риск потери данных.
2. **Не аудитория первого слоя:** команды с сложными ACL/sync/multi-user — не целевой пользователь MVP (конституция §3.3).
3. **Нужны отдельные политики:** single-writer/sync protocol, conflict handling, ACL/privacy/redaction, retention. Без них — нельзя обещать «синхронизацию».
4. **Export HTML/slides** — без стабильных JSON-контрактов CLI будет переделываться (как веб).

## 3. Архитектурные хуки в MVP (уже заложены)

| Хук | Что уже есть в MVP | Как переиспользуется |
|---|---|---|
| **E6 `GenerationStore`** | Atomic generations + `dataset_id` + root-relative paths | Sync — синхронизация файлов + generations (derived), не истины в облаке. Cold-rebuild после sync — тот же тест, что и в MVP |
| **E9 `Hashing`/`Locking`** | SHA-256 + dataset-level lock + `expected_hash` | Расширить до single-writer policy + conflict detection (hash mismatch → конфликт, не silent overwrite) |
| **E10 `OutputSerializer`** | JSON envelope + table/markdown | Добавить SARIF serializer для `validate`/`lint` + HTML/slides exporters поверх тех же `data`/`diagnostics` |
| **FR-12.1 Git** | Текстовые файлы, diffable | Git — рекомендуемый механизм версионирования/бэкапа; `todoc` не строит VCS |
| **Config** | `dataset.json` + `dataset_id` | Добавить `sync`/`collab`/`export` секции (opt-in, выключено по умолчанию) |

**Инвариант:** sync/collab никогда не делает облако истиной (P1). Истина — файлы в DATA_ROOT; облако — копия/транспорт. Удаление sync не теряет данные.

## 4. Пошаговый план внедрения (когда gate пройден)

### Шаг 1 — Gate (до кода)

1. Подтвердить боль: multi-user/ACL/sync действительно нужны (не «было бы nice»), export-форматы выбраны, CI-gate нужен.
2. Зафиксировать single-writer/sync protocol, conflict handling, ACL/privacy/redaction, retention, backup/restore процедуру.
3. Подготовить acceptance-тесты (concurrent edit, conflict, restore).

### Шаг 2 — CI gates (v1, без sync)

1. Реализовать `validate --strict` (warnings → отказ CI) + SARIF output для `validate`/`lint` (референс okf).
2. Реализовать `eval` для retrieval (референс Open Knowledge: MRR/Recall@k/nDCG@k + embedding-uplift gate) + Knowledge CI (GitHub Action, source baseline, starter eval, gates).
3. Тесты: CI-gate на fixtures (битая ссылка/schema → отказ; чистая база → pass).

### Шаг 3 — Export (v1)

1. Реализовать Markdown view/projection export (те же bounded projections, что и CLI) + OKF bundle export (опциональный профиль).
2. Реализовать static HTML export (аналог Quartz/OpenKB `visualize`/`deck` — только при доказанной боли; slides — отдельно).
3. Тесты: экспорт не меняет исходники; static site работает без `todoc`.

### Шаг 4 — Cloud sync / LiveSync (opt-in)

1. Реализовать sync (S3/WebDAV/cloud) поверх файлов + generations: upload/download с hash-проверкой, conflict detection (hash mismatch → явный конфликт, не silent overwrite), single-writer policy.
2. Реализовать LiveSync/watch (наблюдение + авто-sync) только с consent + лимитами. Референс: AnythingLLM beta (отдельные файлы, не целые папки) — не копировать ограничения без проверки.
3. Тесты: concurrent edit → конфликт; offline → queue + sync при появлении сети; cold-rebuild после sync.

### Шаг 5 — Multi-user / ACL (opt-in)

1. Реализовать ACL/permissions (read/write scopes на папки/типы), audit log, redaction для search/read/generated summaries/cache.
2. Реализовать real-time co-editing только при доказанной боли (иначе — file-level sync + conflicts).
3. Тесты: ACL enforced (валидность схемы ≠ право читать); audit полон; redaction работает.

### Шаг 6 — Backup/restore как фича

1. Реализовать `todoc backup/restore` (или документировать Git + sync как backup): snapshot + restore + cold-rebuild проверка.
2. Тесты: backup → удалить derived index/cache → restore → перескан/поиск/query работают.

## 5. Данные и миграции

- **Schema:** добавить `sync`/`collab`/`export` секции в `dataset.json` (`schema_version` bump + migrate/check). Старые конфиги без секций → выключено по умолчанию.
- **Миграция:** sync — новая копия/транспорт; без миграции данных. Export — derived, удаляемый.
- **Backup:** Git + sync — механизмы; `todoc` не строит VCS и не хранит вторую копию истины.

## 6. Безопасность / приватность / производительность

- **Безопасность:** sync/collab — только с hash-проверкой + conflict policy + audit. ACL — отдельно от валидности схемы (NFR-1). Нет shell/`eval` с user content.
- **Приватность:** cloud sync — только с явным consent + documented data flow + retention. Sensitivity/retention rules, explicit scopes на приватные папки (NFR-7).
- **Производительность:** sync — incremental (hash-based); export — bounded (не вся база в один файл без лимитов).

## 7. Benchmark / gate критерии

- Single-writer/conflict policy зафиксирована и покрыта тестами (concurrent edit → конфликт, не потеря данных).
- ACL enforced (невалидный доступ → отказ, даже при валидной схеме).
- CI-gate работает на fixtures (битая база → отказ).
- Export не меняет исходники; static site работает без `todoc`.
- Backup/restore + cold-rebuild пройдены.

## 8. Что НЕ делать

- НЕ делать облако истиной (P1). Облако — копия/транспорт.
- НЕ обещать «синхронизацию» без single-writer/conflict policy.
- НЕ делать multi-user/ACL в MVP (не аудитория первого слоя).
- НЕ копировать Obsidian Sync / AnythingLLM beta без проверки ограничений (отдельные файлы vs целые папки, re-embedding расходы).
- НЕ делать export HTML/slides без стабильных JSON-контрактов CLI.
- НЕ строить VCS (Git уже есть).

## 9. Связи

- Зависит от: MVP Этап 5–6 (generations, write safety, JSON envelope) + Этап 7.5 (CI/SARIF/eval).
- Блокирует: ничего в MVP. Веб (`web-ui.after.md`) может быть cloud-hosted только через эту перспективу.
- Связано с: `memory-llm-wiki.after.md` (single-writer/sync policy для bundle-транзакций), `mcp-adapter.after.md` (remote MCP — только с consent), `plugins-formats-import.after.md` (cloud importers).
