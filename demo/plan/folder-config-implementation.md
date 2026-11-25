---
id: doc:plan-folder-config
title: "Конфиг папок: .config.json — самоописание, дерево с описаниями, suggest-скоринг (план)"
doc_type: plan
lang: ru
status: active
tags: [folder-config, cli, tree, suggest, scoring, search]
updated: 2026-11-25
related: ["[[folder-config]]", "[[skills-engine]]", "[[plan-skills-vault]]"]
---

# Конфиг папок: .config.json — самоописание, дерево с описаниями, suggest-скоринг (план) — план реализации

> **Исполнителю (агенту):** план самодостаточен — читай его, а не историю сессии.
> Работай по задачам сверху вниз; шаги отмечаются чекбоксами (`- [ ]`) в том же
> коммите, который делает шаг. Начинай всегда с первого неотмеченного.

**Цель:** спец-файл `.config.json` в папке датасета — машиночитаемое самоописание
(title/aliases/description/order/tags), которое CLI подхватывает при обходе:
`docs tree`, `skills tree` и `explain-path` печатают заголовки и описания папок,
новая команда `docs suggest` ранжирует папки по запросу (Фаза A скоринга),
`docs search` получает низковесный буст по тегам/заголовкам разделов.
**Спека:** [идея folder-config](../ideas/folder-config.md) (doc:folder-config-idea);
план закрывает все её открытые вопросы — решения в §4.
**Стек:** Python 3.11, click, существующие `parse_json`/`tokenize`, pytest;
**новых зависимостей нет** (Фаза B — стемминг+BM25 — вне скоупа, gate в §4).

## 1. Критерии успеха

1. В демо лежат 5 валидных `.config.json` (3 раздела скилов + plan/ + bugs/);
   `validate --root demo --all` — 0 диагностик; папка без конфига — тоже 0.
2. `docs tree --root demo` печатает рядом с путём русские заголовки и обрезанные
   описания из конфигов; JSON-вывод содержит `folder_meta` на папку.
3. `todoc docs suggest --root demo --query "идея про релиз"` возвращает
   `process/` сверху со `score` и `reason` (alias «процессы|…|релиз|…»);
   несовпавшие папки — в `discarded`; ниже порога 0.25 — ничего не навязывается.
4. `skills tree --root demo` печатает заголовки/описания разделов из конфигов
   (`coding/ — Скилы кодинга: …`); `--query` матчит и текст конфига раздела.
5. pytest зелёный (1006 + новые), coverage 100% на новом коде; исключение
   `.config.json` из индекса подтверждено тестом (не документ, счётчики не растут).

## 2. Вне скоупа

- **Фаза B (стемминг + BM25)**: `snowballstemmer`, `rank-bm25`/`bm25s`,
  стоп-листы, `folder-index.json` в поколение индекса, `relevance_method:
  lexical-stem/exact-alias`. **Gate**: fixture-набор запросов (≥10, фиксируется
  до старта B), на котором Фаза A даёт неверный топ — иначе B не строится
  (решение в §4; порт E4/E5 остаётся контуром).
- **Наследование описаний от родителя** — нет (§4, явность).
- **Централизованный реестр конфигов** (`.todoc/folder-configs.json`) — отложен;
  точка истины — файл рядом с папкой (переносимость, §4).
- **`icon`/`lang`** — парсятся, валидируются по типу, **никак не используются**
  в выводе (UI-метаданные будущего).
- **`docs suggest` для записей (records)** и «куда положить задачу» — только
  папки-документы; records-назначения — позже.
- **Мульти-рутовый реестр папок** — каждый root сканируется отдельно, склейки нет.
- **Кириллические имена самих папок** — не запрещаются и не валидируются
  (конфиг описывает папку, не переименовывает; конвенция именования касается
  новых файлов — для папок действует legacy-правило).

## 3. Глобальные ограничения

- **P1/P2 (конституция):** конфиги читаются **на лету** при выводе/скоринге
  (папок в датасете — десятки, чтение дёшево); никакого `folder-index.json`
  в этой фазе — индекс папок появляется только с Фазой B (вне скоупа).
- **P3/P10:** `.config.json` — декларативные данные, ничего не исполняется.
- **Служебный файл, не документ:** `.config.json` исключается из скана документов
  (как `.todoc.json` — одна строка в scanner.py:96): не попадает в `docs search`,
  в счётчики и в `validate` как JSON-документ; валидируется только dedicated
  кодами `folder.*` (§4).
- **Fail-open на вывод, fail-closed на валидация** (сценарий идеи): битый/лишний
  конфиг даёт диагностику `folder.*`, но дерево и suggest продолжают работать,
  игнорируя нестандартное (конфиг с ошибкой парсинга целиком не участвует).
- **Отсутствие — не ошибка:** папка без `.config.json` валидна и печатается
  как раньше; конфиг — опциональное обогащение.
- **Только точное имя** `.config.json` (не `config.json`, не `.folderconfig`) —
  одна конвенция (§4).
- **Поля:** `schema_version` (int, всегда 1, обязательно); `title` (string 1–80,
  обязательно); `aliases` (string ≤500, `|`-разделитель, опционально);
  `description` (string ≤500), `order` (int), `icon` (string ≤50), `lang`
  (string ≤10), `tags` (list[string], каждый 1–80) — опционально. Неизвестное
  поле → `folder.config.unknown_field` (error). Нормализация aliases: трим
  пробелов, пустые элементы отбрасываются, дубли внутри папки →
  `folder.config.duplicate_alias` (warning), один alias в двух папках →
  `folder.config.alias_collision` (warning, обе участвуют с равным score).
- **Скоринг Фазы A** (детерминированный, без зависимостей): точный alias
  подстрокой в запросе +1.0 за элемент; пословное пересечение alias с запросом
  +0.3 за слово; слова из title/description/tags +0.2 за слово; бонус длины
  alias ×(1 + 0.1·(len−1)); нормировка score/max → 0..1; порог 0.25; tie-break
  order → путь. Токенизация — существующий `tokenize()` (search.py, кириллица
  работает). Никаких порогов «уверенности»: CLI отдаёт ranked+discarded,
  выбор — за агентом/человеком.
- **House-стиль CLI:** `--output json|table|markdown`, `_emit_ok`/`_emit_error`,
  `next_actions`; тесты — house-паттерн (`_run`+`_json`, `TodocError`),
  CLI-тесты поднимают tmp-датасет `init --root` (урок skills-vault §8).
- **Конвенция именования:** русский заголовок в `title` (и конфига, и документов),
  имена файлов — латиница; `.config.json` — фиксированное служебное имя.
- **`related` — wikilink-форма; записи — на существующие record_id.**
- **Конфликтные зоны с параллельными планами:** search.py (doc-tags тоже правит
  веса), scanner.py, cli.py (docs tree) — мержить по порядку риск-таблицы §7.

## 4. Архитектура и файловая карта

**Подход.** Новый модуль `src/todoc/application/folder_config.py` — чистые
функции: обход корня (пропуск `HARD_EXCLUDE_DIRS`, scanner.py:10), чтение
`.config.json` на верхнем уровне каждой папки, парсинг существующим
`parse_json` (локации ошибок), сбор `FolderConfig`, диагностики `folder.*`,
и Фаза A скоринга (веса §3, reason-строки). CLI — тонкая обёртка: `docs tree`,
`explain-path`, новая команда `docs suggest`, `skills tree` и `docs search`
вызывают один и тот же `load_folder_configs`/`score_folder_configs`.
Валидация: `validate_dataset` получает новый шаг `_folder_configs_diagnostics`
(по образцу `_skills_diagnostics` плана skills-vault) — диагностикам
проставляется dataset_id/стабильный id; параллельно сканер перестает видеть
`.config.json` как документ (исключение из индекса и счётчиков).

**Решения открытых вопросов идеи (закрыты здесь):**

| Вопрос | Решение |
|---|---|
| Наследование описания от родителя | **Нет** — явность; молчаливая семантика хуже пустой строки |
| Конфиг vs SKILL.md для скил-папок | Конфиг описывает **разделы**; скил описывается своим SKILL.md (описание скила не читается из конфига) |
| `.config.json` рядом vs централизованно | **Рядом с папкой** (переносится с ней, виден глазами); централизованный реестр — отложен до мульти-рут потребности |
| Имя файла | Только точное `.config.json`; других имён не признаём |
| Граница фаз A/B | Фаза A — в этом плане; Фаза B — gated (fixture-набор ≥10 запросов, на котором A ошибается; фиксируется до старта B) |
| Смешанные ru/en aliases | Существующий `tokenize()` юникодный (`[a-zA-Z0-9_\u0400-\u04ff]+`) — не ломает смешанные строки; alias целиком матчится подстрокой без токенизации |
| Лимит числа псевдонимов | Ограничение длиной строки 500 — достаточно; отдельного лимита нет |
| `version` для миграций | `schema_version` достаточен; отдельного `version` нет |

**Коды диагностики** (`folder.*`; локация — файл:строка через `parse_json`/
`_key_location`): `folder.config.invalid_json` (error), `folder.config.unknown_field`
(error), `folder.config.bad_type` (error: не тот тип/длина), `folder.config.bad_order`
(error: order не int), `folder.config.bad_alias` (error: пустой/больше 80 элемент),
`folder.config.duplicate_alias` (warning), `folder.config.alias_collision` (warning).
Fail-open: конфиг с error-диагностикой не участвует в выводе/скоринге, но папка
продолжает печататься как раньше.

**Карта файлов:**

| Файл | Действие | За что отвечает |
|---|---|---|
| `src/todoc/application/folder_config.py` | Create | `FolderConfig`, `load_folder_configs`, `validate_folder_configs`, `score_folder_configs` (Фаза A) |
| `src/todoc/adapters/filesystem/scanner.py` | Modify (:96) | исключение `.config.json` из скана документов |
| `src/todoc/application/validator.py` | Modify (рядом с `_skills_diagnostics`) | `_folder_configs_diagnostics` → коды `folder.*` в `validate --all` |
| `src/todoc/cli.py` | Modify (docs tree:1041, explain-path:1090, новые команды) | `folder_meta` в tree/explain-path; `docs suggest`; skills tree разделы |
| `src/todoc/application/skills.py` | Modify (нет — читает конфиги через CLI-слой) | — разделы берут мету в cli.py, модуль скилов не меняется |
| `src/todoc/application/search.py` | Modify (после candidates, рядом с :146-148) | буст +2 по title/aliases/tags конфигов папок-предков |
| `demo/skills/{coding,docs,process}/.config.json`, `demo/plan/.config.json`, `demo/bugs/.config.json` | Create | 5 демо-конфигов (order: process=1, docs=2, coding=3) |
| `demo/notes/agent-contract.md`, `demo/HOME.md`, `README.md` | Modify | роутинг-строка «дерево малопонятно — прочитай конфиг раздела»; счётчики; команды |
| `tests/unit/test_folder_config.py` | Test | парсер: поля, лимиты, нормализация aliases, fail-open |
| `tests/unit/test_validator_folder_config.py` | Test | все коды `folder.*`, локации, интеграция в validate_dataset |
| `tests/unit/test_search_muted.py` (расширить) или `tests/unit/test_search_folder_boost.py` | Test | буст docs search |
| `tests/cli/test_cli_folder_meta.py` | Test | docs tree folder_meta (json/table), explain-path, --match |
| `tests/cli/test_cli_docs_suggest.py` | Test | скоринг: сценарий «релиз», порог, discarded, tie-break |
| `tests/cli/test_cli_skills_tree.py` (расширить) | Test | разделы из конфигов, query по тексту конфига |

## 5. Задачи

### Задача 1: парсер, валидация `folder.*`, исключение из скана

**Файлы:**
- Create: `src/todoc/application/folder_config.py`
- Modify: `src/todoc/adapters/filesystem/scanner.py:96`
- Modify: `src/todoc/application/validator.py` (новый шаг в `validate_dataset`)
- Test: `tests/unit/test_folder_config.py`, `tests/unit/test_validator_folder_config.py`

**Интерфейсы:**
- Consumes: `parse_json` (jsonfmt.py:217 — ошибки с line/column),
  `HARD_EXCLUDE_DIRS` (scanner.py:10), house-диагностика-словарь
  (skills.py `_diag` — та же форма).
- Produces: `FolderConfig(path, title, aliases: list[str], description, order,
  icon, lang, tags)`; `load_folder_configs(root: Path) ->
  tuple[dict[str, FolderConfig], list[dict]]` (ключ — rel-путь папки; конфиг с
  error-диагностикой не попадает в словарь — fail-open); `validate_folder_configs(
  root: Path, raw: dict[str, str]) -> list[dict]` — полный набор кодов `folder.*`
  включая cross-папочные (duplicate/alias_collision — warning).

- [ ] **Шаг 1: падающие тесты парсера** (tmp_path, без демо)

```python
# tests/unit/test_folder_config.py — минимум; дополнить по §3
from pathlib import Path
from todoc.application.folder_config import load_folder_configs

def _cfg(root: Path, rel: str, body: str) -> None:
    d = root / rel
    d.mkdir(parents=True)
    (d / ".config.json").write_text(body, encoding="utf-8")

def test_parse_ok_and_alias_normalization(tmp_path):
    _cfg(tmp_path, "ideas/repair", '{"schema_version": 1, "title": "Ремонт", '
         '"aliases": "стройка| ремонт |ванна||стройка", "order": 10}')
    cfgs, diags = load_folder_configs(tmp_path)
    assert cfgs["ideas/repair"].title == "Ремонт"
    assert cfgs["ideas/repair"].aliases == ["стройка", "ремонт", "ванна"]
    assert cfgs["ideas/repair"].order == 10
    assert diags == []

def test_missing_config_is_ok_and_unknown_field_fails_open(tmp_path):
    (tmp_path / "plain").mkdir()
    _cfg(tmp_path, "broken", '{"schema_version": 1, "title": "X", "color": "red"}')
    cfgs, diags = load_folder_configs(tmp_path)
    assert cfgs == {}  # fail-open: не участвует
    assert {d["code"] for d in diags} == {"folder.config.unknown_field"}
    assert diags[0]["location"].get("line") == 1
```

- [ ] **Шаг 2: убедиться, что падает** (`ModuleNotFoundError: todoc.application.folder_config`)
- [ ] **Шаг 3: реализовать `folder_config.py`** — walk с `HARD_EXCLUDE_DIRS`,
  только верхний уровень каждой папки (не рекурсивно внутрь чужих типов —
  rglob запрещён: конфиг ищется как `<dir>/.config.json` при обходе), лимиты
  полей §3, нормализация aliases, диагностики-словари.
- [ ] **Шаг 4: тесты валидатора** — все 7 кодов `folder.*` с локациями
  (`_key_location` для unknown_field/bad_type; line/column от parse_json для
  invalid_json); `duplicate_alias` и `alias_collision` — severity warning;
  интеграция: `validate_dataset` вызывает `validate_folder_configs(root, raw)`
  (raw-тексты читает там же) и мержит с dataset_id/стабильным id — по образцу
  `_skills_diagnostics`.
- [ ] **Шаг 5: убедиться, что падает; реализовать**
- [ ] **Шаг 6: сканер-исключение** — scanner.py:96: `(".todoc.json",)` →
  `(".todoc.json", ".config.json")`; тест: датасет с `.config.json` → его нет
  в `scan`/`validate`-счётчиках документов, `docs search` его не находит.
- [ ] **Шаг 7: полный прогон и коммит**

```bash
.venv/bin/python -m pytest tests/unit/test_folder_config.py tests/unit/test_validator_folder_config.py -v
.venv/bin/todoc validate --root demo --all   # 0 диагностик (конфигов в demo ещё нет)
git add src/todoc/application/folder_config.py src/todoc/adapters/filesystem/scanner.py src/todoc/application/validator.py tests/unit/test_folder_config.py tests/unit/test_validator_folder_config.py
git commit -m "feat(folder-config): парсер+валидация folder.* и исключение .config.json из индекса"
```

### Задача 2: `docs tree` и `explain-path` с `folder_meta`

**Файлы:**
- Modify: `src/todoc/cli.py` (docs tree:1041, explain-path:1090)
- Test: `tests/cli/test_cli_folder_meta.py`

**Интерфейсы:**
- Consumes: `load_folder_configs` (Задача 1).
- Produces: `docs tree [--meta/--no-meta] [--match Q]` — в JSON каждая папка
  получает `"folder_meta": {"title": …, "description": …, "order": …}` (или
  `null`); в table путь печатается как `path — Title: описание(обрезано по 60)`;
  `--match Q` фильтрует папки Фазой A скоринга (score ≥ 0.25, сортировка
  score → order → путь). `explain-path PATH` добавляет блок `folder_meta`
  ближайшей папки из цепочки предков, у которой есть конфиг (сам путь →
  родители → корень).

- [ ] **Шаг 1: падающие CLI-тесты** (house: `init --root` в фикстуре)

```python
# tests/cli/test_cli_folder_meta.py — каркас; дополнить по Produces
def _init(tmp_path):
    _run(CliRunner(), ["init", "--root", str(tmp_path)])

def test_tree_json_folder_meta(tmp_path):
    _init(tmp_path)
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes/.config.json").write_text(
        '{"schema_version": 1, "title": "Заметки", "description": "Рабочие записи", "order": 5}',
        encoding="utf-8")
    d = _json(_run(runner, ["docs", "tree", "--root", str(tmp_path)]))["data"]
    meta = {f["path"]: f.get("folder_meta") for f in d["folders"]}
    assert meta["notes"]["title"] == "Заметки" and meta["notes"]["order"] == 5

def test_tree_match_filters_by_score(tmp_path):
    _init(tmp_path)
    (tmp_path / "ideas/repair").mkdir(parents=True)
    (tmp_path / "ideas/repair/.config.json").write_text(
        '{"schema_version": 1, "title": "Ремонт", "aliases": "ремонт|ванна"}', encoding="utf-8")
    (tmp_path / "misc").mkdir()
    d = _json(_run(runner, ["docs", "tree", "--root", str(tmp_path), "--match", "ремонт ванной"]))["data"]
    paths = [f["path"] for f in d["folders"]]
    assert "ideas/repair" in paths and "misc" not in paths
```

- [ ] **Шаг 2: убедиться, что падает** (нет folder_meta/--match)
- [ ] **Шаг 3: реализовать** — tree: мета из `load_folder_configs`, без
  рекурсивного чтения на каждую папку (один проход на вызов); table-строка с
  тире и обрезкой; `--match` вызывает `score_folder_configs` и оставляет
  только папки-кандидаты; explain-path: подъем по предкам до первого конфига.
- [ ] **Шаг 4: проходят** + существующие tree-тесты не сломались
      (без конфигов вывод прежний).
- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/cli.py tests/cli/test_cli_folder_meta.py
git commit -m "feat(folder-config): docs tree/explain-path с folder_meta и --match (Фаза A)"
```

### Задача 3: команда `docs suggest` (Фаза A скоринга)

**Файлы:**
- Modify: `src/todoc/application/folder_config.py` (`score_folder_configs`)
- Modify: `src/todoc/cli.py` (команда в группе docs)
- Test: `tests/cli/test_cli_docs_suggest.py`

**Интерфейсы:**
- Produces: `todoc docs suggest --root PATH --query Q [--limit N=5] [--output
  json|table]`. JSON: `data: {query, candidates: [{path, title, score, reason,
  order}], discarded: [{path, score}], threshold: 0.25, truncated}`. Скоринг по
  §3 (1.0/0.3/0.2 + бонус длины, нормировка max, порог, tie-break order → путь);
  `reason` называет сработавший компонент (`exact alias «ремонт»`,
  `words: ремонт, ванный (aliases)`, `title: …`). Ошибка пустого запроса —
  `usage.error`.

- [ ] **Шаг 1: падающие тесты** — fixture из 3 конфигов (aliases у одного);
  сценарий идеи: запрос «нужно сохранить идею про ремонт ванной» → ремонт-папка
  сверху с score ≥ 0.8 и reason c alias; папки без совпадений — в `discarded`
  с score < 0.25; запрос-мимо → candidates пуст, discarded все; tie-break:
  равный score → меньший order выше.
- [ ] **Шаг 2: убедиться, что падает** (команды нет)
- [ ] **Шаг 3: реализовать** — скоринг в `folder_config.py` чистой функцией;
  команда — `_emit_ok` c `next_actions` (например, `docs new --dir <папка>`).
- [ ] **Шаг 4: проходят** + детерминизм: два вызова — байт-в-байт вывод.
- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/folder_config.py src/todoc/cli.py tests/cli/test_cli_docs_suggest.py
git commit -m "feat(folder-config): docs suggest — Фаза A скоринга папок по запросу"
```

### Задача 4: `skills tree` — разделы из конфигов

**Файлы:**
- Modify: `src/todoc/cli.py` (skills tree, рядом с `_skills_tree_text`)
- Test: расширить `tests/cli/test_cli_skills_tree.py` (новые тесты не трогают
  старые фикстуры)

**Интерфейсы:**
- Produces: в table строка раздела печатается `имя/ — Title: описание`;
  в JSON навыcx уровня добавляется `"section_meta": {path: {title, description,
  order}}` (только для папок с конфигом); сортировка разделов — `order` → имя;
  `--query` дополнительно матчит title/aliases/description/tags конфига раздела
  (substring, как остальной query).

- [ ] **Шаг 1: падающие тесты** — vault с конфигом раздела: table содержит
  `coding/ — Скилы кодинга:`; без конфига — как раньше; `--query` по alias
  раздела находит скилы внутри; порядок разделов по `order` (process=1 выше
  coding=3).
- [ ] **Шаг 2: убедиться, что падает**
- [ ] **Шаг 3: реализовать** — единый `load_folder_configs(vault_root)` на
  вызов; скилы не трогаются (описание скила — из SKILL.md, §4).
- [ ] **Шаг 4: проходят все skills-тесты.**
- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/cli.py tests/cli/test_cli_skills_tree.py
git commit -m "feat(folder-config): skills tree — заголовки/описания/порядок разделов из .config.json"
```

### Задача 5: буст `docs search` по конфигам папок

**Файлы:**
- Modify: `src/todoc/application/search.py` (после candidates, рядом с :146-148)
- Test: `tests/unit/test_search_folder_boost.py`

**Интерфейсы:**
- Produces: документ, путь которого лежит под папкой с конфигом, получает
  `score += 2`, если слово запроса совпало с токеном title/aliases/tags/description
  этого конфига (низковесный сигнал §3; совпадение с несколькими конфигами
  предков суммируется); существующая метрика не меняется ни для чего другого.

- [ ] **Шаг 1: падающий тест** — два одинаковых по тексту документа под
  `notes/` (с конфигом tags «созвон») и `misc/` (без); запрос «созвон» ставит
  notes-документ выше; запрос-мимо — порядок прежний (буст = 0).
- [ ] **Шаг 2: убедиться, что падает**
- [ ] **Шаг 3: реализовать** — детерминированно: предки пути → конфиги →
  совпадения токенов; ничего не читается дважды (один `load_folder_configs`).
- [ ] **Шаг 4: проходят все поисковые тесты** (в demo до Задачи 6 конфигов нет
  — буст нулевой, старые тесты не меняются).
- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/search.py tests/unit/test_search_folder_boost.py
git commit -m "feat(folder-config): docs search — низковесный буст по конфигам папок-предков"
```

### Задача 6: демо-конфиги и документация

**Файлы:**
- Create: `demo/skills/coding/.config.json`, `demo/skills/docs/.config.json`,
  `demo/skills/process/.config.json` (aliases `"процессы|workflow|релиз|инцидент"`,
  order 1), `demo/plan/.config.json`, `demo/bugs/.config.json`
- Modify: `demo/notes/agent-contract.md` (строка роутинга), `demo/HOME.md`
  (счётчики + упоминание), `README.md` (команда `docs suggest`, формат конфига),
  `demo/plan/folder-config-implementation.md` (§8)

- [ ] **Шаг 1: 5 демо-конфигов** — русские `title` (конвенция), description,
  order (process=1, docs=2, coding=3); план/bugs — без aliases; один конфиг
  намеренно с tags (для буста search).
- [ ] **Шаг 2: сквозная проверка** — `skills tree` печатает разделы с русскими
  заголовками в порядке order; `docs tree` показывает `— Title:`; `docs suggest
  --query "идея про релиз"` → process сверху; `docs search` по тегу даёт буст;
  `validate --root demo --all` — 0 диагностик; `index rebuild` не требуется
  (конфиги вне индекса) — проверить, что счётчики документов не изменились.
- [ ] **Шаг 3: документация** — agent-contract: строка «дерево малопонятно —
  прочитай конфиг раздела: `docs read` по `.config.json`…» (файл читается как
  обычный JSON, отдельная команда не нужна — по идее); HOME: линия про
  `.config.json`; README: формат конфига (таблица полей) + `docs suggest`.
- [ ] **Шаг 4: финал** — pytest, validate 0, linkcheck 0; §8 — запись.
- [ ] **Шаг 5: коммит**

```bash
git add demo README.md
git commit -m "docs(folder-config): демо-конфиги 5 папок + документация (agent-contract, HOME, README)"
```

## 6. Definition of Done

- [ ] Все чекбоксы §5 отмечены; §8 — запись об исполнении с датой.
- [ ] pytest зелёный (1006 + новые); coverage 100% на `folder_config.py` и
      новых ветках cli.py/search.py/validator.py/scanner.py.
- [ ] `validate --root demo --all` — 0 диагностик с 5 конфигами; linkcheck 0.
- [ ] Сценарии идеи воспроизведены: дерево с описаниями; папка без конфига
      как раньше; битый конфиг — диагностика + работа; «релиз» → process
      через alias; коллизия alias — предупреждение и обе папки.
- [ ] `.config.json` не в индексе/поиске/счётчиках (тест).
- [ ] Счётчики README/HOME согласованы с фактом; статусы `done` — только по
      явной фразе пользователя.

## 7. Риски и митигации

| Риск | В×В | Митигация | Владелец |
|---|---|---|---|
| Параллельный мерж пяти планов; doc-tags правит те же веса search.py:146-148 | С×В | порядок: doc-tags → softdoc → folder-config → lifecycle; буст folder — отдельный шаг после candidates, конфликт решается склейкой обеих правок | агент |
| `.config.json` в чьём-то vault скилов платформы (например, внутри superpowers) будет прочитан как конфиг раздела | Н×С | идея: сканер смотрит верхний уровень dir_type-папок; для skills vault — только папки-разделы; конфиг-папка со скилом не мешает (описание скила — SKILL.md) | агент |
| Буст search ломает существующие ожидания ранжирования | С×С | буст только при совпадении токенов конфига; до Задачи 6 конфигов в demo нет — старые тесты зелёные; тест Задачи 5 фиксирует и буст, и его отсутствие | агент |
| Скоринг «навязывает» папку агенту | Н×В | порог 0.25 + discarded + reason; CLI не решает — принцип идеи; зафиксировано в §3 и DoD | агент |
| Fail-open скроет опечатку в поле | С×Н | диагностика error видна в validate; fail-open только на вывод; DoD-сценарий битого конфига | агент |
| Регрессия scanner-исключения (`.todoc.json`-строка) | Н×Н | точечная правка одного кортежа + тест Задачи 1, шаг 6 | агент |
| coverage 100% на CLI-обвязке | Н×С | тесты на каждый флаг (house-паттерн); fallback pragma с обоснованием в §8 | агент |

## 8. Прогресс и отклонения

- Статус: не начат (2026-11-25). Первая задача — Задача 1, шаг 1.
- 2026-11-25 — план создан из идеи folder-config (doc:folder-config-idea) по
  итогам аудита кода: сканер пропускает только `.todoc.json` (scanner.py:96) —
  исключение `.config.json` вошло в Задачу 1; `folders` уже в индексном payload
  (Folder.to_dict — path/parent/dir_type), мета крепится на выводе, индекс не
  расширяется (P1); `_key_location` (validator.py:471) готов для локаций полей;
  `docs tree` лимитирует 50 папок (cli.py:1058) — конфиги читаются одним
  проходом на вызов. Фаза B вынесена за скоуп с gate-условием; открытые вопросы
  идеи закрыты (§4). Отклонений нет.

<!-- Формат строки отклонения: `YYYY-MM-DD — задача N, шаг M: что не так → что
     выбрано вместо и почему`. Шаги задним числом не переписывать. -->
