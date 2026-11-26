---
id: doc:plan-agent-state
title: "Агентский стейт: state.json в движке (v1 — текущий проект)"
doc_type: plan
lang: ru
status: done
created: 2026-11-26
updated: 2026-11-26
tags: [plan, агентский, текущий]
related: ["[[agent-state]]"]
---

# Агентский стейт: state.json в движке (v1 — текущий проект) — план реализации

> **Исполнителю (агенту):** план самодостаточен — читай его, а не историю сессии.
> Работай по задачам сверху вниз; шаги отмечаются чекбоксами (`- [ ]`) в том же
> коммите, который делает шаг. Начинай всегда с первого неотмеченного.

**Цель:** движок хранит рабочее состояние сессий (v1 — `context.current_project`)
в файле вне данных и пишет/читает его командами `todoc state set/get/list/unset`.
**Спека:** `demo/ideas/agent-state.md` (разделы «Предложение», «План изменений» фазы 1–2, «План CLI»).
**Стек:** Python 3.11, click (существующий `@cli` group), pytest/CliRunner, без новых зависимостей.

## 1. Критерии успеха

1. `todoc state set --root demo context.current_project shop` → JSON `{"ok": true, ...}`;
   повторный `state get --root demo context.current_project` возвращает `shop`.
2. Файл создаётся вне репозитория: `~/.local/state/todoc/state-<dataset_id>.json`
   (уважает `XDG_STATE_HOME`); `git status` демо чист после set/get.
3. `todoc state set --root demo foo.bar x` → ошибка `state.unknown_key`, код возврата ≠ 0.
4. `pytest` зелёный (1084 + ~10–15 новых), покрытие нового кода 100%; `validate --root demo --all` — 0 диагностик; метрики README согласованы по факту (урок BUG-003).

## 2. Вне скоупа

- Фазы 3–5 идеи agent-state: скоуп поиска по стейту, `project use/show`,
  `state snapshot`/`doctor`, секции session/queue/review/env/sync — отдельные циклы.
- Глобальный стейт (между датасетами) — не делаем.
- Никакой записи в данные демо: state.json не в Git, счётчики документов не трогаем.

## 3. Глобальные ограничения

- Запись только атомарно: переиспользовать `atomic_write(path, content: str | bytes)`
  из `src/todoc/adapters/filesystem/scanner.py` (mkstemp + os.replace, сам создаёт
  родительский каталог) — не писать новое.
- Ключи — белый список v1: `("context.current_project",)`; расширение = правка
  списка, не формата файла.
- Значение — строка ≤256 символов; файл ≤64 КБ, ≤200 ключей.
- Ошибки — по конвенции движка: `TodocError`/`ValidationError` с кодами
  `state.*`; CLI возвращает не-ноль и JSON с диагностикой.
- Стиль кода и тестов — как в соседних модулях `application/`; coverage 100%
  (проектное правило).

## 4. Архитектура и файловая карта

Ядро без click (тестируемо unit-тестами) + тонкая CLI-обвязка:

- Create `src/todoc/application/state.py` — путь к файлу, load/save, set/get/unset,
  валидация ключей/лимитов. Единственная зависимость — stdlib + `atomic_write`.
- Modify `src/todoc/cli.py` — click-группа `state` с 4 подкомандами; `--root`
  → `_contexts(roots)[0]` → `ctx.dataset_id` (уже читает `<root>/.todoc/dataset.json`);
  вывод через `_emit_ok(data, output, out, next_actions=…)`;
  `TodocError` ловится общим обработчиком — конверт с диагностикой, exit ≠ 0.
- Create `tests/unit/test_state.py` — ядро: отсутствующий файл, whitelist, лимиты,
  атомарность, `XDG_STATE_HOME` через monkeypatch + tmp_path.
- Create `tests/cli/test_cli_state.py` — команды через `CliRunner`.

## 5. Задачи

### Задача 1: хранилище стейта

**Файлы:**
- Create: `src/todoc/application/state.py`
- Test: `tests/unit/test_state.py`

**Интерфейсы:**
- Consumes: `atomic_write(path: Path, content: str) -> None` (adapters/filesystem/scanner.py).
- Produces: `state_path(dataset_id: str) -> Path`;
  `load_state(dataset_id: str) -> dict`;
  `set_var(dataset_id: str, key: str, value: str, *, now: str | None = None) -> dict`;
  `get_var(dataset_id: str, key: str) -> str | None`;
  `unset_var(dataset_id: str, key: str) -> bool`;
  константа `ALLOWED_KEYS_V1: tuple[str, ...] = ("context.current_project",)`.
  Ошибки: `state.unknown_key`, `state.invalid_value`, `state.limit_exceeded`,
  `state.file_unavailable`.

- [x] **Шаг 1: написать падающие тесты** (контракт из Produces выше)

```python
def test_set_get_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    set_var("dataset-x", "context.current_project", "shop", now="2026-11-25T00:00:00Z")
    assert get_var("dataset-x", "context.current_project") == "shop"

def test_unknown_key_rejected(tmp_path, monkeypatch):
    from todoc.errors import ValidationError  # match матчит message, код — в e.value.code
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    with pytest.raises(ValidationError) as err:
        set_var("dataset-x", "foo.bar", "x")
    assert err.value.code == "state.unknown_key"

def test_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert get_var("dataset-x", "context.current_project") is None
```

- [x] **Шаг 2: убедиться, что тесты падают**

Run: `python -m pytest tests/unit/test_state.py -v`
Expected: FAIL/ERROR — модуля `todoc.application.state` не существует

- [x] **Шаг 3: реализовать `state.py`** — сигнатуры из Produces; файл
  `{"schema_version": 1, "vars": {...}, "updated_at": ISO-8601 UTC}`;
  ключ проверяется по `ALLOWED_KEYS_V1` → `ValidationError("...", "state.unknown_key")`;
  значение — `str`, 1–256 символов → `state.invalid_value`; >200 ключей или файл
  >64 КБ → `state.limit_exceeded`; запись `atomic_write`
  (родительский каталог создаёт сама); недоступный путь → `state.file_unavailable` с путём в сообщении.

- [x] **Шаг 4: убедиться, что тесты проходят**

Run: `python -m pytest tests/unit/test_state.py -v`
Expected: PASS — все тесты нового файла

- [x] **Шаг 5: коммит**

```bash
git add src/todoc/application/state.py tests/unit/test_state.py
git commit -m "feat(state): ядро хранилища стейта (set/get/unset, whitelist v1, атомарная запись)"
```

### Задача 2: CLI-группа `state`

**Файлы:**
- Modify: `src/todoc/cli.py` (блок после существующих команд; группа `state`)
- Test: `tests/cli/test_cli_state.py`

**Интерфейсы:**
- Consumes: `set_var/get_var/unset_var/load_state` из Задачи 1;
  `_emit_ok(data, output, out, next_actions=…)` и паттерн групп
  `@cli.group()` → `@<группа>.command("…")` с опциями `--root/--output/--no-input`
  (как у `change`/`docs`); `dataset_id` — `ctx.dataset_id` из `_contexts(roots)[0]`.
- Produces: `todoc state set <key> <value>`, `state get <key>`,
  `state list [--prefix <секция>]`, `state unset <key>` — все с
  `--root/--output json/--no-input` (конвенция движка). Имя группы `state`
  свободно — конфликтов с 26 существующими командами нет (проверено `--help`).

- [x] **Шаг 1: написать падающие CLI-тесты**

```python
import json
from click.testing import CliRunner
from todoc.cli import cli
from todoc.errors import TodocError

def _run(runner, args):  # house-паттерн (tests/cli/test_cli.py)
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result

def test_state_set_get_roundtrip(tmp_path, monkeypatch):
    runner = CliRunner()
    assert _run(runner, ["init", "--root", str(tmp_path), "--no-input"]).exit_code == 0
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    r1 = _run(runner, ["--root", str(tmp_path), "state", "set",
                       "context.current_project", "shop"])
    assert r1.exit_code == 0, r1.output
    assert json.loads(r1.output)["data"]["ok"] is True
    r2 = _run(runner, ["--root", str(tmp_path), "state", "get", "context.current_project"])
    assert json.loads(r2.output)["data"]["value"] == "shop"
```

- [x] **Шаг 2: убедиться, что тесты падают**

Run: `python -m pytest tests/cli/test_cli_state.py -v`
Expected: FAIL — команды `state` нет (exit_code != 0, «No such command»)

- [x] **Шаг 3: реализовать группу `state` в `cli.py`** — `@cli.group("state")` с 4
  подкомандами; `--root` мульти-конвенция как у соседних команд; `dataset_id`
  читается из `.todoc/dataset.json` (нет файла → существующая ошибка инициализации);
  вывод: set → `{ok, key, value, updated_at}`, get → `{ok, key, value|null}`,
  list → `{ok, vars}`, unset → `{ok, key, removed}`; `TodocError` → стандартная
  JSON-диагностика с кодами `state.*` и не-нулевым кодом возврата.

- [x] **Шаг 4: убедиться, что тесты проходят и ничего не сломано**

Run: `python -m pytest tests/cli/test_cli_state.py tests/cli -v`
Expected: PASS — новые и существующие CLI-тесты

- [x] **Шаг 5: коммит**

```bash
git add src/todoc/cli.py tests/cli/test_cli_state.py
git commit -m "feat(state): CLI-группа state set/get/list/unset с JSON-выводом"
```

### Задача 3: синхронизация счётчиков и проверка демо

**Файлы:**
- Modify: `README.md` (строка «| Команд CLI | 26 |»),
  `demo/references/state/03-cli-reference.md` (title «26 команд» + новая
  секция `### state …` в «## Команды»)
- Test: ручная проверка командами ниже (данные демо не меняются)

**Интерфейсы:**
- Consumes: фактическое число команд `todoc --help`.
- Produces: согласованные счётчики в 3 файлах.

- [x] **Шаг 1: пересчитать и обновить счётчики** (26 → 30 после +4 подкоманд;
  26 подтверждено аудитом: `todoc --help` и README.md)

Run: `todoc --help | sed -n '/Commands:/,$p' | grep -c "^  [a-z]"`; править все
вхождения счётчика (`grep -rn "Команд CLI\|команд" README.md demo/references/state/`)
Expected: одно и то же число в README и 03-cli-reference

- [x] **Шаг 2: убедиться, что демо не затронуто**

Run: `git status --short demo/` и `todoc validate --root demo --all`
Expected: `demo/` чист, 0 диагностик

- [x] **Шаг 3: полный прогон**

Run: `coverage run -m pytest && coverage report`
Expected: все тесты зелёные, покрытие 100%, 0 пропусков

- [x] **Шаг 4: коммит**

```bash
git add README.md demo/references/state/03-cli-reference.md
git commit -m "docs: счётчики CLI после добавления группы state"
```

## 6. Definition of Done

- [x] Все чекбоксы задач 1–3 отмечены; каждая задача уехала отдельным коммитом.
- [x] `pytest` — все зелёные (1084 + 10–15 новых); новый код — 100% покрытие;
      метрики README (тесты/покрытие) синхронизированы по факту.
- [x] `todoc state set/get/list/unset` работают на демо; файл стейта вне репозитория;
  `git status demo/` чист.
- [x] `state.unknown_key` на чужом ключе; не-ноль exit; JSON-диагностика.
- [x] `todoc validate --root demo --all` — 0 диагностик; счётчики CLI согласованы (README + 03-cli-reference).
- [x] Спека (идея agent-state, фазы 1–2 и «План CLI») покрыта задачами — пробелов нет.

## 7. Риски и митигации

| Риск | В×В | Митигация | Владелец |
|---|---|---|---|
| `~/.local/state` недоступен (права/sandbox) | В×Н | код `state.file_unavailable` с путём; тест read-only каталогом (chmod 0o500); в CI под root chmod не блокирует — skipif uid==0, альтернатива: путь, у которого «каталог» — файл | агент |
| Два корня с одним dataset_id делят стейт | Н×Н | by design (keyed по dataset_id); задокументировано в идее | агент |
| Параллельные записи двух процессов | Н×С | `atomic_write` (tmp+rename) — атомарная замена, «последний выигрывает»; задокументировано | агент |
| Отсутствует `.todoc/dataset.json` в root | С×Н | существующая ошибка инициализации CLI, новый код не вводится | агент |

## 8. Прогресс и отклонения

- Статус: не начат (2026-11-25). Первая задача — Задача 1, шаг 1.
- fm `status: done` — явная фраза пользователя «закрой все планы и в идеях пометку сделай» (2026-11-26).
- 2026-11-25 — финальный аудит перед реализацией (якоря сверены с кодом,
  план пополнен — шаги не переписывались, правки только уточняющие):
  (1) Consumes Задачи 2 давал сигнатуру `_emit_ok(payload, output, next_actions)` —
  фактическая `_emit_ok(data, output, out, diagnostics=None, next_actions=None)`
  (cli.py, `out` обязателен); сниппет CLI-теста переписан на house-паттерн
  (`CliRunner` + `_run` с TodocError→exit_code + `json.loads(result.output)` —
  у CliRunner нет `.json`, хелпер `_init_dataset` не существует — init через CLI);
  (2) `pytest.raises(..., match=…)` матчит сообщение, а не код — сниппет Задачи 1
  переведён на `err.value.code` (импорт `todoc.errors.ValidationError`);
  (3) `atomic_write` принимает `str | bytes` и сам создаёт родительский каталог —
  отдельный mkdir в state.py не нужен; (4) `dataset_id` — из `ctx.dataset_id`
  (`_contexts(roots)[0]`), ручное чтение dataset.json не требуется;
  (5) счётчик команд фактически живёт в README.md («| Команд CLI | 26 |») и title
  `demo/references/state/03-cli-reference.md` («26 команд»), а не в docs/state/*;
  Задача 3 переписана: README + 03-cli-reference (26 → 30), в справочник добавляется
  секция `### state …`; (6) числа тестов актуализированы: 437 → 1084;
  (7) имя группы `state` свободно (26 команд подтверждены `todoc --help`);
  (8) chmod-тест: песочница не под root, но для CI добавлен skipif uid==0
  (альтернатива — «каталог»-файл); (9) у четырёх неисполненных планов записей в
  demo/records нет — это конвенция, запись плана не создаётся. Отклонений
  семантики идеи нет: фазы 1–2 покрывают все задачи, DoD полон.


- 2026-11-25 — план исполнен (Задачи 1–3, TDD, коммит на задачу: ac205c8 / 2de546c /
  закрывающий). pytest 1117 зелёных по замеру (+25 state-тестов: 18 unit + 7 CLI);
  state.py — 100% покрытие; непокрытое в cli.py — старые ветки docs links (вне
  скоупа). Отклонение Задачи 3, шаг 1: план ожидал 26→30 (+4 подкоманды как
  отдельные строки счётчика), фактически счётчик «Команд CLI» — верхний уровень
  `--help` (группы и одиночные команды) — 26→27; подкоманды видны в `state --help`
  и внесены отдельной секцией справочника. Урок BUG-003 применён: числа README от
  замера (тесты 1084→1117, покрытие 5186→5300 инструкций / 1920→1932 веток, 99%).
  Приёмы file_unavailable: «каталог»-файл (NotADirectoryError ⊂ OSError — работает
  и под root) для load/mkstemp + chmod 0o500 для ветки _save (uid 1001). Демо-данные
  не затронуты; validate 0. Фазы 3–5 идеи — вне скоупа v1.
<!-- Формат строки отклонения: `YYYY-MM-DD — задача N, шаг M: что не так → что
     выбрано вместо и почему`. Шаги задним числом не переписывать. -->
