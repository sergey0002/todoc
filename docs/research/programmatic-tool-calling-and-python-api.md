# Programmatic Tool Calling (PTC) и Python Agent API для `todoc`: аудит репозитория и архитектурные рекомендации

**Статус:** исследовательский и архитектурный документ с рекомендациями к внедрению (нормативные постулаты и полная спецификация пакета `src/todoc/sdk/` вынесены в парное руководство [`docs/guides/python-api-for-agents.md`](../guides/python-api-for-agents.md)).  
**Дата:** 2026-11-28 (UTC).  
**Основание:** аудит исходного кода [`src/todoc/`](../../src/todoc), живые замеры на датасете `demo/`, реестр эксплуатационных фрикций в `demo/bugs/`, конституция [`docs/plan/constitution.md`](../plan/constitution.md), мастер-план рефакторинга [`docs/plan/todoc-master-refactoring-plan.md`](../plan/todoc-master-refactoring-plan.md) и план MCP-адаптера [`docs/plan/mcp-adapter.after.md`](../plan/mcp-adapter.after.md).

---

## 0. Краткий вердикт (Executive Summary)

`todoc` спроектирован вокруг правильного конституционного ядра: **файлы в `DATA_ROOT` — единственный источник истины (`P1`), ядро детерминировано и офлайн (`P5`), данные декларативны (`P3`, `P10`), запись — review-first с CAS-защитой (`P6`), выдача ограничена по контексту (`P7`)**. Однако по мере роста поверхности продукта до **64 листовых CLI-команд в 11 группах** ([`src/todoc/cli.py`](../../src/todoc/cli.py), 2 503 строки) обнаружен системный разрыв между удобством одиночной команды и стоимостью реальной агентской сессии:

1. **Простой CLI идеален для атомарных вызовов (`N = 1..2`), CI-гейтов и финализации `todoc sync`, но дорог на цепочках.** На живом замере по корпусу `demo/` (465 документов, 205 записей, 169 связей, 752 упоминания) типовой 8-шаговый сценарий триажа через subprocess CLI тратит **3 747,6 мс** локального CPU, требует **8 последовательных LLM-инференсов** и выбрасывает в контекст модели **43 006 символов (~11 000 токенов)** промежуточных JSON-конвертов. Тот же сценарий за **1 ход** через внутрипроцессный Python API укладывается в **1 191,5 мс** (1 LLM-ход вместо 8) и возвращает в контекст **1 676 символов (~420 токенов)** — **экономия 96,1% промежуточных токенов**.
2. **Подход Programmatic Tool Calling (PTC / Code Mode)** — когда агент получает компактный типизированный `.pyi`-контракт Python SDK и за один ход пишет короткий скрипт композиции (поиск → фильтрация → обход графа → расчёт агрегата → печать компактного итога) — устраняет сразу пять задокументированных болей `todoc`:
   - ручной `grep` при кросс-резолве двойных идентификаторов `doc:...` и `document:...` ([BUG-013](../../demo/bugs/bug-013-neodnorodnye-id-i-output-kontrakty-rezolv-identifikatora-trebuet-ruchnogo-grep.md));
   - создание временных JSON-файлов под `--input-file` / `--query-file` / `--patch-file` с риском засорить индекс по `P1-9` ([`11-known-issues.md`](../state/11-known-issues.md)) и двойным прогоном `2 × N` процессов ([DESIGN-Q02](../../demo/bugs/design-q02-review-first-dvoynoy-vyzov-stoimost-dlya-agenta-protiv-kontrolya.md));
   - невозможность считать производные метрики (`reps * weight_kg`, медианы, доли, группировки по периодам) в `records aggregate` без выгрузки сотен записей в окно LLM (`P1-11` в [`11-known-issues.md`](../state/11-known-issues.md));
   - ручное перевычисление SHA-256 и построчный ре-анкоринг `derived_from` ([BUG-011](../../demo/bugs/bug-011-dreyf-derived-from-pri-smene-statusa-tela-ishodnika-trebuet-ruchnogo-re-ankoringa.md));
   - непрозрачность операторов фильтрации `records query` без чтения исходников ([BUG-016](../../demo/bugs/bug-016-filtry-records-query-ne-dokumentirovany-v-spravkah.md)).
3. **Главная инженерная рекомендация — НЕ заменять CLI целиком, а закрепить трёхрежимную архитектуру поверх единого application-слоя:**
   - **Режим 1 — Прямая правка файлов (`Write` / `Edit`) + `todoc sync`:** для написания и редактирования содержательных Markdown-документов (оставить без изменений — уже оптимален).
   - **Режим 2 — Простой CLI (`todoc <cmd>`):** для одиночных команд (`N <= 2`), проверок качества (`validate`, `check`, `doctor`), управления индексом/историей и **всех деструктивных или требующих подтверждения операций** (`revert`, `change apply/revert`, `history gc`).
   - **Режим 3 — Публичный Python Agent API (`todoc.sdk` / `DatasetSession`) под стандарт PTC:** для многошагового чтения, поиска, графовых обходов, производной аналитики, кросс-резолва `id` и пакетной подготовки review-first планов (`BatchWritePlan`) в памяти без временных файлов.

---

## 1. Эмпирическая диагностика `todoc`: где простой CLI теряет токены и скорость

### 1.1. Живой замер на корпусе `demo/` (проверено кодом 2026-11-28)

В текущем состоянии [`src/todoc/__init__.py`](../../src/todoc/__init__.py) экспортирует только `__version__ = "0.1.0"` — публичного Python SDK у пакета нет, и любой агент (включая локального coding-агента с доступом к Python) вынужден либо вызывать `todoc` через порождение subprocess на каждый шаг, либо импортировать внутренние неконтрактные модули.

На копии актуального датасета `demo/` (`86` папок, `465` документов, `205` записей, `169` связей, `752` упоминания `mentions`, `31` `doc_type`, `25` `entity_type`, `18` `relation_type`, `24` `dir_type`) с прогретым индексом проведён замер реалистичного 8-шагового сценария триажа:
1. `todoc types list`
2. `todoc records query --query-file .todoc/queries/bugs-agent-friction.json`
3. `todoc records list --type task`
4. `todoc docs search --query "derived_from якорь stale"`
5. `todoc relations graph --from project:todoc-core --depth 2`
6. `todoc docs read --id doc:note-token-economy`
7. `todoc docs read --id doc:note-agent-contract`
8. `todoc stale`

| Метрика | Цепочка из 8 вызовов простого CLI (subprocess) | 1 ход через Python API / PTC (внутри одного процесса) | Разница |
|---|---|---|---|
| Число шагов инференса LLM | **8 ходов** (+ доп. ход при ошибке угадывания `id`) | **1 ход** (скрипт собирает и фильтрует данные сам) | **-87,5% раунд-трипов LLM** |
| Локальное время исполнения (без учёта LLM) | **3 747,6 мс** (`162–182 мс` на быстрые команды, `1 387,5 мс` на `docs search`, `1 307,5 мс` на `stale`) | **1 191,5 мс** (одна инициализация контекста и один проход) | **ускорение 3,1× локально** (~10–20× end-to-end с учётом LLM) |
| Объём JSON, попадающий в контекст агента | **43 006 символов** (~10 750–12 000 токенов) | **1 676 символов** (~420 токенов, только целевая сводка) | **-96,1% токенов выдачи** |
| Временные файлы на диске | Требуются для каждого ad-hoc `query` / `create` / `edit` | **0 временных файлов** (передача Python `dict`/`list` в памяти) | Полное устранение риска `P1-9` |

Показательная деталь: при подготовке самого замера вызов `todoc docs read --id doc:notes/token-economy.md` завершился с кодом `3` (`docs.not_found`), поскольку фактический `document_id` файла `notes/token-economy.md` в индексе — `doc:note-token-economy`. В режиме простого CLI это стоит агенту лишнего хода и ручного поиска `id` (ровно механизм [BUG-013](../../demo/bugs/bug-013-neodnorodnye-id-i-output-kontrakty-rezolv-identifikatora-trebuet-ruchnogo-grep.md)).

### 1.2. Пять структурных узких мест текущего CLI-only подхода

1. **Налог на повторную инициализацию и сериализацию в каждом процессе.** Каждый запуск `todoc` заново поднимает интерпретатор Python, импортирует `click`/`jsonschema`/`markdown-it-py`, создаёт `DatasetContext` ([`src/todoc/service.py`](../../src/todoc/service.py)), читает JSON-правила и `TypeRegistry` (98 описателей типов в `demo/`), вычисляет `corpus_digest` по `stats.json` и десериализует `CURRENT.json` + 6 файлов снимка (`folders.json`, `documents.json`, `records.json`, `relations.json`, `diagnostics.json`, `mentions.json`). Даже на тёплом индексе нижняя планка одного вызова составляет **150–185 мс**.
2. **Накопление промежуточных конвертов в контексте LLM (`O(N)` токенов).** Один вызов `records query` по багам фрикции в `demo/` возвращает **17 887 символов** JSON, а один `docs search` — **11 017 символов**. Если агенту нужно пересечь результаты `records query` с графом связей для 15 записей, в классическом CLI / JSON tool-calling все 15 полных ответов навсегда ложатся в историю сообщений диалога и повторно оплачиваются на каждом следующем шаге рассуждения.
3. **Файловые посредники (`--input-file`, `--query-file`, `--patch-file`) и ловушка `P1-9` + `DESIGN-Q02`.** Команды `records create`, `records query` и `docs edit` не принимают структуры данных напрямую из кода — они требуют путь к JSON-файлу. Если агент случайно создаст такой файл внутри `DATA_ROOT`, срабатывает открытая проблема `P1-9` из [`docs/state/11-known-issues.md`](../state/11-known-issues.md): любой `.json` с полем `record_id` индексируется как боевая запись и блокирует `records create` ошибкой `record.duplicate_id`. А для пачки из 11 новых записей конвенция `--preview` → `--apply` в CLI превращается в **11 временных файлов + 22 запуска процесса** ([DESIGN-Q02](../../demo/bugs/design-q02-review-first-dvoynoy-vyzov-stoimost-dlya-agenta-protiv-kontrolya.md)).
4. **Конституционный потолок декларативных агрегаций (`P1-11`).** В [`src/todoc/application/query.py`](../../src/todoc/application/query.py) функция `aggregate_records()` намеренно вычисляет только `sum(<metric_field>)` с проверкой единиц измерения по группам (`group_units`), потому что по принципам `P3`, `P5`, `P10` ядро не исполняет формул из `DATA_ROOT`. Как зафиксировано в `11-known-issues.md` (`P1-11`), *«производная метрика остаётся сохранённым полем записи или арифметикой вызывающей стороны»*. Без PTC «арифметика вызывающей стороны» означает счёт в уме языковой модели по сырой выдаче CLI; с PTC агент выполняет точную Python-арифметику поверх типизированной выборки в песочнице, не нарушая ни `P3`, ни `P10`.
5. **Раздувание схем при прямом отображении 64 команд в tool-calling.** Если экспортировать все 64 листовые команды CLI как отдельные JSON Schema инструменты (например, в классическом MCP), только описание их параметров займёт **15 000–22 000 токенов** системного промпта и снизит точность выбора инструмента. В стандарте PTC весь фасад чтения, запросов и планирования `todoc.sdk` описывается типизированным `.pyi`-стабом объёмом **~1 000–1 300 токенов** (в 12–18 раз компактнее), одновременно типизируя не только входы, но и форму возвращаемых словарей (`TypedDict`).

---

## 2. Граница разумности: три режима работы агента и ревизия всех 64 команд

Переводить на Python API / PTC «всё подряд» — антипаттерн. Индустриальные бенчмарки Programmatic Tool Calling (Anthropic Advanced Tool Use, градированный бенчмарк Pydantic 2026 на 5 276 прогонах, исследование Patel et al. *The Bitter Lesson of Tool Calling*) и собственные замеры `todoc` показывают чёткую точку кроссовера:

- **При `N = 1..2` простых вызовах** генерация Python-обёртки даёт **+20..38% накладных расходов** по токенам по сравнению с прямым вызовом одной команды.
- **При `N >= 3..5` связанных шагах**, фильтрации/свёртке массивов, веерном обходе (`fan-out >= 10`) или пакетной валидации PTC даёт **кратный выигрыш** по стоимости (-37%..-81%), времени (-50% и более) и надёжности перечисления без пропуска элементов.
- **При редактировании прозы Markdown** генерация строк через Python-код или построчные патчи `docs edit` проигрывает нативным файловым инструментам харнеса (`Edit` / `Write`) в связке с `todoc sync` ([`AGENTS.md`](../../AGENTS.md), [`src/todoc/application/sync.py`](../../src/todoc/application/sync.py)).
- **При деструктивных операциях с историей и ревизиями** вызов внутри авто-повторяемого PTC-скрипта опасен: если скрипт упадёт на строке 12 после мутации на строке 4, повторный прогон скрипта моделью продублирует побочный эффект (*Rerun Write Duplication Hazard*).

### 2.1. Матрица выбора интерфейса для агента

| Сценарий агента | Рекомендуемый интерфейс | Почему это оптимум | Что НЕ использовать |
|---|---|---|---|
| Написание и правка статей, планов, заметок, ADR, баг-репортов (`.md`) | **Нативные `Write` / `Edit` харнеса + `todoc sync <paths>`** | Нативный diff, защита от ручной правки витрин (`docs.derived_edited_directly`), авто-бамп `updated`, запись в историю и проверка за один шаг | Построчный `docs edit` или сборку больших `.md` конкатенацией в Python |
| Одиночная проверка, статус, CI-гейт, одиночный `explain-path`, администрирование | **Простой CLI (`todoc validate --all`, `todoc status`, `todoc sync`)** | Нулевой оверхед на генерацию скрипта, стабильные коды выхода `0..6`, готовый JSON-конверт и `guidance` | Обёртку в Python-скрипт ради одного вызова |
| Откаты истории, сборка мусора, применение/откат многофайловых `change` | **Только прямой CLI (`direct`) с контролем человека/оркестратора** | Исключает двойное применение при ретрае упавшего PTC-скрипта | Вызов внутри автономной PTC-песочницы |
| Триаж, поиск + чтение секций, кросс-резолв `id`, фильтрация записей, обход графа/mentions, производные расчёты | **Python Agent API / PTC (`todoc.sdk`, `mode="readonly"`)** | 1 ход LLM вместо 5–20, один скан/загрузка индекса в памяти, экономия до 95% промежуточных токенов, детерминированная математика Python | Серию subprocess-вызовов CLI с ручным `jq`/`grep` и чтением полных выдач глазами модели |
| Массовое создание/обновление типизированных JSON-записей или пакетный ре-анкоринг `derived_from` | **Двухфазный SDK + CLI/Direct Gate (`ds.batch_plan()` в PTC → ревью → `apply_batch`)** | Нет временных файлов в `/tmp` (нет риска `P1-9`), проверка всех схем и перекрёстных связей за 1 проход, сохранение `P6` review-first и 1 пересборка индекса вместо `N` | Цикл из `2 × N` вызовов `todoc records create --preview/--apply` по одному файлу |

### 2.2. Полная классификация всех 64 листовых команд `todoc` (Tier A – Tier D)

Ниже все 64 листовые команды из [`src/todoc/cli.py`](../../src/todoc/cli.py) распределены по четырём уровням целесообразности перевода в Python Agent API / PTC:

- **Tier A — Ядро PTC Read/Query SDK (`pure=True`, высокий приоритет):** операции чтения, поиска, графа, аналитики и диагностики. Полностью свободны от побочных эффектов на диске, безопасны для параллельного (`asyncio.gather`) и спекулятивного вызова внутри одного `DatasetSession`.
- **Tier B — Plan-First SDK Mutations (средний/высокий приоритет с разделением `plan` и `apply`):** операции подготовки и валидации изменений. Внутри PTC-песочницы открываются методы построения плана (`plan_*`, без записи на диск), а фиксация (`apply_*`) защищается `expected_hash` + `idempotency_key` либо выносится на прямой (`direct`) вызов оркестратора.
- **Tier C — Оставить за простым CLI и связкой `Edit`/`Write` + `todoc sync`:** операции, где subprocess CLI или прямая работа с файлом уже оптимальны и перенос в PTC не даёт экономии токенов.
- **Tier D — Строго вне автономной PTC-песочницы (`direct`-only / HITL):** деструктивные, инфраструктурные и транзакционные операции жизненного цикла истории/бандлов.

| Группа CLI | Листовые команды (всего 64) | Уровень | Целевой метод в `todoc.sdk` (если разумно) | Инженерное обоснование |
|---|---|---|---|---|
| **Поиск и чтение документов** | `docs search`, `docs read`, `docs suggest`, `docs links`, `docs tree` (5) | **Tier A** | `ds.docs.search()`, `ds.docs.read()`, `ds.docs.suggest_dir()`, `ds.docs.links()`, `ds.docs.tree()`, `ds.resolve()` | Главный источник экономии токенов: агент в одном скрипте ищет хиты, резолвит `id`↔`path`↔`record_id`, вырезает только нужные секции/JSON Pointer/CSV-строки и возвращает сжатую выжимку. |
| **Запросы и аналитика записей** | `records list`, `records query`, `records read`, `records aggregate` (4) | **Tier A** | `ds.records.query()`, `ds.records.get()`, `ds.records.aggregate()` | Убирает обязательный `--query-file`, открывает фильтрацию словарём или Python-выражением, закрывает `BUG-016` через `.pyi`-типы и позволяет считать любые производные метрики (`P1-11`) в Python. |
| **Граф и дерево связей** | `relations graph`, `relations tree` (2) | **Tier A** | `ds.relations.neighbors()`, `ds.relations.tree()` | Веерный обход графа по списку сущностей (например, для 20 задач или правил) в памяти занимает `<5 мс` вместо 20 запусков CLI. |
| **Потоки и витрины (чтение)** | `docs flow walk` (1) | **Tier A** | `ds.flows.walk()` | Позволяет программно проверить достижимость состояний и все ветки переходов конечного автомата в одном тесте/скрипте агента. |
| **Свежесть и контекст** | `stale`, `context`, `explain-path` (3) | **Tier A** | `ds.staleness.inspect()`, `ds.context.pack()`, `ds.explain_path()` | `staleness.inspect()` должен сразу отдавать и старый, и вычисленный актуальный якорь (`path#frag@sha256:...`), полностью устраняя внешний подсчёт хешей из `BUG-011`. |
| **Интроспекция типов и схем** | `types list`, `types show`, `types prompt`, `types guide` (4) | **Tier A** | `ds.types.list()`, `ds.types.get()`, `ds.types.prompt()` (`types guide` с `--out` — Tier C) | Программное получение JSON Schema, `allowed_statuses`, `required_sections` и `metric_fields` перед пакетной сборкой записей без лишнего раунд-трипа. |
| **Чтение скилов и стейта** | `skills tree`, `skills read`, `state get`, `state list` (4) | **Tier A** | `ds.skills.list()`, `ds.skills.read()`, `ds.state.get()`, `ds.state.list()` | Быстрая навигация по vault скилов и текущему проекту сессии (`context.current_project`) внутри одного bootstrap-скрипта. |
| **Чтение истории и изменений** | `log`, `show`, `diff`, `blame`, `timeline`, `change list`, `change show`, `change validate`, `change verify` (9) | **Tier A** | `ds.history.log()`, `ds.history.show()`, `ds.history.diff()`, `ds.history.blame()`, `ds.history.timeline()`, `ds.changes.inspect()` | Агент может за один ход сопоставить серию ревизий, найти автора/ревизию поломки ребра и собрать аналитический дифф без выгрузки десятков сырых патчей в промпт. |
| **Валидация (программная vs гейт)** | `validate`, `check`, `check-config` (3) | **Tier A / C** | `ds.validate()` (для фильтрации/группировки находок в больших базах — `P1-15`), плюс **CLI** как финальный гейт | На большой базе плоский ответ `todoc validate --all` перегружает контекст (`P1-15`); в Python агент группирует диагностики по `code` и папке. Как финальный CI/сессионный гейт остаётся простой `todoc validate`. |
| **Создание и точечные мутации записей** | `records create`, `records status`, `records undo-relation` (3) | **Tier B** | `ds.records.plan_create()`, `ds.records.plan_status()`, `ds.records.plan_undo_relation()`, `ds.batch_plan()` + `ds.apply_plan()` | Ключевой выигрыш на записи: сборка 5–50 JSON-записей из Python-словарей без `/tmp/*.json` (`P1-9`), сквозная проверка JSON Schema и перекрёстных `relations` внутри пачки, единый `BatchWritePlan` (`DESIGN-Q02`). |
| **Структурные мутации документов и экспортов** | `docs new`, `docs status`, `docs edit`, `fix`, `docs flow render`, `interop export`, `state set`, `state unset` (8) | **Tier B** | `ds.docs.plan_new()`, `ds.docs.plan_status()`, `ds.docs.plan_fix_links()`, `ds.staleness.plan_reanchor()`, `ds.interop.export()`, `ds.flows.render()`, `ds.state.set()` | Разумно использовать в Python API **только для структурных/шаблонных операций**: пакетная починка битых ссылок (`fix`), пакетный ре-анкоринг `derived_from`, смена `status`, пересборка derived-витрин (`flow render`, `interop export`). Содержательный текст `.md` пишется через `Edit`/`Write` + `todoc sync`. |
| **Финализация прямых правок, обзор и индекс** | `sync`, `status`, `doctor`, `scan`, `index status`, `index rebuild` (6) | **Tier C** | Вызывать как простой CLI (внутри `sdk` доступна служебная `ds.sync()` для тестов/веба) | Команды вызываются ровно 1 раз в начале или в конце работы (`todoc status`, `todoc sync <paths>`); Python-обёртка для агента здесь лишь тратит лишние токены. |
| **Инициализация, мутации истории, бандлы `change`, импорт скилов** | `init`, `revert`, `tag`, `history gc`, `history adopt`, `history export`, `change open`, `change apply`, `change archive`, `change revert`, `skills attach`, `skills import` (12) | **Tier D** | **Не включать в агентский PTC-стаб** (оставить только в прямом CLI и внутреннем админ-слое) | Редкие, инфраструктурные или необратимые операции с историей/файловым деревом. Их изоляция вне PTC гарантирует отсутствие каскадных откатов и дублей ревизий при перезапуске агентского скрипта. |

**Итог ревизии 64 команд:**
- **35 команд (Tier A)** образуют компактное, полностью безопасное (read-only) ядро `todoc.sdk` для PTC-скриптов (при консолидации близких команд — всего **~18 методов** в 6 пространствах имён).
- **11 команд (Tier B)** входят в `todoc.sdk` через двухфазный контракт `plan_*` → `apply_plan` (прежде всего ради пакетного создания записей, ре-анкоринга и автофикса ссылок без временных файлов).
- **6 команд (Tier C)** остаются основным одношаговым CLI-инструментом агента и CI.
- **12 команд (Tier D)** намеренно исключаются из PTC-песочницы и остаются исключительно прямыми (`direct`) командами CLI.

---

## 3. Шесть архитектурных блокеров в текущем коде `src/todoc/`

Перед тем как открывать агенту публичный пакет `todoc.sdk`, необходимо устранить шесть конкретных ограничений текущей реализации. Все шесть напрямую согласуются с этапами `З0-S`, `Э2`, `Э3`, `Э4` и `Э9` мастер-плана [`docs/plan/todoc-master-refactoring-plan.md`](../plan/todoc-master-refactoring-plan.md):

### Блокер 1. Скрытая запись на диск внутри «читающего» `DatasetContext.ensure_index()`
- **Где в коде:** [`src/todoc/service.py`](../../src/todoc/service.py) (строки 194–206).
- **Суть проблемы:** метод `ensure_index()`, вызываемый почти каждой командой чтения, при расхождении `corpus_digest` перезаписывает `.todoc/index/current/*`, `.todoc/index/CURRENT.json`, `.todoc/index/stats.json` и вызывает `observe_external_changes()`, который дописывает событие `external.change` в `.todoc/history/journal.jsonl` и сохраняет сжатые блобы в `.todoc/history/objects/`.
- **Почему ломает PTC:** в PTC-рантаймах читающие вызовы помечаются как чистые (`pure=True`), могут исполняться параллельно (`asyncio.gather`), спекулятивно или из read-only песочницы/MCP-транспорта (правило `M14` в [`docs/plan/mcp-adapter.after.md`](../plan/mcp-adapter.after.md)). Скрытая запись превращает параллельное чтение в гонку на `CURRENT.json` и `journal.jsonl`.
- **Решение:** разделить режимы в `DatasetSession(root, mode="readonly" | "readwrite")`. В `mode="readonly"` (по умолчанию!) при актуальном `CURRENT.json` снимок читается с диска, а при грязном корпусе или отсутствии индекса собирается **эфемерный снимок в памяти процесса** без единой записи в `.todoc/index/` и `.todoc/history/`.

### Блокер 2. Проекционная логика чтения и статусов заперта внутри `src/todoc/cli.py`
- **Где в коде:** [`src/todoc/cli.py`](../../src/todoc/cli.py):
  - `docs_read` (строки 1341–1440, 100 строк): разбор `#fragment` в `--id`, нарезка Markdown-секции с учётом уровня заголовков, байтового `--budget` и `SECTION_MAX_LINES`, `--line-range`, JSON Pointer (`resolve_pointer`), CSV-фильтрация `--where` + `--columns` + `--rows`;
  - `docs_status` (строки 1664–1719) и `records_status` (строки 1870–1915): проверка `allowed_statuses` и `status.enum` JSON Schema;
  - `records_list` (строки 1842–1869): пост-фильтры `--until` и `--relation` реализованы прямо в Click-команде и **отсутствуют** в `application/query.py:query_records()`;
  - `docs_links` (строки 1472–1508), `docs_tree` (строки 1519–1564), `docs_flow_render` (строки 1577–1630), `interop_export` (строки 2010–2052), `explain_path` (строки 1184–1213).
- **Решение:** вынести эти операции в чистые, не зависящие от `click` функции `src/todoc/application/` (этапы `Э2`–`Э4` мастер-плана), чтобы и `cli.py`, и `todoc.sdk`, и будущий MCP/веб вызывали один и тот же код без дублирования семантики (`P11`).

### Блокер 3. Повторный дисковый парсинг всех Markdown-файлов в `search_documents()`
- **Где в коде:** [`src/todoc/application/search.py`](../../src/todoc/application/search.py) (строки 25–41 и 196–201).
- **Суть проблемы:** функция `_document_text()` при каждом вызове `search_documents()` читает с диска и заново прогоняет через `parse_markdown()` все 465 документов корпуса, не обращаясь к `.todoc/cache/parse/` ([`src/todoc/application/registry.py`](../../src/todoc/application/registry.py)), а затем на строке 198 повторно парсит файл каждого найденного хита ради `_breadcrumb()`. На нашем замере по `demo/` именно поэтому один вызов поиска занимает **~1,12 с** даже при прогретом в памяти `DatasetContext`. Если PTC-скрипт выполнит 5 поисковых запросов в цикле, он потратит ~5,6 с на 2 325 повторных парсингов одних и тех же файлов.
- **Решение:** внутри `DatasetSession` держать ленивый in-memory кэш разобранных документов и токенов по ключу `(rel_path, content_hash)`, подхватывающий `.todoc/cache/parse/`. Первый `ds.docs.search()` в сессии уложится в `~120–180 мс`, а 2-й и последующие запросы в том же Python-скрипте — в **`< 5 мс`**.

### Блокер 4. Неоднородность структур данных (`dataclass` vs сырой `dict`) и разрыв пространств `id`
- **Где в коде:** [`src/todoc/domain/models.py`](../../src/todoc/domain/models.py), [`src/todoc/application/search.py`](../../src/todoc/application/search.py), [`src/todoc/application/query.py`](../../src/todoc/application/query.py), [BUG-013](../../demo/bugs/bug-013-neodnorodnye-id-i-output-kontrakty-rezolv-identifikatora-trebuet-ruchnogo-grep.md).
- **Суть проблемы:** `search_documents()` возвращает кортеж `(list[SearchHit], int, bool)`, где `SearchHit` — датакласс с полем `.snippet_text`, тогда как в JSON-выдаче CLI это вложенный словарь `hit["snippet"]["text"]`. В то же время `query_records()` возвращает `(list[dict[str, Any]], int, bool)`, где пользовательские поля лежат внутри `record["data"]`. В режиме PTC модель генерирует весь Python-скрипт **вслепую за один ход** до его запуска: малейшее расхождение между `.attr` и `["key"]` роняет скрипт с `AttributeError`/`KeyError`. Кроме того, один артефакт имеет три ссылки: `rel_path` (`bugs/bug-011-...md`), `document_id` из front matter (`doc:bugs/...`) и `record_id` паспортной записи (`document:bug-011-...` с `source_path`).
- **Решение:**
  1. Все методы `todoc.sdk` возвращают единообразные JSON-сериализуемые словари, строго описанные через `TypedDict` в `.pyi` (единый контейнер страницы `Page[T] = {"items": list[T], "total": int, "truncated": bool, "next_cursor": str | None}`).
  2. Добавить детерминированный резолвер `ds.resolve(identifier_or_path) -> ResolvedRef`, мгновенно связывающий `rel_path`, `document_id` и связанный по `source_path` `record_id` в обоих направлениях.

### Блокер 5. Отсутствие пакетного `BatchWritePlan` и идемпотентности при ретраях скрипта
- **Где в коде:** [`src/todoc/application/write.py`](../../src/todoc/application/write.py) (`create_record_plan`, `apply_write_plan`).
- **Суть проблемы:** сейчас запись работает строго по одному файлу; при создании связанной группы записей (`plan` + 5 `task` с реляцией `belongs_to` друг на друга) валидация поодиночке либо требует строгого топологического порядка и 5 пересборок индекса, либо падает с `relation.dangling_target`. А при сбое PTC-скрипта посреди цикла одиночных `apply` часть файлов уже создана на диске.
- **Решение:** ввести `BatchPlanBuilder` (`ds.batch_plan()`):
  - принимает Python-словари записей и структурные правки в памяти;
  - валидирует JSON Schema и граф отношений **с учётом всех новых `record_id`, добавляемых в этом же батче**;
  - выдаёт детерминированный `BatchWritePlan` с общим `plan_digest` (`sha256:...`) для review-first проверки;
  - применяет пачку атомарно (с откатом при конфликте CAS), пишет одно групповое событие истории с `idempotency_key` и пересобирает индекс **ровно один раз**.

### Блокер 6. Отсутствие файловой блокировки записи (`.todoc/write.lock`)
- **Где в коде:** открытая проблема `P2` в [`docs/state/11-known-issues.md`](../state/11-known-issues.md).
- **Решение:** добавить неблокирующий/таймаутный эксклюзивный лок `.todoc/write.lock` (`fcntl.flock` на POSIX / `msvcrt` на Windows) вокруг `apply_plan`, `sync_files` и `rebuild_index`. Параллельные читающие `DatasetSession(mode="readonly")` лок не берут и работают без ожидания.

---

## 4. Целевой контракт `todoc.sdk` по стандарту PTC

### 4.1. Восемь правил проектирования Python API специально для LLM-агентов

Чтобы модель генерировала безошибочный Python-код с первой попытки и не тратила контекст на лишние поля, `todoc.sdk` должен строиться по восьми правилам стандарта PTC:

1. **Только именованные параметры (`*`) и плоские сигнатуры:** позиционным допускается максимум первый очевидный аргумент (`query` или `ref`); все фильтры и лимиты — keyword-only с `Literal`-типами вместо нетипизированного `str`.
2. **Только JSON-сериализуемые `TypedDict` на выходе:** никаких «живых» внутренних объектов с ленивым I/O или смешанных датаклассов — это даёт 100% совместимость как с обычным CPython, так и с изолированными рантаймами (`pydantic-monty`, Claude PTC, MCP Code Mode).
3. **Управление плотностью выдачи (`detail="concise"` по умолчанию + `fields`):** согласованно с идеей [`demo/ideas/unified-cli-output.md`](../../demo/ideas/unified-cli-output.md), списочные методы по умолчанию возвращают компактную проекцию (идентификаторы, заголовки, статус, локацию и короткий фрагмент), а полные метаданные отдают при `detail="detailed"` или явном списке `fields=("record_id", "status", "severity")`.
4. **Безопасная пагинация и защита от усечения:** каждый списочный метод возвращает `Page[T]` с честным флагом `truncated: bool` (`P7`), а хелпер `ds.collect_all(...)` имеет жёсткий предохранитель `max_items: int = 500`.
5. **Единый кросс-резолвер идентификаторов (`ds.resolve`):** любой метод чтения (`ds.docs.read`, `ds.records.get`, `ds.relations.neighbors`) понимает и `document_id`, и `record_id`, и `rel_path` (при однозначном соответствии).
6. **Самодокументируемые исключения `TodocSDKError` (`P15`):** ошибки валидации и конфликтов поднимают `TodocSDKError(code=..., message=..., fix_hint=..., suggested_fixes=...)`, чей `__str__()` сразу содержит конкретную подсказку из каталога `guidance` (например, список допустимых значений `enum` статуса или точное имя неизвестного поля), без многостраничного внутреннего стектрейса.
7. **Селективная изоляция мутаций (Selective Sandboxing):** внутри автономной PTC-песочницы по умолчанию открывается `mode="readonly"` плюс чистые методы построения плана (`plan_*`), не меняющие диск; выполнение `apply_plan()` требует явного `mode="readwrite"`, проверки `expected_digest` и `idempotency_key`.
8. **Инструктивное ограничение вывода скрипта:** при запуске через tool-рантайм `run_code` stdout ограничивается лимитом `6 000–8 000` символов с диагностикой: *«Вывод усечён: сагрегируйте список в Python (`len`, `Counter`, срез топ-N) и выведите только сводку»*.

### 4.2. Эталонный `.pyi`-контракт `src/todoc/sdk/__init__.pyi`

Ниже приведён рекомендуемый `.pyi`-контракт публичного агентского SDK. Весь интерфейс покрывает 46 из 64 сценариев CLI (все уровни Tier A и Tier B), полностью проверяется статическими анализаторами (`mypy`, `pyright`, `ty`) и занимает **~950 токенов** системного промпта — меньше, чем описание всего 4 команд в формате JSON Schema:

```python
"""Typed Python Agent SDK for todoc (PTC / Code Mode contract)."""

from pathlib import Path
from typing import Any, Generic, Literal, Mapping, Sequence, TypedDict, TypeVar

T = TypeVar("T")
DetailLevel = Literal["concise", "detailed"]
SessionMode = Literal["readonly", "readwrite"]
RelationDirection = Literal["out", "in", "both"]
ExportTarget = Literal["asl", "dmn", "rasa"]

class TodocSDKError(Exception):
    code: str          # e.g. "records.status_not_allowed", "write.hash_mismatch"
    exit_code: int     # 2..6 matching CLI contract
    path: str | None
    fix_hint: str      # actionable self-correction hint (Principle P15)
    suggested_fixes: list[dict[str, Any]]

class Page(TypedDict, Generic[T]):
    items: list[T]
    total: int
    truncated: bool
    next_cursor: str | None

class ResolvedRef(TypedDict):
    path: str
    document_id: str | None
    record_id: str | None
    kind: Literal["document", "record", "both"]
    doc_type: str | None
    entity_type: str | None
    hash: str

class SearchHitItem(TypedDict):
    document_id: str
    record_id: str | None
    path: str
    title: str
    heading_path: list[str]
    rank: int
    matched_terms: list[str]
    line_start: int
    line_end: int
    snippet: str
    snippet_truncated: bool

class DocProjection(TypedDict, total=False):
    document_id: str
    record_id: str | None
    path: str
    format: Literal["markdown", "json", "csv"]
    doc_type: str
    hash: str
    title: str
    tags: list[str] | None
    updated: str | None
    headings: list[dict[str, Any]]
    section: str
    line_start: int
    line_end: int
    truncated: bool
    text: str
    value: Any
    columns: list[str]
    rows: list[dict[str, str]]
    total_rows: int
    matched_rows: int

class FilterOps(TypedDict, total=False):
    # Explicit operator contract (closes BUG-016):
    # exact match passes raw value; operator dict uses keys below.
    # Example: {"status": {"$in": ["open", "in_progress"]}, "priority": {"$gte": 2}}
    ...

class RecordItem(TypedDict):
    record_id: str
    entity_type: str
    path: str
    hash: str
    data: dict[str, Any]

class GraphEdge(TypedDict, total=False):
    type_id: str
    direction: Literal["out", "in"]
    source_id: str
    target_id: str
    via: Literal["relation", "mention"]
    fragment: str

class StaleItem(TypedDict):
    owner_path: str
    owner_id: str
    code: str
    expected_anchor: str
    actual_anchor: str | None  # ready-to-apply replacement anchor (closes BUG-011)
    acknowledged: bool

class PlanItemSummary(TypedDict):
    op: Literal["record.create", "record.status", "doc.new", "doc.status", "doc.fix", "doc.reanchor"]
    target_path: str
    expected_hash: str | None
    new_hash: str
    validations: list[str]

class BatchWritePlanDict(TypedDict):
    plan_id: str
    dataset_id: str
    plan_digest: str
    items: list[PlanItemSummary]
    diagnostics: list[dict[str, Any]]

class DocsAPI:
    def search(
        self,
        query: str,
        *,
        doc_type: str | None = None,
        tag: str | None = None,
        within: str | None = None,
        limit: int = 10,
        cursor: str | None = None,
        budget_bytes: int | None = None,
    ) -> Page[SearchHitItem]: ...
    def read(
        self,
        ref: str,
        *,
        section: str | None = None,
        line_range: tuple[int, int] | None = None,
        pointer: str | None = None,
        columns: Sequence[str] | None = None,
        where: Mapping[str, str] | None = None,
        max_rows: int | None = None,
        budget_bytes: int | None = 4000,
    ) -> DocProjection: ...
    def suggest_dir(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]: ...
    def links(self, *, broken_only: bool = False, within: str | None = None, limit: int = 100) -> Page[dict[str, Any]]: ...
    def tree(self, *, within: str | None = None, depth: int | None = None) -> dict[str, Any]: ...

class RecordsAPI:
    def query(
        self,
        *,
        entity_type: str | None = None,
        filters: Mapping[str, Any] | None = None,
        since: str | None = None,
        until: str | None = None,
        relation: tuple[str, str] | None = None,
        as_of: str | None = None,
        fields: Sequence[str] | None = None,
        detail: DetailLevel = "concise",
        limit: int = 200,
        cursor: str | None = None,
    ) -> Page[RecordItem]: ...
    def get(self, ref: str) -> RecordItem: ...
    def aggregate(
        self,
        entity_type: str,
        metric_field: str,
        *,
        group_by: str | None = None,
        filters: Mapping[str, Any] | None = None,
        as_of: str | None = None,
    ) -> dict[str, Any]: ...

class RelationsAPI:
    def neighbors(
        self,
        ref: str,
        *,
        type_id: str | None = None,
        direction: RelationDirection = "both",
        depth: int = 1,
        include_mentions: bool = True,
        limit: int = 100,
    ) -> list[GraphEdge]: ...
    def tree(
        self,
        ref: str,
        *,
        type_id: str | None = None,
        depth: int = 2,
        include_mentions: bool = True,
        limit: int = 100,
    ) -> dict[str, Any]: ...

class StalenessAPI:
    def inspect(self, *, within: str | None = None) -> list[StaleItem]: ...

class TypesAPI:
    def list(self, *, kind: Literal["dir_type", "doc_type", "entity_type", "relation_type"] | None = None) -> list[dict[str, Any]]: ...
    def get(self, type_id: str) -> dict[str, Any]: ...
    def prompt(self, type_id: str, *, op: Literal["read", "create", "edit", "delete"] = "create") -> str: ...

class BatchPlanBuilder:
    def create_record(self, entity_type: str, data: Mapping[str, Any]) -> "BatchPlanBuilder": ...
    def set_record_status(self, ref: str, status: str) -> "BatchPlanBuilder": ...
    def new_doc(self, title: str, *, doc_type: str | None = None, dir_path: str = "inbox", rel_path: str | None = None) -> "BatchPlanBuilder": ...
    def set_doc_status(self, ref: str, status: str) -> "BatchPlanBuilder": ...
    def reanchor_stale(self, owner_refs: Sequence[str]) -> "BatchPlanBuilder": ...
    def preview(self) -> BatchWritePlanDict: ...

class DatasetSession:
    dataset_id: str
    root: Path
    mode: SessionMode
    docs: DocsAPI
    records: RecordsAPI
    relations: RelationsAPI
    staleness: StalenessAPI
    types: TypesAPI

    def resolve(self, ref: str) -> ResolvedRef: ...
    def explain_path(self, rel_path: str) -> dict[str, Any]: ...
    def validate(self, *, within: str | None = None, severity: Literal["error", "warning"] | None = None) -> list[dict[str, Any]]: ...
    def batch_plan(self) -> BatchPlanBuilder: ...
    def apply_plan(
        self,
        plan: BatchWritePlanDict,
        *,
        expected_digest: str,
        idempotency_key: str,
    ) -> dict[str, Any]: ...
    def __enter__(self) -> "DatasetSession": ...
    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None: ...

def open_session(
    root: str | Path = ".",
    *,
    mode: SessionMode = "readonly",
) -> DatasetSession: ...
```

---

## 5. Примеры «Было (простой CLI) → Стало (`todoc.sdk` / PTC)» на реальных задачах `todoc`

### Пример A. Триаж открытых фрикций + граф + прицельное чтение секций (8+ вызовов CLI → 1 ход)

**Было (простой CLI):** агент запускает `records query --query-file ...`, получает 18 КБ JSON в контекст, руками ищет `source_path`, запускает `grep` по `demo/bugs/*.md` из-за `BUG-013`, делает серию `docs read --section "Предложение по исправлению"` и `relations graph` на каждый баг — сжигая 8–12 ходов LLM и ~12 000 токенов.

**Стало (один PTC-вызов на `todoc.sdk`):**

```python
import json
from todoc.sdk import open_session

with open_session("demo", mode="readonly") as ds:
    bugs = ds.records.query(
        entity_type="document",
        filters={
            "doc_subtype": "bug-report",
            "status": "open",
            "agent_impact": {"$in": [["friction"], ["friction", "token_overrun"]]},
        },
    )["items"]

    report = []
    for rec in bugs:
        ref = ds.resolve(rec["data"]["source_path"])
        fix_sec = ds.docs.read(ref["document_id"], section="Предложение по исправлению", budget_bytes=800)
        edges = ds.relations.neighbors(rec["record_id"], depth=1, include_mentions=True)
        report.append({
            "bug_id": rec["data"].get("bug_id"),
            "tokens_extra": rec["data"].get("tokens_extra_est", 0),
            "edges_count": len(edges),
            "fix_summary": fix_sec.get("text", "").splitlines()[:4],
        })

    report.sort(key=lambda x: -x["tokens_extra"])
    print(json.dumps({"total_open_friction": len(report), "top_bugs": report[:5]}, ensure_ascii=False, indent=2))
```

В контекст модели возвращается ровно 25 строк отранжированной выжимки, ни один байт на диске не изменён, временные файлы не создавались.

### Пример B. Производная аналитика метрик с проверкой единиц (`P1-11`)

Ядро `todoc` по `P3`/`P5`/`P10` не вычисляет выражения в `type.json`. В связке с `todoc.sdk` агент берёт описание метрики и единицы через `ds.types.get()`, отбирает записи за нужный срез времени `as_of` и считает любые производные показатели (сумму произведений, медиану, помесячную динамику) детерминированным кодом Python:

```python
from collections import defaultdict
from statistics import median
from todoc.sdk import open_session

with open_session("demo", mode="readonly") as ds:
    bugs = ds.records.query(entity_type="document", filters={"doc_subtype": "bug-report"})["items"]
    by_component: dict[str, list[int]] = defaultdict(list)
    for b in bugs:
        est = b["data"].get("tokens_extra_est")
        if isinstance(est, int):
            by_component[b["data"].get("component", "unknown")].append(est)

    stats = {
        comp: {"count": len(vals), "sum_tokens": sum(vals), "median_tokens": median(vals)}
        for comp, vals in sorted(by_component.items())
    }
    print(stats)
```

### Пример C. Пакетное создание связанных записей без `/tmp`-файлов (`P1-9` + `DESIGN-Q02`)

Вместо 10 временных JSON-файлов и 20 запусков `todoc records create --preview/--apply`:

```python
from todoc.sdk import open_session

# Шаг 1 (безопасно внутри PTC): сборка и полная валидация пачки в памяти
with open_session("demo", mode="readonly") as ds:
    plan = (
        ds.batch_plan()
        .create_record("task", {
            "record_id": "task:sdk-readonly-session",
            "title": "Выделить DatasetSession(mode='readonly')",
            "status": "planned",
            "relations": [{"type_id": "belongs_to", "target": {"id": "project:todoc-core"}}],
        })
        .create_record("task", {
            "record_id": "task:sdk-batch-write-plan",
            "title": "Добавить BatchPlanBuilder без временных файлов",
            "status": "planned",
            "relations": [
                {"type_id": "belongs_to", "target": {"id": "project:todoc-core"}},
                {"type_id": "depends_on", "target": {"id": "task:sdk-readonly-session"}},  # валидируется внутри пачки!
            ],
        })
        .preview()
    )
    print(plan["plan_id"], plan["plan_digest"], len(plan["items"]))

# Шаг 2 (после ревью плана или через отдельный подтверждённый вызов):
with open_session("demo", mode="readwrite") as ds:
    result = ds.apply_plan(
        plan,
        expected_digest=plan["plan_digest"],
        idempotency_key="create-sdk-tasks-v1",
    )
```

### Пример D. Пакетный ре-анкоринг `derived_from` после правки исходника ([BUG-011](../../demo/bugs/bug-011-dreyf-derived-from-pri-smene-statusa-tela-ishodnika-trebuet-ruchnogo-re-ankoringa.md))

```python
from todoc.sdk import open_session

with open_session("demo", mode="readonly") as ds:
    stale = ds.staleness.inspect()
    owners = sorted({item["owner_path"] for item in stale if item["actual_anchor"] is not None})
    reanchor_plan = ds.batch_plan().reanchor_stale(owners).preview()
    print(reanchor_plan)
```

---

## 6. Три архитектуры интеграции `todoc.sdk` с агентскими рантаймами

Публичный `todoc.sdk` проектируется один раз и обслуживает сразу три класса агентских сред без дублирования бизнес-логики (`P11`):

### 6.1. Локальные coding-агенты с Bash и Python (Claude Code, Codex, Cursor, Arena)
- **Как работает:** агент уже работает в окружении, где установлен пакет `todoc`. Для одиночных команд и `todoc sync` он вызывает CLI, а когда видит задачу из 3+ шагов чтения/анализа/пакетной подготовки записей — запускает одноразовый Python-скрипт против `from todoc.sdk import open_session`.
- **Изменение в [`SKILL.md`](../../SKILL.md):** добавить короткое правило маршрутизации на 8 строк (без раздувания входного скила — принцип `P15`):
  - *Проза `.md` → нативные `Write`/`Edit` + `todoc sync <paths>`.*
  - *Одиночная команда, гейт `validate`, `revert`, `change` → простой CLI `todoc ...`.*
  - *Сложная выборка (3+ шагов), кросс-резолв `id`, граф, кастомный расчёт или пачка записей → один Python-скрипт с `todoc.sdk.open_session(..., mode="readonly")`; контракт смотреть в `src/todoc/sdk/__init__.pyi`.*

### 6.2. Встраиваемый рантайм для веб-интерфейса (Этап 9 конституции) и облачных агентов на `pydantic-monty`
- **Почему именно `pydantic-monty`:** написанный на Rust интерпретатор безопасного подмножества Python (`pydantic-monty`) стартует за доли миллисекунды, по умолчанию **не имеет доступа к файловой системе, сети и переменным окружения хоста**, поддерживает `asyncio.gather` и встроенную статическую проверку сгенерированного моделью кода через `ty` прямо по `.pyi`-стабу `todoc.sdk` до исполнения.
- **Как интегрируется с `todoc`:** хост-процесс держит `DatasetSession(root, mode="readonly")` за пределами песочницы и пробрасывает внутрь `Monty` только методы чтения и `batch_plan().preview()` как внешние функции. Агент внутри песочницы физически не может ни прочитать файлы вне `DATA_ROOT` (`P10`), ни обойти `WritePlan` (`P6`), ни задвоить мутацию при ретрае скрипта. Подтверждённый человеком или оркестратором `BatchWritePlanDict` применяется снаружи через `apply_plan()`.

### 6.3. Развитие плана MCP-адаптера ([`docs/plan/mcp-adapter.after.md`](../plan/mcp-adapter.after.md)) в сторону MCP Code Mode
- В [`docs/plan/mcp-adapter.after.md`](../plan/mcp-adapter.after.md) уже зафиксированы правила тонкого транспорта (`M1`–`M26`), read-only профиль v1 (`M14`) и отказ от наивной автогенерации MCP из всех команд CLI (`M2`, а также анализ контекстной экономии в [`docs/research/mcp-cli-agents.md`](mcp-cli-agents.md) §8.2–8.3).
- При появлении `todoc.sdk` MCP-адаптер v1.5 / Code Mode может предоставлять **всего 3 компактных MCP-инструмента** вместо десятков разрозненных схем:
  1. `todoc_api_stub(domain?: str)` — отдаёт `.pyi`-контракт нужного раздела `DatasetSession` (Progressive Disclosure);
  2. `todoc_run_readonly(code: str, root?: str)` — исполняет аналитический/поисковый скрипт в `pydantic-monty` поверх `DatasetSession(mode="readonly")` с лимитами времени, памяти и размера ответа;
  3. `todoc_apply_batch_plan(plan: BatchWritePlanDict, expected_digest: str, idempotency_key: str)` — отдельный прямой (`direct`) инструмент записи для opt-in режима `--allow-write` (`M15`–`M16`), который можно защитить подтверждением пользователя в клиенте MCP.
- При работе через Claude API с нативным Programmatic Tool Calling (`code_execution_20260120` / `code_execution_20260521`) читающим инструментам выставляется `allowed_callers: ["direct", "code_execution_20260120"]` (с отказом от несовместимых `strict: true` и рекурсивных `$ref`), а мутирующим инструментам Tier B/D — строго `allowed_callers: ["direct"]`.

---

## 7. Поэтапная дорожная карта внедрения (синхронизация с мастер-планом рефакторинга)

Чтобы не создавать параллельную ветку работ, внедрение `todoc.sdk` и стандарта PTC органично встраивается в уже утверждённую последовательность этапов [`docs/plan/todoc-master-refactoring-plan.md`](../plan/todoc-master-refactoring-plan.md):

| Волна | Привязка к мастер-плану | Конкретные изменения в репозитории | Измеримый критерий готовности (Gate) |
|---|---|---|---|
| **Волна 1. Чистое чтение и вынос логики из `cli.py`** | `З0-S`, `Э2`, `Э4` (`QuerySession`) | 1. Разделить `ensure_index()` на чистую загрузку/in-memory сборку (`mode="readonly"`) и явную публикацию (`mode="readwrite"`).<br>2. Вынести проекции `docs_read`, фильтры `until`/`relation` из `records_list`, `docs_links`, `docs_tree`, `docs_status`, `records_status` из `src/todoc/cli.py` в `src/todoc/application/`.<br>3. Добавить сессионную in-memory мемоизацию `parse_markdown` в `search_documents()`. | Нулевая мутация `.todoc/index/` и `.todoc/history/` при любых вызовах в `mode="readonly"`; ускорение повторного `search` внутри одной сессии с `1 120 мс` до `< 10 мс` на `demo/`. |
| **Волна 2. Публичный Read-Only фасад `todoc.sdk` + `.pyi` стабы** | `Э4`, `Э5`, закрытие `BUG-013`, `BUG-016` | 1. Создать `src/todoc/sdk/` (`session.py`, `types.py`, `__init__.py`, `__init__.pyi`, маркер `py.typed`).<br>2. Реализовать `open_session()`, `ds.resolve()`, `ds.docs`, `ds.records`, `ds.relations`, `ds.staleness.inspect()` (с `actual_anchor` для `BUG-011`), `ds.types` и `TodocSDKError` с `fix_hint`.<br>3. Поддержать `detail="concise" \| "detailed"` и `fields`. | `mypy --strict src/todoc/sdk` = 0 ошибок; размер `__init__.pyi` ≤ 1 300 токенов; паритет ответов SDK и CLI на контрактных тестах; покрытие `src/todoc` = **100%** (гейт `pyproject.toml`). |
| **Волна 3. `BatchPlanBuilder`, идемпотентность и `.todoc/write.lock`** | `Э3`, `Э9`, закрытие `DESIGN-Q02`, `BUG-011`, смягчение `P1-9` | 1. Реализовать `ds.batch_plan()` в памяти без временных файлов, с проверкой перекрёстных `relations` внутри батча.<br>2. Реализовать `ds.apply_plan(..., expected_digest=..., idempotency_key=...)` с файловым локом `.todoc/write.lock` и одной пересборкой индекса на пачку.<br>3. В CLI добавить совместимый флаг `--plan-file` (опция из `DESIGN-Q02`). | Пакет из 10 связанных записей валидируется за 1 вызов `preview()` и применяется за 1 `apply_plan()` с 1 записью пересборки индекса; повторный вызов с тем же `idempotency_key` идемпотентен и не создаёт дублей. |
| **Волна 4. Обновление `SKILL.md` и опциональный песочничный адаптер** | `Э10`, `Э11` (после ядра) | 1. Обновить [`SKILL.md`](../../SKILL.md) и `references/` правилом выбора между `Write`/`Edit` + `sync`, простым CLI и `todoc.sdk`.<br>2. Добавить в `bench/` сравнительный замер `CLI chain vs PTC SDK` по токенам и времени.<br>3. При переходе к MCP/вебу подключить `pydantic-monty` поверх `DatasetSession(mode="readonly")`. | `todoc validate --root demo --all` = 0 диагностик; `python3 tools/linkcheck.py` = `broken 0`; снижение расхода токенов на многошаговых сценариях бенчмарка минимум на **70%**. |

---

## 8. Краткая памятка архитектурных инвариантов (что нельзя нарушить при внедрении)

1. **Никакого исполнения кода из `DATA_ROOT` (`P3`, `P10`).** Код PTC генерируется агентом и вызывает установленный пакет `todoc.sdk`; в `DATA_ROOT` по-прежнему лежат исключительно декларативные файлы `.md`/`.json`/`.csv` и схемы `.todoc/`.
2. **Один источник бизнес-правил (`P11`).** `src/todoc/cli.py` и `src/todoc/sdk/` обязаны вызывать одни и те же функции `src/todoc/application/`. Запрещено писать валидацию в SDK в обход `validator.py` или `write.py`.
3. **Честная усечённость (`P7`).** Любой метод `todoc.sdk`, ограничивающий число элементов или байтовый бюджет, обязан возвращать `truncated: bool` и `total: int`, чтобы скрипт агента никогда не принимал первую страницу за весь датасет.
4. **Прямая правка Markdown остаётся в файловых инструментах.** Не превращать `todoc.sdk` в текстовый процессор для редактирования прозы: связка нативных `Write`/`Edit` + `todoc sync` ([`src/todoc/application/sync.py`](../../src/todoc/application/sync.py)) остаётся каноническим путём для текстов документов.
5. **Деструктивные команды остаются вне песочницы.** Операции `revert`, `change apply/revert/archive`, `history gc/adopt` никогда не пробрасываются внутрь авто-повторяемых PTC-скриптов.
