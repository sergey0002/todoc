---
id: doc:agent-brainstorming-and-research-packs
title: "Ресёрч: лучшие паки скилов и скриптов для мозговых штурмов и исследований агентов"
doc_type: research-report
lang: ru
created: 2026-11-26
updated: 2026-11-26
tags: [research, research-report, brainstorming, deep-research, agent-skills, scripts]
related: ["[[skills-vault-implementation]]", "[[skills-engine]]", "[[comparative-audit]]"]
---

# Ресёрч: лучшие готовые паки скриптов и скилов для мозговых штурмов и ресёрча агентов

**Дата среза:** 26 ноября 2026 года  
**Метод проверки:** поиск по открытым реестрам (`skills.sh`, GitHub, каталоги Agent Skills) + прямая инспекция деревьев файлов, `SKILL.md` и каталогов `scripts/` через GitHub API.  
**Фокус:** не просто короткие промпты-памятки, а **зрелые инженерные паки** (формат `SKILL.md` + детерминированные Python/Bash/JS-скрипты, субагенты, анти-галлюцинационные гейты, журналы доказательств и алгоритмы декомпозиции).

---

## 1. Главный вывод (TL;DR)

В экосистеме агентных скилов 2026 года произошёл чёткий водораздел между «промпт-коллекциями» (тысячи одностраничных `SKILL.md` без проверок) и **исполняемыми методическими паками**, где промпт задаёт протокол мышления, а **скрипты в `scripts/` берут на себя детерминированную часть**: ведение append-only журнала идей/источников, валидацию матриц гипотез, сверку дословных цитат с текстом страницы, опрос API (GitHub, arXiv, OpenAlex, PubMed, Reddit/X/HN) и проверку полноты покрытия.

Ни один монолитный репозиторий не закрывает одинаково сильно и штурм, и ресёрч:
- В `obra/superpowers` эталонный сократический `brainstorming` с визуальным сервером-компаньоном, но **нет отдельного скила глубокого ресёрча**.
- В `Imbad0202/academic-research-skills`, `mvanhorn/last30days-skill` и `NousResearch/hermes-agent` мощнейшие скриптовые движки верификации и сбора данных, но нет продуктового штурма.
- Единственные две системы, где оба контура спроектированы как единый скриптовый конвейер, — **`bmad-code-org/BMAD-METHOD` (v6+)** (`bmad-brainstorming` + `bmad-deep-recon`), **`EveryInc/compound-engineering-plugin`** (`ce-ideate` + `ce-brainstorm` + ресёрч-субагенты) и научно-аналитические наборы **`K-Dense-AI/scientific-agent-skills`** / **`wanshuiyin/Auto-claude-code-research-in-sleep` (ARIS)**.

Самая сильная стратегия на практике — **композиция 5–6 лучших специализированных паков** по стадиям воронки мышления.

---

## 2. Критерии отбора

| Код | Критерий | Почему это важно для агента |
|---|---|---|
| **C1** | Наличие реальных `scripts/` | Детерминированный учёт источников/цитат/гипотез, опрос API, локальные серверы или валидаторы вместо надежды на память LLM |
| **C2** | Анти-сикофантия и гейты | Запрет преждевременного согласия, разделение дивергенции и критики, `<HARD-GATE>` до кода, стоп-правила насыщения |
| **C3** | Защита от context rot | Запись промежуточных находок/идей на диск (`memlog`, `findings.md`, JIT-дайджесты субагентов) |
| **C4** | Доказательность (provenance) | Привязка каждого тезиса к первоисточнику, проверка цитат, фиксация отрицательных результатов (что искали и не нашли) |
| **C5** | Портабельность (`SKILL.md`) | Совместимость с открытым стандартом Agent Skills (Claude Code, Codex, Cursor, Gemini CLI, OpenCode, `todoc skills import`) |

---

## 3. Часть А. Лучшие готовые паки для мозговых штурмов и проработки идей

### A1. `obra/superpowers` → `skills/brainstorming` (★ 327.3k · MIT · 442k+ установок)
- **Репозиторий:** https://github.com/obra/superpowers (`skills/brainstorming/`) — *уже импортирован в `demo/skills/process/superpowers/brainstorming`*.
- **Состав пака:** `SKILL.md` + `builder-check-prompt.md` + `visual-companion.md` + 5 скриптов в `scripts/` (`server.cjs`, `helper.js`, `frame-template.html`, `start-server.sh`, `stop-server.sh`).
- **Как устроен:**
  1. Сбор контекста проекта (recon) до первого вопроса пользователю.
  2. Сократический диалог строго **по одному вопросу за ход**, без «меню готовых ответов», которые подталкивают пользователя.
  3. **Play It Back:** возврат понятого кусками по 200–300 слов с явным разделением «что сказал человек» vs «предложение агента и почему».
  4. Обязательная выкладка **2–3 реальных архитектурных подходов** с компромиссами в отдельном сообщении до написания спеки.
  5. **Visual Companion (`scripts/server.cjs`):** локальный браузерный сервер для кликабельных мокапов, схем и side-by-side сравнения вариантов.
  6. **Builder Check:** прогон готового дизайн-дока через свежего субагента (`builder-check-prompt.md`) с сортировкой вопросов на 3 корзины (*Answered / Minor / Theirs*) и жёсткий `<HARD-GATE>` на запрет кода до апрува.
- **Сильная сторона:** лучший сократический продуктово-инженерный штурм «от размытого запроса до согласованного дизайн-дока».
- **Ограничение:** фокусируется на сходимости к одному решению, а не на широкой генерации 50–100 нестандартных идей.

### A2. `mattpocock/skills` → `grilling` / `grill-me` / `grill-with-docs` (★ 333.5k · MIT · 460k+ установок)
- **Репозиторий:** https://github.com/mattpocock/skills (`skills/productivity/grilling/`, `grill-me/`, `skills/engineering/grill-with-docs/`, `prototype/`).
- **Состав пака:** модульные `SKILL.md` + `agents/` (чистый стандарт Agent Skills без внешних зависимостей).
- **Как устроен:** формализует стресс-тест идеи или плана как обход **дерева решений по фронту (Design Tree Frontier)**:
  - На каждом раунде агент вычисляет **фронт** — все узлы дерева решений, чьи предпосылки уже закрыты.
  - Задаёт весь текущий фронт пронумерованным пакетом (`❓ Q1 ... ➡️ рекомендованный ответ`), никогда не спрашивая зависимые вопросы раньше времени.
  - **Разделение фактов и решений:** факты об окружении/коде агент обязан добыть сам через фонового субагента с чистым контекстом, не блокируя независимые ветки опроса; у человека спрашиваются только решения.
  - Завершается, когда фронт пуст; связка `grill-with-docs` параллельно вызывает `domain-modeling`, обновляя `GLOSSARY.md` и ADR по ходу интервью.
- **Сильная сторона:** идеальная «вторая ступень» после штурма — находит все скрытые допущения и дыры в плане.

### A3. `bmad-code-org/BMAD-METHOD` (v6+) → `bmad-brainstorming` + `bmad-party-mode` + `bmad-forge-idea` + `bmad-advanced-elicitation` (★ 55.8k)
- **Репозиторий:** https://github.com/bmad-code-org/BMAD-METHOD (`skills/core-tools/`).
- **Состав пака:** полноценный Python-инструментарий (`scripts/brain.py`, тесты `scripts/tests/`, атомарный логгер `_bmad/scripts/memlog.py`, `customize.toml`, 8 ролевых и режимных `references/*.md`).
- **Как устроен:**
  - **Три жёстких режима (stances):** `Facilitator` (агент вообще не подаёт своих идей — работает чистым катализатором человека), `Creative Partner` (совместный пинг-понг идей), `Autonomous / Headless` (агент сам прогоняет весь многотехникный штурм).
  - **Защита от ранней сходимости:** правило *«Aim past 100 ideas; resist concluding»* + принудительная смена креативной техники/линзы каждые 5–10 ходов (SCAMPER, Six Thinking Hats, Reverse Brainstorming, Starbursting, Mind Mapping, 5 Whys и др.).
  - **Атомарная память сессии (`memlog.py`):** каждая идея, решение и ограничение дописываются одной строкой в `.memlog.md` — сессию можно прервать и возобновить (`resume.md`) без потери контекста.
  - **`bmad-party-mode`:** мульти-персонный круглый стол (PM, Архитектор, Аналитик, UX, Разработчик, QA спорят друг с другом в одном треде).
- **Сильная сторона:** самый мощный пакет именно для **дивергентного** мозгового штурма и командной фасилитации со скриптовой памятью.
- **Нюанс переноса:** для полной автоматизации ожидает bootstrap `_bmad/scripts/` (`uv run`), но имеет штатный fallback на чтение `customize.toml`.

### A4. `EveryInc/compound-engineering-plugin` → `ce-ideate` + `ce-brainstorm` + `ce-pov` + `ce-bakeoff` (★ 26.2k · MIT)
- **Репозиторий:** https://github.com/EveryInc/compound-engineering-plugin (`skills/`).
- **Состав пака:** `SKILL.md` + глубокие фазовые `references/` + скрипты в `ce-brainstorm/scripts/` (`light-webserver.js`, `peer-job-runner.py`, `packs-resolve.py`, `elevation-dispatch.sh`).
- **Как устроен:** делит раннюю проработку на 4 специализированных скила:
  1. **`ce-ideate`:** сначала приземляется об кодовую базу и прошлые уроки (`docs/solutions/`) → генерирует широкий пул кандидатов → **прогоняет жёсткую критику по каждому с явным обоснованием отсева** (*«Generate many, critique all, explain survivors only»*) → отдаёт только выжившие идеи.
  2. **`ce-brainstorm`:** превращает выбранную идею в соразмерный задаче артефакт требований (для мелочей заканчивается абзацем в чате без бюрократии; для крупных задач поднимает `light-webserver.js` или кросс-модельный `peer-job-runner.py`).
  3. **`ce-pov`:** отдельный скил вынесения вердикта по внедрению внешней технологии/библиотеки.
  4. **`ce-bakeoff`:** параллельная сборка конкурирующих прототипов с честным сравнением в бою.
- **Сильная сторона:** лучшее разделение «придумать варианты (`ce-ideate`)» и «оформить требования (`ce-brainstorm`)» с обязательным отсевом слабых идей.

### A5. `garrytan/gstack` → `office-hours` + `autoplan` + `plan-ceo/design/eng-review` + `codex` (★ 142.7k · MIT)
- **Репозиторий:** https://github.com/garrytan/gstack (`office-hours/`, `autoplan/`, `plan-ceo-review/`, `plan-eng-review/`, `codex/`).
- **Состав пака:** шаблонизированные `SKILL.md`, bash-хуки и бинарные обёртки (`autoplan/bin/phase-publication-hook`, `gstack-skill-load`), интеграция с локальной памятью `gbrain` (`eureka.jsonl`, история дизайн-доков и профиль билдера).
- **Как устроен:**
  - **`/office-hours`:** продуктовый штурм в стиле партнёрских сессий Y Combinator (проверка статус-кво, остроты проблемы, самого узкого клина запуска — *narrowest wedge*, неожиданных наблюдений пользователей).
  - **`/autoplan`:** автоматический конвейер последовательного ревью плана глазами CEO → Дизайнера → Инженерного лида → DX с `PreToolUse`-хуком, запрещающим перепрыгивать фазы публикации, и вызовом `/codex` для независимого второго мнения другой модели.
- **Сильная сторона:** лучший пакет для продуктового/стартап-мышления («стоит ли вообще это строить и какой минимальный клин даст максимум ценности»).

### A6. Научный и R&D-брейншторминг со скриптовой валидацией
- **`K-Dense-AI/scientific-agent-skills`** (★ 58.6k · MIT, https://github.com/K-Dense-AI/scientific-agent-skills):
  - `skills/scientific-brainstorming/` (`scripts/session_scaffold.py`, `evaluate_matrix.py`, `validate_register.py`) — матричная оценка идей и валидация реестра концепций.
  - `skills/hypothesis-generation/` (`scripts/validate_hypothesis_schema.py`, `validate_prediction_matrix.py`, `check_falsification_controls.py`, `check_operationalization.py`, `lint_causal_claims.py`, `audit_evidence_ledger.py`) — проверяет, что каждая гипотеза фальсифицируема, операционализирована и не содержит голословных каузальных утверждений.
- **`Orchestra-Research/AI-Research-SKILLs`** (★ 14.8k · MIT, https://github.com/Orchestra-Research/AI-Research-SKILLs):
  - `21-research-ideation/brainstorming-research-ideas/` (10 исследовательских линз: инверсия допущений, перенос узкого места, композиция/декомпозиция, смена масштаба и др.) и `creative-thinking-for-research/` (бисоциация Кёстлера, структурное отображение Гентнер, манипуляция ограничениями).
- **`addyosmani/agent-skills`** (★ 120.6k · MIT, https://github.com/addyosmani/agent-skills):
  - `skills/idea-refine/` (`scripts/idea-refine.sh`, `frameworks.md`, `refinement-criteria.md`) + `interview-me/` + `doubt-driven-development/` — компактный цикл дивергенции → кластеризации → one-pager в `docs/ideas/`.
- **`deanpeters/Product-Manager-Skills`** (★ 8.2k, https://github.com/deanpeters/Product-Manager-Skills):
  - 80+ готовых продуктовых фреймворков (`opportunity-solution-tree`, `assumption-mapping`, `problem-framing-canvas`, `jobs-to-be-done`, `workshop-facilitation`).

### A7. Мульти-агентные дебаты, Советы моделей и классическая фасилитация
- **`worksystems-design/libertee`** (MIT, https://github.com/worksystems-design/libertee) — 9 классических методик фасилитации как мульти-агентные сессии: **Six Thinking Hats**, **Adversarial Debate** (3 раунда, где Pro и Contra *запрещено соглашаться* до вердикта Судьи), **Disney Strategy** (три изолированные комнаты-агента: *Dreamer → Realist → Critic*), **Pre-Mortem** (*Doom Analyst* ищет причины будущего провала), **Polarity Management**, **TRIZ** (обратный штурм «как гарантированно всё сломать») и **W³**.
- **`juanallo/six-hats-skill`** (https://github.com/juanallo/six-hats-skill) — практический урок из боевой эксплуатации Six Hats: шляпы запускаются **последовательно, а не параллельно** (чтобы Чёрная и Зелёная шляпы били по реальным тезисам Белой и Жёлтой), а Синяя шляпа-модератор выступает только в финале.
- **Кросс-модельные советы и равновесие Нэша:** `affaan-m/ECC` (`skills/council/`, `council-multi-model/`, ★ 311.2k), `karpathy/llm-council` (★ 27.0k — анонимное взаимное рецензирование моделей + синтез Председателя), `andrewvaughan/agent-council` (6 профильных советов с голосованием *Approve / Concern / Block*), `sd0xdev/codex-brainstorm` и `zscole/adversarial-spec` (независимый ресёрч Claude и Codex с раундами взаимных атак до равновесия Нэша).

---

## 4. Часть Б. Лучшие готовые паки скриптов и скилов для глубокого ресёрча

### B1. `Imbad0202/academic-research-skills` — максимальный скриптовый конвейер верификации (★ 58.7k)
- **Репозиторий:** https://github.com/Imbad0202/academic-research-skills (`deep-research/`, `sr-screener/`, `academic-paper-reviewer/`, `scripts/`).
- **Состав пака:** 5 крупных многофазных скилов + 47 специализированных субагентов + **более 200 Python-скриптов и модульных тестов в `scripts/`**.
- **Ключевые скрипты и механизмы:**
  - Поисковые клиенты первоисточников: `arxiv_client.py`, `openalex_client.py`, `semantic_scholar_client.py`, `crossref_client.py`, `retraction_status.py` (проверка отозванных статей!).
  - Аудит утверждений и цитат: `claim_audit_pipeline.py`, `uncited_assertion_detector.py`, `bibliographic_integrity_signals.py`, `temporal_integrity_audit.py` (ловит устаревшие факты, выданные за текущие), `slr_lineage.py` (PRISMA-трассировка отбора).
  - Управление ветвями поиска и анти-эхокамера: `inquiry_branch_ledger.py`, `ideation_diversity_assignment_gate.py`, `cross_model_codex_verify.sh`.
- **Сильная сторона:** беспрецедентная глубина автоматических проверок истинности, триангуляции и библиографической гигиены.

### B2. `mvanhorn/last30days-skill` — лучший скриптовый движок живого пульса сети и соцплатформ (★ 75.6k · MIT)
- **Репозиторий:** https://github.com/mvanhorn/last30days-skill (`skills/last30days/`).
- **Состав пака:** `SKILL.md` + 16 скриптов в `scripts/` (`last30days.py`, `briefing.py`, `store.py`, `watchlist.py`, `evaluate_search_quality.py`, `lib/`) + опциональный Go MCP-сервер.
- **Как устроен:**
  - Параллельно собирает свежие обсуждения за настраиваемое окно (по умолчанию 30 дней) из **Reddit, X/Twitter, Hacker News, YouTube, TikTok, Polymarket, GitHub, Bluesky и веба**.
  - Ранжирует результаты не по SEO-мусору, а по **реальным метрикам вовлечённости и ставок** (апвоуты, ответы, звёзды, объёмы Polymarket), выделяя прямую речь первоисточников (`from:@handle`).
  - Имеет встроенную команду `doctor` для диагностики доступных источников и локальную SQLite FTS5-базу (`store.py`, `watchlist.py`) для накопления брифингов и мониторинга тем.
- **Сильная сторона:** незаменим для ресёрча «что прямо сейчас реально используют, хвалят или ругают инженеры и рынок».

### B3. `bmad-code-org/BMAD-METHOD` (v6+) → `bmad-deep-recon` — глубокая техническая, кодовая и рыночная разведка (★ 55.8k)
- **Репозиторий:** https://github.com/bmad-code-org/BMAD-METHOD (`skills/core-tools/bmad-deep-recon/`).
- **Состав пака:** `SKILL.md` + `scripts/recon_kit.py` + `_bmad/scripts/memlog.py` + `evals/` + 14 модулей `references/` (`codebase-locator.md`, `codebase-analyzer.md`, `codebase-historian.md`, `codebase-verifier.md`, `synthesis.md`, `verification.md`, `html-briefing.md`).
- **Как устроен:**
  - **«Nothing exists until it is a file»:** каждый дайджест пачки источников немедленно пишется в папку запуска; при обрыве сессии ресёрч продолжается с диска без потерь.
  - **«Extract, don't ingest»:** сырые веб-страницы и большие файлы никогда не валятся в родительский контекст целиком — изолированные субагенты получают только свой узкий бриф и возвращают отфильтрованные дайджесты.
  - **Окна свежести по классам утверждений:** каждый тезис обязан иметь издателя, дату публикации и дату доступа; отсутствие данных фиксируется как явный научный факт, а не маскируется домыслами; весь ход пишется в `memlog.py --type <decision|source|claim|assumption|question|event>`.

### B4. `K-Dense-AI/scientific-agent-skills` — модульные Python-скрипты для литературы, цитат и рыночных отчётов (★ 58.6k · MIT)
- **Репозиторий:** https://github.com/K-Dense-AI/scientific-agent-skills (`skills/`).
- **Ключевые ресёрч-скилы со скриптами:**
  - `literature-review/scripts/`: `search_databases.py`, `verify_citations.py`, `generate_pdf.py`
  - `citation-management/scripts/`: `doi_to_bibtex.py`, `extract_metadata.py`, `search_openalex.py`, `search_pubmed.py`, `search_google_scholar.py`, `validate_citations.py`
  - `market-research-reports/scripts/`: `audit_claim_citations.py`, `validate_evidence_ledger.py`, `validate_competitor_matrix.py`, `calculate_market_sizing.py`, `check_unit_consistency.py`, `forecast_sensitivity.py`
  - `research-lookup/scripts/`: `research_lookup.py`, `manuscript_packet.py`
- **Сильная сторона:** чистые автономные папки `SKILL.md + scripts/*.py` по стандарту Agent Skills — идеальны для точечного импорта отдельных скилов.

### B5. `wanshuiyin/Auto-claude-code-research-in-sleep` (ARIS ⚔️) — автономный цикл «идея → проверка новизны → ресёрч → кросс-модельное ревью» (★ 19.9k · MIT)
- **Репозиторий:** https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep (`skills/`).
- **Состав пака:** 84+ легковесных скила без привязки к тяжёлому фреймворку:
  - Разведка и отсев идей: `idea-discovery/`, `idea-creator/`, `novelty-check/`, `prior-art-search/`, `kill-argument/` (целенаправленный поиск аргументов, убивающих слабую гипотезу до затрат ресурсов!).
  - Поиск и проверка: `arxiv/`, `alphaxiv/`, `deepxiv/`, `openalex/`, `semantic-scholar/`, `exa-search/`, `firecrawl-search/`, `citation-audit/`, `citation-crosscheck/`, `paper-claim-audit/`.
  - Автономные циклы ревью между моделями: `auto-review-loop/`, `skills-codex-claude-review/`, `skills-codex-gemini-review/`, `research-refine-pipeline/`.

### B6. Компактные эталонные паки строгого ресёрча и анти-галлюцинаций
- **`NousResearch/hermes-agent` → `skills/research/grounded-citations` + `arxiv`** (★ 266.3k · MIT, https://github.com/NousResearch/hermes-agent/tree/main/skills/research):
  - Скрипт `scripts/sources.py` забирает у модели управление номерами ссылок (`url → [n]`): LLM оперирует только выданными целыми индексами и не может выдумать URL из памяти.
  - Режим высокой строгости проверяет, что прикреплённая цитата **буквально входит подстрокой** в скачанный текст страницы, помечает знания из весов модели тегом `[unverified]` и валит сборку (`verify --evidence`), если за ссылкой нет доказательства.
- **`bytedance/deer-flow` → `skills/public/github-deep-research` + `systematic-literature-review`** (★ 85.8k · MIT, https://github.com/bytedance/deer-flow/tree/main/skills/public):
  - `github-deep-research` (`SKILL.md` + `scripts/github_api.py` + `assets/report_template.md`): 4-раундовое исследование любого open-source проекта/конкурента (метрики и история коммитов/PR через GitHub API → веб-дискавери → архитектура и сентимент сообщества → эволюция контрибьюторов, Mermaid-таймлайны и оценка уверенности High/Medium/Low).
  - `systematic-literature-review` (`SKILL.md` + `scripts/arxiv_search.py` + `templates/` + `evals/`): систематический обзор статей с параллельным извлечением методологии и ограничений.
- **`hyderhusainarastu/deep-research-skill`** (MIT, https://github.com/hyderhusainarastu/deep-research-skill):
  - Аудируемый протокол со скриптами `scripts/lexical_audit.py` и `scripts/check_csv.py`: волны поиска, дедупликация, явные уровни верификации (открыт полный текст vs прочитан сниппет), **правило остановки по насыщению (saturation stop rule)** и **журнал отрицательных находок** (что искали и чего нет). Два профиля: `FULL` (параллельные воркеры + независимый аудитор) и `SCOPED` (один агент со сменой ролей).
- **`Weizhena/Deep-Research-skills`** (★ 2.6k · MIT, https://github.com/Weizhena/Deep-Research-skills):
  - Двухфазный ресёрч с контролем человека (по мотивам статьи *RhinoInsight*): Фаза 1 строит и согласует каркас исследования, Фаза 2 ведёт глубокий сбор по утверждённым осям.

### B7. Инфраструктурный слой ресёрча: долговременная память хода и поисковые CLI
- **`OthmanAdi/planning-with-files`** (★ 28.2k · MIT, https://github.com/OthmanAdi/planning-with-files) — 22 скрипта (`init-session.sh`, `inject-plan.py`, `session-catchup.py`, `ledger-append.sh`, `gate-stop.sh`), реализующие паттерн Manus (`task_plan.md` + `findings.md` + `progress.md`) и **«правило 2 действий»**: после каждых 2 поисковых/браузерных вызовов агент обязан сбросить находки в `findings.md`, чтобы сжатие контекста никогда не стирало собранную фактуру.
- **`gsd-build/get-shit-done`** (★ 64.1k · MIT, https://github.com/gsd-build/get-shit-done) — параллельная четвёрка ресёрч-субагентов (`gsd-project-researcher`, `gsd-phase-researcher`, `gsd-domain-researcher`, `gsd-research-synthesizer`) + `gsd-assumptions-analyzer` для предпроектного исследования стека и подводных камней.
- **Готовые CLI/скил-паки извлечения веб-данных (Retrieval Layer):**
  - **`firecrawl/cli` + `firecrawl/skills`** (`npx -y firecrawl-cli@latest init --all --browser`) — поиск + рендер JS-сайтов в чистый Markdown за один вызов (-93% входных токенов против сырого HTML) + индекс научных статей Firecrawl Research Index.
  - **`tavily-ai/skills`** (`tavily-search`, `tavily-research`), **Exa MCP / `exa-search`** (нейронный поиск похожих статей/репозиториев/компаний), **`parallel-web/parallel-agent-skills`** (`parallel-deep-research` с высокой точностью provenance).

---

## 5. Сводная матрица сравнения топовых паков

| Пакет / Репозиторий | ★ GitHub (11.2026) | Контур | Скрипты в паке | Главная инженерная фишка | Импорт в `todoc skills` |
|---|---:|---|---|---|---|
| `mattpocock/skills` | 333.5k | Штурм + Ресёрч | JS lint (репо) | Обход фронта дерева решений (`grilling`), фоновый primary-source `research` | Прямой (`SKILL.md`) |
| `obra/superpowers` | 327.3k | Штурм → План | `server.cjs`, `.sh` | Сократический диалог, `Visual Companion`, `builder-check`, `<HARD-GATE>` | Уже в `demo/skills/` |
| `affaan-m/ECC` | 311.2k | Совет + Ресёрч | Python/JS/sh | `council-multi-model`, `deep-research`, `search-first` | Выборочно по папкам |
| `NousResearch/hermes-agent` | 266.3k | Ресёрч / Цитаты | `sources.py`, `search_arxiv.py` | Детерминированный реестр ссылок `url→[n]` и проверка буквальных цитат | Прямой (`skills/research/*`) |
| `garrytan/gstack` | 142.7k | Продукт-штурм | Bash hooks + bin | YC `/office-hours` (6 форсирующих вопросов) + конвейер `/autoplan` | Требует шаблон/bin обвязку |
| `addyosmani/agent-skills` | 120.6k | Идеация → Спека | `idea-refine.sh` | Быстрый дивергентно-конвергентный `idea-refine` + `doubt-driven` | Прямой (`SKILL.md`) |
| `bytedance/deer-flow` | 85.8k | GitHub + SLR Ресёрч | `github_api.py`, `arxiv_search.py` | 4-раундовый ресёрч GitHub-репозиториев с таймлайнами и confidence | Прямой (`skills/public/*`) |
| `mvanhorn/last30days-skill` | 75.6k | Живой веб/соц-ресёрч | 16 `.py`/`.sh` + SQLite | Параллельный срез Reddit/X/HN/YT/GitHub/Polymarket со скорингом engagement | Прямой (нужен Python 3.12+) |
| `gsd-build/get-shit-done` | 64.1k | Предпроектный ресёрч | `gsd-tools.cjs` | 4 параллельных ресёрчера + синтезатор + анализатор допущений | Свой формат `commands/agents` |
| `Imbad0202/academic-research-skills` | 58.7k | Академ. и глуб. ресёрч | 200+ `.py` + pytest | Триангуляция, детектор голословных тезисов, проверка ретракций, PRISMA | Тяжёлый пакет (свои `scripts/`) |
| `K-Dense-AI/scientific-agent-skills` | 58.6k | Научный штурм + Ресёрч | `.py` в каждом скиле | Скриптовая валидация гипотез, фальсифицируемости, матриц рынка и BibTeX | Прямой (эталон `SKILL.md`) |
| `bmad-code-org/BMAD-METHOD` | 55.8k | Дивергент. штурм + Recon | `brain.py`, `recon_kit.py`, `memlog.py` | 3 режима штурма (>100 идей), `party-mode`, JIT-дайджесты и `memlog` на диске | С fallback без `_bmad/` |
| `OthmanAdi/planning-with-files` | 28.2k | Память ресёрча | 22 `.sh`/`.py`/`.ps1` | Правило 2 действий: сброс находок в `findings.md` против потери контекста | Прямой (`SKILL.md + scripts`) |
| `EveryInc/compound-engineering-plugin` | 26.2k | Идеация → Штурм | `light-webserver.js`, `peer-job-runner.py` | Отсев слабых идей в `ce-ideate` до запуска `ce-brainstorm` + `ce-bakeoff` | Прямой (`skills/ce-*`) |
| `wanshuiyin/Auto-claude-code-research-in-sleep` | 19.9k | Авто-ресёрч + Отсев | Markdown + мосты | `kill-argument`, `novelty-check`, `prior-art-search`, кросс-модельный цикл | Прямой (`skills/*`) |
| `Orchestra-Research/AI-Research-SKILLs` | 14.8k | R&D-идеация | `templates/`, `references/` | 10 линз генерации исследовательских идей + когнитивные фреймворки + `rigor-reviewer` | Прямой (`21-*`, `22-*`) |
| `hyderhusainarastu/deep-research-skill` | — | Аудируемый ресёрч | `lexical_audit.py`, `check_csv.py` | Уровни верификации, правило насыщения (stop rule), лог отрицательных находок | Прямой (`SKILL.md + scripts`) |

---

## 6. Практическая рекомендация: идеальная сборка («золотая связка»)

Вместо установки сотен пересекающихся скилов (что размывает роутинг агента), оптимальный стек строится из **6 непересекающихся модулей**, закрывающих весь цикл от сырой мысли до верифицированного отчёта:

1. **Живой срез реальности и трендов:** `mvanhorn/last30days-skill` *(что реально обсуждают и используют прямо сейчас на GitHub/HN/Reddit/X)* + `github-deep-research` из `bytedance/deer-flow` *(4-раундовый разбор конкретных репозиториев-конкурентов через `github_api.py`)*.
2. **Строгий верифицируемый ресёрч и защита от галлюцинаций:** `grounded-citations` (`scripts/sources.py` из `NousResearch/hermes-agent`) + `hyderhusainarastu/deep-research-skill` *(волны поиска, saturation stop rule, фиксация отрицательных находок и `lexical_audit.py`)* + точечно `market-research-reports` / `literature-review` из `K-Dense-AI/scientific-agent-skills`.
3. **Широкая генерация и безжалостный первичный отсев идей:** `ce-ideate` (`EveryInc/compound-engineering-plugin`) или `bmad-brainstorming` (`BMAD-METHOD`) + техника `kill-argument` из `ARIS` / `libertee:pre-mortem` *(отсеять слабые варианты до траты времени на проектирование)*.
4. **Сократическая доводка выбранной концепции:** `brainstorming` из `obra/superpowers` *(уже есть в `demo/skills/process/superpowers/brainstorming`)*.
5. **Стресс-тест развилок и допущений:** `grilling` / `grill-with-docs` из `mattpocock/skills` *(проход по фронту дерева решений до нуля белых пятен)* либо последовательный `six-hats` / `council` для спорных архитектурных развилок.
6. **Защита от потери фактуры на длинных дистанциях:** паттерн `findings.md` из `OthmanAdi/planning-with-files` или нативный слой записей и типизированных отчётов `todoc` (`research-report` + `validate --all`).

---

## 7. Источники (проверено 26.11.2026)

| Категория | Источник |
|---|---|
| Рейтинги и аудиты экосистемы Agent Skills 2026 | https://www.datasumi.com/blog/best-agent-skills-claude-code-2026 · https://agentskillshub.top/best/claude-code-skills/ · https://skillselion.com/research-skills |
| Superpowers (`brainstorming` v7) | https://github.com/obra/superpowers/tree/main/skills/brainstorming · https://skillselion.com/skills/obra/superpowers/brainstorming |
| Matt Pocock Skills (`grilling`, `grill-with-docs`, `research`) | https://github.com/mattpocock/skills |
| BMAD Method v6 (`bmad-brainstorming`, `bmad-deep-recon`, `bmad-party-mode`) | https://github.com/bmad-code-org/BMAD-METHOD/tree/main/skills/core-tools |
| Compound Engineering (`ce-ideate`, `ce-brainstorm`, `ce-bakeoff`, `ce-pov`) | https://github.com/EveryInc/compound-engineering-plugin/tree/main/skills |
| Garry Tan `gstack` (`office-hours`, `autoplan`) | https://github.com/garrytan/gstack |
| Addy Osmani `agent-skills` (`idea-refine`, `interview-me`, `doubt-driven-development`) | https://github.com/addyosmani/agent-skills/tree/main/skills |
| K-Dense Scientific Agent Skills (177 скилов со скриптами) | https://github.com/K-Dense-AI/scientific-agent-skills |
| Imbad0202 Academic Research Skills (200+ скриптов верификации) | https://github.com/Imbad0202/academic-research-skills |
| ARIS (`Auto-claude-code-research-in-sleep`) | https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep |
| Orchestra Research (`AI-Research-SKILLs`) | https://github.com/Orchestra-Research/AI-Research-SKILLs |
| `last30days-skill` (мульти-платформенный ресёрч-движок) | https://github.com/mvanhorn/last30days-skill |
| Hermes Agent (`grounded-citations`, `arxiv`) | https://github.com/NousResearch/hermes-agent/tree/main/skills/research |
| ByteDance DeerFlow (`github-deep-research`, `systematic-literature-review`) | https://github.com/bytedance/deer-flow/tree/main/skills/public |
| `deep-research-skill` (`lexical_audit.py`, saturation stop rule) | https://github.com/hyderhusainarastu/deep-research-skill |
| `Deep-Research-skills` (RhinoInsight human-in-the-loop) | https://github.com/Weizhena/Deep-Research-skills |
| `planning-with-files` (`findings.md` + 22 скрипта) | https://github.com/OthmanAdi/planning-with-files |
| GSD (`get-shit-done`) | https://github.com/gsd-build/get-shit-done |
| Мульти-агентная фасилитация и советы | https://github.com/worksystems-design/libertee · https://github.com/juanallo/six-hats-skill · https://github.com/karpathy/llm-council · https://github.com/andrewvaughan/agent-council · https://smithery.ai/skills/sd0xdev/codex-brainstorm |
| Поисковая инфраструктура агентов (Firecrawl, Exa, Tavily, Parallel, Brave) | https://www.firecrawl.dev/blog/best-ai-search-engines-agents · https://guptadeepak.com/research/web-search-apis-ai-agents-2026/ · https://github.com/firecrawl/cli |
