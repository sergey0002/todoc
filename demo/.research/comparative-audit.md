---
id: doc:comparative-audit
title: "Comparative audit: статический аудит Agent Skills"
doc_type: research-report
lang: ru
source: docs/research/knowledge-base-comparative-audit.md
copied: true
created: 2026-11-26
updated: 2026-11-26
tags: [research, research-report, comparative, статический]
---

# Сравнительный аудит: может ли план `todoc` стать переносимой памятью для агентов?

**Дата:** 24 ноября 2026 года  
**Связанный план:** [`plan.md`](engineering-plan.md)  
**Загруженные материалы:** `/home/user/docs/research/skills-audit/`  
**Вывод в одну строку:** план хорошо задаёт будущий локальный CLI для диагностики, поиска и адресного чтения файлов; он **не проектирует готовую систему памяти с объектами Task / Plan / Idea / Session и их жизненным циклом**. И, независимо от архитектуры, в `/home/user/todoc/` пока нет реализации — там только `.gitkeep`.

## 1. Что проверено и чего аудит не доказывает

Я скачал исходный gist Karpathy и несколько репозиториев Skill/KB, зафиксировал ревизии и статически прочитал их инструкции, схемы, шаблоны и выбранные вспомогательные файлы. Ничего не устанавливал, не запускал и не подключал к пользовательским данным; команды и сторонние скрипты не исполнялись. Это **аудит описанных workflow и моделей данных**, а не runtime-тест, независимый benchmark качества или проверка рыночного спроса. Внешние страницы, README и Skill-файлы описывают намеренное поведение, но сами по себе не доказывают, что агент всегда ему следует.

| Источник | Зафиксированная ревизия | Что просмотрено и зачем |
|---|---|---|
| [Karpathy — исходный LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) | `ac46de1ad27f92b28ac95459c782c07f6b8c964a` | `llm-wiki.md`. Это собственная идея/дизайн-файл для передачи агенту, **не официальный исполняемый Skill и не готовый CLI**. |
| [Astro-Han/karpathy-llm-wiki](https://github.com/Astro-Han/karpathy-llm-wiki) | `eafcc77001e496cc43499e4923b663aec722c813` | `SKILL.md`, README, шаблоны, `check_evidence.py`, tests: проверка evidence-grounding, raw/wiki/workflow. Неофициальная реализация паттерна. |
| [vanillaflava/llm-wiki-skills](https://github.com/vanillaflava/llm-wiki-skills) | `ff6f7be1a0e397192a1ac4a0d06d298062e9b208` | README, `wiki-config`, `wiki-ingest/query/lint/integrate/crystallize`, схема и шаблон domain-home: настройка, типы страниц, приём источников и фиксация результата сессии. |
| [eugeniughelbur/obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain) | `7f4ddfdafa4e4652b01209f1847c3a3fc7d07754` | README, основной Skill, схема vault, task/idea/project workflows, правила записи: наиболее прямой пример из выборки для задач, проектов и идей; много автоматизации, поэтому риск/сложность тоже важны. |
| [AgriciDaniel/claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian) | `2e545563172f97f02ecaaaab376ceea1246a0583` | Оркестрация, ingest/query/lint/save/retrieve, типы страниц, provenance и transaction contracts: образец ограничений записи, воспроизводимых операций и доказательной модели. |
| [bholmesdev/llm-knowledge-base-skills](https://github.com/bholmesdev/llm-knowledge-base-skills) | `28ac652395adb0522899594b86ce86156ac08695` | README, enrich-note, enrich loop, refresh-wiki: теги, provenance, backlinks, периодическое обслуживание; облачная автоматизация — отдельный слой. |
| [ConardLi/rag-skill](https://github.com/ConardLi/rag-skill) | `e759a1de84debbc02726ee61946522c830da24c1` | README и `kb-retriever/SKILL.md`: многоформатный, бюджетный поиск по иерархическим индексам. README помечает репозиторий архивным. Не источник для модели долговременных объектов. |
| [Open Knowledge CLI](https://github.com/openknowledge-sh/openknowledge) | `99b05e27ce328db3ae4d31cd0e30f178ead6de30` | Частично скачанные Skill и страницы search/validate/setup: референс для Markdown-документации, проверок и разделения shipped/planned. Это не полный аудит всего продукта. |

Тяжёлая демонстрационная папка `knowledge/` у Conard и её Git pack удалены из временной копии после осмотра Skill/README; сам Skill и README сохранены. Это убрало ненужные примеры PDF/XLSX, а не исходные материалы аудита.

## 2. Прямой ответ о готовности

### Если цель — проверять и искать по существующим папкам

**Как план архитектуры — хорошая, но ещё не утверждённая спецификация MVP.** В нём уже есть разделение формата файла, семантического `doc_type` и роли папки `dir_type`; декларативные типы/схемы, переносимые root-relative ссылки, stable IDs, Markdown/CSV/JSON readers, точные locations, машинные diagnostics, ограниченный поиск/чтение и review-first repairs. Для конкретного пользователя можно будет описать тип документа `plan` или `idea` и классифицировать существующий Markdown-файл по явным правилам.

Но это не означает готовый продукт: нет кода, а пользовательские типы ещё предстоит определить и реализовать.

### Если цель — память, которая умеет жить с задачами, планами, идеями и знаниями

**Нет, текущий план этого не обеспечивает.** Он типизирует прежде всего *документы и папки*, а не отдельные жизненные объекты. В плане нет готовых `Task`, `Idea`, `Project/Plan`, `Decision`, `Session` и `Source` схем с понятными полями, переходами статусов и командами для работы с ними. `dir_type: plan` — это тип папки, не менеджер планов; `doc_type: plan` можно будет настроить, но он сам по себе не даст сроков, приоритетов, списка следующих действий, завершения или связи с задачей/проектом.

Иными словами: «найти Markdown-документ, классифицированный как idea» — достижимо в предполагаемой архитектуре после настройки и реализации; «вести идеи, превращать выбранную идею в проект и связывать с задачами» — не описано. То же различие относится к файлу со списком задач и самостоятельному объекту задачи.

## 3. Сравнение подходов

| Критерий | Obsidian | Karpathy LLM Wiki (исходная идея) | План `todoc` |
|---|---|---|---|
| Основная роль | Готовое человекоориентированное приложение/редактор локальных Markdown-vault: файлы, ссылки, backlinks, граф, поиск и расширения. | Паттерн накопления: immutable raw sources → поддерживаемая LLM wiki → инструкции/schema; ingest/query/lint, индекс и журнал. | Отдельный CLI/Skill для scan/check/search/read по существующим корням; источники — истина, индексы — производные. |
| Задачи, планы, идеи | Можно представить Markdown-заметками; задачи/даты/доски обычно зависят от conventions, шаблонов и/или community plugins. Удобен для ручного ведения и визуального просмотра. | Не задаёт универсальной схемы Task/Idea/Project. Пользователь и агент выбирают структуру. | Пользовательские `doc_type` и правила предусмотрены как инфраструктура, но нет готовой task/idea модели, workflow или task-oriented queries. |
| Накопление синтеза | Приложение даёт среду для заметок; compounding/обновление знаний организует пользователь, плагины или внешний агент. | Это центральная идея: источники интегрируются в существующие страницы, конфликты/устаревшие сведения отмечаются, ценные ответы могут вернуться в wiki. | Автосинтез намеренно не включён в MVP. Нет отдельного слоя «сырьё → синтезированная wiki». |
| Поиск для агента | Зрелый UX/поиск и опциональный CLI; Obsidian CLI зависит от установленного и запущенного приложения. | При умеренном размере достаточно индекса и поиска страниц; расширенный retrieval — опция. | Сильная планируемая часть: ограниченный context budget, ссылки на источник, строка/row/JSON Pointer, пагинация, без обязательного vector/RAG. Ещё не реализовано. |
| Целостность исходных CSV/JSON | Не основная задача заметочного приложения; импорт таблиц не равен source-native schema validation. | Gist сосредоточен на markdown wiki и grounded synthesis, а не на точной проверке исходной таблицы. | Самая правдоподобная зона отличия: валидировать исходные CSV/JSON и давать проверяемую location-aware диагностику, не конвертируя и не переписывая данные. |
| Безопасность и контроль записи | Богатый интерфейс, но политика зависит от конкретных плагинов/интеграций. | Общие правила предлагаются агенту; исполняемый security/transaction contract в gist не специфицирован. | Уже предусмотрены read-only MVP, preview/hash/diff и отдельный `--apply`; для будущих многофайловых workflows ещё не описаны полноценная транзакция/восстановление. |
| Синхронизация, мобильность, UI | Сильное преимущество приложения и его экосистемы. | Сам gist не предоставляет UI или sync — файлы можно положить в Git/Obsidian. | Папку планируется переносить без абсолютных путей, но отдельная стратегия backup/sync/distributed writers и богатый UI не входят в текущую спецификацию. |

**Практический итог:** `todoc` должен дополнять Obsidian, а не пытаться заменить его интерфейс. Его предложенная сила — детерминированный source-native QA и точные места ошибок в смешанной папке. Karpathy Wiki решает другую задачу: агентная компиляция знаний и развитие синтеза между сессиями. Эти подходы могут сосуществовать, но один не следует называть другим.

## 4. Что именно показали Agent Skills

### Karpathy gist и его Skill-реализации

- **Исходный gist** прямо обозначает себя как абстрактный idea file, который пользователь передаёт агенту для совместной конкретизации. Его ключевое отличие от обычного RAG — не более хитрый поиск, а persistent wiki, которую дополняют и связывают при ingest, затем используют для query. Индекс и append-only log помогают навигации/аудиту; lint включает противоречия, stale claims, orphan pages и пробелы.
- **Astro-Han** превращает паттерн в конкретный Skill: `raw/` неизменяемый, `wiki/` — синтезируемые страницы, `index.md` + `log.md`; есть ingest/query/lint, правила верности источнику, статусы disputed/outdated и read-only evidence script. Это хороший референс для grounding и дисциплины источников, но не система типов задач/проектов.
- **vanillaflava** делит операции на config, ingest, query, lint, integrate и crystallize. В конфигурации — schema страниц и пользовательские шаблоны; `crystallize` превращает выбранный результат сессии в долговременную заметку, стараясь обновлять существующий hub. В page types есть, например, `profile`, `note` и `domain-home`, но наличие типа страницы ещё не даёт жизненного цикла задачи с due date/recurrence.

### Системы, ближе к повседневной агентной памяти

- **obsidian-second-brain** из просмотренной выборки — наиболее наглядный пример, что для реального workflow нужны отдельные команды и связи: task с `status`, `due`, priority, project/person; проекты, доски и daily notes; идея со стадиями capture/explore/graduated; сохранение решений и контекста сессий. Это не просто маркировка файлов. При этом Skill активно предписывает многосторонние правки vault, автоматическое распространение, hooks и scheduled agents. Это функционально богато, но сложнее, сильнее привязано к Obsidian и опаснее копировать без транзакционного контроля, согласия и проверок. README/Skill заявляют эти возможности; здесь они не запускались.
- **claude-obsidian** — полезнее как референс безопасности: запрос/ответ разделены с записью, операции группируются в reviewed transaction bundle, есть hash preconditions, inspect/apply/recovery, immutable captures, источник и claim ledgers, явные границы egress и read-only retrieval. При этом код и интеграционные соглашения заметно крупнее/специфичнее, чем целевой компактный `todoc`; прямое копирование архитектуры было бы избыточно.
- **Conard `rag-skill`** показывает progressive retrieval по иерархическим `data_structure.md`, с отдельным подходом к PDF и Excel и локальными page/row references. Это референс поиска, а не компаундируемая модель памяти; README помечает проект архивным.
- **bholmesdev** показывает лёгкое обогащение заметки tags/source/backlinks и отдельный unattended loop/облачный schedule. Это удобные maintenance patterns, но они не заменяют типизированную модель или надёжные границы записи.
- **Open Knowledge Wiki Skill** полезен как дисциплина документации: держать wiki в соответствии с реальным shipped behavior, отделять planned features от implemented и проверять документацию. Сам по себе он не реализует личную память или Task model.

Ни один из этих статических обзоров не подтверждает точность, безопасность или удобство навыка при реальном запуске. Например, правила Skill — не то же самое, что технически принудительная транзакция; наличие слова `task` в имени папки — не то же самое, что валидируемая task schema.

## 5. Coverage matrix: текущий план против желаемой «структурированной памяти»

| Возможность | Что уже есть в `plan.md` | Аудит / пробел |
|---|---|---|
| Файл vs формат vs классификация | Явное разделение `format`, `doc_type`, `dir_type`; правила и JSON Schema в DATA_ROOT. | **Хорошая основа, но это классификация документов.** Не эквивалент типизированных записей и бизнес-операций. |
| Отдельные Task / Plan / Idea / Decision / Person / Project | Можно создать новые декларативные типы документа, есть folder IDs и document IDs. | **Не предусмотрены как готовые объекты.** Нет базового общего контракта, встроенных профилей и поддерживаемых операций по типам. Персона «пользователь / автор заметки / ответственный» также не моделируется. |
| Статусы, сроки, исполнители, приоритеты, повторяемость | `status` присутствует в общем output/search-фильтрах; type config может добавить ограничения. | **Недостаточно для управления задачами.** Нет семантики полей, переходов состояния, due/overdue, assignee, priority, recurrence, completion или acceptance tests для этих запросов. |
| Связи | Planned Markdown links/backlinks, parent folders, ограниченная навигация. | **Частично.** Нет декларативных типов отношений вроде `belongs_to`, `blocks`, `derived_from`, `supports`, `contradicts`, `promoted_to`; нет их валидации/обратных проверок. |
| Capture и сортировка | `new`/`capture` в inbox, ручная команда; import отдельный и review-first. | Нет очереди triage/dedupe с решениями «новая запись / обновить / no-op», классификации входящего разговора/файла и явной передачи из capture в durable record. |
| Неизменяемые источники и synthesis layer | Сохраняются существующие исходники, hash и точные locations; attachments остаются opaque. | **Нет Karpathy-архитектуры** `immutable raw → compiled wiki`, source intake/compile/cascade update, отдельной generated knowledge layer и source archive. Это сознательно исключено из MVP. |
| Происхождение и качество evidence | Source/path/hash/location и parser/schema metadata для документа. | Нет отдельного source ledger + claim ledger, статусов принятия/оспаривания claims, независимости источников, valid-time vs recorded-time, freshness/review_due и политики не разрешать конфликт автоматическим выбором. Для обычного file QA это может быть лишним; для исследовательской памяти важно. |
| Агент между сессиями | Родительский Skill, explicit roots, machine-readable responses, indexes/cache. | Нет session/domain home, hot cache/current state, start-of-session bootstrap, решения/открытые вопросы из разговора, сохранения/кристаллизации сессии и разделения transient context от durable memory. |
| Поиск/ответы | Сильный progressive search/read с budget, snippets, ID/location, truncation и benchmark. | Нет стандартных task-oriented запросов («что просрочено», «какой следующий шаг», «почему выбрали решение», «какие идеи ещё не продвинуты»), записи хорошего ответа назад или тестового набора для таких задач. |
| Проверка качества знаний | Parser/schema, broken links, diagnostics, safe-fix concept, тестирование false positives. | В основном механическая целостность. Нет автоматизированной семантической проверки contradictory/stale claims, дубликатов смысла, отсутствующих связей/источников, качества synthesis; не следует просто поручать это LLM без evidence workflow. |
| Теги, алиасы, vocabulary | Front matter может содержать поля; Obsidian profile проверяет часть wikilinks. | Нет общего tag registry/ontology, правил reuse tags, устойчивых aliases для объектов или duplicate-resolution workflow. |
| Запись и согласованность | Read-only source MVP; hash-protected, diff-first и post-validation для будущих fixes. | Для записи сразу в несколько файлов нет operation-level transaction bundle с одним approval digest, journal/rollback/recovery и единым operation ID. Также не описан single-writer/sync protocol для Obsidian/cloud editors. Это не блокер read-only MVP, но блокер широких agent writes. |
| Приватность и фоновые действия | Local-first, без скрытого LLM/network search; входящие файлы недоверенные. | Хорошая база. Для личной памяти дополнительно нужны sensitivity/retention rules, explicit scopes на чтение приватных папок и отдельное согласие на сеть/транскрипцию/синхронизацию. Никакого auto-save всего разговора или background job по умолчанию. |
| Переносимость | Relative paths, multi-root isolation, stable IDs, rebuildable index/cache. | **Планируется хорошо для перемещения папки**, но это не backup/restore, версия/совместное редактирование, облачная синхронизация или миграция произвольного vault без конфликтов. Эти темы не решены. |

## 6. Рекомендуемые решения для плана

1. **Не расширять текущий MVP молча.** Сохранить базовую гипотезу `todoc` как local-first validator + precise search/read для смешанных источников. Это хорошо отделяет CLI от Obsidian и LLM Wiki, остаётся измеримым и не требует строить второй мозг до доказательства необходимости.
2. **Явно назвать текущую границу:** `doc_type` классифицирует файл/документ; это не обещание first-class задач, планов, идей или памяти агента. Обновить критерии готовности так, чтобы никто не счёл «plan folder + JSON type config» поддержкой task management.
3. **Добавить отдельное условие/поздний профиль, если пользователь подтверждает цель memory KB.** Перед его кодированием определить: общий envelope (`id`, `type`, `created`, `updated`, `status`, `tags`, `source_refs`, `relations`); schema/version/custom fields; встроенные поля и переходы для Task, Project/Plan, Idea, Decision, Source, Session; stable ID/alias policy; миграции; команды capture/list/update/query/archive.
4. **Task-профиль минимум:** status, due-date timezone semantics, priority, owner/assignee, project, dependencies/blocked-by, recurrence, completion date; правила перехода статусов; канонический источник истины (файл, отдельная запись или board — не три независимых копии). Запросы «open/overdue/due soon/by project/blocked» должны проверяться на fixtures.
5. **Idea/Plan-профиль минимум:** для идеи — lifecycle `captured → exploring → validated → promoted/parked/archived` (точные имена настраиваемы), evidence/open questions и связь при продвижении; для плана/проекта — цель, owner, статус, срок/этапы, next action, decision links. Это предлагаемые минимумы для обсуждения, не уже утверждённая схема.
6. **Добавить связи и capture workflow до называния продукта agent memory:** явные типы отношений + проверка target; путь `capture → triage → confirm/merge/no-op → link → retrieve → update/complete/archive`; готовые agent scenarios. Не автозаписывать всю переписку: сохранять только выбранный пользователем scope, а неопределённое содержание предлагать как draft.
7. **Если появится накопление знаний по источникам:** отдельная immutable capture/manifest, source metadata/provenance, generated synthesis pages, claim evidence/conflict/freshness policy, query citations и lint/report. Не сливать это с текущим детерминированным `check` и не делать все извлечённые LLM-выводы «истиной».
8. **До широких agent writes усилить write contract:** operation ID; один bundle на логическое изменение; expected hashes для всех touched paths; review/approval над точным планом; serialized apply; восстановление при сбое; проверка изменения в редакторе/sync; пути/rights confinement; offline-by-default и egress consent. Для MVP с чтением/одним новым Markdown-файлом оставить более лёгкий механизм.
9. **Проверять отдельно три результата:** `todoc` source QA (CSV/JSON/Markdown diagnostics); удобство Obsidian (редактор и навигация); качество агентной памяти (capture, recall, typed actions across sessions). Один успешный test search не является доказательством остальных.

### Предложенный go/no-go для задачи пользователя

- Если требование — **«пометь мои файлы/заметки по типам и найди фрагмент агенту»**, план подходит после выбора конкретных типов и реализации CLI; полноценный менеджер задач не нужен.
- Если требование — **«задачи, проекты/планы и идеи с состоянием, сроками, связями и продолжением между сессиями»**, сначала принять отдельный memory-profile scope и добавить его модель/приёмочные тесты. Один `doc_type` на Markdown-файл недостаточен.
- Если требование — **«пусть агент регулярно читает источники, переписывает wiki и синтезирует знания»**, это третья задача: выбрать/использовать LLM Wiki skill или интегрироваться с ним; это прямо выходит за рамки нынешнего MVP `todoc`.

## 7. Основные ссылки

- [Karpathy — исходный gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [Astro-Han — LLM Wiki Skill](https://github.com/Astro-Han/karpathy-llm-wiki)
- [vanillaflava — шесть LLM Wiki Skills](https://github.com/vanillaflava/llm-wiki-skills)
- [obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain)
- [claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian)
- [bholmesdev — LLM knowledge base skills](https://github.com/bholmesdev/llm-knowledge-base-skills)
- [ConardLi — RAG retrieval Skill (archived)](https://github.com/ConardLi/rag-skill)
- [Open Knowledge CLI](https://github.com/openknowledge-sh/openknowledge)