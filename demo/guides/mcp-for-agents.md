---
id: doc:guide-mcp
title: "Guide: MCP для агентов (постулаты и чек-лист)"
doc_type: guide
lang: ru
source: docs/guides/mcp-for-agents.md
copied: true
---

# MCP для агентной работы: постулаты руководства

## Цель, задачи и принципы

**Цель.** Задать практические критерии, когда агенту нужен MCP и как спроектировать MCP-сервер, чтобы модель находила подходящие возможности, передавала точные аргументы и получала ровно тот результат, который нужен для следующего безопасного шага. Контракт должен снижать зависимость от силы модели: небольшой ясный каталог, однозначные схемы и ограниченные результаты помогают даже модели с ограниченным контекстом и слабым планированием. Это снижает вероятность ошибок, но не гарантирует их отсутствие; поведение нужно проверять на целевых, в том числе самых слабых поддерживаемых, моделях.

**Для кого.** Для разработчиков MCP-серверов и tools/resources/prompts, авторов agent hosts/клиентов и тех, кто проектирует рабочие процессы модели с MCP.

**Задачи документа:**
- отличить рассуждение агента от операции, которую следует выполнять детерминированным кодом; решить, нужен ли MCP, CLI или оба интерфейса;
- выбрать поверхность MCP: `tool` для model-controlled запроса/операции, `resource` для адресуемого контекста, `prompt` для повторяемого шаблона;
- определить границы tools, описание и схему аргументов, валидацию, права, ошибки и побочные эффекты;
- спроектировать достаточный результат: полезные поля, условные `next_actions`, атрибуты/дочерние сущности и раскрытие деталей по ID;
- задать безопасный порядок вызова MCP клиентом/агентом и проверять всю цепочку на реалистичных задачах.

**Основные принципы:**
1. MCP — интерфейс к нужной функциональной возможности (capability), а не повод оборачивать каждый endpoint или мыслительную операцию в tool.
2. Семантический выбор и разрешение неоднозначности остаются у агента/пользователя; точная, массовая и повторяемая обработка выполняется кодом.
3. `tools`, `resources` и `prompts` имеют разные роли; аргументы валидируются, а права и бизнес-ограничения проверяются на доверенной стороне.
4. Результат должен быть достаточным, но ограниченным. `next_actions` — прикладные подсказки, а не вызовы; самостоятельные дочерние сущности получают ID только если их нужно отдельно адресовать.
5. Результат tool не является командой или разрешением на следующий вызов: `next_actions` сама не запускает tool; агент/host сверяет подсказку с намерением пользователя, доступной schema, policy и нужным подтверждением.
6. Эффективность оценивается по всему workflow — успешности, риску, числу вызовов, latency и суммарным токенам, — а не по минимальной длине одного ответа.

**Как читать.** Часть I — проектирование MCP; часть II — безопасный вызов и обработка результата; часть III — evaluation и pre-release checklist. Примеры показывают прикладные контракты и не являются встроенными полями MCP, если это прямо не отмечено.

**Срез:** 24 ноября 2026 года; техническая опора — редакция MCP **2026-07-28**.  
**Статус правил:** `[STD]` требование официальной спецификации; `[GUIDE]` рекомендация; `[ЭВРИСТИКА]` гипотеза для измерения.

> **Развести источники:** MCP — официальный протокол, но не RFC IETF; его MUST/SHOULD относятся к редакции, транспорту, клиенту или серверу, указанным в тексте. JSON-RPC 2.0 и JSON Schema 2020-12 — самостоятельные спецификации; RFC 8259/7464 и POSIX — стандарты для своих областей. OWASP/CLIG/vendor guides — рекомендации. Количество tools, форма `--json`-подобных wrappers, размер ответа и проценты экономии — не нормы MCP. [MCP changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog) · [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259.html) · [RFC 7464](https://www.rfc-editor.org/rfc/rfc7464.html) · [POSIX.1-2024](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/V3_chap01.html)

---

## I. Постулаты проектирования MCP для вызова агентами

### 1. Для каждой пользовательской задачи выбрать правильную поверхность
**Правило.** Tools — model-controlled операции/вычисления; resources — адресуемые данные/контекст; prompts — повторяемые шаблоны взаимодействия. Не превращать всякий источник данных в action-tool и не помещать операцию записи в resource. **[STD/GUIDE]** [MCP Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) · [MCP Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)

- **Удачно:** поиск и изменение — tools; крупный документ — resource/resource link, который открывают по необходимости.
- **Неудачно:** один tool каждый раз возвращает весь архив документов, хотя задаче нужна одна конкретная запись.

### 2. Дизайн tools начинать с намерений, не с копирования endpoint
**Правило.** Выбрать небольшой набор отдельных по смыслу workflow-инструментов. Объединять шаги, которые почти всегда идут вместе и имеют одну ясную цель; разделять разные цели, права и риски. Не делать множество перекрывающихся tools или универсальный `do_everything`/`execute_query`, если действие можно выразить безопасной предметной операцией. **[GUIDE]** [Anthropic: Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents) · [OpenAI: Function calling best practices](https://developers.openai.com/api/docs/guides/function-calling)

- **Удачно:** `search_orders` ищет заказы с фильтром/лимитом; отдельный `cancel_order` меняет состояние и требует собственной авторизации/подтверждения.
- **Неудачно:** один `api_request(method, path, body)` даёт модели неограниченный доступ ко всем endpoint.

### 3. Имя должно различать действие и область; каталог — быть стабильным
**Правило.** Имена tools рекомендуется делать уникальными в пределах сервера; MCP **SHOULD**: 1–128 символов, ASCII-буквы/цифры/`_`/`-`/`.` и case-sensitive трактовка. Если агрегируются разные серверы, разрешайте коллизии префиксом/namespace: `search` само по себе не уникально. Сохраняйте детерминированный порядок tools, пока набор не изменился; каталог может зависеть от предъявленной авторизации, но не от соединения или случайного побочного эффекта другого вызова. **[STD]** [MCP Tools: Tool Names](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#tool-names) · [MCP Tools: listing](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#listing-tools)

- **Удачно:** `github.search_issues` и `drive.search_files`.
- **Неудачно:** два подключённых сервера оба называют tool `search`, клиент не показывает, где искать.

### 4. Описание — краткая инструкция выбора, формата и эффекта
**Правило.** Указать: цель; когда/когда не использовать; scope; смысл важных аргументов; формат, единицы/timezone; побочный эффект; limit, полноту и способ продолжения. Писать для модели и человека: без лишней внутренней реализации, но так, чтобы не оставалось существенного вопроса. Считать server-supplied description/schema возможной поверхностью prompt injection. **[GUIDE]** [Anthropic: Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents) · [OWASP MCP Security](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html)

- **Удачно:** «Ищет заказы текущего авторизованного клиента; возвращает до 50 совпадений; для изменения используйте `cancel_order`; время — RFC 3339 UTC offset».
- **Неудачно:** «Fetch data» — непонятны данные, scope, фильтры, эффекты и предел результата.

### 5. Аргументы — типизированный, семантически однозначный контракт
**Правило.** `inputSchema` — валидный JSON Schema object; без `$schema` MCP применяет JSON Schema 2020-12. Для каждого поля определить required/optional, absent vs `null`, формат, единицы, диапазон, enum, длину/число элементов, default и сочетания. JSON Schema `default` само значение не подставляет: сервер должен явно реализовать и описать дефолт. Схема не заменяет бизнес-валидацию. **[STD/GUIDE]** [MCP JSON Schema usage](https://modelcontextprotocol.io/specification/2026-07-28/basic#json-schema-usage) · [MCP Tools: inputSchema](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#tool)

- **Удачно:** время имеет формат/timezone; `limit` bounded; статус — enum; для взаимоисключающих действий — один mode/discriminator.
- **Неудачно:** `date: string`, `count: number`, несколько булевых флагов с невозможными комбинациями и недокументированными дефолтами.

### 6. Закрывать схему осознанно и тестировать подмножество клиента
**Правило.** `additionalProperties: false` полезно для закрытого контракта и защиты от случайных аргументов, но не является универсальным требованием MCP: сопоставить strictness с эволюцией схемы/клиентами. MCP 2026-07-28 допускает JSON Schema 2020-12; фактическую поддержку `$ref`, composition и форматов сверять у каждого SDK/host. В OpenAI strict function calling действует отдельное ограничение: `additionalProperties: false`, все поля перечислены в `required`; nullable-форма используется для моделирования необязательности. **[STD/PLATFORM]** [MCP JSON Schema usage](https://modelcontextprotocol.io/specification/2026-07-28/basic#json-schema-usage) · [OpenAI: strict mode](https://developers.openai.com/api/docs/guides/function-calling)

- **Удачно:** неизвестные поля запрещены в закрытой схеме; альтернативные клиенты проверены; старые версии меняются совместимо.
- **Неудачно:** считать OpenAI strict subset требованием JSON Schema/MCP или применять `$ref`, которую целевой клиент не умеет валидировать.

### 7. Не просить модель генерировать произвольную программу, shell, SQL или URL без границ
**Правило.** Предоставить типизированную предметную операцию/поиск вместо общего исполнительного интерфейса. Если произвольный язык необходим — ограничить грамматику, права, таблицы/поля, URL allowlist, размер и время исполнения; проверить path traversal/SSRF/injection на сервере. **[GUIDE]** [OWASP MCP Security](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html) · [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)

- **Удачно:** `search_logs(service, since, severity, limit)`.
- **Неудачно:** `run_shell(command)` или `fetch_url(url)` с произвольным адресом от модели.

### 8. Валидировать и авторизовывать на доверенной стороне при каждом вызове
**Правило.** Проверять входную схему, бизнес-правила, tenant/object access, разрешённую операцию и лимиты на сервере. Не выводить право на действие из того, что tool доступен модели; не доверять ID объекта только потому, что он валиден по типу. MCP Tools требует проверять входы, access control, rate limits и санитизацию output. **[STD/SECURITY]** [MCP Tools: Security Considerations](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#security-considerations) · [OWASP MCP Security](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html)

- **Удачно:** `order_id` проходит tenant/object authorization на каждом вызове.
- **Неудачно:** сервер принимает любой ID от модели, потому что JSON соответствует схеме.

### 9. Выдавать машинно надёжный результат и соблюдать output schema
**Правило.** Для стабильных машинных данных задавать `outputSchema`; сервер **MUST** возвращать соответствующий результат, клиенту **SHOULD** его валидировать. Использовать `structuredContent`; MCP 2026-07-28 допускает любое JSON-значение. Не путать его с модельным structured output. Для обратной совместимости спецификация рекомендует (**SHOULD**) вернуть сериализованный JSON также в `TextContent`; проверить, не попадает ли дублирующий payload дважды в контекст клиента. Для non-JSON содержимого выбирать подходящий block type: text, image, audio или resource link. **[STD]** [MCP Tools: Structured Content/Output Schema](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#structured-content)

- **Удачно:** schema/structured result содержит предсказуемые поля `status`, `items`, `count`, `next_cursor`.
- **Неудачно:** обещать schema, возвращая иногда строку prose, иногда объект с иными именами/типами.

### 10. Отдавать полезный минимум; явно показывать полноту и происхождение
**Правило.** Возвращать ровно данные для ответа/следующего вызова: идентификаторы, релевантные поля, количество, scope, единицы и время/источник, если они влияют на смысл. Пустой результат — штатный результат; частичный/обрезанный — явно отметить, объяснить и дать путь к деталям. Не выдавать top-N за полную выдачу. **[GUIDE]** [Anthropic: Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents) · [MCP Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)

- **Удачно:** краткая статистика + релевантные записи + признак обрезания + ресурс/вызов по ID.
- **Неудачно:** огромный документ/лог без фильтра либо первые 10 строк без сообщения, что остальное опущено.

### 11. Большие списки — фильтр, лимит, cursor; пагинацию tool-результата определить отдельно
**Правило.** MCP cursor-пагинация стандартизована для `tools/list`, `resources/list`, `resources/templates/list`, `prompts/list`; она не добавляет автоматическую пагинацию произвольному `tools/call`. Для большого tool-результата определить отдельный `limit`/opaque cursor или ресурс. В протокольной пагинации cursor непрозрачен; отсутствие `nextCursor` — конец; клиенты не интерпретируют/не модифицируют token. Серверу рекомендуется стабильный cursor; invalid cursor — `-32602`. Между страницами нет общей гарантии snapshot consistency: при изменениях возможны дубли/пропуски. **[STD/GUIDE]** [MCP Pagination](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination) · [MCP Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)

- **Удачно:** первая страница ограничена; возвращён непрозрачный cursor; подробности элемента читаются отдельно по URI/ID.
- **Неудачно:** сервер молча обрезает `tools/call` до N строк и обещает, что встроенный `nextCursor` всегда продолжит выдачу.

### 12. Различать протокольную ошибку и ошибку выполнения tool
**Правило.** JSON-RPC `error` — проблема запроса/протокола; ошибка принятого tool-вызова (валидный RPC, но действие не выполнено) возвращается в result с `isError: true`. Давать краткую причину, поле/ограничение, стабильную категорию и исправимый следующий шаг; не раскрывать секреты/stack trace. `resultType` характеризует complete/input-required и не заменяет `isError`. **[STD]** [MCP Tools: Error Handling](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#error-handling) · [MCP Base Protocol](https://modelcontextprotocol.io/specification/2026-07-28/basic) · [JSON-RPC 2.0](https://www.jsonrpc.org/specification)

- **Удачно:** «`start_time` должен содержать timezone; передайте RFC 3339» + `isError: true`.
- **Неудачно:** бизнес-ошибка выглядит как пустой список или протокольный `-32602` без объяснения модели, как исправиться.

### 13. Считать MCP stateless; межвызовное состояние — явный handle
**Правило.** В редакции 2026-07-28 сервер не выводит контекст/пользователя из прошлого вызова или соединения. Состояние передавать явным непрозрачным handle; описать TTL/expiry; заново проверять права на handle при каждом вызове. Handle — имя, не authorization token; если он намеренно bearer-capability, использовать достаточную энтропию и ограниченный срок жизни. Не повторять необратимую операцию после timeout, пока не проверен статус или идемпотентность. **[STD/GUIDE]** [MCP statelessness](https://modelcontextprotocol.io/specification/2026-07-28/basic#statelessness) · [MCP Tools: Stateful Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#stateful-tools)

- **Удачно:** create возвращает `basket_id`; дальнейшие вызовы передают его; сервер проверяет owner и срок жизни.
- **Неудачно:** сервер предполагает, что второй tool-call пришёл в том же разговоре/соединении, и молча использует прошлую корзину.

### 14. Кэшировать только по scope и свежести, не смешивать пользователей
**Правило.** Для complete-ответов `server/discover`, списков tools/prompts/resources/templates и `resources/read` редакция MCP требует кэш-подсказки `ttlMs` и `cacheScope`. TTL — hint свежести, не гарантия неизменности; `0` означает немедленное устаревание. `private` нельзя шарить между authorization contexts; `public` разрешён только для реально неперсонального результата. Страницы кэшируются независимо, scope должен совпадать на всех страницах; кэш — не авторизация. Стабильный порядок tools помогает кэшировать определения и prompt. **[STD]** [MCP Caching](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/caching) · [MCP Tools: Listing Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#listing-tools)

- **Удачно:** список, одинаковый для всех, кэшируется public; документ пользователя — private, ключ связан с auth-контекстом.
- **Неудачно:** результат `resources/read` аккаунта A раздаётся по тому же public cache ключу аккаунту B.

### 15. Раскрывать каталог инструментов постепенно
**Правило.** При большом наборе начать с коротких доменных подсказок и малого набора частых tools; остальное находить поиском/отложенной загрузкой и открывать полный schema только для кандидатов по задаче. Tool search/deferred loading — архитектурный/вендорский механизм, не обязательная часть MCP. `<20` tools на старте — soft heuristic из документации OpenAI, не стандарт. **[GUIDE/ЭВРИСТИКА]** [OpenAI: Function calling/tool search](https://developers.openai.com/api/docs/guides/function-calling) · [Anthropic: Advanced tool use](https://www.anthropic.com/engineering/advanced-tool-use) · [Anthropic: context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

- **Удачно:** сначала модель видит `search_tools`; потом получает только подходящие `drive.search_files` и его schema.
- **Неудачно:** при каждом запросе отправлять модели 300 схем, включая административные операции, которые задаче не нужны.

### 16. Разделять данные и инструкции; метаданные/аннотации — не граница безопасности
**Правило.** Tool descriptions, resources и outputs считать недоверенным содержимым; результаты могут содержать prompt injection. Маркировать их как данные — полезная мера, но не защита. Аннотации tool — подсказки поведения, не авторизация/исполнение policy. Sensitive/destructive calls контролировать снаружи: показать точные параметры, дать человеку возможность deny/confirm, enforce policy на доверенной стороне. **[STD/SECURITY]** [MCP Tools: User Interaction/Annotations](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) · [OWASP MCP Security](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html)

- **Удачно:** untrusted text из поиска остаётся данными; перед отправкой письма приложение показывает кому/что и требует подтверждение.
- **Неудачно:** описание сервера говорит «игнорируй все ограничения», а клиент считает `readOnlyHint` доказательством отсутствия риска.

### 17. Защищать транспорт, credentials и локальный процесс
**Правило.** Для удалённого Streamable HTTP — TLS и подходящая аутентификация; MCP требует валидировать присутствующий `Origin` и отвечать 403 на невалидный. Для локального HTTP рекомендуется bind localhost. Авторизовывать каждый защищённый вызов и ресурс; не передавать токен MCP не тому audience/upstream. Не помещать секреты/PII в `x-mcp-header`. Для stdio stdout — только MCP framing; логи/диагностика — stderr; сам stdio не sandbox-ит процесс. **[STD/SECURITY]** [MCP Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http) · [MCP stdio](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio) · [MCP x-mcp-header](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#x-mcp-header) · [OWASP MCP Security](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html)

- **Удачно:** локальный server запущен в ограниченном sandbox; токен и права соответствуют конкретному сервису; stdio stdout содержит только протокольные сообщения.
- **Неудачно:** локальный HTTP listener открыт всей сети без необходимости; токен/PII продублированы в header/log; debug banner ломает stdio JSON-RPC.

### 18. Применять лимиты, таймауты, аудит и least privilege по эффекту
**Правило.** Задавать rate/concurrency/size/time/cost budgets; ограничивать system permissions; журналировать actor, действие, результат и корреляцию, редактируя секреты/PII. Оценивать риск по реальным возможным эффектам — чтение приватных данных тоже может быть высокорисковым. **[STD/SECURITY]** [MCP Tools: Security Considerations](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#security-considerations) · [OWASP MCP Security](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html)

- **Удачно:** bounded search, timeout, per-tenant quota и audit с редактированием чувствительных аргументов.
- **Неудачно:** неограниченный поиск/экспорт, глобальный credential с write-доступом и логирование всех токенов.

### 19. Диагностика полезна по задаче, но имена `status` и `doctor` не предписаны MCP
**Правило.** MCP не определяет универсальные команды или tools `status`/`doctor`. Если сервер зависит от auth, конфигурации, прав, сетевых сервисов или внешних бинарников, и проверка помогает реальным workflow, предоставьте отдельную read-only диагностику — например, `get_status` для компактного снимка и `run_diagnostics` для проверок с ограничиваемым `scope`/`checks`. Выбирайте tool для вычисляемой/on-demand проверки, resource — для адресуемого состояния/документа; описывайте freshness, timeout, проверяемые зависимости и объём доступа. Возвращайте стабильные ID, `pass/warn/fail`, затронутую подсистему и безопасные рекомендации. Проверка не должна незаметно менять конфигурацию; исправление — отдельный авторизованный tool с явными параметрами и подтверждением по риску. Не включайте в результат секреты, токены и неотфильтрованные внутренние данные. `npm doctor` и `brew doctor` — примеры продуктового паттерна, не требование MCP. **[GUIDE]** [MCP Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) · [MCP Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources) · [npm doctor](https://docs.npmjs.com/cli/v12/commands/npm-doctor) · [Homebrew troubleshooting](https://docs.brew.sh/Troubleshooting)

- **Удачно:** `acme.get_status({"scope":"workspace"})` возвращает read-only сводку; `acme.run_diagnostics({"checks":["auth","filesystem"],"detail":"summary"})` запускает ограниченные проверки; `acme.get_finding({"finding_id":"AUTH-03"})` раскрывает выбранную диагностику.
- **Неудачно:** считать название `doctor` зарезервированным стандартом MCP, выполнять repair при чтении статуса или возвращать credential/полный config в ответе диагностики.

### 20. Резюмировать tool-результат и делать ошибки исправимыми
**Правило.** Для успешного изменения кратко назвать действие, стабильный ID/target, итоговое состояние/счётчик и предупреждения. Для небольшого числа findings показать их поштучно; для длинного списка — сводка, группы по общей причине, severity, количества, несколько примеров и явный путь к деталям. Порог, например **5 findings**, — эвристика для оценки объёма, а не стандарт; подберите его по длине сообщений и целевой модели. Стабильные codes/IDs и одно-два релевантных следующих действия полезны, но не перечисляйте полный каталог tools и не предлагайте/не вызывайте исправление автоматически. Удачно выполненная диагностика со статусом `issues_found` остаётся успешным tool result; `isError: true` предназначен для ошибки выполнения, мешающей операции. Для такой ошибки укажите причину, поле/ограничение, стабильную категорию и безопасный способ восстановления. Эти различия согласуются с механизмами error handling MCP; лаконичность и исправимые подсказки — рекомендация по дизайну, не требование длины ответа в протоколе. **[STD: семантика `isError`; GUIDE; ЭВРИСТИКА: порог группировки]** [MCP Tools: Error Handling](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#error-handling) · [Anthropic: Writing effective tools](https://www.anthropic.com/research/writing-tools-for-agents)

- **Удачно, успешное изменение:** `content` кратко сообщает «Release R-42 переведён в staging; 3 сервиса обновлены, 0 предупреждений», а `structuredContent` возвращает, например, `{"status":"updated","release_id":"R-42","services_updated":3,"warnings":0}` по объявленной output schema.
- **Удачно, длинный диагностический ответ:** краткий `content` сообщает «8 проблем: 6 errors, 2 warnings; показана 1. Запросите finding `AUTH-03` или продолжите по cursor»; `structuredContent` содержит schema-валидные `summary`, `groups`, `findings` и данные страницы.

```json
{
  "resultType": "complete",
  "structuredContent": {
    "status": "issues_found",
    "summary": {"checks_total": 24, "passed": 16, "errors": 6, "warnings": 2, "findings_total": 8},
    "groups": [
      {"id": "auth", "errors": 2, "warnings": 0, "count": 2},
      {"id": "permissions", "errors": 4, "warnings": 1, "count": 5},
      {"id": "network", "errors": 0, "warnings": 1, "count": 1}
    ],
    "findings": [{"id": "AUTH-03", "severity": "error", "message": "Токен профиля P7 истёк"}],
    "page": {"returned": 1, "total": 8, "truncated": true, "next_cursor": "opaque-token"}
  },
  "content": [{"type": "text", "text": "Найдено 8 проблем (6 errors, 2 warnings); показана 1. Запросите finding AUTH-03 или продолжите по cursor."}]
}
```

Здесь `next_cursor` — часть **прикладного контракта конкретного tool**, а не встроенная пагинация `tools/call`. Для бизнес-находок `isError` не нужен: вызов диагностики успешно вернул данные.

- **Неудачно:** голое `OK`; повторить тот же длинный список 2 раза — как prose и как JSON — без пользы; пометить весь успешный health report `isError: true` только потому, что в проверяемой системе есть ошибки; либо показать первые 5 проблем без общего количества/признака усечения.

### 21. Для больших деревьев раскрывать summary → оглавление → выбранную ветвь
**Правило.** Используйте progressive disclosure: сначала краткие итоги и счётчики; затем компактное оглавление групп/путей, типы и признаки усечения; дальше — детали только выбранной группы, стабильного `finding_id` или поддерева на заданной глубине. Условные параметры (`section`, `path`/`pointer`, `max_depth`, `fields`, `limit`, прикладной opaque cursor) должны быть явно описаны в schema и ограничены по размеру. Для больших артефактов можно вернуть ссылку на MCP resource, если клиент это поддерживает. MCP cursor-пагинация списка tools/resources не пагинирует автоматически произвольный `tools/call`: механизм continuation такого результата проектирует сервер. Плоская запись `path = value` полезна как **обзор**, но это не стандарт MCP и не формат patch. Для адресации значения JSON можно применять JSON Pointer (RFC 6901); если результат задаёт изменения документа, называйте и выдавайте именно patch по согласованному формату, например JSON Patch (RFC 6902). **[GUIDE; RFC 6901/6902 — только синтаксис JSON Pointer/Patch]** [MCP Pagination](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination) · [MCP Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources) · [RFC 6901: JSON Pointer](https://www.rfc-editor.org/rfc/rfc6901) · [RFC 6902: JSON Patch](https://www.rfc-editor.org/rfc/rfc6902)

- **Удачно:** `acme.inspect_tree({"root":"services","max_depth":2,"limit":20})` возвращает `outline:[{"id":"billing","pointer":"/services/billing","findings":3}]`, `total`, `truncated` и opaque `next_cursor`; затем `acme.inspect_tree({"pointer":"/services/billing/findings","max_depth":1,"limit":10})` либо `acme.get_finding({"finding_id":"F-104"})` раскрывает только нужную ветвь/запись.
- **Неудачно:** один неограниченный tool-result со всем деревом; молча отрезанные элементы; `path=value` названы «JSON Patch» без операций patch; либо пагинация только списка tools ошибочно объявлена пагинацией вызова.

### 22. Считать prompt caching бонусом, а не основанием для лишних MCP-вызовов
**Правило.** Различайте два слоя: MCP-кэш с `ttlMs`/`cacheScope` (раздел 14, когда он поддерживается для конкретных данных) и provider-specific prompt/KV-cache, который может переиспользовать совпадающий префикс запроса модели. Кэш модели не задаётся MCP и не гарантируется каждым tool-call. Повторяемые инструкции, состав/порядок tool schemas могут помочь только если клиент/модель посылает соответствующий стабильный префикс и выполняются условия провайдера; результат с изменившимся содержимым, уникальный вывод и генерация ответа остаются затратами. Дополнительные раскрытия могут экономить контекст по сравнению с гигантским первым ответом, но каждый вызов имеет свою latency/стоимость обработки. Не делайте лишние round-trip «ради cache hit»; сравнивайте task success, суммарные вызовы/latency, usage и реальные cache hit/miss на целевом host/model. **[GUIDE]** [MCP Caching](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/caching) · [OpenAI: Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) · [Anthropic: Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) · [Anthropic: Advanced tool use](https://www.anthropic.com/research/advanced-tool-use)

- **Удачно:** tool definitions/schema стабильны; сначала передана компактная сводка; агент раскрывает ветвь только когда она влияет на задачу; эффективность проверена по usage/latency конкретного API.
- **Неудачно:** передать 30 000 строк «на будущее» в расчёте на cache hit или добавить серию MCP-вызовов только потому, что якобы кэш сделает их бесплатными.

### 23. Сначала решить, нужен ли tool; определить его границу по workflow
**Правило.** MCP tool — интерфейс к полезной операции, не способ сериализовать каждую мысль агента или endpoint. Добавляйте tool, когда агенту требуется capability вне его контекста: актуальные/авторизованные данные, воспроизводимая обработка значимого объёма, точная бизнес-проверка или side effect. Если нужные факты уже в контексте и остаётся небольшая семантическая оценка/формулировка, пусть это делает модель без нового вызова. Для смешанного workflow tool должен извлечь и ограничить факты/кандидаты, агент — оценить смысл; не переносите свободно трактуемое намерение в детерминированную логику или шаблоны regex. **[GUIDE]** [Anthropic: Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents) · [OpenAI: Function calling](https://developers.openai.com/api/docs/guides/function-calling)

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

Распределяйте по семантике поверхностей MCP: resources — application-driven context, tools — model-controlled actions/queries. «Детерминированный» не означает «безопасный»: проверяйте authorization, scope, бизнес-ограничения, повторный вызов и side effects на сервере. MCP уместен, когда capability живёт за сервисной границей и её нужно обнаруживать/вызывать из совместимых hosts по типизированной схеме с серверными правами и аудитом. Если задача естественно работает с локальным repo/filesystem/stdin/stdout, процессом или shell-pipeline и агенту разрешён такой процесс, CLI может быть проще; массовая обработка при этом должна выполняться внутри кода, а не тащить весь dataset в prompt. Если нужны оба интерфейса, держите одну domain implementation и тонкие CLI/MCP adapters. Не плодите почти одинаковые tools: каждая возможность увеличивает пространство выбора, описания и вызова; группируйте только реально повторяемые задачи с общими параметрами/правами и понятным workflow, не делайте универсальный `do_anything`. Этот выбор — проектная эвристика, не нормативное требование протокола. **[STD/GUIDE]** [MCP Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources) · [MCP Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) · [Anthropic: Context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

#### Примеры выбора по дереву

**Хорошие примеры**
1. Пользователь уже прислал два плана и критерии выбора. Агент сравнивает их без MCP; нового внешнего факта или действия нет. **Почему хорошо:** не расходуется токен-бюджет на лишнее описание/call/result, а задача остаётся в области рассуждения по данному контексту.
2. Нужно найти просроченные заказы в авторизованной сервисной системе. MCP `search_orders(status="overdue", limit=20)` фильтрует на сервере и возвращает число совпадений, короткие summaries и IDs; агент выбирает нужный заказ, а `get_order(order_id)` раскрывает только его детали. **Почему хорошо:** сервер выполняет повторяемую фильтрацию; модель получает bounded evidence для смыслового выбора; read/query и изменение состояния остаются разными tools с отдельной проверкой прав.

**Плохие примеры**
1. Универсальный `handle_request(instructions: string)` принимает «разберись с плохими заказами и исправь их», сам угадывает критерий и пишет в базу. **Почему плохо:** смешаны семантическое решение и side effect, нет явного target, узкой schema или безопасного места для уточнения; слабой модели особенно легко выбрать не то.
2. Для каждого API endpoint и каждого поля создаётся отдельный tool (`get_order_status`, `get_order_owner`, `get_order_created_at`), либо один `execute_sql` возвращает все строки. **Почему плохо:** каталог и выбор разрастаются, связанные сведения требуют лишних calls, а большой dump перегружает контекст. Объединяйте естественные read-only projections, оставляйте точечные tools для разных прав/рисков, а объём ограничивайте фильтрами и summaries.

### 24. Формировать контракт входа под явное решение агента

**Правило.** Имя, описание и `inputSchema` вместе должны однозначно отвечать: что делает tool, когда его вызывать, чего он не делает, какие данные/права/состояние затрагивает и какие аргументы обязательны. Используйте предметные `verb + object`, короткое различающее описание, конечные типы, enum/range/max length и пределы числа элементов. Для даты, времени, единиц, timezone, tenant/scope, cursor и defaults опишите точную семантику. `required` — только для значений, без которых вызов невозможно безопасно выполнить; default — только если он безопасен и сервер явно его реализует. Schema помогает сформировать вызов, но не заменяет серверную бизнес-валидацию и авторизацию.

Разделяйте `query` (критерий поиска, не команда на изменение), фильтры, стабильный ID цели и параметры операции. Свободный текст может быть поисковым содержимым, но не должен превращаться в неограниченное поле `instructions`; regex проверяет простую структурную форму, а не смысл намерения. Не заставляйте модель угадывать объект, аккаунт/tenant, единицы или опасный эффект. Если критическое значение неизвестно либо неоднозначно — попросить уточнение или, только если это поддерживает применяемая версия/клиент, вернуть предусмотренный контракт `input_required`; не выбирать default молча. Для больших строк и массивов установить размер/число элементов; batch делать только для повторяющейся предметной операции с ясными лимитами и частичным результатом.

**Хорошие примеры**
1. `search_tickets(query, status?, limit<=20, cursor?)` — `query` только ищет; `limit` bounded; результат содержит кандидатов и ID. **Почему хорошо:** чтение не меняет записи, optional поля имеют понятный смысл, запрос ограничен.
2. `close_ticket(ticket_id, resolution, idempotency_key?)` — однозначная команда для одной записи с отдельным ID и причиной закрытия. **Почему хорошо:** target и эффект названы явно, права/бизнес-правила можно проверить на сервере, повтор — сделать идемпотентным.

**Плохие примеры**
1. `handle_request(instructions: string)` принимает «найди плохие тикеты и исправь их». **Почему плохо:** поле прячет intent, критерий, выбор объекта и side effect в свободном тексте; схема не ограничивает, что именно разрешено сделать.
2. `manage_ticket(id?, close?, delete?, status?, resolution?, force?)` позволяет несовместимые комбинации. **Почему плохо:** модель должна угадать, какие поля сочетать; вместо него нужны отдельные `search_tickets`, `close_ticket`, `delete_ticket` с разными правами/подтверждениями.

**[STD/GUIDE]** [MCP Tools: schema and annotations](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) задаёт протокольные поля/схемы; [OWASP: Input Validation](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html) рекомендует проверять и syntax, и semantics, а authorization — отдельно.

### 25. Возвращать ровно достаточный контракт результата — измерять стоимость каждого поля
**Правило.** Каждый MCP result field должен оправдываться хотя бы одним downstream need: принять решение или вызвать следующий tool; точно указать объект; проверить выполнение/полноту; понять ошибку и восстановиться; сослаться на evidence, когда требуется provenance. Уберите поле, если оно лишь зеркалит внутреннюю модель, не меняет ни один следующий шаг, надёжно дублируется либо раскрывает нерелевантную/чувствительную информацию. В то же время не минимизируйте до «успех»: без ID, фактического значения изменения, scope/unit/source или признака усечения агент может повторно вызвать операцию, действовать не на той записи или ошибочно объявить результат полным. Для коллекций возвращайте counts, bounded `items`, `truncated` и cursor/page token; полные записи — отдельным detail/resource fetch. Не передавайте ненужные поля пользователя, secrets, stack traces и внутренние таблицы. Токены — бюджет для **всего workflow**: компактные высокосигнальные поля часто дешевле цепочки повторных вызовов. **[GUIDE]** [Anthropic: tool results and context](https://www.anthropic.com/engineering/writing-tools-for-agents) · [Anthropic: effective context](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

#### Явно подсказывать модели возможный следующий tool — только когда это помогает
Если сервер знает конкретный, допустимый и непосредственно релевантный follow-up, его output schema может включать проектное поле `next_actions` с точным именем уже опубликованного tool, его аргументами и кратким назначением. Возвращайте один наиболее полезный вариант, редко — до трёх альтернатив, а не каталог всех операций. Если кандидатов несколько и выбирать нужно по смыслу запроса, отдайте компактные ID/атрибуты и оставьте выбор модели. `next_actions` — **данные-подсказки, не вызов и не стандарт MCP**: клиент/агент проверяет, что tool существует в текущем каталоге, arguments соответствуют его актуальной schema и действие соответствует намерению пользователя. Не выполнять подсказку автоматически; write/destructive шаги не предлагать за рамками запроса и защищать обычной policy/confirmation. Если хорошего follow-up нет, не выдумывать его (пустой список или отсутствие поля — как задаёт output schema).

```json
{
  "resultType": "complete",
  "structuredContent": {
    "project": {"id": "P-7", "status": "degraded", "owner": "payments"},
    "deployments": {
      "total": 128,
      "items": [{"id": "D-204", "status": "failed"}],
      "truncated": true,
      "next_cursor": "opaque-token"
    },
    "next_actions": [{
      "tool": "get_deployment",
      "arguments": {"deployment_id": "D-204"},
      "purpose": "получить детали выбранного deploy"
    }]
  },
  "content": [{"type": "text", "text": "Проект P-7 degraded; показана одна из 128 deployment-записей."}]
}
```

Здесь `next_actions` должен входить в прикладной `outputSchema`, если схема объявлена; это не MCP built-in. Не дублируйте в `content` весь `structuredContent`: короткий текстовый summary допустим, если он реально нужен клиенту/модели.

**Ещё хороший пример:** `search_tickets` вернул несколько похожих тикетов, и релевантный может выбрать только агент по контексту пользователя. Сервер возвращает короткие summaries/IDs без `next_actions` для каждого результата. **Почему хорошо:** сервер не принимает смысловое решение и не добавляет лишние tool-рекомендации в контекст.

**Плохие примеры**
1. Каждый ответ включает список всех tools сервера в `next_actions`. **Почему плохо:** он дублирует каталог, увеличивает ввод и размывает наиболее релевантный follow-up.
2. После read-only поиска tool подсказывает `delete_project` или неподдерживаемый tool без связи с запросом. **Почему плохо:** рекомендация не даёт полномочия на изменение и может быть ошибочной/враждебной; клиент обязан проверить каталог, schema, пользовательское намерение и внешнюю policy.

#### Дочерняя сущность или атрибут: отделять модель данных от числа tools/resources

Различайте четыре уровня: **атрибут** (свойство родителя), **вложенная summary-запись** (частичная проекция ребёнка), **дочерняя сущность** (самостоятельно адресуемый объект) и **MCP tool/resource** (протокольная возможность прочитать или обработать данные). `next_actions` — только ссылка-подсказка на уже существующий tool, это не дочерняя сущность и не новый вызов.

```text
1. Это значение описывает только состояние родителя и не выбирается отдельно?
   ├─ Да → атрибут родителя: status, owner, last_deployment_at.
   └─ Нет → у ребёнка есть собственный стабильный ID, права, жизненный цикл,
      история, связь с другими объектами или отдельные действия?
      ├─ Нет → не вводить самостоятельную сущность; вложить только нужную
      │  проекцию или оставить атрибутом родителя.
      └─ Да → моделировать child entity и вернуть ID + связь с родителем.

2. Нужны ли подробности ребёнка в этом ответе?
   ├─ Да, детей мало и эти поля влияют на текущее решение → вернуть короткие
   │  bounded summaries с ID; полные детали — только если действительно нужны.
   └─ Нет / детей много / детали опциональны → count + релевантная выборка
      + `truncated`/cursor; выбранный ID раскрывать отдельным вызовом.

3. Нужна ли отдельная поверхность MCP?
   ├─ Адресуемое read-only содержимое → resource/URI, если host умеет его читать.
   ├─ Поиск, вычисление, изменяющий side effect → подходящий tool.
   └─ Поле/summary достаточно для задачи → не добавлять ни entity endpoint,
      ни tool только ради структуры.
```

**Хорошие примеры**
1. В ответе о проекте есть `project.status`, `project.owner` и `last_deployment_at`. **Почему хорошо:** это компактные свойства, нужные для оценки самого проекта; у них нет самостоятельного жизненного цикла, отдельной авторизации или действия, поэтому не нужен `get_project_status`.
2. Deployment имеет собственные `deployment_id`, статус, историю и возможность отдельного просмотра. Ответ возвращает `deployment_count`, несколько `[{id,status}]`, `truncated`/cursor; `get_deployment(deployment_id)` получает детали только выбранной записи. **Почему хорошо:** ID сохраняет адресуемость и recovery, а ограниченная проекция не тащит все логи в контекст.

**Плохие примеры**
1. Каждый вызов `get_project` вкладывает все 128 deployment-объектов, все события и логи. **Почему плохо:** большинство полей не влияет на текущий шаг; важные факты теряются, контекст раздувается, возрастает риск усечения и передачи лишних данных.
2. Создаются tools `get_deployment_D-204`, `get_deployment_D-205`, `get_project_owner`, `get_project_status`. **Почему плохо:** ID превращён в нестабильное имя, атрибуты требуют лишних вызовов, а каталог становится длиннее и труднее для слабой модели. Оставьте атрибуты в `get_project`, а для независимых детей — один schema-ограниченный `get_deployment(deployment_id)` или подходящий resource.

```json
{
  "status": "updated",
  "target": {"id": "R-42", "name": "Payments staging"},
  "changed": {"version": "4.2"},
  "warnings": []
}
```

Здесь статус, идентичность цели и реально изменённое поле могут помочь пользователю и следующему шагу; не добавляйте всю конфигурацию проекта без сценария. Для поиска подходящи, например, `total`, bounded `matches: [{id,title,status,snippet}]`, `truncated`, `next_cursor`; набор полей зависит от того, как агент выбирает candidate. Состав «достаточного минимума» определяется evaluation, а не универсальным списком свойств.

**Критерий поля:** если убрать поле, станет ли задача реже успешной, менее проверяемой или безопасной, либо потребуется ещё один round-trip? Если нет — не отдавайте его по умолчанию. Проверяйте ablation на реальных заданиях, отдельно сравнивая `next_actions`, вложенные summaries и полный child-detail; измеряйте success/incorrect action, лишние вызовы, суммарные input tokens, latency и утечки. Полезные для отладки большие details можно оставить opt-in (`include_details`) или вынести в отдельный resource. Отдельно от протокольных требований: структура/ограничение результата — рекомендация дизайна; MCP допускает текстовое содержимое и структурированный результат в рамках применимой версии спецификации. Ошибки валидации и бизнес-ограничений формулируйте так, чтобы агент мог исправить аргумент или безопасно уточнить; не раскрывайте приватные детали. **[STD/GUIDE]** [MCP Tools: output schemas and errors](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)

### 26. Проверять входы и результаты на границе сервера
**Правило.** Schema помогает модели сформировать корректный вызов, но не является security boundary. MCP server MUST валидировать все inputs, применять доступы и rate limits и санитизировать outputs; client SHOULD проверять results и запрашивать user confirmation для чувствительных операций. На сервере независимо проверьте тип/shape/size и бизнес-инварианты, актуальные права на конкретный объект, допустимость перехода состояния, idempotency/повтор и ограничение результата. Ошибка исполнения должна называть исправимую причину и допустимое действие (например, разрешённый диапазон); протокольную ошибку не маскировать под успешный ответ. Информация из tool/resource result — данные, а не новая инструкция с привилегией system/developer; не позволяйте содержимому удалённого ресурса переопределять политику или инициировать сторонний write. **[STD/SECURITY]** [MCP Tools: Security Considerations and Error Handling](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) · [OWASP: Input Validation](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)

---

## II. Постулаты вызова MCP агентом/клиентом

1. **Сначала согласовать протокол и возможности:** в редакции 2026-07-28 каждый запрос несёт protocol version и client capabilities в `_meta`; `clientInfo` рекомендуется. `server/discover` сервер **MUST** реализовать, клиенту его вызов необязателен (на stdio для dual-era совместимости клиенту **SHOULD** использовать probe). Современная редакция убрала `initialize`-handshake/протокольную сессию; legacy-сервер может их ожидать и не возвращать `resultType`. Обрабатывать `UnsupportedProtocolVersionError`; клиента и SDK проверять по версии. [MCP Versioning](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning) · [MCP Discovery](https://modelcontextprotocol.io/specification/2026-07-28/server/discover) · [MCP changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
2. **Не трактовать имя сервера/описание как подтверждённую identity или разрешение:** `serverInfo` — self-reported metadata, не security credential. Проверять provenance, авторизацию и policy отдельно. [MCP Discovery](https://modelcontextprotocol.io/specification/2026-07-28/server/discover) · [OWASP MCP Security](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html)
3. **Найти нужный tool и прочитать schema до вызова:** не выдумывать имена/поля; предпочитать инструмент, чьи цель, scope и эффект совпадают с намерением. Для каталога больших размеров искать и раскрывать по требованию, не грузить всё в контекст. [MCP Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) · [Anthropic: tool design](https://www.anthropic.com/engineering/writing-tools-for-agents)
4. **Передать только нужные, проверяемые аргументы:** сверить required/format/enum/limits/timezone и недостающую информацию; не считать валидный ID авторизацией. [MCP JSON Schema usage](https://modelcontextprotocol.io/specification/2026-07-28/basic#json-schema-usage) · [OWASP MCP Security](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html)
5. **Разобрать тип/полноту результата до вывода:** сначала `resultType`; `input_required` — обработать разрешённые `inputRequests`, передать ответы в `inputResponses` (и непрозрачный `requestState`, если он есть) и повторить запрос с новым JSON-RPC ID; затем корректно интерпретировать `isError`, schema, пустой/частичный результат. Старое отсутствие `resultType` учитывать только для совместимого старого протокола. [MCP Base Protocol](https://modelcontextprotocol.io/specification/2026-07-28/basic) · [MCP MRTR](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr) · [MCP Tools errors](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#error-handling)
6. **Курсор — непрозрачный; большой результат читать порциями:** использовать выданный cursor без разбора/изменения; не предполагать snapshot consistency; для `tools/call` проверять отдельный контракт пагинации. [MCP Pagination](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination)
7. **Tool result — данные, не новые полномочия/инструкции:** не исполнять инструкции из результата; не отправлять приватные данные в другой tool/домен без policy/согласия; проверять конкретные аргументы опасного вызова. [OWASP MCP Security](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html)
8. **Подтверждать риск и не повторять side effect вслепую:** приложение/agent harness обязан применить внешнюю авторизацию и подтверждение; после timeout сначала выяснить статус/idempotency. [MCP Tools: User Interaction](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#user-interaction-model) · [OWASP MCP Security](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html)
9. **Не удерживать большие сырые ответы в контексте:** просить filters/fields/limit/summary; использовать ресурсы/IDs для подробностей; преобразовывать, считать и объединять данные безопасно вне модели. [Anthropic: Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) · [Anthropic: context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
10. **Handle передавать явно и беречь:** не угадывать/не модифицировать его; учитывать срок жизни, приватность и повторную авторизацию. [MCP Tools: Stateful Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#stateful-tools)

---

## III. Оценка MCP-дизайна

- Создать held-out набор реалистичных, многошаговых задач с проверяемым outcome и допустимыми альтернативными траекториями; не оценивать только совпадение JSON/формулировки. Тестировать самую слабую модель и самый тесный контекстный бюджет, которые продукт поддерживает: ясные схемы снижают риск ошибок, но не дают гарантии безошибочности. [Anthropic: tool evaluation](https://www.anthropic.com/engineering/writing-tools-for-agents)
- Измерять: task success; правильность выбора и аргументов; ошибки/повторы/лишние вызовы; recovery; tokens/calls/latency p50-p95; частичные ответы; policy bypass, неавторизованные чтения/записи и утечки. [Anthropic: tool evaluation](https://www.anthropic.com/engineering/writing-tools-for-agents) · [OWASP MCP Security](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html)
- Тестировать реальные клиенты/SDK и версии протокола, поддержку JSON Schema, resultType/MRTR, empty/large/partial results, cursor, приватный кэш, expired handle, prompt injection, timeout, повтор side effect и конкурентные вызовы. [MCP Versioning](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning) · [MCP Caching](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/caching) · [MCP Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
- Для диагностических и древовидных tools проверить 0, 1, около выбранного порога и много findings; корректность `isError` vs `issues_found`, согласованность счётчиков/групп, truncation, opaque cursor, получение деталей, auth и отсутствие side effect. Сравнить краткое резюме с раскрытием выбранной ветви и вариантами с/без `next_actions` по task success, calls, latency, суммарным tokens и наблюдаемому prompt-cache hit/miss; фиксированный выигрыш не предполагать.
- Публикуемые числа экономии токенов — ориентиры только для описанных авторами экспериментов. Anthropic сообщал о tool-search reduction до 85% в своей конфигурации и примере code execution с 150k → 2k tokens; не переносить эти эффекты без собственного A/B/evaluation. [Anthropic: Advanced tool use](https://www.anthropic.com/engineering/advanced-tool-use) · [Anthropic: Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)

### Минимальный pre-release чек-лист

- [ ] Каждый tool/resource закрывает реальный agent workflow; выбор MCP vs CLI/agent reasoning обоснован местом данных, host-возможностями, правами и риском.
- [ ] Tool не угадывает семантику свободного текста regex-правилами; объёмная повторяемая работа выполняется детерминированно с фильтрами/лимитами.
- [ ] Каждое поле результата помогает решению, идентификации, проверке, provenance или recovery; полезность проверена на workflow, а не только по компактности.
- [ ] `next_actions` — bounded hints на существующие tools, проверяемые по актуальной schema; клиент не исполняет их автоматически.
- [ ] Проверена самая слабая поддерживаемая модель при целевом малом контекстном бюджете; надежность подтверждена eval и server-side controls, а не предположением о модели.
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

---

## Источники и классификация

### MCP: нормативная спецификация редакции 2026-07-28
- [Base Protocol / JSON Schema / Statelessness](https://modelcontextprotocol.io/specification/2026-07-28/basic)
- [Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
- [Discovery](https://modelcontextprotocol.io/specification/2026-07-28/server/discover)
- [Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)
- [Pagination](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination)
- [Caching](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/caching)
- [MRTR](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr)
- [Versioning](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning)
- [stdio](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio) · [Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http) · [Changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)

### Самостоятельные стандарты/протокольные спецификации
- [JSON Schema 2020-12](https://json-schema.org/draft/2020-12/json-schema-core.html) — спецификация схем, не MCP-специфичное подмножество.
- [JSON-RPC 2.0](https://www.jsonrpc.org/specification) — RPC-формат, не RFC IETF.
- [RFC 8259: JSON](https://www.rfc-editor.org/rfc/rfc8259.html) — IETF Internet Standard.
- [RFC 7464: JSON Text Sequences](https://www.rfc-editor.org/rfc/rfc7464.html) — IETF Standards Track / Proposed Standard.
- [RFC 6901: JSON Pointer](https://www.rfc-editor.org/rfc/rfc6901) — синтаксис адресации значения внутри JSON.
- [RFC 6902: JSON Patch](https://www.rfc-editor.org/rfc/rfc6902) — стандартизованные операции изменения JSON; не общее соглашение о кратком выводе.

### Рекомендации, не нормы MCP
- [OWASP MCP Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html)
- [OWASP Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html) — validation не заменяет business rules, authorization и security controls.
- [npm doctor](https://docs.npmjs.com/cli/v12/commands/npm-doctor) и [Homebrew Troubleshooting](https://docs.brew.sh/Troubleshooting) — примеры продуктовой диагностики, не требования MCP.
- [Anthropic: Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents)
- [Anthropic: Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Anthropic: Advanced tool use](https://www.anthropic.com/engineering/advanced-tool-use)
- [Anthropic: Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [OpenAI: Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI: Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) и [Anthropic: Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) — provider-specific условия кеширования префикса; не свойство MCP.
