---
id: doc:ideas/multi-project-workspace.md
title: "Идея: мульти-проектное рабочее пространство (projects/*, системный проект core и параллельный скоуп CLI через state.json)"
doc_type: idea
lang: ru
status: captured
created: 2026-11-26
updated: 2026-11-26
tags: [ideas, idea, projects, workspace, harness, state, cli, микросервисы]
related: ["[[agent-state]]", "[[folder-config]]", "[[skills-engine]]", "[[toggleable-rules]]", "[[typed-tree-projection]]", "[[sqlite-storage-drivers]]", "[[unified-tags-and-tag-graph]]", "[[docs-move]]", "[[entity-to-folder]]", "[[type-naming-and-state-dir]]"]
---

# Идея: мульти-проектное рабочее пространство (`projects/*`, системный проект `core` и параллельный скоуп CLI через `state.json`)

- Тип: `idea`
- Создан: 2026-11-26
- Идентификатор: `doc:ideas/multi-project-workspace.md`
- Статус: `captured` (идея зафиксирована, не перешла в план)

## Суть

Организовать всю папку данных `<DATA_ROOT>` по единому закону **«всё является проектом внутри `projects/<slug>/`»**, выделяя:
1. **системный проект `projects/core/`** — такой же проект по структуре, но содержащий базовый харнес ядра (`skills`, `flows`, `rules`), общие гайды и сквозной глоссарий, который **доступен на чтение всегда**;
2. **прикладные проекты `projects/<slug>/`** (продукты, сервисы, микросервисы со своим проектным харнесом, идеями, планами, состоянием `state/`, спеками и задачами);
3. **мульти-проектный контекст в `state.json`** (`context.current_project` + `context.projects = "core|billing|auth"`), благодаря которому все команды CLI автоматически ограничивают чтение, поиск, деревья и теги набором открытых проектов (позволяя работать параллельно над связкой микросервисов), направляют создание в фокусный проект и защищают как закрытые проекты, так и `core` от случайной мутации.

## Проблема

1. **Плоский корень не масштабируется на несколько продуктов и микросервисов.** Когда идеи, планы, задачи, баги и скилы лежат в корне `<DATA_ROOT>`, разные проекты перемешиваются в поисковой выдаче, словаре тегов и графе связей.
2. **Асимметрия «отдельный глобальный харнес в корне vs папки проектов» рождает два набора правил.** Если держать `harness/` вне `projects/`, для него приходится изобретать отдельные пути, отдельные `id`, отдельные колонки в индексе и особые флаги CLI. Выделение базового харнеса в полноценный проект **`projects/core/`** убирает асимметрию полностью.
3. **Одиночный `context.current_project` в `state.json` (v1) недостаточен для реальной разработки.** В микросервисной или платформенной архитектуре одна фича почти всегда затрагивает 2–3 связанных сервиса (`billing` + `auth` + `gateway`) плюс базовый харнес `core`. Жёсткое зажатие CLI ровно в один проект заставило бы агента постоянно дёргать переключение стейта, теряя межпроектные контракты и связи.
4. **Сейчас `state.json` в движке вообще не влияет на команды CLI.** В `src/todoc/application/state.py` реализовано хранение `context.current_project`, но ни одна команда (`docs`, `records`, `skills`, `validate`) его не читает и пути не скоупит; шаблоны `path_template` записей и `--vault skills` жёстко прибиты к корню датасета.

## Принципы

1. **Единообразие геометрии: `DATA_ROOT` содержит только `.todoc/`, `.todocignore` и `projects/`.** Никаких «бесхозных» документов и папок вне `projects/<slug>/`. Контейнер `projects/` имеет `dir_type: projects`, а каждая папка первого уровня `projects/<slug>/` — собственный тип **`dir_type: project`** (по стандарту [`type-naming-and-state-dir`](type-naming-and-state-dir.md)).
2. **`core` — такой же проект, но базовый слой по умолчанию.** В `projects/core/` лежат общие скилы (`todoc-*`, git, ресёрч), базовые флоу, общие отключаемые `rules`, платформенные `guides/` и сквозной `glossary/`. Он всегда входит в окно чтения, но защищён от случайной записи из других проектов.
3. **Разделение «окна параллельной видимости» и «фокуса создания».**
   - `context.projects` (`"core|billing|auth"`) определяет, **какие проекты видны параллельно** в поиске, деревьях, тегах, графе и харнесе, а также в каких открытых рабочих проектах разрешена правка по `--id`.
   - `context.current_project` (`"billing"`) определяет **целевой проект по умолчанию** при создании новых документов/записей с коротким относительным путём и высший приоритет при разрешении одноимённых скилов.
4. **Никакой скрытой магии для агента.** Каждый JSON-ответ скоупящейся команды явно сообщает активный срез (`focus_project`, `active_projects`, `scope_source`), а каждый элемент выдачи несёт поле `"project": "<slug>"`.
5. **Целостность графа — глобальная, видимость выборок — скоупленная.** Валидация ссылок и автоправка входящих ссылок при `todoc docs move` учитывают весь датасет, чтобы перенос файла в одном микросервисе никогда не порвал ссылку в соседнем микросервисе, который сейчас выключен из `state.json`.

## Предложение

### 1. Целевая структура папки данных `<DATA_ROOT>`

```text
<DATA_ROOT>/
├── .todoc/                          # Схемы типов, правила масок, index.sqlite, history.sqlite
├── .todocignore                     # Правила исключения мусора из индексации
└── projects/                        # Контейнер проектов (dir_type: projects)
    ├── core/                        # Системный проект ядра (dir_type: project, всегда активен на чтение)
    │   ├── .config.json             # Паспорт ядра (title, description, tags)
    │   ├── HOME.md                  # Оглавление ядра
    │   ├── harness/                 # Общий харнес системы (dir_type: harness)
    │   │   ├── skills/              # Общие скилы: todoc-capture, todoc-plan, git, research...
    │   │   ├── flows/               # Общие процессные флоу
    │   │   └── rules/               # Общие отключаемые правила (doc_type: rules)
    │   ├── guides/                  # Общие руководства
    │   └── glossary/                # Сквозные термины платформы
    │
    ├── auth/                        # Прикладной проект / микросервис 1 (dir_type: project)
    │   ├── .config.json             # Паспорт + related_projects + disabled_harness
    │   ├── HOME.md                  # Оглавление проекта auth
    │   ├── harness/                 # Собственный харнес проекта auth
    │   │   ├── skills/              # Скилы auth (ротация ключей, миграции OAuth...)
    │   │   ├── flows/               # Флоу auth
    │   │   └── rules/               # Отключаемые правила auth
    │   ├── .research/               # Исследования проекта
    │   ├── ideas/                   # Замыслы (TO-BE)
    │   ├── plan/                    # Планы реализации
    │   ├── state/                   # Реальная картина мира сервиса (AS-IS)
    │   ├── specs/ architecture/ contracts/ bugs/ notes/ reports/ changes/
    │   └── tasks/ + records/        # Задачи и предметные JSON-записи проекта auth
    │
    ├── billing/                     # Прикладной проект / микросервис 2 (dir_type: project)
    │   └── ...
    │
    └── crm/                         # Отдельный продукт (полностью изолирован, когда не в context.projects)
        └── ...
```

Расширение паспорта проекта `projects/<slug>/.config.json` (обратно совместимо с [`folder-config`](folder-config.md)):

```json
{
  "schema_version": 1,
  "title": "Сервис биллинга (Billing)",
  "aliases": "биллинг|оплата|платежи|инвойсы|подписки",
  "description": "Приём платежей, списания, тарифы и сверки.",
  "related_projects": ["auth", "gateway"],
  "disabled_harness": [
    "doc:projects/core/harness/rules/strict-english-commits.md"
  ],
  "tags": ["billing", "payments", "microservice"]
}
```

- `related_projects` — декларативный список связанных микросервисов/библиотек (позволяет одной командой открыть всю связку `todoc project use billing --with-related`).
- `disabled_harness` — список `id` правил/флоу/скилов из `projects/core/harness/`, которые выключены **локально только для этого проекта**, не затрагивая остальные проекты.

### 2. Схема мульти-проектного стейта (`state.json`) и приоритет резолва контекста

В `~/.local/state/todoc/state-<dataset_id>.json` белый список `ALLOWED_KEYS_V1` расширяется ключом `context.projects` (в том же плоском строковом формате `1–256` символов через `|`):

```json
{
  "schema_version": 1,
  "vars": {
    "context.current_project": "billing",
    "context.projects": "core|billing|auth"
  },
  "updated_at": "2026-11-26T12:00:00Z"
}
```

**Инварианты вычисления эффективного скоупа (`EffectiveScope`):**
1. **Четырёхуровневый приоритет источников контекста** (от старшего к младшему):
   1) разовые флаги CLI вызова (`--project <slug>`, `--projects "a|b"`, `--all-projects`) →
   2) переменные окружения процесса **`TODOC_PROJECT` / `TODOC_PROJECTS`** (для изоляции параллельных агентов в разных терминалах одной машины) →
   3) файл `state-<dataset_id>.json` (`context.current_project` + `context.projects`) →
   4) дефолт при пустом стейте: `focus_project = None`, `active_projects = ["core"]`.
2. **`core` всегда входит в `active_projects` при чтении** (если не передан явный флаг `--no-core` и проект `projects/core/` существует на диске).
3. Если задан `focus_project` (`context.current_project`), он гарантированно присутствует в `active_projects` и стоит первым среди прикладных проектов по приоритету слоёв: **`[focus_project, ...остальные рабочие проекты в порядке списка..., "core"]`**.

### 3. CLI-группа `todoc project` и сквозные флаги переопределения

| Команда / флаг | Назначение и поведение |
|---|---|
| `todoc project list` | Список всех папок `projects/*` с `title`, `description`, `related_projects`, счётчиками и маркерами `[focus]`, `[active]`, `[core]`. Доступна всегда, независимо от текущего стейта. |
| `todoc project show` | Показывает текущий `EffectiveScope` (`focus_project`, `active_projects`, `scope_source`) и сводку по открытым проектам. |
| `todoc project init <slug> [--title "..."]` | Создаёт каркас нового проекта `projects/<slug>/` (`.config.json`, `HOME.md`, `harness/{skills,flows,rules}/`, `ideas/`, `plan/`, `state/`, `tasks/`). |
| `todoc project use <primary> [<extra>...] [--with-related]` | Делает `<primary>` фокусным (`context.current_project`), а `context.projects` выставляет в `core|<primary>|<extra>...` (при `--with-related` добавляет `related_projects` из `.config.json`). Проверяет существование папок проектов. |
| `todoc project add <slug>...` | Подключает один или несколько проектов в параллельную работу (`context.projects`), не меняя текущий `focus_project` (если фокус был пуст — ставит первый добавленный). |
| `todoc project remove <slug>...` | Убирает проект из `context.projects`. Попытка убрать `core` → ошибка `project.core_protected`. Если убирается текущий `focus_project`, фокус переходит на следующий открытый рабочий проект (или сбрасывается в `None`, если остался только `core`). |
| `todoc project focus <slug>` | Переключает точку создания по умолчанию (`context.current_project`) на `<slug>` (автоматически добавляя его в `context.projects`, если ещё не открыт). |
| `--project <slug>` *(сквозной флаг)* | Разово выполняет команду в фокусе проекта `<slug>` (`active_projects = [slug, "core"]`, запись разрешена в `<slug>`, `state.json` не перезаписывается). |
| `--projects "a|b"` *(сквозной флаг)* | Разово задаёт окно параллельных проектов `a`, `b` (+ `core`), фокус = первый в списке (`a`). |
| `--no-core` *(сквозной флаг чтения)* | Исключает `projects/core/` из выборки, когда нужно увидеть результаты строго прикладных проектов без гайдов/терминов ядра. |
| `--all-projects` *(сквозной флаг чтения/валидации)* | Сквозной read-only режим по всем `projects/*` (для глобального аудита, `todoc validate --all-projects`, сквозного поиска). Мутирующие команды с `--all-projects` запрещены. |

### 4. Матрица поведения всех команд CLI в мульти-проектном режиме

Пусть в `state.json` установлено: `current_project = "billing"`, `projects = "core|billing|auth"` (при этом в базе также есть закрытый `projects/crm/`).

| Группа команд CLI | Поведение без доп. флагов |
|---|---|
| **Поиск и списки данных** (`docs search`, `todoc tree`, `docs tree`, `records list`, `records query`, `stale`) | Выборка автоматически ограничена `project IN ('billing', 'auth', 'core')` и `enabled == true` (см. [`toggleable-rules`](toggleable-rules.md)). `crm` полностью исключён. Относительный `--within specs` ищет в `projects/billing/specs/**`, `projects/auth/specs/**` и `projects/core/specs/**`; явный `--within projects/auth/specs` — только в `auth`. |
| **Харнес: `skills tree/read`, `rules list`, выборка `flows`** | Собирает каскад в порядке приоритета слоёв **`billing → auth → core`**, отбрасывая `enabled == false` и элементы из `projects/billing/.config.json -> disabled_harness`. При совпадении имени скила побеждает верхний слой (`billing`). |
| **Сквозные теги (`todoc tags list`)** | Считает словарь тегов, частоты и порог `200` тегов (см. [`unified-tags-and-tag-graph`](unified-tags-and-tag-graph.md)) **только по активным проектам** (`billing`, `auth`, `core`), не смешивая их с тегами `crm`. |
| **Чтение по точному `--id`** (`docs read`, `records read`) | Если объект в `billing`, `auth` или `core` — читается штатно. Если `--id` указывает в закрытый `crm` (`doc:projects/crm/...`) без `--project crm` / `--all-projects` — ошибка `project.out_of_scope` с подсказкой `todoc project add crm`. |
| **Создание новых сущностей** (`docs new`, `records create`, `change open`) | Требует выбранного `focus_project` (если `focus_project == None` — ошибка `project.not_selected`). Короткий путь `--path ideas/retry.md` разворачивается в **`projects/billing/ideas/retry.md`**; шаблон `tasks/{slug}.json` — в **`projects/billing/tasks/billing-{slug}.json`**. Для создания во втором открытом сервисе передаётся `--project auth` (или явный путь `projects/auth/ideas/retry.md`). |
| **Правка, перенос, статусы и теги по `--id`** (`docs edit`, `docs move`, `docs status`, `records update`, `tags set`) | Для рабочих проектов из `context.projects` (`billing`, `auth`) — **разрешено сразу** (включая межпроектный перенос `docs move` из `billing` в `auth`!). Для закрытого `crm` — `project.out_of_scope`. **Для `core` — защита от случайной записи:** если `focus_project != "core"` и не указан `--project core`, попытка мутировать файл внутри `projects/core/**` возвращает `project.core_readonly` с подсказкой `--project core`. |
| **Включение/выключение правил (`rules disable/enable`)** | На правиле из `billing`/`auth` — меняет `enabled` в самом файле правила. На общем правиле из `projects/core/harness/rules/...` при `focus_project = "billing"` (без `--project core`) — **не трогает файл в `core`**, а добавляет/удаляет его `id` в `projects/billing/.config.json -> disabled_harness`! Чтобы выключить правило глобально во всём `core`, указывается `--project core`. |

### 5. Все подводные камни и инженерные решения (12 краевых случаев)

#### Камень 1. Засорение выборок внутренним бэклогом самого `core`
- **Риск:** если в `projects/core/` помимо общего харнеса положить внутренние задачи, баги и черновики разработки самого движка, то в любом микросервисе команда `records list --type task` будет вываливать задачи `core`.
- **Решение (двойной барьер):**
  1. Организационно разработка самого движка `todoc` ведётся в прикладном проекте `projects/todoc/`, а в `projects/core/` живут только разделяемые контуры (`harness/`, `guides/`, `glossary/`, `constitution/`).
  2. Технически в движке: когда `core` подключён *неявно* (`focus_project != "core"` и `core` не запрошен явно через `--project core`), из `projects/core/` в поисковые и списочные выборки прокидываются только разделяемые разделы (`dir_type IN ('harness', 'skill', 'flows', 'rules', 'guides', 'glossary', 'constitution')`), а `tasks`, `bugs`, `ideas`, `plan` ядра скрываются автоматически.

#### Камень 2. Коллизии `record_id` между параллельными микросервисами (`task:0001` vs `task:0001`)
- **Риск:** у Markdown-документов путь уже входит в ID (`doc:projects/billing/specs/api.md` vs `doc:projects/auth/specs/api.md`), но у JSON-записей сейчас `record_id` плоский (`task:0001`, `flow:login`). В двух микросервисах неизбежно возникнет конфликт уникальности первичного ключа в индексе.
- **Решение:** неймспейсинг `record_id` префиксом проекта **`<entity_type>:<project>-<slug>`** (`task:billing-0001`, `flow:auth-jwt-refresh`, `term:core-actor`). При вызове `records create` в проекте `billing` движок подставляет префикс `billing-` автоматически, если агент передал короткий `slug`.

#### Камень 3. Ошибка `skills.duplicate_name` и прибитый `--vault skills` в текущем коде скилов
- **Риск:** сейчас `cli.py:317` сканирует только `<root>/skills`, а `validate_skills` (`src/todoc/application/skills.py:157`) бросает ошибку `skills.duplicate_name`, если два скила в разных папках имеют одно имя — из-за этого проектный скил не может переопределить базовый скил из `core`, и два разных проекта (`shop` и `crm`) не могут иметь одноимённый скил `deploy`.
- **Решение:**
  1. Сканер скилов ищет папки `dir_type == "skill"` внутри `projects/<p>/harness/skills` по всем активным проектам `p`.
  2. Валидатор проверяет уникальность `name` **строго внутри одного проекта `projects/<p>/`**, а совпадение имени между проектами трактует как штатное переопределение (shadowing) по порядку слоёв `focus_project → остальные active_projects → core` (в JSON у перекрытого скила возвращается `"shadowed_by": "projects/billing/harness/skills/deploy"`).

#### Камень 4. Жёсткие корневые `path_template` в `entity_types/*/type.json`
- **Риск:** во всех текущих `type.json` прописано `"path_template": "records/rules/{slug}.json"` или `"tasks/{slug}.json"` от корня датасета.
- **Решение:** при резолве `path_template` любой шаблон, не начинающийся с `projects/`, автоматически разворачивается относительно папки целевого проекта: `projects/{project}/tasks/{slug}.json` (также разрешается явный плейсхолдер `{project}`).

#### Камень 5. Корневые glob-маски в `.todoc/rules/document-rules.json` и `directory-rules.json`
- **Риск:** текущие маски `"specs/**"`, `"flows/**"`, `"contracts/**"`, `"reports/**"`, `"ops/**"` привязаны к началу пути от корня и перестанут срабатывать внутри `projects/billing/specs/...` и `projects/billing/harness/flows/...`. А правило `"glob": "projects/*/"` сейчас назначает подпапке проекта `dir_type: "projects"` вместо `project`.
- **Решение:** заменить правило подпапки на `"glob": "projects/*"` → `"dir_type": "project"` (`priority: 110`), а все типовые файловые и папочные правила перевести на глубинно-независимые сегментные маски `**/specs/**`, `**/flows/**`, `**/rules/**`, `**/contracts/**`, `**/reports/**`, `**/ops/**`.

#### Камень 6. Неоднозначность коротких wikilinks `[[overview]]` при нескольких открытых проектах
- **Риск:** в `projects/billing/specs/overview.md` и `projects/auth/specs/overview.md` одинаковое имя файла. Если в документе `billing` написано `[[overview]]`, подключение второго проекта `auth` в `state.json` внезапно сделало бы ссылку двусмысленной (`ambiguous link`)!
- **Решение (лексический скоуп ссылок — ссылка не должна зависеть от `state.json`!):** резолв относительных ссылок и коротких wikilinks всегда детерминирован и зависит **только от проекта самого файла-источника**, а не от текущего `state.json`:
  1) сначала ищется совпадение внутри **своего проекта** (`projects/billing/**`);
  2) если внутри своего проекта совпадений нет — ищется в разделяемом **`projects/core/**`**;
  3) для межпроектной ссылки между двумя прикладными сервисами (`billing → auth`) требуется явный путь или ID (`[[projects/auth/specs/overview.md]]` или `flow:auth-jwt`). Тогда включение/выключение проектов в стейте никогда не ломает ссылки.

#### Камень 7. Межпроектные связи на временно закрытые проекты и безопасность `todoc docs move`
- **Риск А:** документ в активном `billing` ссылается на контракт в `gateway`, но `gateway` сейчас не добавлен в `context.projects`. Нельзя считать такую ссылку битой при валидации и нельзя ронять `relations graph`.
- **Риск Б:** агент переносит или переименовывает контракт внутри `auth` через `todoc docs move`, когда `billing` закрыт в стейте — если пропатчить ссылки только в открытых проектах, ссылка в `billing` протухнет!
- **Решение:**
  - Валидатор ссылок и ре-райтер обратных ссылок в `todoc docs move` (см. [`docs-move`](docs-move.md)) при поиске входящих рёбер **всегда используют глобальный индекс `relations` всей базы** и атомарно обновляют входящие ссылки даже в проектах вне `context.projects` (с явным отчётом `updated_cross_project_refs` в `--preview`!).
  - В пользовательском `relations graph` без `--all-projects` узлы закрытых проектов возвращаются как компактные граничные заглушки (`{"id": "...", "project": "gateway", "in_active_scope": false}`) без раскрытия их подграфа, но с подсказкой `todoc project add gateway`.

#### Камень 8. Гонки параллельных агентов / терминалов за один файл `state-<dataset_id>.json`
- **Риск:** разработчик запустил в двух вкладках терминала двух агентов на одном репозитории: первый чинит `billing`, второй — `crm`. Оба пишут в `~/.local/state/todoc/state-<dataset_id>.json` и перетирают контекст друг другу.
- **Решение:** поддержка переменных окружения сессии **`TODOC_PROJECTS="core|crm"`** и **`TODOC_PROJECT="crm"`** (плюс опциональный `TODOC_STATE_SESSION=<id>`, адресующий отдельный файл `state-<dataset_id>-<session>.json`). Переменные окружения перекрывают общий файл стейта без единой гонки записи.

#### Камень 9. Слепота агента к активному фильтру («почему поиск ничего не нашёл?»)
- **Риск:** агент на старте новой сессии не проверил `state.json`, ищет документ из `crm`, находясь в скоупе `billing`, получает `total: 0` и решает создать дубликат документа в `billing`.
- **Решение:**
  1. Во все конверты ответов CLI добавляется блок `scope`: `{"focus_project": "billing", "active_projects": ["core", "billing"], "scope_source": "state"}`.
  2. Если поисковый запрос вернул `0` результатов в активном скоупе, но в `index.sqlite` есть точные совпадения в других проектах, движок возвращает безопасную подсказку в `next_actions` / `hints`: `"В текущем скоупе (core|billing) совпадений 0; найдено 2 совпадения в закрытых проектах: crm (подключить: todoc project add crm)"` — без слива содержимого чужих документов, но с защитой от создания дублей!

#### Камень 10. Быстрая фильтрация в `index.sqlite` без полного скана
- **Риск:** фильтрация тысяч файлов по проектам в Python после `FTS5`-поиска замедлит выборки и сломает `LIMIT` на больших базах.
- **Решение:** в схему `index.sqlite` (см. [`sqlite-storage-drivers`](sqlite-storage-drivers.md)) в таблицу `items` закладывается колонка **`project TEXT NOT NULL`** (первый сегмент после `projects/`) и составные индексы `idx_items_proj_enabled_kind(project, enabled, kind)` и `idx_items_proj_doctype(project, doc_type)`. Все выборки фильтруют `items.project IN (...)` прямо внутри SQL-запроса.

#### Камень 11. Преобразование сущности в папку (`todoc folderize`) внутри проекта
- **Риск:** `todoc folderize` (см. [`entity-to-folder`](entity-to-folder.md)) создаёт вложенные подпапки (`projects/billing/ideas/payment-v2/plan/`), что увеличивает глубину пути.
- **Решение:** вычисление принадлежности к проекту всегда берётся строго по префиксу `projects/<slug>/` (`parts[0] == "projects"` → `project = parts[1]`), поэтому любая глубина вложенности внутри проекта сохраняет `project = "billing"`, а сегментные правила `**/plan`, `**/rules`, `**/specs/**` продолжают работать на любой глубине.

#### Камень 12. Бесшовная миграция существующих плоских баз (включая `demo/`)
- **Риск:** существующие датасеты уже содержат файлы в корне (`ideas/`, `plan/`, `tasks/`, `skill/`, `skills/`). Если включить требование `projects/*` одномоментно без режима совместимости, старые базы перестанут открываться.
- **Решение:**
  1. Режим определения топологии по `dataset.json` (`"layout": "projects" | "legacy_flat"`, либо авто-детект наличия `projects/`): старые плоские датасеты продолжают работать до миграции, выдавая `notice` о доступном переезде.
  2. Команда миграции **`todoc project migrate-flat --into <slug> [--extract-core]`** (--preview / --apply): переносит общий харнес (`skills/`, `skill/`, `guides/`, `glossary/`) в `projects/core/`, а проектные артефакты — в `projects/<slug>/` через транзакционный движок `docs move` с автоправкой всех `id`, ссылок и `derived_from`.

## План внедрения

1. **Фаза 1 — Типизация `dir_type: project`, глубинные маски и колонка `project` в индексе:**
   - Добавить дескриптор `dir_type: project` (`projects/*`), перевести файловые/папочные правила на `**/...`, добавить вычисление `project` для каждого элемента и расширить схему `.config.json` полями `related_projects` и `disabled_harness`.
   - *Acceptance:* элементы внутри `projects/<slug>/**` получают `project = "<slug>"`, валидация проходит в `0` диагностик.
2. **Фаза 2 — Мульти-проектный `state.json` (`EffectiveScope`) и группа `todoc project`:**
   - Расширить `state.py` ключом `context.projects`, реализовать резолвер `EffectiveScope` (CLI-флаги → `TODOC_PROJECT(S)` → `state.json` → `["core"]`) и команды `todoc project list|show|init|use|add|remove|focus`.
   - *Acceptance:* параллельное подключение `project use billing auth --with-related`, защита `remove core`, изоляция через `TODOC_PROJECTS`.
3. **Фаза 3 — Применение скоупа во всех командах чтения/записи CLI и каскадный харнес:**
   - Прокинуть `EffectiveScope`, блок `scope` в конверт ответа, подсказку о совпадениях в закрытых проектах, префиксацию `record_id` (`<type>:<project>-<slug>`), защиту `core` на запись, локальный `disabled_harness` и многослойный сканер скилов/правил/флоу (`focus → active → core`).
   - *Acceptance:* полный цикл параллельной работы в 2 микросервисах + `core`, `100%` branch coverage в `tests/`.
4. **Фаза 4 — Мигратор плоских баз `project migrate-flat` и обновление стартовых скилов `core`:**
   - Реализовать `--preview`/`--apply` миграцию плоского датасета на `projects/core/` + `projects/<slug>/` и обновить агентский контракт старта сессии (`todoc project show`).

## Открытые вопросы

- **Автоподключение `related_projects` по умолчанию при `project use <slug>`:** включать ли связанные микросервисы из `.config.json` только по явному флагу `--with-related` или сразу по умолчанию (с флагом `--isolated` для отключения)? Безопаснее и экономнее по токенам включать **по явному `--with-related`**, а в ответе `todoc project use billing` выводить подсказку: `"Связанные проекты (не подключены): auth, gateway — подключить: todoc project add auth gateway"`.
- **Лимит числа одновременно открытых проектов в `context.projects`:** стоит ли вводить мягкое предупреждение (`warning`), если в `context.projects` открыто больше `5–7` проектов одновременно (риск размывания фокуса и роста выдачи)? Да — мягкий `warning` при `> 5` активных проектах без жёсткого блока.

## Связанные документы

- [Идея: агентский стейт — `state.json` в движке (v1 — текущий проект)](agent-state.md)
- [Идея: `.config.json` — самоописание папок](folder-config.md)
- [Идея: хранилище-движок скилов (`skills-engine`)](skills-engine.md)
- [Идея: отключаемые правила харнеса (`doc_type: rules` и `--include-disabled`)](toggleable-rules.md)
- [Идея: `todoc tree` — типизированная проекция дерева в CLI](typed-tree-projection.md)
- [Идея: переключаемые драйверы хранения (`index.sqlite` + `FTS5 BM25`)](sqlite-storage-drivers.md)
- [Идея: сквозная система тегов (`todoc tags` и `--tag-in`)](unified-tags-and-tag-graph.md)
- [Идея: `todoc docs move` — транзакционный перенос документа](docs-move.md)
- [Идея: `todoc folderize` — преобразование сущности в папку-домен](entity-to-folder.md)
- [Идея: стандарт именования типов (`snake_case`) и папка `state` (`AS-IS`)](type-naming-and-state-dir.md)
