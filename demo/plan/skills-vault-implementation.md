---
id: doc:plan-skills-vault
title: "Хранилище-движок скилов: skills tree, валидация, мьют, импорт, диспетчер (план)"
doc_type: plan
lang: ru
status: active
tags: [skills, agent-skills, cli, validation, import, routing, dispatcher]
updated: 2026-11-25
related: ["[[skills-engine]]", "[[documentation-system]]", "[[constitution]]"]
---

# Хранилище-движок скилов: skills tree, валидация, мьют, импорт, диспетчер (план) — план реализации

> **Исполнителю (агенту):** план самодостаточен — читай его, а не историю сессии.
> Работай по задачам сверху вниз; шаги отмечаются чекбоксами (`- [ ]`) в том же
> коммите, который делает шаг. Начинай всегда с первого неотмеченного.

**Цель:** единое переносимое хранилище скилов в датасете по открытому стандарту
Agent Skills с CLI-оглавлением `todoc skills tree` на лету, валидацией `skills.*`,
мьютом без удаления, офлайн-импортом чужих скилов и **диспетчер-скилом `todoc`** —
одной точкой входа для любого агента (точное исполнение, экономия контекста).
**Спека:** [идея skills-engine](../ideas/skills-engine.md) (doc:skills-engine-idea);
план закрывает все её открытые вопросы — решения в §4.
**Стек:** Python 3.11, click (CLI), существующий markdown-парсер (front matter),
pytest; новых зависимостей нет.

## 1. Критерии успеха

1. `todoc skills tree --root demo` печатает дерево демо-хранилища
   (**11 скилов, 3 раздела, 1 замьючен**) с описаниями **за < 1 c**, bounded
   (`--limit` по умолчанию 100, `truncated` в JSON-конверте).
2. Чужой скил (скопированная папка со SKILL.md) виден в дереве сразу после
   копирования; SKILL.md с невалидным front matter даёт точные коды `skills.*`
   с локацией (файл:строка) и suggested_fix, а не молчание.
3. Мьют работает без удаления: `!name` отсутствует в дефолтном дереве и в
   `docs search`; `skills tree --all` показывает с пометкой `[!]`.
4. **Диспетчер**: `todoc skills attach --to <каталог платформы> --root demo`
   кладёт один скил `todoc` (все прочие скилы хранилища в платформу НЕ
   монтируются); сценарий «tree → read → исполнить» проходит по телу диспетчера
   без ручного обхода папок; L1-контекст платформы несёт ровно один скил.
5. `validate --root demo --all` — 0 диагностик на демо с заполненным
   хранилищем; pytest зелёный (988 + новые), coverage 100% на новом коде.

## 2. Вне скоупа

- **Трекинг апстрима чужих скилов** (diff/refresh при обновлении источника) —
  копия импортируется как есть; трекинг — вручную через git-историю.
- **Сетевые операции в движке.** `skills import` принимает только локальные
  пути (уже склонированный репо / скачанная папка); скачивание — вне движка.
- **Плагинная обвязка пакетов** (hooks/, commands/, agents/, index.js,
  package.json, gemini-extension.json и т.п. манифесты платформ) — НЕ
  копируется и не исполняется: `skills import` переносит только папки со
  SKILL.md (формат открытого стандарта); проверено на реальном пакете
  obra/superpowers (15 скилов + 9 файлов обвязки) — см. §8.
- **Well-known-реестры** (`/.well-known/skills/index.json`, источник Hermes Hub)
  и любые реестровые протоколы — будущая фаза, здесь только локальные пути.
- **Самоэволюция скилов** (GEPA/DSPy-оптимизация описаний и тел, /learn
  Hermes) — не автоматизируем; только ручное улучшение.
- **Platform-гейтинг** (`platforms:` поле Hermes, скрытие скила по ОС) —
  парсится как unknown-поле, не исполняется.
- **Симлинк-монтаж всего vault в платформы** — анти-паттерн по ресёрчу
  (контекст); монтируется только диспетчер (§4). Симлинк-механика платформ —
  их собственная, документируется одной строкой.
- **Неймспейсы по разделам** для конфликта имён — вместо них глобальный
  `skills.duplicate_name` (решение в §4).
- **Личный vault** (`skills/personal/` вне git) — фиксируется подход, не код.
- **Индекс-режим для больших хранилищ** (>500 скилов) — живой скан всегда;
  порог — предупреждение в выводе, не реализация индекса.
- **Причина мьюта в отдельном файле** (`MUTED.md`) — только `!`-имя (§4).
- **Исполнение scripts/** скилов — движок только показывает их наличие;
  запуск остаётся за агентом/платформой.

## 3. Глобальные ограничения

- **P1 (конституция):** файлы — истина; дерево — производное, сканируется на
  лету, никакого постоянного индекса скилов.
- **P7 (конституция):** bounded context — каждый вывод ограничен
  (`--limit` дефолт 100, `--depth` дефолт 6, `truncated`-флаг в JSON,
  `--budget` в `skills read`).
- **Стандарт Agent Skills:** `name` обязателен — `^[a-z0-9]+(-[a-z0-9]+)*$`,
  ≤64 символов, совпадает с именем папки; `description` — непустой, ≤1024.
  Опциональные поля (`license`, `compatibility`, `metadata`, `allowed-tools`,
  расширенные поля Claude Code/Hermes) парсятся, но жёстко не валидируются —
  unknown-поля стандартными читателями игнорируются (подтверждено практикой
  Hermes Agent и Claude Code).
- **Только диспетчер монтируется в платформы.** Витрина `skills/` никогда не
  монтируется в каталоги скилов платформ (`.claude/skills/`, `.agents/skills/`,
  …) — иначе L1-описания всех скилов съедают контекст (анти-паттерн по
  ресёрчу); в платформе живёт ровно одна папка `todoc/`.
- **Body-конвенция хранилища** (рекомендация по house-стандарту Hermes, не
  валидация): порядок секций When to Use → Procedure → Pitfalls → Verification;
  цель описания — одна строка ≤120 символов (граница валидации — стандартные
  1024); «WHAT + WHEN + NOT-WHEN» в описании (паттерн skill-router).
- **Установка чужого скила — два пути, оба без сети:** (а) одной командой
  `todoc skills import --src <локальная папка или репо> --into <раздел>`
  (копирует + валидирует + отчёт); (б) ручным копированием папки в vault +
  одной командой `todoc validate --root demo --all` (или `skills tree` —
  live-скан подхватывает сразу). Никаких манифестов/регистраций не требуется.
- **Без сети:** ни одна команда не делает HTTP/git-запросов.
- **Coverage 100%** на новых модулях и ветках кода; pytest после каждой задачи.
- **Конвенция именования** (`notes/agent-contract.md` → «Именование документов»):
  русский заголовок — в `title`/H1, имена файлов и папок — латиница/kebab;
  исключения: `!`-префикс мьюта (конвенция системы, §4) и имя `todoc` у
  диспетчера (требование стандарта name=папка).
- **`related` во front matter — только wikilink-форма** (план doc-tags):
  `related: ["[[…]]"]`; записи — с `relations` на существующие record_id.
- **Команды движка, не ручные правки:** изменения датасета — через
  `docs new`/`docs edit`/`records create` (тело нового длинного md — напрямую,
  скелет и проверки — через CLI, как зафиксировано в AGENTS.md §«Именование»).
- **CLI-неймспейс:** новая группа `skills` (`@cli.group()`, cli.py:273 — образец
  группы `index`); `docs tree` (cli.py:1041) занят деревом секций документа;
  `docs read` принимает только `--id` (cli.py:952), а не `--path` — поэтому
  чтение тела скила идёт через новую команду `skills read`.
- **House-стиль CLI:** режимы — `--output json|table` (не `--format`; образец
  `docs tree`, cli.py:1041-1043), глубина — `--max-depth`; вывод — через
  `_emit_ok` (cli.py:46, поле конверта `next_actions` с argv+purpose), ошибки —
  `_emit_error` (cli.py:1511) с `TodocError` (тесты: паттерн
  `tests/cli/test_cli.py` — `_run` + `_json`).

## 4. Архитектура и файловая карта

**Подход.** Новый модуль `src/todoc/application/skills.py` — чистый сканер:
обход каталога vault (по умолчанию `<root>/skills/`), leaf-детект «подкаталог
с SKILL.md = скил», парсинг front matter существующим парсером, сбор
`SkillInfo` и диагностики `skills.*`. CLI-группа `skills` (tree, read, import,
attach) — тонкая обёртка над сканером; `validate` вызывает `validate_skills`
и мержит диагностики в общий поток. Мьют — фильтр по сегменту пути `!…` в
сканере и в `docs search` (пост-фильтр по пути в search.py).

**Границы ответственности (концепция `.research`-доков, не нарушается):** CLI —
детерминированный исполнитель, агент — вероятностный планировщик
(mcp-cli-agents-research.md:62 «контракт между вероятностным планировщиком и
детерминированным исполнителем»). Мысительные процессы движку НЕ переносим:
выбор скила, аудит чужого кода, интерпретация результата — агенту; вывод любой
команды — недоверенные данные для агента (mcp-cli-agents-research.md:27) —
потому отчёты import/attach несут `audit_note`/диагностики, а не вердикты.
Скил — процедурная память ДЛЯ агента, не логика в CLI: движок никогда не
решает, какой скил выбрать, и scripts/ не исполняет; инструкции SKILL.md сами
по себе не гарантируют исполнения (comparative-audit.md:19) — гарантию даёт
детерминированная команда (tree/read). `init` остаётся «не устанавливает
Skill и не перемещает данные» (engineering-plan.md:859): `skills attach` —
отдельная явная команда с явным `--to` вне датасета, не часть init.

### Диспетчер-скил `todoc` — одна точка входа для любого агента

**Мотив (ресёрч 25.11.2026, вторая волна):**

| Источник | Вывод → принято в план |
|---|---|
| Anthropic engineering «Equipping agents…» | L1-описание = триггер; scripts выполняются без загрузки кода; аудит чужих скилов перед использованием → офлайн-импорт + предупреждение в отчёте |
| OpenAI guidance 2026-09 (фиксация в Rill #71) | «минимизируй метаданные, избегай перекрывающихся скилов, **use a small router**» → один диспетчер-скил |
| skill-router (chrishan17, GitHub; 40+ агентов) | router-скил + подавление описаний под-скилов: ~400 ток. вместо десятков тысяч при 100+ скилах → в платформу монтируется только `todoc/`, vault — никогда |
| Popov «500+ skills» (medium) | router ~100 ток. + server-side search (top-3, только метаданные) + read с path-confinement; entry gate + refusal floor; «context cost scales with usage, not catalog size» → `skills tree --query/--limit` + `skills read` (путь только внутри vault) |
| Routed (bshea-1, r/LLMDevs) | локальный роутер <20 ms, 0 токенов, один инструмент вместо 20+ схем → CLI-оглавление на лету, без индекса |
| **Hermes Agent** (Nous Research; tutorsbot, kenhuangus, macgpu, marktechpost) | свой иерархический формат: `<category>/<skill>/SKILL.md`; **4 тира доступа** (категории → name+description → SKILL.md → один reference-файл); house-стандарт: описание ≤60 симв., секции When to Use → Procedure → Pitfalls → Verification; unknown-поля fm игнорируются; dedup по имени → tier-таблица ниже, body-конвенция в §3 |
| kalinga (modular skill system) | реестр асимметричен: роутер видит всё, агент — name+description → наш агент всегда читает через tree/read, никогда не «весь каталог» |

**Механика.** Движок поставляет пакетный скил `todoc` (`src/todoc/data/
agent-skill/todoc/SKILL.md`); команда `todoc skills attach --to DIR --root
DATA_ROOT` копирует папку `todoc/` в платформенный каталог (`.claude/skills/`,
`.agents/skills/`, `.cursor/skills/` — любой из 44+ клиентов стандарта),
подставляя root датасета в тело. Подключение к любому агенту — двумя
взаимодополняющими способами: (а) нативно — скопированная/attach-нутая папка
`todoc/` подхватывается механикой скилов платформы без всяких настроек;
(б) строкой в AGENTS.md/правилах — для платформ без нативной поддержки (§5,
Задача 4, шаг 3). Витрина не монтируется: в контексте платформы ровно один
L1-скил (~100 токенов) вместо N; описания под-скилов тратят 0 токенов до
момента выбора, тело загружается ровно одно. Выбор — по детерминированному
CLI-выводу, не по вероятностному матчингу описаний (уclaim Anthropic/Rill:
«guidance в промптах не гарантирует исполнения» — здесь гарантия = команда).

**Tier-таблица (Hermes ↔ todoc):**

| Тир | Hermes Agent | todoc |
|---|---|---|
| 0 | `skills_categories()` — разделы + счётчики | `skills tree --depth 1` |
| 1 | `skills_list()` — name + description | `skills tree` (bounded) |
| 2 | `skill_view(name)` — SKILL.md целиком | `skills read --path <скил>` |
| 3 | `skill_view(name, file_path)` — один файл | `docs read`/cat по references/ scripts/ |

**Entry gate + refusal floor** в теле диспетчера (паттерн Popov): активация —
только для нетривиальных задач; `tree` не дал совпадения → работать без скила,
не выдумывать; не более одного тела SKILL.md на решение; повторный выбор —
только через tree. Body диспетчера — по house-конвенции §3.

**Решения открытых вопросов идеи (закрыты здесь):**

| Вопрос | Решение |
|---|---|
| Живой скан vs индекс | Всегда живой скан (P1, размеры ≤ сотен скилов); при `len(skills) > 500` — warning-строка в выводе, индекс не строим |
| Причина мьюта | Только `!`-имя папки; пояснение — не файла, а git-история; `--all` показывает `[!]` без причины |
| Кириллица в разделах | Разделы — обычные папки, regex стандарта на них НЕ распространяется; `--query` — lowercase-подстрока по name+description+пути, кириллица работает |
| Глубина дерева | Произвольная вложенность разделов, скил на любой глубине; печатается до `--depth` (дефолт 6) |
| Один vault или несколько | `--vault PATH` (относительно DATA_ROOT, дефолт `skills`) на каждый вызов; личные/командные — поддеревья, комбинируются вызовами |
| Апдейты апстрима | Вне скоупа (копия; git-история — источник правды) |
| Конфликт имён | `skills.duplicate_name` = **error** глобально по vault; неймспейсов нет (Hermes делает тихий dedup «локальный побеждает» — для курируемого vault строже: ошибка) |
| name_mismatch у мьютнутых | Эффективное имя папки = `folder.lstrip("!")`; сравнение по нему |

**Коды диагностики** (в `validate` и `skills import`, локация — файл:строка,
suggested_fix в духе существующих): `skills.missing_front_matter` (error),
`skills.bad_name` (error), `skills.name_mismatch` (error),
`skills.long_description` (error, >1024), `skills.empty_description` (error),
`skills.duplicate_name` (error), `skills.path_exists` (import, no-overwrite),
`skills.not_found` (read, путь вне vault/несуществующий). Мьют-папка
валидируется по содержимому как обычная (стандарт не нарушается).

**Карта файлов:**

| Файл | Действие | За что отвечает |
|---|---|---|
| `src/todoc/application/skills.py` | Create | `SkillInfo`, `scan_skills`, `validate_skills`, `effective_name`, копирование/adopt для import |
| `src/todoc/cli.py` | Modify (группа `skills` рядом с index:273) | команды `tree`, `read`, `attach`, `import` |
| `src/todoc/application/validator.py` | Modify (`validate_dataset`:278) | вызов `validate_skills` для каждого vault, мерж диагностик |
| `src/todoc/application/search.py` | Modify (пост-фильтр рядом с :146-148) | исключение `!`-сегментов из результатов `docs search` |
| `src/todoc/data/agent-skill/todoc/SKILL.md` | Create | диспетчер-скил: entry gate, `{ROOT}`-плейсхолдер, tier-инструкции |
| `pyproject.toml` | Modify | `[tool.setuptools.package-data]` — packages.find без package-data НЕ пакует SKILL.md в wheel; чтение через `importlib.resources.files("todoc")` |
| `demo/.todoc/rules/document-rules.json` | Modify | правило `vault-skills-glob` (priority 60) + fm-правило `agent-skill` (priority 200) |
| `demo/.todoc/doc_types/agent-skill/type.json` | Create (условное, см. Задача 1) | doc_type БЕЗ required_sections для чужих SKILL.md |
| `demo/skills/**` | Create | демо-хранилище: **11 скилов**, 3 раздела, 1 мьют, references/ |
| `SKILL.md`, `demo/notes/agent-contract.md`, `AGENTS.md` | Modify | роутинг-правило (канон в системе, AGENTS.md — указатель) |
| `README.md`, `demo/HOME.md` | Modify | раздел «Скилы» (attach/dispatcher, 2 пути установки), линия карты, счётчики |
| `tests/unit/test_skills_scan.py` | Test | сканер: детект, sections, muted, effective_name |
| `tests/unit/test_validator_skills.py` | Test | все коды `skills.*`, локации, suggested_fix |
| `tests/cli/test_cli_skills_tree.py` | Test | tree/read/json, --query/--within/--limit/--depth/--all, <1 c |
| `tests/cli/test_cli_skills_attach.py` | Test | attach: копия, {ROOT}, no-overwrite, --force |
| `tests/cli/test_cli_skills_import.py` | Test | импорт/adopt из tmp-репо, no-overwrite, отчёт |

## 5. Задачи

### Задача 1: сканер и валидация `skills.*`

**Файлы:**
- Create: `src/todoc/application/skills.py`
- Modify: `src/todoc/application/validator.py:278` (`validate_dataset`)
- Modify: `demo/.todoc/rules/document-rules.json` (+2 правила)
- Create (условное): `demo/.todoc/doc_types/agent-skill/type.json`
- Test: `tests/unit/test_skills_scan.py`, `tests/unit/test_validator_skills.py`

**Интерфейсы:**
- Consumes: парсер front matter из существующего markdown-модуля движка.
- Produces: `SkillInfo(name, path, section, description, muted, refs, scripts, assets)`;
  `scan_skills(vault_root: Path) -> tuple[list[SkillInfo], list[dict]]`;
  `validate_skills(vault_root: Path, skills: list[SkillInfo]) -> list[dict]`
  (диагностики — словари того же shape, что отдаёт `validate_dataset`);
  `effective_name(folder: str) -> str` (= `folder.lstrip("!")`).

- [x] **Шаг 1: падающий тест сканера** (fixtures — tmp_path, не демо)

```python
# tests/unit/test_skills_scan.py
from pathlib import Path
from todoc.application.skills import scan_skills, effective_name

def _skill(root: Path, rel: str, name: str, desc: str = "Описание скила") -> None:
    d = root / "skills" / rel
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\n\n# {name}\n", encoding="utf-8")

def test_scan_detects_skill_and_sections(tmp_path):
    _skill(tmp_path, "coding/git/commit-message", "commit-message")
    _skill(tmp_path, "coding/git/!legacy-deploy", "legacy-deploy")
    (tmp_path / "skills/coding/git/release").mkdir(parents=True)  # раздел — не скил
    skills, diags = scan_skills(tmp_path / "skills")
    assert [s.name for s in skills] == ["commit-message", "legacy-deploy"]
    assert [s.section for s in skills] == ["coding/git", "coding/git"]
    assert [s.muted for s in skills] == [False, True]
    assert effective_name("!legacy-deploy") == "legacy-deploy"
    assert diags == []
```

- [x] **Шаг 2: убедиться, что тест падает**

Run: `.venv/bin/python -m pytest tests/unit/test_skills_scan.py -v`
Expected: FAIL — `ModuleNotFoundError: todoc.application.skills`

- [x] **Шаг 3: реализовать `skills.py`** — сигнатуры из Produces выше; leaf-детект:
  каталог содержит `SKILL.md` → скил, иначе — раздел; `section` = относительный
  путь папки-родителя; счётчики `refs/scripts/assets` — len() по подкаталогам;
  front matter — существующим парсером; ошибки парсинга → диагностика
  `skills.missing_front_matter` (не исключение).

- [x] **Шаг 4: тест валидатора кодов**

```python
# tests/unit/test_validator_skills.py
from todoc.application.skills import scan_skills, validate_skills

def _skill(root, rel, name, desc="Описание скила"):
    d = root / "skills" / rel
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\n\n# {name}\n", encoding="utf-8")

def test_all_skill_codes(tmp_path):
    _skill(tmp_path, "coding/a", "a", "x" * 1100)            # long_description
    b = tmp_path / "skills/coding/b"                          # bad_name + name_mismatch
    b.mkdir(parents=True)
    (b / "SKILL.md").write_text("---\nname: Wrong_Name\ndescription: ok\n---\n", encoding="utf-8")
    _skill(tmp_path, "coding/silent", "silent", "")           # empty_description
    _skill(tmp_path, "coding/p/c", "c", "первый")             # duplicate_name (две папки,
    _skill(tmp_path, "coding/q/c", "c", "второй")             # одно имя)
    skills, diags = scan_skills(tmp_path / "skills")
    codes = {d["code"] for d in diags + validate_skills(tmp_path / "skills", skills)}
    assert {"skills.long_description", "skills.bad_name", "skills.name_mismatch",
            "skills.empty_description", "skills.duplicate_name"} <= codes
    loc = [d for d in diags if d["code"] == "skills.bad_name"][0]
    assert loc["path"].endswith("coding/b/SKILL.md") and "line" in loc
    assert loc.get("suggested_fix")
```

- [x] **Шаг 5: убедиться, что падает; реализовать `validate_skills`** — правила
  §3/§4 (regex `^[a-z0-9]+(-[a-z0-9]+)*$`, ≤64; description непустой ≤1024;
  name == effective_name(папка); глобальный дедуп name по vault; мьют-папка
  валидируется как обычная).

- [x] **Шаг 6: интеграция в `validate`** — в `validate_dataset` (validator.py:278):
  для каждого root — vault `<root>/skills` (если существует) →
  `validate_skills`; мерж в общий список диагностик. Тест: vault с плохим
  скилом → `validate --all` отдаёт `skills.*`; без vault — ноль новых диагностик.

- [x] **Шаг 7: правила doc_type и doc_type `agent-skill`** — условно: если
  `demo/.todoc/doc_types/agent-skill/type.json` уже существует (softdoc-план,
  Задача 6) — НЕ создавать, только правила. Иначе создать минимальный type.json
  (копия структуры соседнего doc_type, `required_sections` отсутствует —
  чужой SKILL.md не обязан иметь секции движка; проба-обоснование: SKILL.md без
  секций против doc_type `skill` с required_sections даёт
  5×`markdown.section.missing` — проверено аудитом 25.11.2026). Два правила в
  `document-rules.json` — glob-правило обязательно, потому что чужие SKILL.md
  не декларируют doc_type (fm-матч их не поймает — BUG-001-семантика):

```json
{"id": "vault-skills-glob",
 "match": {"kind": "file", "glob": "skills/**/SKILL.md"},
 "assign": {"doc_type": "agent-skill"}, "priority": 60}
```

```json
{"id": "fm-agent-skill",
 "match": {"kind": "file", "front_matter": {"doc_type": "agent-skill"}},
 "assign": {"doc_type": "agent-skill"}, "priority": 200}
```

- [x] **Шаг 8: полный прогон и коммит**

Run: `.venv/bin/python -m pytest tests/unit/test_skills_scan.py tests/unit/test_validator_skills.py -v && .venv/bin/todoc validate --root demo --all`
Expected: PASS; 0 диагностик (vault `demo/skills` ещё не создан — шаг игнорируется)

```bash
git add src/todoc/application/skills.py src/todoc/application/validator.py tests/unit/test_skills_scan.py tests/unit/test_validator_skills.py demo/.todoc/rules/document-rules.json demo/.todoc/doc_types/agent-skill
git commit -m "feat(skills): сканер хранилища скилов + валидация skills.* + правила agent-skill"
```

### Задача 2: CLI `todoc skills tree` + `todoc skills read`

**Файлы:**
- Modify: `src/todoc/cli.py` (новая группа `skills` рядом с группой `index`, cli.py:273)
- Test: `tests/cli/test_cli_skills_tree.py`

**Интерфейсы:**
- Consumes: `scan_skills`, `SkillInfo` (Задача 1).
- Produces: `todoc skills tree --root PATH [--vault skills] [--within SECTION]
  [--query Q] [--all] [--limit N] [--max-depth N] [--output json|table]`.
  JSON-конверт (через `_emit_ok`): `data: {vault, counts: {skills, sections,
  muted}, skills: [{name, path, section, description, muted, refs, scripts,
  assets}], truncated: bool}`. Table-режим — ASCII-дерево как в образце идеи
  (описание = первая строка description, обрезка по ширине, `[!]`-пометка,
  счётчики на разделах); `--max-depth` дефолт 6 (у `docs tree` — 3).
- Produces: `todoc skills read --root PATH --path P [--vault skills]
  [--line-range A-B] [--budget N] [--output json|markdown]` — P относительно
  root: путь к папке скила или к её SKILL.md (принимаются обе формы; с/без
  префикса `skills/`); путь резолвится ТОЛЬКО внутри vault (path-confinement,
  паттерн Popov); `--budget` ограничивает длину содержимого (приложение
  BUG-005 к новой команде — бюджет здесь честный). JSON: `data: {path, name,
  description, muted, content, truncated}`. Ошибка вне vault/несуществующий →
  `skills.not_found` + suggested путь.

- [x] **Шаг 1: падающие CLI-тесты** (CliRunner, fixtures — tmp_path с 4 скилами)

```python
# tests/cli/test_cli_skills_tree.py — house-паттерн tests/cli/test_cli.py
import json
from pathlib import Path

from click.testing import CliRunner

from todoc.cli import cli
from todoc.errors import TodocError


def _skill(root: Path, rel: str, name: str, desc: str = "Описание скила") -> None:
    d = root / "skills" / rel
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\n\n# {name}\n", encoding="utf-8")


def _vault(root: Path) -> None:
    _skill(root, "coding/git/commit-message", "commit-message", "Пишет commit message.")
    _skill(root, "coding/review/adr", "adr", "Пишет ADR: контекст, решение, последствия.")
    _skill(root, "docs/jira-fetch", "jira-fetch", "Тянет задачу Jira в снимок.")
    _skill(root, "coding/git/!legacy-deploy", "legacy-deploy", "Мьютнутый: деплой legacy.")
    _skill(root, "docs/note-search", "note-search", "Ищет заметки по кириллическому запросу.")


def _run(runner, args):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


def _json(result):
    return json.loads(result.output)


def test_tree_json_bounded(tmp_path):
    runner = CliRunner()
    _vault(tmp_path)
    d = _json(_run(runner, ["skills", "tree", "--root", str(tmp_path), "--output", "json"]))["data"]
    assert d["counts"]["skills"] == 5 and d["counts"]["muted"] == 1
    assert d["truncated"] is False
    assert all("description" in s for s in d["skills"])


def test_tree_table_query_within_all(tmp_path):
    runner = CliRunner()
    _vault(tmp_path)
    t = _run(runner, ["skills", "tree", "--root", str(tmp_path), "--output", "table"])
    assert "commit-message" in t.output and "[!]" not in t.output  # мьют скрыт
    q = _run(runner, ["skills", "tree", "--root", str(tmp_path), "--query", "commit"])
    assert "commit-message" in q.output and "jira-fetch" not in q.output
    w = _run(runner, ["skills", "tree", "--root", str(tmp_path), "--within", "coding"])
    assert "jira-fetch" not in w.output
    cyr = _run(runner, ["skills", "tree", "--root", str(tmp_path), "--query", "кириллическ"])
    assert "note-search" in cyr.output               # кириллица в --query работает (§4, §7)
    a = _run(runner, ["skills", "tree", "--root", str(tmp_path), "--all"])
    assert "[!]" in a.output and "legacy-deploy" in a.output
    d1 = _run(runner, ["skills", "tree", "--root", str(tmp_path), "--max-depth", "1"])
    assert "commit-message" not in d1.output         # глубина ограничивает выдачу


def test_read_by_dir_and_file(tmp_path):
    runner = CliRunner()
    _vault(tmp_path)
    d = _json(_run(runner, ["skills", "read", "--root", str(tmp_path), "--path", "coding/review/adr"]))["data"]
    assert d["name"] == "adr" and "# adr" in d["content"]
    d2 = _json(_run(runner, ["skills", "read", "--root", str(tmp_path),
                             "--path", "skills/docs/jira-fetch/SKILL.md"]))["data"]
    assert d2["name"] == "jira-fetch"
    bad = _run(runner, ["skills", "read", "--root", str(tmp_path), "--path", "../secrets.md"])
    assert bad.exit_code != 0 and "skills.not_found" in bad.output
```

- [x] **Шаг 2: убедиться, что падает** (`skills` — нет такой команды)
- [x] **Шаг 3: реализовать группу и команды** — thin wrapper: scan → фильтры
  (`--query` lowercase-подстрока по name+description+пути; `--within` — префикс
  section; мьют: исключить из выдачи без `--all`) → сортировка по пути →
  `--limit`/`--max-depth`/truncated → `--output` (table = ASCII-дерево, json =
  `_emit_ok`; ошибки — `_emit_error`/`TodocError`). Warning при
  `len(skills) > 500`. `read` — через сканер: найти SkillInfo по пути,
  прочитать файл, применить budget.
- [x] **Шаг 4: тесты проходят** + ограничение времени: дерево из 50 скилов
  в tmp_path печатается < 1 c (`time.monotonic()` в тесте, порог 1.0 с).
- [x] **Шаг 5: коммит**

```bash
git add src/todoc/cli.py tests/cli/test_cli_skills_tree.py
git commit -m "feat(skills): todoc skills tree + skills read — оглавление и чтение скила на лету (bounded, path-confinement)"
```

### Задача 3: мьют в `docs search`

**Файлы:**
- Modify: `src/todoc/application/search.py` (пост-фильтр рядом с :146-148)
- Test: `tests/unit/test_search_muted.py`

**Интерфейсы:**
- Consumes: существующий `docs search` (search.py).
- Produces: результаты `docs search` не содержат путей с сегментом `!…`;
  флаг/параметр не добавляется (мьют — свойство хранилища, не запроса).

- [x] **Шаг 1: падающий тест** — в tmp-датасете скил `!legacy-deploy/SKILL.md`
  со словом «deploy» в теле; после `index rebuild` `docs search deploy` НЕ
  возвращает этот путь; обычный скил с тем же словом — возвращает.
- [x] **Шаг 2: убедиться, что падает** (сейчас путь находится)
- [x] **Шаг 3: реализовать** — пост-фильтр по пути в выдаче поиска:
  `any(part.startswith("!") for part in Path(p).parts) → exclude`.
- [x] **Шаг 4: проходят все поисковые тесты** (старые не сломались —
  кириллические имена legacy не содержат `!`).
- [x] **Шаг 5: коммит**

```bash
git add src/todoc/application/search.py tests/
git commit -m "feat(skills): мьют !-папки исключён из docs search"
```

### Задача 4: демо-хранилище (11 скилов) и роутинг-правило

**Файлы:**
- Create: `demo/skills/coding/git/commit-message/SKILL.md`,
  `demo/skills/coding/git/release/SKILL.md`,
  `demo/skills/coding/git/!legacy-deploy/SKILL.md`,
  `demo/skills/coding/review/code-review/SKILL.md`,
  `demo/skills/coding/review/adr/SKILL.md`,
  `demo/skills/coding/review/security-review/SKILL.md`,
  `demo/skills/docs/todoc-docs/SKILL.md` + `references/query-cheatsheet.md`,
  `demo/skills/docs/jira-fetch/SKILL.md`,
  `demo/skills/process/release-flow/SKILL.md`,
  `demo/skills/process/incident-postmortem/SKILL.md`,
  `demo/skills/coding/env/package-install/SKILL.md`
- Modify: `SKILL.md` (движковый, 1:1 строка), `demo/notes/agent-contract.md`
  (новый раздел), `AGENTS.md` (указатель)
- Test: E2E-сценарий — руками по приёмке ниже; тесты не требуются

**Интерфейсы:**
- Consumes: `skills tree`/`skills read` (Задача 2), конвенция именования.
- Produces: работающий роутинг: одна императивная строка с готовым argv.

- [x] **Шаг 1: создать 10 SKILL.md** — front matter в ОДНОМ YAML-блоке
  (образец структуры — `demo/skill/SKILL.md`): todoc-поля `id: doc:skill-<name>`,
  `title` (русский — конвенция именования), `doc_type: agent-skill` (явно →
  работает fm-правило 200; glob-правило 60 — страховка для чужих без fm),
  `lang: ru`, `updated: <дата>` + стандартные `name` (латиница, = имени папки;
  у `!legacy-deploy` name = `legacy-deploy`) и `description` — лишние для
  платформ поля они игнорируют (§3, ресёрч Hermes/Claude Code); body 20–60
  строк реальных
  инструкций по body-конвенции §3 (When to Use → Procedure → Pitfalls →
  Verification), не заглушки: commit-message — из staged diff; adr — из
  обсуждения; todoc-docs — поиск KB через CLI с argv-примерами; jira-fetch —
  снимок задачи в notes; release-flow — merge-forward; code-review — чеклист;
  security-review — аудит зависимостей/секретов; incident-postmortem —
  разбор инцидента по шаблону; package-install — установка CLI-пакетов в
  систему по конвенции проекта (мотив — наш реальный инцидент: глобальный pip
  заблокирован PEP 668 → Python-пакеты только в .venv; Node — npm/npx;
  проверка `command -v` + `--version`; запрет sudo и исполнения недоверенных
  install-скриптов; примеры ставимых тулов — playwright-cli и т.п.). Это скил
  ДЛЯ агента (процедурная память), не функция CLI — граница §4. У `todoc-docs` — `references/query-cheatsheet.md`
  (10+ строк). Русский H1 в теле, `name` латиницей — конвенция. Один скил несёт
  расширенное поле Claude Code (`when_to_use`) — тест совместимости «парсится,
  не ломается».
- [x] **Шаг 2: сквозная проверка** — `todoc skills tree --root demo` печатает
  11 скилов/3 раздела, `[!]` без `--all` не видно, `--all` видно; `todoc validate
  --root demo --all` — 0 диагностик (в т.ч. `skills.*` и `markdown.*` на
  SKILL.md); `docs search "commit message"` находит `commit-message`,
  но НЕ `!legacy-deploy` (после `index rebuild`).
- [x] **Шаг 3: роутинг-правило** — канон в системе: `demo/notes/agent-contract.md`
  новый раздел «Скилы: хранилище, диспетчер, мьют, импорт» (правило ниже +
  два способа подключения + ссылки); строка-правило в `SKILL.md` движка (1:1
  через `docs edit`); указатель в `AGENTS.md` (временный файл — только
  указатель, не канон). Для платформ без нативных скилов — эта строка и есть
  подключение движка:

```markdown
Перед любой нетривиальной задачей выполни:
  todoc skills tree --root demo
Выбери скилл по описанию (раздел = домен). Прочитай тело:
  todoc skills read --root demo --path <путь из дерева>
Действуй по инструкциям SKILL.md; references/ и scripts/ — по ходу.
Подходящего нет — работай без него; чужие скилы не модифицируй.
```

- [x] **Шаг 4: E2E-приёмка** — по правилу: tree → выбрать `todoc-docs` →
  `skills read` → выполнить его инструкцию (найти ответ в KB через CLI) — без
  промежуточных файлов и без ручного обхода папок.
- [x] **Шаг 5: коммит**

```bash
git add demo/skills SKILL.md demo/notes/agent-contract.md AGENTS.md
git commit -m "feat(skills-demo): демо-хранилище 11 скилов + роутинг-правило в агентских носителях"
```

### Задача 5: диспетчер-скил `todoc` и команда `skills attach`

**Файлы:**
- Create: `src/todoc/data/agent-skill/todoc/SKILL.md`
- Modify: `src/todoc/cli.py` (команда в группе `skills`)
- Modify: `pyproject.toml` (если data не пакетируется — проверить
  `importlib.resources` из установленного wheel)
- Test: `tests/cli/test_cli_skills_attach.py`

**Интерфейсы:**
- Consumes: house-конвенция §3; ничего из vault.
- Produces: `todoc skills attach --to DIR --root DATA_ROOT [--force]` — копирует
  пакетную папку `todoc/` в DIR (любой платформенный каталог скилов:
  `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, …), подставляя
  `--root` вместо плейсхолдера `{ROOT}` в теле. Без перезаписи (ошибка
  `attach.exists`, обновление — `--force`). Отчёт — `_emit_ok` с
  `data: {installed: <путь>, skill: "todoc", mount_hint: "…"}` и `next_actions`
  (house-поле конверта, cli.py:46) — argv+purpose, включая строку AGENTS.md
  из Задачи 4, шаг 3.

Тело диспетчера (house-конвенция; полный текст — в файле):

```markdown
---
name: todoc
description: "Маршрутизатор скилов todoc: найти и исполнить нужный скил из хранилища через CLI. Use before any non-trivial task."
metadata:
  doc_type: agent-skill
---
# todoc — диспетчер скилов
## When to Use
Любая нетривиальная задача. НЕ активируй для болтовни и однострочников (entry gate).
## Procedure
1. `todoc skills tree --root {ROOT}` — выбери скил по описанию (раздел = домен).
2. `todoc skills read --root {ROOT} --path <путь из дерева>` — прочитай тело.
3. Действуй строго по SKILL.md; references/ и scripts/ — по ходу.
## Pitfalls
- tree не дал совпадения — работай без скила, не выдумывай (refusal floor).
- Не более одного тела SKILL.md на решение; повторный выбор — только через tree.
- Витрина скилов не смонтирована в платформу намеренно: экономия контекста.
## Verification
- Воспроизведённая команда из SKILL.md дала ожидаемый результат.
```

- [x] **Шаг 1: падающий тест attach**

```python
# tests/cli/test_cli_skills_attach.py — house-паттерн
from click.testing import CliRunner

from todoc.cli import cli
from todoc.errors import TodocError


def _run(runner, args):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


def test_attach_copies_and_embeds_root(tmp_path):
    runner = CliRunner()
    proj = tmp_path / "proj"; (proj / ".agents" / "skills").mkdir(parents=True)
    demo = tmp_path / "demo"; demo.mkdir()
    args = ["skills", "attach", "--to", str(proj / ".agents/skills"), "--root", str(demo)]
    r = _run(runner, args)
    assert r.exit_code == 0, r.output
    sk = proj / ".agents" / "skills" / "todoc" / "SKILL.md"
    assert sk.exists() and str(demo) in sk.read_text(encoding="utf-8")
    r2 = _run(runner, args)
    assert r2.exit_code != 0 and "attach.exists" in r2.output
    r3 = _run(runner, args + ["--force"])
    assert r3.exit_code == 0
```

- [x] **Шаг 2: убедиться, что падает** (команды нет)
- [x] **Шаг 3: реализовать** — чтение пакетной папки:
  `importlib.resources.files("todoc") / "data" / "agent-skill" / "todoc"`;
  `pyproject.toml`: секция `[tool.setuptools.package-data]` →
  `todoc = ["data/**/*"]` (packages.find без package-data не пакует данные —
  иначе в wheel нет SKILL.md); `{ROOT}` → абсолютный `--root`; copytree
  no-overwrite; `--force` — перезапись.
- [x] **Шаг 4: проходят; приёмка экономики** — attach в tmp-платформу: в
  платформенном каталоге ровно ОДНА папка скила (`todoc/`) — L1 = ~100 токенов
  при vault на 10+ скилов; тело содержит вшитый root и refusal floor.
- [x] **Шаг 5: коммит**

```bash
git add src/todoc/data src/todoc/cli.py pyproject.toml tests/cli/test_cli_skills_attach.py
git commit -m "feat(skills): диспетчер-скил todoc + skills attach — одна точка входа для любого агента (экономия контекста, точное исполнение)"
```

### Задача 6: офлайн-импорт `todoc skills import` (+adopt)

**Файлы:**
- Modify: `src/todoc/cli.py` (команда в группе `skills`)
- Modify: `src/todoc/application/skills.py` (примитив copy+validate+adopt)
- Test: `tests/cli/test_cli_skills_import.py`

**Интерфейсы:**
- Consumes: `scan_skills`, `validate_skills` (Задача 1).
- Produces: `todoc skills import --root PATH --src LOCAL_DIR [--skill NAME]
  --into SECTION [--vault skills] [--dry-run] [--adopt]`. `--src` — локальная
  папка (скил или репо-ПАКЕТ: рекурсивный поиск `**/SKILL.md`); без сети.
  Семантика пакета: копируются ТОЛЬКО папки со SKILL.md; плагинная обвязка
  (hooks/, commands/, index.js, package.json, манифесты) не переносится
  (проверено на obra/superpowers — §8).
  `--adopt` — источник УЖЕ скопирован в vault вручную: валидация + отчёт без
  копирования (путь «скопировал папку → одна команда»). Отчёт-конверт:
  `data: {imported: [{name, path}], skipped: [...], diagnostics: [...],
  audit_note: "аудируй чужие скилы перед использованием (scripts/ — код)"},
  next_actions: [{argv: ["todoc", "index", "rebuild", …], purpose: "Пересобрать
  индекс после импорта"}, {argv: ["todoc", "skills", "tree", …], purpose:
  "Показать дерево после импорта"}]} — house-поле конверта (cli.py:46).

- [x] **Шаг 1: падающие тесты** — tmp «репо» с 2 скилами → import в tmp vault:
  папки скопированы целиком (включая `references/`), отчёт содержит `imported`,
  после импорта tree показывает скилы; повторный import → `skills.path_exists`
  (no-overwrite); `--skill NAME` копирует один; скил с плохим front matter
  импортируется (файлы — истина), но отчёт несёт его `skills.*`-диагностики и
  `audit_note`; `--dry-run` ничего не пишет; `--adopt` на уже скопированной
  папке — валидирует и отчётует без копии, на отсутствующей — ошибка;
  **pack-сценарий**: tmp-«репо» с 3 скилами в `skills/` + обвязкой `hooks/`,
  `commands/`, `plugin.json` → после import в vault ровно 3 папки, обвязки
  нет (воспроизведение структуры obra/superpowers).
- [x] **Шаг 2: убедиться, что падает** (команды нет)
- [x] **Шаг 3: реализовать** — `shutil.copytree` (dirs_exist_ok=False), скан
  копии, диагностики в отчёт; `index rebuild` НЕ вызывается автоматически —
  движок предлагает `next`.
- [x] **Шаг 4: проходят; ручная приёмка по идее** — скачанный из skills.sh
  скил (локально) импортируется в `demo/skills/coding/review/` и виден в
  дереве; после приёмки импорт откатить (демо-хранилище остаётся каноничным 10).
- [x] **Шаг 5: коммит**

```bash
git add src/todoc/cli.py src/todoc/application/skills.py tests/cli/test_cli_skills_import.py
git commit -m "feat(skills): todoc skills import — офлайн-импорт и adopt чужих скилов с валидацией"
```

### Задача 7: документация и финальные проверки

**Файлы:**
- Modify: `README.md` (раздел «Скилы»: vault, tree/read, мьют, 2 пути
  установки чужих скилов, attach диспетчера — «подключение к любому агенту»)
- Modify: `demo/HOME.md` (линия `skills/` в карте)
- Modify: `demo/plan/skills-vault-implementation.md` (§8: запись о выполнении)

- [x] **Шаг 1: README** — подраздел в «Работе агентов»: хранилище `demo/skills/`,
  стандарт Agent Skills, `skills tree/read`, мьют, `skills import/adopt`,
  `skills attach` — диспетчер для платформ с нативными скилами (в контексте
  ровно один скил `todoc`), строка в AGENTS.md — для остальных (README
  описывает установку и работу агентов).
- [x] **Шаг 2: HOME** — линия карты со счётчиками (11 скилов, 3 раздела).
- [x] **Шаг 3: финал** — `todoc validate --root demo --all` (0 диагностик),
  `tools/linkcheck.py` (0 битых), полный pytest; счётчики в этом плане
  согласованы с фактом; §8 — запись с датой и числом задач.
- [x] **Шаг 4: коммит**

```bash
git add README.md demo/HOME.md demo/plan/skills-vault-implementation.md
git commit -m "docs(skills): README/HOME/план — документирование хранилища и диспетчера скилов"
```

## 6. Definition of Done

- [x] Все чекбоксы §5 отмечены; §8 содержит запись о выполнении с датой.
- [x] pytest зелёный (988 + новые); coverage 100% на `skills.py` и новых
      ветках `cli.py`/`search.py`/`validator.py`.
- [x] `validate --root demo --all` — 0 диагностик; `tools/linkcheck.py` — 0 битых.
- [x] `skills tree --root demo` < 1 c, **11 скилов**, мьют и `--all` работают;
      `skills read` читает по пути с confinement; E2E-сценарий Задачи 4 выполнен.
- [x] Диспетчер: `skills attach` кладёт единственный скил `todoc` в платформенный
      каталог с вшитым root; vault НЕ монтируется (0 L1-описаний под-скилов);
      entry gate и refusal floor в теле; SKILL.md диспетчера пакуется в wheel
      (package-data — проверка переустановкой `.venv/bin/pip install -e .`).
- [x] Роутинг-правило присутствует в канонических носителях
      (agent-contract.md, SKILL.md) и указателем в AGENTS.md.
- [x] Счётчики README/HOME согласованы с фактом; ни один статус `done` не
      поставлен без явной фразы пользователя.

## 7. Риски и митигации

| Риск | В×В | Митигация | Владелец |
|---|---|---|---|
| Параллельный мерж четырёх планов (softdoc, doc-tags, lifecycle, skills) конфликтует в `cli.py`, `validator.py`, `document-rules.json` | С×В | мержить последовательно: doc-tags → softdoc Задача 1 → skills → lifecycle; rebase перед каждым PR; конфликтные зоны перечислены в §4 | агент |
| doc_type `agent-skill` создаётся и softdoc-планом (Задача 6), и этим (Задача 1) | С×С | условное создание: «если type.json существует — не создавать»; id правил уникальны | агент |
| Мьют-переименование ломает `docs search`-индекс до `index rebuild` | С×Н | движок в `next` предлагает rebuild; правило в agent-contract упоминает rebuild после мьюта/импорта | агент |
| Чужой SKILL.md резолвится в doc_type `skill` (с required_sections) → 5×`markdown.section.missing` | В×С | glob-правило `skills/**/SKILL.md` + doc_type `agent-skill` без required_sections (Задача 1, шаг 7); проба-доказательство в аудите от 25.11.2026 | агент |
| Диспетчер вшивает абсолютный root — перенос датасета ломает argv | Н×С | root вшит в одном месте ({ROOT}); `skills attach --force` перепечатывает; заметка в README Задачи 7 | агент |
| Витрину всё же смонтируют в платформу целиком → L1 всех скилов в контексте | Н×В | README/agent-contract пишут анти-паттерн явно (§3, §4); монтируется только `todoc/` | агент |
| Чужой скил из недоверенного источника содержит вредоносные инструкции/скрипты | С×В | импорт офлайн и только локальные пути; отчёт несёт `audit_note` (Anthropic security); движок scripts не исполняет | агент |
| Перекрытие описаний скилов снижает точность выбора (OpenAI guidance) | Н×Н | house-стандарт описаний: WHAT+WHEN+NOT-WHEN, ≤120 симв.; границы доменов разведены по разделам Задачи 4 | агент |
| coverage 100% недостижим на CLI-обвязке | Н×С | тесты на каждый флаг tree/read/attach/import (§4 — детерминированные ветки); fallback: `# pragma: no cover` с комментарием-обоснованием в §8 | агент |
| Кириллица в разделе `--query` не матчится | Н×Н | решение §4: lowercase-подстрока; тест с кириллическим описанием в Задаче 2 | агент |
| Целый пакет (15+ скилов как superpowers) в один раздел → свалка | С×Н | агент выбирает `--into` по дереву доменов; отчёт imported/skipped; `--skill` для выборочного; обвязка не переносится (§2); реальная проба: 15/15 валидны, конфликтов имён нет | агент |

## 8. Прогресс и отклонения

- Статус: не начат (2026-11-25). Первая задача — Задача 1, шаг 1.
- 2026-11-25 — аудит плана + ресёрч второй волны (Hermes Agent/Nous Research,
  Anthropic engineering, OpenAI guidance 2026-09 via Rill #71, skill-router,
  Routed, Popov, kalinga). Найдено и закрыто 6 отклонений: (1) `docs read`
  принимает только `--id` (cli.py:952), а не `--path` — правило роутинга было
  бы нерабочим → добавлена команда `skills read` с path-confinement (Задача 2);
  (2) чужой SKILL.md не декларирует doc_type — fm-правило его не ловило бы
  (BUG-001-семантика) → добавлено glob-правило `skills/**/SKILL.md` priority 60
  (Задача 1, шаг 7); (3) демо из 8 скилов не выполняло приёмку идеи «10+
  скилов» → 10 скилов/3 раздела; (4) тест Задачи 1 содержал дубль-папку вместо
  двух папок с одним name (duplicate_name был бы не покрыт) и тест Задачи 2 —
  неопределённый хелпер `_vault` → код исправлен; (5) псевдокод `skills.no_skmd`
  исключён из списка кодов; (6) по ресёрчу router-паттернов добавлена Задача 5
  (диспетчер-скил `todoc` + `skills attach`): в платформу монтируется ровно
  один скил (~100 ток. L1) вместо N описаний — точное исполнение через
  детерминированный CLI и экономия контекста; приёмка идеи «10+ скилов» и
  hermes-tier-маппинг — в §4. Отклонений при исполнении нет.
- 2026-11-25 — финальный аудит перед реализацией (все якоря сверены с кодом):
  (1) house-стиль CLI — `--format` → `--output json|table`, `--depth` →
  `--max-depth` (образец `docs tree`, cli.py:1041-1043), вывод через `_emit_ok`
  (cli.py:46) / `_emit_error` (cli.py:1511), поле конверта `next_actions`;
  тесты приведены к house-паттерну `tests/cli/test_cli.py` (`_run` c
  TodocError + `_json`) и дополнены кириллическим `--query` (рисковая строка §7);
  (2) pyproject: `[tool.setuptools.packages.find]` без package-data — SKILL.md
  диспетчера не попал бы в wheel; правка зафиксирована точно (Задача 5, шаг 3);
  (3) front matter демо-скилов задан единым YAML-блоком по образцу
  `demo/skill/SKILL.md` (id/title/doc_type/lang/updated + name/description) —
  иначе не работают конвенция «русский title» и поиск (Задача 4, шаг 1);
  (4) подтверждено по `typing_system/resolver.py:117`: явный fm-doc_type сам
  по себе не назначается — обязательны ОБА правила (glob 60 + fm 200); у
  демо-файлов матчатся оба с одинаковым assign — `config.ambiguous_rule` не
  возникает; (5) doc_type `skill` подтверждён с 5 required_sections,
  `glob-skill` = `skill/**` (singular) — с `skills/**` не пересекается.
  Отклонений при исполнении нет.
- 2026-11-25 — проба реальным пакетом и сверка с концепцией `.research`:
  (1) obra/superpowers склонирован shallow, все 15 SKILL.md прогнаны реальным
  парсером движка против правил планируемого валидатора: 15/15 valid
  (name=папка, regex, description ≤1024, дубликатов нет, все внутри skills/),
  обвязка (hooks/=4, scripts/=5, index.js, package.json,
  gemini-extension.json) отделена от скилов → «целый пакет встаёт одной
  командой import из локального клона; вмешательство агента: выбор --into,
  аудит scripts/ (audit_note), разбор отчёта» — семантика пакета и pack-тест
  добавлены (§2, Задача 6); сам пакет подтверждает dispatcher-паттерн — в нём
  есть свой «using-superpowers» (индексный скил, 7 references); (2)
  microsoft/playwright-cli — активный CLI-тул («Record and generate Playwright
  code…»), не скил-пак: идея «скил по установке пакетов, помогающий CLI» принята
  как 11-й демо-скил coding/env/package-install (Задача 4; мотив — наш реальный
  инцидент PEP 668: глобальный pip заблокирован, только .venv); (3) границы
  ответственности зафиксированы в §4 по mcp-cli-agents-research.md:62/:27,
  comparative-audit.md:19, engineering-plan.md:859: CLI — детерминированный
  исполнитель, мыслительные процессы — агенту; скил — процедурная память, не
  логика CLI; attach не нарушает «init не устанавливает Skill» (отдельная
  явная команда). Счётчики демо 10 → 11.

Отклонений при исполнении нет.
- 2026-11-25 — ИСПОЛНЕНИЕ (задачи 1–7, TDD): код — `skills.py` (scan/validate/
  effective_name), CLI-группа `skills` (tree/read/attach/import), мьют в
  `docs search`, интеграция в `validate_dataset`; демо-vault 11 скилов +
  references; роутинг в трёх носителях; диспетчер-скил в пакете движка
  (`src/todoc/data/agent-skill/todoc/`, package-data в pyproject). Отклонения
  при исполнении: (1) CLI-тесты поднимают tmp-датасет `init --root` — house
  команды идут через `_contexts` (план-тесты этого не учитывали); (2) счётчик
  sections = разделы ВЕРХНЕГО уровня (семантика идеи), не все промежуточные
  папки; (3) `--max-depth` ограничивает оба режима (P7), не только table;
  (4) коды ошибок в тестах — `result.exception.code` (глобальный обработчик
  ошибок за пределами CliRunner не печатает конверт); (5) фильтр диагностик
  import — по имени папки скила `Path(…).name`, не `parent.name` (поймано
  TDD-тестом test_import_reports_invalid_front_matter); (6) роутинг в копию
  `demo/skill/SKILL.md` внесён edit_file, а не `docs edit` 1:1 — BUG-004
  (вставка строк невозможна); исключение задокументировано в AGENTS.md;
  (7) инцидент сессии: секционная правка этого плана partition-скриптом
  уронала файл (229/829 строк) до пуша — восстановлен из коммита c74b326
  (`git reset --soft` + restore), коммит пересоздан; правило: секционные
  правки плана — только state-машина по строкам с assert на число отметок.
  Приёмка: superpowers — целый пакет 15/15 одной командой import (0 skipped,
  0 skills.*-диагностик), затем откат, validate 0; E2E tree → выбор todoc-docs
  → read → исполнение инструкции (карта → search → секция, bounded);
  attach в реальный платформенный каталог с вшитым root; pytest зелёный
  (988 + 18 новых), validate 0, linkcheck 0.

<!-- Формат строки отклонения: `YYYY-MM-DD — задача N, шаг M: что не так → что
     выбрано вместо и почему`. Шаги задним числом не переписывать. -->
