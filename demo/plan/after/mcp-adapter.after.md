---
id: doc:after-mcp-adapter
title: "AFTER: MCP-адаптер"
doc_type: after-plan
lang: ru
source: docs/plan/mcp-adapter.after.md
copied: true
---

# Перспектива (НЕ сейчас): MCP-адаптер (tools + resources + prompts)

**Статус:** FUTURE — не реализуется в MVP. Этот файл описывает, **как** MCP вставится поверх application-слоя без второго API с собственной семантикой, по лучшим традициям построения MCP.
**Версия:** 0.2 (обогащено 24 ноября 2026 по корневому гайду MCP, research MCP/CLI, гайдам CLI/Markdown и аудиту Skills).
**Дата:** 24 ноября 2026 года.
**Связанные документы:** [`implementation-plan.md`](../implementation-plan.md) §2 (порты E8/E10), §4 Этап 0.5/5–7, §6, §16 (традиции MCP и хранилища памяти); [`constitution.md`](../constitution.md) §6.11, FR-10, S11, C21; [`competitive-analysis.md`](../competitive-analysis.md) §4.2 (QMD, mdkb, Basic Memory MCP), §5.2/5.3/5.6, §6 C21.
**Источники традиций (корень репозитория):** `docs/guides/mcp-for-agents.md` (постулаты 1–26, часть II — вызов агентом, часть III — оценка + pre-release чек-лист; редакция MCP **2026-07-28**), `docs/research/mcp-cli-agents.md` (§1–§13), `docs/guides/cli-for-agents.md` (постулаты 23–26 — поиск, выбор поверхности, входы, выходные поля), `docs/guides/markdown-knowledge-for-agents.md` (§VII процедуры ingest/query/write/lint, §VIII ступени поиска, §X trust/authority/freshness/access, §XI протокол benchmark-а, §XIII Python CLI-каталог), `docs/research/knowledge-base-comparative-audit.md` (§5 coverage matrix, §6 рекомендации 1–9).

> **Как читать.** Слова **MUST / SHOULD / MAY** — нормативные. **[STD]** — требование спецификации MCP 2026-07-28; **[GUIDE]** — рекомендация гайдов/OWASP/Anthropic/OpenAI; **[ЭВРИСТИКА]** — гипотеза для измерения на целевых клиентах/моделях. MCP — официальный протокол, но не RFC IETF; JSON-RPC 2.0 и JSON Schema 2020-12 — самостоятельные спецификации. Количество tools, форма `--json`-подобных wrappers, размер ответа и проценты экономии токенов — **не нормы MCP**.

---

## 1. Что это и зачем

Тонкий MCP-сервер поверх того же application-слоя, что и CLI:

- **Tools** — model-controlled операции/вычисления, которые клиент/модель может вызвать (`search`, `read`, `records_query`, `records_create_preview`, `check` и т.д.).
- **Resources** — application-driven адресуемый контекст (документ, фрагмент, схема, тип), который клиент открывает по URI по необходимости.
- **Prompts** — шаблоны сообщений/рабочих сценариев для повторяемых сценариев (capture/query/lint), если серверу нужно предложить образец взаимодействия.

**Ценность:** агенты в MCP-клиентах (Claude Desktop/Code, Cursor, VS Code, Windsurf и др.) получают `todoc` без shell. **Цена:** MCP-поверхность, совместимость редакций, stateless-модель, права на каждый вызов.

**Конкуренты-референсы:** QMD (`qmd mcp`, tools `qmd_search`/`qmd_vsearch`/`qmd_query`/`qmd_get`/`qmd_multi_get`/`qmd_status`), mdkb (stdio MCP, read-only по умолчанию, `--allow-write` — 2 write tools), Basic Memory (MCP tools `write_note`/`read_note`/`edit_note`/`move_note`/`delete_note`/`search_notes`/`build_context` и др. + schema/project tools + аннотации read-only/destructive/idempotent), Open Knowledge (`okn mcp` + WebMCP tools), okf-gem (`okf-mcp`). Все показывают: MCP — транспорт, не второй источник истины.

### 1.1. MCP vs CLI vs Skill: дерево решения (guide MCP 23, CLI 24)

MCP tool — интерфейс к полезной операции, а не способ сериализовать каждую мысль агента или endpoint. Добавлять tool, когда агенту требуется capability вне его контекста: актуальные/авторизованные данные, воспроизводимая обработка значимого объёма, точная бизнес-проверка или side effect. Если нужные факты уже в контексте и остаётся небольшая семантическая оценка/формулировка — пусть это делает модель без нового вызова.

```text
Достаточно ли агенту имеющегося контекста для ответа/решения без риска?
├─ Да → не вызывать MCP только ради формальности.
└─ Нет → нужны данные или операция?
   ├─ Адресуемое содержимое, которое клиент выбирает/читает → resource.
   ├─ Поиск, проверка, изменение или иная операция, выбранная моделью → tool.
   └─ Объёмная детерминированная обработка → tool с фильтром/лимитом,
      агрегированным выводом и продолжением по cursor, не весь dataset в контекст.
         ↓
Есть неоднозначность намерения или рискованный выбор?
├─ Да → вернуть ограниченные варианты/evidence; агент уточняет у пользователя.
└─ Нет → валидировать данные/права, выполнить точный контракт и вернуть итог.
```

**Правило размещения для `todoc` (MUST):**
- Локальный repo/filesystem/stdin/stdout, shell-pipeline, имеющийся CLI → **CLI** с ограниченным машинным контрактом (первичный контракт, P11).
- Capability должна обнаруживаться/вызываться через MCP-host по типизированной схеме с серверными правами и аудитом → **tool** для операции, **resource** для адресуемого контекста.
- Задача нужна обоим видам клиента → **одна domain implementation, тонкие CLI/MCP adapters**; не дублировать бизнес-правила.
- Не добавлять интерфейс лишь из-за ярлыка «для агента». Не оборачивать каждый endpoint в отдельный tool: начинать с повторяемых high-value задач с ясным результатом; объединять шаги, только если они естественно образуют один частый workflow и не прячут разные риски. Не делать универсальный `do_anything`/`execute_query`.

**Хорошие примеры (guide MCP 23):** пользователь уже прислал два плана и критерии выбора → агент сравнивает без MCP (не расходуется токен-бюджет). Нужен статус просроченных заказов из авторизованной системы → `search_orders(status="overdue", limit=20)` фильтрует на сервере, возвращает summaries + IDs; `get_order(order_id)` раскрывает детали. Read/query и изменение состояния — разные tools с отдельной проверкой прав.

**Плохие примеры:** универсальный `handle_request(instructions: string)` «разберись с плохими заказами и исправь их» (смешаны семантика и side effect, нет target/schema/места для уточнения); отдельный tool на каждый endpoint/поле (`get_order_status`, `get_order_owner`, …) или один `execute_sql` на все строки (каталог разрастается, контекст перегружается).

## 2. Почему НЕ сейчас

1. **CLI — первичный контракт** (P11). MCP без стабильного CLI/application-слоя будет переделываться.
2. **Нужны стабильные use cases:** `SearchObjects`, `ReadProjection`, `QueryRecords`, `CreateRecord` (preview), `ValidateRecord` — с теми же статусами/безопасностью, что и CLI.
3. **MCP 2026-07-28 stateless:** старые ожидания о `initialize`/сессиях нельзя переносить автоматически. Совместимость с прежними редакциями — явный выбор и тесты. Без этого — риск несовместимости с клиентами/SDK.
4. **Нужен eval на слабейшей модели** (guide MCP III): ясные схемы снижают риск ошибок, но не дают гарантии безошибочности. MCP без eval — недоказанная поверхность.

## 3. Лучшие традиции MCP: правила M1–M26 (нормативные для `todoc`)

Сжатое изложение постулатов `docs/guides/mcp-for-agents.md` 1–26 + `docs/research/mcp-cli-agents.md` §3–§9, адаптированное к `todoc`. Полные формулировки, примеры и ссылки — в гайде; здесь — то, что MUST соблюсти при реализации.

| ID | Правило | Источник |
|---|---|---|
| **M1** | Для каждой задачи — правильная поверхность: tools — model-controlled операции, resources — адресуемые данные/контекст, prompts — повторяемые шаблоны. Не превращать всякий источник данных в action-tool и не помещать запись в resource | Guide MCP 1 [STD/GUIDE] |
| **M2** | Дизайн tools с намерений, не копированием endpoint: небольшой набор отдельных по смыслу workflow-инструментов. Объединять шаги, которые почти всегда идут вместе и имеют одну ясную цель; разделять разные цели, права и риски. Не делать `do_everything`/`execute_query` | Guide MCP 2 [GUIDE] |
| **M3** | Имя различает действие и область; каталог стабилен: уникальные имена в пределах сервера, 1–128 символов, ASCII-буквы/цифры/`_`/`-`/`.`, case-sensitive [STD]; при агрегации серверов — префикс/namespace (`todoc.search`); детерминированный порядок tools, пока набор не изменился; каталог может зависеть от авторизации, но не от соединения/побочного эффекта | Guide MCP 3 [STD] |
| **M4** | Описание — краткая инструкция выбора: цель; когда/когда не использовать; scope; смысл важных аргументов; формат/единицы/timezone; побочный эффект; limit, полноту и способ продолжения. Без внутренней реализации, но без существенных вопросов. Server-supplied description/schema — возможная поверхность prompt injection | Guide MCP 4 [GUIDE] |
| **M5** | Аргументы — типизированный, семантически однозначный контракт: `inputSchema` — валидный JSON Schema object; без `$schema` MCP применяет JSON Schema 2020-12. Для каждого поля: required/optional, absent vs `null`, формат, единицы, диапазон, enum, длина/число элементов, default и сочетания. JSON Schema `default` значение не подставляет: сервер явно реализует и описывает дефолт. Схема не заменяет бизнес-валидацию | Guide MCP 5 [STD/GUIDE] |
| **M6** | Закрывать схему осознанно: `additionalProperties: false` полезно для закрытого контракта, но не универсальное требование MCP. Сверять поддержку `$ref`/composition/форматов у каждого SDK/host. OpenAI strict function calling — отдельное ограничение (`additionalProperties: false`, все поля в `required`, nullable для необязательности), не требование MCP/JSON Schema | Guide MCP 6 [STD/PLATFORM] |
| **M7** | Не просить модель генерировать произвольную программу/shell/SQL/URL без границ: типизированная предметная операция вместо общего исполнительного интерфейса. Если язык необходим — ограничить грамматику, права, таблицы/поля, URL allowlist, размер и время; проверить traversal/SSRF/injection на сервере | Guide MCP 7 [GUIDE] |
| **M8** | Валидировать и авторизовывать на доверенной стороне при каждом вызове: входная схема, бизнес-правила, tenant/object access, разрешённая операция и лимиты на сервере. Доступность tool модели ≠ право на действие; валидный ID ≠ авторизация | Guide MCP 8 [STD/SECURITY] |
| **M9** | Машинно надёжный результат + output schema: для стабильных данных задавать `outputSchema`; сервер MUST возвращать соответствующий результат, клиенту SHOULD валидировать. Использовать `structuredContent`; MCP 2026-07-28 допускает любое JSON-значение. Для обратной совместимости SHOULD вернуть сериализованный JSON также в `TextContent` — проверить, не попадает ли дубль дважды в контекст клиента. Для non-JSON — подходящий block type (text/image/audio/resource link) | Guide MCP 9 [STD] |
| **M10** | Полезный минимум; явно полнота и происхождение: ровно данные для ответа/следующего вызова (ID, релевантные поля, количество, scope, единицы, время/источник, если влияют на смысл). Пустой результат — штатный; частичный/обрезанный — явно отметить, объяснить и дать путь к деталям. Не выдавать top-N за полную выдачу | Guide MCP 10 [GUIDE] |
| **M11** | Большие списки — фильтр/лимит/cursor; пагинацию tool-результата определить отдельно: MCP cursor-пагинация стандартизована для `tools/list`/`resources/list`/`resources/templates/list`/`prompts/list`, она не добавляет автоматическую пагинацию произвольному `tools/call`. Для большого tool-результата — отдельный `limit`/opaque cursor или ресурс. Cursor непрозрачен; отсутствие `nextCursor` — конец; invalid cursor — `-32602`. Между страницами нет snapshot consistency: возможны дубли/пропуски | Guide MCP 11 [STD/GUIDE] |
| **M12** | Различать протокольную ошибку и ошибку выполнения tool: JSON-RPC `error` — проблема запроса/протокола; ошибка принятого tool-вызова — result с `isError: true`. Краткая причина, поле/ограничение, стабильная категория, исправимый следующий шаг; без секретов/stack trace. `resultType` (complete/input-required) не заменяет `isError` | Guide MCP 12 [STD] |
| **M13** | Stateless: сервер не выводит контекст/пользователя из прошлого вызова/соединения. Межвызовное состояние — явный непрозрачный handle с TTL/expiry; права на handle проверяются заново при каждом вызове. Handle — имя, не authorization token; bearer-capability — только с достаточной энтропией и коротким сроком. Не повторять необратимую операцию после timeout без проверки статуса/идемпотентности | Guide MCP 13 [STD/GUIDE] |
| **M14** | Кэшировать только по scope и свежести: для complete-ответов `server/discover`, списков tools/prompts/resources/templates и `resources/read` — кэш-подсказки `ttlMs`/`cacheScope`. TTL — hint свежести, не гарантия неизменности; `0` — немедленное устаревание. `private` нельзя шарить между authorization contexts; `public` — только для реально неперсонального результата. Кэш — не авторизация. Стабильный порядок tools помогает кэшировать определения | Guide MCP 14 [STD] |
| **M15** | Раскрывать каталог постепенно: при большом наборе — короткие доменные подсказки + малый набор частых tools; остальное — поиском/отложенной загрузкой, полный schema только для кандидатов по задаче. Tool search/deferred loading — архитектурный/вендорский механизм, не обязательная часть MCP. `<20` tools на старте — soft heuristic OpenAI, не стандарт | Guide MCP 15 [GUIDE/ЭВРИСТИКА] |
| **M16** | Разделять данные и инструкции: tool descriptions, resources и outputs — недоверенное содержимое; результаты могут содержать prompt injection. Маркировка «данные» — полезная мера, не защита. Аннотации tool — подсказки поведения, не авторизация/policy. Sensitive/destructive calls — контроль снаружи: точные параметры, deny/confirm, enforce policy на доверенной стороне | Guide MCP 16 [STD/SECURITY] |
| **M17** | Защищать транспорт/credentials/локальный процесс: удалённый Streamable HTTP — TLS + аутентификация; валидировать `Origin`, невалидный — 403. Локальный HTTP — bind localhost. Авторизовывать каждый защищённый вызов/ресурс; не передавать токен не тому audience/upstream. Не помещать секреты/PII в `x-mcp-header`. stdio stdout — только MCP framing; логи — stderr; stdio не sandbox-ит процесс | Guide MCP 17 [STD/SECURITY] |
| **M18** | Лимиты/таймауты/аудит/least privilege по эффекту: rate/concurrency/size/time/cost budgets; ограничение system permissions; журнал actor/действие/результат/корреляция с редактированием секретов/PII. Риск — по реальным эффектам: чтение приватных данных тоже может быть высокорисковым | Guide MCP 18 [STD/SECURITY] |
| **M19** | Диагностика полезна по задаче, но имена `status`/`doctor` не предписаны MCP: при зависимости от auth/конфигурации/прав/сети/внешних бинарников — отдельная read-only диагностика, например `get_status` (компактный снимок) + `run_diagnostics` (проверки с `scope`/`checks`) + `get_finding` (раскрытие по ID). Tool — для вычисляемой/on-demand проверки, resource — для адресуемого состояния. Стабильные ID, `pass/warn/fail`, подсистема, безопасные рекомендации. Проверка не меняет конфигурацию; исправление — отдельный авторизованный tool с подтверждением. Без секретов/токенов/неотфильтрованных внутренностей | Guide MCP 19 [GUIDE] |
| **M20** | Резюмировать tool-результат; ошибки исправимые: успешное изменение — кратко действие + стабильный ID/target + итоговое состояние/счётчик + предупреждения. Мало findings — поштучно; много — сводка, группы по общей причине, severity, количества, несколько примеров, явный путь к деталям. Порог 5 findings — эвристика. Стабильные codes/IDs + 1–2 релевантных следующих действия, не полный каталог tools и не auto-fix. `issues_found` — успешный tool result; `isError: true` — только ошибка выполнения, мешающая операции | Guide MCP 20 [STD/GUIDE/ЭВРИСТИКА] |
| **M21** | Большие деревья — summary → оглавление → выбранная ветвь (progressive disclosure): краткие итоги/счётчики → компактное оглавление групп/путей/типы/признаки усечения → детали только выбранной группы/`finding_id`/поддерева на заданной глубине. Условные параметры (`section`, `path`/`pointer`, `max_depth`, `fields`, `limit`, opaque cursor) — в schema, с лимитами. Для больших артефактов — ссылка на resource, если клиент поддерживает. Плоская `path = value` — обзор, не стандарт MCP и не формат patch. Адресация значения JSON — JSON Pointer (RFC 6901); изменения документа — patch по согласованному формату, например JSON Patch (RFC 6902) | Guide MCP 21 [GUIDE; RFC 6901/6902] |
| **M22** | Prompt caching — бонус, не основание для лишних вызовов: MCP-кэш (`ttlMs`/`cacheScope`, M14) ≠ provider prompt/KV-cache. Кэш модели не задаётся MCP и не гарантируется каждым tool-call. Не делать лишние round-trip «ради cache hit»; сравнивать task success, суммарные вызовы/latency, usage и реальные cache hit/miss на целевом host/model | Guide MCP 22 [GUIDE] |
| **M23** | Сначала решить, нужен ли tool; границу — по workflow (см. §1.1): tool — интерфейс к полезной операции, не сериализация каждой мысли/endpoint. Добавлять tool при capability вне контекста (данные, воспроизводимая обработка, бизнес-проверка, side effect). При смешанном workflow tool извлекает/ограничивает факты/кандидатов, агент оценивает смысл. «Детерминированный» ≠ «безопасный»: authorization/scope/бизнес-ограничения/повтор/side effects — на сервере | Guide MCP 23 [GUIDE] |
| **M24** | Контракт входа под явное решение агента: имя + описание + `inputSchema` однозначно отвечают что делает tool, когда вызывать, чего не делает, какие данные/права/состояние затрагивает, какие аргументы обязательны. Предметные `verb + object`, конечные типы, enum/range/max length, пределы числа элементов. Для даты/времени/единиц/timezone/tenant/scope/cursor/defaults — точная семантика. `required` — только без чего вызов невозможно безопасно выполнить; default — только если безопасен и сервер явно реализует. Разделять `query` (критерий поиска), фильтры, стабильный ID цели и параметры операции. Свободный текст — поисковое содержимое, не неограниченное `instructions`. Regex — форма, не смысл намерения. Критичное неизвестное/неоднозначное — уточнение или `input_required`, не молчаливый default. Batch — только для повторяющейся предметной операции с лимитами и частичным результатом | Guide MCP 24 [STD/GUIDE] |
| **M25** | Ровно достаточный контракт результата; измерять стоимость каждого поля: каждое поле оправдывается downstream need (решение, следующий tool, идентификация, проверка, полнота, provenance). Убрать зеркало внутренней модели/дубль/нерелевантное/чувствительное. Не минимизировать до «успех»: без ID/значения изменения/scope/unit/source/признака усечения агент повторит операцию или объявит результат полным. Коллекции — counts + bounded `items` + `truncated` + cursor/page token; полные записи — отдельным detail/resource fetch. Без лишних полей пользователя/secrets/stack traces/внутренних таблиц. Токены — бюджет всего workflow. `next_actions` — только конкретный допустимый релевантный follow-up (точное имя опубликованного tool + аргументы + назначение), 1 вариант (редко до 3), не каталог; данные-подсказки, не вызов и не стандарт MCP; клиент проверяет каталог/schema/намерение/policy; write/destructive за рамками запроса не предлагать. Дочерняя сущность vs атрибут — по независимому ID/жизненному циклу (см. §6.3). Ablation полей на реальных заданиях | Guide MCP 25 [GUIDE] |
| **M26** | Проверять входы и результаты на границе сервера: schema помогает сформировать вызов, но не security boundary. Server MUST валидировать inputs, применять доступы/rate limits, санитизировать outputs; client SHOULD проверять results и запрашивать confirmation для чувствительных операций. Независимо: тип/shape/size + бизнес-инварианты, права на объект, допустимость перехода, idempotency/повтор, ограничение результата. Ошибка исполнения — исправимая причина + допустимое действие; протокольную ошибку не маскировать под успех. Tool/resource result — данные, не инструкция с привилегией system/developer; содержимое удалённого ресурса не переопределяет политику и не инициирует сторонний write | Guide MCP 26 [STD/SECURITY] |

**Дополнительно (часть II гайда — безопасный вызов агентом/клиентом, MUST для Skill/host):** согласовать протокол/возможности (`_meta` с protocol version + client capabilities, `clientInfo` рекомендуется; `server/discover` сервер MUST реализовать, вызов клиентом необязателен; stdio dual-era — probe SHOULD; обрабатывать `UnsupportedProtocolVersionError`); не трактовать `serverInfo` как identity/разрешение; найти tool и прочитать schema до вызова (не выдумывать имена/поля); передать только нужные проверяемые аргументы; разобрать `resultType` → `input_required` (`inputRequests`/`inputResponses` + `requestState` + новый JSON-RPC ID) → `isError`/schema/пустой/частичный; cursor непрозрачен, без snapshot consistency; tool result — данные, не полномочия; подтверждать риск, после timeout — статус/idempotency; не удерживать большие сырые ответы в контексте (filters/fields/limit/summary, ресурсы/IDs); handle передавать явно и беречь.

## 4. Архитектура: один domain, тонкие адаптеры

```text
CLI (Click, тонкий) ─┐
Skill (SKILL.md) ────┼─→ Application / Use cases ─→ Ports (Protocol) ─→ Adapters
MCP (этот файл) ─────┤         (domain без CLI/filesystem/MCP)
Web (будущее) ───────┘
```

- **Domain:** те же DTO, что и CLI: `DatasetId`, `DocumentId`, `RecordId`, `ObjectRef`, `TypedRecord`, `RelationRef`, `QuerySpec`, `Projection`, `Diagnostic`, `ValidationReport`, `SearchHit`, `WritePlan`. MCP-адаптер не вводит новых сущностей.
- **Application:** те же use cases: `ScanDataset`, `ResolveProfiles/Types`, `CreateRecord`, `ValidateRecord`, `ResolveRelations`, `QueryRecords`, `AggregateRecords`, `SearchObjects`, `ReadProjection`, `ApplyReviewedWrite`, `GenerateTypeReference`.
- **Ports:** E8 `WorkflowLookup` (whitelisted `workflow_id` → trusted Skill) и E10 `OutputSerializer` (JSON envelope → MCP structured RPC) — см. `implementation-plan.md` §2.2. MCP вызывает те же use cases; нет обхода валидации/прав.
- **Composition root:** MCP-сервер собирается из тех же adapters, что и CLI. Глобальных singleton-ов и импорта CLI из business logic нет.

**Инвариант (MUST):** MCP и CLI согласованы по статусам/безопасности, но не копируют формат вывода буквально. MCP — структурированный RPC (`structuredContent` + `TextContent`); CLI — терминальный + composable-поверхность ОС (stdout/stderr/exit status). Один смысл — много транспортов (P11).

### 4.1. Транспорт, discovery, версии

1. **Транспорт v1 — stdio.** Stdout процесса — только MCP framing; логи/диагностика — stderr (M17). HTTP (Streamable HTTP) — только при доказанной боли (удалённая capability, несколько hosts). Для HTTP: TLS + аутентификация, валидация `Origin` (невалидный — 403), локальный HTTP — bind localhost.
2. **Discovery:** сервер MUST реализовать `server/discover` (редакция 2026-07-28). Результат обычного RPC MUST содержать `resultType` (`complete` / `input_required`). Клиент, совместимый со старым сервером, учитывает отсутствие `resultType` в старом ответе. Запросы несут protocol version + client capabilities в `_meta`; `clientInfo` рекомендуется. Legacy `initialize`-handshake не переносить автоматически; совместимость со старыми редакциями — явный выбор + тесты на целевых SDK.
3. **Identity:** `serverInfo` — self-reported metadata, не security credential. Provenance/авторизация/policy — отдельно (M26).
4. **Каталог:** детерминированный порядок tools, пока набор не изменился; каталог может зависеть от авторизации, но не от соединения/побочного эффекта (M3). Стабильный порядок помогает кэшировать определения и prompt (M14, M22).

### 4.2. Stateless и handles

- Сервер не выводит контекст/пользователя из прошлого вызова/соединения (M13). Межвызовное состояние (корзина, транзакция, длительная задача) — явный непрозрачный handle с TTL/expiry; права на handle проверяются заново при каждом вызове.
- Для `todoc` в v1 handles не нужны (все операции — запрос/ответ по явным `--root`/`dataset_id` + `id`/`cursor`). Если появится длительная операция (index rebuild с прогрессом) — handle с TTL + проверка статуса вместо повторного запуска.
- Не повторять необратимую операцию после timeout, пока не проверен статус или идемпотентность (M13, M26).

### 4.3. Кэширование

- Для `server/discover`, списков tools/prompts/resources/templates и `resources/read` — кэш-подсказки `ttlMs`/`cacheScope` (M14). TTL — hint свежести, не гарантия неизменности; `0` — немедленное устаревание.
- `cacheScope: private` — только в том же контексте авторизации; запрещено шарить между контекстами доступа. `public` — только для реально неперсонального результата (например, список tools одинаковый для всех). Кэш — не авторизация.
- Для `todoc`: список tools — `public` (одинаковый для всех); документы/записи пользователя — `private`, ключ связан с auth-контекстом. Страницы кэшируются независимо; scope совпадает на всех страницах.
- Prompt/KV-cache провайдера — отдельный слой (M22). Не проектировать вывод в расчёте на cache-hit; измерять `cached_tokens`/usage/latency на целевом host/model.

## 5. Каталог tools/resources/prompts для `todoc`

### 5.1. Именование и описания

- Имена — уникальные в пределах сервера, `todoc.<verb>_<object>` или `todoc.<object>_<verb>` (M3). Примеры: `todoc.search_docs`, `todoc.read_doc`, `todoc.query_records`, `todoc.check`, `todoc.get_status`. Не использовать голое `search` (коллизия при агрегации серверов).
- Описание (M4) — краткая инструкция выбора: цель; когда/когда не использовать (с указанием альтернативы); scope; смысл важных аргументов; формат/единицы/timezone; побочный эффект; limit/полноту/способ продолжения. Без внутренней реализации. Считать description/schema возможной поверхностью prompt injection (M16).
- Аннотации MCP (`readOnlyHint`, `destructiveHint`, `idempotentHint` и т.д.) — подсказки поведения, **не авторизация и не доказательство безопасности** (M16, M26). Клиент не считает `readOnlyHint` доказательством отсутствия риска.

### 5.2. Tools v1 (read-only)

Все tools — thin wrappers над application use cases. Вход — явный, типизированный, ограниченный контракт (M5, M24); выход — `outputSchema` + `structuredContent` (M9, M25).

| Tool | Use case | Вход (ключевые поля) | Выход (`structuredContent`) |
|---|---|---|---|
| `todoc.search_docs` | `SearchObjects` | `query` (текст для поиска, не инструкция), `within?` (path/section-id, охватывает дочерние по умолчанию), `format?`/`doc_type?`/`dir_type?` (enum), `limit` (bounded, default + max), `cursor?` (opaque), `fields?` (проекция) | `total`, `returned`, `truncated`, `next_cursor`, `items: [{id, path, title, heading_path, rank, relevance.method, matched_terms, snippet{text, line_start, line_end, snippet_truncated}}]`, `next_actions?` (0–1, только если follow-up очевиден) |
| `todoc.read_doc` | `ReadProjection` | `id` (стабильный, required) или `path` + `dataset_id`, `selector?` (`section`/`anchor`/`line_range`/`pointer`/`columns`/`rows`/`where` — bounded, без `eval`/SQL), `budget?`, `fields?` | Проекция фрагмента + `path`, `heading_path`, `hash`, `truncated`, `provenance` (parser/schema versions). Полный текст — только по явному запросу |
| `todoc.query_records` | `QueryRecords` | `entity_type` (required, enum из registry), `filter?` (allowlisted AST, не Python/SQL), `project?`, `limit`/`cursor` | `total`, `items` (bounded summaries с ID), `truncated`, `next_cursor`. Полные записи — через `todoc.read_record` |
| `todoc.aggregate_records` | `AggregateRecords` | `entity_type`, `metric` (required), `group_by?`, `period?` (timezone policy) | `value`, `metric_definition`, `units`, `formula`, `timezone/date_policy`, `incoming_ids/paths/pointers`, `completeness_status`. Unknown metric/unit → `isError` с исправимым сообщением, не догадка |
| `todoc.check` | `ValidateDataset` (сводка) | `dataset_id`/`root` (required), `scope?` (`checks`/`section`) | `status: issues_found|ok`, `summary{checks_total, passed, errors, warnings, findings_total}`, `groups[{id, errors, warnings, count}]`, `findings` (первые N по порогу 5, эвристика), `page{returned, total, truncated, next_cursor}`. `issues_found` — успешный result, не `isError` (M20) |
| `todoc.get_status` | Быстрый снимок (M19) | `scope?` (`workspace`/`dataset`) | Компактный read-only снимок: generation, counts, freshness. Не запускает тяжёлые проверки |
| `todoc.run_diagnostics` | Набор проверок (M19) | `checks?` (enum: `auth`/`filesystem`/`config`/`index`/`links`), `detail?` (`summary`/`full`) | Стабильные ID, `pass/warn/fail`, подсистема, безопасные рекомендации. Без секретов/токенов/полного config |
| `todoc.get_finding` | Раскрытие по ID (M19, M21) | `finding_id` (required) | Одна диагностика полностью: `code`, `severity`, `message`, `location`, `evidence`, `suggested_fixes?` (rationale, не auto-apply) |
| `todoc.inspect_tree` | Оглавление/ветвь (M21) | `root?` (`services`/`docs`), `max_depth?`, `limit`, `cursor?`, `pointer?` | `outline[{id, pointer, findings}]`, `total`, `truncated`, `next_cursor`. Затем `inspect_tree` с `pointer` или `get_finding` раскрывает ветвь |
| `todoc.list_types` / `todoc.show_type` | `ResolveProfiles/Types` | `entity_type?`/`doc_type?` | Каталог типов + поля/шаблон/единицы. `show_type` — для capture-диалога |

**Правила каталога (MUST):**
- Старт — малый набор частых tools (эвристика `<20` на старте, M15). Не загружать все схемы в модель по умолчанию при большом каталоге: короткие доменные подсказки → поиск/отложенная загрузка → полный schema только для кандидатов по задаче.
- Не плодить почти одинаковые tools (M23). Каждая возможность увеличивает пространство выбора/описания/вызова. Группировать только реально повторяемые задачи с общими параметрами/правами и понятным workflow.
- Не делать tool на каждый атрибут/экземпляр (`get_project_owner`, `get_deployment_D-204`) (M25). Атрибуты — в родителе; независимые дети — один schema-ограниченный `get_<child>(id)` или resource.

### 5.3. Tools v2 (write, opt-in)

| Tool | Семантика | Контракт |
|---|---|---|
| `todoc.records_create_preview` | Preview/diff, ничего не пишет | `entity_type`, `fields`, `relations` → `WritePlan` (target/template, new content, new hash, diff, validations). Read-only по эффекту |
| `todoc.records_create_apply` | Создаёт новый JSON record | Только за явным consent/флагом (аналог mdkb `--allow-write`), с `expected_hash` + post-validation. No-overwrite. Advisory/LLM suggestion никогда не получает auto-apply |
| `todoc.fix_preview` | Preview/diff для поддержанного правила | `diagnostic_id` → diff + rationale/evidence. Без auto-apply |
| `todoc.fix_apply` | Применяет проверенное исправление | Только за consent, с `expected_hash` + re-parse + re-validate. Concurrent update → конфликт + перечитывание |

Write tools отсутствуют в v1 или за явным флагом/consent. Read-only по умолчанию (M8, M18).

### 5.4. Resources

- Ресурсы — для адресуемого контекста, не для действий (M1). Крупный документ — resource/resource link, который открывают по необходимости, а не каждый раз возвращают целиком в tool-result.
- Схема URI для `todoc` (проектная, зафиксировать на gate): `todoc://<dataset_id>/doc/<document_id>` (документ целиком или проекция), `todoc://<dataset_id>/doc/<document_id>#<anchor>` (раздел), `todoc://<dataset_id>/record/<record_id>`, `todoc://<dataset_id>/type/<entity_type>` (схема/шаблон), `todoc://<dataset_id>/tree` (оглавление). URI — стабильный ID, не путь к файлу.
- `resources/read` кэшируется по M14 (`private` для пользовательских документов). Права на ресурс проверяются заново при каждом чтении (M8).
- Для больших артефактов tool может вернуть ссылку на resource, если клиент поддерживает (M21). Не передавать полный документ через контекст между двумя tools, если его можно безопасно скопировать по ссылке/ID внутри orchestration (research §8.3).

### 5.5. Prompts

- Prompts — повторяемые шаблоны взаимодействия (capture/query/lint), если серверу нужно предложить образец. Не превращать каждую выдачу данных в tool; не помещать операцию записи в prompt.
- Кандидаты: `capture-record` (уточнение обязательных полей/targets → preview/create), `query-aggregate` (поиск → query → aggregate с provenance), `lint-report` (check → группировка → `get_finding` → preview fix). Prompts не дают полномочий на write; write остаётся за tools v2 + consent.

### 5.6. Аннотации

- Аннотации tool — подсказки поведения для клиента (например, `readOnlyHint: true` для v1 tools, `destructiveHint: false`). Они **не являются границей безопасности** (M16). Клиент не считает аннотацию доказательством; сервер всё равно валидирует/авторизует каждый вызов (M8, M26).

## 6. Контракт входа (M5, M6, M24)

### 6.1. Семантика полей

Для каждого аргумента явно решить: обязательность; смысл отсутствия; отличие отсутствующего от `null`; default и где он применяется; форматы/значения/единицы/пределы; принадлежность к пользователю/аккаунту/проекту/ресурсу и откуда берётся контекст; допустимые сочетания.

- `default` в JSON Schema — аннотация, не команда валидатору. Либо сервер явно применяет и документирует default, либо поле обязательно.
- `required` — только для значений, без которых вызов невозможно безопасно выполнить. Default — только если безопасен и сервер явно реализует.
- Для даты/времени — ISO 8601 с часовым поясом (RFC 3339 offset); длительность — с единицами; деньги — с валютой; проценты — с диапазоном и шкалой. Для `todoc`: `limit` bounded (default + max), `status`/`format`/`doc_type` — enum, взаимоисключающие действия — один mode/discriminator вместо нескольких булевых флагов.
- Разделять `query` (критерий поиска), фильтры, стабильный ID цели и параметры операции. Свободный текст может быть поисковым содержимым, но не неограниченным `instructions`. Regex проверяет простую структурную форму, а не смысл намерения.
- Не заставлять модель угадывать объект, tenant/scope, единицы или опасный эффект. Критичное неизвестное/неоднозначное — уточнение или `input_required`, не молчаливый default.
- Для больших строк/массивов — размер/число элементов. Batch — только для повторяющейся предметной операции с ясными лимитами и частичным результатом.
- Не перекладывать на модель данные, уже известные доверенному приложению (выбранный tenant/account, ID из UI), если они могут быть подставлены orchestration-кодом. Идентичность/полномочия/принадлежность ресурса — не на веру из аргументов модели: валидный ID проходит серверную авторизацию (M8).

### 6.2. Закрытие схемы и совместимость

- `additionalProperties: false` — для закрытого контракта и защиты от случайных аргументов (M6). Сопоставить strictness с эволюцией схемы/клиентами. Не считать OpenAI strict subset требованием JSON Schema/MCP.
- MCP 2026-07-28 допускает JSON Schema 2020-12; фактическую поддержку `$ref`, composition и форматов сверять у каждого SDK/host. Ограничивать глубину/размер схем, валидировать их, проверять совместимость на целевых клиентах.
- Неизвестные поля запрещены в закрытой схеме; альтернативные клиенты проверены; старые версии меняются совместимо (additive, breaking — с депрекацией).

### 6.3. Запрет произвольного исполняемого ввода

- Предпочитать параметризированный поиск/операцию сырому SQL, коду, shell-команде, regex без лимитов или произвольному URL (M7). Для `todoc`: `search_logs(service, since, severity, limit)` вместо `run_shell(command)`/`fetch_url(url)`/`execute_sql`.
- Если язык запросов необходим (например, query AST для records) — ограничить грамматику, набор таблиц/полей, объём результата, время и доступ; parameterized queries + read-only, где возможно. Для `todoc` query — allowlisted JSON AST, запрещены Python/SQL/`eval`/import/shell/network (E7).
- Если tool принимает путь — канонизировать и проверять, что остаётся в разрешённой области. Если URL — allowlist схем/доменов/IP-диапазонов + защита от SSRF. Если командная строка — не строить из аргументов shell-строку.

## 7. Контракт выхода (M9–M12, M20, M21, M25)

### 7.1. `structuredContent`, `outputSchema`, `TextContent`

- Для стабильных машинных данных задавать `outputSchema`; сервер MUST возвращать соответствующий результат, клиенту SHOULD валидировать (M9). Использовать `structuredContent` (MCP 2026-07-28 допускает любое JSON-значение). Не путать с модельным structured output.
- Для обратной совместимости SHOULD вернуть сериализованный JSON также в `TextContent` — проверить, не попадает ли дубль дважды в контекст клиента. Не добавлять к дублю многословную прозу. Короткий текстовый summary допустим, если реально нужен клиенту/модели.
- Для non-JSON содержимого — подходящий block type: text, image, audio или resource link. Тип результата, формат транспорта и то, как клиент передаст его модели, — разные уровни: проверять весь путь end-to-end.

### 7.2. Полнота, пустые/частичные результаты, ошибки

- Возвращать ровно данные для ответа/следующего вызова (M10, M25): идентификаторы, релевантные поля, количество, scope, единицы, время/источник, если влияют на смысл. Пустой результат — штатный (валидная пустая коллекция + применённые фильтры). Частичный/обрезанный — явно отметить, объяснить, дать путь к деталям. Не выдавать top-N за полную выдачу.
- **Протокольная ошибка** (JSON-RPC `error`) — проблема запроса/протокола. **Ошибка выполнения tool** — result с `isError: true` (M12). Ошибка формулируется как короткая причина + исправимый следующий шаг (например, «`start_time` должен содержать timezone; передайте RFC 3339»). При известном диапазоне — назвать его. Стабильный код категории/поле/возможность retry; без stack trace/секретов/внутренних адресов/сырого ответа backend. Не подменять ошибку пустым результатом и не прятать в успешной прозе. `resultType` и `isError` — разные роли.
- Успех с предупреждением ≠ ошибка выполнения. Поля статуса соответствуют реальной семантике; не возвращать «успех», если критичный побочный эффект не выполнен.
- Диагностика со статусом `issues_found` — успешный tool result, не `isError` (M20). `isError: true` — только ошибка, мешающая операции.

### 7.3. `next_actions`, дочерние сущности, progressive disclosure

- **`next_actions` — данные-подсказки, не вызов и не стандарт MCP** (M25). Если сервер знает конкретный, допустимый и непосредственно релевантный follow-up, `outputSchema` может включать поле `next_actions` с точным именем уже опубликованного tool, его аргументами и кратким назначением. Возвращать один наиболее полезный вариант, редко — до трёх альтернатив, а не каталог всех операций. Клиент/агент проверяет, что tool существует в текущем каталоге, arguments соответствуют актуальной schema и действие соответствует намерению пользователя. Не выполнять подсказку автоматически; write/destructive шаги не предлагать за рамками запроса и защищать обычной policy/confirmation. Если хорошего follow-up нет — не выдумывать его (пустой список или отсутствие поля по `outputSchema`).
- **Дочерняя сущность vs атрибут** (M25): атрибут — свойство родителя (`status`, `owner`, `last_deployment_at`); вложенная summary-запись — частичная проекция ребёнка; дочерняя сущность — самостоятельно адресуемый объект (собственный стабильный ID, права, жизненный цикл, история, отдельные действия). `next_actions` — только ссылка-подсказка на существующий tool, не дочерняя сущность и не новый вызов. Если у ребёнка нет собственного ID/прав/жизненного цикла — не вводить сущность; вложить только нужную проекцию или оставить атрибутом. Если детей мало и поля влияют на текущее решение — bounded summaries с ID; если много/детали опциональны — count + выборка + `truncated`/cursor, выбранный ID раскрывать отдельным вызовом. Отдельная поверхность MCP — только если нужна: адресуемое read-only содержимое → resource/URI; поиск/вычисление/side effect → tool; поле/summary достаточно → не добавлять endpoint/tool ради структуры.
- **Progressive disclosure** (M21): summary → оглавление → выбранная ветвь. Сначала краткие итоги/счётчики; затем компактное оглавление групп/путей/типы/признаки усечения; дальше — детали только выбранной группы/`finding_id`/поддерева на заданной глубине. Условные параметры (`section`, `path`/`pointer`, `max_depth`, `fields`, `limit`, opaque cursor) — в schema, с лимитами. Для больших артефактов — ссылка на resource. Плоская `path = value` — обзор, не стандарт MCP и не формат patch. Адресация значения JSON — JSON Pointer (RFC 6901); изменения документа — patch по согласованному формату, например JSON Patch (RFC 6902).

### 7.4. Стоимость каждого поля (абляция)

- Каждое поле результата оправдывается downstream need: решение, следующий tool, идентификация, проверка, полнота, provenance (M25). Убрать поле, если оно зеркалит внутреннюю модель, не меняет следующий шаг, дублируется или раскрывает нерелевантную/чувствительную информацию.
- Не минимизировать до «успех»: без ID/значения изменения/scope/unit/source/признака усечения агент повторит операцию или объявит результат полным. Для коллекций — counts + bounded `items` + `truncated` + cursor/page token; полные записи — отдельным detail/resource fetch.
- Проверять ablation на реальных заданиях, отдельно сравнивая `next_actions`, вложенные summaries и полный child-detail; измерять success/incorrect action, лишние вызовы, суммарные input tokens, latency и утечки. Богатые details — opt-in (`include_details`) или отдельный resource.
- Токены — бюджет всего workflow: компактные высокосигнальные поля часто дешевле цепочки повторных вызовов. Сохранять обязательные маркеры (единицы, интервал, scope, источник, статус полноты, поля ключа). Не повторять длинный ввод пользователя/инструкции/схемы/disclaimers в каждом шаге, если достаточно устойчивого ID. Имена полей — с устойчивым смыслом, не `x`/`v` без легенды.

### 7.5. Резюме изменения и диагностика (M19, M20)

- Успешное изменение — кратко действие + стабильный ID/target + итоговое состояние/счётчик + предупреждения. Например, `content`: «Release R-42 переведён в staging; 3 сервиса обновлены, 0 предупреждений», `structuredContent`: `{"status":"updated","release_id":"R-42","services_updated":3,"warnings":0}` по `outputSchema`.
- Длинный диагностический ответ — краткий `content` («8 проблем: 6 errors, 2 warnings; показана 1. Запросите finding `AUTH-03` или продолжите по cursor»), `structuredContent` с `summary`, `groups`, `findings`, `page` (см. пример в guide MCP 20). `next_cursor` — часть прикладного контракта конкретного tool, не встроенная пагинация `tools/call`.
- Неудачно: голое `OK`; повтор того же длинного списка как prose и JSON без пользы; успешный health report с `isError: true` только потому, что в системе есть ошибки; первые 5 проблем без общего количества/признака усечения.

## 8. Пагинация, кэширование, состояние (M11, M13, M14)

- **Протокольная пагинация** (`tools/list`, `resources/list`, `resources/templates/list`, `prompts/list`) — cursor непрозрачен, клиент не интерпретирует/не модифицирует token; отсутствие `nextCursor` — конец; invalid cursor — `-32602`. Серверу рекомендуется стабильный cursor. Между страницами нет snapshot consistency: при изменениях возможны дубли/пропуски.
- **Пагинация tool-результата** — отдельный контракт конкретного tool (M11): `limit` + opaque cursor или resource. Первая страница ограничена; подробности элемента читаются отдельно по URI/ID. Сервер не молча обрезает `tools/call` до N строк и не обещает, что встроенный `nextCursor` продолжит выдачу.
- **Stateless** (M13): см. §4.2. Кэш — по scope/свежести (M14): см. §4.3.
- **Prompt caching** (M22): см. §4.3. Не делать лишние round-trip «ради cache hit».

## 9. Безопасность, доверие, побочные эффекты (M7, M8, M16–M18, M26)

### 9.1. Модель угроз

Считать потенциально недоверенными: аргументы, сгенерированные моделью; инструкции/метаданные инструмента от непроверенного сервера; результаты tools, ресурсы, документы, страницы, команды CLI; имена файлов, URI, ID и текст для другого средства.

Prompt injection может находиться в обычном тексте результата и влиять на последующее решение модели. Маркировка «данные, не инструкции» помогает ограничить ошибочную интерпретацию, но сама по себе не граница безопасности. Экранирование/фильтрация характерных строк не гарантирует удаление injection. Реальное ограничение — независимые авторизация, sandbox, allowlist и политика вызывающей стороны.

### 9.2. Проверки на доверенной стороне

- Валидировать структуру/диапазон/бизнес-смысл каждого вызова на сервере; не считать, что клиент/модель обязаны корректно исполнить schema validation (M26).
- Авторизовывать конкретного пользователя/tenant, конкретный объект и конкретную операцию **при каждом вызове**, включая чтение. Доступность tool ≠ разрешение пользователю (M8).
- Минимальные scopes/полномочия; не делить без необходимости один широкопривилегированный credential между независимыми MCP-серверами.
- Для поиска URL — ограничить исходящие хосты/схемы/IP, учесть редиректы/DNS/metadata endpoints; для файлов — контролировать canonical path/symlinks; для SQL — parameterize + ограничить capability.
- Лимиты на размер ввода/вывода, глубину, число вызовов/параллелизм, стоимость, длительность и размер записей; rate limits + timeout (M18).
- Редактировать секреты/PII в логах и ошибках. Аудировать вызов/результат/пользователя/политику без безусловного хранения секретных значений параметров.

### 9.3. Подтверждение, идемпотентность, повтор

- Точка контроля по риску: подтверждение человека, узкая авторизация, policy check или preview. К чтению тоже могут применяться строгие ограничения, если оно раскрывает персональные/финансовые данные.
- Для опасных/внешних действий показывать **точные** параметры: кому/что отправится, какой объект изменится, какой объём/сумма затронуты. Сводное имя инструмента не заменяет демонстрацию target и аргументов.
- Dry-run/preview, если результат помогает проверить scope до применения. Подтверждение в пользовательском тексте модели — не техническая защита.
- Повтор безопасен по возможности: чтение идемпотентно; для side effect — idempotency key, проверка статуса или явный workflow подтверждения. Таймаут не доказывает, что операция не состоялась: после сетевого сбоя не повторять отправку/платёж/удаление автоматически без безопасной семантики повторения или выяснения статуса.

### 9.4. Транспорт и supply chain

- Удалённый Streamable HTTP — TLS + аутентификация; валидация `Origin` (невалидный — 403). Локальный HTTP — bind localhost (M17).
- Не зеркалить секреты/токены/чувствительный PII из параметров в HTTP-заголовки через `x-mcp-header`: промежуточные узлы могут видеть заголовки.
- Для установленных сторонних MCP-серверов проверять издателя/происхождение, package/dependencies и изменение описаний/schema; возможны supply-chain и rug-pull сценарии. Фиксация хэша определения обнаруживает изменение metadata, но сама по себе не доказывает, что сервер безопасно исполняет код.
- Для stdio stdout — только MCP framing; логи/диагностика — stderr; сам stdio не sandbox-ит процесс. Локальный server — в ограниченном sandbox; токен и права соответствуют конкретному сервису.

### 9.5. Особые моменты CLI и транспорта

- Не вставлять неизвестный текст аргумента прямо в shell-команду. Вызов процесса по argv с отдельными аргументами безопаснее, чем конструирование строки с `eval`/интерпретацией shell. Не сериализовать и не исполнять недоверенный JSON через `eval`.
- Не помещать секреты/PII в `x-mcp-header`. Не передавать токен MCP не тому audience/upstream.

## 10. Традиции хранилища памяти, применимые к MCP

MCP для `todoc` — не система памяти в MVP (аудит §2, §5: план типизирует документы/папки, а не Task/Plan/Idea/Session с жизненным циклом). Ниже — традиции из `docs/guides/markdown-knowledge-for-agents.md` и аудита, которые MCP должен уважать, чтобы не превратить `todoc` в «второй мозг» и чтобы memory-профиль позже вставился без переписывания.

### 10.1. Слои: документация / знания / память / сырьё / журналы / индексы

| Слой | Для кого и зачем | Источник истины | Жизненный цикл |
|---|---|---|---|
| **Документация продукта** | Пользователь/разработчик учится выполнять задачу, проверяет API/поведение | Принятые инструкции, спецификация API, код/тесты | Рецензируемое изменение рядом с кодом; публикация/версия |
| **Знания / wiki** | Человек/агент связывает понятия, компоненты, решения, исходники | Производная карта утверждений со ссылками на свидетельства | Пополнение по ingest; проверка, слияние дублей, пометка устаревшего |
| **Память текущего проекта** | Следующая сессия понимает цель/ограничения/следующий шаг | Текущая проверенная сводка; решения → ADR/issues/коммиты | Короткоживущий документ с датой и сроком пересмотра |
| **Сырьё / архив источников** | Проверить, что именно сказал документ/issue/стенограмма/файл/сайт | Оригинал или зафиксированный снимок | По возможности неизменяем; исправление — новая версия/снимок |
| **Журнал сессий / событий** | Восстановить историю и найти забытое | Хронологическая запись с происхождением | Append-only или политика retention; не загружать целиком в каждую сессию |
| **Индексы поиска и графы** | Быстро найти страницы и свидетельства | Данные, вычисленные из файлов и конфигурации | Пересоздаваемы; версионировать конфигурацию, не считать первоисточником |

**Правило для MCP (MUST):** MCP tools/resources не смешивают слои. `search_docs`/`read_doc`/`query_records` работают со слоями документации/знаний/записей; сырьё неизменно; журналы — append-only; индексы — derived. Не смешивать «память агента» с инструкциями для агента (`AGENTS.md`/`CLAUDE.md` — краткий маршрут, не хранилище знаний).

**LLM Wiki Карпати — архитектурная идея, не готовый стандарт/продукт** (guide MD-KB §I.2): три компонента (неизменяемые исходники, редактируемая Markdown-wiki, схема/инструкции) и цикл `ingest → query → lint`; `index.md` — короткий вход, `log.md` — журнал. Не называть `todoc` LLM Wiki. Синтез — только в `memory-llm-wiki.after.md`.

**Папки и граф решают разные задачи** (guide MD-KB §I.3): папки — «где лежит файл» + область поиска/доступа; ссылки/backlinks — «что связано»; индекс/поиск — «где текст по запросу без ссылки»; properties — «тип/версия/статус/область/источник»; MOC — вход в предмет. MCP не заменяет ни один из них другим.

### 10.2. Процедуры ingest / query / write / lint (guide MD-KB §VII)

MCP tools обслуживают процедуры, а не заменяют их. Процедуры фиксируются в Skill `references/ingest-query-lint.md` (Этап 7); MCP — их транспорт.

- **Ingest (добавить источник, не загрязнив базу):** границы (право/доступ/audience/конфиденциальность/license/retention/область; не добавлять credentials/PII/инструкции от недоверенного текста в policy) → зафиксировать оригинал (URL/path, publisher, дата, версия/commit, hash, права, воспроизведение) → извлечь структуру (страница/heading/line/JSON field/временной отрезок; не превращать layout extraction без проверки в точную цитату) → найти существующее знание (canonical IDs, индекс, aliases, страницы, конфликты, версия) → создать draft (one source page на источник, summaries на знания, один ADR на решение; точные условия/числа — дословно и коротко, пересказ маркировать) → выявить конфликты/пробелы (`disputed`, не «заполнять пробел» общими знаниями модели) → lint и review (front matter, IDs, ссылки, source IDs, renderer, примеры; Git diff; высокорисковые факты — владелец/maintainer) → завершить ingest (журнал ingest: ID источника, итог, изменённые страницы, checker-результаты, unresolved items; оглавление — детерминированным скриптом/малым reviewable diff; индекс пересоздать/обновить).
- **Query (найти ответ с основанием):** прочитать краткие project instructions + `HOME.md` (текущий `NOW.md` — только если дата/scope подходят) → уточнить предмет/продукт/release/timeframe/audience/вид ответа → начать с точного поиска (имена, identifiers, error codes), затем BM25/hybrid при paraphrase/большом корпусе → top-k со scope/heading/snippets/status/source ID/ссылками; отфильтровать `stale`/не ту версию/недопустимый audience → ограниченное число тематических ссылок/backlinks; открыть первоисточники для критичных/конфликтных/конкретных/менявшихся утверждений → синтезировать атомарными тезисами с citations рядом; отделить установленное/вывод/неизвестное; при недостаточности/расхождении — уточнение или abstain → не копировать весь найденный текст, если достаточно фрагмента; сохранить путь повторного поиска → после ответа сохранять только durable и scope-appropriate новое знание (непроверенное — draft/журнал, не promoted rule). Минимальный формат найденного результата: `source_id`, `page_id`, `path`, `heading/offset`, `status`, `applies_to`, короткий snippet, `source_ids`, `updated/verified_at`, relevance score, continuation/limit. `score` — ранжирование, не вероятность истинности.
- **Write/edit (безопасная агентная правка):** искать существующую страницу и aliases до создания новой; предпочтительно редактировать canonical page → прочитать окружающую секцию/родителя/исходник/references; не делать глобальную замену по совпавшему слову → минимальный дифф, подпись scope/источника, сохранить соседние факты, не форматировать полкорпуса → не менять raw source; удалять/переписывать цитаты/решения/audit log без оснований — нет → для конкурирующих правок — разные файлы/секции + review; не давать нескольким агентам перезаписывать один общий файл целиком (append/patch/transaction/lock) → устаревшее утверждение — пометить + evidence/issue, не заменить на правдоподобное новое → показать diff, changed pages, checks, source coverage, неразрешённые вопросы → не записывать скрытые prompt instructions/приватные характеристики/secrets в долговременную память. Экспериментальный сигнал Anthropic: при совместной работе на общей странице сохранилось 41/57 фактов; при странице на документ + точное цитирование — 57/57 (case study, не универсальный закон; основание ограничивать конкурентную перезапись и сохранять точные свидетельства).
- **Lint/review (надёжность, не «красота графа»):** валидировать ссылки/схему; отчёты по `stale`, missing source, конфликтам, orphan pages, duplicate candidates → кандидатов на semantic merge/rename/retire — человеку/review workflow (модель может предложить reconciliation diff, не удалять canonical note молча) → проверить достижимость от index/MOC или поиском; не требовать backlink к каждой записи-свидетельству → тестировать examples/commands/API schemas/ссылки на release; не выполнять произвольные блоки Markdown как код в CI без sandbox/allowlist → изменение внешнего URL/deprecated API/release trigger должно находить связанный материал.
- **Конкурентность и транзакции:** по одному владельцу/воркеру на page/source при параллельном ingest; агрегация в отдельном merge pass → Git branch/patch/PR; проверка base commit/конфликта; не заменять файл текстом, прочитанным до параллельных изменений → журналы append-only с уникальным `run_id`; большие тематические страницы — контролируемый блок/patch → многопользовательская система — lock/transaction/version check или временные files + атомарный merge → после merge — повтор validators + сравнение IDs/содержимого с версией до операции.

**Coverage matrix аудита (§5) — что MCP не закрывает в MVP:** отдельные Task/Plan/Idea/Decision/Person/Project со статусами/сроками/исполнителями/приоритетами/повторяемостью; декларативные типы отношений (`belongs_to`, `blocks`, `derived_from`, `supports`, `contradicts`, `promoted_to`) с валидацией; capture/triage/dedupe очередь; immutable raw → compiled wiki слой; source ledger + claim ledger (статусы принятия/оспаривания, независимость источников, valid-time vs recorded-time, freshness/review_due, не разрешать конфликт автоматически); session/domain home + bootstrap + кристаллизация сессии; task-oriented запросы («что просрочено», «какой следующий шаг», «почему выбрали решение»); семантическая проверка contradictory/stale claims; tag registry/ontology/aliases/duplicate-resolution; многофайловая transaction bundle; sensitivity/retention/scopes. Всё это — `memory-llm-wiki.after.md`, не MCP v1.

### 10.3. Происхождение, конфликты, свежесть (guide MD-KB §V)

- Отделять утверждение от подтверждающего: `утверждение → scope/версия/время → свидетельство → оригинал/снимок`. Ключевые фразы — с источником в абзаце, не только в конце страницы. Разделять цитату/пересказ/наблюдение/вывод/гипотезу. Не превращать правдоподобное агентное объяснение в «документ говорит…».
- Полезная запись свидетельства: stable source ID; автор/издатель; тип источника; URL/путь; release/commit; дата обращения + timezone; страница/heading/строка/JSON path; hash снимка; license/access scope; точная короткая цитата/тестируемое наблюдение; страницы, выведенные из источника. Для кода — commit + путь к строке/тесту (URL на `main` сегодня не фиксирует версию). Для веба — URL + дата не гарантируют тот же текст завтра.
- Иерархия доказательств зависит от вопроса: код/тесты — фактическое поведение текущего бинарника; спецификация/публичная документация — ожидаемый контракт; ADR — причина решения; issue/PR/meeting note — ход обсуждения/авторство (план мог не попасть в release). Для старого клиента документация `latest` слабее зафиксированной версии его release.
- Процедура при конфликте: сохранить обе формулировки + scopes/версии → проверить, не говорят ли источники о разных релизах/tenants/условиях/интерфейсах/датах → определить приоритет для данного claim type → при реальной разнице — `disputed`/раздел «Расхождение», не искусственное общее правило → запросить владельца/maintainer или проверить код/тест, если безопасно → после решения оставить источник/обоснование/дату/link на superseded claim; очередь закрыть после validation. Неудачно: «модель выбрала X, потому что звучит новее». Удачно: «в `release-4.1` действует X (ссылка A); с `release-4.2` контракт заменён на Y по ADR и тесту Z; применимость старых клиентов ограничена страницей W».
- Обнаружение устаревания: `updated` — время редактирования файла, не момент проверки источника. Добавлять `verified_at`/`review_after`, если используются workflow; события подозрительности (изменился API schema/код/owner/runbook/release/ADR; источник удалён/перемещён/заменён; вопрос/ошибка показали неполноту; rapidly changing area; давно не было доступа, но страница инъектируется в каждый сеанс; источник стал доступен/недоступен другой аудитории или истёк license/retention). Cadence по риску/частоте изменения, не одинаковый срок на все страницы. `review_after` — напоминание, не автоматическая истина. Просроченную страницу — сначала пометить `stale` или исключить из `current`, не исправлять догадкой.
- Поиск дубликатов/идентичность: сначала title/aliases/ID/ссылки, потом создавать новую страницу → на CI — точные дубликаты по нормализованному hash, одинаковые IDs, похожие имена; semantic similarity — для кандидатов, не для автоматического удаления/слияния → при одной сущности — canonical ID, перенос уникальных сведений со ссылками, алиасы/redirect, обновление incoming links → при совпадении слова, но разных контекстах/версиях/компонентах — отдельные entity pages с qualifier → не удалять повторно сформулированную выдержку, если она нужна как точное юридическое/API-свидетельство.

### 10.4. Ссылки, граф, навигация (guide MD-KB §VI)

- Переносимость прежде удобного синтаксиса: переносимый файл — обычные Markdown-ссылки (`[OAuth callback flow](../systems/oauth-callback.md)`); Obsidian-only — wikilinks/embeds. Обычные ссылки читаются шире. Не хранить две конкурирующие копии каждой страницы. Ссылки на заголовки ломаются при rename; для устойчивой архитектуры — стабильный ID страницы + ссылка на страницу + явный заголовок/label, поддерживаемый renderer; проверять anchor в итоговой сборке.
- Ставить на ребро смысл, а не только наличие `[[link]]`: `implements`, `depends_on`, `supports`/`evidence_for`, `contradicts`, `supersedes`, `owned_by`, `used_by`, `part_of`, `caused_by` — если нужны в домене и имеют чёткую семантику. Человекочитаемая формулировка «identity-api реализует ADR-0042» полезнее нейтрального `related: [...]`. Для машинных запросов — relation list в front matter/JSON sidecar + валидация schema; не дублировать с текстом без генерации/проверки согласованности. Небольшой контролируемый словарь типов; новые связи — через review.
- Навигация по крупной базе: главный вход (`HOME.md`) — назначение, авторитетные источники, как искать, где актуальная память, куда не ходить, как предложить изменение (короткий); индекс домена/MOC — главные узлы и несколько маршрутов, не полный каталог; страница сущности — canonical ID, aliases, owner, ответственность, inbound/outbound relations, contracts, source links; backlinks — обнаружение влияния/навигация, периодическая проверка orphan pages/ссылок на переименованные файлы; полнотекстовый поиск — непредусмотренные связи/синонимы/error code/новые формулировки; ограниченный graph traversal — 1–2 смысловых перехода после retrieval, затем первоисточники (не «весь связный компонент» в prompt); поиск по свойствам — статус/продукт/version/audience/owner/time validity/source type.
- JSON Canvas — вспомогательная диаграмма, не система истин: `.canvas` по JSON Canvas 1.0 (`nodes`/`edges`) — карта компонентов/обсуждение/планирование. Факт/отношение/provenance — также на странице/в структуре данных.
- Простые проверки графа (ежедневно/CI): уникальность `id`, разрешённость локальных links/wikilinks/anchors в целевом renderer; source IDs существуют и доступны audience; accepted/current page не ссылается только на отсутствующие/архивные источники без пометки; orphan pages/чрезмерно центральные узлы — отчёт для review, не автоматическая ошибка; links на `stale`/`superseded` — с пояснением/redirect; relation endpoints/enum values существуют; дубликаты alias/одинаковые titles разрешены. Сборка ссылок — AST parser соответствующего renderer (regex может принять ссылку внутри fenced code за настоящую).

### 10.5. Ступени поиска и бюджет контекста (guide MD-KB §VIII)

| Сценарий | Начальная стратегия | Дополнительный шаг |
|---|---|---|
| Имя функции, ID, error code, точная цитата | `git grep` / `rg -n` / editor search | Поиск по Git history, exact phrase, source ID |
| Вопрос с терминами документа | BM25/FTS по страницам/чанкам | Расширить lexical variants, parent page, source collection |
| Переформулировка/синонимы, большой корпус | Vector + BM25 hybrid | Reranker по shortlist, query decomposition |
| Ответ требует нескольких документов | Wiki/MOC для карты + search по оригиналам + ограниченный graph expansion | Таблица claim → source, проверка конфликтов/scope |
| «Найти всё», миграция, влияние изменения | Фильтр по metadata/relations + outgoing/incoming links + source code search | Сканировать полный inventory, не считать top-k исчерпывающим |

- Baseline: перед embedding search измерить точный/лексический retrieval. BEIR: BM25 — сильная робастная база; reranking/late-interaction в среднем могут выигрывать при большей стоимости. Нельзя заключить, что конкретная vector DB/embedding-модель лучше для корпуса, из одного общего рейтинга.
- Гибридная схема: отдельные collections/filters для raw/wiki/docs/журналов (или единый индекс с типом/статусом/версией в метаданных) → heading path + provenance в каждом chunk → точные/лексические кандидаты + параллельно semantic для широкого natural-language query → объединить ранги (RRF) + опционально rerank top-N → после получения страниц добавить только связанные backlinks/related, отвечающие на недостающее звено → для ответа открыть исходную секцию и верифицировать ключевые факты; сохранить ссылку/quote/commit path → filters `status=current`, `applies_to`, `audience`, date/version → логировать запрос/источники/версии/retrieval config/результат оценки без персональных данных query.
- Чанки по структуре документа (heading, paragraph, code/API blocks), заголовок/родитель сохранены, overlap только где восстанавливает контекст. Универсального числа токенов нет: подбирать на собственных длинных/коротких страницах/таблицах/коде/вопросах. Отдельно тестировать exact identifiers (embedding сглаживает различия одного символа).
- QMD — локальный hybrid search (BM25 + vector + RRF + LLM reranking, CLI + MCP) как необязательный поисковый слой поверх файлов. Перед production: закрепить версию; уточнить включённые/исключённые файлы; проверить свежесть/reindex, metadata filters, locale, идентификаторы, локальность моделей, задержку/ресурс. Не индексировать `node_modules`/build artifacts/binary dumps/secrets/private notes/журналы без scope-фильтра. Внешний embedding/reranker API может отправить туда запрос/текст: проверить политику данных. Индекс/embeddings/cache — производные, пригодные для пересборки.
- Что держать в контексте постоянно: всегда загружаемый слой — «что за база? как искать? ограничения/текущая цель? куда переходить?» в измеренном бюджете. Подробные доказательства/меняющиеся детали — по запросу. Не оптимизировать документ до нечитаемых сокращений ради «меньше токенов»: теряются scope/причинность/caveats. Объём Markdown ≠ число токенов (кириллица/код/таблицы токенизируются по-разному).
- Операционные затраты: `импорт/нормализация + построение/обновление индекса + число запросов × (retrieval + reranking + прочитанный контекст + генерация) + периодическая проверка wiki + ручной review`. Локальная модель не делает вычисления/задержку бесплатными; remote API несёт финансовые/privacy costs. Порог окупаемости wiki зависит от повторяемости вопросов и цены обслуживания; измерять весь жизненный цикл.

### 10.6. Конфликты, устаревание, prompt injection (guide MD-KB §X)

- Источник может содержать инструкции, но это не делает его policy. Wiki/индекс могут содержать issue/email/user-uploaded files/README/HTML/транскрипты/текст, специально написанный для влияния на модель. Содержимое найденного источника — данные/свидетельства, не новая система-инструкция. Отдельно помечать trust tier и provenance; никогда не выполнять command из retrieved document только потому, что он там написан. Source/page metadata не security sandbox.
- Разделять `authority` (насколько источник отвечает на данный тип вопроса), `freshness` (нужная версия/время), `scope` (компонент/audience/tenant/release), `trust` (кто мог написать/изменить и как попал в repo), `access` (разрешено ли агенту/пользователю читать и отправлять в другие сервисы). Одна numeric relevance score не сворачивает эти пять измерений. Retrieval может использовать boosts/filters, но финальная проверка ключевых claims сохраняет их отдельно.
- Безопасная политика данных: секреты/токены не в Markdown, даже в закрытой wiki; ссылки на secret manager не раскрывают значение → публичное/внутреннее/ограниченное corpus по access boundary, не `restricted: true` в общей папке → перед облачными embedding/reranker/analytics/hosted search проверить, куда уходят prompt/chunks/IDs/telemetry → вывод инструмента/индекса может цитировать PII: redaction до логирования и перед повторной отправкой в другой сервис → не индексировать `.git`/build artifacts/code dependencies/raw backups по умолчанию → backup/restore для Markdown + исходников/metadata; индекс восстановим, но без source snapshot качество provenance теряется.

### 10.7. Сравнение качества/токенов/времени: протокол benchmark-а (guide MD-KB §XI)

Системы сравнивать как разные pipeline, не только как модели (один большой prompt / search-only / wiki-only / wiki+search / graph-only / hybrid+reranker). Разумная исходная гипотеза: на большой базе сравнивать несколько pipeline над **тем же corpus snapshot, вопросами, моделью, prompt и бюджетом**; UI и retrieval — разные переменные.

- Опубликованные исследования — протокол, результат и пределы вывода (Anthropic wiki over internal corpus; shared wiki edit 41/57 vs 57/57; DoGBench; LongMemEval; LoCoMo; MemoryAgentBench; BEIR; MTEB; FreshStack; Ragas). Цифры привязаны к конфигурациям/наборам; не переносить как универсальную точность/окупаемость/latency. Не опубликовано как универсальный факт: latency/стоимость полного жизненного цикла Obsidian vs QMD vs search-only; «лучший» размер файла/чанка/число ссылок; общая токенная экономия от Markdown; гарантированная точность wiki после N sessions. Указывать «не измерено», если работа этого не сообщает.
- Собственный held-out набор до настройки индекса: старт 40–100 задач как эвристический размер, затем увеличивать по покрытию/риску. Не настраивать по закрытой test части. Для каждой задачи: `snapshot_commit`/дата корпуса, prompt, вопрос, допустимые tools, необходимый release/scope, expected answer atoms, authoritative evidence sections, allowed abstention, edit/no-op rubric, сложность.
- Классы задач: exact lookup; single-document synthesis; cross-document/multi-hop; temporal/versioned; conflict/uncertainty/abstain; change-impact; editing integrity; privacy/scope.
- Метрики: retrieval (Recall@k/Success@k, MRR/nDCG@k, coverage nuggets, diversity); answer (precision/completeness по атомарным требованиям, scope/version, citation precision/recall, unsupported claim rate); safety/temporal (correct abstention, stale-source use, contradiction resolution, неавторизованный retrieval, prompt injection success); editing (patch acceptance по rubric, полнота/accuracy/reader guidance/placement, сохранность нецелевых фактов, broken links/schema/build, число ненужных edits, правильная no-op); операции (input/output tokens с одинаковым tokenizer и учётом tool/context, число вызовов, cold/warm p50/p95 latency, индексация/refresh time, storage/CPU/GPU/API cost, ручное время review/поддержки wiki).
- Честное сравнение: зафиксировать корпус commit/hash, модель/revision, system prompt, max output, hardware, search library/version, parser/dialect, chunk strategy, `top-k`, filter, embedding model, reranker, температурные/seed → одинаковые права доступа и knowledge base; не давать скрытые загруженные данные или более высокий budget → ablations: (A) full-context на малом корпусе, (B) raw BM25/FTS, (C) raw vector, (D) hybrid, (E) wiki-only, (F) wiki+search; затем graph expansion/reranker по одному → разделять retrieval/answer/edit quality → один вопрос может иметь несколько корректных ответов/траекторий; rubric оценивает обязательные факты/допустимые варианты, не буквальное сходство → независимый reviewer blind samples; LLM-judge — дешёвый triage после проверки согласия с людьми → публиковать N, split, scope, model/harness, exact metrics, confidence intervals/variability, prompt/config/version, ограничения.
- Практический критерий внедрения wiki: curated layer — когда на held-out cross-document/update задачах надёжно повышает coverage/citation quality или снижает query cost без неприемлемого stale/conflict/edit risk; учитывать стоимость ingest/review/обновления. Если raw search уже отвечает на большинство вопросов из одного источника, дополнительная wiki лишь добавит затраты и слой рассинхронизации.

## 11. Архитектурные хуки в MVP (уже заложены)

| Хук | Что уже есть в MVP | Как переиспользуется |
|---|---|---|
| **E8 `WorkflowLookup`** | Whitelisted `workflow_id` → trusted Skill | MCP tools вызывают те же use cases; нет обхода валидации/прав |
| **E10 `OutputSerializer`** | JSON envelope (`data`/`diagnostics`/`next_actions`) | MCP возвращает `structuredContent` + `TextContent` (не буквальная копия CLI-вывода); `next_actions` (argv-массив) → `next_actions` (tool hints, M25) |
| **E4/E5 retrieval/renderer** | Lexical + bounded projection | MCP `search_docs`/`read_doc` — те же bounded projections с `truncated`/cursor/provenance (M10, M21) |
| **E9 write safety** | `WritePlan` + `expected_hash` + preview/apply | MCP write tools — только preview по умолчанию; apply — за явным consent/флагом (аналог `--allow-write`) |
| **Config** | `dataset.json` + `--root` | MCP server принимает `--root` (повторяемый) + `TODOC_ROOT`; CWD не выбирает config |
| **E6 generations** | Atomic JSON generations (`CURRENT.json`) | MCP читает только `CURRENT` generation; incomplete не выдаётся как полный |
| **E7 query engine** | Allowlisted JSON AST, без Python/SQL/`eval` | MCP `query_records`/`aggregate_records` — те же AST + units/formula/provenance |

**Инвариант:** MCP и CLI согласованы по статусам/безопасности, но не копируют формат вывода буквально. MCP — структурированный RPC; CLI — терминальный + composable-поверхность ОС (research §2.3).

## 12. Пошаговый план внедрения (когда gate пройден)

### Шаг 1 — MCP gate (до кода)

1. Зафиксировать редакцию MCP (2026-07-28), транспорт (stdio в v1; HTTP — только при доказанной боли), целевые клиенты/SDK, версии JSON Schema dialect.
2. Зафиксировать набор tools/resources/prompts (§5) — не каждый endpoint API отдельный tool; инструменты имеют различимые цели и помогают выбрать верное действие (M2, M23). Зафиксировать `<20` tools на старте как эвристику (M15).
3. Зафиксировать stateless-модель (M13): состояние между вызовами — явным идентификатором; права проверяются заново на каждый вызов. Совместимость со старыми редакциями — явный выбор + тесты.
4. Зафиксировать input/output schemas (§6–§7), URI-схему resources (§5.4), кэш-политику (§4.3), лимиты/таймауты/аудит (§9).
5. Зафиксировать eval-набор (§14) и baseline (CLI + `rg` + QMD/Open Knowledge) до кода.

### Шаг 2 — Read-only MCP (v1)

1. Реализовать MCP-сервер (отдельный пакет/подпакет, например `src/todoc/mcp/` или отдельный `todoc-mcp/`): tools из §5.2 + resources из §5.4. `server/discover` MUST реализован; `resultType` в каждом RPC.
2. Вход — явный, типизированный, ограниченный контракт (M5, M24). Валидация схемой не заменяет проверку бизнес-правил и прав (M8, M26).
3. Выход — отвечает на вопрос «что агенту нужно знать или сделать дальше?» (M10, M25): краткая сводка + достаточные идентификаторы; большие наборы — фильтровать/агрегировать/раскрывать по требованию (M21). Компактность — высокая полезность на токен, а не минимальное число символов (не удалять единицы/область/полноту/источник/неопределённость).
4. Read-only по умолчанию. Write tools отсутствуют или за явным флагом/consent.
5. Тесты: MCP contract tests (те же fixtures, что и CLI); stateless (нет сессионного состояния); права проверяются заново; результат инструмента — недоверенные данные (prompt injection не исполняется); `outputSchema` соблюдена; `isError` vs протокольная ошибка vs `issues_found` различимы; cursor непрозрачен; кэш `private` не пересекает auth-контекст.

### Шаг 3 — Write MCP (opt-in)

1. Реализовать `records_create_preview` (preview/diff, ничего не пишет) + `records_create_apply` (за явным consent/флагом, с `expected_hash` + post-validation). Аналог mdkb `--allow-write`.
2. Реализовать `fix_preview` (preview/diff) без auto-apply. Advisory/LLM suggestion никогда не получает auto-apply.
3. Тесты: concurrent update → конфликт; невалидная запись → оригинал нетронут; no-overwrite; повтор после timeout — проверка статуса/идемпотентности, не вслепую.

### Шаг 4 — Prompts (опционально)

1. Реализовать MCP prompts для повторяемых сценариев (capture/query/lint, §5.5), если серверу нужно предложить образец взаимодействия.
2. Не превращать каждую выдачу данных в tool. Resources — для контекста, tools — для действий (M1).

### Шаг 5 — Совместимость и eval

1. Тестировать на целевых клиентах (Claude Desktop/Code, Cursor, VS Code и др.) + целевых моделях (включая слабые) + целевых SDK/версиях протокола (M26, guide MCP III).
2. Измерять: успех задач, выбор инструмента, ошибки аргументов, восстановление, токены, вызовы, задержку, небезопасные действия (не только валидность JSON) (§14).
3. Зафиксировать `server/discover`, `resultType` (`complete`/`input_required`), `_meta` (версия протокола, возможности клиента) по редакции 2026-07-28. Обрабатывать `UnsupportedProtocolVersionError`; legacy-ответ без `resultType` — только для совместимого старого протокола.

## 13. Данные и миграции

- **Schema:** MCP не вводит новых схем данных. Читает те же `dataset.json` + generations + types. Изменения MCP — только в адаптере, не в DATA_ROOT.
- **Миграция:** не требуется. MCP — новый транспорт; старые DATA_ROOT работают без MCP.
- **Backup:** MCP не хранит копию истины. Удаление MCP не теряет данные (P1). Индекс/embeddings/cache — производные, пригодные для пересборки (guide MD-KB §VIII.3).

## 14. Безопасность / приватность / производительность

- **Безопасность:** авторизация, подтверждение рискованных действий и лимиты — вне модели (описание инструмента и аннотации MCP не дают полномочий, M16). Не выполнять shell с user content; не передавать query напрямую в SQL/`eval`/regex без лимитов (M7). Результат инструмента — недоверенные данные (защита от prompt injection — политика агента, а не regex-validator). Валидация/авторизация на доверенной стороне при каждом вызове (M8, M26).
- **Приватность:** local-first; без скрытых сетевых вызовов. Cloud MCP (remote HTTP per project, как в Basic Memory) — только с явным consent. Перед облачными embedding/reranker/analytics/hosted search проверить, куда уходят prompt/chunks/IDs/telemetry (guide MD-KB §X.3).
- **Производительность:** bounded projections + pagination как в CLI (M11, M21); stateless (нет долгоживущего процесса в v1, кроме stdio server). Rate/concurrency/size/time/cost budgets; audit с редактированием секретов/PII (M18).

## 15. Benchmark / gate критерии и pre-release чек-лист

### 15.1. Gate критерии

- CLI стабилен; use cases для MCP зафиксированы и покрыты contract tests.
- MCP tools имеют различимые цели; агент выбирает верное действие без уточняющих вопросов о формате/назначении.
- Stateless + права заново — проверены тестами.
- Eval на целевых клиентах/моделях: успех задач, токены/вызовы/latency, небезопасные действия — в пределах заявленных лимитов.
- Read-only default + write за consent — проверены.
- `outputSchema` соблюдена; `structuredContent` + `TextContent` не дублируют payload в контекст клиента дважды (проверено на целевых клиентах).
- Кэш `private` не пересекает auth-контекст; `public` — только для неперсонального результата.

### 15.2. Eval: что измерять (guide MCP III, research §11)

- Held-out набор реалистичных, многошаговых задач с проверяемым outcome и допустимыми альтернативными траекториями; не оценивать только совпадение JSON/формулировки. Тестировать самую слабую модель и самый тесный контекстный бюджет, которые продукт поддерживает.
- Измерять: task success; правильность выбора и аргументов; ошибки/повторы/лишние вызовы; recovery; tokens/calls/latency p50-p95; частичные ответы; policy bypass, неавторизованные чтения/записи и утечки.
- Тестировать реальные клиенты/SDK и версии протокола, поддержку JSON Schema, `resultType`/MRTR, empty/large/partial results, cursor, приватный кэш, expired handle, prompt injection, timeout, повтор side effect и конкурентные вызовы.
- Для диагностических/древовидных tools проверить 0, 1, около выбранного порога и много findings; корректность `isError` vs `issues_found`, согласованность счётчиков/групп, truncation, opaque cursor, получение деталей, auth и отсутствие side effect. Сравнить краткое резюме с раскрытием выбранной ветви и вариантами с/без `next_actions` по task success, calls, latency, суммарным tokens и наблюдаемому prompt-cache hit/miss; фиксированный выигрыш не предполагать.
- Публикуемые числа экономии токенов — ориентиры только для описанных авторами экспериментов (Anthropic: tool-search reduction до 85% в своей конфигурации; code execution 150k → 2k tokens). Не переносить без собственного A/B/evaluation.
- Метрики research §11.3: результат (доля корректно завершённых задач, корректность объекта/получателя/суммы, качество ответа); использование инструментов (верность выбора, доля валидных аргументов, неудачные вызовы, повторы, ненужные шаги); контекст/стоимость (входные/выходные токены на успешную задачу, токены описаний tools, объём промежуточных результатов); скорость (время до результата, p50/p95 вызова и всей задачи, число model/tool round-trips); надёжность (таймауты, ошибки downstream, доля восстановления, доля частичных результатов, повторяемость); безопасность (неавторизованные эффекты/чтения, обход подтверждения, утечка секретов/PII, небезопасная передача данных между серверами).

### 15.3. Минимальный pre-release чек-лист (guide MCP III + research §13)

- [ ] Каждый tool/resource закрывает реальный agent workflow; выбор MCP vs CLI/agent reasoning обоснован местом данных, host-возможностями, правами и риском.
- [ ] Tool не угадывает семантику свободного текста regex-правилами; объёмная повторяемая работа выполняется детерминированно с фильтрами/лимитами.
- [ ] Каждое поле результата помогает решению, идентификации, проверке, provenance или recovery; полезность проверена на workflow, а не только по компактности.
- [ ] `next_actions` — bounded hints на существующие tools, проверяемые по актуальной schema; клиент не исполняет их автоматически.
- [ ] Проверена самая слабая поддерживаемая модель при целевом малом контекстном бюджете; надёжность подтверждена eval и server-side controls, а не предположением о модели.
- [ ] Дочерние сущности отделены от атрибутов по независимому ID/жизненному циклу; большие наборы детей раскрываются выборочно, не целиком.
- [ ] Цель, область, побочный эффект и альтернативы ясны из имени/описания.
- [ ] Input/output schema валидны и совместимы с заявленными клиентами.
- [ ] Server-side validation, auth, tenant/object access, quotas и timeouts обязательны.
- [ ] Empty/partial/error/complete/input-required различаются и восстанавливаемы.
- [ ] Большой вывод ограничен; cursor/URI/handle имеют явную семантику.
- [ ] Кэш и порядок каталогов безопасны; private data не пересекает auth-контекст.
- [ ] Рискованные действия имеют внешний policy/confirm; annotations не считаются защитой.
- [ ] Tool descriptions, результат, URLs, paths, SQL и credentials входят в threat model.
- [ ] Пройдены evaluation и compatibility-тесты на целевых клиентах/версиях.

### 15.4. Анти-паттерны (research §12 + guide MCP)

- Отображать все endpoint внешнего API как инструменты, даже когда большая часть не соответствует пользовательским задачам.
- Несколько инструментов с почти одинаковым назначением без объяснения, какой выбирать.
- Параметр `date` без формата/календаря/часового пояса/границ включения.
- `string` без описания допустимой формы, когда значение ограничимо enum/паттерном/типом.
- Считать, что схема валидирует права доступа или бизнес-условия.
- Возвращать все строки/поля «на всякий случай», затем надеяться на длинное контекстное окно.
- Обрезать список молча или возвращать «топ-N» без признака ограничения и пути получить остальные записи.
- Возвращать успешный статус при выполнении только части операции либо пустой результат при сбое.
- Передавать полный документ через контекст между двумя tools, если его можно безопасно скопировать по ссылке/ID внутри orchestration.
- Не отличать protocol error от ошибки выполнения MCP-инструмента.
- Включать в tool result лог/traceback/внутренний URL, который не помогает модели исправить ввод.
- Принимать `readOnlyHint`/`destructiveHint`/описание от сервера за доказательство безопасного поведения.
- Считать громкие проценты экономии токенов из статьи гарантией для иной системы.
- Делать машинный режим неотличимым от меняющейся human-таблицы.
- Автоматически повторять после таймаута необратимое действие, не проверив статус/идемпотентность.
- Принимать пользовательский запрос на shell/SQL/URL без границ, allowlist, sandbox и лимитов.

## 16. Что НЕ делать

- НЕ делать MCP вторым API с собственной семантикой (P11). Один смысл — много транспортов.
- НЕ копировать CLI-вывод буквально в MCP (разные транспортные контракты).
- НЕ полагаться на скрытую сессионность (stateless 2026-07-28).
- НЕ превращать каждую выдачу данных в tool (resources — для контекста).
- НЕ считать описание инструмента/аннотации контролем безопасности.
- НЕ делать write tools default без consent (аналог `--allow-write`).
- НЕ называть `status`/`doctor` стандартом MCP (M19).
- НЕ делать `next_actions` auto-execution или каталогом всех tools.
- НЕ проектировать вывод в расчёте на prompt cache-хит.
- НЕ превращать `todoc` в memory-систему через MCP: Task/Plan/Idea lifecycle, claim ledger, session bootstrap — только в `memory-llm-wiki.after.md` (аудит §2, §5).

## 17. Связи

- Зависит от: Этап 5–7 MVP (use cases, bounded read, write safety, JSON envelope).
- Блокирует: ничего в MVP. Веб (`web-ui.after.md`) — параллельный adapter поверх того же слоя.
- Связано с: `search-embeddings-vector.after.md` (MCP может отдавать hybrid поиск), `memory-llm-wiki.after.md` (MCP tools для memory-профиля), `implementation-plan.md` §16 (традиции MCP и хранилища памяти).
