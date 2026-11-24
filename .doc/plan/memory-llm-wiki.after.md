# Перспектива (НЕ сейчас): Memory / LLM Wiki профиль (Task/Plan/Idea, session, синтез)

**Статус:** FUTURE — не реализуется в MVP. Этот файл описывает, **как** memory-профиль вставится поверх generic record-операций MVP без превращения `doc_type` в task manager.
**Дата:** 24 ноября 2026 года.
**Связанные документы:** [`implementation-plan.md`](implementation-plan.md) §2 (порты E2/E3/E6/E7), §4 Этап 0/0.5 (scope gate), §5 (slice C/D); [`constitution.md`](constitution.md) §6.10, FR-6.10, G1–G4, C25–C28, C47–C49; [`competitive-analysis.md`](competitive-analysis.md) §4.3 (Karpathy, OpenKB, second-brain, claude-obsidian), §4.4 (Mem0/Zep/Letta), §4.6 (Tana/Capacities), §6 C25–C28.

---

## 1. Что это и зачем

Отдельный **memory/domain профиль** поверх generic `create/validate/list/filter/link/aggregate` MVP. Включает (по подтверждённой потребности, не всё сразу):

- **Task/Plan/Idea lifecycle:** статусы/переходы, due/overdue, priority, owner/assignee, recurrence, blocked-by, promote-idea-to-project, запросы open/overdue/due soon/by project/blocked.
- **Session continuity:** session/domain home, hot cache/current state, start-of-session bootstrap, crystallize сессии, разделение transient context vs durable memory.
- **LLM Wiki synthesis:** `raw/` immutable → `wiki/` синтез, ingest/query/lint, claim/evidence ledger, freshness/conflict, source/claim статусы.
- **Capture lifecycle:** `capture → triage/dedupe → confirm/merge/no-op → link → retrieve → update/complete/archive`.
- **Maintenance:** tag/alias registry, dedupe, daily notes/calendar, boards/dashboards, bundle-транзакции для многофайловых writes.

**Ценность:** агент помнит задачи/планы/идеи между сессиями и компилирует знания. **Цена:** сложная модель данных, lifecycle, транзакции, приватность (sensitivity/retention), риск «LLM-выводы = истина».

**Конкуренты-референсы:** Karpathy LLM Wiki (raw/wiki/index/log, ingest/query/lint), OpenKB (compile + lint + visualize), obsidian-second-brain (task/project/idea, daily, boards, graduate), claude-obsidian (transactions, source/claim ledgers), Basic Memory (MD canonical + watcher + MCP), Tana/Capacities (supertags/objects + queries), Mem0/Zep/Letta (vector/graph/state memory). Все показывают: memory — отдельная задача, не «включённый search».

## 2. Почему НЕ сейчас

1. **MVP — generic records, не task manager.** `doc_type: plan`/`idea` сам по себе не даёт сроков/приоритетов/переходов (конституция G1). Без отдельных схем/lifecycle/queries это обещание без реализации.
2. **Нужен отдельный scope gate:** подтвердить, что пользователю нужны именно задачи/планы/идеи с состоянием/сроками/связями/продолжением между сессиями (или именно компиляция wiki), и зафиксировать schemas/lifecycle/queries/acceptance-тесты до проектирования публичного API.
3. **Риски:** многофайловые writes без транзакций (G3), LLM-синтез без evidence (G2), auto-save всей переписки (приватность). Без bundle-транзакций и claim ledger — опасно.
4. **Ядро не должно делать скрытую LLM-компиляцию** (P5). Синтез — opt-in профиль с evidence workflow.

## 3. Архитектурные хуки в MVP (уже заложены)

| Хук | Что уже есть в MVP | Как переиспользуется |
|---|---|---|
| **E2 `TypeRegistry`** | `entity_type`/`relation_type` descriptors + JSON Schema | Новые `entity_type` (`task`, `idea`, `project`, `decision`, `source`, `session`) + `relation_type` (`blocks`, `belongs_to`, `derived_from`, `supports`, `contradicts`, `promoted_to`) как данные, не hard-coded классы |
| **E3 `Validator`** | Schema + relation + business validators | Новые validators: status transitions, due/timezone, recurrence, claim evidence/freshness (как отдельные validators, не LLM-совет) |
| **E6 `RecordStorage`/`GenerationStore`** | File-backed records + atomic generations | Bundle-транзакции поверх тех же `RecordId`/`ObjectRef`/`WritePlan`/`expected_hash`; generations остаются derived |
| **E7 `QueryEngine`** | Safe declarative AST + units/formula/provenance | Новые versioned operators для task-oriented queries (open/overdue/due soon/by project/blocked) + тесты на fixtures |
| **E9 `Hashing`/`Locking`** | SHA-256 + dataset-level lock + temp+replace | Расширить до operation-level transaction bundle (один approval digest на логическое изменение) + journal/rollback/recovery |
| **FR-6 capture** | Type-directed capture (1 новый файл) | Расширить до capture lifecycle (triage/dedupe/merge/no-op) как Skill workflow поверх тех же CLI-контрактов |

**Инвариант:** memory-профиль — **надстройка**, не замена ядра. Generic `create/validate/query` продолжают работать без профиля. Профиль не вводит истину в БД/вектор (P1) и не делает LLM-выводы истиной без evidence.

## 4. Пошаговый план внедрения (когда scope gate пройден)

### Шаг 1 — Scope gate (до кода)

1. Подтвердить цель: (a) «задачи/проекты/планы/идеи с состоянием/сроками/связями/продолжением» **или** (b) «агент компилирует wiki из источников» **или** (c) оба. Это разные задачи с разными критериями успеха (аудит §3.6).
2. Зафиксировать общий envelope (`id`, `type`, `created`, `updated`, `status`, `tags`, `source_refs`, `relations`), schema/version/custom fields, stable ID/alias policy, миграции.
3. Зафиксировать встроенные поля и переходы (минимум ниже), канонический источник истины (файл vs отдельная запись vs board — не три независимые копии), команды capture/list/update/query/archive.
4. Подготовить ожидаемые данные/relations + acceptance-тесты (fixtures) до проектирования публичного API.

### Шаг 2 — Task-профиль (минимум)

1. Поля: `status` + переходы (например `open → in_progress → done/archived`), `due` (timezone semantics), `priority`, `owner`/`assignee`, `project`, `dependencies`/`blocked-by`, `recurrence`, `completion_date`.
2. Связи: `belongs_to` (project), `blocks`/`blocked_by`, `derived_from`, `supports`/`contradicts`.
3. Запросы: open/overdue/due soon/by project/blocked — на fixtures, с provenance.
4. Тесты: status transitions (невалидный переход → diagnostic), due/overdue с timezone, recurrence, completion.

### Шаг 3 — Idea/Plan-профиль (минимум)

1. **Idea:** lifecycle `captured → exploring → validated → promoted/parked/archived` (имена настраиваемы), evidence/open questions, связь при продвижении (`promoted_to` → project).
2. **Plan/Project:** цель, owner, статус, срок/этапы, next action, decision links.
3. Тесты: promote-idea-to-project (создание project + связь + архив идеи), next action queries.

### Шаг 4 — Capture lifecycle + triage/dedupe

1. Реализовать `capture → triage/dedupe → confirm/merge/no-op → link → retrieve → update/complete/archive` как Skill workflow поверх CLI.
2. Реализовать поиск существующей Task/Idea/Project перед созданием дубликата (agent-behavior cases).
3. Правило: сохранять только выбранный пользователем scope; остальное — draft. Никакого auto-save всей переписки.

### Шаг 5 — Bundle-транзакции (до широких agent writes)

1. Реализовать operation-level transaction bundle: operation ID, один bundle на логическое изменение, expected hashes для всех touched paths, review/approval над точным планом, serialized apply, восстановление при сбое, проверка изменения в редакторе/sync, confinement путей/прав.
2. Реализовать single-writer/sync-aware policy (см. также `sync-collab-export.after.md`).
3. Тесты: crash mid-bundle → recovery; concurrent update → конфликт; partial apply запрещён.

### Шаг 6 — LLM Wiki / синтез (если нужен)

1. Реализовать immutable capture/manifest (`raw/`), source metadata/provenance, generated synthesis pages (`wiki/`), claim evidence/conflict/freshness policy, query citations, lint/report.
2. Реализовать claim ledger: source ledger + claim ledger, статусы принятия/оспаривания, независимость источников, valid-time vs recorded-time, freshness/review_due, политика «не разрешать конфликт автоматическим выбором».
3. Не сливать с детерминированным `check`; LLM-выводы не являются истиной без evidence workflow.
4. Тесты: contradictory/stale claims, дубликаты смысла, отсутствующие связи/источники, качество synthesis (не только механическая целостность).

### Шаг 7 — Session continuity (если нужен)

1. Реализовать session/domain home, hot cache/current state, start-of-session bootstrap, решения/открытые вопросы из разговора, crystallize сессии, разделение transient vs durable.
2. Реализовать sensitivity/retention rules, explicit scopes на приватные папки, отдельное согласие на сеть/транскрипцию/синхронизацию.
3. Тесты: bootstrap читает только нужное; crystallize сохраняет только выбранный scope; приватные папки не читаются без scope.

### Шаг 8 — Maintenance (tag registry, daily, boards)

1. Tag/alias registry/ontology, правила reuse tags, устойчивые aliases, duplicate-resolution workflow.
2. Daily notes/calendar, kanban/boards/dashboards — как views поверх тех же records (не отдельные копии истины).
3. Тесты: tag reuse, alias stability, board queries.

## 5. Данные и миграции

- **Schema:** новые `entity_type`/`relation_type` descriptors + schemas (versioned). Миграции — явные `migrate/check`, не silent rewrite. Старые records без новых полей → `unknown`/diagnostic, не догадка.
- **Канонический источник:** зафиксировать один источник истины на объект (файл). Board/dashboard — derived view, не вторая копия.
- **Backup:** текстовые файлы diff-ятся в Git; bundle-транзакции — с journal/rollback.

## 6. Безопасность / приватность / производительность

- **Безопасность:** те же containment/hash/post-validation + bundle-транзакции (E9). DATA_ROOT — недоверенные данные (P10). LLM-совет не подменяет validator.
- **Приватность:** sensitivity/retention, explicit scopes, consent на сеть/транскрипцию/синхронизацию (NFR-7). Никакого auto-save всего разговора или background job по умолчанию.
- **Производительность:** task-oriented queries — на fixtures с лимитами; session bootstrap — bounded (не вся база в контекст).

## 7. Benchmark / gate критерии

- Task queries (open/overdue/due soon/by project/blocked) — 100% на fixtures с provenance.
- Status transitions, promote-idea-to-project, session bootstrap, crystallize — agent-behavior cases пройдены (не засчитывать ответ из model memory без чтения root).
- Bundle-транзакции: crash recovery, concurrent conflict, partial apply запрещён.
- Синтез (если есть): contradictory/stale claims детектируются; каждый claim с evidence; конфликт не разрешается автоматически.
- Пилот: пользователи возвращаются к memory-workflow на реальных данных и называют повторяющуюся выгоду.

## 8. Что НЕ делать

- НЕ называть `doc_type: plan`/`idea` поддержкой task management без Шага 1–3 (конституция G1).
- НЕ делать скрытую LLM-компиляцию в core (P5). Синтез — opt-in профиль с evidence.
- НЕ автозаписывать всю переписку. Только выбранный scope, остальное — draft.
- НЕ делать три независимые копии истины (файл + board + БД).
- НЕ копировать obsidian-second-brain auto-writes/hooks/scheduled agents без транзакционного контроля.
- НЕ делать vector/graph DB истиной (P1). Memory — файлы + derived indexes.

## 9. Связи

- Зависит от: MVP Этап 4–6 (types/validation/records/relations/query/write safety) + scope gate (Шаг 1).
- Блокирует: ничего в MVP. Веб (`web-ui.after.md`) может показать boards/dashboards как views, но не требует memory-профиля.
- Связано с: `search-embeddings-vector.after.md` (semantic memory — opt-in), `mcp-adapter.after.md` (MCP tools для memory), `sync-collab-export.after.md` (single-writer/sync policy).
