---
id: doc:skills-engine-idea
title: "Идея: хранилище-движок скилов на todoc (skills vault + CLI-оглавление на лету)"
doc_type: idea
lang: ru
status: planned
updated: 2026-11-25
related: ["[[plan-skills-vault]]"]
---

# Идея: хранилище-движок скилов на todoc

**Статус:** запланирована (2026-11-25) — исполняющий план
[skills-vault-implementation](../plan/skills-vault-implementation.md)
(doc:plan-skills-vault): задачи 1–7 покрывают фазы 1–5 и диспетчер-скил
`todoc`; открытые вопросы закрыты в §4 плана. Ресёрч стандартов скилов
(25.11.2026): открытый стандарт Agent Skills, механики Claude Code и OpenAI
Codex, skills CLI (Vercel); дополнение — Hermes Agent и router-паттерны (§ниже).

## Суть

Единое переносимое хранилище скилов в формате открытого стандарта Agent Skills
(SKILL.md): **скил — не документ, а тип папки** (dir_type), хранилище иерархически
разбито на разделы и подразделы, и это дерево работает как меню-оглавление.
Новая CLI-команда `todoc skills tree` печатает **компактное древовидное оглавление
с описаниями прямо в stdout на лету** — агент видит каталог целиком и immediately
выбирает скилл, ничего не сохраняя во временные файлы. Чужие скилы из открытых
источников кладутся в хранилище как есть и подхватываются автоматически;
отключение — восклицательный знак в имени папки (`!имя`), без удаления.
Роутинг — одна строка-правило в AGENTS.md с готовой argv-командой.

## Проблема

1. **Скилы размазаны по инструментам.** Один и тот же скил лежит в `.claude/skills/`
   (Claude Code), `.agents/skills/` (Codex), `.cursor/skills/` (Cursor) — копиями или
   симлинками в N местах. Нет единого переносимого хранилища, версонируемого в git:
   обновил скил в одном месте — в трёх остальных протух.
2. **Каталога нет.** Чтобы узнать, какие скилы вообще есть и для чего, агент должен
   обходить папки и читать каждый SKILL.md; платформа показывает описания только своих
   скилов, и только на платформах с нативной поддержкой.
3. **Роутинг через рулесы вероятностный.** «Выбери подходящий навык из таблицы в файле»
   — инструкция в длинном контексте: агент может забыть её выполнить, а файл-оглавление
   «сохранить и потом прочитать» — лишние ходы и потерянные токены.
4. **Чужие скилы неудобно принимать.** Открытая экосистема (skills.sh, 44+ клиентов,
   тысячи готовых скилов) должна уметь «свалиться в папку» и заработать; и уметь
   выключаться без удаления, когда скил не подходит проекту.

## Принципы

1. **Скил = папка, не документ.** dir_type поверх формата открытого стандарта:
   папка скила содержит всё, что содержит типичный скил — `SKILL.md` + опциональные
   `scripts/`, `references/`, `assets/`. Никакой конверсии: чужой скил кладётся как есть.
2. **Файлы — истина, оглавление — производное.** Дерево сканируется CLI на лету
   (малые хранилища) или из пересобираемого индекса (большие) — в духе P1 конституции.
3. **Иерархия = дерево решений.** Раздел → подраздел → скил задаются структурой папок;
   агент спускается по дереву от домена к конкретному скилу.
4. **Bounded output на лету.** Оглавление печатается в stdout команды (конверт JSON
   или дерево в table-режиме), с лимитами и `truncated`; агент не сохраняет его в файл.
5. **Мьют — конвенция имени, не удаление.** `!`-префикс в имени папки исключает скил
   из дефолтного дерева и поиска; `--all` показывает его с пометкой.
6. **Валидация по стандарту.** Front matter каждого SKILL.md проверяется: коды
   `skills.*` с точными локациями — как остальная диагностика todoc.
7. **CLI-first.** Роутинг — одна императивная строка в AGENTS.md с готовым argv,
   не «прочитай файл и разберись».

## Ресёрч: стандарты и механики скилов (25.11.2026)

### Открытый стандарт Agent Skills (agentskills.io)

Формат опубликован Anthropic как открытый стандарт 18.12.2025 (сами скилы появились
в October 2025); официальный showcase — 44+ клиента, включая Claude Code, OpenAI Codex,
Cursor, Gemini CLI, GitHub Copilot, VS Code. Контракт пакета:

- **Скил = директория**, обязана содержать `SKILL.md`; опционально `scripts/`,
  `references/`, `assets/`.
- **Front matter** (YAML): обязательные `name` (≤64 символов, строчные буквы/цифры/
  дефисы, без ведущих/хвостовых/двойных дефисов, **совпадает с именем папки**) и
  `description` (≤1024 символа, «что делает + когда использовать», с ключевыми словами
  для матчинга задачи). Опциональные: `license`, `compatibility` (≤500), `metadata`
  (произвольные key-value), `allowed-tools` (экспериментальное, пре-аппрувленные тулзы).
- **Body** — Markdown-инструкции; рекомендация: <500 строк, <5000 токенов.
- **Progressive disclosure в 3 уровня**: L1 — name+description (~100 токенов на скил,
  загружены всегда); L2 — тело SKILL.md по активации; L3 — scripts/references/assets
  по мере упоминания в инструкциях.
- `.agents/skills/` в корне репо — формирующаяся кросс-тульная конвенция.

### Claude Code (референс-реализация)

Локации: personal `~/.claude/skills/<name>/SKILL.md`, project `.claude/skills/<name>/`,
nested `<dir>/.claude/skills/` (монорепо), plugin `<plugin>/skills/<name>/`
(неймспейс `plugin:skill`), enterprise managed. Расширенный front matter поверх
стандарта: `when_to_use` (доп. триггеры), `argument-hint`, `arguments`,
`disable-model-invocation` (только ручной вызов `/name`), `user-invocable`,
`allowed-tools` / `disallowed-tools` (пре-аппрув / изъятие тулз на время скила),
`model`, `effort`, `context: fork` (под-агент), `agent`, `hooks`, `paths`
(glob-паттерны ограничения авто-активации). Инвокация: `/skill-name` или авто по
description. В claude.ai/API — строже: только 6 стандартных полей.

### OpenAI Codex

Скилы «build on the open agent skills standard»; тиры загрузки: `$CWD/.agents/skills/`,
корень репо `.agents/skills/`, `~/.agents/skills/`, `/etc/codex/skills/`, bundled.
Инвокация `$skill-name`. Описания навыков Codex читает тем же progressive disclosure.

### skills CLI (Vercel, январь 2026) и skills.sh

Деф-факто пакетный менеджер экосистемы (vercel-labs/skills, MIT, ~20K+ звёзд,
75+ агентов): `npx skills add <owner/repo> [--skill name] [-a agent] [-g]`
(симлинк или копия), `npx skills find [query]` (каталог skills.sh), `npx skills list
[--json]`, `npx skills use` (запуск без установки). skills.sh — лидерборд и каталог
скил-пакетов (packs, topics, audits). OpenSpec 2.0 ставит свои скилы через этот же
пакет (`openspec init --global` → `~/.agents/skills/`).

### Сводная таблица требований (что обязан поддерживать наш сканер)

| Требование | Источник | Наша поддержка |
|---|---|---|
| Папка с SKILL.md — скил | стандарт | leaf-детект: подкаталог с SKILL.md = скил |
| `name`: regex, ≤64, = имени папки | стандарт | валидация, код `skills.name_mismatch` / `skills.bad_name` |
| `description`: ≤1024, non-empty | стандарт | валидация, код `skills.long_description` / `skills.missing_front_matter` |
| `scripts/ references/ assets/` | стандарт | подсчёт в дереве, чтение через существующий CLI |
| Опц. поля license/compatibility/metadata/allowed-tools | стандарт | парсятся, не валидируются жёстко |
| Расширенные поля Claude Code (when_to_use, paths, …) | Claude Code | игнорируются сканером, сохраняются файлом — мы не единственный читатель |
| Progressive disclosure L1–L3 | стандарт | L1 = наше дерево; L2/L3 = чтение SKILL.md и файлов |
| Мьют без удаления | наша конвенция | `!`-префикс папки (вне стандарта — помечено) |

### Дополнение ресёрча (25.11.2026, вторая волна): Hermes Agent и router-паттерны

- **Hermes Agent (Nous Research)** — ближайший референс со своим иерархическим
  форматом: скил = `~/.hermes/skills/<category>/<skill>/SKILL.md` (двухуровневая
  иерархия категорий, 310+ скилов); **4 тира доступа** — `skills_categories()`
  (разделы+счётчики) → `skills_list()` (name+description) → `skill_view(name)`
  (SKILL.md целиком) → `skill_view(name, file_path)` (один reference-файл);
  house-стандарт: описание ≤60 симв., фиксированный порядок секций When to Use →
  Procedure → Pitfalls → Verification; поля `platforms`, `prerequisites`,
  `metadata.hermes` поверх открытого стандарта; rglob + первые 4000 симв. на
  front matter; dedup по имени (локальный побеждает); Skills Hub с trust-уровнями.
  Источники: tutorsbot.com/blog/hermes-agent-skills-explained-2026,
  kenhuangus.substack.com (Chapter 12: Claude Code vs Hermes), macgpu.com
  (GEPA-гайд), marktechpost.com (/learn).
- **Router-паттерн (context economy)**: OpenAI guidance 2026-09 — «минимизируй
  метаданные, избегай перекрывающихся скилов, use a small router»; skill-router
  (chrishan17, 40+ агентов): один router-скил + подавление описаний под-скилов —
  ~400 токенов вместо десятков тысяч при 100+ скилах; Popov (500+ скилов):
  router ~100 ток. + server-side search top-3 (только метаданные) + read с
  path-confinement, entry gate + refusal floor, «context cost scales with usage,
  not catalog size»; Routed (r/LLMDevs): локальный роутер <20 ms/0 токенов,
  один инструмент вместо 20+ схем. Принято в план: диспетчер-скил `todoc` +
  `skills tree/read` как search/read с ограничением пути; витрина в платформы
  не монтируется.

## Предложение

### Хранилище: скил = тип папки, иерархия = разделы

```
skills/                        ← DATA_ROOT или корень в составе общего KB
├── coding/                    ← раздел (обычная папка, dir_type: skill)
│   ├── git/                   ← подраздел
│   │   ├── commit-message/    ← СКИЛ: SKILL.md + scripts/ + references/
│   │   ├── release/
│   │   └── !legacy-deploy/    ← замьючен: исключён из дефолтного дерева
│   └── review/
│       ├── code-review/
│       └── adr/
├── docs/
│   ├── todoc-docs/
│   └── jira-fetch/
└── process/
    └── release-flow/
```

- **dir_type `skill`** (в датасете уже есть) — семантика расширяется: папка любого
  уровня с этим типом — «скил-хранилище»; подкаталог, содержащий `SKILL.md`, — скил;
  подкаталог без SKILL.md — раздел/подраздел.
- **Совместимость**: любой скил из открытых источников (skills.sh, репозитории)
  кладётся `cp -r` или `npx skills add … --skill name` и подхватывается после
  `index rebuild` — формат тот же открытый стандарт.
- **Мьют**: префикс `!` в имени папки. `name` внутри SKILL.md остаётся валидным по
  стандарту — мьютится физическое размещение, не содержимое. `!name` исключается из
  дефолтного дерева и из `docs search`; `--all` показывает с пометкой `[!]`.
  «Почему не конфиг-файл»: имя папки видно в git-диффе и правится одной клавишей,
  без отдельного файла состояния.

### CLI: `todoc skills tree` — оглавление на лету

```bash
todoc skills tree [--root PATH] [--within SECTION] [--query Q]
                  [--all] [--format tree|json] [--limit N]
```

Table/tree-режим — то, что агент видит сразу в stdout:

```
skills/  (12 skills, 3 sections, 1 muted)
├── coding/
│   ├── git/ (3)
│   │   ├── commit-message  Пишет commit message из staged diff. Use when committing.
│   │   ├── release         Режет релиз: changelog, тег, notes по конвенции releases/*.
│   │   └── [!] legacy-deploy
│   └── review/ (2)
│       ├── code-review     Ревью дифа: безопасность, обработка ошибок, тесты.
│       └── adr             Пишет ADR из обсуждения решения.
├── docs/ (2)
│   ├── todoc-docs          Ищет и читает KB датасета через todoc CLI.
│   └── jira-fetch          Тянет задачу Jira в снимок task-snapshot.
└── process/ (1)
    └── release-flow        Проводит merge-forward релиза без конфликтов.
```

- Описание — первая строка `description` из front matter, обрезка по ширине терминала;
  дерево — не JSON: человеко- и агенто-читаемо без постобработки.
- JSON-режим (конверт): `data: {root, counts, skills: [{name, path, section,
  description, muted, refs, scripts}]}` — для программной обработки.
- `--query` — лексический фильтр по name+description; `--within coding/git` — срез
  раздела; `--limit` + `truncated` — bounded по умолчанию.
- Компаньоны: `todoc docs read` по пути SKILL.md (L2 — тело скила),
  `docs search` по содержимому скилов (SKILL.md индексируется как Markdown уже сейчас).
- Валидация: в `todoc validate` добавляются коды `skills.missing_front_matter`,
  `skills.bad_name`, `skills.name_mismatch`, `skills.long_description` — с точной
  локацией в SKILL.md и suggested_fixes в духе существующих диагностик.

### Роутинг: что прописать агенту

Текст правила в AGENTS.md (первой строкой, императивом, с готовым argv):

```markdown
Перед любой нетривиальной задачей выполни:
  todoc skills tree --root skills
Выбери подходящий скилл по описанию (имя раздела = домен задачи). Прочитай его:
  todoc docs read --root skills --path <путь из дерева>/SKILL.md
Действуй строго по инструкциям SKILL.md; файлы references/ и scripts/ — по ходу.
Подходящего скилла нет — работай без него, не выдумывай и не модифицируй чужие.
```

Для платформ с нативными скилами тот же каталог монтируется их механизмом:
симлинк `.claude/skills` → разделы хранилища или `npx skills add <ваш-репо>`
(симлинк-стратегия: апдейт хранилища течёт во все тулы). Хранилище одно,
точки монтирования — многие; наш CLI-каталог остаётся каноническим для агентов
без нативной поддержки.

### Распределение ролей с нативным progressive disclosure

| Уровень | Кто делает | Что |
|---|---|---|
| L1 discovery | платформа (нативные скилы) или наш `skills tree` | описания в контексте/в выводе |
| L2 активация | агент читает SKILL.md | тело <5000 токенов |
| L3 ресурсы | агент читает references/scripts/assets | по мере упоминания |

Наш CLI не заменяет платформу там, где она есть; он даёт L1 всем остальным и
канонический каталог с мьютами и валидацией — единый для всех тулз.

### Сценарии (WHEN/THEN)

```markdown
#### Scenario: Агент находит скилл
- **WHEN** агент получает нетривиальную задачу и выполняет skills tree
- **THEN** он видит дерево с описаниями, выбирает скилл по домену,
  читает SKILL.md и следует инструкциям — без промежуточных файлов

#### Scenario: Чужой скил подхватывается
- **WHEN** в skills/coding/review/ скопирована папка скила с SKILL.md
- **THEN** после index rebuild он виден в дереве; если front matter невалиден —
  диагностика skills.* с локацией, скил помечен [x] в дереве

#### Scenario: Мьют без удаления
- **WHEN** папка скила переименована в !legacy-deploy
- **THEN** дефолтное дерево и docs search его не показывают;
  skills tree --all показывает с пометкой [!]; содержимое не менялось
```

## План внедрения (до рабочей системы)

> Исполнение — план `plan/skills-vault-implementation.md` (doc:plan-skills-vault):
> Задачи 1–2 = Фазы 1–2, Задача 3 = Фаза 3, Задача 4 = Фаза 4, Задача 6 = Фаза 5;
> Задача 5 — диспетчер-скил `todoc` и `skills attach` (дополнение из ресёрча
> router-паттернов 25.11.2026).

- **Фаза 1 — сканер и валидация.** dir_type-семантика «папка = раздел, подкаталог
  со SKILL.md = скил»; парсер front matter (markdown-парсер уже умеет front matter);
  коды `skills.*` в валидаторе. Приёмка: чужой скил в папке → 0 или точные диагностики.
- **Фаза 2 — `skills tree` + JSON-конверт.** Дерево с описаниями, `--query/--within/
  --limit/--format`. Приёмка: демо-хранилище на 10+ скилов печатается <1 c, bounded.
- **Фаза 3 — мьют `!`.** Исключение из дефолтного дерева и поиска, `--all`.
  Приёмка: сценарий мьюта выше проходит.
- **Фаза 4 — роутинг-правило и демо-скилы.** 3–5 скилов в демо (todoc-docs,
  jira-fetch, release-flow), строка в AGENTS.md/SKILL.md. Приёмка: агент по одному
  правилу находит и исполняет скилл.
- **Фаза 5 — импорт из открытых источников.** Скрипт-обёртка: список скилов репо
  (аналог `skills add --list`) → копирование в выбранный раздел с сохранением
  front matter. Приёмка: скил с skills.sh установлен в раздел и виден в дереве.

## Открытые вопросы

- Дерево из живого скана или из индекса? Малые хранилища — живой скан (свежесть),
  большие — индекс + `index rebuild`; порог переключения?
- Причина мьюта: только `!`-имя, или рядом `MUTED.md` с пояснением (и показывать ли
  его в `--all`)?
- Кириллица в именах разделов: разделы — не скилы, regex стандарта на них не
  распространяется; но как искать по кириллическим разделам в `--query`?
- Глубина: ограничить 3 уровнями (раздел/подраздел/скил) или произвольная?
- Один vault или несколько (multi-root `--root` уже есть)? Как делить личные и
  командные скилы?
- Апдейты upstream: как трекать изменения чужих скилов (symlink-стратегия skills CLI
  vs копия + ручной refresh)?
- Конфликт имён: два скила с одинаковым `name` в разных разделах — валидация
  `skills.duplicate_name` или неймспейсы по разделу?

## Связанные документы

- [Идея документирования кодовой базы](documentation-system.md) — collector и
  task-report; скилы `jira-fetch`/`release-flow` из этого плана — её исполнители.
- [SKILL.md](../skill/SKILL.md) — сам todoc как скил (тот же формат).
- [Конституция](../plan/constitution.md) — P1 (файлы — истина), P7 (bounded context).

## Ссылки (внешние)

| Что | Ссылка |
|---|---|
| Agent Skills — официальный стандарт | https://agentskills.io |
| Спецификация SKILL.md (зеркало) | https://openagentskills.dev/docs/specification |
| Стандарт, объяснённый (поля, disclosure) | https://www.getlockstep.dev/blog/agent-skills-open-standard |
| Обзор: один SKILL.md для всех тулов, 44 клиента | https://agentscamp.com/guides/skills/agent-skills-open-standard |
| Портативность скилов (QA-разбор) | https://qaskills.sh/blog/agent-skills-open-standard-portability |
| Что такое Agent Skills (adopters, риски) | https://atlan.com/know/ai-agent/ai-agent-skills/what-are-agent-skills/ |
| Claude Code Skills — полный гайд (front matter, локации) | https://hidekazu-konishi.com/entry/claude_code_skills_complete_guide.html |
| Claude Code Skills — справочник полей | https://vanja.io/claude-code-skills-guide/ |
| Claude Code Skills — complete guide (security) | https://neuraltrust.ai/blog/claude-code-skills |
| Claude Code Skills — создание скила | https://www.mdskills.ai/learn/how-to-create-a-claude-code-skill |
| Claude Code Skills — build/fix | https://heybento.ai/guides/claude-code-skills-complete-guide |
| skills CLI (Vercel) — введение | https://vercel.com/changelog/introducing-skills-the-open-agent-skills-ecosystem |
| skills CLI — репозиторий | https://github.com/vercel-labs/skills |
| skills.sh — каталог скилов | https://skills.sh |
| Codex CLI + Vercel skills CLI (тиры .agents/skills) | https://codex.danielvaughan.com/2026/05/31/codex-cli-vercel-skills-cli-npx-skills-open-agent-skills-ecosystem/ |
| Skills.sh Review (packs, установки) | https://vibecoding.app/blog/skills-sh-review |
| skills CLI обзор (75+ агентов) | https://ai-tldr.dev/tools/skills/ |
