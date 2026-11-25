---
id: doc:plan-skills-vault
title: "Хранилище-движок скилов: skills tree, валидация, мьют, импорт (план)"
doc_type: plan
lang: ru
status: active
tags: [skills, agent-skills, cli, validation, import, routing]
updated: 2026-11-25
related: ["[[skills-engine]]", "[[documentation-system]]", "[[constitution]]"]
---

# Хранилище-движок скилов: skills tree, валидация, мьют, импорт (план) — план реализации

> **Исполнителю (агенту):** план самодостаточен — читай его, а не историю сессии.
> Работай по задачам сверху вниз; шаги отмечаются чекбоксами (`- [ ]`) в том же
> коммите, который делает шаг. Начинай всегда с первого неотмеченного.

**Цель:** единое переносимое хранилище скилов в датасете по открытому стандарту
Agent Skills с CLI-оглавлением `todoc skills tree` на лету, валидацией `skills.*`,
мьютом без удаления и офлайн-импортом чужих скилов.
**Спека:** `ideas/skills-engine.md` (идея; план закрывает её «Открытые вопросы» —
решения в §4).
**Стек:** Python 3.11, click (CLI), существующий markdown-парсер (front matter),
pytest; новых зависимостей нет.

## 1. Критерии успеха

1. `todoc skills tree --root demo` печатает дерево демо-хранилища
   (8 скилов, 3 раздела, 1 замьючен) с описаниями **за < 1 c**, bounded
   (`--limit` по умолчанию 100, `truncated` в JSON-конверте).
2. Чужой скил (скопированная папка со SKILL.md) виден в дереве сразу после
   копирования; SKILL.md с невалидным front matter даёт точные коды `skills.*`
   с локацией (файл:строка) и suggested_fix, а не молчание.
3. Мьют работает без удаления: `!name` отсутствует в дефолтном дереве и в
   `docs search`; `skills tree --all` показывает с пометкой `[!]`.
4. `validate --root demo --all` — 0 диагностик на демо с заполненным
   хранилищем; pytest зелёный (988 + новые), coverage 100% на новом коде.

## 2. Вне скоупа

- **Трекинг апстрима чужих скилов** (diff/refresh при обновлении источника) —
  копия импортируется как есть; трекинг — вручную через git-историю.
- **Сетевые операции в движке.** `skills import` принимает только локальные
  пути (уже склонированный репо / скачанная папка); скачивание — вне движка.
- **Симлинк-монтаж в платформы** (`.claude/skills → skills/…`, `npx skills add`)
  — механика платформ, не todoc; документируется одной строкой, не кодом.
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
  (`--limit` дефолт 100, `--depth` дефолт 6, `truncated`-флаг в JSON).
- **Стандарт Agent Skills:** `name` обязателен — `^[a-z0-9]+(-[a-z0-9]+)*$`,
  ≤64 символов, совпадает с именем папки; `description` — непустой, ≤1024.
  Опциональные поля (`license`, `compatibility`, `metadata`, `allowed-tools`,
  расширенные поля Claude Code) парсятся, но жёстко не валидируются.
- **Без сети:** ни одна команда не делает HTTP/git-запросов.
- **Coverage 100%** на новых модулях и ветках кода; pytest после каждой задачи.
- **Конвенция именования** (`notes/agent-contract.md` → «Именование документов»):
  русский заголовок — в `title`/H1, имена файлов и папок — латиница/kebab;
  исключение — `!`-префикс мьюта (конвенция системы, §4).
- **`related` во front matter — только wikilink-форма** (план doc-tags):
  `related: ["[[…]]"]`; записи — с `relations` на существующие record_id.
- **Команды движка, не ручные правки:** изменения датасета — через
  `docs new`/`docs edit`/`records create` (тело нового длинного md — напрямую,
  скелет и проверки — через CLI, как зафиксировано в AGENTS.md §«Именование»).
- **CLI-неймспейс:** новая группа `skills` (`@cli.group()`, cli.py:273 — образец
  группы `index`); `docs tree` (cli.py:1041) занят деревом секций документа.

## 4. Архитектура и файловая карта

**Подход.** Новый модуль `src/todoc/application/skills.py` — чистый сканер:
обход каталога vault (по умолчанию `<root>/skills/`), leaf-детект «подкаталог
с SKILL.md = скил», парсинг front matter существующим парсером, сбор
`SkillInfo` и диагностики `skills.*`. CLI-группа `skills` (tree, import) —
тонкая обёртка над сканером; `validate` вызывает `validate_skills` и мержит
диагностики в общий поток. Мьют — фильтр по сегменту пути `!…` в сканере и
в `docs search` (пост-фильтр по пути в search.py).

**Решения открытых вопросов идеи (закрыты здесь):**

| Вопрос | Решение |
|---|---|
| Живой скан vs индекс | Всегда живой скан (P1, размеры ≤ сотен скилов); при `len(skills) > 500` — warning-строка в выводе, индекс не строим |
| Причина мьюта | Только `!`-имя папки; пояснение — не файла, а git-история; `--all` показывает `[!]` без причины |
| Кириллица в разделах | Разделы — обычные папки, regex стандарта на них НЕ распространяется; `--query` — lowercase-подстрока по name+description+пути, кириллица работает |
| Глубина дерева | Произвольная вложенность разделов, скил на любой глубине; печатается до `--depth` (дефолт 6) |
| Один vault или несколько | `--vault PATH` (относительно DATA_ROOT, дефолт `skills`) на каждый вызов; личные/командные — поддеревья, комбинируются вызовами |
| Апдейты апстрима | Вне скоупа (копия; git-история — источник правды) |
| Конфликт имён | `skills.duplicate_name` = **error** глобально по vault; неймспейсов нет |
| name_mismatch у мьютнутых | Эффективное имя папки = `folder.lstrip("!")`; сравнение по нему |

**Коды диагностики** (в `validate` и `skills import`, локация — файл:строка,
suggested_fix в духе существующих): `skills.missing_front_matter` (error),
`skills.bad_name` (error), `skills.name_mismatch` (error),
`skills.long_description` (error, >1024), `skills.duplicate_name` (error),
`skills.no_skmd` (error: папка-скил без SKILL.md невозможна по детекту — код
для папки, заявленной `name` без SKILL.md не нужен; не реализуется), 
`skills.empty_description` (error). Мьют-папка валидируется по содержимому
как обычная (стандарт не нарушается).

**Карта файлов:**

| Файл | Действие | За что отвечает |
|---|---|---|
| `src/todoc/application/skills.py` | Create | `SkillInfo`, `scan_skills`, `validate_skills`, `effective_name` |
| `src/todoc/cli.py` | Modify (~273, ~1103 — рядом с группами) | группа `skills`: команды `tree`, `import` |
| `src/todoc/application/validator.py` | Modify (`validate_dataset`:278) | вызов `validate_skills` для каждого vault, мерж диагностик |
| `src/todoc/application/search.py` | Modify (`search.py:146-148` рядом) | пост-фильтр: исключение `!`-сегментов из результатов `docs search` |
| `demo/.todoc/rules/document-rules.json` | Modify | fm-правило `fm-agent-skill-vault` (priority 200) |
| `demo/.todoc/doc_types/agent-skill/type.json` | Create (условное, см. Задача 1) | doc_type БЕЗ required_sections для чужих SKILL.md |
| `demo/skills/**` | Create | демо-хранилище: 8 скилов, 3 раздела, 1 мьют, references/ |
| `SKILL.md`, `demo/notes/agent-contract.md`, `AGENTS.md` | Modify | роутинг-правило (канон в системе, AGENTS.md — указатель) |
| `README.md`, `demo/HOME.md` | Modify | раздел «Скилы», линия карты, счётчики |
| `tests/unit/test_skills_scan.py` | Test | сканер: детект, sections, muted, effective_name |
| `tests/unit/test_validator_skills.py` | Test | все коды `skills.*`, локации, suggested_fix |
| `tests/cli/test_cli_skills_tree.py` | Test | tree/json, --query/--within/--limit/--depth/--all, <1 c |
| `tests/cli/test_cli_skills_import.py` | Test | импорт из tmp-репо, no-overwrite, отчёт |

## 5. Задачи

### Задача 1: сканер и валидация `skills.*`

**Файлы:**
- Create: `src/todoc/application/skills.py`
- Modify: `src/todoc/application/validator.py:278` (`validate_dataset`)
- Modify: `demo/.todoc/rules/document-rules.json` (+правило)
- Create (условное): `demo/.todoc/doc_types/agent-skill/type.json`
- Test: `tests/unit/test_skills_scan.py`, `tests/unit/test_validator_skills.py`

**Интерфейсы:**
- Consumes: парсер front matter из существующего markdown-модуля движка.
- Produces: `SkillInfo(name, path, section, description, muted, refs, scripts, assets)`;
  `scan_skills(vault_root: Path) -> tuple[list[SkillInfo], list[dict]]`;
  `validate_skills(vault_root: Path, skills: list[SkillInfo]) -> list[dict]`
  (диагностики — словари того же shape, что отдаёт `validate_dataset`);
  `effective_name(folder: str) -> str` (= `folder.lstrip("!")`).

- [ ] **Шаг 1: падающий тест сканера** (fixtures — tmp_path, не демо)

```python
# tests/unit/test_skills_scan.py
from pathlib import Path
from todoc.application.skills import scan_skills, effective_name

def _skill(root: Path, rel: str, fm: str) -> None:
    d = root / rel
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(fm + "\n# Тело\n", encoding="utf-8")

FM = "---\nname: commit-message\ndescription: Пишет commit message.\n---\n"

def test_scan_detects_skill_and_sections(tmp_path):
    _skill(tmp_path, "coding/git/commit-message", FM)
    _skill(tmp_path, "coding/git/!legacy-deploy", FM.replace("commit-message", "legacy-deploy"))
    (tmp_path / "coding/git/release").mkdir()  # раздел без SKILL.md — не скил
    skills, _ = scan_skills(tmp_path)
    assert [s.name for s in skills] == ["commit-message", "legacy-deploy"]
    assert [s.section for s in skills] == ["coding/git", "coding/git"]
    assert [s.muted for s in skills] == [False, True]
    assert effective_name("!legacy-deploy") == "legacy-deploy"
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `.venv/bin/python -m pytest tests/unit/test_skills_scan.py -v`
Expected: FAIL — `ModuleNotFoundError: todoc.application.skills`

- [ ] **Шаг 3: реализовать `skills.py`** — сигнатуры из Produces выше; leaf-детект:
  каталог содержит `SKILL.md` → скил, иначе — раздел; `section` = относительный
  путь папки-родителя; счётчики `refs/scripts/assets` — len() по подкаталогам;
  front matter — существующим парсером; ошибки парсинга → диагностика
  `skills.missing_front_matter` (не исключение).

- [ ] **Шаг 4: тест валидатора кодов**

```python
# tests/unit/test_validator_skills.py
from todoc.application.skills import scan_skills, validate_skills

def _skill(root, rel, fm):
    d = root / rel; d.mkdir(parents=True)
    (d / "SKILL.md").write_text(fm, encoding="utf-8")

def test_all_skill_codes(tmp_path):
    bad = "---\nname: Wrong_Name\ndescription: '" + "x" * 1100 + "'\n---\n"
    _skill(tmp_path, "coding/a", bad)                      # bad_name + long_description + name_mismatch
    _skill(tmp_path, "coding/git/b", "---\nname: b\n---\n")   # empty_description
    _skill(tmp_path, "coding/git/c", FM_VALID)             # ok, name= c
    _skill(tmp_path, "coding/git/c", "---\nname: c\ndescription: d2\n---\n")  # duplicate_name
    skills, diags = scan_skills(tmp_path)
    codes = {d["code"] for d in diags + validate_skills(tmp_path, skills)}
    assert {"skills.bad_name", "skills.long_description", "skills.name_mismatch",
            "skills.empty_description", "skills.duplicate_name"} <= codes
    loc = [d for d in diags if d["code"] == "skills.bad_name"][0]
    assert loc["path"].endswith("coding/a/SKILL.md") and "line" in loc
    assert loc.get("suggested_fix")
```

- [ ] **Шаг 5: убедиться, что падает; реализовать `validate_skills`** — правила
  §3/§4 (regex `^[a-z0-9]+(-[a-z0-9]+)*$`, ≤64; description непустой ≤1024;
  name == effective_name(папка); глобальный дедуп name по vault; мьют-папка
  валидируется как обычная).

- [ ] **Шаг 6: интеграция в `validate`** — в `validate_dataset` (validator.py:278):
  для каждого root — vault `<root>/skills` (если существует) →
  `validate_skills`; мерж в общий список диагностик. Тест: vault с плохим
  скилом → `validate --all` отдаёт `skills.*`; без vault — ноль новых диагностик.

- [ ] **Шаг 7: fm-правило и doc_type `agent-skill`** — условно: если
  `demo/.todoc/doc_types/agent-skill/type.json` уже существует (softdoc-план,
  Задача 6) — НЕ создавать, только правило. Иначе создать минимальный type.json
  (копия структуры соседнего doc_type, `required_sections` отсутствует —
  чужой SKILL.md не обязан иметь секции движка; проба-обоснование: SKILL.md без
  секций против doc_type `skill` с required_sections даёт
  5×`markdown.section.missing` — проверено аудитом 25.11.2026). Правило в
  `document-rules.json`:

```json
{"id": "fm-agent-skill-vault",
 "match": {"kind": "file", "front_matter": {"doc_type": "agent-skill"}},
 "assign": {"doc_type": "agent-skill"}, "priority": 200}
```

- [ ] **Шаг 8: полный прогон и коммит**

Run: `.venv/bin/python -m pytest tests/unit/test_skills_scan.py tests/unit/test_validator_skills.py -v && .venv/bin/todoc validate --root demo --all`
Expected: PASS; 0 диагностик (vault `demo/skills` ещё не создан — шаг игнорируется)

```bash
git add src/todoc/application/skills.py src/todoc/application/validator.py tests/unit/test_skills_scan.py tests/unit/test_validator_skills.py demo/.todoc/rules/document-rules.json demo/.todoc/doc_types/agent-skill
git commit -m "feat(skills): сканер хранилища скилов + валидация skills.* + fm-правило agent-skill"
```

### Задача 2: CLI `todoc skills tree`

**Файлы:**
- Modify: `src/todoc/cli.py` (новая группа `skills` рядом с группой `index`, cli.py:273)
- Test: `tests/cli/test_cli_skills_tree.py`

**Интерфейсы:**
- Consumes: `scan_skills`, `SkillInfo` (Задача 1).
- Produces: `todoc skills tree --root PATH [--vault skills] [--within SECTION]
  [--query Q] [--all] [--limit N] [--depth N] [--format tree|json]`.
  JSON-конверт: `data: {vault, counts: {skills, sections, muted},
  skills: [{name, path, section, description, muted, refs, scripts, assets}],
  truncated: bool}`. Tree-режим — как в образце идеи (описание = первая строка
  description, обрезка по ширине, `[!]`-пометка, счётчики на разделах).

- [ ] **Шаг 1: падающий CLI-тест** (CliRunner, fixtures — tmp_path с 3 скилами)

```python
# tests/cli/test_cli_skills_tree.py
from click.testing import CliRunner
from todoc.cli import cli

def test_tree_json_bounded(tmp_path):
    _vault(tmp_path)  # commit-message, adr, jira-fetch (см. Задача 1 helpers)
    r = CliRunner().invoke(cli, ["skills", "tree", "--root", str(tmp_path), "--format", "json"])
    assert r.exit_code == 0
    data = r.json_data()["data"] if hasattr(r, "json_data") else _parse(r.output)["data"]
    assert data["counts"]["skills"] == 3 and data["truncated"] is False
    assert all("description" in s for s in data["skills"])

def test_tree_query_within_all(tmp_path):
    _vault(tmp_path)
    q = CliRunner().invoke(cli, ["skills", "tree", "--root", str(tmp_path), "--query", "commit"])
    assert "commit-message" in q.output and "jira-fetch" not in q.output
    w = CliRunner().invoke(cli, ["skills", "tree", "--root", str(tmp_path), "--within", "coding"])
    assert "jira-fetch" not in w.output
    a = CliRunner().invoke(cli, ["skills", "tree", "--root", str(tmp_path), "--all", "--vault", "v2"])
    assert "[!]" in a.output  # v2: muted-скил виден только с --all
```

- [ ] **Шаг 2: убедиться, что падает** (`skills` — нет такой команды)
- [ ] **Шаг 3: реализовать группу и команду** — thin wrapper: scan → фильтры
  (`--query` lowercase-подстрока по name+description+пути; `--within` — префикс
  section; мьют: исключить из выдачи без `--all`) → сортировка по пути →
  limit/depth/truncated → формат. Warning при `len(skills) > 500`.
- [ ] **Шаг 4: тесты проходят** + ограничение времени: дерево из 50 скилов
  в tmp_path печатается < 1 c (`time.monotonic()` в тесте, порог 1.0 с).
- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/cli.py tests/cli/test_cli_skills_tree.py
git commit -m "feat(skills): todoc skills tree — оглавление хранилища на лету (tree/json, query/within/limit/depth/all)"
```

### Задача 3: мьют в `docs search`

**Файлы:**
- Modify: `src/todoc/application/search.py` (пост-фильтр рядом с :146-148)
- Test: `tests/cli/test_cli_skills_tree.py` (класс TestMutedSearch) или отдельный
  `tests/unit/test_search_muted.py`

**Интерфейсы:**
- Consumes: существующий `docs search` (search.py).
- Produces: результаты `docs search` не содержат путей с сегментом `!…`;
  флаг/параметр не добавляется (мьют — свойство хранилища, не запроса).

- [ ] **Шаг 1: падающий тест** — в tmp-датасете скил `!legacy-deploy/SKILL.md`
  со словом «deploy» в теле; после `index rebuild` `docs search deploy` НЕ
  возвращает этот путь; обычный скил с тем же словом — возвращает.
- [ ] **Шаг 2: убедиться, что падает** (сейчас путь находится)
- [ ] **Шаг 3: реализовать** — пост-фильтр по пути в выдаче поиска:
  `any(part.startswith("!") for part in Path(p).parts) → exclude`.
- [ ] **Шаг 4: проходят все поисковые тесты** (старые не сломались —
  кириллические имена legacy не содержат `!`).
- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/search.py tests/
git commit -m "feat(skills): мьют !-папки исключён из docs search"
```

### Задача 4: демо-хранилище и роутинг-правило

**Файлы:**
- Create: `demo/skills/coding/git/commit-message/SKILL.md`,
  `demo/skills/coding/git/release/SKILL.md`,
  `demo/skills/coding/git/!legacy-deploy/SKILL.md`,
  `demo/skills/coding/review/code-review/SKILL.md`,
  `demo/skills/coding/review/adr/SKILL.md`,
  `demo/skills/docs/todoc-docs/SKILL.md` + `references/query-cheatsheet.md`,
  `demo/skills/docs/jira-fetch/SKILL.md`,
  `demo/skills/process/release-flow/SKILL.md`
- Modify: `SKILL.md` (движковый, 1:1 строка), `demo/notes/agent-contract.md`
  (новый раздел), `AGENTS.md` (указатель)
- Test: E2E-сценарий — руками по приёмке ниже; тесты не требуются

**Интерфейсы:**
- Consumes: `skills tree` (Задача 2), конвенция именования.
- Produces: работающий роутинг: одна императивная строка с готовым argv.

- [ ] **Шаг 1: создать 8 SKILL.md** — front matter по стандарту (name = имени
  папки; у `!legacy-deploy` name = `legacy-deploy`); body 20–60 строк реальных
  инструкций (не заглушки: commit-message — из staged diff; adr — из обсуждения;
  todoc-docs — поиск KB через CLI с argv-примерами; jira-fetch — снимок задачи
  в notes; release-flow — merge-forward; code-review — чеклист; release —
  changelog/тег). У `todoc-docs` — `references/query-cheatsheet.md` (10+ строк).
  Русский H1 в теле, `name` латиницей — конвенция. Один скил несёт расширенное
  поле Claude Code (`when_to_use`) — тест совместимости «парсится, не ломается».
- [ ] **Шаг 2: сквозная проверка** — `todoc skills tree --root demo` печатает
  8 скилов/3 раздела, `[!]` без `--all` не видно, `--all` видно; `todoc validate
  --root demo --all` — 0 диагностик (в т.ч. `skills.*` и `markdown.*` на
  SKILL.md); `docs search "commit message"` находит `commit-message`,
  но НЕ `!legacy-deploy` (после `index rebuild`).
- [ ] **Шаг 3: роутинг-правило** — канон в системе: `demo/notes/agent-contract.md`
  новый раздел «Скилы: хранилище, дерево, мьют, импорт» (правило ниже + ссылки);
  строка-правило в `SKILL.md` движка (1:1 через `docs edit`); указатель в
  `AGENTS.md` (временный файл — только указатель, не канон):

```markdown
Перед любой нетривиальной задачей выполни:
  todoc skills tree --root demo
Выбери скилл по описанию (раздел = домен). Прочитай:
  todoc docs read --path <путь из дерева>/SKILL.md
Действуй по инструкциям SKILL.md; references/ и scripts/ — по ходу.
Подходящего нет — работай без него; чужие скилы не модифицируй.
```

- [ ] **Шаг 4: E2E-приёмка** — по правилу: tree → выбрать `todoc-docs` →
  `docs read` → выполнить его инструкцию (найти ответ в KB через CLI) — без
  промежуточных файлов и без ручного обхода папок.
- [ ] **Шаг 5: коммит**

```bash
git add demo/skills SKILL.md demo/notes/agent-contract.md AGENTS.md
git commit -m "feat(skills-demo): демо-хранилище 8 скилов + роутинг-правило в агентских носителях"
```

### Задача 5: офлайн-импорт `todoc skills import`

**Файлы:**
- Modify: `src/todoc/cli.py` (команда в группе `skills`)
- Modify: `src/todoc/application/skills.py` (примитив copy+validate)
- Test: `tests/cli/test_cli_skills_import.py`

**Интерфейсы:**
- Consumes: `scan_skills`, `validate_skills` (Задача 1).
- Produces: `todoc skills import --root PATH --src LOCAL_DIR [--skill NAME]
  --into SECTION [--vault skills] [--dry-run]`. `--src` — локальная папка
  (скил или репо: рекурсивный поиск `**/SKILL.md`); без сети. Отчёт-конверт:
  `data: {imported: [{name, path}], skipped: [...], diagnostics: [...],
  next: ["todoc index rebuild", "todoc skills tree --root …"]}`.

- [ ] **Шаг 1: падающие тесты** — tmp «репо» с 2 скилами → import в tmp vault:
  папки скопированы целиком (включая `references/`), отчёт содержит `imported`,
  после импорта tree показывает скилы; повторный import → ошибка
  `skills.path_exists` (no-overwrite); `--skill NAME` копирует один;
  скил с плохим front matter импортируется (файлы — истина), но отчёт несёт
  его `skills.*`-диагностики; `--dry-run` ничего не пишет.
- [ ] **Шаг 2: убедиться, что падает** (команды нет)
- [ ] **Шаг 3: реализовать** — `shutil.copytree` (dirs_exist_ok=False), скан
  копии, диагностики в отчёт; `index rebuild` НЕ вызывается автоматически —
  движок предлагает `next`.
- [ ] **Шаг 4: проходят; ручная приёмка по идее** — скачанный из skills.sh
  скил (локально) импортируется в `demo/skills/coding/review/` и виден в
  дереве; после приёмки импорт откатить (демо-хранилище остаётся каноничным 8).
- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/cli.py src/todoc/application/skills.py tests/cli/test_cli_skills_import.py
git commit -m "feat(skills): todoc skills import — офлайн-импорт чужих скилов с валидацией"
```

### Задача 6: документация и финальные проверки

**Файлы:**
- Modify: `README.md` (раздел «Скилы»: что это, tree/import, роутинг)
- Modify: `demo/HOME.md` (линия `skills/` в карте)
- Modify: `demo/plan/skills-vault-implementation.md` (§8: запись о выполнении)

- [ ] **Шаг 1: README** — подраздел в «Работе агентов»: хранилище `demo/skills/`,
  стандарт Agent Skills, `skills tree`, мьют, `skills import`, строка роутинга
  (README описывает установку и работу агентов).
- [ ] **Шаг 2: HOME** — линия карты со счётчиками (8 скилов, 3 раздела).
- [ ] **Шаг 3: финал** — `todoc validate --root demo --all` (0 диагностик),
  `tools/linkcheck.py` (0 битых), полный pytest; счётчики в этом плане
  согласованы с фактом; §8 — запись с датой и числом задач.
- [ ] **Шаг 4: коммит**

```bash
git add README.md demo/HOME.md demo/plan/skills-vault-implementation.md
git commit -m "docs(skills): README/HOME/план — документирование хранилища скилов"
```

## 6. Definition of Done

- [ ] Все чекбоксы §5 отмечены; §8 содержит запись о выполнении с датой.
- [ ] pytest зелёный (988 + новые); coverage 100% на `skills.py` и новых
      ветках `cli.py`/`search.py`/`validator.py`.
- [ ] `validate --root demo --all` — 0 диагностик; `tools/linkcheck.py` — 0 битых.
- [ ] `skills tree --root demo` < 1 c, 8 скилов, мьют и `--all` работают;
      E2E-сценарий Задачи 4 выполнен.
- [ ] Роутинг-правило присутствует в канонических носителях
      (agent-contract.md, SKILL.md) и указателем в AGENTS.md.
- [ ] Счётчики README/HOME согласованы с фактом; ни один статус `done` не
      поставлен без явной фразы пользователя.

## 7. Риски и митигации

| Риск | В×В | Митигация | Владелец |
|---|---|---|---|
| Параллельный мерж четырёх планов (softdoc, doc-tags, lifecycle, skills) конфликтует в `cli.py`, `validator.py`, `document-rules.json` | С×В | мержить последовательно: doc-tags → softdoc Задача 1 → skills → lifecycle; rebase перед каждым PR; конфликтные зоны перечислены в §4 | агент |
| doc_type `agent-skill` создаётся и softdoc-планом (Задача 6), и этим (Задача 1) | С×С | условное создание: «если type.json существует — не создавать»; правило fm id уникально | агент |
| Мьют-переименование ломает `docs search`-индекс до `index rebuild` | С×Н | движок в `next` предлагает rebuild; правило в agent-contract упоминает rebuild после мьюта/импорта | агент |
| Чужой SKILL.md резолвится в doc_type `skill` (с required_sections) → 5×`markdown.section.missing` | В×С | fm-правило + doc_type `agent-skill` без required_sections (Задача 1, шаг 7); проба-доказательство в аудите от 25.11.2026 | агент |
| coverage 100% недостижим на CLI-обвязке | Н×С | тесты на каждый флаг tree/import (таблица решений в §4 — детерминированные ветки); fallback: `# pragma: no cover` с комментарием-обоснованием в §8 | агент |
| Кириллица в разделе `--query` не матчится | Н×Н | решение §4: lowercase-подстрока; тест с кириллическим описанием в Задаче 2 | агент |

## 8. Прогресс и отклонения

- Статус: не начат (2026-11-25). Первая задача — Задача 1, шаг 1.
- Отклонений нет.

<!-- Формат строки отклонения: `YYYY-MM-DD — задача N, шаг M: что не так → что
     выбрано вместо и почему`. Шаги задним числом не переписывать. -->
