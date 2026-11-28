# Python API для агентной работы в `todoc`: постулаты, архитектура и спецификация контракта

## Цель, задачи и принципы

**Цель.** Задать полные инженерные критерии и проектную архитектуру публичного Python API (`todoc.sdk`) для вызова языковыми моделями — как напрямую из локальной coding-среды, так и через рантаймы **Programmatic Tool Calling (PTC / Code Mode)**. Документ стоит в одном ряду с [`cli-for-agents.md`](cli-for-agents.md) и [`mcp-for-agents.md`](mcp-for-agents.md) и отвечает на практический вопрос проекта `todoc`: **как дать агенту типизированный Python-доступ к базе знаний там, где цепочки вызовов простого CLI перерасходуют токены, время и порождают временные файлы, не нарушив ни одного инварианта конституции [`docs/plan/constitution.md`](../plan/constitution.md) (`P1`–`P15`)**.

**Для кого.** Для разработчиков ядра `todoc`, авторов `SKILL.md` и агентных харнесов (локальных coding-агентов, MCP-серверов, будущего веб-приложения Этапа 9 [`web-ui.after.md`](../plan/web-ui.after.md)) и инженеров, подключающих к `todoc` песочницы исполнения кода (`pydantic-monty`, Claude PTC, изолированные worker-контейнеры).

**Задачи документа:**
- провести точную границу между четырьмя контурами работы агента в `todoc`: прямой правкой файлов + `todoc sync`, простым одношаговым CLI, локальным Python SDK и песочничным PTC / MCP Code Mode;
- зафиксировать 26 постулатов проектирования Python API для агентов с учётом всех доменных особенностей `todoc` (6 измерений типизации `P4`, тройное пространство идентификаторов `BUG-013`, би-темпоральность `valid_from`/`superseded_at`, фрагментные якоря `derived_from`, витрины `flow` и интероп-экспорты `ASL`/`DMN`/`Rasa`, мьют `!-сегментов`, `.config.json` папок, YAML-lite front matter, review-first `WritePlan` и CAS-хеши);
- спроектировать внутреннюю структуру пакета `src/todoc/sdk/` поверх единого слоя `src/todoc/application/` без новых тяжёлых зависимостей в ядре [`pyproject.toml`](../../pyproject.toml) и с сохранением гейта `100%` branch coverage;
- определить эталонный `.pyi`-контракт, модель сессий `readonly` / `readwrite`, пакетный планировщик `BatchPlanBuilder` с `idempotency_key`, файловую блокировку `.todoc/write.lock` и самодокументируемые исключения `TodocSDKError` (`P15`);
- задать правила безопасного исполнения сгенерированного моделью Python-кода и критерии приёмки в [`bench/run_benchmark.py`](../../bench/run_benchmark.py).

**Основные принципы:**
1. **Один смысл — много транспортов (`P11`).** Python SDK — не второй движок и не обход валидатора: `todoc.sdk`, `cli.py`, MCP-адаптер и будущий веб-интерфейс вызывают одни и те же функции `src/todoc/application/`.
2. **Файлы в `DATA_ROOT` остаются единственной истиной и строго декларативными (`P1`, `P3`, `P10`).** Python-код пишется и исполняется на стороне агента/харнеса поверх установленного пакета `todoc`; внутри `DATA_ROOT` никакой код или формула никогда не хранятся и не исполняются.
3. **Одноходовая композиция вместо конвейера JSON-конвертов.** Там, где агенту нужно пересечь выборки, обойти граф, разрешить идентификаторы или посчитать производную метрику, фильтрация и свёртка происходят в памяти Python-сессии, а в контекст модели возвращается только компактный итог.
4. **Чтение гарантированно свободно от записи на диск; запись — двухфазная (`plan` → `apply`) и идемпотентная (`P6`).** Открытие сессии по умолчанию (`mode="readonly"`) не трогает ни `DATA_ROOT`, ни `.todoc/index/`, ни `.todoc/history/`. Любая мутация проходит через проверяемый план с CAS-защитой `expected_hash` и защитой от повторного запуска упавшего скрипта.
5. **Оптимизируется весь рабочий цикл агента, а не число строк в одном методе.** Проза Markdown остаётся за нативными `Edit`/`Write` + `todoc sync`; одиночные проверки и опасные откаты — за простым CLI; многошаговая навигация, аналитика и пакетная подготовка записей — за `todoc.sdk`.

**Как читать.** Часть I содержит 26 постулатов проектирования Python API под специфику `todoc`; Часть II — подробную архитектуру пакета `src/todoc/sdk/`, эталонный `.pyi`-стаб и референсную реализацию ключевых механизмов; Часть III — операционные правила безопасности для агента и песочниц; Часть IV — методику оценки, расширение бенчмарка и pre-release чек-лист. Эмпирические замеры на корпусе `demo/` и поштучная ревизия всех 64 команд CLI вынесены в парное исследование [`docs/research/programmatic-tool-calling-and-python-api.md`](../research/programmatic-tool-calling-and-python-api.md).

**Срез:** 28 ноября 2026 года.  
**Статус правил:** `[MUST/P]` обязательный инвариант конституции `todoc`; `[STD]` стандарт Python/спецификация формата; `[GUIDE]` проектная рекомендация; `[ЭВРИСТИКА]` измеряемый ориентир, проверяемый на бенчмарке.

> **Граница норм:** PEP 484 / PEP 561 / PEP 589 (`TypedDict`) задают стандарт статической типизации Python и распространения `.pyi`-стабов; RFC 8259 (JSON) и RFC 6901 (JSON Pointer) задают синтаксис структур и адресации; JSON Schema Draft 2020-12 задаёт валидацию записей. Конституция [`constitution.md`](../plan/constitution.md) (`P1`–`P15`) нормативна для всех слоёв `todoc`. Пороги кроссовера PTC (`N >= 3` последовательных шагов, `fan-out >= 15..25`), лимиты страниц и размеры усечения `stdout` — инженерные эвристики, калибруемые на корпусе `bench/`.

---

## I. Постулаты проектирования Python API (`todoc.sdk`) для вызова агентами

### 1. Разделять четыре контура работы агента по задаче и точке кроссовера, а не переводить всё на Python
**Правило.** Python API вводится там, где простой CLI заставляет агента делать серию раунд-трипов (`N >= 3`), копить промежуточные JSON-конверты в контексте, создавать временные файлы для входа или считать агрегаты «в уме» модели. Он **не заменяет** прямую работу файловыми инструментами над текстами `.md` и не заменяет одношаговый CLI на коротких операциях (`N = 1..2`), где генерация скрипта лишь добавляет 20–38% входных/выходных токенов. **[GUIDE/ЭВРИСТИКА]** См. замер на `demo/` в [`programmatic-tool-calling-and-python-api.md`](../research/programmatic-tool-calling-and-python-api.md) §1.1 и правила [`AGENTS.md`](../../AGENTS.md).

```text
Какую операцию над базой знаний todoc выполняет агент?
├─ 1. Создание или содержательная правка текста Markdown (статья, заметка, план, ADR, отчёт)
│  └─ Нативные файловые инструменты харнеса (`Write` / `Edit`) + финальный `todoc sync <paths>`.
├─ 2. Одиночная проверка, статус, CI-гейт или инфраструктурная/деструктивная операция
│  ├─ Гейт / обзор (`validate --all`, `check`, `doctor`, `status`, `explain-path` 1 файла)
│  │  └─ Простой CLI (`todoc <cmd>`): 1 вызов, нулевой оверхед на генерацию кода.
│  └─ История / откат / бандлы (`revert`, `change apply/revert/archive`, `history gc/adopt`, `init`)
│     └─ Строго прямой CLI (`direct`) вне авто-повторяемых скриптов (защита от двойной мутации).
└─ 3. Многошаговое чтение (`N >= 3`), веерный обход графа, кросс-резолв ID, расчёт метрик
      или пакетная сборка типизированных записей / ре-анкоринг `derived_from`
   ├─ Агент работает в локальной среде с установленным пакетом `todoc`
   │  └─ Один вызов Python со скриптом поверх `todoc.sdk.open_session(root, mode="readonly")`.
   └─ Агент работает за сервисной границей (облачный API, MCP-клиент, будущий веб-интерфейс)
      └─ Изолированная песочница (`pydantic-monty` / PTC) с проброшенными методами `todoc.sdk`.
```

- **Удачно:** агент одним коротким скриптом на `todoc.sdk` отбирает открытые баг-репорты с `agent_impact="token_overrun"`, резолвит их Markdown-файлы, вырезает секции `## Предложение по исправлению`, считает сумму `tokens_extra_est` по компонентам и печатает таблицу на 20 строк.
- **Неудачно:** агент пишет Python-скрипт на 25 строк только чтобы вызвать эквивалент `todoc status --root demo`, либо собирает длинную статью `docs/architecture.md` конкатенацией строк в Python вместо штатного `Write` + `todoc sync`.

### 2. Держать единый слой бизнес-логики (`P11`): ни в `cli.py`, ни в `sdk/` нет собственных правил домена
**Правило.** Любая доменная операция — разбор селектора секции, фильтрация CSV `--where`, фильтрация записей по `until`/`relation`, проверка `allowed_statuses` в front matter и `status.enum` в JSON Schema, инвентаризация ссылок, сборка витрины флоу или экспорт в DMN/ASL/Rasa — реализуется ровно один раз в чистом модуле [`src/todoc/application/`](../../src/todoc/application) без зависимости от `click` и форматирования консоли. И [`src/todoc/cli.py`](../../src/todoc/cli.py), и `src/todoc/sdk/` являются тонкими адаптерами ввода/вывода поверх этих функций. **[MUST/P: P11]**

- **Удачно:** логика проекционного чтения (сейчас занимающая 100 строк внутри `docs_read` в `src/todoc/cli.py:1341–1440`) вынесена в `todoc.application.read_doc.read_document_projection()`; CLI оборачивает её в `Envelope`, а `ds.docs.read()` возвращает типизированный `DocProjection`.
- **Неудачно:** скопировать проверку `status.enum` из `records_status` (`cli.py:1870–1915`) в `todoc/sdk/records.py`, после чего при добавлении правила терминальных статусов ([DESIGN-Q01](../../demo/bugs/design-q01-terminalnyy-status-zapisi-guard-procedurnyy-dvizhok-molchit.md)) CLI и Python API начинают вести себя по-разному.

### 3. Жёстко разделять режимы `readonly` и `readwrite`: читающая сессия не пишет ни одного байта на диск
**Правило.** `open_session(root)` по умолчанию открывается в `mode="readonly"`. В этом режиме запрещены любые записи не только в пользовательские файлы `DATA_ROOT`, но и в служебные каталоги `.todoc/index/`, `.todoc/cache/` и `.todoc/history/`. Если опубликованный в `.todoc/index/current/` снимок свеж (`corpus_digest` совпадает), сессия читает его; если индекса нет или корпус изменён извне, сессия строит **эфемерный снимок в оперативной памяти процесса**, не вызывая `RegistryStore.publish()`, `write_stats()` и `observe_external_changes()`. **[MUST/P: P5, P6; закрывает сайд-эффекты `ensure_index` и класс проблем BUG-012 на чтении]**

- **Почему это критично именно в `todoc`:** сейчас `DatasetContext.ensure_index()` ([`src/todoc/service.py`](../../src/todoc/service.py), строки 194–206) при малейшем дрейфе перезаписывает `CURRENT.json`, `stats.json` и пишет событие `external.change` в `.todoc/history/journal.jsonl`. При параллельных вызовах `asyncio.gather` в PTC или при работе read-only MCP-сервера (`M14` в [`mcp-adapter.after.md`](../plan/mcp-adapter.after.md)) это вызывает гонки записи и нежелательные мутации репозитория.
- **Удачно:** `with open_session("demo", mode="readonly") as ds:` выполняет 30 поисковых и графовых запросов в 4 конкурентных корутинах; `git status` и mtime всех файлов в `demo/.todoc/` остаются байт-в-байт неизменными.
- **Неудачно:** вызов `ds.records.query()` молча пересобирает `.todoc/index/current/` на диске и дописывает строку в `journal.jsonl`.

### 4. Публиковать `.pyi`-стабы (PEP 484/561) как первичный машинный контракт для генерации кода моделью
**Правило.** Пакет `todoc` обязан содержать маркер `py.typed` и компактный, самодостаточный файл стабов `src/todoc/sdk/__init__.pyi` (или доменные подмодули `todoc/sdk/*.pyi`), описывающий **и входные сигнатуры, и точные типы возвращаемых словарей (`TypedDict`)**. Для агента в режиме PTC именно текст `.pyi` (а не JSON Schema и не длинная проза гайда) служит спецификацией интерфейса. **[STD/GUIDE]**

- **Почему это важно для одноходового PTC:** когда агент пишет скрипт из 5 вызовов подряд, он **не видит промежуточный JSON первого вызова до того, как напишет пятый вызов**. Если возвращаемый тип описан как `dict[str, Any]`, модель вынуждена угадывать, называется ли ключ `id`, `doc_id` или `document_id`, и лежит ли текст сниппета в `hit["snippet"]` или `hit["snippet"]["text"]`. Строгий `TypedDict` в `.pyi` снимает эту неоднозначность до запуска и позволяет проверить код быстрым тайпчекером (`ty` / `pyright` / `mypy`) за миллисекунды до исполнения.
- **Удачно:** `def search(...) -> Page[SearchHitItem]: ...`, где `SearchHitItem` объявляет все ключи и их типы в 10 строках `.pyi` (~85 токенов на метод против ~300 токенов JSON Schema).
- **Неудачно:** аннотировать публичные функции SDK как `def query_records(**kwargs: Any) -> tuple[list[dict[str, Any]], int, bool]: ...`.

### 5. Использовать именованные аргументы (`*`), плоские сигнатуры и `Literal` вместо строковых мини-языков CLI
**Правило.** В методах `todoc.sdk` позиционным допускается не более одного главного аргумента (`ref` у чтения/графа или `query` у поиска); все остальные параметры объявляются строго keyword-only после `*`. Вместо склеенных CLI-строк (`--where status=open`, `--line-range 10:40`, `--relation belongs_to=flow:checkout`) в Python API передаются нативные структуры языка: `where={"status": "open"}`, `line_range=(10, 40)`, `relation=("belongs_to", "flow:checkout")`, а закрытые перечисления типизируются через `Literal[...]`. **[GUIDE]**

- **Удачно:** `ds.docs.read("doc:note-token-economy", line_range=(1, 35), budget_bytes=2000)`.
- **Неудачно:** заставлять агента в Python клеить строку `ds.docs.read("doc:note-token-economy", line_range="1:35", where="status=open")` и получать ошибку парсинга разделителя, если в значении встретилось `=` или `:`.

### 6. Возвращать единообразные JSON-сериализуемые `TypedDict`, а не смесь `dataclass`, кортежей и `Path`
**Правило.** Все публичные методы `todoc.sdk` возвращают чистые структуры из базовых JSON-типов (`dict`, `list`, `str`, `int`, `float`, `bool`, `None`), типизированные через `TypedDict`. Внутренние доменные датаклассы ([`src/todoc/domain/models.py`](../../src/todoc/domain/models.py): `Document`, `Record`, `SearchHit`, `Diagnostic`, `WritePlan`), объекты `pathlib.Path`, `tuple`-возвраты вида `(items, total, truncated)` и ленивые файловые дескрипторы преобразуются на границе `sdk/` в единообразные словари. **[STD/GUIDE]**

- **Почему это обязательно:**
  1. Убирает ловушку текущего ядра, где `search_documents()` возвращает датакласс `SearchHit` (обращение `hit.snippet_text`), а `query_records()` — словарь `dict` (обращение `rec["record_id"]`). В SDK везде действует единое словарное обращение `item["..."]`.
  2. Любой результат метода `todoc.sdk` проходит через `json.dumps(..., ensure_ascii=False)` без кастомных сериализаторов и прозрачно пересекает границу изолированных рантаймов (`pydantic-monty` `FunctionSnapshot`, IPC-канал воркера, MCP `structuredContent`).
- **Удачно:** `res = ds.docs.search("якорь"); first_path = res["items"][0]["path"]`.
- **Неудачно:** в одном методе возвращать `tuple[list[SearchHit], int, bool]`, во втором — `dict`, в третьем — `list[Diagnostic]` с полями-кортежами и объектами `Path`.

### 7. Обеспечить сквозной кросс-резолв идентификаторов `ds.resolve(ref)` через все три пространства имён `todoc`
**Правило.** В `todoc` один логический объект знаний может адресоваться тремя способами: относительным путём файла (`bugs/bug-011-...md`), идентификатором документа из front matter (`doc:bugs/bug-011-...md` или `doc:note-token-economy`) и идентификатором паспортной JSON-записи (`document:bug-011-...`, содержащей `data.source_path`). SDK обязан предоставлять детерминированный метод `ds.resolve(ref: str) -> ResolvedRef` и принимать любой однозначный `ref` во всех методах чтения, графа и проверки свежести, а также возвращать связанную пару `(document_id, record_id, path, hash)` в каждом ответе. **[GUIDE; полностью закрывает [BUG-013](../../demo/bugs/bug-013-neodnorodnye-id-i-output-kontrakty-rezolv-identifikatora-trebuet-ruchnogo-grep.md)]**

- **Правило разрешения неоднозначности (`P13`):** порядок проверки точный и детерминированный: (1) точное совпадение `document_id`; (2) точное совпадение `record_id`; (3) нормализованный POSIX `rel_path` внутри `DATA_ROOT` (с обратным поиском записи, у которой `data.source_path == rel_path`, если такая запись единственна). Если на один `source_path` ссылаются две разные записи, `record_id` в `ResolvedRef` остаётся `None`, а поле `related_record_ids: list[str]` перечисляет все найденные записи без угадывания.
- **Удачно:** `ds.docs.read("notes/token-economy.md")` и `ds.docs.read("doc:note-token-economy")` и `ds.docs.read("document:bug-013-...")` работают без предварительного `grep` по файлам.
- **Неудачно:** падать с `docs.not_found` на валидный относительный путь файла или возвращать из `plan_new_doc` путь без вычисленного `document_id`.

### 8. Соблюдать портабельность, POSIX-пути и строгий файловый containment на каждом входе (`P1`, `P2`, `P10`)
**Правило.** Все пути во входных и выходных структурах `todoc.sdk` — исключительно POSIX-относительные от корня датасета (`notes/agent-contract.md`, без ведущего `/` и без абсолютного префикса `/home/user/...`). При любом обращении к файлу SDK проверяет containment относительно `root.resolve()`, запрещает выход за `DATA_ROOT` (`AccessError` / `access.outside_data_root`, `exit_code=4`), соблюдает `follow_symlinks: false` из `dataset.json`, блокирует синхронизацию или чтение служебного `.todoc/*` под видом документа (`sync.internal_path`) и формирует имена файлов записей только через `portable_name()` ([`src/todoc/application/write.py`](../../src/todoc/application/write.py), защита от `:`, `/`, `CON`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`). **[MUST/P: P1, P2, P10]**

- **Удачно:** `ds.records.get("workout:2026-11-28")` находит файл `records/workout/workout-2026-11-28.json`, в ответе `"path": "records/workout/workout-2026-11-28.json"`; попытка `ds.docs.read("../../etc/passwd")` бросает `TodocSDKError(code="access.outside_data_root", exit_code=4)`.
- **Неудачно:** принимать в `todoc.sdk` произвольный `Path` и открывать его напрямую через `Path(user_arg).read_text()` в обход containment-проверки сканера.

### 9. Поддерживать явную изоляцию нескольких корней (`open_session` для одного `DATA_ROOT`, `open_workspace` для multi-root)
**Правило.** В соответствии с конституцией (`P2`, повторяемый `--root`), SDK никогда не выводит `DATA_ROOT` магически из глобального состояния модуля. Для одного датасета используется `open_session(root)`, для федеративной выборки по нескольким базам знаний — `open_workspace(roots=[...])`, где каждый возвращаемый элемент обязательно несёт `dataset_id`, а графы и индексы разных корней изолированы и никогда не сливаются на диске. **[MUST/P: P2]**

- **Удачно:** `ws = open_workspace(["demo", "personal-kb"], mode="readonly")`; `ws.search_all("BM25")` возвращает хиты с явным `dataset_id` каждого корня.
- **Неудачно:** хранить текущий `DATA_ROOT` в глобальном синглтоне `todoc.sdk.CURRENT_ROOT`, ломающемся при работе с двумя датасетами в одном процессе.

### 10. Хранить декларативность в `DATA_ROOT`, а производную математику отдавать PTC-скрипту агента (`P3`, `P10`, `P1-11`)
**Правило.** `todoc.sdk` никогда не вычисляет формулы или код из конфигураций и записей `DATA_ROOT`: в `entity_types/*/type.json` у `metric_fields.<field>` разрешены только `unit` и текстовый `prompt` (решение `P1-11` в [`11-known-issues.md`](../state/11-known-issues.md)), а `agent_instructions` и `prompts/*.md` возвращаются строго как пассивные строки данных. При этом SDK даёт агенту метод `ds.types.get(entity_type)` (чтобы прочитать `unit` и семантику `prompt`) и `ds.records.query(...)` (чтобы получить числовые поля и вложенные `{"value": ..., "unit": ...}`), позволяя самому PTC-скрипту выполнить любой точный расчёт (`reps * weight_kg`, медиану, группировку по `YYYY-MM`, проверку совпадения `unit`) на Python без раздувания контекста модели. **[MUST/P: P3, P5, P10]**

- **Удачно:** `ds.records.aggregate("metric", "value", group_by="category")` проверяет однородность единиц внутри каждой группы (`query.unit_mismatch`) и возвращает честную `formula: "sum(value)"` + `prompt`, а сложную производную метрику агент считает в 5 строках Python поверх `ds.records.query()`.
- **Неудачно:** добавлять в `ds.records.aggregate()` параметр `expr="reps * weight_kg"` с вызовом `eval()` или хранить лямбда-выражения в `.todoc/`.

### 11. Проектировать двойное прогрессивное раскрытие: компактные проекции данных (`detail`, `fields`) и модульные стабы (`P7`)
**Правило.** Даже внутри Python-скрипта не нужно тащить лишние мегабайты текста без запроса, а при возврате данных из функций в изолированную песочницу (где каждый вызов сериализуется через RPC/snapshot) объём особенно важен. Списочные методы `todoc.sdk` поддерживают:
1. `detail: Literal["concise", "detailed"] = "concise"` — в режиме `concise` возвращаются идентификаторы, путь, тип, статус, заголовок/ключевые скалярные поля и хеш; тяжёлые текстовые поля, полные массивы `examples` или дерева `tree` опускаются либо запрашиваются через `detail="detailed"` / `get(ref)`.
2. `fields: Sequence[str] | None` и `exclude_fields: Sequence[str] | None` — точечная проекция полей (в том числе по точечным путям внутри `data`, согласовано с [`demo/ideas/unified-cli-output.md`](../../demo/ideas/unified-cli-output.md)).
3. Для слабых моделей и MCP Code Mode `.pyi`-контракт делится по подпространствам (`docs`, `records`, `relations`, `staleness`, `flows`, `batch`), чтобы при необходимости отдавать стаб только нужного домена (~150–250 токенов). **[MUST/P: P7; GUIDE]**

- **Удачно:** `ds.records.query(entity_type="flow", fields=("record_id", "title", "status"))` не тянет в память полные JSON-деревья всех флоу, когда агенту нужен только реестр.
- **Неудачно:** в `ds.docs.search()` по умолчанию вкладывать полный текст каждого найденного Markdown-файла вместо ограниченного `snippet` (≤ 240 символов) с `line_start`/`line_end` и `heading_path`.

### 12. Стандартизировать пагинацию `Page[T]`, курсоры и защищённый сборщик `collect_all(..., max_items=500)`
**Правило.** Любой метод `todoc.sdk`, возвращающий потенциально длинную коллекцию (`docs.search`, `docs.links`, `records.query`, `history.log`, `history.timeline`), обязан возвращать единый словарь `Page[T]`: `{"items": list[T], "total": int, "returned": int, "truncated": bool, "next_cursor": str | None}`. Дефолтные лимиты конечны и совпадают с `dataset.json` (`limits.max_query_results = 200` для записей, `limit = 10` для поиска). Для полного обхода в аналитических PTC-скриптах SDK предоставляет хелпер `ds.collect_all(fetch_fn, *, max_items: int = 500)`, который сам листает `next_cursor`, но останавливается на предохранителе `max_items` и возвращает явный флаг `hit_cap: bool`. **[MUST/P: P7]**

- **Удачно:** агент вызывает `ds.records.query(entity_type="task", limit=50)` и сразу видит `total=142, truncated=True, next_cursor="50"`, не принимая первую страницу за весь список задач.
- **Неудачно:** обрезать список до 200 элементов молча, возвращая голый `list[RecordItem]` без `total` и `truncated`.

### 13. Использовать двухуровневый кэш разбора внутри сессии: дисковый `.todoc/cache/parse/` + мемоизация в памяти
**Правило.** Внутри одного экземпляра `DatasetSession` разобранное представление файла (`ParsedMarkdown`, JSON-структура, CSV-таблица, лексические токены поиска и `.config.json` папок) мемоизируется в оперативной памяти по ключу `(rel_path, content_hash)`. При холодном чтении в `DatasetSession` подхватывается существующий дисковый кэш `.todoc/cache/parse/<16 hex>.json` с проверкой `content_hash` и `PARSER_VERSION` ([`src/todoc/application/registry.py`](../../src/todoc/application/registry.py), строки 179–233), но в `mode="readonly"` промахи кэша остаются только в памяти (на диск не пишутся). При любой записи в `mode="readwrite"` вызывается синхронный сброс и дискового (`invalidate_parse_cache`), и in-memory кэша затронутых путей. **[GUIDE; устраняет узкое место `search.py` с 1 120 мс до < 5 мс на повторных вызовах]**

- **Удачно:** в одном PTC-скрипте агент делает 6 вызовов `ds.docs.search()` по разным терминам и затем `ds.staleness.inspect()` — каждый из 465 Markdown-файлов `demo/` разбирается максимум один раз за всю сессию.
- **Неудачно:** как в текущем `search_documents()` (`src/todoc/application/search.py:37, 198`), заново читать и парсить все `.md` с диска на каждый вызов и парсить файлы хитов второй раз ради хлебных крошек заголовков.

### 14. Строго учитывать особенности парсеров форматов `todoc`: YAML-lite front matter, границы секций, JSON-позиции и порядок фильтрации CSV
**Правило.** Методы `todoc.sdk` обязаны опираться исключительно на штатные форматы `src/todoc/adapters/formats/` и их граничные гарантии:
- **Markdown (`markdown.py`):** парсинг через `markdown-it-py` (игнорирование `#`-комментариев и ссылок внутри code fence / инлайн-кода); front matter — плоский **YAML-lite** (`key: value` и инлайн-списки `[a, b]`, строки с `:` обязаны быть в кавычках — `markdown.front_matter.yaml_unsafe`; генератор front matter в SDK не должен порождать сломанных `\"`-последовательностей с учётом [BUG-015](../../demo/bugs/bug-015-yaml-lite-front-matter-ne-obrabatyvaet-backslash-escape-kavychek.md)). Вырезка секции (`section="..."` или `ref="doc:...#section"`) режет строго до следующего заголовка уровня `<= selected.level` и применяет `budget_bytes` (или `SECTION_MAX_LINES = 40` по умолчанию), сообщая `section_total_lines` и `truncated`.
- **JSON (`jsonfmt.py`):** итеративный контроль глубины `max_json_depth` (`128`, защита от `RecursionError` → `json.too_deep`), детекция дублирующихся ключей и `NaN`/`Infinity` с точными номерами строк, адресация вложенных узлов строго по RFC 6901 JSON Pointer (`pointer="/tree/nodes/0"`).
- **CSV (`csvfmt.py`):** фильтрация `where` всегда применяется **до** среза `max_rows` (урок закрытого дефекта `P1-5`), а ответ содержит `total_rows`, `matched_rows` и `truncated`. **[MUST/P: P4, P7, P8]**

- **Удачно:** `ds.docs.read("data/metrics.csv", where={"status": "fail"}, columns=("id", "latency_ms"), max_rows=5)` сначала находит все упавшие строки во всём файле, а затем берёт первые 5.
- **Неудачно:** парсить Markdown регулярками `^#+ ` в обход `parse_markdown()` или перезаписывать front matter документа внешним `yaml.dump()`, порождая многострочный YAML, который собственный парсер `todoc` не прочитает.

### 15. Единообразно соблюдать конвенции хранилища: мьют `!-сегментов` пути и метаданные папок `.config.json`
**Правило.** В `todoc` есть два важных файловых соглашения, не хранящихся в `.todoc/index/`:
1. **Мьют по префиксу `!` на сегменте папки** (например, `skills/!legacy-deploy/SKILL.md` или архивная папка `!old-notes/`): мьют — свойство размещения, а не удаления ([`src/todoc/application/skills.py`](../../src/todoc/application/skills.py), [`src/todoc/application/search.py`](../../src/todoc/application/search.py) строка 150). По умолчанию `ds.docs.search()`, `ds.docs.tree()` и `ds.skills.list()` исключают `!-пути`, а при передаче `include_muted=True` включают их с явным полем `"muted": True`.
2. **Самоописание папок `<folder>/.config.json`** ([`src/todoc/application/folder_config.py`](../../src/todoc/application/folder_config.py)): работает по правилу **fail-open на чтении / fail-closed на валидации**. В `ds.docs.tree()` валидный `.config.json` обогащает узел папки человекочитаемым `title`, `description`, `tags` и `order`; в `ds.docs.search()` даёт аддитивный буст `+2` за предков; в `ds.docs.suggest_dir(query)` ранжирует кандидатов с порогом `0.25`; битый `.config.json` не роняет чтение и поиск, но обязательно виден в `ds.validate()`. **[MUST/P: P1, P4, P5]**

- **Удачно:** `ds.docs.suggest_dir("отчёты об ошибках и фрикциях агентов")` возвращает папку `bugs` с `title` и `score >= 0.25`, помогая агенту выбрать `--dir` без чтения всего дерева.
- **Неудачно:** в SDK-методе дерева папок игнорировать `.config.json` или падать с необработанным исключением чтения при синтаксической ошибке в одном `.config.json`.

### 16. Явно типизировать язык фильтров `records.query()` и би-темпоральную семантику (`as_of`)
**Правило.** В `todoc` записи поддерживают как структурную фильтрацию по вложенным полям `data` (`"a.b"`), так и би-темпоральную модель ([`src/todoc/application/temporal.py`](../../src/todoc/application/temporal.py)):
- **Операторы фильтрации** должны быть задокументированы прямо в `.pyi` и докстроках SDK (закрывая [BUG-016](../../demo/bugs/bug-016-filtry-records-query-ne-dokumentirovany-v-spravkah.md)): скаляр/список проверяется на равенство `actual == expected`; `{"$in": [...]}` проверяет `actual in expected["$in"]` (включая списочные поля вроде `agent_impact`); `{"$gte": X, "$lte": Y}` проверяет диапазон; дополнительно добавляется оператор `{"$contains_any": [...]}` для удобного поиска вхождения элемента в массив тегов/меток без перечисления комбинаций списков!
- **Би-темпоральность (`as_of`):** различает время правды в мире (`valid_from <= T < valid_to`, интервал **полуоткрытый** — в момент `valid_to` факт уже не действует) и время знания системы (`observed_at`, `superseded_at`). При `as_of=None` скрываются записи, закрытые через `superseded_at` (но они остаются читаемыми напрямую по `ds.records.get(ref)` и в `ds.history.timeline()`). Неразбираемая строка `as_of` (например, `"вчера"`) обязана немедленно поднимать `TodocSDKError(code="temporal.invalid_instant", exit_code=3)`, а не возвращать пустую выборку. **[MUST/P: P5, P8]**

- **Удачно:** `ds.records.query(entity_type="rule", as_of="2026-11-01T00:00:00Z")` точно возвращает правила, действовавшие и не отменённые на указанный UTC-момент.
- **Неудачно:** трактовать невалидный `as_of` как «0 совпадений» или физически удалять устаревший факт вместо выставления `superseded_at`.

### 17. Различать в графе валидируемые рёбра `Relation` и текстовые упоминания `mentions`
**Правило.** Графовые методы `ds.relations.neighbors()` и `ds.relations.tree()` обязаны сохранять чёткую семантическую границу `todoc` ([`src/todoc/application/query.py`](../../src/todoc/application/query.py), строки 118–217):
- **Явные связи (`via="relation"`):** хранятся в источнике (`record.relations` или front matter), проходят строгую валидацию типов вершин по `endpoints` в `relation_types/*/type.json` и участвуют в многошаговом BFS на глубину `depth`, с фильтрацией по `type_id`, направлению `direction: Literal["out", "in", "both"]` и темпоральному срезу `as_of` (`temporal.relations_as_of`).
- **Текстовые упоминания из Markdown (`via="mention"`):** строятся из ссылок и упоминаний идентификаторов в `.md`, несут якорь источника `fragment` (`#section`), присоединяются к узлу без дальнейшего рекурсивного расползания по всему корпусу Markdown (если `include_mentions=True`). В `ds.relations.tree()` повторно встреченные вершины помечаются `"cycle": True` без бесконечной рекурсии. **[MUST/P: P9]**

- **Удачно:** агент одним вызовом `ds.relations.tree("flow:checkout", depth=2, include_mentions=True)` получает и связанные правила `belongs_to`, и используемые термины `uses_term`, и документы спецификаций, где этот флоу упомянут, с отметкой циклов.
- **Неудачно:** смешивать случайную ссылку в заметке и типизированное ребро `depends_on` без поля `via`, из-за чего агент считает черновую заметку блокером релиза.

### 18. Делать диагностику свежести `derived_from` самодостаточной для автоматического ре-анкоринга
**Правило.** Зависимость свежести в `todoc` привязана к **фрагменту**, а не только к файлу ([`src/todoc/application/staleness.py`](../../src/todoc/application/staleness.py)): весь файл (`path@sha256:...`), Markdown-секция (`path#section:<heading>@sha256:...`) или JSON Pointer с канонической сортировкой ключей (`path#/pointer@sha256:...`). Метод `ds.staleness.inspect()` обязан возвращать для каждой дрейфующей зависимости структуру `StaleItem`, содержащую **и старый `expected_anchor`, и готовый вычисленный `actual_anchor`**, а также различать статус `changed`, `missing` (файл удалён), `unresolved` (секция/поинтер переименованы) и `acknowledged` (подтверждено человеком в `stale_ack_hashes`). На стороне планировщика методы `batch.reanchor_stale(owner_refs)` и `batch.acknowledge_stale(owner_ref, reason=...)` готовят точечные правки front matter с сохранением тела документа байт-в-байт. **[GUIDE; полностью закрывает [BUG-011](../../demo/bugs/bug-011-dreyf-derived-from-pri-smene-statusa-tela-ishodnika-trebuet-ruchnogo-re-ankoringa.md)]**

- **Удачно:** после обновления термина в глоссарии агент вызывает `ds.staleness.inspect()`, видит 10 затронутых владельцев с готовыми `actual_anchor` и одной командой `ds.batch_plan().reanchor_stale(owners).preview()` готовит чистый review-first план.
- **Неудачно:** отдавать только «зависимость изменилась» со старым хешем, вынуждая агента запускать внешний `hashlib.sha256`, вручную канонизировать JSON Pointer и искать номер строки во front matter.

### 19. Защищать автособираемые витрины (`generated`) и давать чистый API для `flow` и `interop`
**Правило.** Производные представления в `todoc` — витрины `flow-doc` ([`src/todoc/application/flow_view.py`](../../src/todoc/application/flow_view.py)) и экспорты интероперабельности `flow → ASL`, `rule → DMN 1.3 (hitPolicy="UNIQUE")`, `term → Rasa NLU` ([`src/todoc/application/interop.py`](../../src/todoc/application/interop.py)) — подчиняются правилу единственного источника истины: правятся исходные записи `flow`/`rule`/`term`, а витрины пересобираются детерминированно с маркером `<!-- СГЕНЕРИРОВАНО:` и якорями `derived_from`. В `todoc.sdk`:
- `ds.flows.inspect(flow_ref, *, start_at=None)` и `ds.flows.walk_all(flow_ref)` дают чистый в памяти обход состояний, таблицы решений и всех ациклических путей до терминалов;
- `ds.interop.preview_export(target="dmn" | "asl" | "rasa", ...)` и `ds.interop.check_drift()` проверяют корректность маппинга (включая наличие `ALLCAPS` кодов отказа вне слов RFC 2119 и комплементарной ветви `да`) без записи на диск;
- попытка прямой точечной правки файла витрины через `ds.docs` или `ds.sync()` без явного `allow_derived=True` отклоняется с кодом `docs.derived_edited_directly` и списком исходников `sources` из `derived_from`. **[MUST/P: P1, P5, P6]**

- **Удачно:** агент проверяет покрытие всех правил флоу в памяти через `ds.flows.walk_all("flow:payment")` и `ds.interop.check_drift()`, и материализует обновлённые витрины через единый `BatchWritePlan`.
- **Неудачно:** править руками сгенерированную таблицу решений в Markdown-витрине, которая затрётся при следующем `flow render --write`.

### 20. Масштабировать `P6` review-first через пакетный `BatchPlanBuilder` без временных файлов (`P1-9` + `DESIGN-Q02`)
**Правило.** Вместо переноса в Python антипаттерна CLI «запиши временный JSON-файл → вызови `--preview` → вызови `--apply` с теми же аргументами для каждой из N записей», `todoc.sdk` вводит двухфазный **пакетный планировщик в памяти** (`ds.batch_plan()`):
1. **Фаза `preview()` (чистая, доступна в `mode="readonly"` и внутри PTC-песочницы):** принимает нативные словари Python, проверяет все JSON Schema 2020-12, `required_fields`, `required_sections`, `portable_name()` и **валидирует граф `relations` с учётом всех новых `record_id` и `document_id`, создаваемых в этом же батче**. Возвращает сериализуемый `BatchWritePlanDict` с индивидуальными `expected_hash`/`new_hash` и общим криптографическим `plan_digest` (`sha256:...`), не создавая ни одного файла на диске.
2. **Фаза `apply_plan(plan, expected_digest=..., idempotency_key=...)` (требует `mode="readwrite"`):** повторно проверяет CAS-хеши всех целей под локом `.todoc/write.lock`, атомарно пишет файлы (при сбое на K-м файле откатывает первые K−1 к исходным байтам), сбрасывает кэш парсинга затронутых путей, пишет связанную запись в журнал истории и вызывает пересборку индекса **ровно один раз на всю пачку**. **[MUST/P: P1, P6, P9; закрывает DESIGN-Q02 и обходит риск P1-9]**

- **Удачно:** создание плана и 8 связанных задач с `belongs_to` и `depends_on` между собой проходит за 1 `preview()` и 1 `apply_plan()` без единого файла в `/tmp` и за одну пересборку индекса вместо шестнадцати.
- **Неудачно:** заставлять агента сохранять `input.json` во рабочую папку (рискуя поймать `P1-9` `record.duplicate_id`) или пересобирать весь индекс после каждого элемента цикла.

### 21. Сохранять узкую дисциплину мутаций: create-only для записей, управляемые статусы и байт-точный `undo_relation`
**Правило.** Python API не должен открывать «чёрный ход» `overwrite_record(record_id, arbitrary_dict)` в обход конституционного правила `P6` («записи create-only в базовом контуре»). Разрешённые операции изменения существующих объектов в `BatchPlanBuilder` строго соответствуют проверенным инвариантам ядра:
- `create_record(entity_type, data)` — строго create-only (`record.duplicate_id` / `record.target_exists`, `exit_code=5`);
- `set_record_status(ref, status)` — меняет только поле `status` после проверки вхождения в `properties.status.enum` схемы типа (`records.status_not_allowed`) и опционального guard-а терминальных статусов ([DESIGN-Q01](../../demo/bugs/design-q01-terminalnyy-status-zapisi-guard-procedurnyy-dvizhok-molchit.md));
- `undo_relation(record_ref, pointer="/relations/N")` — точечный откат ребра по журналу истории с сохранением остального JSON байт-в-байт (`_json_array_element_span` в [`src/todoc/application/write.py`](../../src/todoc/application/write.py));
- `new_doc(...)`, `set_doc_status(ref, status)` (с проверкой `allowed_statuses` в `doc_type`), `fix_link(...)` (с пересчётом относительного пути от папки файла через `_link_replacement()`), `reanchor_stale(...)`, `acknowledge_stale(...)`.
Для сложных многофайловых рефакторингов документов с базовым снимком и дельтами (`## ADDED / MODIFIED / REMOVED`) остаётся подсистема `changes` на внешнем контуре. **[MUST/P: P6]**

- **Удачно:** `batch.set_record_status("task:sdk-core", "done")` проверяет схему `task` до касания диска и меняет ровно статус под защитой `expected_hash`.
- **Неудачно:** дать в SDK метод `update_record(id, dict)`, который затирает `created_at`, темпоральные поля `observed_at` или чужие `relations` при частичной передаче словаря моделью.

### 22. Защищать систему от повторного прогона PTC-скрипта (*Rerun Write Duplication Hazard*) через Selective Sandboxing и `idempotency_key`
**Правило.** Главное отличие PTC от одиночного вызова инструмента: если агентский скрипт из 15 строк успешно выполнил мутацию на строке 5, а на строке 11 упал с `KeyError`, модель исправит строку 11 и **запустит весь скрипт целиком во второй раз**. Для защиты от двойных записей в `todoc.sdk` действуют два барьера:
1. **Selective Sandboxing (разделение контуров):** в изолированную PTC-песочницу пробрасываются только читающие методы (`mode="readonly"`) и чистый конструктор `batch_plan().preview()`. Вызов `apply_plan()` исполняется оркестратором как отдельный прямой шаг после успешного завершения скрипта и проверки плана.
2. **Обязательный `idempotency_key` в `apply_plan()`:** в локальном режиме, когда скрипт вызывает `apply_plan()` напрямую, ключ идемпотентности вместе с `plan_digest` фиксируется в метаданных события `.todoc/history/journal.jsonl`. Повторный вызов `apply_plan` с тем же `idempotency_key` и тем же `plan_digest` возвращает сохранённый результат первой фиксации (`"idempotent_replay": True`) без повторной записи и без ошибки; тот же `idempotency_key` с **другим** `plan_digest` отклоняется с `ConflictError("write.idempotency_conflict", exit_code=5)`.
3. **Запретный список Tier D:** 12 инфраструктурных/деструктивных команд (`init`, `revert`, `tag`, `history gc/adopt/export`, `change open/apply/archive/revert`, `skills attach/import`) не экспортируются в агентский стаб `todoc.sdk`. **[GUIDE/SECURITY]**

- **Удачно:** скрипт внутри PTC возвращает `BatchWritePlanDict`, а при локальном запуске с `idempotency_key="triage-2026-11-28-batch1"` повторный запуск не плодит дублей ревизий.
- **Неудачно:** вызывать `revert` или создание записей со случайным UUID внутри цикла PTC-скрипта без ключа идемпотентности.

### 23. Гарантировать snapshot isolation на чтении и эксклюзивный `.todoc/write.lock` на записи
**Правило.** Объект снимка внутри `DatasetSession(mode="readonly")` неизменяем (immutable view): параллельные корутины `asyncio.gather(...)` или потоки внутри одного скрипта читают его без блокировок и без состояния гонки. Любая операция записи (`apply_plan`, `sync_files`, `rebuild_index`) захватывает межпроцессный файловый лок `.todoc/write.lock` (`fcntl.flock` на Linux/macOS, `msvcrt.locking` на Windows) с конечным `lock_timeout_sec: float = 5.0`. Если другой процесс удерживает датасет дольше таймаута, поднимается `TodocSDKError(code="write.dataset_locked", exit_code=5)` с подсказкой подождать завершения параллельной операции, а не портится `CURRENT.json` или `journal.jsonl`. **[GUIDE; закрывает открытый риск блокировки датасета из `11-known-issues.md`]**

- **Удачно:** два параллельных агента читают `demo/` одновременно без ожидания; при одновременной попытке записи второй ждёт до 5 с или получает чистый `write.dataset_locked`.
- **Неудачно:** два параллельных процесса одновременно переименовывают `.todoc/index/.tmp-current` в `current` и теряют чужие изменения в `CURRENT.json`.

### 24. Отличать штатные бизнес-находки от ошибок вызова и делать `TodocSDKError` самодокументируемым (`P15`)
**Правило.**
1. Диагностические методы (`ds.validate()`, `ds.staleness.inspect()`, `ds.docs.links(broken_only=True)`, `ds.interop.check_drift()`) при обнаружении ошибок в данных датасета **не бросают исключение**, а штатно возвращают список типизированных находок (чтобы скрипт агента мог их сгруппировать, отфильтровать и починить).
2. Ошибки самого вызова (неизвестный `ref`, выход за `DATA_ROOT`, нарушение JSON Schema при `preview()`, конфликт `expected_hash`, невалидный `as_of`) поднимают единое исключение `TodocSDKError` (наследник или адаптер `TodocError` из [`src/todoc/errors.py`](../../src/todoc/errors.py)), содержащее поля `code`, `exit_code` (`2..6`), `path`, `location`, `fix_hint` и `suggested_fixes`.
3. В соответствии с конституционным принципом **`P15`**, текст `fix_hint` берётся из переключаемого `i18n`-каталога подсказок `guidance` по стабильному `code` (а не зашивается простынями текста по всему коду), а рантайм исполнения кода перехватывает `TodocSDKError` и печатает агенту компактную карточку ошибки (5–8 строк с точным списком допустимых значений или исправимым примером) вместо 60 строк внутреннего стектрейса библиотеки. **[MUST/P: P8, P13, P15]**

- **Удачно:**
  `TodocSDKError [records.status_not_allowed, exit=3] path='records/task/t1.json': Статус 'closed' не входит в enum типа 'task'. Допустимые значения: ['planned', 'in_progress', 'blocked', 'done', 'cancelled']. Hint: передайте одно из допустимых значений в set_record_status().`
- **Неудачно:** вывалить модели 80 строк traceback из недр `jsonschema/validators.py` без списка разрешённых статусов либо вернуть `{}` вместо ошибки при несуществующем `id` ([BUG-013](../../demo/bugs/bug-013-neodnorodnye-id-i-output-kontrakty-rezolv-identifikatora-trebuet-ruchnogo-grep.md)).

### 25. Сохранять полную атрибуцию в журнале истории (`actor`, `basis`, `change_id`) и изоляцию сессионного стейта
**Правило.** При открытии пишущей сессии `open_session(root, mode="readwrite", actor="agent:sdk", change_id=None)` все события, записываемые в `.todoc/history/journal.jsonl`, получают честный `actor` (отличающий программный вызов SDK от ручного `cli`), осмысленный `basis` из элементов плана и опциональную привязку `change_id` ([`src/todoc/application/history.py`](../../src/todoc/application/history.py)). Оперативный контекст сессии агента (`context.current_project` из `ALLOWED_KEYS_V1` в [`src/todoc/application/state.py`](../../src/todoc/application/state.py)) остаётся строго в `{XDG_STATE_HOME}/todoc/state-<dataset_id>.json` вне `DATA_ROOT`, чтобы переключение рабочего фокуса агента никогда не загрязняло ни файлы базы знаний, ни `git status`. **[MUST/P: P1, P2]**

- **Удачно:** `ds.state.get("context.current_project")` подставляет проект по умолчанию при фильтрации задач в скрипте, не трогая `DATA_ROOT`.
- **Неудачно:** сохранять временные переменные сессии агента внутрь `dataset.json`.

### 26. Ограничивать объём вывода скрипта и давать инструктивную диагностику при переполнении буфера
**Правило.** Экономия PTC обнуляется, если агент пишет `print(json.dumps(ds.records.query(limit=200)))` и вываливает 80 КБ сырого JSON обратно в контекст модели. В обёртке исполнения кода (`todoc.sdk.sandbox` / MCP `todoc_run_readonly`) стандартный вывод (`stdout`) и сериализованное возвращаемое значение жёстко ограничиваются порогом `max_output_chars: int = 8_000` (настраиваемо). При превышении лимита возвращаются первые `max_output_chars` символов + явный блок `output_truncated: True` с подсказкой: *«Вывод скрипта превысил 8 000 символов (фактически 43 120). Отфильтруйте записи, сгруппируйте счётчики (`Counter`, `sum`) или запросите только нужные поля `fields=(...)` внутри Python-скрипта перед `print()`»*. **[GUIDE/ЭВРИСТИКА]**

- **Удачно:** агент при случайном дампе получает ясную инструкцию и следующим ходом сворачивает данные в компактную таблицу.
- **Неудачно:** молча обрезать JSON посередине строки (ломая парсер на стороне клиента) или пропустить 200 КБ в контекстное окно.

---

## II. Архитектурная организация `src/todoc/sdk/` с учётом особенностей проекта `todoc`

### 1. Место `todoc.sdk` в слоёной архитектуре и политика нулевых лишних зависимостей

В [`pyproject.toml`](../../pyproject.toml) ядро `todoc` опирается ровно на три лёгкие библиотеки (`click>=8.1`, `jsonschema>=4.20`, `markdown-it-py>=3.0`), требует `python >= 3.11` и проверяется строгим гейтом покрытия `--cov=todoc --cov-branch --cov-fail-under=100`. Архитектура `todoc.sdk` обязана сохранить оба свойства:

1. **Ноль новых обязательных зависимостей в `[project.dependencies]`:** сам пакет `src/todoc/sdk/` строится целиком на стандартной библиотеке Python 3.11+ (`typing.TypedDict`, `typing.Literal`, `dataclasses`, `contextlib`, `fcntl`/`msvcrt`, `hashlib`) и уже установленных `jsonschema` / `markdown-it-py`. Тяжёлые рантаймы песочниц (`pydantic-monty`) и протокольные обвязки (`mcp`) подключаются исключительно как опциональные extras:
   ```toml
   [project.optional-dependencies]
   dev = ["pytest>=8.0", "pytest-cov>=5.0", "mypy>=1.11"]
   sandbox = ["pydantic-monty>=0.1"]
   mcp = ["mcp>=1.0", "pydantic-monty>=0.1"]
   ```
2. **Строгое направление импортов (`02-architecture.md`):**
   ```text
   cli.py (Click) ──────┐
   sdk/ (Python API) ───┼──► application/* ──► domain/ + typing_system/ + ports/
   mcp/ (будущий) ──────┤          │
   web/ (Этап 9) ───────┘          ▼
                         adapters/ (filesystem, formats, history) + guidance (i18n P15)
   ```
   - `src/todoc/sdk/` **никогда не импортирует `click` и `src/todoc/cli.py`**.
   - `src/todoc/application/` **никогда не импортирует `src/todoc/sdk/`**.
   - В [`src/todoc/__init__.py`](../../src/todoc/__init__.py) реэкспортируются только высокоуровневые точки входа: `__version__`, `open_session`, `open_workspace`, `DatasetSession`, `TodocSDKError`.

### 2. Рекомендуемая раскладка модулей `src/todoc/sdk/`

```text
src/todoc/
├── __init__.py                 # __version__, open_session, open_workspace, TodocSDKError
├── py.typed                    # PEP 561 маркер типизированного пакета
├── guidance/                   # Общий каталог кодов и i18n-подсказок (Принцип P15, для CLI и SDK)
│   ├── __init__.py
│   └── catalog_ru.json         # Стабильные code -> summary, fix_hint, doc_ref
├── application/                # Чистые use-case модули (включая вынесенные из cli.py):
│   ├── read_doc.py             # ВЫНЕСТИ из cli.py: docs_read (section/line_range/pointer/csv)
│   ├── links_tree.py           # ВЫНЕСТИ из cli.py: docs_links, docs_tree с .config.json
│   ├── status_ops.py           # ВЫНЕСТИ из cli.py: docs_status, records_status + enum/allowed checks
│   └── ...                     # существующие validator, search, query, write, sync, staleness, ...
└── sdk/
    ├── __init__.py             # Публичный фасад пакета
    ├── __init__.pyi            # Компактный сводный стаб для агентов/PTC и тайпчекеров (mypy/ty)
    ├── types.py                # Все TypedDict и Literal контракты входов и выходов
    ├── errors.py               # TodocSDKError, конвертер TodocError + guidance, форматтер без шума
    ├── lock.py                 # Кроссплатформенный эксклюзивный файловый лок .todoc/write.lock
    ├── snapshot.py             # ReadOnlySnapshot + сессионный in-memory кэш разбора по (path, hash)
    ├── resolver.py             # Кросс-резолв ref: document_id <-> record_id <-> rel_path (#fragment)
    ├── session.py              # DatasetSession (readonly/readwrite), WorkspaceSession, collect_all
    ├── batch.py                # BatchPlanBuilder, кросс-валидация пачки в памяти, идемпотентный apply
    ├── namespaces/
    │   ├── docs.py             # DocsAPI: search, read, suggest_dir, links, tree
    │   ├── records.py          # RecordsAPI: query, get, aggregate
    │   ├── relations.py        # RelationsAPI: neighbors, tree (с as_of и mentions)
    │   ├── staleness.py        # StalenessAPI: inspect (со старым и актуальным якорем)
    │   ├── types_ns.py         # TypesAPI: list, get (со схемой и allowed_statuses), prompt
    │   ├── flows.py            # FlowsAPI: inspect, walk, walk_all, preview_markdown
    │   ├── interop.py          # InteropAPI: preview_export (asl/dmn/rasa), check_drift
    │   ├── skills.py           # SkillsAPI: list, read (с поддержкой мьюта !-папок)
    │   ├── history.py          # HistoryAPI: log, show, diff, blame, timeline, context_pack
    │   └── state.py            # StateAPI: get, list, set, unset (XDG state вне DATA_ROOT)
    └── sandbox.py              # Регистрация чистых тулов для pydantic-monty / PTC + stdout guard
```

### 3. Жизненный цикл `DatasetSession`: изоляция чтения, кэш и транзакционная запись

```text
open_session(root, mode="readonly")                 open_session(root, mode="readwrite")
───────────────────────────────────                 ────────────────────────────────────
1. Загрузка dataset.json + TypeRegistry             1. То же + проверка доступности корня на запись
2. Сканирование stats / проверка CURRENT.json       2. Ленивое чтение до первой мутации
   ├─ Снимок актуален → чтение JSON в память        3. ds.batch_plan()...preview():
   └─ Снимок устарел / отсутствует →                   ├─ Валидация JSON Schema 2020-12 и секций
      сборка InMemorySnapshot в ОЗУ                    ├─ Кросс-проверка relations внутри батча
      (0 записей в .todoc/index и .todoc/history!)     └─ Вычисление expected_hash и plan_digest
3. Ленивый in-memory ParseCache[(path, hash)]:      4. ds.apply_plan(plan, expected_digest, idempotency_key):
   ├─ Подхват .todoc/cache/parse/*.json (только R)     ├─ Захват .todoc/write.lock (timeout 5s)
   └─ Повторные search/read/stale берут AST из ОЗУ     ├─ Проверка idempotency_key в journal.jsonl
4. Параллельные чтения безопасны (immutable view)      ├─ Повторная сверка всех expected_hash (CAS)
                                                       ├─ Атомарная запись файлов (rollback при сбое!)
                                                       ├─ Сброс ParseCache + запись в journal.jsonl
                                                       ├─ ЕДИНСТВЕННЫЙ rebuild_index() на всю пачку
                                                       └─ Освобождение .todoc/write.lock
```

### 4. Полный эталонный контракт `src/todoc/sdk/__init__.pyi`

Этот стаб спроектирован так, чтобы его можно было целиком помещать в контекст модели (или отдавать по доменам через `todoc_api_stub(domain)`) и проверять через `mypy --strict` и `ty`:

```python
"""Public typed Python Agent API for todoc (compatible with CPython & PTC sandboxes)."""

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Generic, Literal, TypedDict, TypeVar

T = TypeVar("T")

SessionMode = Literal["readonly", "readwrite"]
DetailLevel = Literal["concise", "detailed"]
TypeKind = Literal["dir_type", "doc_type", "entity_type", "relation_type"]
PromptOp = Literal["read", "create", "edit", "delete"]
RelationDirection = Literal["out", "in", "both"]
InteropTarget = Literal["asl", "dmn", "rasa"]
Severity = Literal["error", "warning"]

class TodocSDKError(Exception):
    code: str
    exit_code: int
    path: str | None
    location: dict[str, Any]
    fix_hint: str
    suggested_fixes: list[dict[str, Any]]

class Page(TypedDict, Generic[T]):
    items: list[T]
    total: int
    returned: int
    truncated: bool
    next_cursor: str | None

class CollectResult(TypedDict, Generic[T]):
    items: list[T]
    total: int
    hit_cap: bool

class ResolvedRef(TypedDict):
    dataset_id: str
    path: str
    document_id: str | None
    record_id: str | None
    related_record_ids: list[str]
    fragment: str | None
    format: str | None
    doc_type: str | None
    entity_type: str | None
    hash: str

class SearchHitItem(TypedDict):
    document_id: str
    record_id: str | None
    path: str
    title: str
    doc_type: str
    heading_path: list[str]
    rank: int
    matched_terms: list[str]
    line_start: int
    line_end: int
    snippet: str
    snippet_truncated: bool

class DocProjection(TypedDict, total=False):
    dataset_id: str
    document_id: str
    record_id: str | None
    path: str
    format: Literal["markdown", "json", "csv"]
    doc_type: str
    hash: str
    title: str
    status: str | None
    tags: list[str] | None
    updated: str | None
    related: list[str] | None
    headings: list[dict[str, Any]]
    section: str
    heading_path: list[str]
    line_start: int
    line_end: int
    section_total_lines: int
    truncated: bool
    text: str
    value: Any
    columns: list[str]
    rows: list[dict[str, str]]
    total_rows: int
    matched_rows: int

class RecordItem(TypedDict, total=False):
    dataset_id: str
    record_id: str
    document_id: str | None
    entity_type: str
    path: str
    hash: str
    data: dict[str, Any]

class AggregateResult(TypedDict):
    entity_type: str
    metric: str
    units: str
    group_units: dict[str, str]
    formula: str
    prompt: str
    groups: dict[str, float]
    incoming_ids: list[str]
    completeness: Literal["complete", "filtered"]

class GraphEdge(TypedDict, total=False):
    type_id: str
    direction: Literal["out", "in"]
    source_id: str
    target_id: str
    via: Literal["relation", "mention"]
    fragment: str
    valid_from: str | None
    valid_to: str | None

class StaleItem(TypedDict):
    owner_path: str
    owner_id: str
    owner_kind: Literal["document", "record"]
    dependency_path: str
    status: Literal["changed", "missing", "unresolved", "unreadable", "acknowledged"]
    code: str
    expected_anchor: str
    actual_anchor: str | None
    acknowledged_at: str | None
    ack_reason: str | None

class DiagnosticItem(TypedDict):
    dataset_id: str
    id: str
    code: str
    severity: Severity
    path: str
    location: dict[str, Any]
    evidence: str
    message: str
    suggested_fixes: list[dict[str, Any]]

class PlanOpSummary(TypedDict):
    op: Literal[
        "record.create",
        "record.status",
        "record.undo_relation",
        "doc.new",
        "doc.status",
        "doc.fix_link",
        "doc.reanchor",
        "doc.ack_stale",
        "view.render",
    ]
    target_path: str
    record_id: str | None
    document_id: str | None
    expected_hash: str | None
    new_hash: str
    basis: str
    validations: list[str]

class BatchWritePlanDict(TypedDict):
    schema_version: Literal[1]
    plan_id: str
    dataset_id: str
    plan_digest: str
    items: list[PlanOpSummary]
    # opaque validated payload bound to plan_digest:
    operations: list[dict[str, Any]]

class ApplyPlanResult(TypedDict):
    dataset_id: str
    plan_id: str
    plan_digest: str
    idempotency_key: str
    idempotent_replay: bool
    rev: str | None
    generation_id: str
    applied: list[dict[str, Any]]

class DocsAPI:
    def search(
        self,
        query: str,
        *,
        doc_type: str | None = None,
        tag: str | None = None,
        within: str | None = None,
        include_muted: bool = False,
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
    def links(
        self,
        *,
        broken_only: bool = False,
        within: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> Page[dict[str, Any]]: ...
    def tree(
        self,
        *,
        within: str | None = None,
        max_depth: int | None = None,
        include_muted: bool = False,
    ) -> dict[str, Any]: ...

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
        exclude_fields: Sequence[str] | None = None,
        detail: DetailLevel = "concise",
        limit: int = 200,
        cursor: str | None = None,
    ) -> Page[RecordItem]: ...
    def get(self, ref: str, *, fields: Sequence[str] | None = None) -> RecordItem: ...
    def aggregate(
        self,
        entity_type: str,
        metric_field: str,
        *,
        group_by: str | None = None,
        filters: Mapping[str, Any] | None = None,
        as_of: str | None = None,
    ) -> AggregateResult: ...

class RelationsAPI:
    def neighbors(
        self,
        ref: str,
        *,
        type_id: str | None = None,
        direction: RelationDirection = "both",
        depth: int = 1,
        as_of: str | None = None,
        include_mentions: bool = True,
        limit: int = 100,
    ) -> list[GraphEdge]: ...
    def tree(
        self,
        ref: str,
        *,
        type_id: str | None = None,
        depth: int = 2,
        as_of: str | None = None,
        include_mentions: bool = True,
        limit: int = 100,
    ) -> dict[str, Any]: ...

class StalenessAPI:
    def inspect(
        self,
        *,
        owner_ref: str | None = None,
        include_acknowledged: bool = False,
    ) -> list[StaleItem]: ...

class TypesAPI:
    def list(self, *, kind: TypeKind | None = None) -> list[dict[str, Any]]: ...
    def get(self, type_id: str, *, kind: TypeKind | None = None) -> dict[str, Any]: ...
    def prompt(self, type_id: str, *, op: PromptOp = "create") -> str: ...

class FlowsAPI:
    def inspect(self, flow_ref: str, *, start_at: str | None = None) -> dict[str, Any]: ...
    def walk(self, flow_ref: str, *, start_at: str | None = None) -> list[dict[str, Any]]: ...
    def walk_all(self, flow_ref: str, *, start_at: str | None = None) -> list[list[dict[str, Any]]]: ...

class InteropAPI:
    def preview_export(self, target: InteropTarget, *, ref: str | None = None) -> dict[str, Any]: ...
    def check_drift(self) -> list[DiagnosticItem]: ...

class SkillsAPI:
    def list(self, *, section: str | None = None, include_muted: bool = False) -> list[dict[str, Any]]: ...
    def read(self, skill_name_or_path: str, *, resource: str | None = None, budget_bytes: int | None = 8000) -> dict[str, Any]: ...

class HistoryAPI:
    def log(self, *, path: str | None = None, change_id: str | None = None, tag: str | None = None, limit: int = 20, cursor: str | None = None) -> Page[dict[str, Any]]: ...
    def show(self, rev: str, *, path: str | None = None) -> dict[str, Any]: ...
    def diff(self, rev_a: str, rev_b: str | None = None, *, path: str | None = None, max_lines: int = 500) -> dict[str, Any]: ...
    def blame(self, path: str, *, section: str | None = None) -> list[dict[str, Any]]: ...
    def timeline(self, *, as_of: str | None = None, path: str | None = None, limit: int = 200) -> dict[str, Any]: ...
    def pack_context(self, *, change_id: str | None = None, tag: str | None = None, budget_bytes: int = 8000, with_diff: bool = False) -> dict[str, Any]: ...

class StateAPI:
    def get(self, key: str) -> str | None: ...
    def list(self) -> dict[str, str]: ...
    def set(self, key: str, value: str) -> dict[str, Any]: ...
    def unset(self, key: str) -> bool: ...

class BatchPlanBuilder:
    def create_record(self, entity_type: str, data: Mapping[str, Any]) -> "BatchPlanBuilder": ...
    def set_record_status(self, ref: str, status: str) -> "BatchPlanBuilder": ...
    def undo_relation(self, record_ref: str, pointer: str) -> "BatchPlanBuilder": ...
    def new_doc(
        self,
        title: str,
        *,
        doc_type: str | None = None,
        dir_path: str = "inbox",
        rel_path: str | None = None,
        template: str | None = None,
    ) -> "BatchPlanBuilder": ...
    def set_doc_status(self, ref: str, status: str) -> "BatchPlanBuilder": ...
    def fix_link(self, doc_ref: str, *, diagnostic_id: str | None = None, old_target: str | None = None, new_target: str | None = None) -> "BatchPlanBuilder": ...
    def reanchor_stale(self, owner_refs: Sequence[str]) -> "BatchPlanBuilder": ...
    def acknowledge_stale(self, owner_ref: str, *, reason: str) -> "BatchPlanBuilder": ...
    def render_flow_view(self, flow_ref: str, *, out_path: str | None = None) -> "BatchPlanBuilder": ...
    def render_interop_export(self, target: InteropTarget, *, ref: str | None = None, out_path: str) -> "BatchPlanBuilder": ...
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
    flows: FlowsAPI
    interop: InteropAPI
    skills: SkillsAPI
    history: HistoryAPI
    state: StateAPI

    def resolve(self, ref: str) -> ResolvedRef: ...
    def explain_path(self, rel_path: str) -> dict[str, Any]: ...
    def validate(
        self,
        *,
        within: str | None = None,
        severity: Severity | None = None,
        code_prefix: str | None = None,
    ) -> list[DiagnosticItem]: ...
    def collect_all(
        self,
        fetch_page: Callable[[str | None], Page[T]],
        *,
        max_items: int = 500,
    ) -> CollectResult[T]: ...
    def batch_plan(self) -> BatchPlanBuilder: ...
    def apply_plan(
        self,
        plan: BatchWritePlanDict,
        *,
        expected_digest: str,
        idempotency_key: str,
    ) -> ApplyPlanResult: ...
    def sync(
        self,
        paths: Sequence[str] = (),
        *,
        expected_hash: str | None = None,
        allow_derived: bool = False,
    ) -> dict[str, Any]: ...
    def close(self) -> None: ...
    def __enter__(self) -> "DatasetSession": ...
    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None: ...

class WorkspaceSession:
    sessions: dict[str, DatasetSession]
    def search_all(self, query: str, *, doc_type: str | None = None, limit_per_root: int = 5) -> list[dict[str, Any]]: ...
    def query_all_records(self, *, entity_type: str | None = None, filters: Mapping[str, Any] | None = None, limit_per_root: int = 50) -> list[RecordItem]: ...
    def validate_all(self) -> dict[str, list[DiagnosticItem]]: ...
    def __enter__(self) -> "WorkspaceSession": ...
    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None: ...

def open_session(
    root: str | Path = ".",
    *,
    mode: SessionMode = "readonly",
    actor: str = "agent:sdk",
    change_id: str | None = None,
) -> DatasetSession: ...

def open_workspace(
    roots: Sequence[str | Path],
    *,
    mode: SessionMode = "readonly",
) -> WorkspaceSession: ...
```

### 5. Референсная реализация четырёх критических узлов `src/todoc/sdk/`

#### 5.1. Чистый снимок в памяти без побочных эффектов (`src/todoc/sdk/snapshot.py`)

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from todoc.adapters.formats.markdown import MarkdownDoc, doc_from_payload, parse_markdown
from todoc.application.registry import corpus_digest, read_parse_cache
from todoc.service import DatasetContext


@dataclass
class SessionSnapshot:
    """Неизменяемый на чтении снимок датасета + сессионный кэш разбора в ОЗУ."""

    dataset_id: str
    root: Path
    payload: dict[str, Any]
    ephemeral: bool  # True, если собран в ОЗУ без записи в .todoc/index/
    _md_cache: dict[tuple[str, str], MarkdownDoc] = field(default_factory=dict)

    @classmethod
    def load_readonly(cls, ctx: DatasetContext) -> "SessionSnapshot":
        stats = ctx.store.read_stats()
        _, files = ctx.scan(stats=stats)
        cfg_digest = ctx.store.config_digest()
        digest = corpus_digest(files, cfg_digest)
        meta = ctx.store.read_current_meta()
        if meta is not None and meta.get("corpus_digest") == digest:
            published = ctx.store.load_current()
            if published is not None:
                return cls(ctx.dataset_id, ctx.root, published, ephemeral=False)
        # Индекс устарел или отсутствует: собираем ТОЛЬКО в памяти (0 байт на диск!)
        folders, documents, records, relations, diagnostics = ctx.scan_and_validate()
        mentions = ctx.build_mentions(documents, records)
        ephemeral_payload: dict[str, Any] = {
            "generation_id": "in-memory",
            "corpus_digest": digest,
            "folders": folders,
            "documents": documents,
            "records": records,
            "relations": relations,
            "diagnostics": diagnostics,
            "mentions": mentions,
        }
        return cls(ctx.dataset_id, ctx.root, ephemeral_payload, ephemeral=True)

    def get_markdown(self, rel_path: str, content_hash: str) -> tuple[str, MarkdownDoc]:
        """Единая точка чтения и разбора Markdown без двойного парсинга."""
        text = (self.root / rel_path).read_text(encoding="utf-8")
        key = (rel_path, content_hash)
        cached = self._md_cache.get(key)
        if cached is not None:
            return text, cached
        disk_cached = read_parse_cache(self.root, rel_path, content_hash)
        if disk_cached is not None:
            try:
                parsed = doc_from_payload(disk_cached)
                self._md_cache[key] = parsed
                return text, parsed
            except (KeyError, TypeError, ValueError):
                pass
        parsed = parse_markdown(text)
        self._md_cache[key] = parsed
        return text, parsed
```

#### 5.2. Детерминированный кросс-резолвер идентификаторов (`src/todoc/sdk/resolver.py`)

```python
from __future__ import annotations

from typing import Any

from todoc.application.sync import normalize_sync_path
from todoc.sdk.errors import TodocSDKError
from todoc.sdk.snapshot import SessionSnapshot


def resolve_ref(snap: SessionSnapshot, ref: str) -> dict[str, Any]:
    """Разрешает document_id, record_id или rel_path (с опциональным #fragment)."""
    raw_base, sep, fragment = ref.strip().partition("#")
    if not raw_base:
        raise TodocSDKError("usage.empty_ref", 2, None, "Пустой идентификатор объекта.",
                            "Передайте document_id ('doc:...'), record_id ('task:...') или относительный путь.")

    docs = snap.payload["documents"]
    records = snap.payload["records"]

    # Индекс обратных ссылок source_path -> [record_id, ...]
    by_source: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        src = (r.get("data") or {}).get("source_path")
        if isinstance(src, str) and src:
            by_source.setdefault(src, []).append(r)

    # 1. Точное совпадение document_id
    doc = next((d for d in docs if d.get("document_id") == raw_base), None)
    if doc is not None:
        linked = by_source.get(doc["path"], [])
        return {
            "dataset_id": snap.dataset_id,
            "path": doc["path"],
            "document_id": doc["document_id"],
            "record_id": linked[0]["record_id"] if len(linked) == 1 else None,
            "related_record_ids": [r["record_id"] for r in linked],
            "fragment": fragment if sep else None,
            "format": doc.get("format"),
            "doc_type": doc.get("doc_type"),
            "entity_type": linked[0]["entity_type"] if len(linked) == 1 else None,
            "hash": doc["hash"],
        }

    # 2. Точное совпадение record_id
    rec = next((r for r in records if r.get("record_id") == raw_base), None)
    if rec is not None:
        src_path = (rec.get("data") or {}).get("source_path")
        linked_doc = next((d for d in docs if d.get("path") == src_path), None) if src_path else None
        return {
            "dataset_id": snap.dataset_id,
            "path": linked_doc["path"] if linked_doc else rec["path"],
            "document_id": linked_doc["document_id"] if linked_doc else None,
            "record_id": rec["record_id"],
            "related_record_ids": [rec["record_id"]],
            "fragment": fragment if sep else None,
            "format": linked_doc.get("format") if linked_doc else "json",
            "doc_type": linked_doc.get("doc_type") if linked_doc else None,
            "entity_type": rec["entity_type"],
            "hash": rec["hash"],
        }

    # 3. Относительный путь внутри DATA_ROOT (с проверкой containment)
    rel_path = normalize_sync_path(snap.root, raw_base)
    doc = next((d for d in docs if d.get("path") == rel_path), None)
    rec = next((r for r in records if r.get("path") == rel_path), None)
    if doc is not None or rec is not None:
        linked = by_source.get(rel_path, [])
        primary_rec = rec or (linked[0] if len(linked) == 1 else None)
        return {
            "dataset_id": snap.dataset_id,
            "path": rel_path,
            "document_id": doc["document_id"] if doc else None,
            "record_id": primary_rec["record_id"] if primary_rec else None,
            "related_record_ids": [r["record_id"] for r in linked] or ([rec["record_id"]] if rec else []),
            "fragment": fragment if sep else None,
            "format": doc["format"] if doc else "json",
            "doc_type": doc["doc_type"] if doc else None,
            "entity_type": primary_rec["entity_type"] if primary_rec else None,
            "hash": (doc or rec)["hash"],  # type: ignore[index]
        }

    raise TodocSDKError(
        code="sdk.ref_not_found",
        exit_code=3,
        path=raw_base,
        message=f"Объект {raw_base!r} не найден ни среди документов, ни среди записей.",
        fix_hint="Вызовите ds.docs.search(...) или ds.records.query(...) для получения точного идентификатора.",
    )
```

#### 5.3. Пакетная валидация с перекрёстными связями, атомарным откатом и `idempotency_key` (`src/todoc/sdk/batch.py`)

Ключевая тонкость `todoc`: при создании пачки из `N` записей запись `B` часто ссылается через `relations` на запись `A`, которая **тоже создаётся в этой же пачке** и ещё не существует на диске. `BatchPlanBuilder.preview()`:
1. Собирает виртуальное множество известных идентификаторов `known_ids = existing_record_ids | existing_doc_ids | staged_new_ids` и словарь типов `known_types = existing_types | staged_new_types`.
2. Для каждой операции вызывает стандартный `create_record_plan()` / `create_document_plan()`, но дополнительно прогоняет валидатор `relation_types` против объединённого `known_types`, отвергая висячие ссылки (`relation.dangling_target`) и неверные `endpoints` ещё на этапе `preview()`.
3. Вычисляет канонический `plan_digest = "sha256:" + sha256(canonical_json(operations))`.
4. В `apply_plan()`:
   - захватывает `.todoc/write.lock`;
   - ищет в последних событиях `journal.jsonl` пару `(idempotency_key, plan_digest)` — если найдена, возвращает идемпотентный успех без записи; если `idempotency_key` найден с другим `plan_digest` — бросает `write.idempotency_conflict`;
   - сохраняет в памяти байтовые образы `before_bytes` всех целевых файлов;
   - выполняет серию `atomic_write`; если на K-м файле возникает `OSError` или гонка хеша, восстанавливает все предыдущие K−1 файлов обратно (удаляя вновь созданные и возвращая `before_bytes` для изменённых);
   - пишет событие в журнал истории и вызывает `ctx.rebuild_index(force=True, observe=False)` ровно один раз.

#### 5.4. Адаптер безопасной песочницы `pydantic-monty` / MCP Code Mode (`src/todoc/sdk/sandbox.py`)

Для интеграции в облачные харнесы, MCP Code Mode и будущий веб-интерфейс (`web-ui.after.md`) обёртка `sandbox.py` регистрирует поверх `DatasetSession(mode="readonly")` плоский набор безопасных внешних функций (поскольку в изолированных интерпретаторах проще и надёжнее пробрасывать именованные функции, чем сложные иерархии прокси-объектов) и контролирует размер `stdout`:

```python
MAX_SANDBOX_STDOUT_CHARS = 8_000


def truncate_sandbox_output(stdout: str, max_chars: int = MAX_SANDBOX_STDOUT_CHARS) -> dict[str, Any]:
    if len(stdout) <= max_chars:
        return {"stdout": stdout, "truncated": False, "total_chars": len(stdout)}
    return {
        "stdout": stdout[:max_chars],
        "truncated": True,
        "total_chars": len(stdout),
        "guidance": (
            f"Вывод усечён до {max_chars} из {len(stdout)} символов. "
            "Не печатайте сырые выборки целиком: сгруппируйте или отфильтруйте "
            "данные внутри Python-скрипта и выведите только агрегированный итог."
        ),
    }
```

---

## III. Постулаты безопасного вызова Python API агентом и рантаймами исполнения

1. **По умолчанию открывать `mode="readonly"` в контекстном менеджере `with open_session(...) as ds:`.** Пишущий режим `mode="readwrite"` запрашивать только на шаге `apply_plan()` после явной сборки и проверки `BatchWritePlanDict`.
2. **Проверять контракт по `.pyi`-стабу до генерации скрипта.** Не угадывать имена аргументов по флагам CLI (`budget_bytes`, а не `--budget`; `entity_type`, а не `--type`; `ref`, а не `--id`). При подключённом `ty` / `mypy` валидировать типы сгенерированного скрипта статически до запуска.
3. **Никогда не обходить `todoc.sdk` прямым чтением или записью файлов внутри `.todoc/`.** Каталоги `.todoc/index/`, `.todoc/cache/` и `.todoc/history/` — внутреннее производное состояние движка; прямое изменение JSON внутри них ломает инварианты дайджеста и журнала.
4. **Считать все строки из `DATA_ROOT` недоверенными данными (`P10`).** Заголовки заметок, поля `prompt`, `statement`, `description`, `agent_instructions` могут содержать случайный или враждебный текст (prompt injection). Агент не должен конкатенировать строки из записей в shell-команды, системные промпты привилегированного уровня или динамический `exec()`.
5. **Проверять `truncated` в каждом ответе `Page[T]` и `DocProjection`.** Если `page["truncated"] is True`, агент обязан либо долистать через `ds.collect_all(..., max_items=...)`, либо явно сообщить пользователю, что расчёт проведён по выборке `returned` из `total`, не выдавая частичный срез за полный корпус (`P7`).
6. **Агрегировать и сжимать данные внутри Python до `print()`.** Печатать в `stdout` структурированный `json.dumps(summary, ensure_ascii=False)` только с теми полями, которые нужны для ответа пользователю или следующего решения.
7. **Не ловить `Exception: pass` вслепую вокруг методов `todoc.sdk`.** Если `ds.resolve()` или `batch.preview()` поднимают `TodocSDKError`, скрипт должен либо обработать конкретный `err.code`, либо позволить исключению всплыть с `err.fix_hint`, чтобы модель увидела причину ошибки и не продолжила работу по пустым данным.
8. **Генерировать детерминированный `idempotency_key` из смысла задачи, а не `uuid4()` внутри скрипта.** Если `idempotency_key = str(uuid.uuid4())` вычисляется внутри самого перезапускаемого PTC-скрипта, при ретрае ключ будет новым и защита от дублей не сработает. Ключ должен либо передаваться снаружи от оркестратора (например, ID шага диалога), либо строиться детерминированно от целевого набора идентификаторов.
9. **Для изолированного исполнения чужого/облачного кода использовать настоящую песочницу, а не AST-фильтр CPython.** В веб-сервере и облачном MCP-адаптере исполнять сгенерированный моделью Python-код в Rust-интерпретаторе `pydantic-monty` (без ФС, сети и `os.environ`, с лимитами времени `<= 15 с` и памяти `<= 128–256 МиБ`) или в одноразовой микро-ВМ / rootless-контейнере с `--network=none`. Не использовать самописные `eval`-песочницы поверх стандартного `ast` CPython (обходятся через интроспекцию фреймов и дескрипторов).
10. **Нормализовать экранирование переносов строк перед запуском в tool-рантайме.** Некоторые модели при передаче многострочного Python-скрипта в JSON-аргумент `code` генерируют двойное экранирование `\\n` вместо переводов строк, вызывая `SyntaxError` на первой строке. Харнес `run_code` должен распознавать однострочный ввод с литеральными `\n` (при ошибке `ast.parse` исходной строки и успешном `ast.parse` разэкранированной) до возврата синтаксической ошибки модели.
11. **Соблюдать совместимость с ограничениями провайдерских PTC-протоколов.** При публикации инструментов `todoc` в нативный Claude Programmatic Tool Calling (`code_execution_20260120` / `code_execution_20260521`) учитывать протокольные ограничения: не включать одновременно несовместимый `strict: true` и рекурсивные `$ref`, возвращать текстово-сериализуемый JSON, удерживать `container` ID на время паузы tool-вызова и выставлять `allowed_callers: ["direct"]` для любых мутирующих операций.
12. **Финализировать сессию проверкой инвариантов.** После серии изменений через `apply_plan()` или прямой правки файлов с `todoc sync` удостовериться, что `ds.validate()` (или `todoc validate --all`) возвращает 0 ошибок, а локальные ссылки целы (`ds.docs.links(broken_only=True)["total"] == 0`).

---

## IV. Оценка качества Python API, расширение `bench/` и pre-release чек-лист

Существующий бенчмарк [`bench/run_benchmark.py`](../../bench/run_benchmark.py) проверяет 30 критериев CLI (`K1`–`K30`, текущий результат `30.0 / 30` в [`bench/results/benchmark.md`](../../bench/results/benchmark.md)). При вводе `todoc.sdk` оценка должна охватывать не только unit-покрытие, но и реальную эффективность агентских сценариев:

### 1. Новые автоматизируемые критерии для `bench/` (`K31`–`K40`)

| Код | Проверяемый инвариант Python API / PTC | Порог прохождения |
|---|---|---|
| **K31** | **Чистота `mode="readonly"`:** на корпусе с намеренно устаревшим индексом серия вызовов `search`, `read`, `records.query`, `relations.neighbors`, `staleness.inspect` не создаёт и не меняет ни одного файла в `DATA_ROOT` и `.todoc/` | `0` изменённых/созданных файлов и неизменный `journal.jsonl` |
| **K32** | **Семантический паритет SDK и CLI (`P11`):** результаты `docs.search`, `docs.read`, `records.query`, `records.aggregate`, `relations.tree`, `validate` идентичны полю `data` соответствующих команд CLI на эталонном корпусе | `100%` совпадение идентификаторов, порядка и чисел |
| **K33** | **Кросс-резолв `ds.resolve()` (`BUG-013`):** разрешение по `rel_path`, `document_id` и `record_id` (через `source_path`) в обе стороны + ошибка `sdk.ref_not_found` на несуществующий ключ | Все 4 проверки `pass` |
| **K34** | **Скорость тёплой сессии (`ParseCache` в ОЗУ):** 5 последовательных вызовов `ds.docs.search()` по разным запросам внутри одной `DatasetSession` на корпусе `>= 250` документов | 2-й..5-й вызовы `< 15 мс` каждый (`parse_markdown` вызван `<= 1` раза на файл) |
| **K35** | **Пакетная связность `BatchPlanBuilder`:** создание в одном батче записи `flow` и ссылающейся на неё записи `rule` проходит `preview()` при валидной связи и отказывает с `relation.dangling_target` при битой цели | `0` файлов на диске после `preview()`; точный отказ до записи |
| **K36** | **Атомарность и идемпотентность `apply_plan()`:** (а) повтор с тем же `idempotency_key` и `plan_digest` возвращает `idempotent_replay=True` без дубля в `journal.jsonl`; (б) искусственный сбой записи на 3-м файле из 4 откатывает первые 2 файла и оставляет корпус чистым | `0` частично записанных батчей; `1` пересборка индекса на успешный батч |
| **K37** | **Межпроцессная блокировка `.todoc/write.lock`:** при удержании лока первым процессом второй процесс с малым `lock_timeout_sec` получает детерминированный `write.dataset_locked` (`exit_code=5`), не повреждая `CURRENT.json` | Индекс и журнал валидны после конкурентного теста |
| **K38** | **Статическая полнота `.pyi` и компактность стаба:** проверка `mypy --strict` (и `ty` при наличии) на наборе эталонных агентских скриптов + замер размера `src/todoc/sdk/__init__.pyi` | `0` ошибок типов; объём стаба `<= 1 500` токенов |
| **K39** | **Самодокументируемость `TodocSDKError` (`P15`):** ошибки схемы, недопустимого статуса, невалидного `as_of`, выхода за `DATA_ROOT` несут непустой локализованный `fix_hint` без утечки абсолютных системных путей | `100%` проверяемых кодов содержат исправимый `fix_hint` |
| **K40** | **Экономия полного агентского цикла (CLI chain vs PTC SDK):** замер суммарных символов/токенов выдачи и числа шагов на 5 многошаговых задачах (триаж багов, граф зависимостей, производная метрика, ре-анкоринг `stale`, пакет из 10 записей) | Снижение объёма промежуточных данных в контексте **`>= 70%`**, число ходов `1..2` |

### 2. Минимальный pre-release чек-лист перед открытием `todoc.sdk`

- [ ] В ядро `[project.dependencies]` не добавлено новых сторонних пакетов; покрытие ветвлений `pytest --cov=todoc --cov-branch` составляет **100%**.
- [ ] Из `src/todoc/cli.py` вынесены в `src/todoc/application/` проекционное чтение `docs_read`, фильтры `until`/`relation`, проверки статусов `docs_status`/`records_status`, инвентаризация `docs_links` и сборка дерева `docs_tree`.
- [ ] `open_session(..., mode="readonly")` гарантированно не мутирует `.todoc/index/` и `.todoc/history/` даже при отсутствии или устаревании индекса.
- [ ] Пакет содержит `src/todoc/py.typed` и актуальный `src/todoc/sdk/__init__.pyi`, проходящий `mypy --strict` и не расходящийся с рантаймом.
- [ ] Все методы возвращают исключительно JSON-сериализуемые структуры (`TypedDict`) с относительными POSIX-путями и честными полями `total` / `returned` / `truncated` / `next_cursor`.
- [ ] `ds.resolve()` закрывает тройное пространство имён (`document_id` ↔ `record_id` ↔ `rel_path`), а `ds.staleness.inspect()` возвращает готовый `actual_anchor` для ре-анкоринга.
- [ ] `BatchPlanBuilder` проверяет схемы и перекрёстные связи внутри пачки до записи, защищает каждый файл через `expected_hash`, удерживает `.todoc/write.lock`, поддерживает `idempotency_key` и пересобирает индекс ровно один раз на батч.
- [ ] 12 деструктивных и инфраструктурных команд уровня Tier D (`revert`, `change apply/revert/archive`, `history gc/adopt`, `init` и др.) исключены из агентского PTC-стаба.
- [ ] Обновлён корневой [`SKILL.md`](../../SKILL.md) коротким правилом выбора между `Write`/`Edit` + `todoc sync`, простым CLI и `todoc.sdk`.
- [ ] Пройдены `todoc validate --root demo --all` (`0` диагностик), `python3 tools/linkcheck.py` (`broken 0`) и расширенный прогон `bench/run_benchmark.py`.

---

## Источники и связанные документы

### Внутренние нормативные и проектные документы `todoc`
- [`docs/plan/constitution.md`](../plan/constitution.md) — конституция продукта (`P1`–`P15`, `FR`/`NFR`), приоритетный норматив.
- [`docs/guides/cli-for-agents.md`](cli-for-agents.md) и [`docs/guides/mcp-for-agents.md`](mcp-for-agents.md) — парные руководства по проектированию CLI и MCP для агентов.
- [`docs/guides/markdown-knowledge-for-agents.md`](markdown-knowledge-for-agents.md) — правила организации Markdown-корпуса знаний для агентов.
- [`docs/research/programmatic-tool-calling-and-python-api.md`](../research/programmatic-tool-calling-and-python-api.md) — эмпирические замеры на `demo/` и ревизия всех 64 команд CLI по уровням Tier A–D.
- [`docs/plan/todoc-master-refactoring-plan.md`](../plan/todoc-master-refactoring-plan.md) и [`docs/research/cli-architecture-refactoring.md`](../research/cli-architecture-refactoring.md) — дорожная карта декомпозиции `cli.py` и выделения транспортно-нейтрального application-фасада (`З0-S`, `Э1`–`Э12`).
- [`docs/plan/mcp-adapter.after.md`](../plan/mcp-adapter.after.md) и [`docs/plan/web-ui.after.md`](../plan/web-ui.after.md) — целевые адаптеры, переиспользующие сессии `todoc.sdk`.
- [`docs/state/11-known-issues.md`](../state/11-known-issues.md) и реестр `demo/bugs/` ([BUG-011](../../demo/bugs/bug-011-dreyf-derived-from-pri-smene-statusa-tela-ishodnika-trebuet-ruchnogo-re-ankoringa.md), [BUG-012](../../demo/bugs/bug-012-history-revizii-mutiruyuschih-komand-zagryaznyayut-git-status.md), [BUG-013](../../demo/bugs/bug-013-neodnorodnye-id-i-output-kontrakty-rezolv-identifikatora-trebuet-ruchnogo-grep.md), [BUG-015](../../demo/bugs/bug-015-yaml-lite-front-matter-ne-obrabatyvaet-backslash-escape-kavychek.md), [BUG-016](../../demo/bugs/bug-016-filtry-records-query-ne-dokumentirovany-v-spravkah.md), [DESIGN-Q01](../../demo/bugs/design-q01-terminalnyy-status-zapisi-guard-procedurnyy-dvizhok-molchit.md), [DESIGN-Q02](../../demo/bugs/design-q02-review-first-dvoynoy-vyzov-stoimost-dlya-agenta-protiv-kontrolya.md)).

### Стандарты языка Python и форматов данных
- [PEP 484 — Type Hints](https://peps.python.org/pep-0484/) и [PEP 561 — Distributing and Packaging Type Information](https://peps.python.org/pep-0561/) — стандарт `.pyi`-стабов и маркера `py.typed`.
- [PEP 589 — TypedDict: Type Hints for Dictionaries with a Fixed Set of Keys](https://peps.python.org/pep-0589/) — строгая типизация JSON-совместимых словарей.
- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12/json-schema-core.html), [RFC 8259 (JSON)](https://www.rfc-editor.org/rfc/rfc8259.html), [RFC 6901 (JSON Pointer)](https://www.rfc-editor.org/rfc/rfc6901).

### Исследования и инженерные руководства по Programmatic Tool Calling / Code Mode
- [Anthropic — Programmatic Tool Calling Documentation](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling) и [Advanced Tool Use](https://www.anthropic.com/research/advanced-tool-use) — протокольная модель PTC (`allowed_callers`, контейнеры, экономия промежуточных токенов).
- [Anthropic — Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) и [Writing effective tools for AI agents](https://www.anthropic.com/engineering/writing-tools-for-agents) — прогрессивное раскрытие модулей, проектирование высокосигнальных ответов и исправимых ошибок.
- [Pydantic — Why Code Mode is the Future](https://pydantic.dev/articles/why-code-mode-is-the-future) и [`pydantic/monty`](https://github.com/pydantic/monty) — градированный бенчмарк Code Mode, пороги кроссовера по числу элементов, риск повторного запуска мутаций (*rerun write duplication*) и архитектура изолированного Rust-интерпретатора подмножества Python со статическим тайпчекером `ty`.
- [Patel et al. — The Bitter Lesson of Tool Calling (`arXiv:2608.06370`)](https://arxiv.org/abs/2608.06370) — сравнение типизированных `.pyi`-стабов Python с JSON Schema tool-calling на многошаговых цепочках и больших веерных обходах (`fan-out`).
- [Cloudflare — Code Mode](https://blog.cloudflare.com/code-mode/) — двухшаговый паттерн `search()` + `execute()` поверх типизированного SDK в изолированном рантайме без прямого доступа к сети.
