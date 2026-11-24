# Перспектива (НЕ сейчас): Человеческий веб-интерфейс + публикация

**Статус:** FUTURE — не реализуется в MVP. Этот файл описывает, **как** веб вставится поверх CLI/API/снапшотов без дублирования истины.
**Дата:** 24 ноября 2026 года.
**Связанные документы:** [`implementation-plan.md`](implementation-plan.md) §2 (порты E8/E10), §4 Этап 7; [`constitution.md`](constitution.md) §6.12, FR-9, S10, S12, C30–C31, C56; [`competitive-analysis.md`](competitive-analysis.md) §4.1 (Obsidian, Quartz), §4.3 (OpenKB `visualize`), §4.5 (Open Notebook), §6 C30–C31.

---

## 1. Что это и зачем

Локальный веб-интерфейс поверх тех же данных и контрактов, что и CLI/агент:

- **Дерево папок** (иерархия по `dir_type`/папкам) + **карточки типизированных записей** (по `entity_type`).
- **Интерактивный граф связей** (typed edges + backlinks) с фильтрами по типам/полям/связям/датам.
- **Гибкий поиск** (по тексту/типам/полям/разделам/связям) + просмотр/редактирование записей + навигация по связанным объектам.
- **Визуальные настройки из типов:** цвет, иконка, вид карточки, отображение в графе — из `ui` metadata типа (FR-3.6, уже данные в MVP).
- **Публикация (опционально):** статический экспорт vault (digital garden, аналог Quartz) + `visualize` (интерактивный graph HTML, аналог OpenKB).

**Ценность:** человек видит базу красиво, фильтрует и редактирует без ручного редактирования файлов. **Цена:** отдельный UI-слой, API-поверхность, поддержка браузеров.

**Конкуренты-референсы:** Obsidian (граф/доски/плагины — зрелый UX, не копировать приложение), OpenKB `visualize` (graph.html: 3D/mind-map/radial), okf `serve`/`render` (live graph + static file), Quartz (static site из vault), Open Notebook (web app + REST API). Все показывают: UI — adapter, не истина.

## 2. Почему НЕ сейчас

1. **Нужны стабильные JSON-контракты CLI.** Веб читает snapshots и пишет через CLI/API; без стабильных `data`/`diagnostics`/`next_actions` и generations веб будет переделываться.
2. **CLI-first:** первичный пользователь MVP — агент. Веб без CLI — вторая копия истины (нарушение P1/P11).
3. **Входной критерий конституции:** CLI стабилен, machine-readable API/JSON контракты для нужных операций есть, понятно, что UI добавляет ценность поверх файлов/агента.

## 3. Архитектурные хуки в MVP (уже заложены)

| Хук | Что уже есть в MVP | Как переиспользуется |
|---|---|---|
| **E6 `GenerationStore`** | Atomic generations (`CURRENT.json` + `folders/documents/records/relations/diagnostics`) | Веб читает готовые snapshots (read-only); не строит собственный индекс |
| **E8 `WorkflowLookup`** | Whitelisted `workflow_id` → trusted Skill | Веб вызывает те же application use cases, что и CLI/Skill; нет обхода валидации |
| **E10 `OutputSerializer`** | JSON envelope + table/markdown | Добавить HTTP JSON API поверх тех же `data`/`diagnostics`; `next_actions` — как подсказки, не auto-execution |
| **FR-3.6 `ui` metadata** | `ui` (цвет/иконка/вид) + `agent_instructions` как неисполняемые данные в type descriptors | Веб читает `ui` из типов; не требует отдельной админки стилей |
| **FR-7 relations/graph** | Typed edges + derived graph/backlinks | Веб рендерит граф из `relations.json` + `relations graph` use case |
| **FR-5 bounded read** | Section/pointer/rows/fields + `truncated`/cursor | Веб показывает фрагменты, не полные документы по умолчанию |

**Инвариант:** веб никогда не редактирует файлы напрямую. Все writes — через валидированные CLI/API операции с `expected_hash` + post-validation (P6, P11).

## 4. Пошаговый план внедрения (когда gate пройден)

### Шаг 1 — API gate (до UI)

1. Зафиксировать HTTP JSON API поверх application-слоя: `GET /datasets`, `GET /folders`, `GET /documents`, `GET /records`, `GET /relations/graph`, `POST /records/preview`, `POST /records/apply`, `GET /search`, `GET /documents/:id/read`. Все — те же use cases, что и CLI.
2. Зафиксировать auth/permissions (локальный single-user в v1; multi-user — только в `sync-collab-export.after.md`).
3. Тесты: API contract tests (те же fixtures, что и CLI); `next_actions` не исполняются автоматически.

### Шаг 2 — Read-only веб (дерево + карточки + граф + фильтры)

1. Создать отдельный пакет `todoc-web/` (см. конституцию §11.3): `api.py` (тонкий HTTP-адаптер), `snapshots.py` (чтение `CURRENT` generation + cache), `ui/` (дерево, карточки, граф, фильтры).
2. Реализовать дерево папок (из `folders.json`), карточки записей (из `records.json` + `ui` metadata типа), граф связей (из `relations.json`), фильтры по типам/полям/связям/датам (те же фильтры, что и `docs search`/`records query`).
3. Реализовать просмотр bounded fragment (section/pointer/rows) + навигацию по связанным объектам.
4. Тесты: UI smoke tests на fixtures; cold-rebuild (удалить cache → веб пересобирает из файлов).

### Шаг 3 — Write-веб (редактирование через CLI/API)

1. Реализовать preview/diff + `--apply` эквивалент в вебе: показать `WritePlan` (target, patch/new content, expected/new hash, diff, validations) → явное подтверждение → apply через application-слой → post-validation → обновить generation.
2. Реализовать `docs new` / `records create` в вебе (те же шаблоны/валидация, что и CLI).
3. Тесты: concurrent update → конфликт; невалидная запись → оригинал нетронут; no-overwrite.

### Шаг 4 — Публикация (опционально)

1. Реализовать статический экспорт (аналог Quartz): Markdown vault + derived index → HTML + graph. Исходники остаются Markdown; экспорт — derived, удаляемый.
2. Реализовать `visualize` (аналог OpenKB): self-contained interactive graph HTML (`output/visualize/graph.html`).
3. Тесты: экспорт не меняет исходники; static site работает без `todoc`.

## 5. Данные и миграции

- **Schema:** веб не вводит новых схем данных. Читает `dataset.json` + generations + `ui` metadata. Изменения `ui` metadata — через type descriptors (versioned), не через веб-админку.
- **Миграция:** не требуется. Веб — новый adapter; старые DATA_ROOT работают без веба.
- **Backup:** веб не хранит вторую копию истины. Удаление веба не теряет данные (P1).

## 6. Безопасность / приватность / производительность

- **Безопасность:** веб — только локальный (bind `127.0.0.1` по умолчанию; `--bind` — явный opt-in). Все writes — через application-слой с containment/hash/post-validation (NFR-1). Нет shell/`eval` с user content.
- **Приватность:** local-first; без скрытых сетевых вызовов. Cloud-хостинг веба — только в `sync-collab-export.after.md` с consent.
- **Производительность:** веб читает snapshots (не сканирует файлы на каждый запрос); bounded projections + pagination как в CLI.

## 7. Benchmark / gate критерии

- CLI стабилен; JSON-контракты для нужных операций зафиксированы и покрыты contract tests.
- UI добавляет измеримую ценность поверх файлов/агента (пользовательское тестирование: дерево/граф/фильтры/редактирование быстрее, чем ручное редактирование).
- Веб не требует миграции данных и не хранит вторую копию истины (проверено cold-rebuild + удаление веба).
- Все writes в вебе проходят те же валидации, что и CLI (fixtures).

## 8. Что НЕ делать

- НЕ делать веб истиной (P1). Веб — adapter.
- НЕ редактировать файлы напрямую из веба в обход CLI/API (P11).
- НЕ копировать Obsidian-приложение (граф/доски/плагины/sync/мобильный) — интегрироваться, не конкурировать.
- НЕ делать веб обязательным для использования базы (P14).
- НЕ хранить в UI отдельную БД/копию данных.
- НЕ делать веб multi-user/sync в этой перспективе (см. `sync-collab-export.after.md`).

## 9. Связи

- Зависит от: Этап 5–7 MVP (generations, bounded read, relations/graph, `ui` metadata, JSON envelope).
- Блокирует: ничего в MVP. Публикация может использовать hybrid поиск (`search-embeddings-vector.after.md`), но не требует его.
- Связано с: `mcp-adapter.after.md` (тот же application-слой, другой транспорт), `sync-collab-export.after.md` (cloud/multi-user — отдельная перспектива).
