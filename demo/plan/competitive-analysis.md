---
id: doc:competitive-analysis
title: "Competitive analysis: конкурентный анализ"
doc_type: competitive-analysis
lang: ru
source: docs/plan/competitive-analysis.md
copied: true
---

# Конкурентный анализ `todoc`: CLI, возможности, портабельность, аудитория

**Дата:** 24 ноября 2026 года. **Статус:** feature audit по официально описанным функциям и документации; не benchmark качества, не market sizing, не доказательство спроса.
**Связанные документы:** [`constitution.md`](constitution.md) — нормативные требования и итоговый продукт; [`../plan.md`](../.research/engineering-plan.md) §3 — исходный срез аналогов; [`../docs/research/knowledge-base-comparative-audit.md`](../.research/comparative-audit.md) — статический аудит Agent Skills по снимкам в `docs/research/skills-audit/`.
**Метод:** (1) разбор референсов из `docs/research/skills-audit/` (8 репозиториев, snapshot commit hashes — в аудите); (2) веб-поиск дополнительных конкурентов (24 ноября 2026); (3) сверка CLI-вход/выход по официальным README/docs/releases. Версии быстро меняются (особенно QMD, Open Knowledge, obsidian-second-brain, Basic Memory) — перед реализацией перепроверить лицензии, стабильные релизы и фактические команды на закреплённых версиях.

> **Как читать таблицы.** `●` — полная поддержка, `◐` — частичная/опциональная/через плагин, `○` — нет, `—` — неприменимо. «todoc (план)» — целевое состояние по конституции, не существующая функция (реализации пока нет).

---

## 1. Ландшафт: 7 категорий конкурентов

| Категория | Суть | Примеры | Отношение к `todoc` |
|---|---|---|---|
| **A. Markdown PKM + Obsidian-экосистема** | Человекоориентированные редакторы локальных Markdown-vault: файлы, ссылки, backlinks, граф, поиск, плагины | Obsidian (+ CLI, Dataview, Tasks), Logseq, Foam, Quartz, SiYuan, Trilium, SilverBullet, Joplin, Zettlr | Obsidian — **совместимый просмотрщик/редактор**, не конкурент ядра. Остальные — референсы хранения/графа/публикации |
| **B. Local search / RAG CLI** | Локальный поиск по Markdown/документам для человека и агента: BM25/vector/hybrid, MCP, eval | QMD, mdkb, Open Knowledge CLI (`okn`), okfcli/okf, Khoj (частично) | **Прямые конкуренты ядра поиска/валидации.** `todoc` не должен конкурировать «ещё одним общим поиском» |
| **C. LLM Wiki / compounding KB** | Агент компилирует источники в связную wiki: `raw/ → wiki/`, ingest/query/lint, синтез, противоречия | Karpathy LLM Wiki gist + Astro-Han/vanillaflava реализации, OpenKB, obsidian-second-brain, claude-obsidian, bholmesdev skills, ConardLi rag-skill | **Другая задача** (компиляция/синтез), не source-native QA. Возможен отдельный профиль или интеграция |
| **D. Agent memory (вектор/граф)** | Память агента как API: extract-and-store, temporal graph, self-managing blocks | Mem0 (+ OpenMemory MCP), Zep/Graphiti, Letta/MemGPT, Cognee, Supermemory, mcp-memory-service | Конкуренты **только если** `todoc` пойдёт в memory-профиль. В MVP — не конкуренты (нет скрытой LLM-памяти) |
| **E. App-centric RAG / Notebook** | Готовое приложение «загрузи документы и задавай вопросы»: workspaces, chunking, embeddings, chat, агенты | AnythingLLM, Khoj, Open Notebook, RAGFlow, Dify, FastGPT, NotebookLM/Gemini Notebook | Конкуренты для «чат по документам». `todoc` не повторяет app-centric RAG без отдельной потребности |
| **F. Typed / object-based PKM** | Пользовательские типы/поля/запросы как первый класс: supertags, object types, databases | Tana (supertags), Capacities (object types), Notion (databases), Anytype, AFFiNE, AppFlowy | **Ближайшие концептуальные конкуренты** для `entity_type` + query/aggregate. Все — cloud/app-centric, не file-native CLI |
| **G. Wiki / docs platforms** | Командные wiki и docs-as-code: Markdown + front matter + links + CI | Open Knowledge Format (OKF) + okfcli/okf + okfctl, Wiki.js, Outline, Docmost, Docusaurus/MkDocs | Референсы interchange-формата и CI-валидации. `todoc` может быть OKF-совместимым, не требовать OKF |
| **H. Spec-driven development** | Спецификация как источник истины: жизненный цикл изменения, дельты, фазовые гейты, slash-команды для агентов | OpenSpec (Fission-AI), GitHub Spec Kit (`specify`), MySpec, BMad, Kiro | **Соседний слой, не прямой конкурент.** Они ведут *процесс изменения*, `todoc` проверяет *состояние*. Дополняют друг друга; см. `history-and-changes.md` §16 |

**Вывод ландшафта:** пустой ниши «папка + Markdown + поиск» нет. Правдоподобная ниша `todoc` — **связка** «пользовательские типы + маршрутизация папок + type-directed agent workflows + schema-checked file writes + explicit relations/query + swappable derived indexes» поверх переносимых файлов. Каждый компонент по отдельности распространён; moat не доказан.

---

## 2. Референсы из `docs/research/skills-audit/` (8 репозиториев)

Статический разбор по снимкам; репозитории не устанавливались, скрипты не запускались. Детали и commit hashes — в [`../docs/research/knowledge-base-comparative-audit.md`](../.research/comparative-audit.md).

| Репозиторий | Что это | Что взять в `todoc` | Что не копировать |
|---|---|---|---|
| **Karpathy LLM Wiki gist** (`karpathy-original-gist`) | Абстрактный idea/design file: `raw/` immutable → `wiki/` синтез → schema; ingest/query/lint; `index.md` + `log.md`. Не исполняемый Skill/CLI | Различение «сырьё vs синтез»; идею `index.md`/`log.md`; lint как health check | Не делать gist «ядром» `todoc`. Синтез — отдельный профиль (§6.10 конституции) |
| **Astro-Han/karpathy-llm-wiki** | Skill-реализация паттерна: `raw/`/`wiki/`, ingest/query/lint, проверка source fidelity (`check_evidence.py`), статусы disputed/outdated | Evidence-grounding дисциплину; read-only evidence script как референс | Не копировать как код/промпты без проверки. Не обещать claim-level freshness в MVP |
| **vanillaflava/llm-wiki-skills** | 6 Skills: config/ingest/query/lint/integrate/crystallize; schema страниц, шаблоны, domain-home; `crystallize` фиксирует результат сессии | Разделение операций; идею `crystallize` для memory-профиля; page types как референс | Наличие типа страницы ≠ lifecycle задачи. Не смешивать с детерминированным `check` |
| **eugeniughelbur/obsidian-second-brain** | Obsidian-oriented workflows: task/project/idea, daily notes, boards, межсессионный контекст; 33–47 slash-команд (`/obsidian-save`, `/obsidian-task`, `/obsidian-capture`, `/obsidian-find`, `/obsidian-project`, `/obsidian-graduate`, `/research`, `/obsidian-health` и др.) | Полный каталог пользовательских команд как референс для capture-профиля; task/idea/project схемы как минимальный референс | Многосторонние правки vault, hooks, scheduled agents — опасно копировать без транзакционного контроля. Привязка к Obsidian |
| **AgriciDaniel/claude-obsidian** | Orchestration ingest/query/lint/save/retrieve; типы страниц, provenance, transaction contracts: reviewed bundle, hash preconditions, inspect/apply/recovery, immutable captures, source/claim ledgers, egress границы | Референс безопасности для широких agent writes (bundle + hash + recovery) | Архитектура крупнее/специфичнее компактного `todoc`. Прямое копирование — избыточно |
| **bholmesdev/llm-knowledge-base-skills** | Enrich-note, enrich loop, refresh-wiki: теги, provenance, backlinks, периодическое обслуживание; облачная автоматизация | Лёгкие maintenance patterns (enrichment, tag registry, source attribution) | Не заменяют типизированную модель или границы записи. Облачный schedule — отдельный слой |
| **ConardLi/rag-skill** (archived) | Многоформатный бюджетный поиск по иерархическим индексам (`data_structure.md`), отдельный подход к PDF/Excel, page/row references | Progressive retrieval по иерархии; page/row references как референс для bounded read | README помечает архивным. Не источник для долговременной object-модели |
| **Open Knowledge CLI** (частично скачан) | Markdown-валидация, поиск, setup/check/eval (см. §4.3) | Дисциплина документации: shipped vs planned; `validate`/`check`/`eval` как референс | Не полный аудит всего продукта по снимку. См. полный профиль в §4 |

---

## 3. Дополнительные конкуренты (найдены поиском)

| Конкурент | Почему включён | Категория |
|---|---|---|
| **Basic Memory** (basicmachines-co) | Ближайший «Markdown как память агента» с MCP + CLI + SQLite/Postgres индексом + Obsidian-совместимостью. Прямой конкурент для memory-профиля и референс для MCP/CLI | B/C/D |
| **Tana** | Supertags: пользовательские типы с полями/запросами в outliner. Ближайший концептуальный конкурент для `entity_type` | F |
| **Capacities** | Object types (Person/Project/Book/Task + custom properties) + graph + AI. Более доступный аналог Tana | F |
| **Logseq** | Локальный block-outliner, Markdown/org, backlinks/graph, daily notes. Референс локального хранения и графа | A |
| **Foam** | VS Code PKM: Markdown + wikilinks + graph. Референс «папка как vault без приложения» | A |
| **Quartz** | Static site generator для Obsidian vault (digital garden). Референс публикации | A/G |
| **SiYuan** | Block-level PKM, local DB, HTTP API, Markdown import. Референс block-ссылок и API | A |
| **Trilium / TriliumNext** | Иерархические заметки в SQLite + ETAPI. Референс дерева/атрибутов | A |
| **SilverBullet** | Self-hosted Markdown wiki в браузере + Lua-скриптинг/запросы. Референс «Markdown, но программируемый» | A |
| **Mem0 (+ OpenMemory MCP)** | Extract-and-store memory API (vector + optional graph), крупнейшее сообщество agent memory | D |
| **Zep / Graphiti** | Temporal knowledge graph: validity intervals, fact invalidation, contradiction resolution | D |
| **Letta (ex-MemGPT)** | Self-managing agent OS: memory blocks, sleep-time compute, archival search | D |
| **Open Notebook** | Self-hosted NotebookLM-альтернатива: notebooks/sources/chat/podcasts, 18+ провайдеров, REST API, SurrealDB (FTS+vector) | E |
| **RAGFlow / Dify / FastGPT** | Enterprise RAG-движки: deep parsing, hybrid+rerank, visual workflows, API | E |
| **NotebookLM / Gemini Notebook** | Cloud-only research notebook (Google). Референс UX «источники → чат → подкаст», но не локальный конкурент | E |
| **Notion** | Cloud databases + API. Референс typed databases для широкой аудитории | F |
| **Dataview / Tasks (Obsidian plugins)** | DQL-запросы по front matter + task management в Obsidian. Референс query/aggregate поверх Markdown | A/F |
| **Cognee / Supermemory / mcp-memory-service** | Document graphs / hosted memory / local SQLite+ONNX memory. Референсы graph/memory API | D |
| **OKF-экосистема** (okfcli/okf, okfctl, okf-gem, abatyuk/okf) | Vendor-neutral Markdown+YAML bundles: validate/lint/index/search/graph/server/render. Референс interchange и CI | G |
| **SurfSense** | Air-gapped NotebookLM-альтернатива с агентом-редактором документов | E |

---

## 4. Профили конкурентов

### 4.1. Категория A: Markdown PKM + Obsidian

**Obsidian (+ официальный CLI 1.12+, Dataview, Tasks).** Аудитория: человек, ведущий vault вручную. Хранение: обычная папка Markdown + вложения; vault может быть где угодно; не вкладывать vault в vault. Форматы: `.md` — заметки; изображения/PDF — вложения; CSV импорт превращается в Markdown + `.base` (отдельная конвертация). CLI: `obsidian <command> [param=value]` (см. §5.1); требует установленный и запущенный Obsidian 1.12+. Поиск: встроенный + CLI (`search`, `search:context`); backlinks/links/unresolved/orphans/deadends. Валидация: нет source-native schema validation CSV/JSON; unresolved links — диагностика. Типы: front matter properties + шаблоны + плагины (Dataview DQL, Tasks); нет JSON Schema record-типов с units/formula. Запись: человек в приложении; CLI — CRUD/append/move с автообновлением wikilinks. UI: зрелый (граф, доски, плагины, sync, мобильный). Портабельность: высокая для `.md` (см. §8); `.obsidian/` и плагины — необязательны. Лицензия: proprietary (CLI — GA с 1.12.4). Зрелость: высокая.

**Logseq.** Аудитория: privacy-focused outliner. Хранение: локальные Markdown/org файлы; блоки — атомарная единица; properties на блоках/страницах; backlinks/graph; daily notes. CLI: официального нет (редактирование — в приложении; автоматизация — через плагины/файлы). Поиск: встроенный по блокам. Типы: properties + queries (базовые supertag-поля). Портабельность: высокая (текстовые файлы). Лицензия: AGPL-3.0.

**Foam.** Аудитория: разработчики в VS Code. Хранение: plain Markdown + wikilinks; graph view в расширении. CLI: нет (VS Code extension). Поиск: VS Code + graph. Портабельность: максимальная (только файлы). Лицензия: MIT.

**Quartz.** Аудитория: публикующие digital garden. Хранение: читает Markdown vault, генерирует статический сайт. CLI: `npx quartz build` (см. §5). Поиск: статический сайт + graph. Портабельность: высокая (исходники — Markdown). Лицензия: open source.

**SiYuan.** Аудитория: block-level PKM с локальной БД. Хранение: собственный формат (`.sy` JSON) + Markdown import; block references, two-way links, database views, FSRS flashcards. Интерфейс: desktop/mobile/Docker + HTTP API. Портабельность: средняя (свой формат; импорт Markdown — миграция, не второе окно на vault). Лицензия: AGPL-3.0.

**Trilium / TriliumNext.** Аудитория: большая личная иерархия. Хранение: SQLite DB + атрибуты/отношения; ETAPI для доступа. Портабельность: низкая-средняя (DB — истина; экспорт Markdown — выгрузка). Лицензия: AGPL-3.0.

**SilverBullet.** Аудитория: self-hosted Markdown wiki в браузере. Хранение: Markdown файлы на сервере; queries + Lua-скриптинг. Портабельность: высокая (файлы). Лицензия: MIT.

**Dataview / Tasks (плагины Obsidian).** Dataview: DQL-запросы по front matter (таблицы, списки, агрегации) — ближайший референс для `records query/aggregate` поверх Markdown. Tasks: task management (status/due/priority/recurrence) в Markdown. Оба — плагины, не CLI-ядро; требуют Obsidian runtime.

### 4.2. Категория B: Local search / RAG CLI

**QMD** (tobi/qmd). Аудитория: разработчики/агенты, ищущие по локальным Markdown-коллекциям. Хранение: коллекции + индекс (BM25/FTS5 + vector + rerank); процессоры преобразуют JSON/логи в Markdown **только внутри индекса** (доверенный код, не sandbox). CLI: `collection add`, `context add`, `embed`, `search` (BM25), `vsearch` (vector), `query` (hybrid + LLM rerank), `get`, `multi-get`, `status`, `mcp` (см. §5.2). MCP tools: `qmd_search`, `qmd_vsearch`, `qmd_query`, `qmd_get`, `qmd_multi_get`, `qmd_status`. Поиск: BM25 + vector + hybrid + reranking, metadata-фильтры, per-collection processors (v2.9.0). Валидация: нет source-native schema validation. Типы: коллекции + context metadata, не JSON Schema record-типы. Портабельность: средняя-высокая (исходники — Markdown; индекс — производный). Закрывает тезис «быстро искать по Markdown и выдавать агенту подходящее» — `todoc` не должен конкурировать ещё одним общим поиском.

**mdkb** (ContractorKeith/mdkb, v0.1.0, 2026-11-01). Аудитория: агенты + Obsidian как редактор. Хранение: обычный Markdown в своей папке; SQLite FTS5 кэш (`$XDG_CACHE_HOME/mdkb/<root-hash>.db`), disposable. CLI: `init`, `new`, `search`, `backlinks`, `ls`, `cat`, `tags`, `info`, `reindex`, `daily`, `capture`, `mv`, `mcp` (см. §5.3). MCP: stdio, read-only по умолчанию; `--allow-write` включает 2 write tools. Поиск: FTS5 BM25 + опциональные локальные embeddings (Ollama/nomic-embed-text) + hybrid RRF; self-reported hit@3 0.90/MRR 0.91 vs 0.70/0.70 keyword на fixture. Запись: git-committed agent writes, `--dry-run`, `--json` на чтениях. Портабельность: высокая (один Go binary, файлы + disposable кэш). Ближайший референс для CLI/MCP-контрактов и `--json`.

**Open Knowledge CLI** (`okn`, openknowledge-sh). Аудитория: люди и агенты, управляющие Markdown-знаниями в репозитории. Хранение: managed copy или in-place adoption Markdown-бандла (OKF v0.2); setup plan-before-write с diff. CLI: `setup`, `check`, `validate`, `search`, `view`, `review`, `eval`, `audit`, `claims`, `evidence`, `query`, `export`, `mcp` и др. (см. §5.4). Поиск: локальный детерминированный, budget-limited context; ответ — файл, строки, hash/locator. Валидация: `validate` — JSON-отчёт с файлом/строкой/rule/message; `check` — сводный статус (structure/links/freshness/retrieval/publication); `eval` — retrieval-eval (MRR/Recall@k/nDCG@k). **Самое близкое совпадение для Markdown-only части идеи.** Открытая документация сосредоточена на Markdown/OKF, а не на типизированной проверке исходных CSV/JSON с location-aware fixes.

**okfcli/okf** (Go) + **okfctl** + **okf-gem** + **abatyuk/okf**. Аудитория: AI-driven docs/catalog pipelines. Хранение: OKF bundles (Markdown + YAML front matter, relative links, provenance/trust/freshness/lifecycle). CLI (okfcli): `init`, `validate` (`--format json|sarif`), `lint`, `index`, `list`, `show`, `search` (`--tag/--type/--text`), `backlinks`, `graph`, `schema`, `version` (см. §5.5). okfctl добавляет `bundle init`, `node new/list`, `index build/check`, `log append`, `analyze`, `serve`, `graph export`. Поиск: lexical + graph-neighborhood (stdlib-only, без модели). Валидация: conformance (parseable frontmatter, non-empty type, reserved-filename structure) vs lint (opinions: broken links, missing fields, orphans). Портабельность: высокая (vendor-neutral формат). Референс для OKF-совместимости и CI (`--fail-on`, SARIF).

**Basic Memory** (basicmachines-co/basic-memory, Python 3.12+, AGPL-3.0). Аудитория: агенты, которым нужна межсессионная память в Markdown. Хранение: plain Markdown — canonical; SQLite/Postgres — rebuildable projection (entity/observation/relation); file watcher reconciles out-of-band edits; stable id survives move. CLI: `basic-memory sync`, `sync --watch`, `mcp` (см. §5.6). MCP tools: `write_note`, `read_note`, `read_content`, `view_note`, `edit_note`, `move_note`, `delete_note`, `search_notes`, `build_context`, `recent_activity`, `list_directory`, `list_memory_projects`, `create_memory_project`, `get_current_project`, `sync_status`, `canvas` + schema/project tools. Поиск: FTS5/tsvector + optional semantic chunks + graph context, score-fused; hybrid retrieval. Типы: frontmatter + observations (`- [category] content #tag (context)`) + relations; schema inference/validation. Запись: bidirectional sync (человек редактирует файл → агент видит; агент пишет → файл обновляется); Claude Code hooks (SessionStart brief, PreCompact checkpoint). Портабельность: высокая (файлы + rebuildable индекс; cloud sync — opt-in). **Сильнейший конкурент для memory-профиля и референс для MCP/CLI.**

**Khoj.** Аудитория: personal second brain, multi-device. Хранение: app-centric (документы индексируются в vector DB; Obsidian/Emacs sync). Интерфейс: web/desktop/mobile/Obsidian/Emacs/WhatsApp; CLI — в основном `khoj --content-file/--content-dir` + server flags (см. §5.7). Поиск: embeddings + reranking, natural-language chat/RAG, agents, scheduled research. Форматы: Markdown, PDF, plain text, Org, Notion, Word, images. Портабельность: средняя (исходники можно держать локально, но истина — в приложении/индексе; cloud опция). Не позиционируется как переносимый source-native CLI validator для CSV/JSON.

### 4.3. Категория C: LLM Wiki / compounding KB

**Karpathy LLM Wiki (gist + Astro-Han skill).** Аудитория: человек + coding agent, накапливающие знания. Хранение: `raw/` immutable + `wiki/` LLM-generated + `CLAUDE.md` schema + `index.md` + `log.md`. CLI: нет бинаря; операции — промпты агента: **ingest** (source → summary + entity/concept pages + index/log), **query** (поиск по wiki + ответ с цитатами; хорошие ответы — обратно в wiki), **lint** (противоречия, stale claims, orphans, gaps). Поиск: index + drill-down; при росте — расширенный retrieval опционально. Валидация: LLM lint (не детерминированный validator). Портабельность: высокая (Markdown + Git). Центральное свойство — накопительный synthesis, не детерминированные проверки.

**OpenKB** (VectifyAI/OpenKB). Аудитория: компиляция знаний в wiki. Хранение: `raw/` sources → `wiki/` summaries/concept/entity pages + cross-links; wiki — plain Markdown, заявлена совместимость с Obsidian и OKF. CLI: `init`, `add`, `list`, `status`, `watch`, `lint`, `remove`, `recompile`, `query`, `chat`, `visualize`, `skill new`, `deck new` (см. §5.8). Поиск: PageIndex (vectorless long-document retrieval) + LLM navigation; query/chat с цитатами. Валидация: `lint` (structural + knowledge health). Запись: recompile может перегенерировать страницы и перезаписать ручные изменения. Форматы intake: PDF, Word, Markdown, PowerPoint, HTML, Excel, CSV, text, URL. Портабельность: средняя-высокая (wiki — Markdown; raw/ + registry + PageIndex — производные/сопутствующие). Уже сочетает широкий input + накопление + Obsidian-compatible Markdown, поэтому широкий тезис «папка + форматы + Obsidian + поиск» сильно ослаблен. Документированный README не доказывает точных source-row/JSON-Pointer fixes — проверить hands-on.

**obsidian-second-brain** (eugeniughelbur и форки). Аудитория: AI-first second brain в Obsidian через Claude Code/Codex/Gemini/OpenCode. Хранение: Obsidian vault (Markdown). Интерфейс: 33–47 slash-команд (см. §2). Поиск: vault-first + hybrid semantic + key-less web research. Валидация: `/obsidian-health` (contradictions, gaps, stale claims, orphans, freshness, typed-edge lint). Запись: self-rewriting notes, scheduled agents. Портабельность: средняя (vault — Markdown, но workflow сильно привязан к Obsidian + конкретным CLI-агентам). Наиболее наглядный пример, что для реального workflow нужны отдельные команды и связи (task с status/due/priority/project/person; idea lifecycle; graduate idea→project), а не просто маркировка файлов.

**claude-obsidian** (AgriciDaniel). Аудитория: безопасные agent writes в Obsidian. Хранение: vault + source/claim ledgers. Операции: ingest/query/lint/save/retrieve; reviewed transaction bundle, hash preconditions, inspect/apply/recovery, immutable captures, egress границы. Портабельность: средняя. Референс безопасности, не компактности.

**vanillaflava/llm-wiki-skills, bholmesdev skills, ConardLi rag-skill.** См. §2. Все — Skills (промпт-workflows), не CLI-ядра. ConardLi — hierarchical progressive retrieval; bholmesdev — enrichment/refresh; vanillaflava — config/ingest/query/lint/integrate/crystallize.

### 4.4. Категория D: Agent memory (вектор/граф)

**Mem0.** Аудитория: разработчики, добавляющие память в существующего агента. Хранение: LLM-extracted facts + embeddings (vector DB); optional graph (Neo4j add-on). Интерфейс: Python SDK (`add`/`search`/`update`/`delete`) + OpenMemory MCP (local-first server). Поиск: semantic similarity. Портабельность: низкая (векторы — истина; human-readable нет). LLM call on write по умолчанию (`infer=false` отключает). Сильнейшее сообщество (~60–69K stars).

**Zep / Graphiti.** Аудитория: агенты с меняющимися фактами (pricing, entitlements, staffing). Хранение: temporal knowledge graph (nodes/edges + validity intervals); Graphiti — open framework (Neo4j/FalkorDB/Neptune + LLM); Zep Cloud — managed. Интерфейс: REST API + Python/TS SDK + official MCP server. Поиск: graph traversal + temporal queries. Портабельность: низкая (graph DB — истина).

**Letta (ex-MemGPT).** Аудитория: greenfield stateful agents. Хранение: memory blocks (in-context core + archival vector search); agent server + DB. Интерфейс: agent server + CLI/API; MCP — community servers. Поиск: tier-based (core всегда в контексте, archival paged). Портабельность: низкая (state blocks — истина). Adopt wholesale или не использовать.

**Cognee / Supermemory / mcp-memory-service.** Cognee — document graphs; Supermemory — hosted memory API; mcp-memory-service — local SQLite + ONNX embeddings, MCP, dashboard. Все — vector/graph-first, не file-first.

### 4.5. Категория E: App-centric RAG / Notebook

**AnythingLLM** (Mintplex Labs, MIT). Аудитория: private document chat, workspaces. Хранение: app-owned parsed documents + vector DB (LanceDB/Chroma/Pinecone/Qdrant/Weaviate/Milvus) + cache. Интерфейс: Desktop app (Win/Mac/Linux) + Docker multi-user + REST API (см. §5.9). Поиск: RAG (chunking/embedding/indexing автоматически), agents (web search/scraping/SQL/meeting assistant), Live Document Sync beta (наблюдает отдельные файлы, не целые папки). Портабельность: низкая (источники/производные принадлежат приложению). Не повторять app-centric RAG без отдельной потребности.

**Open Notebook** (lfnovo/open-notebook, MIT). Аудитория: self-hosted NotebookLM. Хранение: SurrealDB (FTS + vector) + sources/notes/chats. Интерфейс: Docker web app + REST API (см. §5.10). Поиск: full-text + vector; grounded chat; podcasts (1–4 speakers); 18+ провайдеров (Ollama/LM Studio для offline). Портабельность: низкая-средняя (DB — истина; API — доступ).

**RAGFlow / Dify / FastGPT.** Аудитория: enterprise KB Q&A / LLM apps. Хранение: datasets + vector stores + workflows. Интерфейс: Docker web + API (см. §5.11). Поиск: hybrid + rerank, agentic retrieval, deep parsing (RAGFlow — таблицы), visual workflows (Dify/FastGPT). Портабельность: низкая (серверная БД — истина).

**NotebookLM / Gemini Notebook** (Google, cloud-only). Аудитория: research notebooks. Хранение: Google cloud. Интерфейс: web only; официального CLI/API нет (community `notebooklm-cli`/`nlm` — неофициальный, через HTTP/RPC + cookie extraction). Поиск: grounded chat + Audio Overviews. Портабельность: нулевая (cloud lock-in). Референс UX, не конкурент локального ядра.

### 4.6. Категория F: Typed / object-based PKM

**Tana.** Аудитория: power users, CRM/project tracking. Модель: **supertags** — tag с собственной базой свойств; привязка `#Person` превращает note в row people database; поля (Last Contact Date, Industry), inheritance, live queries, AI commands на supertags. Хранение: cloud (cloud-synced). Интерфейс: web/mobile app; API доступен; export Markdown/JSON. CLI: нет. Портабельность: низкая (cloud DB — истина; export — выгрузка). Ближайший концептуальный конкурент для `entity_type` + query.

**Capacities.** Аудитория: visual thinkers. Модель: **object types** (Note/Person/Book/Task + custom properties); bidirectional links; graph; Readwise integration; AI (Q&A/summarisation). Хранение: cloud. Интерфейс: web/mobile; API/MCP (ChatGPT/Claude/Cursor для search/create/update). CLI: нет. Портабельность: низкая. Более доступный аналог Tana (pre-defined types, без supertag inheritance).

**Notion.** Аудитория: широкая (docs/tasks/databases). Модель: databases с properties/relations/formulas/views. Хранение: cloud. Интерфейс: web/mobile/desktop + API. CLI: нет (API only). Портабельность: низкая (cloud DB — истина; export — выгрузка). Референс typed databases для массовой аудитории.

**Anytype / AFFiNE / AppFlowy.** Local-first / block-based object systems. Anytype — local-first encrypted objects с custom types; AFFiNE/AppFlowy — Notion-like blocks + self-host. Все — app-centric, не file-native CLI. Портабельность: средняя-низкая.

### 4.7. Категория G: Wiki / docs platforms

**OKF (Open Knowledge Format v0.2)** — см. okfcli/okf в §4.2. Vendor-neutral interchange: Markdown + YAML front matter, relative links, provenance/trust/freshness/lifecycle. CLI-экосистема: okfcli/okf, okfctl, okf-gem (Ruby + server + MCP), abatyuk/okf (36 команд, NDJSON). **Wiki.js / Outline / Docmost** — self-hosted team wiki (DB-backed). **Docusaurus/MkDocs** — docs-as-code static sites. Все — референсы interchange/CI, не file-native typed CLI.

---

## 5. Полный список CLI-команд: вход / выход

### 5.1. Obsidian CLI (`obsidian <command> [param=value] [flag]`)

Требует Obsidian 1.12+ и запущенное приложение. Параметры — `key=value`; флаги — bare words (исключение `--copy`). Multi-vault: `vault="My Vault"` первым параметром. Форматы вывода: `format=json|tsv|csv|text|md|paths` (на многих командах).

| Команда | Вход | Выход |
|---|---|---|
| `files` / `folders` | `folder=`, `ext=` | Список файлов/папок |
| `file` / `folder` | `file=` / `folder=` | Info: path, size, created, modified |
| `read` | `file=` | Содержимое файла |
| `create` | `name=`/`file=`, `content=`, `template=` | Создаёт/перезаписывает файл |
| `append` / `prepend` | `file=`, `content=` | Добавляет в конец/начало |
| `move` / `rename` | `file=`, `to=` | Move/rename с автообновлением wikilinks |
| `delete` | `file=` | В trash или permanent |
| `search` | `query=`, `limit=`, `format=` | Пути файлов с совпадениями |
| `search:context` | `query=`, `limit=` | `path:line: text` (grep-style) |
| `search:open` | — | Открывает search view в приложении |
| `backlinks` / `links` | `file=` | Входящие/исходящие ссылки |
| `unresolved` / `orphans` / `deadends` | — | Битые ссылки / без входящих / без исходящих |
| `daily` / `daily:path` / `daily:read` / `daily:append` / `daily:prepend` | `content=` | Daily note операции |
| `tasks` / `task` | `daily`, `todo/done`, line number | Задачи daily note; toggle/done |
| `tags` / `tag` | `counts`, `tag=` | Теги с частотой / файлы по тегу |
| `templates` / `template:read` / `template:insert` | `template=` | Шаблоны |
| `vault` / `vaults` / `vault:open` | — | Info / список / переключение vault |
| `random` / `random:read` | — | Случайная заметка |
| `wordcount` | `file=` | Число слов |
| `diff` | `file=`, `from=`, `to=` | Сравнение версий файла |
| `open` | `file=` | Открыть в приложении |
| `eval` | `code=` (JS в контексте приложения) | Результат JS (`app.vault.getFiles().length` и т.п.) |
| `devtools` / `dev:console` / `dev:errors` / `dev:css` / `dev:dom` / `dev:screenshot` | `selector=`, `path=` | DevTools / консоль / ошибки / CSS / DOM / скриншот |
| `plugin:reload` | `id=` | Перезагрузка плагина (dev) |

### 5.2. QMD (`qmd …`)

| Команда | Вход | Выход |
|---|---|---|
| `qmd collection add <path> --name <n> --mask "**/*.md"` | Путь + имя + маска | Коллекция добавлена |
| `qmd context add <path> "description"` | Путь + контекст | Hierarchical context для retrieval |
| `qmd embed` | — | Vector embeddings сгенерированы/обновлены |
| `qmd search "query" [-n NUM] [-c NAME] [--min-score NUM] [--full] [--json]` | Запрос + фильтры | BM25 хиты: snippets + scores (fast, ~0.2s) |
| `qmd vsearch "query" …` | Запрос | Vector хиты (semantic, ~3s) |
| `qmd query "query" …` | Запрос (поддерживает `lex:`/`vec:`/`expand:` префиксы) | Hybrid + LLM rerank хиты (best quality, ~2–3s warm) |
| `qmd get <docid\|path\|path:line>` | ID/путь/строка | Полный документ / line range |
| `qmd multi-get "glob" --json` | Glob | Несколько файлов |
| `qmd status` | — | Index health + collections |
| `qmd mcp` / `qmd mcp --http --daemon` | — | MCP server (stdio/HTTP) |

### 5.3. mdkb (`mdkb --root <path> …`)

| Команда | Вход | Выход |
|---|---|---|
| `mdkb init <path>` | Путь KB | Инициализированная KB |
| `mdkb --root <path> new "Title" --body '…'` | Title + body | Новая заметка |
| `mdkb --root <path> search 'query' [--json]` | Запрос | FTS5 хиты: snippets + BM25 scores |
| `mdkb --root <path> backlinks <note>` | Note ID | Backlinks |
| `mdkb ls --limit 5 --json` | Limit | Список заметок (cap 50, `truncated`) |
| `mdkb cat <note>` | Note ID | Содержимое |
| `mdkb tags` | — | Теги |
| `mdkb info --json` | — | Indexed details |
| `mdkb reindex [--full]` | — | Переиндексация (disposable cache) |
| `mdkb daily` / `mdkb capture` / `mdkb mv` | Дата/текст/пути | Daily note / capture / move с link rewrite |
| `mdkb --root <path> mcp [--allow-write]` | — | MCP server (read-only по умолчанию; `--allow-write` — 2 write tools) |

Все чтения поддерживают `--json`; CLI writes — `--dry-run`. Git commit per write.

### 5.4. Open Knowledge CLI (`okn …`)

| Команда | Вход | Выход |
|---|---|---|
| `okn setup [Wiki] [--from docs] [--mode copy\|adopt] [--agent codex\|claude\|opencode] [--prompt]` | Target path + источник | Managed bundle + setup plan (9 create, 3 add frontmatter, 0 delete и т.п.) + validation/search READY |
| `okn check Wiki` | Target | Сводный статус: Structure/Links/Freshness/Retrieval/Publication → Overall READY |
| `okn validate Wiki [--profile bundle\|okf]` | Target | Детальные format/link diagnostics (JSON-отчёт: файл/строка/rule/message) |
| `okn search Wiki "release workflow"` | Target + запрос | Budget-limited context: файл, line range, content hash, scores |
| `okn view Wiki` | Target | Локальный браузер (`http://127.0.0.1:4185/wiki/`) + WebMCP tools (`openknowledge_search`, `openknowledge_apply_edit`, `openknowledge_save_document`) |
| `okn review Wiki` | Target | Agent review после setup |
| `okn eval run` | Eval dataset | Retrieval/answer/citation/groundedness/trust/freshness/lifecycle/source expectations; MRR/Recall@k/nDCG@k |
| `okn audit` / `okn claims` / `okn evidence` | Target | Trust/governance: source/evidence/lifecycle/conflict controls |
| `okn query` / `okn export` / `okn mcp` / `okn setup github Wiki` | Target/запрос | Query / export / MCP runtime / Knowledge CI (GitHub Action, source baseline, starter eval, gates) |

### 5.5. okfcli/okf (Go) + okfctl

| Команда | Вход | Выход |
|---|---|---|
| `okf init ./my-bundle` | Bundle path | Новый OKF bundle |
| `okf validate ./bundle [--format json\|sarif] [--exit-zero]` | Bundle | Conformance (exit 1 on errors) |
| `okf lint ./bundle [--format json\|sarif]` | Bundle | Recommended fields/style (warnings only) |
| `okf index ./bundle` | Bundle | Сгенерированные `index.md` (progressive disclosure) |
| `okf list ./bundle` | Bundle | Concepts: ID, type, title, status, trust tier |
| `okf show ./bundle <concept-id>` | Bundle + ID | Полное содержимое concept (JSON) |
| `okf search ./bundle [--tag X] [--type Table] [--text "deprecated"]` | Bundle + фильтры | Concepts по tag/type/text |
| `okf backlinks ./bundle <concept-id>` | Bundle + ID | Кто ссылается на concept |
| `okf graph ./bundle` | Bundle | Cross-link graph: nodes, edges, stats; orphans |
| `okf schema [command]` | — | Machine-readable CLI metadata (JSON) |
| `okf version` | — | Версия |
| `okfctl bundle init mykb` / `okfctl node new concepts/tannin.md --type Reference --title "Tannin" --bundle mykb` | Bundle/node | Scaffold bundle / новый node |
| `okfctl index build mykb` / `okfctl index check mykb` | Bundle | Generate / verify reserved `index.md` |
| `okfctl log append mykb --message "…"` | Bundle + message | Change log entry |
| `okfctl validate mykb` / `okfctl lint mykb [--strict]` / `okfctl analyze mykb` | Bundle | Spec floor / curation findings / weakness report |
| `okfctl search "tannin" mykb` / `okfctl graph export mykb [--format json\|dot]` / `okfctl serve mykb` | Bundle | Lexical search / graph export / web visualization |

### 5.6. Basic Memory (`basic-memory …` + MCP)

| Команда / Tool | Вход | Выход |
|---|---|---|
| `basic-memory sync` | — | One-time sync локальных обновлений |
| `basic-memory sync --watch` | — | Realtime sync process |
| `basic-memory mcp [--project NAME]` | Project | MCP server (stdio, `uvx basic-memory mcp`) |
| `write_note(title, content, folder, tags)` | Title/content/folder/tags | Созданная/обновлённая заметка (Markdown + индекс) |
| `read_note(identifier, page, page_size)` | Title/permalink | Заметка постранично |
| `read_content(path)` | Path | Raw file content (text/images/binaries) |
| `view_note(identifier)` | Identifier | Formatted artifact |
| `edit_note(identifier, operation, content)` | ID + операция | Инкрементальная правка |
| `move_note(identifier, destination_path)` | ID + путь | Move с DB consistency |
| `delete_note(identifier)` | ID | Удаление |
| `search_notes` / `build_context` / `recent_activity` / `list_directory` | Запрос/контекст | Хиты / bounded context / активность / листинг |
| `list_memory_projects` / `create_memory_project` / `get_current_project` / `sync_status` / `canvas` | Project | Проекты / статус / canvas |

### 5.7. Khoj (`khoj …` + web/plugins)

| Команда / Интерфейс | Вход | Выход |
|---|---|---|
| `khoj --content-file /path` / `khoj --content-dir /path` | Файлы/папки | Индексация (embeddings) |
| `khoj --index-type standard\|semantic` / `--enable-ocr` / `--workers` / `--device` | Опции индексации | Standard/semantic/OCR индекс |
| `khoj run` / Docker `ghcr.io/khoj-ai/khoj` | — | Web server (chat/search/agents) |
| Web UI: Settings → Files | Drag-and-drop PDF/MD/Notion | Индексация |
| Obsidian plugin / Emacs client / WhatsApp | Vault/чат | Индексация vault / chat |
| Chat: `/notes`, `/code`, natural language | Запрос + slash-команды | RAG ответ с цитатами; agents; scheduled briefings |

### 5.8. OpenKB (`openkb …`)

| Команда | Вход | Выход |
|---|---|---|
| `openkb init` | — | Инициализированная KB (interactive) |
| `openkb add <file\|dir\|URL>` | Файл/папка/URL | Скомпилированные wiki pages (summaries, concepts, cross-links) |
| `openkb list` / `openkb status` | — | Indexed documents/concepts / stats |
| `openkb watch` | — | Watch `raw/` + auto-compile |
| `openkb lint` | — | Structural + knowledge health checks |
| `openkb remove <doc> [--dry-run] [--keep-raw] [--keep-empty]` | Doc | Удаление + cleanup wiki pages/images/registry/PageIndex |
| `openkb recompile [<doc>] [--all] [--dry-run] [--refresh-schema]` | Doc | Перегенерация summaries/concepts (перезаписывает ручные правки) |
| `openkb query "question" [--save]` | Вопрос | Grounded ответ с цитатами (опционально в `wiki/explorations/`) |
| `openkb chat [--resume] [--list] [--delete]` | Interactive | Multi-turn сессия (`/help`, `/status`, `/list`, `/add`, `/skill new`, `/deck new`, `/critique`, `/save`, `/clear`, `/lint`, `/exit`) |
| `openkb visualize` | — | Interactive knowledge graph (`output/visualize/graph.html`: 3D/mind-map/radial) |
| `openkb skill new <name> "intent"` | Name + intent | Redistributable agent skill из wiki |
| `openkb deck new <name> "intent" [--skill] [--critique]` | Name + intent | Single-file HTML slide deck |

### 5.9. AnythingLLM (Desktop/Docker/REST API — нет CLI subcommands)

| Операция | Вход | Выход |
|---|---|---|
| Create workspace | Name + settings | Изолированный workspace |
| Upload/embed document | Drag-and-drop PDF/DOCX/TXT/MD/URL/GitHub/Confluence | Chunked + embedded + indexed (LanceDB и др.) |
| Chat (RAG) | Вопрос | Ответ с citations; accuracy-optimized reranking опционально |
| Agent skills | Web search/scraping/SQL/meeting assistant/custom SDK | Агентские действия |
| REST API | `POST /api/v1/workspaces`, `/documents`, `/chat` и др. | Программный доступ ко всем UI-действиям |
| Live Document Sync (beta) | URL/data connector | Re-embedding при изменениях (hourly Docker / 10 min Desktop) |

### 5.10. Open Notebook (Docker web + REST API — нет CLI subcommands)

| Операция | Вход | Выход |
|---|---|---|
| Create notebook | Name | Notebook |
| Add source | PDF/video/audio/web page/Office doc | Индексированный source (FTS + vector в SurrealDB) |
| Chat with sources | Вопрос | Grounded ответ с references |
| Generate podcast | 1–4 speakers + profiles | Multi-speaker podcast |
| REST API (`localhost:5055`) | Notebooks/sources/queries | Программный доступ |
| Configure provider | 18+ провайдеров / Ollama / LM Studio | Model routing per task |

### 5.11. RAGFlow / Dify / FastGPT (Docker web + API — нет CLI subcommands)

| Операция | Вход | Выход |
|---|---|---|
| Create dataset/knowledge base | Documents/URLs | Parsed + chunked + embedded dataset |
| Upload document | File (TXT/MD/HTML/PDF/DOCX/PPTX/CSV/XLSX) | Индексированные chunks (editable/deletable в FastGPT) |
| Chat / Workflow | Вопрос / visual flow | RAG ответ / workflow output |
| REST API | Dataset/document/chat endpoints + API key | Программный доступ |

### 5.12. Karpathy LLM Wiki / obsidian-second-brain / Skills (нет CLI-бинаря)

| Система | Вход (промпт/команда) | Выход |
|---|---|---|
| Karpathy gist (ingest) | «Ingest `raw/…` per `CLAUDE.md`» | Summary page + entity/concept pages + `index.md` + `log.md` (10–15 файлов на источник) |
| Karpathy gist (query) | Вопрос к wiki | Ответ с цитатами; хорошие ответы — обратно в wiki |
| Karpathy gist (lint) | «Lint my wiki» | Противоречия, stale claims, orphans, gaps |
| Astro-Han skill | «Ingest this article: URL» / «What do I know about X?» / «Lint my wiki» | `raw/` + `wiki/` + citations + health report |
| obsidian-second-brain | `/obsidian-save`, `/obsidian-task`, `/obsidian-capture`, `/obsidian-find`, `/obsidian-project`, `/obsidian-graduate`, `/obsidian-health`, `/research [topic]`, `/obsidian-daily`, `/obsidian-board`, `/obsidian-decide`, `/obsidian-recap`, `/obsidian-review`, `/obsidian-synthesize`, `/obsidian-reconcile`, `/obsidian-export`, `/obsidian-visualize`, `/obsidian-learn`, `/obsidian-init`, `/obsidian-architect`, `/obsidian-challenge`, `/obsidian-emerge`, `/obsidian-connect`, `/idea-discovery`, `/x-read`, `/youtube`, `/podcast`, `/notebooklm`, `/research-deep` и др. (33–47 команд) | Vault writes (tasks/projects/ideas/decisions/synthesis) + research dossiers + health/eval reports |
| vanillaflava skills | config / ingest / query / lint / integrate / crystallize | Schema/templates + wiki updates + session crystallize |
| bholmesdev skills | enrich-note / refresh-wiki | Enriched note (tags/source/backlinks) / refreshed wiki |
| ConardLi rag-skill | kb-retriever skill | Hierarchical retrieval (PDF/Excel отдельно) |

### 5.13. Tana / Capacities / Notion / Logseq / Foam / SiYuan / Trilium / SilverBullet (нет CLI)

| Система | Интерфейс | Вход | Выход |
|---|---|---|---|
| Tana | Web/mobile app + API + export | Supertag + поля + query | Typed nodes + live query results |
| Capacities | Web/mobile + API/MCP | Object type + properties + links | Objects + graph + AI answers |
| Notion | Web/mobile/desktop + API | Database + properties + relations | Pages + database views |
| Logseq | Desktop/mobile app | Blocks + properties + links | Graph + daily notes |
| Foam | VS Code extension | Markdown + wikilinks | Graph + navigation |
| Quartz | `npx quartz build` | Vault path | Static site (HTML + graph) |
| SiYuan | Desktop/mobile/Docker + HTTP API | Blocks + refs + DB views | Block graph + API responses |
| Trilium | Desktop/web + ETAPI | Notes + attributes/relations | Tree + ETAPI responses |
| SilverBullet | Server + PWA | Markdown + Lua queries | Rendered pages |

### 5.14. Mem0 / Zep / Letta (SDK/API/MCP — нет CLI subcommands)

| Система | Вход | Выход |
|---|---|---|
| Mem0 SDK | `memory.add(text, user_id)`, `memory.search(query)`, `memory.update/delete` | Extracted facts + embeddings; semantic hits |
| OpenMemory MCP | MCP tools (add/search/update/delete) | Shared local memory для Claude Desktop/Cursor/Windsurf |
| Zep/Graphiti | REST/SDK: episodes, facts, temporal queries | Temporal graph context string; validity intervals |
| Letta | Agent server: memory blocks, archival search, sleep-time compute | Stateful agent + self-edited memory |

### 5.15. `todoc` (план, §8 конституции)

См. §8.1 конституции: `init`, `check`, `scan`, `check-config`, `validate`, `index status/rebuild`, `explain-path`, `docs new/search/read/edit`, `records create/list/query/aggregate/read`, `relations graph`, `types list/show/guide`, `fix --preview/--apply`. Вход: явный `--root` (повторяемый), `--output json|table|markdown`, `--budget/--limit`, `--preview/--apply/--if-hash`. Выход: версионированный JSON envelope `{schema_version, ok, data, diagnostics, next_actions}` + stable exit codes.

---

## 6. Мастер-список возможностей: нужен ли `todoc`?

**Вердикты:** **MUST** — обязательно в MVP; **SHOULD** — нужно в v1/скоро после MVP; **COULD** — полезно позже/опционально; **WON'T** — не делать (или делать отдельным профилем/интеграцией).

| ID | Возможность | Вердикт | Фаза | Обоснование |
|---|---|---|---|---|
| C01 | Plain files — source of truth (Markdown/CSV/JSON + вложения) | **MUST** | MVP | P1. Основа портабельности и Git |
| C02 | Portable folder: move без фикса absolute paths; cold-rebuild | **MUST** | MVP | P2. Отличие от app-centric систем |
| C03 | Multi-format read (MD/CSV/JSON) с locations | **MUST** | MVP | Source-native QA — ниша |
| C04 | Multi-format write: create-only новые записи; правки — review-first | **MUST** | MVP | P6. Без молчаливой перезаписи |
| C05 | User-defined doc types (schema/view/workflow) | **MUST** | MVP | FR-3. Классификация документов |
| C06 | User-defined entity/record types + JSON Schema + units/enums | **MUST** | MVP | FR-6/8. Главная гипотеза |
| C07 | Folder profiles / routing (path/basename/glob + inheritance + explain-path) | **MUST** | MVP | FR-3. `**/plan/`, `.research/` |
| C08 | Typed relations + validation (endpoint/cardinality/dangling) | **MUST** | MVP | FR-7. Явные связи, не «паутина» |
| C09 | Graph/backlinks derived index (пересоздаваемый) | **MUST** | MVP | FR-7. Без graph DB |
| C10 | Lexical search (BM25/FTS5) offline | **MUST** | MVP | FR-5. Default backend |
| C11 | Semantic/vector search (embeddings) | **COULD** | v2 opt-in | Только после benchmark/privacy gate; не в MVP |
| C12 | Hybrid fusion + reranking (LLM reranker) | **COULD** | v2 opt-in | Порты заложены; провайдер — opt-in |
| C13 | Metadata/field filters (type/date/tags/status/relations) | **MUST** | MVP | FR-5/8. Гибкий поиск по типам/полям |
| C14 | Bounded read (section/pointer/columns/rows/fields) | **MUST** | MVP | FR-5. Progressive disclosure |
| C15 | Exact locations + provenance/hash | **MUST** | MVP | FR-5. Проверяемость |
| C16 | Validation (schema/links/structure/business) | **MUST** | MVP | FR-5. Source-native QA |
| C17 | Diagnostics + suggested fixes + preview/diff | **MUST** | MVP | FR-5. Review-first |
| C18 | Safe writes (no-overwrite, hash, atomic, post-validation) | **MUST** | MVP | FR-5/6. P6 |
| C19 | Capture workflows (note/link/research/plan/product/person/workout) | **MUST** | MVP (generic) | FR-6. Type-directed, generic engine |
| C20 | Agent Skill (`SKILL.md` + references) | **MUST** | MVP | FR-11. Диалог, не валидатор |
| C21 | MCP server (tools + resources) | **SHOULD** | v1 | FR-10. Тонкий adapter после CLI |
| C22 | CLI с JSON envelope + exit codes + `next_actions` | **MUST** | MVP | §8. Контракт для агента |
| C23 | Obsidian compatibility (vault, wikilinks subset, attachments) | **MUST** | MVP (subset) | FR-4. Просмотрщик, не зависимость |
| C24 | OKF compatibility (validate/metadata profile) | **SHOULD** | v1 | FR-4. Interchange, не требование |
| C25 | LLM synthesis/compilation (`raw/ → wiki/`) | **WON'T (core)** | Отдельный профиль | §6.10. Не скрытая LLM-компиляция в MVP |
| C26 | Task/Plan/Idea lifecycle (status/due/owner/recurrence/promote) | **WON'T (core)** | Отдельный профиль | §6.10. Generic records ≠ task manager |
| C27 | Session memory / bootstrap / crystallize | **WON'T (core)** | Отдельный профиль | §6.10. Межсессионная память — отдельный scope |
| C28 | Claim/evidence ledger, freshness/conflict | **WON'T (core)** | Отдельный профиль | §6.10. Для research-памяти, не file QA |
| C29 | Chat/RAG Q&A с цитатами (natural language) | **WON'T (core)** | Интеграция | Агент сам отвечает из bounded read; не строить чат-UI |
| C30 | Web UI (tree/graph/filters/edit) | **SHOULD** | Этап 9 | FR-9. Отдельный adapter, не MVP |
| C31 | Static publishing (digital garden) | **COULD** | После веба | Аналог Quartz; экспорт из тех же файлов |
| C32 | Sync/backup (Git / cloud / LiveSync) | **SHOULD (Git)** / **COULD (cloud)** | MVP (Git-friendly) / v2 | FR-12. Git — бесплатно; cloud — с single-writer policy |
| C33 | Multi-user / collab / ACL | **WON'T** | — | Не аудитория первого слоя |
| C34 | Importers (PDF/DOCX/XLSX/URL/Notion) | **COULD** | v2 opt-in | FR-4.5. Preview-first; не обязательная конвертация |
| C35 | Watch mode / auto-ingest | **COULD** | v2 | Только по боли; не скрытый background job |
| C36 | Eval/benchmark (retrieval quality, MRR/Recall) | **MUST** | MVP | §13. Без benchmark — нет gate |
| C37 | Query/aggregate с units/formula/provenance | **MUST** | MVP | FR-8. Проверяемая «универсальность» |
| C38 | Templates / naming / path policies | **MUST** | MVP | FR-3/6. Безопасные placeholders |
| C39 | UI metadata (color/icon/views/graph style) | **MUST** | MVP (данные) | FR-3.6. Неисполняемые данные |
| C40 | Offline/local-first, no hidden LLM/network | **MUST** | MVP | P5/P12. Доверие и воспроизводимость |
| C41 | Plugin system (entry points) | **COULD** | v2 | Только по боли; allowlist; не в MVP |
| C42 | Mobile/desktop apps | **WON'T** | — | Obsidian/веб покрывают просмотр |
| C43 | Scheduled agents / automations | **WON'T (core)** | Отдельный слой | Не скрытые фоновые действия |
| C44 | Audio/podcast/multimodal | **WON'T** | — | Не задача `todoc` |
| C45 | Code execution in notebook | **WON'T** | — | Не задача `todoc` |
| C46 | Versioning/history (Git-friendly diffs) | **SHOULD** | MVP (совместимость) | FR-12. Текстовые файлы diff-ятся. **Уточнено 2026-11-25:** Git остаётся рекомендуемым механизмом, но журнал событий и откат собственных записей — в core, см. C61–C66 и `history-and-changes.md`. Это не VCS: без веток, слияний и remote |
| C47 | Tag/alias registry | **COULD** | v2 | FR-6.10. После MVP |
| C48 | Daily notes / calendar | **WON'T (core)** | Профиль | Obsidian/second-brain покрывают; не core |
| C49 | Kanban/boards/dashboards | **WON'T (core)** | Профиль/веб | Не core; веб может показать views |
| C50 | Export (JSON/MD/HTML/slides) | **SHOULD** | v1 | FR-12. JSON уже есть; HTML/slides — позже |
| C51 | External fetch для `link` capture (URL → выжимка) | **SHOULD** | v1 opt-in | FR-6.3. Allowlisted fetch, не скрытая сеть |
| C52 | Multi-root (`--root` × N, изоляция) | **MUST** | MVP | FR-1. Не смешивать configs/IDs |
| C53 | `explain-path` / `types guide` (объяснимость) | **MUST** | MVP | FR-3. P13 |
| C54 | Atomic generations + incomplete state | **MUST** | MVP | FR-5. Не публиковать несогласованные индексы |
| C55 | CI gates (`--strict`, SARIF) | **SHOULD** | v1 | Референс okf/Open Knowledge; для maintainer-персоны |
| C56 | Visualize (interactive graph HTML) | **COULD** | v1/веб | Референс OpenKB `visualize`; веб покрывает |
| C57 | Skill Factory (wiki → skill) | **WON'T** | — | OpenKB-фича; не задача `todoc` |
| C58 | Deck/slides generation | **WON'T** | — | OpenKB-фича; не задача `todoc` |
| C59 | Meeting assistant / transcription | **WON'T** | — | AnythingLLM-фича; не задача `todoc` |
| C60 | Web search / scraping как встроенная фича | **WON'T (core)** | Интеграция | Агент/пользователь приносят источники; `todoc` их валидирует |
| C61 | Журнал событий и откат собственных записей **без обязательного** VCS | **SHOULD** | После редизайна индекса | Заменяет накопление поколений индекса (P1-2). Не VCS: без веток/слияний/remote; git — опциональный бэкенд, не зависимость. `history-and-changes.md` Фазы 0–1 |
| C62 | Жизненный цикл изменения: proposal → apply → archive | **SHOULD (core)** | После Фазы 1 | Решение принято 2026-11-25. Закрывает G3 (bundle-транзакции). Референс — OpenSpec, не SpecKit |
| C63 | Дельты с проверяемой применимостью к живому состоянию | **SHOULD (core)** | После Фазы 1 | Сильнее OpenSpec: проверка якоря, `base_hash` и пост-валидация, а не только формата |
| C64 | Обнаружение устаревания по якорям (`derived_from`) | **SHOULD** | Первая отдача | Референс — Swimm (связь на уровне токена, не файла). Независимо от журнала |
| C65 | Би-темпоральные факты, `--as-of` | **COULD** | После Фазы 3 | Референс — Zep/Graphiti. Инвалидация вместо удаления; без LLM-поиска противоречий (P5) |
| C66 | Лента изменений документа и раздела | **SHOULD** | После Фазы 1 | git даёт историю файла, но не раздела. Парсер секций уже есть |
| C67 | Два бэкенда истории: `embedded` и `git`, с правилом `gap-filling` | **SHOULD** | После Фазы 1 | Решение 2026-11-25. git закрывает долговечность и снимает третью категорию хранения, но не выражает `change_id`/`ranges`/би-темпоральность — журнал нужен в обоих режимах. `history-and-changes.md` §18 |
| C68 | Дельты валидируются существующим `doc_type`-механизмом | **SHOULD** | Вместе с C63 | Префиксные селекторы `## MODIFIED:` работают уже сейчас (`_heading_matches`, `validator.py:179`); нового нужно только `any_of_sections`. §19 |

---

## 7. Сравнительные таблицы

### 7.1. Ядро CLI/поиска/валидации (B + C + A-CLI)

| Возможность | Obsidian CLI | QMD | Open Knowledge | okfcli/okf | OpenKB | mdkb | Basic Memory | todoc (план) |
|---|---|---|---|---|---|---|---|---|
| Plain files — истина | ● (`.md`) | ● (Markdown) | ● (Markdown/OKF) | ● (OKF bundles) | ◐ (wiki MD + raw/ + registry) | ● (Markdown) | ● (Markdown canonical) | ● (MD/CSV/JSON) |
| Portable folder + cold-rebuild | ● | ◐ | ● | ● | ◐ | ● | ● | ● |
| Multi-format read (MD/CSV/JSON) | ◐ (MD + вложения; CSV→MD import) | ◐ (MD + processors→MD в индексе) | ○ (MD-only) | ○ (MD-only) | ● (PDF/DOCX/MD/PPTX/HTML/XLSX/CSV/text/URL) | ○ (MD-only) | ◐ (MD; importers ChatGPT/Claude) | ● (MD/CSV/JSON source-native) |
| User-defined doc types | ◐ (properties/templates) | ◐ (collections/context) | ◐ (OKF types) | ● (OKF types) | ◐ (wiki page types) | ○ | ◐ (frontmatter/observations) | ● (declarative `doc_type`) |
| User-defined entity types + JSON Schema | ○ | ○ | ○ | ◐ (OKF type field) | ○ | ○ | ◐ (schema inference) | ● (JSON Schema + units) |
| Folder profiles / routing | ◐ (folders/templates) | ◐ (collections/masks) | ◐ (setup paths) | ◐ (bundle dirs) | ◐ (`raw/`/`wiki/`) | ◐ (`--root`) | ◐ (projects/folders) | ● (glob + inheritance + explain) |
| Typed relations + validation | ◐ (wikilinks/backlinks) | ○ | ◐ (links/claims) | ◐ (cross-links) | ◐ (cross-links) | ◐ (wikilinks/backlinks) | ● (relations в графе) | ● (declarative + cardinality) |
| Graph/backlinks derived | ● | ○ | ◐ | ● (`graph`/`backlinks`) | ● (`visualize`) | ● (`backlinks`) | ● (graph traversal) | ● (derived index) |
| Lexical search offline | ● | ● (BM25/FTS5) | ● (deterministic) | ● (lexical) | ◐ (PageIndex) | ● (FTS5) | ● (FTS5/tsvector) | ● (default) |
| Vector/hybrid/rerank | ○ | ● (vsearch/query) | ◐ (eval embedding-uplift) | ○ | ◐ (PageIndex, no vector DB) | ◐ (opt-in Ollama) | ● (semantic + fused) | ○ (MVP) → ◐ (opt-in) |
| Metadata/field filters | ◐ (search syntax/properties) | ◐ (metadata filters) | ◐ | ● (`--tag/--type/--text`) | ○ | ◐ (tags) | ◐ | ● (typed filters) |
| Bounded read | ◐ (`read`, `search:context`) | ● (`get`, `multi-get`) | ● (budget-limited) | ● (`show`) | ◐ (`query`/`chat`) | ● (`cat`, `ls` cap) | ● (`read_note` paging) | ● (section/pointer/rows) |
| Exact locations + hash | ◐ (path:line в `search:context`) | ◐ (docid/path) | ● (file/line/hash) | ◐ (concept ID) | ◐ (citations) | ◐ (snippets/scores) | ◐ | ● (row/pointer/line + hash) |
| Validation (schema/links) | ◐ (unresolved links) | ○ | ● (`validate`/`check`) | ● (`validate`/`lint`) | ◐ (`lint`) | ○ | ◐ (schema tools) | ● (schema + relations + business) |
| Diagnostics + fixes + preview | ○ | ○ | ◐ (plan-before-write diff) | ◐ (lint findings) | ○ | ○ | ○ | ● (preview/diff + hash) |
| Safe writes (no-overwrite/atomic) | ◐ (app-mediated) | ○ (read-only search) | ◐ (review) | ◐ (`add`/`edit`/`mv`/`rm`) | ○ (recompile overwrites) | ● (`--dry-run`, git commit) | ◐ (MCP writes + watcher) | ● (create-only + hash) |
| Capture workflows | ◐ (templates/daily) | ○ | ◐ (setup agent task) | ◐ (`add` scaffold) | ● (`add` compile) | ● (`new`/`capture`/`daily`) | ● (`write_note`) | ● (type-directed) |
| Agent Skill | ○ (CLI для агента) | ◐ (skill docs) | ◐ (skills install) | ◐ (companion skill) | ◐ (skill factory) | ○ | ● (`skills/` SKILL.md) | ● (parent `SKILL.md`) |
| MCP server | ○ | ● (`qmd mcp`) | ● (`okn mcp`) | ◐ (okf-gem MCP) | ○ | ● (read-only + `--allow-write`) | ● (core) | ◐ (SHOULD v1) |
| CLI + JSON envelope | ◐ (`format=json`) | ◐ (`--json`) | ◐ | ● (`--format json\|sarif`, NDJSON) | ○ | ● (`--json` goldens) | ◐ (CLI + API) | ● (envelope + exit codes) |
| Obsidian compatibility | ● (сам Obsidian) | ◐ (MD vault) | ◐ (MD) | ◐ (render obsidian) | ● (wiki MD + wikilinks) | ● (editor) | ● (vault) | ● (subset, no dependency) |
| OKF compatibility | ○ | ○ | ● (OKF v0.2) | ● (OKF) | ◐ (claimed) | ○ | ○ | ◐ (SHOULD v1) |
| LLM synthesis (`raw/→wiki/`) | ○ | ○ | ○ | ○ | ● (compile) | ○ | ○ | ○ (отдельный профиль) |
| Task/Plan/Idea lifecycle | ◐ (Tasks plugin) | ○ | ○ | ○ | ○ | ○ | ○ | ○ (отдельный профиль) |
| Chat/RAG Q&A | ○ | ○ | ○ | ○ | ● (`query`/`chat`) | ○ | ○ | ○ (агент отвечает) |
| Web UI | ● (app) | ○ | ◐ (`view` local) | ◐ (`serve`/`render`) | ◐ (Workbench + `visualize`) | ○ | ◐ (cloud/API) | ○ (Этап 9) |
| Offline, no hidden LLM | ● | ◐ (`search` offline; `query` — LLM) | ● | ● | ○ (LLM compile) | ● (semantic opt-in) | ● (local default) | ● (ядро) |

### 7.2. Приложения и memory (A/F/D/E)

| Возможность | Logseq/Foam | Tana/Capacities | Mem0/Zep/Letta | AnythingLLM/Khoj/Open Notebook | RAGFlow/Dify/FastGPT | todoc (план) |
|---|---|---|---|---|---|---|
| Plain files — истина | ● | ○ (cloud DB) | ○ (vector/graph/state) | ○ (app DB) | ○ (server DB) | ● |
| Portable folder | ● | ○ | ○ | ○ | ○ | ● |
| User-defined types + query | ◐ (properties) | ● (supertags/objects) | ○ | ○ | ◐ (datasets/workflows) | ● |
| Typed relations + graph | ● (backlinks/graph) | ● (relations/graph) | ◐ (graph в Zep) | ○ | ◐ (Knowledge Compilation в RAGFlow) | ● |
| Lexical + vector/hybrid | ◐ (keyword) | ◐ (search) | ◐ (semantic/graph) | ● (RAG) | ● (hybrid+rerank) | ● (lexical MVP) |
| Validation + diagnostics | ○ | ○ | ○ | ○ | ○ | ● |
| Safe writes | ◐ (app) | ◐ (app) | ○ (LLM extract) | ○ (app) | ○ (app) | ● |
| Capture workflows | ◐ (daily/templates) | ◐ (AI commands) | ● (extract-and-store) | ◐ (upload) | ◐ (upload) | ● |
| MCP / CLI | ○ | ◐ (API/MCP в Capacities) | ● (MCP/SDK) | ◐ (REST API) | ◐ (REST API) | ◐ (CLI MUST, MCP SHOULD) |
| Obsidian compatibility | ● (Logseq/Foam — MD) | ○ | ○ | ◐ (Khoj plugin) | ○ | ● |
| LLM synthesis | ○ | ◐ (AI commands) | ● (extraction) | ● (RAG/chat) | ● (RAG/agentic) | ○ |
| Task/Plan/Idea | ◐ (daily/tasks) | ● (supertags/objects) | ○ | ○ | ○ | ○ |
| Chat/RAG | ○ | ◐ (AI) | ○ | ● | ● | ○ |
| Web UI | ● (app) | ● (app) | ◐ (dashboard) | ● (app) | ● (web) | ○ (Этап 9) |
| Offline, no hidden LLM | ● | ○ (cloud) | ○ (LLM on write) | ◐ (local models opt-in) | ◐ (self-host, LLM) | ● |

---

## 8. Портабельность как отдельный критерий

### 8.1. Определение

**Портабельность** — способность перенести папку знаний (целиком, на другой путь/машину/ОС) и продолжить работу без ручного исправления, без потери истины и без зависимости от конкретного приложения/сервера. Это не «экспорт в ZIP» и не «синхронизация в облако».

### 8.2. 8 подкритериев (0 = нет, 1 = частично, 2 = полностью)

| ID | Подкритерий | Что проверяется |
|---|---|---|
| P1 | Файлы читаемы без инструмента | Открыть папку в любом редакторе/Obsidian/VS Code без `todoc`/приложения |
| P2 | Нет абсолютных путей в истине | Конфиги/записи/индексы содержат только relative paths; move не ломает ссылки |
| P3 | Нет proprietary DB как истины | Удаление индекса/кэша не теряет данные; истина — файлы |
| P4 | Git-friendly (diffable text) | Изменения видны как текстовые diffs; нет бинарных блобов истины |
| P5 | Cold-rebuild | После удаления derived index/cache всё пересобирается из файлов |
| P6 | OS-независимость | Работает на Linux/macOS/Windows без переконфигурации (пути, case, separators) |
| P7 | Interchange (OKF/Markdown/JSON) | Стандартный формат, который понимают другие инструменты |
| P8 | Offline / no account | Работает без сети, аккаунта, подписки и запущенного приложения |

### 8.3. Скоринг (макс. 16)

| Инструмент | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | Итого | Комментарий |
|---|---|---|---|---|---|---|---|---|---|---|
| **todoc (план)** | 2 | 2 | 2 | 2 | 2 | 2 | 1 (OKF — SHOULD) | 2 | **15** | Цель: максимум. OKF — опциональный профиль, не требование |
| Foam | 2 | 2 | 2 | 2 | 2 | 2 | 1 | 2 | 15 | Только файлы; нет типов/валидации |
| Logseq | 2 | 2 | 2 | 2 | 2 | 2 | 1 | 2 | 15 | MD/org файлы; нет CLI-валидации |
| mdkb | 2 | 2 | 2 | 2 | 2 | 2 | 1 | 2 | 15 | Файлы + disposable FTS5 кэш; MD-only |
| Open Knowledge (`okn`) | 2 | 2 | 2 | 2 | 2 | 2 | 2 (OKF) | 2 | **16** | OKF-формат + managed copy; MD-only |
| okfcli/okf | 2 | 2 | 2 | 2 | 2 | 2 | 2 (OKF) | 2 | **16** | Vendor-neutral bundles; MD-only |
| Basic Memory | 2 | 2 | 2 | 2 | 2 | 2 | 1 | 2 | 15 | MD canonical + rebuildable SQLite/PG |
| Obsidian | 2 | 2 | 2 | 2 | 2 | 2 | 1 | 2 | 15 | Vault — папка MD; CLI требует запущенное приложение (P8 — 2 для файлов, но CLI — нет) |
| QMD | 2 | 2 | 2 | 2 | 2 | 2 | 1 | 1 (`query` — LLM) | 14 | Исходники MD; индекс производный; hybrid — с моделью |
| OpenKB | 1 (wiki MD, но raw/ + registry + PageIndex) | 2 | 1 | 1 | 1 | 2 | 1 | 0 (LLM compile) | 9 | Wiki — MD, но компиляция — LLM и перезаписывает |
| Khoj | 1 | 1 | 0 (vector DB) | 0 | 0 | 1 | 0 | 1 (cloud opt-in) | 4 | App-centric |
| AnythingLLM | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 2 | App-owned storage |
| Open Notebook | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 2 | SurrealDB — истина |
| RAGFlow/Dify/FastGPT | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 2 | Server DB — истина |
| Tana / Capacities / Notion | 0 | 0 | 0 | 0 | 0 | 1 | 0 (export — выгрузка) | 0 | 1 | Cloud DB — истина |
| Mem0 / Zep / Letta | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | Vector/graph/state — истина |
| SiYuan | 1 (import MD) | 1 | 0 (`.sy` + DB) | 0 | 0 | 1 | 0 | 2 | 5 | Свой формат |
| Trilium | 0 | 0 | 0 (SQLite) | 0 | 0 | 1 | 0 | 2 | 3 | DB — истина |
| SilverBullet | 2 | 2 | 2 | 2 | 2 | 1 (server) | 1 | 1 | 13 | MD файлы на сервере |
| Quartz (исходники vault) | 2 | 2 | 2 | 2 | 2 | 2 | 1 | 2 | 15 | Публикация, не база |

**Выводы по портабельности:**
1. `todoc` (план) находится в верхней группе (15/16) вместе с Foam/Logseq/mdkb/Open Knowledge/okf/Basic Memory/Obsidian. Отличие — не «более переносимый», а **переносимый + типизированный + валидируемый + queryable**.
2. Open Knowledge и okfcli получают 16/16 за счёт OKF как interchange-стандарта. Если `todoc` хочет 16/16, OKF-совместимость должна стать MUST, а не SHOULD. Рекомендация конституции: оставить SHOULD для MVP (не требовать OKF для обычных заметок), но сделать OKF-profile первым v1-профилем совместимости.
3. App-centric RAG (AnythingLLM/Open Notebook/RAGFlow/Dify/FastGPT) и cloud PKM (Tana/Capacities/Notion) и vector/graph memory (Mem0/Zep/Letta) — внизу (1–4/16). Это не «плохо», а другая модель владения: истина в приложении/БД, не в файлах. `todoc` не должен копировать эту модель.
4. OpenKB — средняя (9/16): wiki — Markdown, но компиляция — LLM, перезаписывает ручные правки, требует модель. Trade-off «автоматическая компиляция vs source-native deterministic проверки» — ключевое позиционирование `todoc`.

---

## 9. Аудитория и позиционирование

| Инструмент | Кого обслуживает | Позиционирование одной фразой | Что не обслуживает |
|---|---|---|---|
| Obsidian | Человек, ведущий vault вручную | «Папка Markdown + мощный редактор/граф/плагины» | Агентскую валидацию CSV/JSON, typed records с units/formula |
| QMD | Разработчик/агент, ищущий по Markdown | «Быстрый hybrid-поиск по локальным коллекциям» | Проверку исходников, типы, записи |
| Open Knowledge | Maintainer Markdown-знаний в репозитории | «Managed Markdown-бандл с check/validate/eval/CI» | CSV/JSON source-native QA, typed records |
| okfcli/okf | AI-driven docs/catalog pipelines | «Vendor-neutral OKF bundles: validate/lint/search/graph» | CSV/JSON, record query/aggregate |
| OpenKB | Исследователь, компилирующий источники в wiki | «LLM компилирует raw/ в связную wiki» | Source-native deterministic QA без LLM |
| mdkb | Агент + Obsidian как редактор | «Один Go binary: CLI+MCP+FTS5+git writes» | Типы/схемы/запросы/валидация |
| Basic Memory | Агент, нуждающийся в межсессионной памяти | «Markdown — память агента, SQLite — проекция» | Source-native QA CSV/JSON, typed aggregate с units |
| Khoj | Personal second brain, multi-device | «Self-hosted AI second brain: chat по своим документам» | CLI-валидацию, переносимые типы |
| AnythingLLM | Private document chat, workspaces | «Turnkey desktop RAG + agents + API» | Файловую истину, валидацию |
| LLM Wiki | Человек + coding agent, накапливающие знания | «Агент компилирует и поддерживает wiki» | Детерминированную проверку исходников |
| obsidian-second-brain | AI-first second brain в Obsidian | «Vault как живая память: tasks/projects/ideas/research» | Не-Obsidian workflow, source-native QA |
| Tana/Capacities | Power user / visual thinker | «Supertags/objects: типизированные заметки с запросами» | Локальные файлы, CLI, offline |
| Mem0/Zep/Letta | Разработчик agent memory | «Memory API / temporal graph / self-managing agent» | Человекочитаемые файлы |
| Open Notebook/RAGFlow | Research/enterprise KB | «Self-hosted NotebookLM / enterprise RAG» | Файловую истину, CLI-валидацию |
| **todoc (план)** | **Человек, просящий агента поддерживать собственные структурированные знания** | **«Опиши типы один раз — агент сохраняет/связывает/проверяет/находит в переносимой папке»** | **Polished dashboards, автономную LLM-компиляцию, multi-user sync** |

**Gap для `todoc`:** никто из конкурентов не соединяет **source-native валидацию смешанных MD/CSV/JSON с точными locations** + **пользовательские entity types с JSON Schema/units** + **typed relations/query/aggregate с provenance** + **type-directed capture через Skill** + **полную портабельность**. Каждый компонент есть где-то; связка — гипотеза.

---

## 10. Сравнение между собой и с `todoc` по планируемому функционалу

### 10.1. Где `todoc` выигрывает (по плану)

1. **Source-native QA смешанных источников.** Open Knowledge/okf валидируют Markdown/OKF; QMD/mdkb ищут; OpenKB компилирует. Никто не валидирует исходные CSV/JSON по структуре/смысловым правилам с row/column/JSON Pointer diagnostics и review-first fixes без конвертации.
2. **Typed records + query/aggregate с provenance.** Tana/Capacities/Notion/Dataview имеют типы/запросы, но в cloud/app, без JSON Schema/units/formula в файлах и без CLI-контракта для агента. `todoc` — file-native + CLI + units/formula/provenance.
3. **Type-directed capture.** «Сохрани ссылку/ресерч/план» → Skill уточняет обязательные поля → CLI валидирует и создаёт. Obsidian templates/second-brain commands — ручные/промптовые; Basic Memory `write_note` — без schema/units/relation validation.
4. **Портабельность + детерминированность.** Basic Memory/mdkb/Open Knowledge тоже локальны, но `todoc` добавляет: multi-root изоляцию, atomic generations, `explain-path`, `next_actions` как argv, eval-gate. QMD `query` и OpenKB compile требуют модель; `todoc` ядро — без модели.
5. **Разделение измерений.** `format` ≠ `doc_type` ≠ `dir_type` ≠ `entity_type` ≠ `relation_type`. Конкуренты смешивают (коллекция = тип, папка = тип, tag = тип).

### 10.2. Где `todoc` проигрывает (честно)

1. **Поиск.** QMD (BM25+vector+rerank), Basic Memory (hybrid), Khoj/AnythingLLM/Open Notebook (RAG) — зрелые движки. `todoc` MVP — только lexical; vector/hybrid — opt-in позже. Без benchmark `todoc` не должен обещать «лучший поиск».
2. **Человеческий UX.** Obsidian/Tana/Capacities/Notion — polished apps (граф, доски, мобильные, sync). `todoc` MVP — CLI + файлы; веб — Этап 9. Не конкурировать с приложениями.
3. **Компиляция/синтез.** OpenKB/LLM Wiki/second-brain — уже компилируют и синтезируют. `todoc` MVP сознательно не делает. Если пользователю нужен синтез — это отдельный профиль или интеграция, не core.
4. **Memory.** Mem0/Zep/Letta/Basic Memory — готовые memory API с MCP/SDK. `todoc` MVP — не memory. Не называть `doc_type` поддержкой памяти.
5. **Зрелость.** Все конкуренты выше — существующие продукты (от v0.1.0 mdkb до зрелого Obsidian). `todoc` — только план, реализации нет. Любое сравнение — feature audit, не benchmark.

### 10.3. Что копировать / что не копировать / где интегрироваться

| Решение | Действие | Почему |
|---|---|---|
| QMD `search/vsearch/query/get/multi-get/status` + `--json` | **Копировать контракт** (имена/флаги/JSON) | Зрелый CLI для поиска; `todoc` может быть thin adapter поверх QMD. Подкоманда `mcp` из этого набора **исключена**: решение 2026-11-25 — MCP является поздней надстройкой над CLI и может не понадобиться вовсе |
| mdkb `--root`, `--json`, `--dry-run`, `--allow-write`, disposable cache, goldens | **Копировать** | Лучший референс CLI/MCP-контрактов для агента |
| Open Knowledge `setup/check/validate/search/view/eval` + plan-before-write diff + hash/locator | **Копировать** | Ближайший Markdown CLI; `validate`/`check`/`eval` — референс |
| okf `validate/lint/index/list/show/search/backlinks/graph` + SARIF + `--fail-on` | **Копировать** | CI-валидация и interchange |
| Basic Memory MCP tools + watcher + stable id survives move + SessionStart brief | **Копировать** (для memory-профиля) | Лучший референс Markdown-памяти |
| Obsidian vault + wikilinks subset + `search:context`/`backlinks`/`unresolved` | **Копировать subset** | Совместимость без зависимости |
| Tana supertags / Capacities objects / Dataview DQL | **Копировать идею** (типы/запросы), не реализацию | Концептуальный референс для `entity_type`/query |
| OpenKB `add/query/chat/visualize/skill/deck` | **Не копировать** (кроме `lint`/`visualize` как идей) | LLM compile + overwrite — противоположная модель |
| AnythingLLM/Khoj/Open Notebook/RAGFlow app-centric RAG | **Не копировать**; интегрироваться при нужде | App-owned storage противоречит P1/P2 |
| Mem0/Zep/Letta vector/graph memory | **Не копировать** в core; интегрироваться как opt-in adapter при memory-профиле | Vector/graph — истина противоречит P1 |
| obsidian-second-brain 40+ команд | **Не копировать** как есть; взять task/idea/project схемы как референс для профиля | Привязка к Obsidian + опасные auto-writes |
| Karpathy `raw/wiki/index/log` + ingest/query/lint | **Не копировать** в core; отдельный профиль | Синтез ≠ source-native QA |

**Интеграция вместо конкуренции:** если discovery gate покажет, что Markdown-only поиск закрывается QMD/Open Knowledge, а cross-format checks не оказываются регулярной болью — оставить `todoc` как небольшой validator/adapter/Skill поверх существующего search tooling. Если location-aware diagnosis/repair реально экономит время — развивать эту узкую часть первой.

---

## 11. Выводы для конституции (что добавить/убрать)

1. **OKF-совместимость:** оставить SHOULD для MVP, но сделать OKF-profile первым v1-профилем совместимости (путь к 16/16 портабельности). Не требовать OKF для обычных заметок.
2. **MCP:** подтвердить SHOULD (v1) по референсу QMD/mdkb/Basic Memory: read-only по умолчанию, write за явным флагом, stateless, tools + resources.
3. **Search backend:** benchmark `todoc` lexical (FTS5) vs QMD на одних задачах до выбора. Не обещать vector/hybrid в MVP.
4. **Memory/LLM Wiki:** подтвердить WON'T в core. При memory-профиле — референсы Basic Memory (MCP/watcher/stable id), claude-obsidian (transactions), second-brain (task/idea схемы), Karpathy (raw/wiki).
5. **Typed query:** референс Dataview DQL + Tana live queries + Capacities objects. `todoc` отличается file-native JSON Schema + units/formula + CLI.
6. **Веб:** референс OpenKB `visualize` + okf `serve/render` + Quartz publishing. Веб — Этап 9, не MVP.
7. **Ничего не добавлять в MVP** из C25–C60 WON'T/COULD без отдельного scope gate. Конституция уже фиксирует границы; конкурентный анализ их подтверждает.

---

## 12. Источники

### Референсы из `docs/research/skills-audit/` (snapshot hashes — в аудите)

- Karpathy LLM Wiki gist — https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- Astro-Han/karpathy-llm-wiki — https://github.com/Astro-Han/karpathy-llm-wiki
- vanillaflava/llm-wiki-skills — https://github.com/vanillaflava/llm-wiki-skills
- eugeniughelbur/obsidian-second-brain — https://github.com/eugeniughelbur/obsidian-second-brain
- AgriciDaniel/claude-obsidian — https://github.com/AgriciDaniel/claude-obsidian
- bholmesdev/llm-knowledge-base-skills — https://github.com/bholmesdev/llm-knowledge-base-skills
- ConardLi/rag-skill — https://github.com/ConardLi/rag-skill
- Open Knowledge CLI — https://github.com/openknowledge-sh/openknowledge

### Дополнительные конкуренты (веб-поиск, 24 ноября 2026)

- Obsidian CLI — https://obsidian.md/cli ; Obsidian data storage — https://obsidian.md/help/data-storage ; Obsidian file formats — https://obsidian.md/help/file-formats
- QMD — https://github.com/tobi/qmd ; release v2.9.0 — https://github.com/tobi/qmd/releases/tag/v2.9.0 ; processors — https://github.com/tobi/qmd/blob/main/docs/PROCESSORS.md
- Open Knowledge — https://openknowledge.sh/ ; wiki — https://openknowledge.sh/wiki/ ; changelog — https://openknowledge.sh/wiki/changelog/cli.html
- okfcli/okf — https://github.com/okfcli/okf ; okfctl — https://github.com/cwest/okfctl ; okf-gem — https://github.com/serradura/okf-gem ; abatyuk/okf — https://github.com/abatyuk/okf ; OKF spec v0.2 — https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
- OpenKB — https://github.com/VectifyAI/OpenKB ; README — https://github.com/VectifyAI/OpenKB/blob/main/README.md
- mdkb — https://github.com/ContractorKeith/mdkb ; release v0.1.0 — https://github.com/ContractorKeith/mdkb/releases/tag/v0.1.0
- Basic Memory — https://github.com/basicmachines-co/basic-memory ; MCP — https://mcpdir.dev/servers/basic-memory
- Khoj — https://docs.khoj.dev/ ; search — https://docs.khoj.dev/features/search/
- AnythingLLM — https://docs.anythingllm.com/chatting-with-documents/introduction ; storage — https://docs.anythingllm.com/installation-desktop/storage ; live sync beta — https://docs.anythingllm.com/beta-preview/active-features/live-document-sync
- Karpathy LLM Wiki pattern — https://blog.starmorph.com/blog/karpathy-llm-wiki-knowledge-base-guide ; Astro-Han skill — https://github.com/Astro-Han/karpathy-llm-wiki
- obsidian-second-brain (44 команды) — https://github.com/eugeniughelbur/obsidian-second-brain
- Tana vs Capacities vs Logseq — https://www.asianefficiency.com/technology/tana-vs-capacities-vs-logseq/ ; Capacities vs Tana — https://capacities.io/compare/tana
- Mem0 vs Letta vs Zep — https://dev.to/plur9/mem0-vs-letta-vs-zep-which-should-you-use-for-agent-memory-1n8m ; Mem0 alternatives 2026 — https://xerj.org/compare/mem0-alternatives-2026
- SiYuan / Trilium / SilverBullet / Foam / Quartz — https://www.femaleswitch.com/directories/tpost/open-source-obsidian-alternatives ; https://github.com/manuvamp/awesome-second-brain
- Open Notebook — https://pinggy.io/blog/self_host_open_notebook_notebooklm_alternative/ ; NotebookLM local — https://goldstarlinks.com/notebooklm-local/
- RAGFlow / Dify / FastGPT — https://awesomeosai.com/self-hosted/rag ; https://jimmysong.io/blog/open-source-ai-agent-workflow-comparison/

### Граница применимости

Документация показывает официально описанные функции, но не гарантирует корректность продукта на конкретном корпусе. Сравнительные таблицы — feature audit, не market sizing, adoption/demand research или независимый quality benchmark. Self-reported метрики авторов (например, mdkb search-eval, Mem0/Zep LOCOMO) не являются независимым сравнительным тестом. Всё из §4–§7 надо проверять на закреплённых версиях реальных инструментов, одинаковых данных и пользовательских задачах.
