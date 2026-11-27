---
id: doc:plan/bmad-wave-planning-skills.md
title: "Пакет скилов волнового планирования идей без переделок (адаптация BMAD Method v6/v7 под todoc + doc_type roadmap)"
doc_type: plan
lang: ru
created: 2026-11-26
updated: 2026-11-26
status: active
wave: 0
covers: ["doc:ideas/wave-planning-cli-helpers.md", "doc:ideas/cli-model-guidance-and-hint-catalog.md"]
derived_from: [".research/bmad-v6-wave-planning-skills.md#section:4. Итоговая архитектура адаптации под todoc и анализ сущностей@sha256:e0b942f44e04559ef6751bf1a1a453e9eb9e6def5ba3c8bcac9a644cf4bbad09", ".research/bmad-v6-wave-planning-skills.md#section:5. Калибровка под сильные и слабые модели и стандарт читаемости волны для занятого человека@sha256:0b675f34e2b62ad483abb3a15dade2ace0b0852dfad5cd4957ffbb09efd504cc", "ideas/skills-engine.md#section:Предложение@sha256:9c7ffd3896853242e604ce249e0cc6d86182834d2c5dec888e305304111090a9", "ideas/wave-planning-cli-helpers.md#section:Предложение@sha256:ad7dd083f7b0d1494bba62527c5d756633b49cb6e4df512754bd78a502a7824a", "ideas/cli-model-guidance-and-hint-catalog.md#section:Предложение@sha256:144a217da54e33ba356493d29189b53e707e3d170322047ce15b9260ee88cbe4"]
tags: [plan, bmad, gsd, spec-kit, skills, roadmap, planning, cli]
related: ["[[bmad-v6-wave-planning-skills]]", "[[wave-planning-cli-helpers]]", "[[cli-model-guidance-and-hint-catalog]]", "[[constitution]]", "[[skills-engine]]", "[[скилы-взаимодействия--захват--план--исполнение--переходы--жизненный-цикл]]", "[[type-naming-and-state-dir]]", "[[entity-to-folder]]", "[[multi-project-workspace]]", "[[toggleable-rules]]"]
---

# Волна 0: Конвейер планирования волн без переделок (6 скилов `process/bmad`, `doc_type: roadmap` и CLI-механика волн) — план реализации

> **Резюме волны для занятого человека (без погружения в контекст):**
> - **Суть простыми словами:** добавляем в `todoc` готовый набор из 6 рабочих скилов и 5 быстрых команд терминала, которые собирают десятки разрозненных идей в понятную очерёдность этапов («волн»), чтобы новые доработки не заставляли переписывать вчерашний код.
> - **Зачем делаем сейчас:** в бэклоге уже накопилось больше десятка крупных идей по развитию движка; если делать их по одной вслепую, одни и те же таблицы и команды придётся переделывать по три-четыре раза.
> - **Что получим на выходе:** 1) карту волн с понятным человеческим описанием каждого этапа за 20 секунд чтения; 2) автоматическую проверку забытых идей и пересечений по файлам одной командой; 3) единый процесс планирования и приёмки, который не душит сильную ИИ-модель бюрократией и даёт точные шаблоны более слабой модели.
> - **Чего в этой волне ТОЧНО НЕ делаем:** в рамках этого плана мы настраиваем сам инструмент планирования (скилы, шаблон карты волн и команды-помощники), но ещё не переписываем поисковое хранилище, теги и мульти-проектность — они пойдут следующими волнами уже по созданной карте.

> **Исполнителю (агенту):** план самодостаточен — читай его, а не историю сессии.
> Работай по задачам сверху вниз; шаги отмечаются чекбоксами (`- [ ]`) в том же
> коммите, который делает шаг. Начинай всегда с первого неотмеченного.

**Цель:** внедрить в `demo/skills/process/bmad/<skill-name>/SKILL.md` пакет из **6 процессных скилов** на базе `BMAD Method v6.12.4/v7` + `GSD` + `GitHub Spec Kit` + `OpenSpec` (с калибровкой степеней свободы по `Anthropic Agent Skills` и `SkillsBench`), легковесный тип документа `doc_type: roadmap`, дословный человекопонятный стандарт карточки каждой волны, маршрутизацию из `todoc-plan` и детерминированные CLI-команды `todoc` (`stale anchor/reanchor`, `stale --git-range`, `plan portfolio`, `plan bind`, секционный `docs edit`).
**Спека:** [Исследование скилов волнового синтеза идей](../.research/bmad-v6-wave-planning-skills.md) (`doc:.research/bmad-v6-wave-planning-skills.md`), [Идея: CLI-команды волнового планирования](../ideas/wave-planning-cli-helpers.md) (`doc:ideas/wave-planning-cli-helpers.md`), [Идея: поле guidance и i18n-каталог подсказок CLI](../ideas/cli-model-guidance-and-hint-catalog.md) (`doc:ideas/cli-model-guidance-and-hint-catalog.md`), [Конституция P15](constitution.md) (`doc:constitution`), [Идея: хранилище-движок скилов](../ideas/skills-engine.md) (`doc:skills-engine-idea`).
**Стек:** Python 3.11 (стандартная библиотека + `click`, без новых runtime-зависимостей; дескрипторы `.todoc/` + стандарт Agent Skills `SKILL.md` + `pytest`/`CliRunner` со `100%` branch coverage в `src/`).

## 1. Критерии успеха

1. В `demo/.todoc/doc_types/roadmap/` зарегистрирован тип `doc_type: roadmap` (`1` слово `snake_case`), а во front matter `doc_type: plan` поддержан опциональный волновой контракт (`roadmap`, `wave`, `covers`, `depends_on_waves`, `files_touched`) без создания лишних `entity_type: wave` или `doc_type: wave_plan`.
2. Во всех шаблонах и гейтах закреплён **обязательный двухслойный формат карточки волны**: говорящий заголовок результата + 4 тезисных пункта простыми словами для занятого человека без погружения в контекст, и только ниже — технический паспорт для агента и CLI; отсутствие заголовка волны или человеческого резюме ловится проверкой в `todoc plan portfolio` и `readiness-gate.md`.
3. В CLI `todoc` реализованы и покрыты **`100%` branch coverage** команды детерминированной механики волн (`todoc stale anchor`, `todoc stale reanchor`, `todoc stale --git-range`, `todoc plan portfolio`, `todoc plan bind`, повторяющийся `--id` в `todoc docs status`, а также `replace_section` / `append_section` в `todoc docs edit`).
4. В `demo/skills/process/bmad/<skill-name>/SKILL.md` развёрнуты **все 6 скилов** (`bmad-forge-idea`, `bmad-architecture-spine`, `bmad-slice-roadmap`, `bmad-wave-plan`, `bmad-adversarial-review`, `bmad-wave-retro`), откалиброванные одновременно под сильные и слабые модели: адаптивная маршрутизация `Quick / Standard / Full Portfolio` из `todoc-plan`, высокая свобода на архитектурный синтез + жёсткие шаблоны и одноуровневые заполненные примеры `references/worked-example.md`.
5. `pytest` зелёный (`100%` branch coverage по новым и изменённым модулям `src/todoc/`), `todoc validate --root demo --all` — `0` диагностик, `todoc stale --root demo` — `0` устаревших документов, `tools/linkcheck.py` — `0` битых ссылок.

## 2. Вне скоупа

- Перенос чужого рантайма `_bmad/scripts/*.py`, `bmod.toml`, `tickets.toml` из `BMAD-METHOD` или Node-скриптов `gsd-tools.cjs` из `GSD` — **не делаем**: вся механика реализуется нативно в `src/todoc/`.
- Создание отдельных типов `entity_type: wave` (JSON) или `doc_type: wave_plan` — **не делаем** (обоснование в разделе 4.1).
- Исполнение самой дорожной карты по остальным архитектурным идеям движка (`sqlite-storage-drivers`, `multi-project-workspace`, `toggleable-rules` и др.) — выполняется следующим шагом уже с помощью созданных скилов и CLI-команд.

## 3. Глобальные ограничения

- Лицензионная чистота: заимствуемые практики берутся из открытых MIT-репозиториев ([`bmad-code-org/BMAD-METHOD`](https://github.com/bmad-code-org/BMAD-METHOD), [`gsd-build/get-shit-done`](https://github.com/gsd-build/get-shit-done), [`github/spec-kit`](https://github.com/github/spec-kit), [`Fission-AI/OpenSpec`](https://github.com/Fission-AI/OpenSpec), [`anthropics/skills`](https://github.com/anthropics/skills)); в `demo/skills/process/bmad/.config.json` и шапке скилов указывается источник и MIT attribution.
- Покрытие кода движка: **`100%` branch coverage** на всех новых и изменённых файлах `src/todoc/`.
- Контракт Agent Skills (`src/todoc/application/skills.py` + `Anthropic Best Practices`): `name` совпадает с именем папки (`<= 64` симв.), `description` `<= 1024` симв. («WHAT + WHEN + NOT-WHEN»), `SKILL.md` до `180` строк, ссылки на `references/*.md` **строго в 1 уровень вложенности** (без цепочек `SKILL.md → a.md → b.md`), у файлов `references/*.md` длиннее `100` строк — оглавление вверху.
- Стандарт именования новых типов ([`type-naming-and-state-dir`](../ideas/type-naming-and-state-dir.md)): `1–2` слова `snake_case` (`roadmap`).
- Терминальные статусы (`done`, `rejected`, `superseded`) выставляются только после явного подтверждения пользователя; мутирующие команды CLI работают по review-first (`--preview` по умолчанию, `--apply` для записи).
- **Чистота чтения (`No-Write on Read / Preview`, совместимость с `docs/plan/todoc-master-refactoring-plan.md` §2.1):** команды чтения и предпросмотра (`todoc plan portfolio`, `todoc stale --anchor`, `todoc skills read --mode`, а также `--preview` у `--reanchor` и `plan bind`) **никогда не пишут** в исходные файлы, `.todoc/cache`, `.todoc/history` или `XDG_STATE_HOME` (работают поверх in-memory `ctx.scan()`, а не `ctx.ensure_index()`; покрывается отдельным тестом неизменности ФС).
- **Тонкий слой CLI (шов прямой совместимости под модульный рефакторинг CLI Э2–Э3 и `unified-cli-output`):** вся логика `portfolio.py`, `staleness.py`, `write.py` и `skills.py` реализуется в `src/todoc/application/` без импорта `click` и без прямого вывода в `stdout`, возвращая чистые словари, `Diagnostic` и осмысленные `next_actions`.

## 4. Архитектура и файловая карта

### 4.1. Перепроверка типов файлов и сущностей (почему НЕ нужен отдельный тип `wave`)

| Сущность процесса | Решение в `todoc` | Почему не заводим лишний тип |
|---|---|---|
| **Идея** | Существующий **`doc_type: idea`** | Полностью покрывает статусы `captured → planned → in_progress → done \| rejected \| superseded`. |
| **Архитектурный хребет** | Существующий **`doc_type: architecture-doc`** (`architecture/architecture-spine.md`) | Хранит сквозные решения `AD-1..N` (`Binds / Prevents / Rule`) и таблицу швов прямой совместимости (`Forward Seams`). |
| **Дорожная карта волн** | **НОВЫЙ `doc_type: roadmap`** (`plan/roadmap-<slug>.md`, статусы `active \| in_progress \| done \| superseded`) | **Единственный новый тип!** Держит все будущие тонкие волны в одном документе и позволяет двигать идеи между волнами при `replan` правкой одной секции без каскада по десятку файлов. |
| **Активная волна в работе** | Существующий **`doc_type: plan`** (`plan/wave-01-<slug>.md`) с опциональными полями front matter `roadmap`, `wave`, `covers`, `depends_on_waves`, `files_touched` и массивом `derived_from` | Отдельные `entity_type: wave` и `doc_type: wave_plan` дублировали бы `plan` и `roadmap`. Если волна крупная и делится на `wave-02a`/`wave-02b` с локальным ресёрчем — штатно используется папка-сущность (`[[entity-to-folder]]`). |

### 4.2. Калибровка «Умная модель vs Слабая модель» (`Anthropic Degrees of Freedom` + `SkillsBench`)

Чтобы скилы **не загоняли сильную рассуждающую модель в бюрократические рельсы** и одновременно **не оставляли слабую модель без точных опор**, в пакет закладываются три архитектурных правила:

1. **Адаптивная маршрутизация по масштабу (`Scale-Adaptive Routing` в `todoc-plan` — против когнитивного перегруза):**
   - **`Quick` (1 изолированная идея без архитектурных развилок):** идёт напрямую в обычный `todoc-plan` (`0` лишних артефактов, не запускаем 6 скилов ради мелкой фичи).
   - **`Standard` (2–4 связанные идеи, архитектура прозрачна):** идёт сразу в `bmad-wave-plan` (создаётся один сводный план волны со швами без обязательного создания отдельных файлов `architecture-spine.md` и `roadmap.md`).
   - **`Full Portfolio` (`5+` идей или сквозные развилки схемы БД / CLI / правил):** запускается полный цикл `bmad-architecture-spine → bmad-slice-roadmap → bmad-wave-plan`.
2. **Разделение степеней свободы по шагам внутри каждого `SKILL.md` (`High / Medium / Low Freedom`):**
   - **Зона `High Freedom` (для сильной модели):** архитектурная группировка идей, выбор швов совместимости и размерность задач в плане. Скил объясняет **почему** важны 4 инварианта (`0` сирот, `0` файловых коллизий, явные швы, запрет на тихое урезание скоупа), но **не диктует** модели искусственное дробление «строго по 2 минуты» или жёсткий порядок мыслей.
   - **Зона `Medium Freedom` (единый контракт чтения для человека):** строгие шаблоны выходных секций Markdown (включая карточку волны для занятого человека из п. 4.3).
   - **Зона `Low Freedom` (железные рельсы для слабой модели на хрупких шагах):** точные вызовы CLI (`todoc plan portfolio`, `todoc plan bind`, `todoc stale --anchor`) + эталонный заполненный образец `references/worked-example.md`.
3. **Как система детерминированно определяет, что отдавать сильной и слабой модели (без самооценки самой LLM):**
   - Полагаться на фразу в промпте *«если ты слабая модель — прочитай пример»* нельзя: слабая модель считает себя умной и пропускает файл, а сильная тратит токены на перестраховку. Поэтому работают **три объективных контура**:
     1. **Явный профиль в стейте сессии (`todoc state set agent.guidance_mode compact|guided|auto` + `todoc skills read --mode`):** если пользователь или оркестратор запускает малую/дешёвую модель (или субагента-исполнителя), он ставит `guided` — и CLI `todoc skills read` **сам физически доклеивает `references/worked-example.md`** к тексту `SKILL.md`. В режиме `compact` отдаётся только сухое ядро `SKILL.md` без примеров.
     2. **Поведенческий авто-детект через CLI (`auto` по умолчанию — проверка боем):** если профиль заранее не указан, любая модель сначала получает лёгкий `SKILL.md` (`0` лишних токенов для умной модели). На выходе она обязана запустить `todoc plan portfolio` / `todoc validate`. Если модель с первого раза прошла гейт — она справилась без подсказок; если же споткнулась (сломала карточку волны, протащила `.py`/`doc:` жаргон в человеческое резюме или оставила сироту), CLI ловит ошибку и в `next_actions` **принудительно выдаёт команду `todoc skills read --path ... --mode guided`**, переключая модель на работу по готовому образцу.
     3. **Разделение по ролям скилов:** синтезирующие скилы (`forge-idea`, `architecture-spine`, `slice-roadmap`, `adversarial-review`) рассчитаны по умолчанию на рассуждающую модель (`compact`), а механическое исполнение по готовому плану (`todoc-execute`) и чеклист закрытия волны (`bmad-wave-retro`) спокойно выполняются быстрой моделью в `guided`.

### 4.3. Дословный обязательный стандарт заголовка и описания волны для занятого человека

Каждая волна — **и как подсекция внутри `plan/roadmap-<slug>.md`, и в самом верху `plan/wave-NN-<slug>.md`** — обязана оформляться строго по двухслойному стандарту (**верхний слой — для занятого человека без погружения в контекст за 20 секунд чтения; нижний слой — технический паспорт для агента и CLI**):

- **Правило 1 (Говорящий заголовок волны от результата):**
  - Формат в `roadmap`: `### Волна <N>: <Короткое название результата понятными словами (5–12 слов)>`
  - Формат в файле плана волны (`title` и `# H1`): `Волна <N>: <Короткое название результата понятными словами> — план реализации`
  - Запрещено выносить в заголовок волны сырые имена `.py`-файлов, функции, регулярки или внутренние коды (`BUG-011`, `descriptors.py`). Заголовок отвечает на вопрос: **что реально появится или изменится в продукте после этой волны**.
- **Правило 2 (Самодостаточное резюме из 4 обязательных тезисных пунктов простыми словами сразу под заголовком):**
  - Текст этих 4 пунктов должен полностью пониматься занятым человеком **«с холодного старта»** — без чтения других документов, без знания внутренних `doc:...` идентификаторов, SHA-256 хэшей, названий переменных и истории чата:
    1. **`Суть простыми словами:`** `1–2` коротких предложения на обычном языке — что именно делаем в этой волне и как изменится работа с системой.
    2. **`Зачем делаем сейчас:`** `1–2` тезиса — какую конкретную боль или риск переделок закрываем сейчас и почему этот этап стоит именно здесь в очереди.
    3. **`Что получим на выходе:`** `2–4` конкретных, проверяемых результата глазами пользователя / владельца проекта (*что начнёт работать, какие возможности появятся, какие ошибки исчезнут*).
    4. **`Чего в этой волне ТОЧНО НЕ делаем:`** `1–2` тезиса простыми словами — что сознательно вынесено в следующие волны (чтобы не было ложных ожиданий) и какой задел под будущее закладываем уже сейчас.
- **Правило 3 (Отделение технического паспорта вниз):**
  - Все машинные реквизиты (`Входящие идеи: [[...]]`, `Зависит от волн`, `Затрагиваемые файлы/модули`, `Швы прямой совместимости`) располагаются **строго отдельным блоком ниже** человеческого резюме, чтобы не зашумлять чтение руководителю/владельцу и при этом давать `100%` точности слабой модели и CLI.

Каноничный шаблон карточки волны (включается дословно в `demo/.todoc/doc_types/roadmap/template.md` и `bmad-wave-plan/SKILL.md`):

```markdown
### Волна <N>: <Понятное название результата без техжаргона>

- **Суть простыми словами:** <1–2 предложения без внутренних ID и имён .py-файлов: что делаем в этом этапе>.
- **Зачем делаем сейчас:** <какую проблему снимаем и какие следующие волны это разблокирует>.
- **Что получим на выходе:**
  - <наблюдаемый результат 1 простыми словами>;
  - <наблюдаемый результат 2 простыми словами>.
- **Чего в этой волне ТОЧНО НЕ делаем:** <что сознательно оставлено на следующие волны и какой задел под это оставляем сейчас>.

**Технический паспорт волны (для агента и CLI):**
- Статус волны: `planned | active | done` (план: `[[wave-0N-slug]]` или `тонкая волна — детальный план создаётся перед стартом`)
- Покрываемые идеи: `[[idea-a]]`, `[[idea-b]]`
- Зависит от волн: `нет` (или `Волна <M>`)
- Затрагиваемые контуры кода: `src/todoc/...`
- Швы прямой совместимости под будущие волны: <какой интерфейс/колонку/параметр закладываем сразу, чтобы не переписывать в Волне N+1>
```

### 4.4. Новые CLI-команды `todoc` для поддержки скилов волнового планирования

1. **`todoc stale anchor` и `todoc stale reanchor` + `todoc stale --git-range <base>..HEAD`** (`src/todoc/application/staleness.py`, `src/todoc/cli.py`):
   - `todoc stale anchor --root KB --id doc:ideas/a.md [--id doc:ideas/b.md ...] [--section Предложение]` → возвращает `{"anchors": ["ideas/a.md#section:Предложение@sha256:...", ...]}`;
   - `todoc stale reanchor --root KB --id doc:plan/wave-01.md [--only doc:ideas/a.md] [--preview | --apply]` → пересчитывает SHA-256 в `derived_from` после согласованной синхронизации плана;
   - `todoc stale --root KB --git-range <base>..HEAD` → находит документы в `architecture/` и `state/`, ссылающиеся на затронутые в `git diff` файлы `src/...`, но сами ещё не обновлённые.
2. **`todoc plan portfolio` и `todoc plan bind` + мульти-`--id` в `todoc docs status`** (`src/todoc/application/portfolio.py`, `src/todoc/cli.py`):
   - `todoc plan portfolio --root KB` → за один вызов возвращает JSON:
     - `ideas_by_status`: группировка идей с заголовками, тегами и счётчиком открытых вопросов;
     - `coverage`: `orphan_ideas` (`captured`-идеи вне волн) и `duplicate_assignments` (одна идея в двух активных планах);
     - `file_collisions`: пересечения `files_touched` и строк `- Create:/- Modify:` между незавершёнными планами;
     - `wave_cards_lint`: проверка, что у каждой волны в активных `roadmap` и волновых `plan` заполнен говорящий заголовок `Волна <N>: ...` и все 4 пункта человеческого резюме (`Суть простыми словами`, `Зачем делаем сейчас`, `Что получим на выходе`, `Чего в этой волне ТОЧНО НЕ делаем`);
     - `ready_waves`: список волн/планов с закрытыми `depends_on_waves`.
   - `todoc plan bind --root KB --plan doc:plan/wave-01.md --idea doc:a [--idea doc:b ...] [--section Предложение] [--set-status planned] [--preview | --apply]`.
3. **Секционные правки в `todoc docs edit`** (`src/todoc/application/write.py`):
   - операции `{"op": "replace_section", "heading": "...", "text": [...]}` и `{"op": "append_section", "heading": "...", "text": [...]}`.
4. **Стандартное информационное поле `guidance` и `i18n`-каталог подсказок по кодам ситуаций (`P15`, `[[cli-model-guidance-and-hint-catalog]]`):**
   - в `Envelope` (`src/todoc/output/envelope.py`) добавляется поле верхнего уровня `guidance`, которое рендерится во **всех форматах вывода** (`json`, `table`, `markdown`) как в успешных (`ok: true`), так и в ошибочных (`ok: false`) ответах;
   - в Python-коде зашиты только коды ситуаций (`code`), а тексты подсказок, ссылки на подробные скилы (`skills`, в т.ч. `process/bmad/* --mode guided`) и документы (`docs`) загружаются из `src/todoc/resources/guidance/<profile>.json` (`ru.json`, `en.json` + безопасный по `P10` локальный оверрайд `.todoc/guidance.json` и табличный конвертер в `CSV`), переключаемый через `agent.guidance_profile` в `state.py`:
     - при `ok: true` поле `guidance` остаётся минимальным (`0` шума для сильной модели);
     - при ошибке проверки/теста/валидации CLI в `guidance` автоматически выдаются рекомендации и ссылки на скилы/документы по сработавшим `code`.

### 4.5. Сводная матрица 6 скилов `demo/skills/process/bmad/`

| Скил (`demo/skills/process/bmad/<name>/SKILL.md`) | Оригиналы `BMAD-METHOD` (MIT) | Практики `GSD` / `Spec Kit` / `OpenSpec` / `Anthropic` + опора CLI |
|---|---|---|
| 1. `bmad-forge-idea` | [`v6.12.4/bmad-forge-idea`](https://github.com/bmad-code-org/BMAD-METHOD/blob/v6.12.4/src/core-skills/bmad-forge-idea/SKILL.md), [`main/bmad-forge-idea`](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/core-tools/bmad-forge-idea/SKILL.md) | `attack / defend` по 1 вопросу за ход + таксономия `spec-kit/clarify.md` + `Discovery Level 0..3` из `gsd-planner.md` + формулировка идеи понятным языком без дыр. Опирается на `docs search/read/edit`. |
| 2. `bmad-architecture-spine` | [`v6.12.4/bmad-architecture`](https://github.com/bmad-code-org/BMAD-METHOD/blob/v6.12.4/src/bmm-skills/plan/bmad-architecture/SKILL.md), [`spine-template.md`](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/method/bmad-architecture/assets/spine-template.md), [`reviewer-gate.md`](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/method/bmad-architecture/references/reviewer-gate.md) | `High Freedom` на синтез + блоки `AD-n` (`Binds / Prevents / Rule`) + таблица `Forward Seams` + иерархия авторитета `spec-kit/analyze.md` (`rules/` > `AD-n` > `roadmap` > `plan`). Вход через `todoc plan portfolio`. |
| 3. `bmad-slice-roadmap` | [`slice.md`](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/method/bmad-agent-po/references/slice.md), [`validate-checks.md`](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/method/bmad-agent-po/references/validate-checks.md), [`replan.md`](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/method/bmad-agent-po/references/replan.md), [`bmad-correct-course`](https://github.com/bmad-code-org/BMAD-METHOD/blob/v6.12.4/src/bmm-skills/ship/bmad-correct-course/SKILL.md) | Инварианты `Collisions` и `Shared Setup` + `100% Coverage / 0 Orphans` из `gsd-roadmapper.md` + **обязательные двухслойные карточки волн для занятого человека (п. 4.3)** + `references/worked-example.md`. Проверка `todoc plan portfolio`. |
| 4. `bmad-wave-plan` | [`bmad-spec`](https://github.com/bmad-code-org/BMAD-METHOD/blob/v6.12.4/src/bmm-skills/plan/bmad-spec/SKILL.md), [`bmad-create-epics-and-stories`](https://github.com/bmad-code-org/BMAD-METHOD/blob/v6.12.4/src/bmm-skills/plan/bmad-create-epics-and-stories/SKILL.md), [`readiness-gate.md`](https://github.com/bmad-code-org/BMAD-METHOD/blob/v6.12.4/src/bmm-skills/plan/bmad-sprint-planning/references/readiness-gate.md) | **Говорящий заголовок + резюме волны в шапке плана (п. 4.3)** + `Scope-Reduction Prohibition` и `Multi-Source Coverage Audit` из `gsd-planner.md` + дельты `ADDED / MODIFIED / REMOVED` для `state/` + привязка `todoc plan bind` + `references/worked-example.md`. |
| 5. `bmad-adversarial-review` | [`bmad-review`](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/core-tools/bmad-review/SKILL.md), [`lens-adversarial.md`](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/core-tools/bmad-review/references/lens-adversarial.md), [`lens-edge-case-hunter.md`](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/core-tools/bmad-review/references/lens-edge-case-hunter.md), [`lens-verification-gap.md`](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/core-tools/bmad-review/references/lens-verification-gap.md) | 4 линзы (`Adversarial`, `Edge-Case`, `Verification-Gap`, `Cross-Wave Wiring & Future-Rework`) + проверка читаемости резюме волны глазами занятого человека (`wave_cards_lint` в `todoc plan portfolio`). |
| 6. `bmad-wave-retro` | [`bmad-retrospective`](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/method/bmad-retrospective/SKILL.md), [`acceptance-verdict.md`](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/method/bmad-retrospective/references/acceptance-verdict.md), [`bmad-project-context`](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/method/bmad-project-context/SKILL.md) | Приёмка по объективным артефактам + `Append-Only Convergence` из `spec-kit/converge.md` + подсказка `todoc stale --git-range` для обновления `state/` + краткий человеческий итог закрытой волны. |

### 4.6. Файловая карта изменений

- Create: `demo/.todoc/doc_types/roadmap/{type.json,template.md,prompts/read.md,prompts/create.md,prompts/edit.md,prompts/delete.md}`
- Modify: `demo/.todoc/rules/document-rules.json` (правило `fm-roadmap`)
- Modify: `src/todoc/output/envelope.py` (стандартное поле `guidance` во всех форматах `json/table/markdown` для `ok: true` и `ok: false`)
- Create: `src/todoc/application/guidance.py` + `src/todoc/resources/guidance/{ru.json,en.json}` (загрузчик `i18n`-каталога подсказок, переключатель профилей и CSV-экспорт/импорт)
- Modify: `src/todoc/application/staleness.py` (`compute_anchors`, `plan_reanchor`, `check_git_range_drift`)
- Modify: `src/todoc/application/write.py` (`replace_section` и `append_section` в `apply_edit_ops`)
- Create: `src/todoc/application/portfolio.py` (`build_plan_portfolio` включая `wave_cards_lint`, `plan_bind_ideas`)
- Modify: `src/todoc/cli.py` (`stale anchor`, `stale reanchor`, `stale --git-range`, группа `plan portfolio` / `plan bind`, мульти-`--id` в `docs status`)
- Create: `demo/skills/process/bmad/.config.json`
- Create: `demo/skills/process/bmad/bmad-forge-idea/{SKILL.md,references/worked-example.md}`
- Create: `demo/skills/process/bmad/bmad-architecture-spine/{SKILL.md,references/spine-checklist.md}`
- Create: `demo/skills/process/bmad/bmad-slice-roadmap/{SKILL.md,references/slicing-rules.md,references/worked-example.md}`
- Create: `demo/skills/process/bmad/bmad-wave-plan/{SKILL.md,references/readiness-gate.md,references/worked-example.md}`
- Create: `demo/skills/process/bmad/bmad-adversarial-review/{SKILL.md,references/lenses.md}`
- Create: `demo/skills/process/bmad/bmad-wave-retro/SKILL.md`
- Modify: `demo/skills/process/todoc-plan/SKILL.md` (адаптивная маршрутизация `Quick / Standard / Full Portfolio`)
- Modify: `demo/HOME.md`, `demo/README.md`, `README.md`
- Test: `tests/unit/test_roadmap_doc_type.py`, `tests/unit/test_wave_cli_helpers.py`, `tests/unit/test_cli_guidance_catalog.py`

## 5. Задачи

### Задача 1: Дескриптор `doc_type: roadmap` с обязательным шаблоном человекопонятных карточек волн

**Файлы:**
- Create: `demo/.todoc/doc_types/roadmap/type.json`
- Create: `demo/.todoc/doc_types/roadmap/template.md`
- Create: `demo/.todoc/doc_types/roadmap/prompts/{read,create,edit,delete}.md`
- Modify: `demo/.todoc/rules/document-rules.json`
- Test: `tests/unit/test_roadmap_doc_type.py`

**Точный контракт `type.json` и `template.md`:**
- `type_id = "roadmap"`, `allowed_statuses = ["active", "in_progress", "done", "superseded"]`.
- `required_sections`:
  1. `## 1. Резюме дорожной карты простыми словами` (зачем нужна эта серия волн, какую общую цель закрывает и в какой последовательности — для чтения руководителем за 30 секунд без контекста);
  2. `## 2. Матрица коллизий и швов прямой совместимости`;
  3. `## 3. Волны реализации` (внутри шаблон содержит дословную карточку `### Волна 1: <Понятное название результата без техжаргона>` с 4 обязательными тезисными пунктами из раздела 4.3 + блоком технического паспорта ниже);
  4. `## 4. Отложено и вне скоупа`;
  5. `## 5. Прогресс волн`;
  6. `## 6. Связанные документы`.

- [ ] **Шаг 1: написать падающий тест `tests/unit/test_roadmap_doc_type.py` на регистрацию `roadmap`, `todoc docs new --type roadmap` и наличие в созданном файле каноничной карточки волны с 4 пунктами человеческого резюме**
- [ ] **Шаг 2: убедиться, что тест падает (`.venv/bin/pytest tests/unit/test_roadmap_doc_type.py -v`)**
- [ ] **Шаг 3: создать `demo/.todoc/doc_types/roadmap/*` (включая подробные `prompts/create.md` и `prompts/edit.md`, запрещающие техжаргон в верхних 4 пунктах волны) и правило `fm-roadmap` (`priority: 200`) в `demo/.todoc/rules/document-rules.json`**
- [ ] **Шаг 4: убедиться, что тест и `todoc validate --root demo --all` проходят с `0` диагностик**
- [ ] **Шаг 5: коммит (`feat(types): добавлен doc_type roadmap с двухслойным шаблоном карточки волны`)**

### Задача 2: Стандартное поле `guidance` + `i18n`-каталог подсказок (`P15`), CLI-якоря `stale` и секционный `docs edit`

**Файлы:**
- Modify: `src/todoc/output/envelope.py`
- Create: `src/todoc/application/guidance.py`
- Create: `src/todoc/resources/guidance/ru.json`, `src/todoc/resources/guidance/en.json`
- Modify: `src/todoc/application/state.py` (`agent.guidance_mode` и `agent.guidance_profile` в `ALLOWED_KEYS_V1`)
- Modify: `src/todoc/application/staleness.py`
- Modify: `src/todoc/application/write.py`
- Modify: `src/todoc/cli.py` (`skills read --mode auto|compact|guided`, `stale --anchor/--reanchor/--git-range`)
- Test: `tests/unit/test_wave_cli_helpers.py`, `tests/unit/test_cli_guidance_catalog.py`

**Точные сигнатуры CLI и функций:**
- В `src/todoc/output/envelope.py` + `src/todoc/application/guidance.py`: стандартное поле `guidance` в каждом `Envelope` (`_emit_ok`, `_emit_result`, `_emit_error`) и рендеринг во всех форматах (`json`, `table`, `markdown`). При `ok: true` без диагностик — минимальный объект без шума; при `ok: false` или предупреждениях — подстановка по коду `code` из декларативного `i18n`-каталога `src/todoc/resources/guidance/<profile>.json` (+ безопасный по `P10` локальный `.todoc/guidance.json` и конвертер `CSV ↔ JSON`) с полями `hint`, `skills`, `docs` и автослиянием шаблонных `actions` в `next_actions`.
- В `tests/unit/test_cli_guidance_catalog.py`: обязательные контрактные тесты самодокументации CLI для моделей — (1) наличие `guidance` во всех ошибочных и неошибочных ответах всех форматов, (2) покрытие кодов ошибок каталогом, (3) существование всех целевых путей `skills` и `docs` в `demo/`, (4) переключение профиля `ru ↔ en` и `compact ↔ guided` без изменения `code`.
- В `src/todoc/application/state.py`: расширить `ALLOWED_KEYS_V1 = ("context.current_project", "agent.guidance_mode", "agent.guidance_profile")` с проверкой `agent.guidance_mode in {"auto", "compact", "guided"}`.
- В `todoc skills read` (`src/todoc/cli.py`): опция `--mode [auto|compact|guided]` (при отсутствии берётся `agent.guidance_mode` из `load_state`, дефолт `auto`). В режиме `guided`, если внутри папки скила есть `references/worked-example.md` (с проверкой `is_within_root(vault_root, ref_path)`), его содержимое доклеивается через `\n\n---\n\n` до применения `--budget`, а в JSON добавляется `"guided_example_included": True`; если у старого скила файла `worked-example.md` нет — команда без ошибки отдаёт базовый `SKILL.md` с `"guided_example_included": False`. Никакой записи на диск при `skills read`.
- `todoc stale --root KB --anchor <rel_path_or_doc_id> [--anchor ...] [--section <heading>]` (строго read-only, без вызова `ensure_index()`) → возвращает `data.anchors: list[str]` через `fragment_hash` + `format_anchor`.
- `todoc stale --root KB --reanchor <rel_path_or_doc_id> [--only <dep_path>] [--preview | --apply]` → обновляет хэши в `derived_from` front matter документа.
- `todoc stale --root KB --git-range <base>..HEAD` → сверяет изменённые в `git diff --name-only <base>..HEAD` пути `src/...` с `source_anchor` и упоминаниями путей в `architecture/` и `state/`.
- В `apply_edit_ops` (`write.py`): операции `{"op": "replace_section", "heading": "...", "text": [...]}` и `{"op": "append_section", "heading": "...", "text": [...]}` (находят заголовок через `parse_markdown`, заменяют или дополняют строки до следующего заголовка уровня `<= target_level`).

- [ ] **Шаг 1: написать падающие юнит- и CLI-тесты в `tests/unit/test_wave_cli_helpers.py` на все ветки (`ok`, `missing`, `unresolved`, `--preview`, `--apply`, `git-range`, `replace_section`, `append_section`)**
- [ ] **Шаг 2: убедиться, что тесты падают**
- [ ] **Шаг 3: реализовать функции в `staleness.py`, `write.py` и подключить опции в `cli.py` без поломки существующих тестов `stale`**
- [ ] **Шаг 4: проверить `pytest` и `100%` branch coverage на `staleness.py`, `write.py`, `cli.py`**
- [ ] **Шаг 5: коммит (`feat(cli): добавлены якоря stale, проверка git-range и секционный docs edit`)**

### Задача 3: CLI-команды `todoc plan portfolio`, `todoc plan bind` и мульти-`--id` в `todoc docs status`

**Файлы:**
- Create: `src/todoc/application/portfolio.py`
- Modify: `src/todoc/cli.py`
- Modify: `tests/unit/test_wave_cli_helpers.py`

**Точный JSON-контракт `todoc plan portfolio --root KB`:**
```json
{
  "ideas_by_status": {"captured": [...], "planned": [...], "in_progress": [...], "done": [...]},
  "coverage": {"orphan_ideas": [...], "duplicate_assignments": [...]},
  "file_collisions": [{"file": "src/todoc/...", "plans": ["doc:plan/a.md", "doc:plan/b.md"]}],
  "wave_cards_lint": [{"path": "plan/roadmap-x.md", "wave": "Волна 1", "missing": []}],
  "ready_waves": ["doc:plan/wave-01.md"]
}
```
- `wave_cards_lint` детерминированно проверяет наличие заголовка `### Волна <N>: <непустое название>` в `roadmap` (и `# Волна <N>: ...` или блока `> **Резюме волны...` в волновых планах `wave` != `None`) и всех 4 обязательных тезисов (`Суть простыми словами`, `Зачем делаем сейчас`, `Что получим на выходе`, `Чего в этой волне ТОЧНО НЕ делаем`).
- `todoc plan bind --root KB --plan <doc_id> --idea <doc_id> [--idea ...] [--section Предложение] [--set-status planned] [--preview | --apply]`.
- `todoc docs status`: поддержка повторяющегося `--id` по правилу **validate-all-before-write** (сначала проверяются все переданные документы и допустимость статуса, и только затем выполняются записи; при одном `--id` полностью сохраняется прежняя JSON-схема `id / status / new_hash`, при `>= 2` добавляется список `items`).
- При нахождении ошибок в `wave_cards_lint` (отсутствует заголовок `Волна <N>: ...`, пропущен любой из 4 человеческих тезисов или в них обнаружены сырые `.py` / `doc:` / `sha256:` идентификаторы) `todoc plan portfolio` возвращает в `next_actions` принудительную команду эскалации `todoc skills read --path process/bmad/bmad-wave-plan --mode guided` (поведенческий авто-детект для слабых моделей).
- `todoc plan portfolio` работает строго read-only поверх `ctx.scan()` без записи в `.todoc/cache` и `.todoc/history`.

- [ ] **Шаг 1: дописать падающие тесты в `tests/unit/test_wave_cli_helpers.py` на `plan portfolio` (включая `wave_cards_lint`, `orphan_ideas`, `file_collisions`, `ready_waves`), `plan bind` и мульти-`--id` `docs status`**
- [ ] **Шаг 2: убедиться, что тесты падают**
- [ ] **Шаг 3: реализовать `src/todoc/application/portfolio.py` и группу `todoc plan` + мульти-`--id` в `src/todoc/cli.py`**
- [ ] **Шаг 4: прогнать `coverage run --branch -m pytest && coverage report` — убедиться в `100%` покрытии новых модулей и отсутствии регрессий в старых тестах**
- [ ] **Шаг 5: коммит (`feat(cli): добавлены todoc plan portfolio с линтером карточек волн и plan bind`)**

### Задача 4: Паспорт раздела `process/bmad` и скил прожарки идей `bmad-forge-idea`

**Файлы:**
- Create: `demo/skills/process/bmad/.config.json`
- Create: `demo/skills/process/bmad/bmad-forge-idea/SKILL.md`
- Create: `demo/skills/process/bmad/bmad-forge-idea/references/worked-example.md`

**Контракт скила:**
- Зона `High Freedom`: выбор острых контр-вопросов и ролевой оптики (`attack / defend` по 1 вопросу за ход, без опросника из 10 пунктов сразу).
- Зона `Medium/Low Freedom`: проверка фактов по базе через `todoc docs search/read` и живому коду `src/`; присвоение `Discovery Level 0..3`; на выходе — чистая запись идеи простым языком без техводы + одноуровневый пример `references/worked-example.md` для слабой модели.

- [ ] **Шаг 1: создать `demo/skills/process/bmad/.config.json` и `bmad-forge-idea/{SKILL.md,references/worked-example.md}`**
- [ ] **Шаг 2: проверить `todoc skills tree --root demo --within process/bmad` и `todoc validate --root demo --all` (`0` диагностик)**
- [ ] **Шаг 3: коммит (`feat(skills): добавлен раздел process/bmad и скил bmad-forge-idea`)**

### Задача 5: Скил архитектурного хребта `bmad-architecture-spine`

**Файлы:**
- Create: `demo/skills/process/bmad/bmad-architecture-spine/SKILL.md`
- Create: `demo/skills/process/bmad/bmad-architecture-spine/references/spine-checklist.md`

**Контракт скила:**
- Зона `High Freedom`: содержательный поиск точек несовместимости между всеми идеями бэклога (*«где две волны примут конфликтующие решения по таблицам, индексам или CLI?»*).
- Зона `Medium/Low Freedom`: старт с `todoc plan portfolio`; в начале документа — короткое резюме на человеческом языке; далее компактные блоки `AD-n` (`Binds / Prevents / Rule`), иерархия авторитета (`rules/` > `AD-n` > `roadmap` > `plan`) и таблица `Forward Seams`.

- [ ] **Шаг 1: создать `SKILL.md` и одноуровневый `references/spine-checklist.md`**
- [ ] **Шаг 2: проверить `todoc skills read --root demo --path process/bmad/bmad-architecture-spine` и `todoc validate --root demo --all` (`0` диагностик)**
- [ ] **Шаг 3: коммит (`feat(skills): добавлен скил bmad-architecture-spine со швами совместимости`)**

### Задача 6: Скил нарезки волн `bmad-slice-roadmap` с эталоном человеческих карточек волн

**Файлы:**
- Create: `demo/skills/process/bmad/bmad-slice-roadmap/SKILL.md`
- Create: `demo/skills/process/bmad/bmad-slice-roadmap/references/slicing-rules.md`
- Create: `demo/skills/process/bmad/bmad-slice-roadmap/references/worked-example.md`

**Контракт скила:**
- Зона `High Freedom`: смысловая группировка идей в волны по правилам `Collisions` и `Shared Setup` с обязательным учётом уже существующих мастер- и `AFTER`-планов (`docs/plan/todoc-master-refactoring-plan.md`, `demo/plan/unified-cli-output-implementation.md`, `demo/plan/after/*.after.md` — встраиваться в них и проверять статус по живому коду, а не плодить конкурирующие дубликаты).
- Зона `Medium/Low Freedom`: обязательное оформление **каждой волны строго по дословному двухслойному стандарту п. 4.3** (говорящий заголовок + 4 тезиса простыми словами для занятого человека без контекста + техпаспорт ниже), заполненный образец в `references/worked-example.md` для слабой модели и финальная самопроверка `todoc plan portfolio` (`orphan_ideas == []`, `wave_cards_lint` без пропусков).

- [ ] **Шаг 1: создать `SKILL.md`, `references/slicing-rules.md` и эталонный `references/worked-example.md`**
- [ ] **Шаг 2: проверить `todoc skills tree --root demo --within process/bmad` и `todoc validate --root demo --all` (`0` диагностик)**
- [ ] **Шаг 3: коммит (`feat(skills): добавлен скил bmad-slice-roadmap с эталоном карточек волн`)**

### Задача 7: Скил плана волны `bmad-wave-plan` и адаптивная связка в `todoc-plan`

**Файлы:**
- Create: `demo/skills/process/bmad/bmad-wave-plan/SKILL.md`
- Create: `demo/skills/process/bmad/bmad-wave-plan/references/readiness-gate.md`
- Create: `demo/skills/process/bmad/bmad-wave-plan/references/worked-example.md`
- Modify: `demo/skills/process/todoc-plan/SKILL.md`

**Контракт скила и маршрутизации:**
- В `bmad-wave-plan`: обязательный блок **«Резюме волны для занятого человека» (4 тезиса без жаргона по п. 4.3)** сразу под говорящим `# Волна <N>: ...`; высокая свобода на выбор внутренней декомпозиции задач при жёстком запрете на тихое урезание скоупа (`Scope-Reduction Prohibition`); таблица `Multi-Source Coverage Audit`; секция швов `Forward Seams`; дельты `ADDED / MODIFIED / REMOVED` для живых доков; атомарная привязка идей через `todoc plan bind` и эталон `references/worked-example.md`.
- В `todoc-plan/SKILL.md`: добавляется адаптивный выбор маршрута **`Quick` (1 идея → остаёмся в `todoc-plan`) / `Standard` (2–4 понятные идеи → `bmad-wave-plan`) / `Full Portfolio` (`5+` идей или сквозные развилки → `bmad-architecture-spine` + `bmad-slice-roadmap`)**, чтобы не загонять сильную модель в лишние шаги на простых задачах.

- [ ] **Шаг 1: создать `bmad-wave-plan/{SKILL.md,references/readiness-gate.md,references/worked-example.md}`**
- [ ] **Шаг 2: обновить `demo/skills/process/todoc-plan/SKILL.md` через `todoc docs edit` (`--preview` → `--apply`)**
- [ ] **Шаг 3: проверить `todoc validate --root demo --all` = `0` и `tools/linkcheck.py` = `0`**
- [ ] **Шаг 4: коммит (`feat(skills): добавлен bmad-wave-plan и адаптивная маршрутизация в todoc-plan`)**

### Задача 8: Скил четырёхлинзового стресс-ревью `bmad-adversarial-review`

**Файлы:**
- Create: `demo/skills/process/bmad/bmad-adversarial-review/SKILL.md`
- Create: `demo/skills/process/bmad/bmad-adversarial-review/references/lenses.md`

**Контракт скила:**
- 4 линзы (`Adversarial`, `Edge-Case Hunter`, `Verification-Gap`, `Cross-Wave Wiring & Future-Rework`) + обязательный пункт проверки человеческой читаемости: **поймёт ли занятой человек заголовок и 4 тезиса волны за 20 секунд без знания кода и истории чата** (если в резюме просочился техжаргон или внутренние ID — выдаётся замечание `WARNING/BLOCKER`).

- [ ] **Шаг 1: создать `SKILL.md` и `references/lenses.md`**
- [ ] **Шаг 2: проверить `todoc validate --root demo --all` = `0`**
- [ ] **Шаг 3: коммит (`feat(skills): добавлен четырёхлинзовый bmad-adversarial-review`)**

### Задача 9: Скил приёмки волны `bmad-wave-retro`, интеграционные тесты и синхронизация витрин

**Файлы:**
- Create: `demo/skills/process/bmad/bmad-wave-retro/SKILL.md`
- Modify: `demo/HOME.md`, `demo/README.md`, `README.md`
- Modify: `tests/unit/test_roadmap_doc_type.py`

**Контракт скила:**
- Сбор объективных доказательств (`pytest` + coverage, `validate --all`, `stale`, `linkcheck.py`, `stale --git-range`); режим `Append-Only Convergence` при недоделках; короткий человеческий отчёт по итогам волны (3–4 предложения без жаргона: что закрыли, что обновили в документации реальности, готова ли следующая волна); пакетный перевод статуса после подтверждения пользователя.

- [ ] **Шаг 1: создать `bmad-wave-retro/SKILL.md`**
- [ ] **Шаг 2: расширить `tests/unit/test_roadmap_doc_type.py` проверкой всех 6 скилов `process/bmad`, отсутствия вложенных более чем на 1 уровень ссылок `references/` и валидации нашего собственного плана линтером `wave_cards_lint`**
- [ ] **Шаг 3: синхронизировать ссылки и счётчики документов, типов (`31 → 32`), скилов (`30 → 36`) и команд CLI в `demo/HOME.md`, `demo/README.md`, `README.md`**
- [ ] **Шаг 4: прогнать полный пре-коммит гейт (`coverage` `100%`, `validate --all` = `0`, `stale` = `0`, `linkcheck.py` = `0`)**
- [ ] **Шаг 5: финальный коммит (`feat(skills): добавлен bmad-wave-retro и синхронизированы витрины`)**

## 6. Definition of Done

- [ ] Дескриптор `doc_type: roadmap` + шаблон с двухслойной карточкой волны + 4 CRUD-промпта + правило `fm-roadmap` созданы и покрыты автотестами.
- [ ] Реализованы стандартное поле `guidance` во всех выводах CLI + переключаемый `i18n`-каталог подсказок (`P15`), CLI-команды якорей `stale`, `--git-range`, `todoc plan portfolio` (включая `wave_cards_lint`), `todoc plan bind`, мульти-`--id` в `docs status` и `replace_section`/`append_section` в `docs edit` со **`100%` branch coverage** и контрактными тестами самодокументации ошибок CLI.
- [ ] Все **6 скилов** в `demo/skills/process/bmad/<skill-name>/SKILL.md` разделяют зоны `High / Medium / Low Freedom`, содержат одноуровневые `references/worked-example.md` для слабых моделей и требуют говорящего заголовка + 4 тезисов для занятого человека у каждой волны.
- [ ] `demo/skills/process/todoc-plan/SKILL.md` поддерживает адаптивную маршрутизацию `Quick / Standard / Full Portfolio` без лишней бюрократии на малых задачах.
- [ ] `todoc validate --root demo --all` = `0`, `todoc stale --root demo` = `0`, `tools/linkcheck.py` = `0`, счётчики в `README.md` и `demo/README.md` совпадают с фактом.

## 7. Риски и митигации

| Риск | В × В | Митигация | Владелец |
|---|---|---|---|
| Зажимание сильной модели избыточной цепочкой из 6 скилов на простых задачах (`SkillsBench` penalty `> 3` скилов) | В × В | Адаптивный гейт `Quick / Standard / Full Portfolio` в `todoc-plan` + `High Freedom` на архитектурный синтез внутри скилов. | Автор скила |
| Потеря структуры или техжаргон у слабой / быстрой модели | В × В | Точные CLI-команды (`Low Freedom`) + жёсткий шаблон карточки волны + одноуровневые заполненные образцы `references/worked-example.md` + автопроверка `wave_cards_lint` в `todoc plan portfolio`. | CLI + шаблоны |
| Проникновение кода, ID и сленга в резюме волны для занятого человека | С × В | Чёткое разделение карточки волны на два визуальных блока (верхние 4 пункта без ID/файлов для человека, нижний техпаспорт — для агента) + проверка в `readiness-gate.md` и `bmad-adversarial-review`. | Ревью-гейт |
| Тихое урезание скоупа идей при слиянии нескольких идей в одну волну | В × В | `Scope-Reduction Prohibition` + `Multi-Source Coverage Audit` из `GSD`. | Автор скила |

## 8. Прогресс и отклонения

- `2026-11-26` — создана первая редакция плана в статусе `active`.
- `2026-11-27` — добавлены практики `GSD / Spec Kit / OpenSpec` и задачи на CLI-механику волн (`[[wave-planning-cli-helpers]]`).
- `2026-11-27` — по результатам аудита против `Anthropic Agent Skills` и `SkillsBench` (`arXiv:2602.12670`) внедрены адаптивная маршрутизация `Quick / Standard / Full Portfolio`, разделение `High / Medium / Low Freedom` с одноуровневыми `worked-example.md`, а также дословный обязательный стандарт заголовка и 4-пунктного понятного описания волны для занятого человека без погружения в контекст (включая автопроверку `wave_cards_lint` в `todoc plan portfolio`).
- `2026-11-27` — выполнен финальный предреализационный аудит на актуальном `origin/master` (`3a5753d`): зафиксированы детерминированное переключение `agent.guidance_mode` (`auto/compact/guided` + поведенческая авто-эскалация через `next_actions`), инвариант `No-Write on Read/Preview`, правило `validate-all-before-write` для пакетного `docs status` и шов совместимости с `todoc-master-refactoring-plan.md` и `unified-cli-output`. План полностью готов к реализации с Задачи 1.
