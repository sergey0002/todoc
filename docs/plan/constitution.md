# todoc — Конституция: итоговый продукт, требования, концепция и принципы

**Статус:** нормативный документ-основа. При конфликте с `plan.md` приоритет имеет этот файл; `plan.md` остаётся подробным инженерным наброском и историей решений.
**Дата:** 24 ноября 2026 года. **Версия:** 0.1 (первая конституция, до реализации).
**Связанные документы:** [`../plan.md`](engineering-draft.md) — инженерный план; [`competitive-analysis.md`](competitive-analysis.md) — конкурентный анализ, CLI-вход/выход, мастер-список возможностей и сравнительные таблицы; [`../docs/research/knowledge-base-comparative-audit.md`](../research/knowledge-base-comparative-audit.md) — статический аудит Agent Skills; гайды `docs/guides/cli-for-agents.md`, `docs/guides/mcp-for-agents.md`, `docs/guides/markdown-knowledge-for-agents.md`, `docs/research/mcp-cli-agents.md` — принципы CLI/MCP/Markdown для агентов.

> **Как читать.** Слова **MUST / SHOULD / MAY** — нормативные: MUST — обязательно для соответствия конституции, SHOULD — рекомендуется, отклонение требует обоснования, MAY — опционально. Идентификаторы требований: **FR** (функциональные), **NFR** (нефункциональные), **P** (принципы), **S** (сценарии). Все пути в примерах — POSIX-style relative от `DATA_ROOT`, если не сказано иначе.

---

## 0. Аудит `plan.md`: цели, возможности, перспективы

### 0.1. Что обещает `plan.md` (цели)

`plan.md` описывает **переносимый типизированный knowledge substrate для агентов с будущим человеческим веб-интерфейсом**, а не «ещё один Obsidian» и не RAG-чат. Ядро гипотезы:

1. Пользователь **один раз описывает типы** (`note`, `research`, `link`, `plan`, `product`, `person`, `workout`, `glossary-entry` и любые свои): поля, JSON Schema, шаблоны, место создания, правила именования, допустимые связи, обязательные разделы, `ui`-метаданные (цвет/иконка/вид) и неисполняемые `agent_instructions`.
2. Затем он просто говорит агенту: «сохрани ссылку», «сделай ресерч конкурентов», «создай тип продукта и заполни его», «сохрани план» — и доверенный Skill + CLI выполняют **предсказуемый проверяемый workflow**: выбрать тип → уточнить пропуски → вычислить путь/имя → preview → валидация → create-only запись → перечитывание → индекс.
3. Источник истины — **обычные файлы в папке пользователя** (Markdown/CSV/JSON + вложения). Граф, полнотекстовый индекс, кэш и будущий веб — **производные представления**, пересобираемые из файлов.
4. Сначала продукт решает задачу **для агента** (быстро и проверяемо сохранять, связывать, искать, читать ограниченно). Поверх того же CLI/кэша позже добавляется **красочный веб-интерфейс**: дерево папок + граф связей + фильтры по типам/полям + редактирование через те же write-контракты.

### 0.2. Возможности, уже заложенные в плане

| Область | Что предусмотрено | Статус в плане |
|---|---|---|
| DATA_ROOT и портабельность | Явный `--root` (повторяемый), `dataset_id`, только relative paths, multi-root изоляция, cold-rebuild | Спроектировано, не реализовано |
| Типы и маршрутизация | `format` ≠ `doc_type` ≠ `dir_type` ≠ `entity_type` ≠ `relation_type`; rules + inheritance + `explain-path`; reserved names (`plan/`, `.research/`, `architecture/`, `constitution/`, `harness/`, `glossary/`) | Спроектировано |
| Форматы | Markdown (CommonMark + Obsidian-subset), CSV, JSON; будущие YAML/XLSX/PDF/SQLite через малые контракты | Спроектировано |
| Валидация и диагностика | Stable codes, точные locations (row/column, JSON Pointer, line/column/anchor), `suggested_fixes`, preview/diff, `expected_hash`, post-validation | Спроектировано |
| Поиск и чтение | Progressive disclosure: counts/outline → snippets → bounded fragment; `--budget`, `truncated`, cursor, provenance/hash | Спроектировано |
| Записи и запросы | `records create/query/aggregate/list/read`, typed relations, graph/backlinks, units/formula/provenance | Спроектировано |
| Безопасность | No code/prompt из DATA_ROOT, allowlist workflow IDs, no-overwrite, containment, limits, offline-by-default | Спроектировано |
| Индексы | Atomic generations (`CURRENT.json`), JSON snapshots, per-doc cache, invalidation по digest | Спроектировано |
| Skill | Короткий родительский `SKILL.md` + прямые `references/*.md`, progressive disclosure | Спроектировано |
| Веб-интерфейс | Отдельный adapter поверх CLI/API/снапшотов; иерархия + граф + фильтры; `ui`-метаданные из типов | Зарезервировано как Этап 9 |

### 0.3. Перспективы (что план сознательно оставляет допустимым, но не обещает в MVP)

- **Typed capture для любых доменов:** `Task`/`Idea`/`Project`/`Workout` как пользовательские `entity_type` + generic `create/validate/list/filter/link/aggregate`. Богатые lifecycle/dashboards — отдельные профили/Skills, не core.
- **Search-эволюция:** offline lexical → graph traversal → embeddings/hybrid fusion → reranking → external vector/graph adapters. Порты заложены, провайдеры — только opt-in после benchmark/privacy gate.
- **MCP-адаптер:** тот же application-слой отдаётся как MCP tools/resources (см. `docs/guides/mcp-for-agents.md`). CLI остаётся первичным контрактом; MCP — транспорт, а не второй источник истины.
- **Веб-интерфейс:** дерево + граф + фильтры + редактирование без дублирования истины. Входной критерий — стабильные JSON-контракты CLI.
- **Memory-профиль / LLM Wiki:** накопительная компиляция `raw/ → wiki/`, claim/evidence ledger, session bootstrap — **отдельный профиль**, не «включённый search». См. §0.5.
- **Плагины и форматы:** entry-point plugins (allowlist), YAML/XLSX/PDF, watch mode, import/AI enrichment — только по подтверждённой боли.

### 0.4. Сильные стороны плана

1. **Правильное разделение:** Skill (диалог) / CLI (контракт) / DATA_ROOT (данные) / derived index (кэш). Ни один слой не дублирует чужую ответственность.
2. **Source-native честность:** существующие CSV/JSON/Markdown не переписываются молча; create-only для новых записей; review-first для правок. Это реальное отличие от компилирующих RAG/wiki-систем.
3. **Проверяемость:** точные locations, hash, `next_actions` как `argv`-подсказки (не auto-execution), JSON envelope, exit codes, benchmark-пороги. Продукт можно тестировать, а не «верить модели».
4. **Портабельность как архитектура:** relative paths, `dataset_id`, rebuildable index, Obsidian-совместимость без зависимости от Obsidian.
5. **Расширяемость без монолита:** малые Protocol/ports (reader/writer/validator/retriever/ranker/renderer), SOLID без матрицы классов `CsvResearchDocument` и т.п.
6. **Честные границы:** план прямо говорит, что это гипотеза, а не доказанный moat; требует discovery gate и сравнения с baseline (`rg`, Obsidian, QMD, Open Knowledge, OpenKB).

### 0.5. Пробелы, риски и что меняет эта конституция

| # | Пробел/риск из аудита | Решение в конституции |
|---|---|---|
| G1 | `doc_type`/`entity_type` сами по себе **не дают** Task/Plan/Idea-менеджера: нет статусов/переходов, due/overdue, owner, recurrence, promote-idea-to-project | §6.7 + §12: memory/domain-профили — **отдельный scope с собственными схемами и acceptance-тестами**; в MVP только generic record-операции. Запрещено называть `doc_type: plan` поддержкой task management |
| G2 | Нет накопительной памяти Karpathy-стиля: `raw/ → wiki/`, synthesis, claim ledger, freshness/conflict, session crystallize | §6.10: отдельный **LLM Wiki / memory профиль** (опциональный, после MVP). Core не делает скрытую LLM-компиляцию |
| G3 | Нет транзакций для многофайловых agent writes, single-writer/sync policy | §6.8 + NFR: MVP — только create-only (1 новый файл) + review-first patch (1 файл, hash-protected). Многофайловые bundle-транзакции — gate перед широкими записями |
| G4 | Нет tag/alias registry, dedupe/triage очереди, session bootstrap | §6.7: triage/dedupe — SHOULD для capture-профиля; tag registry — MAY после MVP. Не блокирует MVP |
| G5 | Риск «generic framework без сценария» | §12 Этап 0: discovery gate обязателен. Один vertical slice (`link` capture **или** `research → product → plan` **или** `workout` aggregate) выбирается до кода |
| G6 | Схема валидирует форму, но не смысл (units, timezone, формула агрегации) | FR-7.x: units/timezone/formula — часть type metadata + versioned query contract; unknown → abstain/clarify, не догадка |
| G7 | Конкурентный ландшафт шире, чем в плане (Basic Memory, Tana/Capacities, Mem0/Zep/Letta, Open Notebook, RAGFlow/Dify и др.) | См. `competitive-analysis.md`: мастер-список возможностей, таблица, портабельность, выводы «копировать / не копировать / интегрироваться» |
| G8 | Нет явного MCP-контракта в плане (CLI-first) | §6.11: MCP — SHOULD как тонкий adapter поверх application-слоя после стабилизации CLI; не второй API с собственной семантикой |
| G9 | Веб-интерфейс описан как «красочный», но без контракта | §6.12: веб — отдельный adapter, читает snapshots, пишет только через CLI/API; `ui`-метаданные — данные, не код |

**Вердикт аудита:** план концептуально готов как спецификация MVP для **source-native validator + typed records + bounded search/read CLI**. Он **не готов** как «переносимая память с задачами/планами/идеями» и не должен так называться без отдельного memory-профиля. Конституция ниже фиксирует эту границу как норму.

---

## 1. Миссия и позиционирование

### 1.1. Миссия

> Дать человеку и его агенту **одну переносимую папку знаний**, где пользователь сам описывает типы объектов, а агент **предсказуемо и проверяемо** сохраняет, связывает, проверяет и находит их — без сервера, облака и скрытых LLM-вызовов в ядре.

### 1.2. Что такое `todoc`

- **File-native typed knowledge substrate:** обычные файлы + декларативные типы/схемы/шаблоны/отношения + безопасный generic CLI + доверенный Skill.
- **CLI-first, agent-first:** первичный пользователь — агент (человек — второй, через файлы/Obsidian/будущий веб).
- **Local-first и offline-by-default:** ядро работает без сети и без модели. Сеть/модель — только opt-in адаптеры с consent.
- **Производные индексы, а не вторая база:** граф/поиск/веб пересобираются из файлов.

### 1.3. Что `todoc` НЕ является

- НЕ клон Obsidian / «второй мозг» / RAG-чат / hosted-сервис.
- НЕ универсальная онтология: core не угадывает смысл произвольного JSON.
- НЕ автономная LLM-компиляция базы в MVP (нет скрытого ingest/synthesis).
- НЕ graph database и НЕ vector DB в MVP (нет обязательной внешней инфраструктуры).
- НЕ task manager / CRM / календарь в MVP (только generic record-операции поверх пользовательских типов).

### 1.4. Рабочая гипотеза ценности

> «Опиши свои знания как переносимые типизированные файлы; подключи к типам проверяемые workflows; сохрани записи, связи и схемы в обычной папке; используй общий CLI для безопасного capture, validate, query, aggregate и bounded read».

Это гипотеза о **связке** (типы + маршрутизация + type-directed workflows + schema-checked writes + explicit relations/query + swappable indexes), а не утверждение об уникальности каждого компонента. Доказательство — только discovery gate (§12, Этап 0) на реальных папках.

---

## 2. Принципы (конституционные, MUST)

| ID | Принцип | Правило | Почему / нарушение |
|---|---|---|---|
| P1 | **Файлы — истина** | Source files в DATA_ROOT — единственный source of truth. Индексы/кэш/граф/веб — производные и удаляемые. | Без этого нет портабельности и Git-версионирования. Нарушение: «истина в SQLite/векторной БД» |
| P2 | **Портабельность по умолчанию** | Только relative paths в конфигах/индексах; `dataset_id` переживает move/rename; cold-rebuild без ручного фикса | Папка копируется/бэкапится/версионируется целиком. Нарушение: абсолютные `/home/...` в конфиге |
| P3 | **Декларативность типов** | Типы/схемы/шаблоны/отношения/queries — JSON-данные. Никакого Python/shell/prompt-кода в DATA_ROOT | Данные не исполняются. Нарушение: `python: module:func` в type.json |
| P4 | **Разделение измерений** | `format` (синтаксис) ≠ `doc_type` (семантика документа) ≠ `dir_type` (роль папки) ≠ `entity_type` (запись) ≠ `relation_type` (связь) ≠ query/view | Расширение `.md` не выбирает смысл; папка `plan/` не переклассифицирует каждый файл молча |
| P5 | **Детерминированное ядро** | Scan/check/validate/search/read/query — без скрытых LLM/сетевых вызовов. Модель — только в Skill-диалоге и opt-in адаптерах | Проверяемость и воспроизводимость. Нарушение: «поиск через LLM» по умолчанию |
| P6 | **Review-first запись** | Существующие источники read-only в MVP. Разрешены только: (a) новый Markdown draft, (b) create-only новый JSON record, (c) preview/diff + явный `--apply` с `expected_hash` | Нет молчаливой перезаписи. Нарушение: auto-save всей беседы |
| P7 | **Bounded context** | Каждый ответ — counts/outline → snippets → fragment; `--budget`, `truncated`, cursor, provenance/hash обязательны | Агент не получает всю базу. Нарушение: экспорт полного корпуса в контекст |
| P8 | **Точные locations** | Каждая диагностика/хит несёт root-relative path + row/column / JSON Pointer / line/column/anchor + hash + severity | Ошибка без места — не ошибка, а шум. Нарушение: «где-то в файле есть битая ссылка» |
| P9 | **Явные связи** | Typed edges хранятся в источнике (record/front matter), валидируются (endpoint types/cardinality), индексируются как derived graph/backlinks | Граф пересобирается; нет дрейфующей graph DB. Нарушение: связи только в кэше |
| P10 | **Доверие — только установленному коду** | Исполняемый код — только из установленного пакета/Skill. DATA_ROOT — недоверенные данные (включая описания типов и значения полей) | Защита от prompt injection и RCE. Нарушение: исполнение `workflow` из DATA_ROOT |
| P11 | **CLI — контракт, Skill — диалог** | CLI владеет валидацией/правами/записью. Skill выбирает тип, задаёт вопросы, вызывает CLI. MCP/веб — тонкие адаптеры поверх application-слоя | Один смысл — много транспортов. Нарушение: бизнес-логика в `SKILL.md` или в MCP-сервере |
| P12 | **Offline-first, opt-in для сети/модели** | Default — offline lexical/path/metadata. Embeddings/vector/graph/rerank/fetch — opt-in с privacy/egress review, benchmark и fallback | Нет сюрпризов приватности и стоимости. Нарушение: тихая отправка документов в облако |
| P13 | **Объяснимость** | `explain-path`, `types guide`, `next_actions` (argv-массив) показывают, какое правило сработало и что делать дальше. Неоднозначность → diagnostic/clarify, не догадка | Пользователь и агент видят причину. Нарушение: «магическая» классификация |
| P14 | **Совместимость без зависимости** | DATA_ROOT открывается как Obsidian vault (`.md` + YAML + relative links); Obsidian/OKF — опциональные профили, не runtime-зависимости | Не ломать существующие папки. Нарушение: «установите Obsidian для работы CLI» |

---

## 3. Аудитория, персонажи и не-аудитория

### 3.1. Целевая аудитория (первый пользователь)

Человек, который **просит агента поддерживать собственные структурированные знания** и хочет: переносимые файлы, пользовательские схемы, точные запросы/агрегации, явные источники. Примеры: разработчик/аналитик с Markdown + CSV/JSON; исследователь конкурентов; автор личных логов (тренировки, проекты, решения, люди/термины); maintainer базы знаний для агента.

### 3.2. Персонажи

| Персонаж | Задача | Что получает от `todoc` |
|---|---|---|
| **A. Агент (первичный)** | Сохранить/найти/проверить/прочитать без перегруза контекста | Стабильный CLI + JSON envelope + bounded projections + `next_actions` |
| **B. Владелец папки (человек)** | Описать типы один раз, потом просто давать команды | Type descriptors + шаблоны + `types guide` + Obsidian-просмотр |
| **C. Рецензент/CI** | Убедиться, что база не битая и не дрейфует | `check/validate` + diagnostics + eval + exit codes |
| **D. Будущий читатель веба** | Смотреть дерево/граф/фильтры, редактировать визуально | Веб-адаптер поверх тех же контрактов (Этап 9) |

### 3.3. Не-аудитория первого слоя

- Команды с сложными ACL/sync/multi-user (нужны отдельные профили).
- Пользователи, которым прежде всего нужны polished dashboards/мобильный UI (это Obsidian/Notion/Tana/Capacities — см. competitive analysis).
- Те, кто хочет полностью автономную LLM-компиляцию знаний (это LLM Wiki / OpenKB / RAG-платформы — отдельный профиль).
- Те, кому нужен только «чат по PDF» (это Khoj/AnythingLLM/Open Notebook — интегрироваться, не конкурировать).

### 3.4. Jobs-to-be-done (JTBD)

1. «Сохрани ссылку/заметку/ресерч/план так, чтобы потом нашлось и было связано».
2. «Проверь папку: где битые ссылки, неверные схемы, дубли ID — с точным местом».
3. «Найди все X, где поле Y = Z и связано с W, и покажи только нужное».
4. «Посчитай агрегат по моим записям — с формулой, единицами и источниками».
5. «Перенеси папку на другой путь/машину — и всё работает».
6. «Открой папку в Obsidian и посмотри как человек».

---

## 4. Варианты применения (сценарии S)

Каждый сценарий — проверяемый workflow поверх одних и тех же примитивов. Типы `note/research/link/plan/product` — **примеры пользовательских типов**, не hard-coded домены core.

### S1. Сохранить ссылку (`link` capture)

Пользователь: «сохрани ссылку https://…». Агент: выбирает `entity_type=link`, читает type config, выполняет предпромптенный workflow типа (fetch страницы → title/описание/ключевые пункты/теги → предложение выжимки → связи к активному `research`/`product`), показывает preview записи и пути. CLI валидирует схему + связи и создаёт **новый** файл. После этого ссылка доступна в поиске, графе и вебе.
*Требует:* FR-6.1 (capture), FR-6.5 (external fetch policy как opt-in), FR-5.2 (create-only).

### S2. Конкурентный ресерч (`research → product → plan`)

Пользователь: «произведи ресерч конкурентов для todoc и выяви уникальные свойства/возможности». Агент создаёт `research` запись (цель, вопросы, источники, выжимки, выводы), для каждого продукта создаёт/обновляет `product` сущности (название, URL, возможности, сильные/слабые стороны, источники), связывает их с `research`, сохраняет ссылки, затем генерирует типизированный `plan` по структуре из конфига типа `plan` (обязательные разделы, принципы, связи).
*Требует:* FR-6.1–6.4, FR-7 (relations/graph), FR-8 (query/aggregate).

### S3. Сохранить план (`plan`)

Пользователь описывает идею плана. Агент использует конфиг `plan`: проверяет обязательные разделы/принципы, связанные ресерчи/ссылки/продукты, сохраняет в папку по правилам маршрутизации (`**/plan/` + template).
*Требует:* FR-3 (dir profiles), FR-6.3 (required sections/templates).

### S4. Подключить существующую папку без миграции

`todoc init --root ./knowledge` создаёт `.todoc/` конфиг/типы-шаблоны; сканирование **не перемещает/не копирует/не редактирует** существующие источники. Непарсируемые бинарные assets учитываются как opaque relative targets.
*Требует:* FR-1, FR-4.

### S5. Проверить и починить (QA)

`check/validate` выдаёт стабильные diagnostics с locations; `fix --preview` показывает diff; `--apply` — только с `expected_hash` + post-validation. Неоднозначное исправление не применяется автоматически.
*Требует:* FR-5.3–5.5.

### S6. Найти и прочитать ограниченно

`docs search --type adr --query "refresh token" --budget 1200` → top-k snippets с path/line/hash → `docs read --id … --section "Decision"`. Агент видит counts/outline сначала, полный текст — только после выбора ID.
*Требует:* FR-5.6–5.8.

### S7. Запросить и агрегировать записи

Пример: все `workout` Сергея за месяц, только `muscle_groups contains triceps`, сумма `reps × weight_kg` в `kg·reps`. CLI возвращает формулу, выборку IDs, paths/JSON Pointers, timezone/units, статус полноты. Неизвестная схема/метрика → abstain/clarify.
*Требует:* FR-8.

### S8. Личный лог (`workout` / `person`)

Пользователь: «сохрани тренировку». Skill уточняет только отсутствующие обязательные поля (дата, человек, упражнения, подходы/повторы/вес + единицы), разрешает ссылку на стабильный ID человека, вычисляет путь/имя из шаблона, просит подтверждение для неоднозначного маршрута. CLI создаёт новый JSON record без перезаписи.
*Требует:* FR-6.1, FR-8.1.

### S9. Глоссарий / ADR / проектные документы

`glossary-entry` может жить в любом месте (явный front matter/rule), а не только в `glossary/`. `adr` — Markdown `doc_type` с собственной схемой/вью/workflow. Папка `architecture/`/`plan/` даёт контекст, но не переклассифицирует молча каждый вложенный файл.
*Требует:* FR-3.

### S10. Человекский просмотр через веб (будущее)

Локальный сайт: дерево папок, клик на тип `research` → все исследования, фильтр «связано с `product:todoc`», граф связей, редактирование — всё через CLI/API, без второй копии истины. Визуал (цвет/иконка/вид карточки) — из `ui`-метаданных типа.
*Требует:* FR-9 (веб-адаптер), FR-3.6 (`ui` metadata).

### S11. MCP-доступ для агента (будущее)

Тот же application-слой отдаётся как MCP tools (`search`, `read`, `records_query`, `records_create_preview` и т.д.) + resources (документ/фрагмент/схема). CLI и MCP согласованы по статусам/безопасности, но не копируют формат вывода буквально.
*Требует:* FR-10.

### S12. Публикация / digital garden (опционально, после MVP)

Статический экспорт vault (аналог Quartz) из тех же файлов + derived index. Не часть MVP; не должен требовать миграции данных.
*Требует:* FR-9.4 (MAY).

---

## 5. Концепция и модель данных

### 5.1. Пять независимых измерений

| Измерение | Пример | Кто задаёт поведение |
|---|---|---|
| **Формат** | `json`, `markdown`, `csv` | Trusted parser/writer adapter; синтаксис + locations, не смысл |
| **Тип документа** | `adr`, `glossary-entry`, `research-note` | Declarative `doc_type` + schema/view + optional trusted workflow |
| **Тип папки / профиль** | `plan`, `research`, `glossary` | Directory descriptor + explainable path/basename/glob rules + inherited context |
| **Тип сущности/записи** | `note`, `research`, `link`, `workout`, `person`, `product`, `plan` | User-authored `entity_type`: JSON Schema, field metadata, template/path policy, required sections, optional agent instructions, UI metadata |
| **Тип связи** | `performed_by`, `derived_from`, `supports`, `contradicts` | Declarative relation descriptor: source/target kind+type, cardinality, dangling policy |
| **Запрос/представление** | filter, projection, `sum`, month bucket, Markdown view | Versioned safe query contract + registered operations; вывод — проекция с provenance, не копия истины |
| **Хранение/индекс/поиск** | source files; derived JSON snapshots/lexical/graph cache | Storage/retrieval/ranking/rendering ports; индексируется/меняется, не определяет семантику |

**Ключевые правила:**
- Расширение выбирает parser, а не смысл. `**/plan/` назначает папке тип `plan`, но **не** делает каждый JSON внутри `entity_type=plan`.
- Одна JSON-запись = один файл в первом slice (stable `record_id` + `entity_type` в теле). Файл может переезжать без переписывания references. Путь — location, не identity.
- Typed edges хранятся рядом с owning record (или в front matter); CLI валидирует и индексирует как пересоздаваемый graph/backlink view. Markdown links могут становиться нетипизированными `links_to` edges.
- Начальный граф — данные + локальный derived index, **не** обязательная graph DB.

### 5.2. Слои пакета (SOLID/OOP)

1. **Domain** — контракты без CLI/filesystem: `DatasetId`, `DocumentId`, `RecordId`, `ObjectRef`, `TypedRecord`, `RelationRef`, `QuerySpec`, `Projection`, `Diagnostic`, `ValidationReport`, `SearchHit`, `WritePlan`.
2. **Application/use cases** — `ScanDataset`, `ResolveProfiles/Types`, `CreateRecord`, `ValidateRecord`, `ResolveRelations`, `QueryRecords`, `AggregateRecords`, `SearchObjects`, `ReadProjection`, `ApplyReviewedWrite`, `GenerateTypeReference`.
3. **Ports/Protocols** — format reader/writer, registry/config loader, schema/semantic validator, safe query/metric evaluator, record storage, relation resolver/index, atomic generation store, candidate retriever, filter/ranker/fusion/reranker, context renderer, workflow-ID lookup, hashing/locking.
4. **Adapters** — Click CLI, `pathlib`/`os.scandir`, JSON/CSV/Markdown codecs, JSON Schema validator, file-backed record store, JSON snapshots, optional SQLite FTS/QMD/vector/graph connectors, explicit model reranker.
5. **Agent Skill** — trusted диалог: classify intent → choose type → ask missing → prepare/preview → call CLI → explain. Не дублирует validator/query logic, не получает filesystem authority.

Зависимости направлены внутрь: `CLI/Skill/MCP/Web → application → ports`. Domain/application не импортируют Click, `pathlib.Path`, конкретный search provider или структуру `.todoc`. CLI — authority для containment, schema/types, stable IDs, relation checks, safe query evaluation и writes; агент/модель только координирует.

**SOLID без избыточной иерархии:** S — одна ответственность на слой; O — новый формат = новый driver + регистрация, не `if/elif` везде; L — все drivers проходят общий contract test; I — `FormatReader` ≠ `FormatWriter`, read-only типу не нужен фиктивный writer; D — use cases зависят от Protocol, concrete adapters — через composition root. Запрещено: матрица классов `CsvResearchDocument`/`JsonResearchDocument`/…

### 5.3. Поисковый pipeline

`filter/scope → candidate retrieval (lexical; позже vector/graph) → fusion/rank → optional rerank → bounded projection`. Default — offline lexical/path/metadata. Внешние embeddings/vector DBs/graph stores/model rerankers — opt-in adapters с consent, benchmark, budget и fallback. `RetrievalBackend`/`Ranker`/`Reranker`/`Renderer` — отдельные порты; замена движка не меняет `SearchHit` contract.

---

## 6. Функциональные требования

### 6.1. DATA_ROOT, init и портабельность (FR-1)

- **FR-1.1 (MUST):** CLI принимает один или несколько явных `--root PATH` (повторяемый флаг) + документированную `TODOC_ROOT` для одного root. CWD не становится неявным источником config/типа. Каждый root — отдельный `dataset_id`, config/index namespace, identity space.
- **FR-1.2 (MUST):** `todoc init --root ./knowledge` создаёт только локальные control files/types/templates в DATA_ROOT (`.todoc/dataset.json`, каталоги типов/rules/templates/queries). Не устанавливает Skill, не перемещает/копирует данные, не сканирует автоматически без команды.
- **FR-1.3 (MUST):** Существующая папка подключается **без обязательной миграции/конвертации**. Исходные документы и вложения остаются источником истины. Непарсируемые бинарные assets не читаются как текст, но сохраняются как relative targets.
- **FR-1.4 (MUST):** В `.todoc/` и индексах — только relative paths (POSIX-style). Абсолютный путь root не сохраняется как identity. `dataset_id` сохраняется при move/rename. Перенос целиком + удаление derived index/cache → cold-rebuild без ручного фикса.
- **FR-1.5 (MUST):** Multi-root операции не смешивают конфиги/ID. Каждый результат маркируется `dataset_id`. Write/record-create требуют однозначного выбора root/dataset. Cross-dataset relations в MVP запрещены по умолчанию.
- **FR-1.6 (SHOULD):** Поддержка `inherit`/`separate`/`stop` для вложенных проектов (наличие `.git`/`pyproject.toml` само по себе не создаёт новый scope). Двойная индексация одного файла запрещена или диагностируется как конфликт.

### 6.2. Типы, правила и маршрутизация (FR-3)

- **FR-3.1 (MUST):** Раздельны `format`, `doc_type`, `dir_type`, `entity_type`, `relation_type`. Формат никогда не служит достаточным семантическим правилом.
- **FR-3.2 (MUST):** Пользователь описывает типы декларативно (JSON): допустимый формат, JSON Schema/front-matter policy, обязательные поля, units/enums, naming/location template, compact/full views, допустимые typed relations, `ui` metadata, `agent_instructions` (неисполняемые данные).
- **FR-3.3 (MUST):** Directory profiles: path/basename/glob rule назначает тип/роль папке и передаёт контекст детям. Пример: `**/plan/` классифицирует plan-папки на любой глубине. `explain-path` показывает сработавшее правило, наследование, шаблоны, workflow reference.
- **FR-3.4 (MUST):** Приоритет разрешения: (1) security hard boundary → (2) явное локальное назначение (`.todoc.json`/front matter/identity map) → (3) правило ближайшей папки (field-wise merge вниз) → (4) правила набора (exact path → exact basename → glob, `priority` + literal-segments tie-break; равный результат разных правил — error) → (5) reserved-name defaults → (6) document type (front matter/identity → explicit rule → единственный `default_doc_type` папки → `unknown`).
- **FR-3.5 (MUST):** Reserved defaults (exact segment/basename на любой глубине): `architecture/`, `constitution/`, `harness/`, `glossary/`, `plan/` (как `**/plan/`), `.research/`. Каноническое написание — `harness`; `harnes` — только явный alias. Кастомные root-local правила могут переопределить defaults; hard-excludes — нет.
- **FR-3.6 (MUST):** Type descriptor MAY содержать неисполняемые `ui` (цвет, иконка, display template, list view, graph style) и `agent_instructions` (структура разделов, правила извлечения, capture-подсказки). Это данные для доверенного Skill/UI-адаптера, не код/prompt authority.
- **FR-3.7 (MUST):** Грамматика масок v1: `/` — separator; `.`/`..`/absolute patterns отвергаются; `*`/`?` не пересекают `/`; `**` как отдельный segment = ноль или больше сегментов; exact basename — отдельный matcher; `!`/повторное включение не поддерживается; исключённый каталог не обходится. Правила покрыты тестами (zero-depth + nested для `**/name/`).
- **FR-3.8 (MUST):** `<subfolder>/.todoc.json` — только декларативные параметры папки (`dir_type`, `exclude`, `doc_type_defaults`, `priority`), по JSON Schema. Не может включать `python`/`shell`/`import`/`exec`/внешний URL и не может расширять разрешённые форматы/plugins/доступ сверх root policy.
- **FR-3.9 (MUST):** `todoc types list/show/guide` — каталог типов и generated-справка. Per-dataset guide по умолчанию печатается в stdout; запись в `.todoc/generated/` — только по явному `--out`. Общая generated-справка по контракту типов — в Skill `references/type-system.generated.md`, не в DATA_ROOT.

### 6.3. Форматы (FR-4)

- **FR-4.1 (MUST):** MVP-форматы: **Markdown** (CommonMark-профиль + ограниченный `obsidian-compatible` profile: YAML front matter, relative links, headings/anchors, проверяемый subset wikilinks/embeds), **CSV** (explicit encoding/dialect/delimiter/quote/header policy, `newline=''`), **JSON** (строгий, UTF-8 policy, size/depth limits, reject duplicate keys, JSON Pointer/locations).
- **FR-4.2 (MUST):** Existing sources в MVP — прежде всего read/validate. Create-only типизированные JSON records — отдельный безопасный контракт (не редактирование исходного корпуса).
- **FR-4.3 (MUST):** Markdown headings строятся из parser tokens/AST, не regex. Headings внутри fenced code не становятся heading. Неизвестный синтаксис сохраняется как исходный текст. Не рендерить документ целиком из AST ради «редактирования».
- **FR-4.4 (MUST):** CSV cell по умолчанию — строка; преобразования колонок/типов — только по явному конфигу типа/источника. Dialect/encoding/header/quoting не угадываются молча. Formula injection (`=`,`+`,`-`,`@`) для spreadsheet-экспорта документируется, исходные значения не меняются молча.
- **FR-4.5 (SHOULD):** Будущие форматы через малые контракты: YAML (безопасная загрузка, без доверенных constructors/tags; front matter ≠ произвольные `.yaml`), Excel (политика по формулам/макросам/hidden sheets), SQLite (read-only source adapter **или** search backend — не `doc_type`), PDF (opaque asset в MVP; парсинг — opt-in adapter).
- **FR-4.6 (MUST):** Obsidian-совместимость: DATA_ROOT открывается как vault; `.md` + YAML + relative links + вложения рядом; неизвестные YAML-поля round-trip не теряются; `.obsidian/` исключается из поиска документов и не редактируется; vault не вкладывается в vault; Obsidian не является зависимостью. Сырые CSV/JSON не называются «заметками Obsidian» без явного opt-in import.

### 6.4. Сканирование, реестры, кэш (FR-5.1–5.2)

- **FR-5.1 (MUST):** Детерминированный рекурсивный скан: сортировка entries, не следовать symlinks/junctions по умолчанию, не выходить за канонический root, hard-excludes (`.todoc/`, VCS/build/cache, секреты по конфигу), не читать бинарные файлы как текст. Регистрировать `unsupported`/`ignored`/`parse_error`/`permission_denied`, не исчезать молча.
- **FR-5.2 (MUST):** Реестры `folders.json`/`documents.json`/`records.json`/`relations.json` — versioned derived snapshots с `schema_version`, `dataset_id`, `generation_id`, `config_digest`, root-relative paths, hashes, parser/type versions. Атомарная публикация: temp generation → validate → rename → atomic `replace` `CURRENT.json`. При ошибке старое поколение остаётся `CURRENT`; incomplete не выдаётся как полный.
- **FR-5.3 (MUST):** Cache key учитывает `dataset_id`, path, content hash, parser/version/options/dialect, type/relation/query schema digest, relation target generation, validator/query engine version. `mtime_ns+size` — только fast-path. Повреждённый кэш → диагностировать и пересоздать из первоисточника. Не собирать миллион документов в один `cache.json` (JSON shards).
- **FR-5.4 (MUST):** Markdown outline: `title`, `level`, line/span, anchor, parent heading ID; пропуски уровня сохраняют фактический `level`; дубли получают детерминированные anchors. Outgoing links/backlinks для CommonMark links + включённого subset wikilinks/embeds; unresolved/ambiguous → exact location.

### 6.5. Валидация, диагностика, исправления (FR-5.3–5.5)

- **FR-5.3 (MUST):** Пайплайн: limits/access → format/parse → resolve profiles/types → schema + field/unit/enum metadata → stable IDs + relation targets/cardinality → deterministic business validators → security/write policy. `ValidationReport` содержит `status` (`valid`/`invalid`/`unsupported`/`not_checked`), parser/schema/type version, path, digest, issues.
- **FR-5.4 (MUST):** Issue: стабильный `{id, code, severity, message, location, evidence}`. Location: CSV row+column (+ physical line range где доказуемо), JSON Pointer + line/column, Markdown line/column + heading/anchor. `suggested_fixes[]`: kind, patch/value, rationale, `autofixable`, confidence, `requires_review`. Предложение ≠ факт. `parse_error`/`schema_error`/`business_error`/warning/`unsupported`/access denial различимы.
- **FR-5.5 (MUST):** `fix` — сначала preview/diff, ничего не применяет без явного `--apply`. Apply проверяет `expected_hash`, пишет temp + atomic replace/create, повторяет parse + schema + type + relation validation, обновляет индекс. Неоднозначный fix / недостающие units/target → не auto-apply. No-op не меняет hash/байты.

### 6.6. Поиск, чтение, навигация (FR-5.6–5.8)

- **FR-5.6 (MUST):** Progressive disclosure: `status/list/tree` → counts/IDs/outline → `search` (top-k snippets с path/line/row/pointer + hash) → `read` (выбранный fragment). Полный каталог с текстом в первом ответе запрещён.
- **FR-5.7 (MUST):** Один общий `docs search/read` с фильтрами `format`, `doc_type`, `dir_type`, project/scope, path mask, metadata, status, limit. Отдельная команда по типу — только при действительно особой user action.
- **FR-5.8 (MUST):** Bounded projections: Markdown `--section/--anchor/--line-range`; JSON `--pointer` / разрешённая projection; CSV `--columns/--rows` / bounded `--where` по безопасной грамматике (без `eval`/SQL); records `--view compact/full`, `--project`. Все выдачи: byte/row/result limits, `truncated`, cursor, hash, provenance. `--budget` ограничивает сериализованную context packet; токены exact только при известном tokenizer, иначе — оценка + hard byte/character cap.
- **FR-5.9 (SHOULD):** Links/backlinks доступны для навигации; по умолчанию не расширяют контекст на всю соседнюю сеть. Deep graph traversal — только явный `relations graph` с depth/limit.

### 6.7. Записи, связи, запросы и capture (FR-6–FR-8)

- **FR-6.1 (MUST):** Type-directed capture: Skill выбирает `entity_type`, показывает поля/шаблон, уточняет только отсутствующие обязательные данные, разрешает relation targets (существующий ID или уточнение), вычисляет допустимый путь/имя из шаблона, просит подтверждение для неоднозначного типа/маршрута. CLI валидирует полный JSON + target relations и создаёт **новый** файл без перезаписи. Неизвестное обязательное значение/единица/неоднозначный target → structured clarification error, не догадка.
- **FR-6.2 (MUST):** `records create` — create-only atomic write с no-overwrite: проверка отсутствия target file/`record_id` collision, required fields, units/date normalization, relation existence/type/cardinality, naming/template constraints (только документированные placeholders из validated fields; нормализация + containment; запрет `..`/absolute). После записи — перечитывание/валидация + обновление индекса.
- **FR-6.3 (MUST):** Type config MAY задавать `required_sections`/`template` (для `plan`/`research`), `external_fetch_policy` (для `link`: allowlisted fetch + извлечение title/описания/фактов/тегов), `default_workflow` (whitelisted `workflow_id`). Неподключённый workflow не блокирует generic `create/validate/list/read` и явно обозначается warning.
- **FR-6.4 (MUST):** `docs new` — новый Markdown draft в выбранной/типизированной папке. Import/copy существующих файлов — отдельный plan/preview сценарий, не обязательный первый шаг. AI extraction/summary может предложить draft, но до schema validation/подтверждения не считается фактом.
- **FR-7.1 (MUST):** Typed relations: declarative relation descriptors (source/target kind+type, cardinality/uniqueness, inverse, dangling/missing-target policy). CLI проверяет endpoint types/targets/cardinality до подтверждения записи. Unknown/ambiguous target → diagnostic/clarify.
- **FR-7.2 (MUST):** Graph/backlink index — derived, пересоздаваемый. `relations graph --from … --type … --depth … --limit …` выдаёт явные typed edges + краткие neighbours. Cross-dataset refs в MVP запрещены.
- **FR-8.1 (MUST):** Safe query/aggregate: только schema-known поля, typed filters, projections, explicit aggregate metrics, provenance. Query/metric syntax — allowlisted JSON AST; запрещены Python/SQL/`eval`/import/shell/network/dynamic imports. Ресурсные лимиты обязательны.
- **FR-8.2 (MUST):** Агрегация возвращает metric definition, единицы, формулу, timezone/date policy, входящие IDs/paths/pointers, статус полноты. Оператор явно определяет local date/timezone, правила перевода единиц, пропущенный/неизмеримый вес, учёт compound/multi-category (без двойного счёта). JSON Schema сама по себе не доказывает semantics.
- **FR-8.3 (SHOULD):** Saved QuerySpec/metric definitions — versioned JSON в `.todoc/queries/`, schema-checked, тестируемые. Необычное lifecycle/metric — явное versioned declarative operation или trusted installed handler с тестами; Skill выбирает и собирает входы, но не является единственным источником математической истины.

### 6.8. Контролируемая запись (FR-5.5, FR-6.2 — сводка)

MVP read-only для **существующих** источников. Разрешённые create-path: (1) `docs new`, (2) `records create` (новый JSON). Редактирование существующего source — review-first patch/apply. WritePlan: target selector/template, minimal patch/new content, expected/new hash, preview diff, основание/уверенность, writer, validations. Default — dry-run/preview. Advisory/LLM suggestion никогда не получает auto-apply. Writer пишет temp рядом/в безопасном temp, flush/close, валидирует, atomically replace/create, сохраняет права/encoding/newline по policy. Если драйвер не умеет без потерь — `unsupported_write`, не fallback к полной перезаписи. Raw import/export — отдельная операция с plan/preview/explicit confirmation. Индексирование никогда не изменяет исходные файлы.

### 6.9. Skill и доверие (FR-11)

- **FR-11.1 (MUST):** Родительский `SKILL.md`: YAML front matter (`name: todoc`, совпадающий с каталогом), короткое тело (<500 lines, instruction body <5000 tokens ориентир), прямые relative links на `references/*.md` (без цепочек `SKILL → guide A → guide B`). Не грузить все references в каждой задаче.
- **FR-11.2 (MUST):** Type-specific procedures — references/generated guidance в установленном Skill, **не** копии в DATA_ROOT как навыки. Type config ссылается только на whitelisted trusted `workflow_id` из установленного окружения. Неизвестный/отсутствующий workflow — warning, не отказ в read/create/validate.
- **FR-11.3 (MUST):** Содержимое CSV/JSON/Markdown, свободные поля/описания типов, record values/template/example тексты — potentially untrusted data. Не могут переписать `SKILL.md`, запросить команды, изменить права или заставить CLI принять source как policy. Показываются как quoted data/metadata.
- **FR-11.4 (SHOULD):** Дочерние автономные Skills (`todoc-read`, `todoc-edit`) — только если чтение/редактирование нужно активировать независимо от `todoc`. В первом релизе «дочерние документы» = обычные `references/*.md`.

### 6.10. Memory / LLM Wiki профиль (отдельный scope, НЕ MVP)

Если пользователь подтверждает цель «память с задачами/планами/идеями» или «компаундируемая wiki», это **отдельный профиль** со своими схемами и acceptance-тестами. Минимум до обещания функции:

- Общий envelope (`id`, `type`, `created`, `updated`, `status`, `tags`, `source_refs`, `relations`), schema/version/custom fields, stable ID/alias policy, миграции.
- **Task:** status + переходы, due-date timezone semantics, priority, owner/assignee, project, dependencies/blocked-by, recurrence, completion date. Запросы open/overdue/due soon/by project/blocked — на fixtures.
- **Idea/Plan:** idea lifecycle `captured → exploring → validated → promoted/parked/archived` (имена настраиваемы), evidence/open questions, связь при продвижении; plan/project — цель, owner, статус, срок/этапы, next action, decision links.
- **Capture lifecycle:** `capture → triage/dedupe → confirm/merge/no-op → link → retrieve → update/complete/archive`. Не автозаписывать всю переписку: только выбранный пользователем scope, остальное — draft.
- **LLM Wiki (если нужен синтез):** immutable capture/manifest, source metadata/provenance, generated synthesis pages, claim evidence/conflict/freshness policy, query citations, lint/report. Не сливать с детерминированным `check`; LLM-выводы не являются «истиной» без evidence workflow.
- **Session continuity (если нужен):** session/domain home, hot cache/current state, start-of-session bootstrap, решения/открытые вопросы, crystallize сессии, разделение transient context vs durable memory.

**Запрещено:** называть `doc_type: plan`/`idea` поддержкой task management без вышеперечисленного.

### 6.11. MCP-адаптер (SHOULD после стабилизации CLI)

- **FR-10.1 (SHOULD):** Тонкий MCP-сервер поверх application-слоя: tools для действий (`search`, `read`, `records_query`, `records_create_preview`, `check`), resources для контекста (документ/фрагмент/схема/тип). Статусы/безопасность согласованы с CLI; формат вывода не копируется буквально.
- **FR-10.2 (SHOULD):** Stateless-модель (MCP 2026-07-28): состояние между вызовами — явным идентификатором; права проверяются заново. Read-only по умолчанию; write tools — за явным флагом/consent (аналог `mdkb --allow-write`).
- **FR-10.3 (MAY):** MCP prompts для повторяемых сценариев (capture/query/lint). Не превращать каждую выдачу данных в tool.

### 6.12. Веб-интерфейс (Этап 9, не MVP)

- **FR-9.1 (MUST, когда строится):** Отдельный UI adapter поверх CLI/API/derived snapshots. Не source of truth. Читает готовые snapshots/кэш; пишет только через валидированные CLI/API операции, никогда напрямую в файлы.
- **FR-9.2 (MUST):** Иерархия папок (дерево) + граф связей + фильтры по типам/полям/связям/датам + просмотр/редактирование записей + навигация по связанным объектам. Визуал — из `ui` metadata типа.
- **FR-9.3 (MUST):** Веб не обязателен для использования базы. Не требует миграции данных или дублирующей БД.
- **FR-9.4 (MAY):** Статическая публикация (digital garden) как отдельный экспорт из тех же файлов.

### 6.13. Экспорт, импорт, backup, sync

- **FR-12.1 (SHOULD):** Git — рекомендуемый механизм версионирования/бэкапа (текстовые файлы diff-ятся). `todoc` не требует Git, но не мешает ему.
- **FR-12.2 (SHOULD):** Экспорт: JSON envelope (уже CLI), Markdown view/projection, опционально OKF bundle / static HTML. Импорт: preview-first copy/adopt (без обязательной конвертации); CSV→Markdown — отдельный opt-in import с preview.
- **FR-12.3 (MAY, после MVP):** Cloud sync / LiveSync / multi-writer — только с single-writer policy, conflict handling и явным consent. Не обещать «синхронизацию» без этого.

---

## 7. Нефункциональные требования (NFR)

| ID | Требование |
|---|---|
| NFR-1 **Безопасность** | Canonicalize root/candidate; reject absolute/`..`/другой drive/UNC/escape после resolve; сравнение по компонентам, не строковому prefix. По умолчанию не следовать symlink; Windows junction/reparse — зафиксированное поведение. Защита от race/TOCTOU: hash-before-apply, parent containment, postcondition. Не выполнять shell с user content; query — только allowlisted declarative operators. Лимиты (bytes/rows/depth/files/results/время/память) — на уровне application/config. JSON config/types/queries/templates валидируются до использования; schema refs — только локальный registry, без сети. DATA_ROOT не содержит исполняемого кода; entrypoint plugins — только из установленной среды по allowlist с проверкой API version. Permissions/ACL/privacy/redaction — отдельно от валидности схемы |
| NFR-2 **Надёжность** | Стабильные `code`, severity, path, location range, message/evidence, recovery guidance, exit status на каждую ошибку. Ошибка одного документа не останавливает независимые элементы scan, но generation помечается incomplete. `--strict` превращает warnings в отказ CI. Нельзя скрывать `unsupported`/`truncated`/`permission_denied`/недоступный root как «чистый/валидный» |
| NFR-3 **Производительность** | Измерять на зафиксированном корпусе: latency scan/search/query, cold-rebuild время, память. Целе калибруются на корпусе, не объявляются универсальными. FTS5/lexical backend выбирается benchmark-ом (доступность FTS5 в builds, размер/латентность, переносимость, сравнение с QMD) |
| NFR-4 **Наблюдаемость** | Версии parser/schema/type/validator/query engine/tokenizer (если есть) видны в отчёте. `check`/`search` работают локально без скрытого сетевого/LLM-вызова |
| NFR-5 **Тестируемость** | Unit/contract/integration/CLI/packaging/agent-eval тесты (§14 плана). CI: pytest, coverage по critical modules, Ruff, mypy или Pyright, build/install check, fixture validation. Wheel тестируется вне checkout |
| NFR-6 **Совместимость** | Python 3.12+ (предварительно; 3.11 — только с совместимым обходом через `os.scandir` + CI на 3.11). Click как консервативный старт (Typer — допустимая альтернатива). JSON Schema 2020-12. `pyproject.toml` + `src/` layout + `project.scripts` (`todoc = "todoc.cli:main"`) |
| NFR-7 **Приватность** | Local-first, без скрытого LLM/network search. Входящие файлы недоверенные. Sensitivity/retention rules, explicit scopes на приватные папки, отдельное согласие на сеть/транскрипцию/синхронизацию — для memory-профиля. Никакого auto-save всего разговора или background job по умолчанию |

---

## 8. CLI-контракт

### 8.1. Полный список команд (нормативный эскиз)

```bash
todoc init --root ./knowledge
todoc --root ./knowledge check
todoc --root ./knowledge --root ./research check          # multi-root, изолированные отчёты
todoc --root ./knowledge scan
todoc --root ./knowledge check-config
todoc --root ./knowledge validate --all --output json
todoc --root ./knowledge index status
todoc --root ./knowledge index rebuild
todoc --root ./knowledge explain-path projects/service-a/plan/migration-plan.md
todoc --root ./knowledge docs new --title "Release decision" --dir inbox --template note
todoc --root ./knowledge records create --type workout --input-file ./draft-workout.json --preview
todoc --root ./knowledge records create --type workout --input-file ./draft-workout.json --if-hash-new --apply
todoc --root ./knowledge types list --output json
todoc --root ./knowledge types show research-note --output json
todoc --root ./knowledge types guide --format markdown
todoc --root ./knowledge types guide --format markdown --out .todoc/generated/types-reference.md
todoc --root ./knowledge docs search --type adr --query "refresh token" --budget 1200 --limit 10 --output json
todoc --root ./knowledge docs read --id doc_... --section "Decision" --output json
todoc --root ./knowledge docs read --id doc_... --pointer /version --output json
todoc --root ./knowledge docs read --id doc_... --columns run_id,status --rows 20 --output json
todoc --root ./knowledge records list --type workout --since 2026-11-01 --until 2026-11-30 --relation performed_by=person:sergei --output json
todoc --root ./knowledge records query --query-file .todoc/queries/triceps-volume-month.json --output json
todoc --root ./knowledge records aggregate --metric monthly_volume_by_muscle --group-by date.month,muscle --output json
todoc --root ./knowledge records read --id workout:2026-11-24-sergei-01 --view compact --output json
todoc --root ./knowledge relations graph --from person:sergei --type performed_by --depth 2 --limit 100 --output json
todoc --root ./knowledge fix --diagnostic <diagnostic-id> --preview
todoc --root ./knowledge fix --diagnostic <diagnostic-id> --if-hash sha256:... --apply
todoc --root ./knowledge docs edit --id doc_... --patch-file ./change.diff
todoc --root ./knowledge docs edit --id doc_... --patch-file ./change.diff --if-hash sha256:... --apply
```

Точную вложенность Click-команд можно изменить, сохранив контракты. CLI — тонкий входной слой: разобрать аргументы → application service → результат/exit code. Разбор CSV/бизнес-валидация в callback Click запрещены.

### 8.2. Вход/выход, envelope, exit codes

- **Вход:** явный `--root` (повторяемый) или `TODOC_ROOT`; CWD не выбирает config. `--output` = режим сериализации (`json`/`table`/`markdown`), `--out` = необязательный путь отчёта (relative проверяется на containment). `--budget`/`--limit`/cursor — лимиты выдачи. `--preview`/`--apply`/`--if-hash` — write-контроль. `--no-input` — неинтерактивный режим без зависания.
- **Выход (JSON):** версионированный envelope `{schema_version, ok, data, diagnostics, next_actions}`. `next_actions` — только проверяемая подсказка: `argv` как массив (не склеенная строка) + purpose. Large listing: `total`, ограниченные `items`, `truncated`, `cursor`. `--output json`: stdout — только JSON; progress/help — stderr; error code устойчив, exit status ненулевой при operation error. Human и JSON output несут одни и те же machine facts.
- **Exit codes:** `0` — успех; ненулевые коды — стабильная карта (usage error / validation error / access denied / conflict / incomplete generation и т.д.), зафиксированная как часть контракта. `--strict` может превращать warnings в отказ CI.
- **Пример envelope:**
```json
{
  "schema_version": 1,
  "ok": true,
  "data": {"dataset_id": "dataset-example", "total": 1, "items": [{"id": "doc_0123", "format": "markdown", "doc_type": "adr", "path": "projects/service-a/adr/0042.md", "summary": "Решение о refresh token"}], "truncated": false, "cursor": null},
  "diagnostics": [],
  "next_actions": [{"argv": ["todoc", "--root", "./knowledge", "docs", "read", "--id", "doc_0123", "--section", "Decision", "--output", "json"], "purpose": "Прочитать решение у выбранного ADR"}]
}
```
- **Диагностика (эскиз):**
```json
{"dataset_id": "dataset-example", "id": "diag_0042", "code": "markdown.link.target_missing", "severity": "error", "path": "notes/design.md", "location": {"line": 42, "column": 18, "end_line": 42, "end_column": 39}, "evidence": "[runbook](../ops/runbok.md)", "message": "Локальная цель ссылки не найдена.", "suggested_fixes": [{"kind": "replace_link_target", "replacement": "../ops/runbook.md", "basis": "Найден единственный кандидат с совпадающим basename.", "autofixable": true, "requires_review": true}]}
```

---

## 9. Конфигурация и схемы данных

### 9.1. Файлы конфигурации (все JSON, все с `schema_version`)

- `.todoc/dataset.json` — `dataset_id`, `schema_version`, ссылки на каталоги типов/rules/templates/queries, разрешённые форматы, trusted workflow whitelist, resource limits.
- `.todoc/rules/directory-rules.json` — path/glob/basename/front matter признаки для `dir_type`, inheritance, priority, ambiguity diagnostics, project boundaries.
- `.todoc/rules/document-rules.json` — сопоставление path/filename/front matter с `doc_type`.
- `.todoc/dir_types/<type>/type.json` — роль папки, inherited context, default/create destinations, optional workflow hint.
- `.todoc/doc_types/<type>/type.json` — семантика документа, допустимые форматы, schema refs, views, optional trusted `workflow_id`.
- `.todoc/entity_types/<type>/type.json` — record schema, required/optional fields, units/date/enum metadata, relation requirements, destination/template policies, projections, optional capture workflow, `ui`/`agent_instructions`.
- `.todoc/relation_types/<type>/type.json` — declarative edges: source/target kind+type, cardinality/uniqueness, inverse, dangling policy.
- `.todoc/queries/*.json` — optional saved QuerySpec/metric definitions (versioned operators + units).
- `.todoc/templates/` — safe starter templates (например JSON skeleton для нового record).
- `.todoc/schemas/` — schema-файлы DATA_ROOT; системные schemas для versioned config/types/queries поставляет `todoc`.
- `.todoc/identities.json` — versioned identity map для стабильных ID, где ID нельзя хранить в source.
- `<folder>/.todoc.json` — локальные override (декларативные, по JSON Schema).

Для Markdown front matter по умолчанию не обязателен. Профили могут включить Obsidian properties или optional OKF v0.2 validation/metadata; `todoc` сохраняет неизвестные YAML-поля и не требует конвертации existing notes. JSON-записи хранят ID/type явно в теле файла.

### 9.2. Примеры (иллюстративные, не утверждённые schemas)

**Dataset:**
```json
{"schema_version": 1, "dataset_id": "dataset-example", "enabled_formats": ["csv", "json", "markdown"], "directory_rules": "rules/directory-rules.json", "document_rules": "rules/document-rules.json", "directory_types": "dir_types", "document_types": "doc_types", "entity_types": "entity_types", "relation_types": "relation_types", "queries": "queries", "templates": "templates", "trusted_workflows": {"record-capture-v1": {"kind": "external-skill", "workflow_id": "todoc-record-capture", "version": "0.1.0"}}, "follow_symlinks": false, "limits": {"max_file_bytes": 10485760, "max_json_depth": 128, "max_csv_rows": 1000000, "max_query_results": 200, "max_record_create_path": 512}}
```

**Entity type (`workout`):**
```json
{"schema_version": 1, "type_id": "workout", "version": "0.1", "description": "Одна тренировка с упражнениями и подходами.", "format": "json", "schema": "schema.json", "id_pattern": "workout:{date}-{person-slug}-{slug}", "template": "template.json", "prompts": {"read": "prompts/read.md", "create": "prompts/create.md", "edit": "prompts/edit.md", "delete": "prompts/delete.md"}, "path_template": "records/workouts/{date_year}/{date_month}/{slug}.json", "required_relations": ["performed_by"], "default_workflow": "record-capture-v1", "views": {"compact": ["record_id", "date", "relations", "exercises.name", "exercises.muscle_groups"], "summary": ["date", "totals"]}}
```

**Relation type:**
```json
{"schema_version": 1, "type_id": "performed_by", "version": "0.1", "from": {"kind": "record", "entity_type": "workout"}, "to": {"kind": "record", "entity_type": "person"}, "cardinality": "one_to_many"}
```

**Запись (`workout`, иллюстративная):**
```json
{"schema_version": 1, "record_id": "workout:2026-11-24-sergei-01", "entity_type": "workout", "date": "2026-11-24", "relations": [{"type_id": "performed_by", "target": {"kind": "record", "id": "person:sergei"}}], "exercises": [{"name": "Разгибание на блоке", "muscle_groups": ["triceps"], "sets": [{"reps": 12, "weight": {"value": 25, "unit": "kg"}}, {"reps": 10, "weight": {"value": 27.5, "unit": "kg"}}]}]}
```

**Directory rules (reserved):**
```json
{"schema_version": 1, "rules": [{"id": "reserved-research", "match": {"kind": "directory", "basename": ".research"}, "assign": {"dir_type": "research"}, "priority": 100}, {"id": "reserved-plan", "match": {"kind": "directory", "glob": "**/plan"}, "assign": {"dir_type": "plan"}, "priority": 100}, {"id": "reserved-architecture", "match": {"kind": "directory", "basename": "architecture"}, "assign": {"dir_type": "architecture"}, "priority": 100}, {"id": "reserved-constitution", "match": {"kind": "directory", "basename": "constitution"}, "assign": {"dir_type": "constitution"}, "priority": 100}, {"id": "reserved-harness", "match": {"kind": "directory", "basename": "harness"}, "assign": {"dir_type": "harness"}, "priority": 100}, {"id": "reserved-glossary", "match": {"kind": "directory", "basename": "glossary"}, "assign": {"dir_type": "glossary"}, "priority": 100}]}
```

**Document rules (пример):**
```json
{"schema_version": 1, "rules": [{"id": "adr-markdown", "match": {"kind": "file", "glob": "**/adr/*.md"}, "assign": {"doc_type": "adr"}, "priority": 50}, {"id": "glossary-by-front-matter", "match": {"kind": "file", "front_matter": {"doc_type": "glossary-entry"}}, "assign": {"doc_type": "glossary-entry"}, "priority": 200}]}
```

**Локальный override:**
```json
{"schema_version": 1, "dir_type": "research", "exclude": ["_drafts/"], "doc_type_defaults": {"**/*.md": "research-note"}}
```

Все `dir_type`/`doc_type`/`entity_type`/`relation_type` IDs должны существовать в соответствующих каталогах. Неизвестные поля/версии — diagnostic + предложение migrate/check, не «примерно совместимо». Дубликаты имён/ID — ошибка. Числа лимитов — стартовые, калибруются на корпусе.

---

## 10. Итоговый продукт: что будет на выходе

### 10.1. Три артефакта (MVP)

| Артефакт | Что это | Что внутри | Что НЕ внутри |
|---|---|---|---|
| **A. Skill-пакет `todoc/`** | Устанавливаемый Python-проект + родительский Skill | `SKILL.md`, `references/*.md`, `assets/data-root-template/`, `src/todoc/` (CLI + domain/application/ports/adapters), `pyproject.toml`, тесты, README разработчика | Данные пользователя, `.todoc/` конкретного набора, исполняемый код в DATA_ROOT |
| **B. DATA_ROOT пользователя** | Переносимая папка знаний | `.todoc/` (dataset/rules/types/schemas/templates/queries/identities/index/cache/generated), `projects/`, `records/`, `inbox/`, `attachments/`, `notes/` и т.д. | `SKILL.md`, skill-каталоги, executable Python/shell, `module:callable` ссылки |
| **C. Документация и контракты** | То, по чему проверяется продукт | Эта конституция, `plan.md`, competitive analysis, JSON Schemas, `types guide` (generated), benchmark-отчёты | Неисполняемые prompt-копии из данных |

### 10.2. Расширения после MVP (отдельные артефакты, не ломающие A/B)

| Артефакт | Когда | Контракт |
|---|---|---|
| **D. MCP-адаптер** | После стабилизации CLI | Тонкий транспорт поверх application-слоя; read-only по умолчанию |
| **E. Веб-интерфейс** | Этап 9, после стабильных JSON-контрактов | Отдельный adapter; читает snapshots, пишет через CLI/API |
| **F. Memory/LLM Wiki профиль** | Только после отдельного scope gate | Собственные схемы/lifecycle/acceptance-тесты; не часть core MVP |
| **G. Плагины/форматы** | По подтверждённой боли | Entry-point plugins по allowlist; новые format drivers через Protocol |

### 10.3. Definition of Done (первый usable release)

Релиз пригоден для пилота, если **все** пункты выполнены, пройден product gate (§12 Этап 0) и выбран product scope (§6.10):

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

---

## 11. Структура файлов идеального проекта

Это целевая схема, не обещание заранее создать каждый пустой модуль. Разделять пакет далее следует по мере роста.

### 11.1. Skill + CLI: `todoc/`

```text
todoc/
├── SKILL.md                         # единственный родительский Skill (name: todoc)
├── pyproject.toml                   # пакет, зависимости, console entry point, tools
├── README.md                        # инструкции разработчику по dev/install/test
├── docs/                            # документация проекта (не Skill-references)
│   ├── plan/                        # норматив и планы: constitution, implementation-plan,
│   │   │                            # competitive-analysis, audit-implementation, *.after.md
│   │   └── engineering-draft.md     # инженерный набросок §1–§18 (первоисточник)
│   ├── state/                       # текущее состояние системы: 01-overview … 15-benchmark
│   ├── guides/                      # гайды для агентов: cli, mcp, markdown-knowledge
│   └── research/                    # исследования и аудиты + skills-audit/ (материалы аудита)
├── references/                      # Skill-references: обычные docs, не отдельные skills
│   ├── workflow.md
│   ├── data-roots-and-config.md
│   ├── types-and-validation.md
│   ├── formats-csv-json-markdown.md
│   ├── entities-relations-and-queries.md
│   ├── safe-read-write.md
│   ├── ingest-query-lint.md
│   ├── page-templates.md
│   └── type-system.generated.md     # автогенерация общей справки о типах
├── assets/
│   └── data-root-template/          # JSON-шаблоны для `todoc init`, не реальные данные
├── src/
│   └── todoc/
│       ├── cli.py                   # создание Click app и main()
│       ├── config.py                # init датасета, типы по умолчанию
│       ├── service.py               # DatasetContext: scan/validate/rebuild
│       ├── errors.py                # TodocError + коды + exit codes
│       ├── domain/                  # модели: Document, Record, Relation, QuerySpec
│       ├── application/             # registry, validator, write, query, search
│       ├── ports/                   # Protocol-контракты адаптеров
│       ├── adapters/
│       │   ├── filesystem/          # scandir, containment, atomic write
│       │   ├── formats/             # markdown / json / csv
│       │   ├── indexes/  cache/  search/
│       ├── typing_system/           # descriptors, resolver, prompts
│       └── output/                  # JSON/table/Markdown конверт
├── tests/
│   ├── unit/  cli/  integration/  conftest.py
├── bench/                           # критерии качества + run_benchmark.py + results/
├── tools/                           # служебные скрипты репозитория (не часть пакета)
└── demo/                            # демонстрационный DATA_ROOT (живой пример)
```

Правило: в корне репозитория живут только `SKILL.md`, `README.md`, `pyproject.toml`,
`.gitignore` и каталоги верхнего уровня (`docs/`, `references/`, `assets/`, `src/`,
`tests/`, `bench/`, `tools/`, `demo/`). Отдельные документы в корне не появляются: план — в
`docs/plan/`, состояние — в `docs/state/`, гайды — в `docs/guides/`, исследования — в
`docs/research/`. Временные рабочие каталоги (`tmp_*`) в git не коммитятся.

В `tools/` лежат скрипты, которые обслуживают сам репозиторий, а не набор данных:
`refresh_demo_state.py` пересобирает `demo/references/state/` из `docs/state/` (копия
производная и руками не правится), `linkcheck.py` проверяет относительные ссылки во всех
Markdown-файлах, пропуская примеры внутри блоков кода и inline-кода, а также снимки
сторонних репозиториев в `docs/research/skills-audit/`. Они не входят в устанавливаемый пакет.

### 11.2. Набор данных: `<DATA_ROOT>/`

```text
<DATA_ROOT>/
├── .todoc/                          # машинные настройки/индексы; исключается из каталога документов
│   ├── dataset.json                 # dataset_id, версия config, относительные пути
│   ├── rules/
│   │   ├── directory-rules.json
│   │   └── document-rules.json
│   ├── dir_types/
│   │   ├── research/type.json
│   │   └── plan/type.json
│   ├── doc_types/
│   │   └── adr/
│   │       ├── type.json            # формат, required_sections, section_rules
│   │       ├── template.md          # стартовый шаблон документа этого типа
│   │       └── prompts/             # стартовые промпты агента: read|create|edit|delete
│   ├── entity_types/
│   │   └── workout/
│   │       ├── type.json            # required_fields, path_template, views, metric_fields
│   │       ├── schema.json          # JSON Schema записей этого типа
│   │       ├── template.json        # стартовая запись
│   │       └── prompts/             # read|create|edit|delete
│   ├── relation_types/
│   │   ├── performed_by/type.json
│   │   ├── derived_from/type.json
│   │   ├── supports/type.json
│   │   └── contradicts/type.json
│   ├── queries/                     # optional declarative saved QuerySpec/metric definitions
│   ├── index/
│   │   ├── CURRENT.json             # атомарно обновляемый указатель поколения
│   │   └── generations/
│   │       └── <generation-id>/
│   │           ├── folders.json
│   │           ├── documents.json
│   │           ├── records.json
│   │           ├── relations.json
│   │           └── diagnostics.json
│   └── cache/
│       └── parse/                   # JSON cache по hash/версии parser-а
├── projects/
│   ├── service-a/
│   │   ├── .todoc.json              # необязательные локальные правила/override
│   │   ├── .research/
│   │   ├── plan/
│   │   │   └── migration-plan.md
│   │   ├── architecture/
│   │   └── docs/
│   │       └── glossary.md           # doc_type=glossary-entry; тип не зависит от папки
│   └── service-b/
│       └── notes/
│           └── terms.md              # тоже может быть doc_type=glossary-entry
├── records/
│   ├── people/sergei.json            # entity_type=person, stable record_id
│   └── workouts/2026/11/             # путь вычисляет безопасный type template
├── inbox/                            # optional: новые непроверенные документы/черновики
├── attachments/                      # optional: assets рядом с заметками; paths относительно DATA_ROOT
├── tables/
└── notes/
```

Правила DATA_ROOT: внутри `.todoc/` и папок проекта может быть JSON-конфиг, JSON Schema, JSON-реестр/кэш и исходные данные. **Не должно быть `SKILL.md`, skill-каталогов, executable Python, shell-скриптов или ссылок на `module:callable`.** `.todoc/` читается целенаправленно и не индексируется как пользовательская документация. Type-конфиги/schemas/relation definitions/query specs/templates — declarative JSON; `description`/пример — untrusted data для справки, не исполняемый prompt/code. File-backed record содержит явные `record_id` и `entity_type`; typed references — в source record/front matter. Naming/location templates — только документированные placeholders из validated fields, нормализация + containment; запрет `..`/absolute/подмены type/permissions. Saved QuerySpec/metric — ограниченные JSON AST/операторы, schema-checked, ресурсно ограниченные; запрещены Python/SQL/`eval`/import/shell/network. `generated/types-reference.md` — опциональная производная справка с маркером `generated`; `types guide` по умолчанию печатает в stdout. Папку можно переносить целиком: только relative paths. Один root = одна config/index namespace. Если папка открыта как Obsidian vault, Obsidian может создать `.obsidian/`; `todoc` исключает её из поиска и не редактирует.

### 11.3. Будущий веб-интерфейс (отдельный adapter, не часть MVP-структуры)

```text
todoc-web/                           # отдельный пакет/репозиторий или подпакет, не source of truth
├── README.md
├── pyproject.toml                   # или package.json — зависит от стека UI
├── src/todoc_web/
│   ├── api.py                       # тонкий HTTP-адаптер поверх application-слоя (читает snapshots, пишет через CLI/API)
│   ├── snapshots.py                 # чтение CURRENT generation + cache
│   └── ui/                          # дерево папок, граф связей, фильтры по типам/полям, карточки записей
└── tests/
```

Веб не входит в первый CLI MVP, но архитектура обязана предусмотреть его как отдельный read/write UI adapter поверх того же CLI/dataset API/кэша, без второй копии истины.

---

## 12. Roadmap и gates

| Этап | Результат | Gate / «Готово, если» |
|---|---|---|
| **0 — Discovery** | Проблема и scope проверены на реальных/обезличенных папках; 8–12 problem interviews; 20–30 реальных поисковых вопросов + набор внесённых дефектов; benchmark против `rg`/Obsidian/QMD/Open Knowledge/OpenKB/`todoc`-прототипа | Подтверждённый смешанный формат/интегрити сценарий + измеримая выгода. Если Markdown-only поиск закрывается готовыми инструментами и cross-format checks не оказываются регулярной болью — **остановить широкий scope**, оставить тонкий validator/adapter/Skill. Если выбран memory/domain профиль — закрыть отдельный scope gate до проектирования публичного API |
| **0.5 — Design contracts** | ADR/решения: Python версия, Click/Typer, `.todoc` + relative-path contract, document vs entity/record boundary, ID/file policy, Obsidian/OKF profiles, `harness` alias, generated docs location, diagnostic/fix/query contract, search backend, write permission model, vertical-slice fixtures | Код после подтверждения вопросов, влияющих на layout/API |
| **1 — Скелет Skill/CLI** | `SKILL.md`, references, `pyproject.toml`, `src/todoc`, Click root, `todoc --help/--version`, tooling, tests. `init` только создаёт пустой `.todoc/dataset.json` шаблон | Wheel запускается вне repo; skill front matter валиден; нет imports из CWD/data root; help/exit codes тестируются |
| **2 — Data schema + portable init** | JSON Schema 2020-12 для dataset/rules/descriptors/templates/identity-map/local `.todoc.json`. `init` создаёт конфиг/типы-шаблон, не создаёт Skill/code, не сканирует автоматически | Schema positive/negative tests; relative paths; root создаётся в temp, перемещается целиком и снова открывается |
| **3 — Scanner + resolver** | Deterministic recursive scan, hard-excludes, local config inheritance, nested-root policy, reserved-name defaults, маски, `explain-path`. Без custom plugins | Fixtures подтверждают приоритеты; двусмысленность → diagnostic; symlink/traversal не выходит за root; `.todoc/`/`.todoc.json` не индексируются как content |
| **4 — Три format adapters + validation** | CSV/JSON/Markdown reader, ParseResult locations, schema/entity/relation validator, field/unit/date metadata, profiles, error envelope. Markdown outline; JSON records — explicit ID/type/relation extraction + compact projection. Writer Protocol (existing writes за feature flag до safety gate) | Driver contract tests; parser versions/options указаны; недопустимый файл/record/query не объявляется valid и не пропадает без diagnostic |
| **5 — Registry/cache + bounded search/read** | Folder/document/record/relation registry + atomic `CURRENT.json`; identity-map; per-doc JSON parse cache; exact/name/path/type/field search; safe declarative records query/aggregate; cursor/limit; bounded typed projections. Deterministic lexical/metadata backend через benchmark (in-process FTS5 или минимальная альтернатива); retrieval/ranking ports сохранены, embeddings/graph DB не обязательны | Перескан без изменений воспроизводим; изменение config/parser/content/type/relation/query сбрасывает правильный cache; повреждённый/incomplete generation не подменяет предыдущий полный; большие результаты paginated; reference aggregate возвращает units/formula/provenance; retrieval benchmark на frozen queries не хуже target baseline |
| **6 — Review-first diagnostics + ограниченные fixes** | Structured deterministic issues + `suggested_fixes`/preview diff (ничего не применять). Затем explicit `--apply` только для проверенных create/patch, с expected absence/hash, temp + atomic replace/create, повторной валидацией, обновлением индекса. Разрешённые writes: `docs new` + `records create` (новый JSON); существующие CSV/JSON/Markdown — review-first patch, gated later | Каждый supported issue — stable code + точное местоположение; no-op не меняет hash/байты; record create соблюдает no-overwrite/path-template/relation validation; неоднозначный fix/недостающие units/target не auto-apply; concurrent update обнаруживается; невалидная запись оставляет оригинал нетронутым; пользователи считают suggestions/capture полезными по критериям Этапа 0 |
| **7 — Obsidian/profile, Skill, capture workflow** | Минимальный Obsidian-compatible Markdown profile + типовые vault link patterns. Parent `SKILL.md`, `references/*.md` (включая entities/relations/queries), generated `type-system.generated.md`, `types guide`, trusted record-capture workflow reference. Per-dataset guide — stdout или явный путь в `.todoc/generated/` | Папка открывается как vault без runtime plugin; обещанный subset links/headings/assets проходит smoke tests; parent Skill пользуется явным `--root`, уточняет обязательные record fields/targets, вызывает CLI preview/create, читает только выбранную проекцию/fragment, не запускает действия автоматически; отсутствующий workflow не блокирует generic CLI; references прямые/валидны/кратки |
| **8 — Optional scale/extensions** | Только по измерениям/запросам: entry-point plugins/pluggy, дополнительный format driver, alternative retrieval backend, QMD/external vector/graph bridge, hybrid fusion, rerankers, watch mode, import/AI enrichment, специализированные domain workflows | Конкретная подтверждённая боль + тестовый набор/план безопасности. Без use case, privacy/egress/resource limits, benchmark и security/compatibility tests — не вводить |
| **9 — Optional веб-интерфейс** | Локальный веб-UI как отдельный adapter: дерево папок, карточки записей, интерактивный граф, фильтры по типам/полям/связям/датам, просмотр/редактирование, навигация по связанным объектам. Читает snapshots/кэш, пишет через те же валидированные CLI/API. Визуал — из `ui` metadata типа | CLI стабилен, machine-readable API/JSON контракты для нужных операций есть, понятно, что UI добавляет ценность поверх файлов/агента. Веб не обязателен, не хранит вторую копию истины |

**Предварительные go/no-go для PoC (уточнить после baseline):** (a) 100% известных дефектов в synthetic fixtures обнаруживаются и локализуются точно; (b) на реальном корпусе пользователи считают ≥90% показанных actionable diagnostics действительно проблемами — иначе сузить rules; (c) retrieval не хуже лучшего baseline на выбранных задачах и укладывается в бюджет вывода; (d) перенос полного root в новый путь с удалённым cache/index проходит без ручного исправления absolute paths; (e) хотя бы 3 pilot users возвращаются к check/search на своих реальных данных в течение 2 недель и могут назвать повторяющуюся выгоду.

---

## 13. Критерии успеха и метрики

Измерять на зафиксированном корпусе и held-out задачах (model/harness или `none` для deterministic test, версии Skill/config/parser, N, dataset split, exact scoring, total input/output bytes/tokens, latency, все failure cases):

- **Retrieval:** Recall@k / MRR / nDCG на размеченных запросах, попадание ожидаемого source section, время до правильного ответа, bytes/tokens на задачу. Маленький top-1 с пропущенным источником — не экономия контекста.
- **Диагностика:** доля найденных issues с верной source location; precision полезных fixes, false-positive rate, доля принятых предложений; 100% synthetic defects с точными locations.
- **Переносимость:** clean relocation + время cold rebuild; 0 ручных исправлений absolute paths.
- **Capture/query:** end-to-end success capture → validate → link → aggregate → cite source; время выполнения задачи; размер context; лишние действия/неправильные type/file selections/избыточные чтения агента.
- **Пилот:** ≥3 пользователей возвращаются в течение 2 недель и называют повторяющуюся выгоду; ≥90% actionable diagnostics признаны реальными проблемами.
- **Безопасность:** 0 исполнений кода/prompt из DATA_ROOT; 0 молчаливых перезаписей; 0 скрытых сетевых/LLM-вызовов в ядре.

Рекламировать цифры только для конкретного frozen corpus, tokenizer, versions и benchmark. Не обещать фиксированное снижение затрат или безошибочность по числу tool calls.

---

## 14. Открытые вопросы и решения по умолчанию

| # | Вопрос | Рекомендация (default) |
|---|---|---|
| Q1 | Минимальный Python? | `>=3.12`; если нужен 3.11 — обход через совместимые API + CI на 3.11 |
| Q2 | Где хранить dataset metadata? | `<DATA_ROOT>/.todoc/`; локальный override — `<folder>/.todoc.json`. Переименование (`todoc/`/`.agentdocs/`) — только до первого schema version |
| Q3 | Generated type guide? | Общая справка по schema — в Skill `references/`; dataset-specific — stdout или явный `--out` в `.todoc/generated/`. Не писать dataset-specific guide в общий Skill по умолчанию |
| Q4 | Запись и исправления? | Существующие sources review-first; сначала diagnostics + preview, затем безопасный `--apply`; create-only новые Markdown notes и JSON records допустимы по validated type/template. Нужна ли позже правка существующих CSV/JSON или достаточно проверки/чтения + новых записей? Первый vertical slice: `workout`, иной personal log или проектный entity type? |
| Q5 | Идентичность и granularity? | `dataset_id` + stable document/record IDs; path не использовать как постоянную идентичность; один JSON-файл = одна запись в v1. Нужна ли позже поддержка множества records внутри CSV/table sources? |
| Q5a | Отношения и граф? | Явные typed refs в record/front matter + derived graph index без отдельной graph DB. Первый набор relation types? Нужны ли cross-dataset references позже? |
| Q6 | `harnes`/`harness`? | Каноническое `harness`; `harnes` — alias только если это существующий реальный путь |
| Q7 | Несколько корней? | CLI принимает один или несколько `--root`, обрабатывает независимо. Multi-root check/scan не смешивает configs; объединённый поиск — явный режим с root/dataset ID в каждом результате |
| Q8 | Главная персона/проблема? | Один автор vault, разработчик/аналитик с CSV/JSON + Markdown или maintainer базы для агента? Решить интервью и примерами из собственных папок, не архитектурой |
| Q9 | Obsidian compatibility? | Базовый `.md` + YAML + relative links. Нужна ли проверка wikilinks/embeds/backlinks и какой реальный subset должен работать? |
| Q10 | Добавление знаний? | Начать с `new`/`capture` в `inbox/` или копировать/import-ить существующие файлы? Рекомендация — capture first, import/copy только после preview; URL/LLM ingestion отложить |
| Q11 | Поиск и представления? | Встроенный deterministic lexical/metadata или thin integration с QMD/другим движком? Какие bounded views нужны помимо исходного Markdown/JSON? Рекомендация — benchmark + retrieval/ranking/rerank ports; external vector/graph/reranker по умолчанию не реализовывать |
| Q12 | Go/no-go? | Какую частоту и выгоду считать достаточными? Предложенные пороги пилота есть в §12, согласовать после baseline |
| Q13 | Главная цель? | Source QA/search, typed records/aggregate или agent memory? Выбрать один проверяемый vertical slice. Если нужны задачи/планы/тренировки/персональные сущности/межсессионное состояние — какие schemas, units/metrics, связи, статусы/переходы, capture и запросы обязательны? Утвердить как отдельный профиль до реализации |

Полноценную реализацию CLI начинать только после отдельного решения пользователя.

---

## 15. Глоссарий

| Термин | Значение |
|---|---|
| **DATA_ROOT** | Переносимая папка знаний пользователя (один или несколько `--root`). Содержит `.todoc/` конфиг + исходные файлы |
| **Dataset** | Один DATA_ROOT с `dataset_id`, config/index namespace и identity space |
| **Format** | Физический синтаксис файла (`markdown`/`csv`/`json`); выбирает parser/writer |
| **Doc type** | Семантический тип документа (`adr`, `glossary-entry`, `research-note`); может встречаться в любом каталоге |
| **Dir type** | Роль/профиль папки (`plan`, `research`, `glossary`); может наследоваться детьми |
| **Entity type** | Тип file-backed записи (`note`, `research`, `link`, `workout`, `person`, `product`, `plan`); JSON Schema + template + relations + views |
| **Relation type** | Тип связи между объектами (`performed_by`, `derived_from`, `supports`); source/target constraints + cardinality |
| **Record** | Одна типизированная запись (в v1 — один JSON-файл с `record_id` + `entity_type`) |
| **ObjectRef** | Стабильная ссылка (`kind`, `id`, optional `type`); не хрупкая строка пути |
| **Diagnostic** | Структурированная ошибка/предупреждение: `{id, code, severity, message, location, evidence}` + optional `suggested_fixes` |
| **WritePlan** | План записи: target, patch/new content, expected/new hash, preview diff, writer, validations |
| **Generation** | Атомарный снимок индексов (`folders/documents/records/relations/diagnostics`); публикуется через `CURRENT.json` |
| **Bounded projection** | Ограниченная выдача (section/pointer/columns/rows/fields) с `truncated`/cursor/provenance |
| **Trusted workflow** | Установленный Skill/workflow по whitelisted `workflow_id`; не prompt/код из DATA_ROOT |
| **OKF** | Open Knowledge Format v0.2: Markdown + YAML front matter, relative links, provenance/trust/freshness/lifecycle; опциональный профиль совместимости |

---

## 16. Источники и связь с конкурентным анализом

- Инженерный набросок: [`../plan.md`](engineering-draft.md) (§1–§18, особенно §1.3 — пользовательское видение, §3 — аналоги, §3.6 — аудит Skills, §5–§16 — архитектура/CLI/этапы).
- Статический аудит Skills: [`../docs/research/knowledge-base-comparative-audit.md`](../research/knowledge-base-comparative-audit.md) (snapshot commit hashes, coverage matrix, пробелы memory-профиля).
- Конкурентный анализ: [`competitive-analysis.md`](competitive-analysis.md) — полный список CLI команд (вход/выход), мастер-список возможностей с вердиктом «нужен ли todoc», сравнительные таблицы, портабельность как критерий, аудитория, сравнение между собой и с `todoc`.
- Принципы CLI/MCP/Markdown: `docs/guides/cli-for-agents.md`, `docs/guides/mcp-for-agents.md`, `docs/guides/markdown-knowledge-for-agents.md`, `docs/research/mcp-cli-agents.md`.
- Первичные спецификации: Agent Skills specification, PyPA (src layout, `pyproject.toml`, entry points), Click, Python `typing.Protocol`, `pluggy`, JSON Schema 2020-12 + `jsonschema`, Python `csv`, `markdown-it-py`/CommonMark, `pathlib`, OWASP Input Validation, SQLite FTS5. Полные ссылки — в `plan.md` §18.

> **Граница применимости.** Техническая документация показывает контракты и официально описанные функции, но не гарантирует корректность продукта на конкретном корпусе. Конкурентная таблица — feature audit, не market sizing, adoption/demand research или независимый quality benchmark. Всё из конкурентного среза надо проверять на закреплённых версиях реальных инструментов, одинаковых данных и пользовательских задачах.
