---
id: doc:plan/multi-project-workspace.md
title: "Мульти-проектное рабочее пространство: projects/*, системный проект core и параллельный скоуп CLI (план реализации)"
doc_type: plan
lang: ru
status: active
tags: [plan, projects, workspace, scope, cli, state, harness, migration]
related: ["[[multi-project-workspace]]", "[[agent-state]]", "[[folder-config]]", "[[skills-engine]]", "[[type-naming-and-state-dir]]"]
derived_from: ["ideas/multi-project-workspace.md@sha256:f96d3df175b41018eee2c1bf06aefb6a798f5ba8cfb541189eac7edff5a9c10b"]
created: 2026-11-28
updated: 2026-11-28
---

# Мульти-проектное рабочее пространство: projects/*, системный проект core и параллельный скоуп CLI (план реализации) — план реализации

> **Исполнителю (агенту):** план самодостаточен — читай его, а не историю сессии.
> Работай по задачам сверху вниз; шаги отмечаются чекбоксами (`- [ ]`) в том же
> коммите, который делает шаг. Начинай всегда с первого неотмеченного.

**Цель:** ввести единый закон `<DATA_ROOT>/projects/<slug>/` с системным проектом `core`, мульти-проектным стейтом `context.projects` и сквозным скоупом CLI, чтобы поиск, списки, запись и харнес работали параллельно по связке проектов и никогда не смешивали закрытые проекты.
**Спека:** [Идея: мульти-проектное рабочее пространство](../ideas/multi-project-workspace.md) (`doc:ideas/multi-project-workspace.md`), хеш `sha256:f96d3df175b41018eee2c1bf06aefb6a798f5ba8cfb541189eac7edff5a9c10b`.
**Стек:** Python 3.11+, `click` 8.1, стандартная библиотека, `pytest`/`CliRunner`; новых runtime-зависимостей нет. Индекс — существующий JSON-снапшот `RegistryStore` (не SQLite).

## 1. Критерии успеха

1. Датасет раскладки `projects/<slug>/` открывается и валидируется: `projects` — контейнер (`dir_type: projects`), `projects/<slug>` — `dir_type: project`, `projects/<slug>/harness` — `dir_type: harness`; `todoc validate --root <root> --all` — `0` ошибок; старый плоский датасет (`demo/`) открывается без изменений и получает `layout: legacy_flat`.
2. `todoc project use billing auth --with-related` пишет `context.current_project=billing` и `context.projects=core|billing|auth`; `todoc project show` возвращает `focus_project`, `active_projects`, `layout`, `scope_source`; `TODOC_PROJECT`/`TODOC_PROJECTS` перекрывают `state.json`, флаги CLI перекрывают переменные окружения.
3. Каждая выборка (`docs list`, `docs search`, `docs tree`, `records list`, `records query`, `stale`) ограничена активными проектами; каждый элемент несёт поле `project`; результат **всегда** сгруппирован: `result.groups = [{project, total, items}]` в порядке `focus → остальные active → core`; закрытые проекты не попадают в `items`, но при нулевой выдаче движок подсказывает `todoc project add <slug>`. `relations graph` для закрытого узла отдаёт `result.boundary` и не раскрывает подграф.
4. Запись защищена: создание в раскладке `projects/` без фокуса даёт `project.not_selected`; короткий путь разворачивается в `projects/<focus>/...`; правка `projects/core/**` без фокуса `core` даёт `project.core_readonly`; правка закрытого проекта — `project.out_of_scope`; новые `record_id` получают префикс `<type>:<project>-<slug>`, а `path_template` — префикс `projects/<focus>/`.
5. Каскадный харнес работает: `skills tree` собирает `focus → active → core`, одноимённый скил верхнего слоя перекрывает нижний (`shadowed_by`), `disabled_harness` проекта скрывает указанные элементы; `todoc project migrate-flat --preview/--apply` переносит плоский датасет в `projects/core/` + `projects/<slug>/` с автоправкой локальных ссылок.
6. Гейты: полный `pytest` зелёный, `100%` branch coverage по `src/todoc`, `todoc validate --root demo --all` — `0` ошибок, `todoc check-config --root demo` — `0` ошибок, `tools/linkcheck.py` — `0` битых ссылок.

## 2. Вне скоупа

- **SQLite-драйвер и FTS5/BM25.** Идея ссылается на `index.sqlite` из [`sqlite-storage-drivers`](../ideas/sqlite-storage-drivers.md), но драйвер в коде отсутствует. План добавляет поле `project` в строки JSON-снапшота и фильтрует в Python; SQLite-колонка `items.project` с индексами — отдельная волна.
- **Публичный `todoc docs move`.** Команды нет; её активный план — [docs-move-implementation](docs-move-implementation.md) (`src/todoc/application/move.py`: `plan_move`, `apply_move`). Задача 17 переиспользует этот движок и выполняется после его влития; второй движок ссылок не создаётся.
- **`todoc tags` и `todoc tree`.** Команд нет; скоуп применяется к существующим `--tag/--tag-in/--tag-all` у `docs`/`records` и к `docs tree`. Новые команды тегов — из [`unified-tags-and-tag-graph`](../ideas/unified-tags-and-tag-graph.md).
- **`rules disable/enable` и `--include-disabled`.** Команд нет. План только хранит, валидирует и учитывает `disabled_harness`; переключение `enabled` в файлах правил — из [`toggleable-rules`](../ideas/toggleable-rules.md), отдельная волна.
- **Автоподключение `related_projects`.** Решение пользователя (2026-11-28): связанные проекты подключаются только явным `--with-related`.
- **Жёсткий лимит числа проектов.** Решение пользователя (2026-11-28): вместо warning при `>5` проектов каждый результат обязан показывать `project` и группироваться по проектам.
- **`docs flow render --write` и витрины флоу.** Пишут в корневые `flows/`; перенос витрин в `projects/<p>/harness/flows/` — отдельная задача после появления `dir_type` для флоу.
- **Переименование и слияние проектов.** `migrate-flat` только переносит файлы и правит локальные ссылки; смысловые переименования — вручную.
- **Веб-интерфейс, фоновые процессы, сеть.** Только локальный CLI и файлы.

## 3. Глобальные ограничения

- Файлы — источник истины; индекс и кэш — производные и пересобираемые (`P1`).
- Новых runtime-зависимостей нет: только `click` 8.1 и стандартная библиотека.
- Все пути в снапшоте и ответах CLI — POSIX-относительные от `DATA_ROOT`.
- Идентификаторы: `doc:<rel-path>`, `folder:<rel-path>`, `record_id` — `<entity_type>:<slug>`; в проектах — `<entity_type>:<project>-<slug>`.
- `created`/`updated` в front matter ставит движок; руками не править.
- Мутация review-first: `--preview` по умолчанию, `--apply` с `--if-plan-hash`/`--if-hash` там, где это уже принято.
- Ошибки — `ValidationError(message, code)`; коды `project.*` и `layout.*` добавляются в guidance и покрываются контрактными тестами.
- `100%` branch coverage по `src/todoc` — проектное правило.
- Плоский датасет ведёт себя как раньше: `project` равен `None`, скоуп не фильтрует.
- `--all-projects` — только чтение; на мутирующих командах он отвергается кодом `project.all_projects_readonly`.

## 4. Архитектура и файловая карта

Подход: принадлежность пути к проекту вычисляется один раз (`project_of`) и попадает в снапшот; резолвер `EffectiveScope` сводит флаги CLI → env → `state.json` → дефолт; единый фильтр применяется к выборкам, запись проверяет фокус и защиту `core`. Группировка по проектам — свойство конверта коллекции: `result.groups` строится всегда, когда `scope.layout == "projects"`.

**Решения по открытым вопросам идеи (закрыты 2026-11-28):**
- `related_projects` подключаются только по `--with-related`; без флага `project use` печатает подсказку о связанных проектах.
- Вместо warning при `>5` активных проектах — обязательное поле `project` и группировка `result.groups`.

**Интерфейсы (единый контракт для всех задач):**

```python
Layout = Literal["projects", "legacy_flat"]

def project_of(rel_path: str) -> str | None: ...
def dataset_layout(root: Path) -> Layout: ...

@dataclass(frozen=True)
class EffectiveScope:
    layout: Layout
    focus_project: str | None
    active_projects: tuple[str, ...]
    source: str          # "cli" | "env" | "state" | "default"
    all_projects: bool = False

def parse_projects(value: str) -> tuple[str, ...]: ...
def resolve_scope(root: Path, dataset_id: str, *, project: str | None = None,
                  projects: str | None = None, all_projects: bool = False,
                  no_core: bool = False,
                  env: Mapping[str, str] | None = None) -> EffectiveScope: ...
def scope_allows(scope: EffectiveScope, project: str | None) -> bool: ...
def project_rank(scope: EffectiveScope, project: str | None) -> tuple[int, str]: ...
def group_by_project(items: list[dict[str, Any]],
                     scope: EffectiveScope) -> list[dict[str, Any]]: ...
def namespace_record_id(record_id: str, project: str | None) -> str: ...
def resolve_new_path(scope: EffectiveScope, rel_path: str) -> str: ...
def ensure_writable(scope: EffectiveScope, rel_path: str, *,
                    explicit_core: bool = False) -> None: ...
def scoped_link_candidates(source_path: str, candidates: list[str]) -> list[str]: ...
```

**Семантика `scope_allows`:**
- `scope.all_projects` → `True` для любого проекта;
- `project is None` → `True` только при `scope.layout == "legacy_flat"`;
- иначе → `project in scope.active_projects`.

**Новые файлы:**
- `src/todoc/application/project_scope.py` — весь блок интерфейсов выше, кроме `ensure_writable`/`resolve_new_path` (они тоже здесь).
- `src/todoc/application/migrate.py` — `plan_migration`, `apply_migration` поверх `move.py`.
- `demo/.todoc/dir_types/project/type.json` — дескриптор `dir_type: project`.
- `tests/unit/test_project_scope.py`, `tests/unit/test_project_rules.py`, `tests/unit/test_migrate.py`, `tests/cli/test_cli_project.py`.

**Изменяемые файлы:**
- `src/todoc/config.py:53-66` — `default_directory_rules`; `src/todoc/config.py:166-173` — `init_dataset` создаёт `dir_types/projects` и `dir_types/project`.
- `src/todoc/application/state.py:24` — whitelist `context.projects`.
- `src/todoc/application/folder_config.py:26-45,105-210` — `related_projects`, `disabled_harness`.
- `src/todoc/domain/models.py:53-101` — `Folder`/`Document`; `:103-140` — `Record`; `:140-170` — `SearchHit` не меняется (проект добавляется в CLI).
- `src/todoc/service.py:45-150` — `layout`, поле `project` в строках снапшота.
- `src/todoc/application/documents.py:7-86` — `FIELDS`, `project`, порядок по проекту.
- `src/todoc/application/search.py:126-230` — `scope`, `project` в хитах.
- `src/todoc/application/skills.py` — `scan_skill_layers`, `shadowed_by`.
- `src/todoc/application/validator.py:56-150,360-400,729-757` — `scoped_link_candidates`, `layout.outside_projects`, per-project skills.
- `src/todoc/application/write.py:63-109` — `project` в `create_record_plan`.
- `src/todoc/application/changes.py:47-110,614-660` — `changes_dirs`, поиск изменения по проектам.
- `src/todoc/output/envelope.py:20-45` — `groups` в `Envelope.collection`.
- `src/todoc/cli.py` — группа `project`, `scope_options`, блок `scope`, группировка, защита записи.
- `demo/.todoc/rules/directory-rules.json:202-212`, `demo/.todoc/rules/document-rules.json` — глубинные маски.
- `demo/notes/agent-contract.md`, `demo/HOME.md`, `README.md` — контракт и карта.

## 5. Задачи

### Фаза 1 — Геометрия и типы

### Задача 1: `project_of` и поле `project` в снапшоте

**Файлы:**
- Create: `src/todoc/application/project_scope.py`
- Modify: `src/todoc/domain/models.py:53-101` (`Folder`, `Document`), `src/todoc/domain/models.py:103-140` (`Record`)
- Modify: `src/todoc/service.py:73-150` (папки, документы, записи)
- Test: `tests/unit/test_project_scope.py`

**Интерфейсы:**
- Consumes: ничего.
- Produces: `project_of(rel_path: str) -> str | None`; поля `project` в `Folder.to_dict()`, `Document.to_dict()`, `Record.to_dict()`; строки `folders/documents/records` снапшота содержат `"project": <slug> | None`.

- [ ] **Шаг 1: написать падающий тест**

```python
from todoc.application.project_scope import project_of


def test_project_of_reads_first_segment_after_projects():
    assert project_of("projects/billing/specs/api.md") == "billing"
    assert project_of("projects/core/harness/rules/x.md") == "core"
    assert project_of("projects/billing") == "billing"


def test_project_of_is_none_outside_projects_and_for_container():
    assert project_of("ideas/retry.md") is None
    assert project_of("projects") is None
    assert project_of(".") is None
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_project_scope.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'todoc.application.project_scope'`

- [ ] **Шаг 3: реализовать `project_of` и добавить поле в модели**

`project_of` разбирает путь через `PurePosixPath`, возвращает `parts[1]`, если `parts[0] == "projects"` и длина ≥ 2, иначе `None`. В моделях добавить `project: str | None = None` и включить в `to_dict()`. В `service.py` при сборке `folders`, `documents`, `records` передавать `project=project_of(rel_path)`.

- [ ] **Шаг 4: убедиться, что тест проходит**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_project_scope.py -v`
Expected: PASS (2 passed)

- [ ] **Шаг 5: проверить снапшот и закоммитить**

Run: `env PYTHONPATH=src python3 -m todoc index rebuild --root demo --apply`, затем `env PYTHONPATH=src python3 -m pytest tests/unit/test_scanner_registry.py -q`
Expected: PASS; в `demo/.todoc/index/current/documents.json` у всех элементов `project: null`.

```bash
git add src/todoc/application/project_scope.py src/todoc/domain/models.py src/todoc/service.py tests/unit/test_project_scope.py
git commit -m "feat(projects): compute project for snapshot rows"
```

### Задача 2: `dir_type: project`, глубинные маски и дефолты `init_dataset`

**Файлы:**
- Create: `demo/.todoc/dir_types/project/type.json`
- Modify: `demo/.todoc/rules/directory-rules.json:202-212` (`demo-dir-projects-subdirs`)
- Modify: `demo/.todoc/rules/document-rules.json` (корневые glob-правила)
- Modify: `src/todoc/config.py:53-66` (`default_directory_rules`)
- Modify: `src/todoc/config.py:166-173` (`init_dataset` создаёт `projects` и `project`)
- Test: `tests/unit/test_project_rules.py`

**Интерфейсы:**
- Consumes: `resolve_type`, `load_rules`, `init_dataset`.
- Produces: `projects` → `dir_type: projects`; `projects/<slug>` → `dir_type: project`; правила `**/specs/**`, `**/flows/**`, `**/contracts/**`, `**/reports/**`, `**/ops/**`, `**/rules/**` работают на любой глубине; свежий датасет сразу знает оба типа.

- [ ] **Шаг 1: написать падающий тест**

```python
from pathlib import Path

from todoc.config import init_dataset, load_dataset, load_rules
from todoc.typing_system.resolver import RESERVED_DIR_TYPES, resolve_type

DEMO = Path(__file__).resolve().parents[2] / "demo"


def _dir_type(root: Path, path: str) -> str:
    rules, _ = load_rules(root, load_dataset(root))
    resolved, _source, conflicts = resolve_type(
        rules, path, Path(path).name, None, "dir_type", RESERVED_DIR_TYPES, "unknown")
    assert conflicts == []
    return resolved


def test_demo_projects_layout_types():
    assert _dir_type(DEMO, "projects") == "projects"
    assert _dir_type(DEMO, "projects/billing") == "project"
    assert _dir_type(DEMO, "projects/billing/harness") == "harness"
    assert _dir_type(DEMO, "projects/billing/specs") == "specs"


def test_fresh_dataset_has_projects_types(tmp_path):
    root = tmp_path / "kb"
    root.mkdir()
    init_dataset(root, dataset_id="dataset-projects")
    assert _dir_type(root, "projects") == "projects"
    assert _dir_type(root, "projects/billing") == "project"
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_project_rules.py -v`
Expected: FAIL — `projects/billing` возвращает `unknown`.

- [ ] **Шаг 3: добавить дескриптор, правила и дефолты**

`demo/.todoc/dir_types/project/type.json`:

```json
{
  "schema_version": 1,
  "type_id": "project",
  "version": "0.1",
  "kind": "dir_type",
  "description": "Проект: папка projects/<slug>/ с паспортом .config.json и собственным харнесом."
}
```

В `demo/.todoc/rules/directory-rules.json` заменить `demo-dir-projects-subdirs` на:

```json
{
  "id": "demo-dir-projects-subdirs",
  "match": {"kind": "directory", "glob": "projects/*"},
  "assign": {"dir_type": "project"},
  "priority": 110
}
```

В `document-rules.json` заменить корневые маски на глубинные: `contracts/**` → `**/contracts/**`, `flows/**` → `**/flows/**`, `ops/postmortems/**` → `**/ops/postmortems/**`, `ops/runbooks/**` → `**/ops/runbooks/**`, `specs/**` → `**/specs/**`, `reports/**` → `**/reports/**`, `architecture/**` → `**/architecture/**`, `attachments/**` → `**/attachments/**`, `bugs/**` → `**/bugs/**`, `competitors/**` → `**/competitors/**`, `glossary/**` → `**/glossary/**`, `guides/**` → `**/guides/**`, `notes/**` → `**/notes/**`, `plan/after/**` → `**/plan/after/**`, `records/**` → `**/records/**`, `references/**` → `**/references/**`, `skill/**` → `**/skill/**`, `skills/**/SKILL.md` → `**/skills/**/SKILL.md`.

В `src/todoc/config.py`:
- в `default_directory_rules()` добавить правила `reserved-projects` (`basename: projects` → `projects`, priority 100) и `projects-subdirs` (`glob: projects/*` → `project`, priority 110);
- в `init_dataset` добавить `"projects"` и `"project"` в кортеж создаваемых `dir_types` (строка 166).

- [ ] **Шаг 4: убедиться, что тест проходит и демо не сломалось**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_project_rules.py -q`
Expected: PASS (2 passed)

Run: `env PYTHONPATH=src python3 -m todoc validate --root demo --all && env PYTHONPATH=src python3 -m todoc check-config --root demo`
Expected: `0` ошибок в обеих командах.

- [ ] **Шаг 5: коммит**

```bash
git add demo/.todoc/dir_types/project/type.json demo/.todoc/rules src/todoc/config.py tests/unit/test_project_rules.py
git commit -m "feat(projects): project dir type, depth-independent masks and init defaults"
```

### Задача 3: паспорт проекта — `related_projects` и `disabled_harness`

**Файлы:**
- Modify: `src/todoc/application/folder_config.py:26-45` (`_KNOWN_FIELDS`, `FolderConfig`)
- Modify: `src/todoc/application/folder_config.py:105-210` (разбор конфига)
- Test: `tests/unit/test_folder_config.py`

**Интерфейсы:**
- Consumes: `load_folder_configs(root)`.
- Produces: `FolderConfig.related_projects: tuple[str, ...]`, `FolderConfig.disabled_harness: tuple[str, ...]`; невалидные значения дают существующий код `folder.config.bad_type`; неизвестный id в `disabled_harness` — `folder.config.unknown_harness_id` уровня `warning` (проверка в задаче 15).

- [ ] **Шаг 1: написать падающий тест**

```python
import json

from todoc.application.folder_config import load_folder_configs


def test_project_config_reads_related_and_disabled(tmp_path):
    folder = tmp_path / "projects" / "billing"
    folder.mkdir(parents=True)
    (folder / ".config.json").write_text(json.dumps({
        "schema_version": 1,
        "title": "Billing",
        "related_projects": ["auth", "gateway"],
        "disabled_harness": ["doc:projects/core/harness/rules/strict-english-commits.md"],
    }), encoding="utf-8")

    configs, diags = load_folder_configs(tmp_path)
    config = configs["projects/billing"]
    assert config.related_projects == ("auth", "gateway")
    assert config.disabled_harness == ("doc:projects/core/harness/rules/strict-english-commits.md",)
    assert diags == []
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_folder_config.py -k related_and_disabled -v`
Expected: FAIL — `AttributeError: 'FolderConfig' object has no attribute 'related_projects'`

- [ ] **Шаг 3: расширить `_KNOWN_FIELDS` и разбор**

Добавить в `_KNOWN_FIELDS` ключи `related_projects`, `disabled_harness`. В `FolderConfig` — поля-кортежи. В разборе:
- `related_projects` — список строк по regex `^[a-z0-9]+(-[a-z0-9]+)*$`; иначе `_bad("related_projects", ...)`;
- `disabled_harness` — список строк, каждая начинается с `doc:`; иначе `_bad("disabled_harness", ...)`.

Невалидный конфиг, как и раньше, исключается из `configs` (`broken`), диагностика видна в `validate`.

- [ ] **Шаг 4: убедиться, что тест проходит**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_folder_config.py -q`
Expected: PASS.

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/folder_config.py tests/unit/test_folder_config.py
git commit -m "feat(projects): passport fields related_projects and disabled_harness"
```

### Задача 4: топология датасета и предупреждение о файлах вне `projects/`

**Файлы:**
- Modify: `src/todoc/application/project_scope.py` (`dataset_layout`)
- Modify: `src/todoc/service.py:45-72` (`DatasetContext.layout`)
- Modify: `src/todoc/application/validator.py:700-757` (новая `_layout_diagnostics`)
- Test: `tests/unit/test_project_scope.py`, `tests/unit/test_validator.py`

**Интерфейсы:**
- Consumes: `project_of`.
- Produces: `dataset_layout(root: Path) -> Layout`; `DatasetContext.layout: Layout`; диагностика `layout.outside_projects` (severity `warning`) для папок/файлов верхнего уровня вне `projects/` при `layout == "projects"`.

- [ ] **Шаг 1: написать падающий тест**

```python
from todoc.application.project_scope import dataset_layout


def test_layout_detects_projects_dir(tmp_path):
    (tmp_path / "projects" / "core").mkdir(parents=True)
    assert dataset_layout(tmp_path) == "projects"


def test_layout_defaults_to_legacy_flat(tmp_path):
    (tmp_path / "ideas").mkdir()
    assert dataset_layout(tmp_path) == "legacy_flat"


def test_explicit_dataset_layout_wins(tmp_path):
    (tmp_path / "projects" / "core").mkdir(parents=True)
    (tmp_path / ".todoc").mkdir()
    (tmp_path / ".todoc" / "dataset.json").write_text(
        '{"schema_version": 1, "dataset_id": "d", "layout": "legacy_flat"}', encoding="utf-8")
    assert dataset_layout(tmp_path) == "legacy_flat"
```

```python
import json

from click.testing import CliRunner

from todoc.cli import cli
from todoc.config import init_dataset


def test_root_files_outside_projects_warn(tmp_path):
    root = tmp_path / "kb"
    root.mkdir()
    init_dataset(root, dataset_id="dataset-projects")
    (root / "projects" / "core").mkdir(parents=True)
    (root / "ideas").mkdir()
    (root / "ideas" / "x.md").write_text(
        "---\ntitle: X\ndoc_type: note\n---\n\n# X\n", encoding="utf-8")
    result = CliRunner().invoke(cli, ["--root", str(root), "validate", "--all"])
    envelope = json.loads(result.output)
    codes = {item["code"] for item in envelope["diagnostics"]}
    assert "layout.outside_projects" in codes
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_project_scope.py -k layout -v`
Expected: FAIL — `ImportError: cannot import name 'dataset_layout'`

- [ ] **Шаг 3: реализовать топологию и диагностику**

`dataset_layout` читает `.todoc/dataset.json` (если `layout` — одно из двух значений, вернуть его), иначе проверяет каталог `projects/`. `DatasetContext.__init__` сохраняет `self.layout`.

`_layout_diagnostics(dataset_id, root) -> list[Diagnostic]`: если `dataset_layout(root) != "projects"` — пусто. Иначе для каждого элемента верхнего уровня, кроме `.todoc`, `.todocignore`, `projects`, выпускать `layout.outside_projects` с `suggested_fixes=["Перенесите файл в projects/<slug>/: todoc project migrate-flat --into <slug>"]`. Вызвать рядом с `_skills_diagnostics` и `_folder_configs_diagnostics` в `validate_dataset`.

- [ ] **Шаг 4: убедиться, что тесты проходят**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_project_scope.py tests/unit/test_validator.py -q`
Expected: PASS.

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/project_scope.py src/todoc/service.py src/todoc/application/validator.py tests/unit/test_project_scope.py tests/unit/test_validator.py
git commit -m "feat(projects): dataset layout detection and outside-projects warning"
```

### Фаза 2 — Стейт и группа `todoc project`

### Задача 5: `context.projects` в `state.json`

**Файлы:**
- Modify: `src/todoc/application/state.py:24` (`ALLOWED_KEYS_V1`)
- Test: `tests/unit/test_state.py`

**Интерфейсы:**
- Consumes: `set_var`, `get_var`, `load_state`.
- Produces: разрешённый ключ `context.projects` (строка `1–256` символов, формат `slug|slug|...`).

- [ ] **Шаг 1: написать падающий тест**

```python
def test_projects_key_roundtrip():
    set_var("dataset-x", "context.projects", "core|billing|auth", now="2026-11-28T00:00:00Z")
    assert get_var("dataset-x", "context.projects") == "core|billing|auth"
    assert "context.projects" in ALLOWED_KEYS_V1


def test_projects_key_still_validates_length():
    with pytest.raises(ValidationError) as err:
        set_var("dataset-x", "context.projects", "x" * 257)
    assert err.value.code == "state.invalid_value"
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_state.py -k projects_key -v`
Expected: FAIL — `state.unknown_key`.

- [ ] **Шаг 3: расширить whitelist**

```python
ALLOWED_KEYS_V1: tuple[str, ...] = ("context.current_project", "context.projects")
```

Обновить `test_unknown_key_rejected` (строка 53), который сравнивает кортеж целиком.

- [ ] **Шаг 4: убедиться, что тесты проходят**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_state.py -q`
Expected: PASS.

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/state.py tests/unit/test_state.py
git commit -m "feat(state): allow context.projects"
```

### Задача 6: резолвер `EffectiveScope`

**Файлы:**
- Modify: `src/todoc/application/project_scope.py`
- Test: `tests/unit/test_project_scope.py`

**Интерфейсы:**
- Consumes: `load_state`/`get_var` (задача 5), `dataset_layout` (задача 4).
- Produces: `EffectiveScope`, `parse_projects`, `resolve_scope`, `scope_allows`, `project_rank`, `group_by_project`.

- [ ] **Шаг 1: написать падающий тест**

```python
from todoc.application.project_scope import resolve_scope
from todoc.application.state import set_var


def _layout(root):
    for slug in ("core", "billing", "auth", "crm"):
        (root / "projects" / slug).mkdir(parents=True, exist_ok=True)


def test_default_scope_is_core_only(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    _layout(tmp_path)
    scope = resolve_scope(tmp_path, "ds", env={})
    assert scope.layout == "projects"
    assert scope.focus_project is None
    assert scope.active_projects == ("core",)
    assert scope.source == "default"


def test_state_scope_and_focus(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    _layout(tmp_path)
    set_var("ds", "context.current_project", "billing")
    set_var("ds", "context.projects", "core|billing|auth")
    scope = resolve_scope(tmp_path, "ds", env={})
    assert scope.focus_project == "billing"
    assert scope.active_projects == ("billing", "auth", "core")
    assert scope.source == "state"


def test_env_overrides_state_and_cli_overrides_env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    _layout(tmp_path)
    set_var("ds", "context.current_project", "billing")
    env = {"TODOC_PROJECT": "crm", "TODOC_PROJECTS": "crm|auth"}
    assert resolve_scope(tmp_path, "ds", env=env).active_projects == ("crm", "auth", "core")
    assert resolve_scope(tmp_path, "ds", env=env).source == "env"
    scope = resolve_scope(tmp_path, "ds", project="billing", env=env)
    assert scope.focus_project == "billing"
    assert scope.source == "cli"


def test_core_is_always_last_and_focus_first(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    _layout(tmp_path)
    scope = resolve_scope(tmp_path, "ds", projects="auth|billing", env={})
    assert scope.focus_project == "auth"
    assert scope.active_projects == ("auth", "billing", "core")


def test_no_core_and_all_projects(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    _layout(tmp_path)
    assert resolve_scope(tmp_path, "ds", no_core=True, env={}).active_projects == ()
    scope = resolve_scope(tmp_path, "ds", all_projects=True, env={})
    assert scope.all_projects is True
    assert set(scope.active_projects) == {"core", "billing", "auth", "crm"}


def test_scope_allows_legacy_and_projects(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    _layout(tmp_path)
    scope = resolve_scope(tmp_path, "ds", project="billing", env={})
    assert scope_allows(scope, "billing")
    assert not scope_allows(scope, "crm")
    assert not scope_allows(scope, None)
    legacy = EffectiveScope(layout="legacy_flat", focus_project=None,
                            active_projects=(), source="default")
    assert scope_allows(legacy, None)
```

Добавить импорты `EffectiveScope`, `scope_allows`.

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_project_scope.py -k "scope or core or env" -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_scope'`

- [ ] **Шаг 3: реализовать резолвер**

Порядок источников: CLI (`project`/`projects`/`all_projects`/`no_core`) → env (`TODOC_PROJECT`/`TODOC_PROJECTS`) → `state.json` → дефолт. Инварианты: `core` добавляется последним, если `projects/core` существует и не задан `no_core`; фокус всегда первый среди прикладных; `all_projects=True` выставляет все существующие slug. `parse_projects` режет строку по `|`, убирает пустые и дубли, проверяет slug-regex (иначе `project.invalid_slug`). `project_rank`: фокус → `(0, "")`, остальные активные → `(1, slug)`, `core` → `(2, "core")`, `None` → `(3, "")`. `group_by_project` возвращает группы в этом порядке, внутри — исходный порядок элементов.

- [ ] **Шаг 4: убедиться, что тесты проходят**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_project_scope.py -q`
Expected: PASS.

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/project_scope.py tests/unit/test_project_scope.py
git commit -m "feat(projects): effective scope resolver"
```

### Задача 7: `todoc project list|show|init`

**Файлы:**
- Modify: `src/todoc/cli.py` (новая группа `project` после `state`, ~строка 4000)
- Test: `tests/cli/test_cli_project.py`

**Интерфейсы:**
- Consumes: `resolve_scope`, `dataset_layout`, `load_folder_configs`, `init_dataset`.
- Produces: `todoc project list`, `todoc project show`, `todoc project init <slug> [--title] [--preview/--apply]`.

- [ ] **Шаг 1: написать падающий тест (с фикстурой)**

```python
import json

import pytest
from click.testing import CliRunner

from todoc.cli import cli
from todoc.config import init_dataset


@pytest.fixture()
def projects_root(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    root = tmp_path / "kb"
    root.mkdir()
    init_dataset(root, dataset_id="dataset-projects")
    for slug in ("core", "billing", "auth", "crm"):
        folder = root / "projects" / slug
        folder.mkdir(parents=True)
        (folder / ".config.json").write_text(
            json.dumps({"schema_version": 1, "title": slug.title()}), encoding="utf-8")
    return root


def _run(root, *args):
    return CliRunner().invoke(cli, ["--root", str(root), *args])


def _json(result):
    assert result.exit_code == 0, (result.output, result.exception)
    return json.loads(result.output)["data"]


def test_project_show_reports_scope(projects_root):
    out = _json(_run(projects_root, "project", "show"))
    assert out["result"]["focus_project"] is None
    assert out["result"]["active_projects"] == ["core"]
    assert out["result"]["layout"] == "projects"
    assert out["result"]["scope_source"] == "default"


def test_project_init_creates_scaffold(projects_root):
    out = _json(_run(projects_root, "project", "init", "crm2", "--title", "CRM 2", "--apply"))
    assert out["result"]["project"] == "crm2"
    assert (projects_root / "projects" / "crm2" / ".config.json").is_file()
    assert (projects_root / "projects" / "crm2" / "HOME.md").is_file()
    assert (projects_root / "projects" / "crm2" / "harness" / "skills").is_dir()


def test_project_init_is_create_only(projects_root):
    result = _run(projects_root, "project", "init", "core", "--apply")
    assert result.exit_code != 0
    assert json.loads(result.output)["diagnostics"][0]["code"] == "project.exists"
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `env PYTHONPATH=src python3 -m pytest tests/cli/test_cli_project.py -k "show or init" -v`
Expected: FAIL — `No such command 'project'`.

- [ ] **Шаг 3: реализовать группу и три команды**

`list` обходит `projects/*`, читает `.config.json`, показывает `slug`, `title`, `description`, `related_projects`, маркеры `focus/active/core`, счётчики документов из снапшота. `show` печатает `EffectiveScope` (`layout`, `focus_project`, `active_projects`, `source`) и сводку. `init` проверяет slug-regex (`project.invalid_slug`), создаёт `.config.json`, `HOME.md`, `harness/{skills,flows,rules}/`, `ideas/`, `plan/`, `state/`, `tasks/`; по умолчанию `--preview`, запись — `--apply`; существующий проект → `project.exists`.

- [ ] **Шаг 4: убедиться, что тесты проходят**

Run: `env PYTHONPATH=src python3 -m pytest tests/cli/test_cli_project.py -q`
Expected: PASS.

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/cli.py tests/cli/test_cli_project.py
git commit -m "feat(cli): project list/show/init"
```

### Задача 8: `todoc project use|add|remove|focus`

**Файлы:**
- Modify: `src/todoc/cli.py` (группа `project`)
- Test: `tests/cli/test_cli_project.py`

**Интерфейсы:**
- Consumes: `resolve_scope`, `set_var`, `unset_var`, `load_folder_configs`.
- Produces: команды меняют `context.current_project` и `context.projects`; `use --with-related` добавляет `related_projects`; `remove core` → `project.core_protected`; `remove` фокуса переводит фокус на следующий активный или сбрасывает.

- [ ] **Шаг 1: написать падающий тест**

```python
def test_project_use_sets_focus_and_active(projects_root):
    out = _json(_run(projects_root, "project", "use", "billing", "auth"))
    assert out["result"]["focus_project"] == "billing"
    assert out["result"]["active_projects"] == ["billing", "auth", "core"]
    assert _json(_run(projects_root, "project", "show"))["result"]["scope_source"] == "state"


def test_project_use_with_related_expands(projects_root):
    config = projects_root / "projects" / "billing" / ".config.json"
    config.write_text(json.dumps({"schema_version": 1, "title": "Billing",
                                  "related_projects": ["auth"]}), encoding="utf-8")
    out = _json(_run(projects_root, "project", "use", "billing", "--with-related"))
    assert out["result"]["active_projects"] == ["billing", "auth", "core"]


def test_project_use_unknown_slug_is_refused(projects_root):
    result = _run(projects_root, "project", "use", "nope")
    assert result.exit_code != 0
    assert json.loads(result.output)["diagnostics"][0]["code"] == "project.not_found"


def test_project_remove_core_is_refused(projects_root):
    result = _run(projects_root, "project", "remove", "core")
    assert result.exit_code != 0
    assert json.loads(result.output)["diagnostics"][0]["code"] == "project.core_protected"


def test_project_remove_focus_moves_focus(projects_root):
    _json(_run(projects_root, "project", "use", "billing", "auth"))
    out = _json(_run(projects_root, "project", "remove", "billing"))
    assert out["result"]["focus_project"] == "auth"
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `env PYTHONPATH=src python3 -m pytest tests/cli/test_cli_project.py -k "use or remove" -v`
Expected: FAIL — `No such command 'use'`.

- [ ] **Шаг 3: реализовать четыре команды**

`use` проверяет существование папок, пишет оба ключа; без `--with-related` добавляет в `next_actions` подсказку о связанных проектах. `add` добавляет в `context.projects`, не меняя фокус (если фокус пуст — ставит первый). `remove` защищает `core` и переносит фокус. `focus` меняет только `context.current_project` и добавляет проект в активные. Все команды возвращают новый `EffectiveScope`.

- [ ] **Шаг 4: убедиться, что тесты проходят**

Run: `env PYTHONPATH=src python3 -m pytest tests/cli/test_cli_project.py -q`
Expected: PASS.

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/cli.py tests/cli/test_cli_project.py
git commit -m "feat(cli): project use/add/remove/focus"
```

### Фаза 3 — Скоуп, группировка и харнес

### Задача 9: сквозные флаги скоупа, блок `scope` и `groups` в конверте

**Файлы:**
- Modify: `src/todoc/cli.py:74-130` (хелперы), команды чтения
- Modify: `src/todoc/output/envelope.py:20-45` (`Envelope.collection`)
- Test: `tests/cli/test_cli_project.py`

**Интерфейсы:**
- Consumes: `resolve_scope`, `scope_allows`, `project_rank`.
- Produces: декоратор `scope_options`; хелперы `_scope(...)` и `_scope_meta(ctx, scope)`; `Envelope.collection(..., groups=None)`; `meta.scope` содержит `dataset_id`, `layout`, `focus_project`, `active_projects`, `scope_source`, `all_projects`.

- [ ] **Шаг 1: написать падающий тест**

```python
def test_docs_list_has_scope_block_and_project_field(projects_root):
    (projects_root / "projects" / "billing" / "ideas").mkdir(parents=True, exist_ok=True)
    (projects_root / "projects" / "billing" / "ideas" / "a.md").write_text(
        "---\ntitle: A\ndoc_type: note\n---\n\n# A\n", encoding="utf-8")
    out = _json(_run(projects_root, "docs", "list", "--project", "billing"))
    assert out["meta"]["scope"]["focus_project"] == "billing"
    assert out["meta"]["scope"]["layout"] == "projects"
    assert out["result"]["items"][0]["project"] == "billing"
    assert out["result"]["groups"][0]["project"] == "billing"


def test_closed_project_is_not_listed(projects_root):
    (projects_root / "projects" / "crm" / "ideas").mkdir(parents=True, exist_ok=True)
    (projects_root / "projects" / "crm" / "ideas" / "x.md").write_text(
        "---\ntitle: X\ndoc_type: note\n---\n\n# X\n", encoding="utf-8")
    out = _json(_run(projects_root, "docs", "list", "--project", "billing"))
    assert out["result"]["items"] == []
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `env PYTHONPATH=src python3 -m pytest tests/cli/test_cli_project.py -k "scope_block or closed_project" -v`
Expected: FAIL — неизвестная опция `--project`.

- [ ] **Шаг 3: добавить декоратор, хелперы и `groups`**

```python
_SCOPE_OPTIONS = (
    click.option("--project", "scope_project", default=None),
    click.option("--projects", "scope_projects", default=None),
    click.option("--all-projects", "scope_all_projects", is_flag=True),
    click.option("--no-core", "scope_no_core", is_flag=True),
)


def scope_options(fn):
    for option in reversed(_SCOPE_OPTIONS):
        fn = option(fn)
    return fn
```

Каждая декорированная команда получает в сигнатуре четыре параметра `scope_project`, `scope_projects`, `scope_all_projects`, `scope_no_core`. `_scope(ctx, scope_project, scope_projects, scope_all_projects, scope_no_core)` вызывает `resolve_scope(ctx.root, ctx.dataset_id, ..., env=os.environ)`. `_scope_meta` собирает блок `meta.scope`. В `Envelope.collection` добавить необязательный `groups`: `result["groups"] = groups`, когда `groups is not None`; в `render` при наличии групп печатать секции по проектам. `group_by_project` включает только непустые группы, а плоский `items` идёт в том же порядке, что и обход групп.

**Курсоры:** в список `selection` каждой коллекции добавить срез скоупа (`focus_project`, `active_projects`, `all_projects`), иначе курсор одной выборки примет выборку другого скоупа.

- [ ] **Шаг 4: убедиться, что тесты проходят**

Run: `env PYTHONPATH=src python3 -m pytest tests/cli/test_cli_project.py -q`
Expected: PASS.

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/cli.py src/todoc/output/envelope.py tests/cli/test_cli_project.py
git commit -m "feat(cli): scope flags, scope block and grouped results"
```

### Задача 10: `docs list/search/read` — фильтр, `project`, группировка, подсказка

**Файлы:**
- Modify: `src/todoc/application/documents.py:7-86`
- Modify: `src/todoc/application/search.py:126-230`
- Modify: `src/todoc/cli.py:1818-2165` (`docs_list`, `docs_search`), `2164-2334` (`docs_read`)
- Test: `tests/cli/test_cli_project.py`

**Интерфейсы:**
- Consumes: `scope_allows`, `group_by_project`, `project_rank`.
- Produces: `FIELDS` содержит `project`; `matching_documents(..., scope=None)`; `list_documents(..., scope=None)`; `search_documents(..., scope=None)`; `result.groups`; `project.out_of_scope`; подсказка `todoc project add <slug>`.

- [ ] **Шаг 1: написать падающий тест**

```python
def _doc(root, rel, title, body="retry policy"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntitle: {title}\ndoc_type: note\n---\n\n# {title}\n\n{body}\n",
                    encoding="utf-8")


def test_search_groups_by_project_in_focus_order(projects_root):
    _doc(projects_root, "projects/core/notes/core.md", "Core")
    _doc(projects_root, "projects/billing/notes/billing.md", "Billing")
    _doc(projects_root, "projects/auth/notes/auth.md", "Auth")
    _json(_run(projects_root, "project", "use", "billing", "auth"))
    out = _json(_run(projects_root, "docs", "search", "--query", "retry"))
    assert [group["project"] for group in out["result"]["groups"]] == ["billing", "auth", "core"]
    assert all(item["project"] == group["project"]
               for group in out["result"]["groups"] for item in group["items"])
    assert [item["id"] for item in out["result"]["items"]] == [
        item["id"] for group in out["result"]["groups"] for item in group["items"]]


def test_zero_hits_hint_closed_project(projects_root):
    _doc(projects_root, "projects/crm/notes/crm.md", "CRM")
    _json(_run(projects_root, "project", "use", "billing"))
    out = _json(_run(projects_root, "docs", "search", "--query", "retry"))
    assert out["result"]["items"] == []
    assert any("project" in " ".join(action["argv"]) and "crm" in action["argv"]
               for action in out["next_actions"])


def test_read_out_of_scope_is_refused(projects_root):
    _doc(projects_root, "projects/crm/notes/crm.md", "CRM")
    _json(_run(projects_root, "project", "use", "billing"))
    result = _run(projects_root, "docs", "read", "--id", "doc:projects/crm/notes/crm.md")
    assert result.exit_code != 0
    assert json.loads(result.output)["diagnostics"][0]["code"] == "project.out_of_scope"


def test_explicit_within_closed_project_is_refused(projects_root):
    _doc(projects_root, "projects/crm/notes/crm.md", "CRM")
    _json(_run(projects_root, "project", "use", "billing"))
    result = _run(projects_root, "docs", "list", "--within", "projects/crm")
    assert result.exit_code != 0
    assert json.loads(result.output)["diagnostics"][0]["code"] == "project.out_of_scope"
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `env PYTHONPATH=src python3 -m pytest tests/cli/test_cli_project.py -k "groups or hint or out_of_scope" -v`
Expected: FAIL — `result.groups` отсутствует.

- [ ] **Шаг 3: применить скоуп и группировку**

В `matching_documents`/`list_documents` добавить `scope` и фильтровать `scope_allows(scope, doc["project"])`. Сортировать кандидатов по `project_rank` до пагинации. В `docs search` после получения хитов сортировать по `(project_rank, -rank, id)`, строить `groups`; `items` остаётся плоским в том же порядке. `--budget` применяется к `items`; `groups` строятся из уже усечённого списка, `meta.truncated` отражает усечение. Для `docs read` — проверка `scope_allows` до чтения (`project.out_of_scope`). Явный `--within`, называющий закрытый проект, — `project.out_of_scope`. При нулевой выдаче искать по документам вне скоупа (тот же лексический поиск, `limit=1`) и добавлять `next_actions` `todoc project add <slug>`.

- [ ] **Шаг 4: убедиться, что тесты проходят**

Run: `env PYTHONPATH=src python3 -m pytest tests/cli/test_cli_project.py tests/cli/test_unified_docs.py tests/cli/test_unified_lists.py -q`
Expected: PASS.

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/documents.py src/todoc/application/search.py src/todoc/cli.py tests/cli/test_cli_project.py
git commit -m "feat(docs): scope filter, project field and grouped results"
```

### Задача 11: `records list/query/read` и `relations graph` — скоуп и границы

**Файлы:**
- Modify: `src/todoc/service.py:120-150` (поле `project` у записей)
- Modify: `src/todoc/cli.py:2927-3334` (`records_list`, `records_query`, `records_read`), `3445-3519` (`relations_graph`)
- Test: `tests/cli/test_cli_project.py`

**Интерфейсы:**
- Consumes: `scope_allows`, `group_by_project`.
- Produces: `records` несут `project`; выборки фильтруются и группируются; `relations graph` для закрытого узла отдаёт `result.boundary = [{id, project, in_active_scope}]`, `nodes` остаются списком строк, подграф не раскрывается.

- [ ] **Шаг 1: написать падающий тест**

```python
def _record(root, rel, record_id):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "record_id": record_id,
                                "entity_type": "note", "title": "Note"}), encoding="utf-8")


def test_records_list_filters_closed_projects(projects_root):
    _record(projects_root, "projects/billing/records/note/a.json", "note:billing-a")
    _record(projects_root, "projects/crm/records/note/b.json", "note:crm-b")
    _json(_run(projects_root, "project", "use", "billing"))
    out = _json(_run(projects_root, "records", "list", "--type", "note"))
    assert [item["record_id"] for item in out["result"]["items"]] == ["note:billing-a"]
    assert out["result"]["items"][0]["project"] == "billing"
    assert out["result"]["groups"][0]["project"] == "billing"


def test_relations_graph_marks_closed_boundary(projects_root):
    _record(projects_root, "projects/crm/records/note/b.json", "note:crm-b")
    _json(_run(projects_root, "project", "use", "billing"))
    out = _json(_run(projects_root, "relations", "graph", "--from", "note:crm-b"))
    assert out["result"]["nodes"] == ["note:crm-b"]
    assert out["result"]["boundary"] == [
        {"id": "note:crm-b", "project": "crm", "in_active_scope": False}]
    assert out["result"]["edges"] == []
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `env PYTHONPATH=src python3 -m pytest tests/cli/test_cli_project.py -k "records_list_filters or boundary" -v`
Expected: FAIL — `crm` попадает в выдачу, `boundary` отсутствует.

- [ ] **Шаг 3: применить скоуп к записям и графу**

В `service.py` запись получает `"project": project_of(doc["path"])`. В `records_list`/`records_query` фильтровать `payload["records"]` по `scope_allows` до `_select_records`; в `_emit_records_page` добавить `project` в набор полей (`("record_id","entity_type","dataset_id","path","hash","data","project")`) и передавать `groups` из `group_by_project` по уже отобранной странице. В `records_read` — `project.out_of_scope`. В `relations_graph`: если `project_of` узла не проходит `scope_allows`, вернуть `nodes=[from_id]`, `edges=[]`, `boundary` с записью узла и `next_actions` `todoc project add <slug>`; иначе строить граф как раньше.

- [ ] **Шаг 4: убедиться, что тесты проходят**

Run: `env PYTHONPATH=src python3 -m pytest tests/cli/test_cli_project.py tests/cli/test_unified_relations.py -q`
Expected: PASS.

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/service.py src/todoc/cli.py tests/cli/test_cli_project.py
git commit -m "feat(records): scope records and relation graph boundaries"
```

### Задача 12: `docs tree` и `stale` — скоуп

**Файлы:**
- Modify: `src/todoc/cli.py:2439-2552` (`docs_tree`), `867-929` (`stale`)
- Test: `tests/cli/test_cli_project.py`

**Интерфейсы:**
- Consumes: `scope_allows`, `EffectiveScope`.
- Produces: дерево и устаревшие документы ограничены активными проектами; `meta.scope` присутствует; закрытые папки не печатаются.

- [ ] **Шаг 1: написать падающий тест**

```python
def test_tree_hides_closed_projects(projects_root):
    (projects_root / "projects" / "crm" / "ideas").mkdir(parents=True, exist_ok=True)
    (projects_root / "projects" / "billing" / "ideas").mkdir(parents=True, exist_ok=True)
    _json(_run(projects_root, "project", "use", "billing"))
    out = _json(_run(projects_root, "docs", "tree", "--limit", "1000"))
    paths = json.dumps(out["result"], ensure_ascii=False)
    assert "projects/billing" in paths
    assert "projects/crm" not in paths


def test_stale_filters_closed_projects(projects_root):
    _json(_run(projects_root, "project", "use", "billing"))
    out = _json(_run(projects_root, "stale"))
    assert out["result"]["stale"] == 0
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `env PYTHONPATH=src python3 -m pytest tests/cli/test_cli_project.py -k "tree_hides or stale_filters" -v`
Expected: FAIL — `projects/crm` присутствует.

- [ ] **Шаг 3: применить скоуп**

В `docs_tree` фильтровать `payload["folders"]` и `payload["documents"]` по `scope_allows` до построения дерева; корень `projects` оставлять только если в нём есть активные дети; `selection` дополнить срезом скоупа. В `stale` фильтровать диагностики по `project_of(diag["path"])`; `--all-projects` отключает фильтр.

- [ ] **Шаг 4: убедиться, что тесты проходят**

Run: `env PYTHONPATH=src python3 -m pytest tests/cli/test_cli_project.py tests/cli/test_cli_stale.py -q`
Expected: PASS.

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/cli.py tests/cli/test_cli_project.py
git commit -m "feat(tree): scope docs tree and stale"
```

### Задача 13: запись — фокус, защита `core`, `out_of_scope`, изменения

**Файлы:**
- Modify: `src/todoc/application/project_scope.py` (`ensure_writable`, `resolve_new_path`)
- Modify: `src/todoc/cli.py:1716-1818` (`docs_new`), `2646-2770` (`docs_status`), `2766-2826` (`docs_edit`), `2975-3043` (`records_status`), `2826-2854` (`records_edit`), `3781-3843` (`fix`), `821-866` (`sync`), `1385-1410` (`change_open`), `1470-1510` (`change_apply`)
- Modify: `src/todoc/application/changes.py:47-110` (`changes_dirs`, `change_dir`)
- Test: `tests/cli/test_cli_project.py`

**Интерфейсы:**
- Consumes: `EffectiveScope`, `project_of`, `scope_allows`.
- Produces: `ensure_writable(scope, rel_path, *, explicit_core=False)`; `resolve_new_path(scope, rel_path)`; `changes_dirs(root) -> list[Path]`; коды `project.not_selected`, `project.core_readonly`, `project.out_of_scope`, `project.all_projects_readonly`.

- [ ] **Шаг 1: написать падающий тест**

```python
def test_docs_new_requires_focus_in_projects_layout(projects_root):
    result = _run(projects_root, "docs", "new", "--type", "note", "--title", "Idea", "--apply")
    assert result.exit_code != 0
    assert json.loads(result.output)["diagnostics"][0]["code"] == "project.not_selected"


def test_docs_new_prefixes_focus_project(projects_root):
    _json(_run(projects_root, "project", "use", "billing"))
    out = _json(_run(projects_root, "docs", "new", "--type", "note", "--title", "Retry",
                     "--path", "ideas/retry.md", "--apply"))
    assert out["result"]["path"] == "projects/billing/ideas/retry.md"


def test_docs_new_explicit_other_active_project(projects_root):
    _json(_run(projects_root, "project", "use", "billing", "auth"))
    out = _json(_run(projects_root, "docs", "new", "--type", "note", "--title", "Retry",
                     "--project", "auth", "--path", "ideas/retry.md", "--apply"))
    assert out["result"]["path"] == "projects/auth/ideas/retry.md"


def test_core_write_requires_explicit_core(projects_root):
    path = projects_root / "projects" / "core" / "notes" / "x.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\ntitle: X\ndoc_type: note\nstatus: captured\n---\n\n# X\n", encoding="utf-8")
    _json(_run(projects_root, "project", "use", "billing"))
    result = _run(projects_root, "docs", "status", "--id", "doc:projects/core/notes/x.md",
                  "--set", "done", "--apply")
    assert result.exit_code != 0
    assert json.loads(result.output)["diagnostics"][0]["code"] == "project.core_readonly"
    out = _json(_run(projects_root, "docs", "status", "--id", "doc:projects/core/notes/x.md",
                     "--set", "done", "--project", "core", "--apply"))
    assert out["result"]["status"] == "done"


def test_all_projects_is_readonly_for_mutation(projects_root):
    path = projects_root / "projects" / "billing" / "notes" / "x.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\ntitle: X\ndoc_type: note\nstatus: captured\n---\n\n# X\n", encoding="utf-8")
    result = _run(projects_root, "docs", "status", "--id", "doc:projects/billing/notes/x.md",
                  "--set", "done", "--all-projects", "--apply")
    assert result.exit_code != 0
    assert json.loads(result.output)["diagnostics"][0]["code"] == "project.all_projects_readonly"


def test_change_open_goes_to_focus_project(projects_root):
    _json(_run(projects_root, "project", "use", "billing"))
    out = _json(_run(projects_root, "change", "open", "--title", "Fix billing", "--apply"))
    assert out["result"]["path"].startswith("projects/billing/changes/")
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `env PYTHONPATH=src python3 -m pytest tests/cli/test_cli_project.py -k "requires_focus or prefixes_focus or core_write or readonly or change_open" -v`
Expected: FAIL — создание уходит в корень, защиты нет.

- [ ] **Шаг 3: реализовать проверки и разворачивание пути**

`resolve_new_path(scope, rel)`: при `layout == "legacy_flat"` вернуть `rel`; если `rel` начинается с `projects/<slug>/`, проверить `scope_allows` и вернуть как есть; иначе потребовать `focus_project` (`project.not_selected`) и вернуть `projects/<focus>/<rel>`.

`ensure_writable(scope, rel_path, *, explicit_core=False)`:
- `project = project_of(rel_path)`;
- `project is None` → при `legacy_flat` вернуть, иначе `project.outside_projects`;
- `project == "core"` и `scope.focus_project != "core"` и не `explicit_core` → `project.core_readonly`;
- `not scope_allows(...)` → `project.out_of_scope`.

Вызывать: `docs new` (после `resolve_new_path`), `docs status/edit`, `records status/edit`, `fix`, `sync` для каждого пути. На мутирующих командах при `scope.all_projects` → `project.all_projects_readonly`.

`change open`: `changes_dirs(root)` возвращает `[root/changes, root/projects/*/changes]`; `change_dir` ищет запись во всех; `change_open` пишет в `projects/<focus>/changes/<slug>/` при `layout == "projects"`. `change_apply` перед записью проверяет `ensure_writable` для каждого `record["artifacts"]`.

- [ ] **Шаг 4: убедиться, что тесты проходят**

Run: `env PYTHONPATH=src python3 -m pytest tests/cli/test_cli_project.py tests/cli/test_unified_failures.py tests/cli/test_cli_changes.py -q`
Expected: PASS.

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/project_scope.py src/todoc/application/changes.py src/todoc/cli.py tests/cli/test_cli_project.py
git commit -m "feat(write): focus path resolution, core protection and project changes"
```

### Задача 14: неймспейсинг `record_id` и `path_template` для новых записей

**Файлы:**
- Modify: `src/todoc/application/project_scope.py` (`namespace_record_id`)
- Modify: `src/todoc/application/write.py:63-109` (`create_record_plan(..., project=None)`)
- Modify: `src/todoc/cli.py:2854-2889` (`records_create`)
- Test: `tests/unit/test_project_scope.py`, `tests/cli/test_cli_project.py`

**Интерфейсы:**
- Consumes: `EffectiveScope`, `project_of`.
- Produces: `namespace_record_id(record_id, project) -> str`; `create_record_plan(..., project: str | None = None)`; в раскладке `projects` `task:0001` → `task:billing-0001`, а `tasks/{slug}.json` → `projects/billing/tasks/billing-0001.json`.

- [ ] **Шаг 1: написать падающий тест**

```python
from todoc.application.project_scope import namespace_record_id


def test_namespace_record_id_adds_project():
    assert namespace_record_id("task:0001", "billing") == "task:billing-0001"
    assert namespace_record_id("flow:login", "auth") == "flow:auth-login"


def test_namespace_record_id_is_idempotent_and_legacy_safe():
    assert namespace_record_id("task:billing-0001", "billing") == "task:billing-0001"
    assert namespace_record_id("task:0001", None) == "task:0001"
```

```python
def test_records_create_namespaces_id_and_path(projects_root, tmp_path):
    _json(_run(projects_root, "project", "use", "billing"))
    payload = tmp_path / "note.json"
    payload.write_text(json.dumps({"schema_version": 1, "record_id": "note:0001",
                                   "entity_type": "note", "title": "Note"}), encoding="utf-8")
    out = _json(_run(projects_root, "records", "create", "--type", "note",
                     "--input-file", str(payload), "--apply"))
    assert out["result"]["created"] == "projects/billing/records/note/billing-0001.json"
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_project_scope.py -k namespace -v`
Expected: FAIL — `ImportError: cannot import name 'namespace_record_id'`.

- [ ] **Шаг 3: реализовать и подключить**

`namespace_record_id`: разделить id по первому `:`, добавить `<project>-` к slug, если префикса ещё нет; `project is None` — no-op. В `create_record_plan` принять `project`; если `project` задан и `path_template` не начинается с `projects/`, итоговый путь — `projects/<project>/<template-result>`; проверки `../` и `existing_paths` выполняются по итоговому пути. В `records_create` определить проект (фокус или `--project`), применить `namespace_record_id` до `create_record_plan` и передать `project`; без фокуса — `project.not_selected`. Тест использует `entity_type: note`, потому что `note` есть в дефолтах `init_dataset`; для `task` из `demo` правило то же (`projects/billing/tasks/billing-0001.json`).

- [ ] **Шаг 4: убедиться, что тесты проходят**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_project_scope.py tests/cli/test_cli_project.py -q`
Expected: PASS.

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/project_scope.py src/todoc/application/write.py src/todoc/cli.py tests/unit/test_project_scope.py tests/cli/test_cli_project.py
git commit -m "feat(records): namespace record ids and paths by project"
```

### Задача 15: каскадный харнес — скилы, `disabled_harness` и валидация

**Файлы:**
- Modify: `src/todoc/application/skills.py` (новые `scan_skill_layers`, `SkillLayer`)
- Modify: `src/todoc/cli.py:426-646` (`skills_tree`, `skills_read`)
- Modify: `src/todoc/application/validator.py:729-757` (`_skills_diagnostics`)
- Test: `tests/unit/test_skills_scan.py`, `tests/cli/test_cli_project.py`

**Интерфейсы:**
- Consumes: `EffectiveScope`, `load_folder_configs`.
- Produces: `scan_skill_layers(root: Path, scope: EffectiveScope) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]`; элементы несут `project`, `shadowed_by`; `skills tree` по умолчанию сканирует `projects/<p>/harness/skills` активных проектов; `skills read --path` резолвит по каскаду; `_skills_diagnostics` валидирует каждый проектный vault отдельно.

- [ ] **Шаг 1: написать падающий тест**

```python
def _skill(root, rel, name):
    folder = root / rel / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Deploy the service.\n---\n\n# {name}\n", encoding="utf-8")


def test_project_skill_shadows_core_skill(projects_root):
    _skill(projects_root, "projects/core/harness/skills", "deploy")
    _skill(projects_root, "projects/billing/harness/skills", "deploy")
    _json(_run(projects_root, "project", "use", "billing"))
    out = _json(_run(projects_root, "skills", "tree", "--limit", "100"))
    deploy = [item for item in out["result"]["skills"] if item["name"] == "deploy"]
    core = next(item for item in deploy if item["project"] == "core")
    billing = next(item for item in deploy if item["project"] == "billing")
    assert core["shadowed_by"] == "projects/billing/harness/skills/deploy"
    assert billing["shadowed_by"] is None


def test_disabled_harness_hides_skill(projects_root):
    _skill(projects_root, "projects/core/harness/skills", "legacy")
    config = projects_root / "projects" / "billing" / ".config.json"
    config.write_text(json.dumps({
        "schema_version": 1, "title": "Billing",
        "disabled_harness": ["doc:projects/core/harness/skills/legacy/SKILL.md"],
    }), encoding="utf-8")
    _json(_run(projects_root, "project", "use", "billing"))
    out = _json(_run(projects_root, "skills", "tree", "--limit", "100"))
    assert not [item for item in out["result"]["skills"] if item["name"] == "legacy"]


def test_skills_read_resolves_cascade(projects_root):
    _skill(projects_root, "projects/core/harness/skills", "deploy")
    _skill(projects_root, "projects/billing/harness/skills", "deploy")
    _json(_run(projects_root, "project", "use", "billing"))
    out = _json(_run(projects_root, "skills", "read", "--path", "deploy"))
    assert out["result"]["path"] == "projects/billing/harness/skills/deploy/SKILL.md"
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `env PYTHONPATH=src python3 -m pytest tests/cli/test_cli_project.py -k "shadows or disabled_harness or resolves_cascade" -v`
Expected: FAIL — сканируется только корневой `skills/`; `skills tree` падает с `skills.not_found`.

- [ ] **Шаг 3: реализовать многослойный скан**

`scan_skill_layers` обходит `projects/<p>/harness/skills` в порядке `scope.active_projects`, добавляет `project` и `shadowed_by` (путь первого скила с тем же `name` выше по каскаду). `disabled_harness` собирается объединением паспортов всех активных проектов; элемент исключается, если его `id` (`doc:<skill_md>`) в объединении. `skills tree`: при `layout == "projects"` и `vault` на дефолтном значении (`click.get_current_context().get_parameter_source("vault") == "default"`) использовать `scan_skill_layers` и не требовать существования корневого `skills/`; явный `--vault` сохраняет прежнее поведение. В набор полей `skills tree` добавить `project`, `shadowed_by`. `skills read` ищет скил по каскаду и возвращает `project` в результате.

`_skills_diagnostics`: при `layout == "projects"` сканировать каждый `projects/<p>/harness/skills` отдельно (`validate_skills` внутри vault); совпадение имён между проектами ошибкой не считается. Неизвестный id из `disabled_harness` → `folder.config.unknown_harness_id` (`warning`).

- [ ] **Шаг 4: убедиться, что тесты проходят**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_skills_scan.py tests/unit/test_validator_skills.py tests/cli/test_cli_skills_tree.py tests/cli/test_cli_project.py -q`
Expected: PASS.

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/skills.py src/todoc/application/validator.py src/todoc/cli.py tests/unit/test_skills_scan.py tests/cli/test_cli_project.py
git commit -m "feat(skills): cascade scan with project shadowing and disabled_harness"
```

### Задача 16: проектный резолв ссылок

**Файлы:**
- Modify: `src/todoc/application/project_scope.py` (`scoped_link_candidates`)
- Modify: `src/todoc/application/validator.py:183-210,300-400`
- Test: `tests/unit/test_project_scope.py`, `tests/unit/test_validator.py`

**Интерфейсы:**
- Consumes: `project_of`; существующие `_wikilink_candidates`, `resolve_link_target`.
- Produces: `scoped_link_candidates(source_path: str, candidates: list[str]) -> list[str]` — сужает кандидатов до своего проекта, затем до `core`, иначе возвращает всех (плоский датасет). Новая функция не заменяет `resolve_link_target` из `markdown.py`.

- [ ] **Шаг 1: написать падающий тест**

```python
from todoc.application.project_scope import scoped_link_candidates


def test_short_link_prefers_own_project_then_core():
    candidates = [
        "projects/billing/specs/overview.md",
        "projects/auth/specs/overview.md",
        "projects/core/specs/overview.md",
    ]
    assert scoped_link_candidates("projects/billing/specs/api.md", candidates) == [
        "projects/billing/specs/overview.md"]


def test_short_link_falls_back_to_core():
    candidates = ["projects/core/guides/setup.md", "projects/auth/guides/setup.md"]
    assert scoped_link_candidates("projects/billing/specs/api.md", candidates) == [
        "projects/core/guides/setup.md"]


def test_legacy_dataset_keeps_all_candidates():
    candidates = ["notes/a.md", "notes/b.md"]
    assert scoped_link_candidates("notes/c.md", candidates) == candidates
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_project_scope.py -k link -v`
Expected: FAIL — `ImportError: cannot import name 'scoped_link_candidates'`.

- [ ] **Шаг 3: реализовать сужение и подключить**

`scoped_link_candidates`:
- `project = project_of(source_path)`; если `None` — вернуть `candidates`;
- если среди кандидатов есть файлы того же проекта — вернуть только их;
- иначе, если есть кандидаты из `projects/core/` — вернуть их;
- иначе вернуть `candidates` (межпроектная ссылка остаётся неоднозначной → диагностика как раньше).

Подключить в трёх местах `validator.py`: `build_mentions` (строка ~202), `_check_link_targets` (~314), `_check_markdown_links` (~373) — после `_wikilink_candidates(...)` применять `scoped_link_candidates(scanned.rel_path, ...)`. Валидация по-прежнему идёт по всему индексу. Ссылка на файл закрытого проекта не считается битой: `markdown.link.project_closed` (`info`) с подсказкой `todoc project add <slug>`.

- [ ] **Шаг 4: убедиться, что тесты проходят**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_validator.py tests/unit/test_project_scope.py -q`
Expected: PASS.

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/project_scope.py src/todoc/application/validator.py tests/unit/test_validator.py tests/unit/test_project_scope.py
git commit -m "feat(links): project-local link resolution with core fallback"
```

### Фаза 4 — Миграция и контракт

### Задача 17: `todoc project migrate-flat`

**Файлы:**
- Create: `src/todoc/application/migrate.py`
- Modify: `src/todoc/cli.py` (группа `project`)
- Test: `tests/unit/test_migrate.py`, `tests/cli/test_cli_project.py`

**Интерфейсы:**
- Consumes: `plan_move`, `apply_move` из `src/todoc/application/move.py` (план [docs-move-implementation](docs-move-implementation.md)), `dataset_layout`, `project_of`, `scan_and_validate`.
- Produces: `plan_migration(root: Path, into: str, *, extract_core: bool) -> dict[str, Any]`, `apply_migration(...)`; CLI `todoc project migrate-flat --into <slug> [--extract-core] [--preview/--apply]`; отчёт `moves`, `rewritten_links`, `skipped`.

- [ ] **Шаг 1: написать падающий тест**

```python
import json

from click.testing import CliRunner

from todoc.cli import cli
from todoc.config import init_dataset


def _run(root, *args):
    return CliRunner().invoke(cli, ["--root", str(root), *args])


def test_migrate_flat_moves_files_and_keeps_links_valid(tmp_path):
    root = tmp_path / "kb"
    root.mkdir()
    init_dataset(root, dataset_id="dataset-flat")
    (root / "ideas").mkdir()
    (root / "plan").mkdir()
    (root / "ideas" / "a.md").write_text(
        "---\ntitle: A\ndoc_type: note\n---\n\n# A\n\nСм. [план](../plan/b.md).\n", encoding="utf-8")
    (root / "plan" / "b.md").write_text(
        "---\ntitle: B\ndoc_type: note\n---\n\n# B\n", encoding="utf-8")

    preview = _run(root, "project", "migrate-flat", "--into", "billing")
    assert preview.exit_code == 0, preview.output
    assert (root / "ideas" / "a.md").exists()

    applied = _run(root, "project", "migrate-flat", "--into", "billing", "--apply")
    assert applied.exit_code == 0, applied.output
    moved = root / "projects" / "billing" / "ideas" / "a.md"
    assert moved.is_file()
    assert "../plan/b.md" in moved.read_text(encoding="utf-8")
    assert (root / "projects" / "billing" / "plan" / "b.md").is_file()

    validate = _run(root, "validate", "--all")
    envelope = json.loads(validate.output)
    assert envelope["data"]["result"]["datasets"][0]["diagnostic_count"] == 0
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_migrate.py -k migrate -v`
Expected: FAIL — `No such command 'migrate-flat'`.

- [ ] **Шаг 3: реализовать план и применение**

**Уточнение аудита 2026-11-28 — gate перед задачей 17:** [пересмотренный план docs move](docs-move-implementation.md) даёт в v1 перенос **одного Markdown** в существующую папку; не даёт переноса JSON/CSV/ассетов, создания каталогов/config, виртуального переноса skills и общей batch-транзакции. Поэтому эта задача **не готова к исполнению только по факту появления `apply_move`**. Фазы 1–3 данного плана независимы; задача 17 ждёт отдельного проверяемого контракта пакетной миграции (см. [BUG-074](../bugs/bug-074-move-plan-execution-fixtures.md)).

`plan_migration` строит переносы: `skills/`, `skill/`, `guides/`, `glossary/` → `projects/core/...` при `--extract-core`; остальные папки (`ideas`, `plan`, `tasks`, `records`, `bugs`, `specs`, `architecture`, `contracts`, `notes`, `reports`, `changes`, `state`, `.research`) → `projects/<into>/...`. Для целевых проектов план также создаёт `.config.json` (`schema_version: 1`, `title` из slug) и `HOME.md`, если их нет. Это сохраняемый целевой scope, не обещание уже готового одиночного move.

До реализации дополнить этот шаг batch-контрактом: единая old→new map, виртуальные новые каталоги и полный read-set, переиспользование **чистых rewrite helpers** move, поддержка записей/ассетов/skills и active changes, одно preflight-состояние, одна граница коммита/история, общий rollback и один index publish без observation. Нельзя заранее построить независимые `MovePlan` для каждого документа и последовательно выполнить `apply_move`: после первого коммита fingerprint остальных устарел, а исходящие ссылки могут переписываться несколько раз. Также цикл одиночных move не даёт атомарности всей миграции.

Добавить тесты `test_migration_batch_rewrites_cross_links_once`, `test_migration_handles_records_assets_and_skills`, `test_migration_mid_batch_failure_restores_all_bytes_and_history`, `test_migration_preview_apply_binds_full_readset`. Каждый проверяет whole-batch manifest и event-count. Конфликт целевого пути → `migration.target_exists` **до** первой записи; виртуальная validate/relations/skills/folder-config проверяется до commit. Ошибки после commit должны честно сообщать применённое состояние. CLI-пример выше (apply без hash) перед реализацией привести к утверждённому batch review-first контракту; не ослаблять hash-guard одиночного move ради прохождения старой фикстуры.

- [ ] **Шаг 4: убедиться, что тесты проходят**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_migrate.py tests/cli/test_cli_project.py -q`
Expected: PASS.

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/migrate.py src/todoc/cli.py tests/unit/test_migrate.py tests/cli/test_cli_project.py
git commit -m "feat(projects): migrate-flat transactional migration"
```

### Задача 18: агентский контракт, HOME, README и стартовый скил

**Файлы:**
- Modify: `demo/notes/agent-contract.md` (раздел «Старт сессии» и «Раскладка датасета»)
- Modify: `demo/HOME.md` (карта демо, счётчики)
- Modify: `README.md` (раскладка и скоуп)
- Test: `tests/unit/test_demo_prompts_policy.py`

**Интерфейсы:**
- Consumes: все команды задач 7–17.
- Produces: контракт старта сессии (`todoc project show` первым шагом), правило группировки, защита `core`, описание `migrate-flat`.

- [ ] **Шаг 1: написать падающий тест**

```python
from pathlib import Path

DEMO = Path(__file__).resolve().parents[2] / "demo"


def test_agent_contract_mentions_project_start():
    text = (DEMO / "notes" / "agent-contract.md").read_text(encoding="utf-8")
    assert "todoc project show" in text
    assert "result.groups" in text


def test_home_mentions_projects_layout():
    text = (DEMO / "HOME.md").read_text(encoding="utf-8")
    assert "projects/<slug>" in text
    assert "migrate-flat" in text
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `env PYTHONPATH=src python3 -m pytest tests/unit/test_demo_prompts_policy.py -k "project_start or projects_layout" -v`
Expected: FAIL — `2 failed` (строк нет).

- [ ] **Шаг 3: обновить документы**

В `agent-contract.md`: старт сессии начинается с `todoc project show`; правило группировки `result.groups`; защита `core`; `record_id` с префиксом проекта; команда `migrate-flat`. В `HOME.md` — карта `projects/*`, счётчики по факту (`todoc types list --root demo`), ссылка на план. В `README.md` — краткое описание раскладки и миграции.

- [ ] **Шаг 4: финализировать и проверить гейты**

Run: `env PYTHONPATH=src python3 -m todoc sync --root demo demo/notes/agent-contract.md demo/HOME.md README.md --apply`
Expected: `applied: true`, `diagnostics_count: 0`.

Run: `env PYTHONPATH=src python3 -m todoc validate --root demo --all && env PYTHONPATH=src python3 -m todoc check-config --root demo`
Expected: `0` ошибок.

Run: `python3 tools/linkcheck.py`
Expected: `0` битых ссылок.

- [ ] **Шаг 5: коммит**

```bash
git add demo/notes/agent-contract.md demo/HOME.md README.md
git commit -m "docs(projects): session contract, demo map and README"
```

## 6. Definition of Done

- [ ] Все задачи 1–18 отмечены; каждый шаг имеет команду проверки и подтверждённый вывод.
- [ ] Полный `pytest` зелёный; `100%` branch coverage по `src/todoc`:

```bash
env PYTHONPATH=src .venv/bin/python -m coverage run --branch --source=src/todoc -m pytest -q
env PYTHONPATH=src .venv/bin/python -m coverage report -m --fail-under=100
```

- [ ] `todoc validate --root demo --all` — `0` ошибок; `todoc check-config --root demo` — `0` ошибок; `tools/linkcheck.py` — `0` битых.
- [ ] Плоский `demo/` открывается без изменений: `layout == "legacy_flat"`, `project == null`, выдача команд прежняя, `result.groups` отсутствует.
- [ ] Новый тестовый датасет раскладки `projects/` проходит сценарий: `project use billing auth` → `docs search` с группами → `docs new` в фокус → `records create` с префиксом id и пути → `skills tree` с каскадом → `change open` в проект → `project migrate-flat`.
- [ ] Коды `project.not_selected`, `project.core_readonly`, `project.core_protected`, `project.out_of_scope`, `project.exists`, `project.not_found`, `project.invalid_slug`, `project.all_projects_readonly`, `layout.outside_projects`, `migration.target_exists` имеют guidance и контрактные тесты.
- [ ] Свежий датасет (`init_dataset`) содержит `dir_types/projects`, `dir_types/project` и правила `reserved-projects`/`projects-subdirs`; `check-config` на нём — `0` ошибок.
- [ ] Документы `agent-contract.md`, `HOME.md`, `README.md` обновлены и синхронизированы.
- [ ] Ревью выполнено; замечания закрыты или вынесены в отдельные баги.

## 7. Риски и митигации

| Риск | Вероятность | Влияние | Митигация | Владелец |
|---|---|---|---|---|
| Дефолтные правила `init_dataset` меняют поведение существующих тестов | С | С | Прогнать полный `pytest` после задачи 2; правила аддитивны (новые id), старые не переименовываются | исполнитель задачи 2 |
| Глубинные маски `**/specs/**` меняют `doc_type` в `demo/` | С | В | Сравнить `doc_type` до/после на снапшоте; при расхождении — точечные исключения | исполнитель задачи 2 |
| Фильтрация после пагинации рвёт страницы и группы | С | В | Сортировать по `project_rank` **до** `page()`; тест на две страницы с разными проектами | исполнитель задач 9–10 |
| Курсор одной выборки принимается выборкой другого скоупа | С | С | Срез скоупа входит в `selection`; тест с двумя курсорами | исполнитель задач 9–12 |
| `result.groups` ломает внешних потребителей | С | С | `items` остаётся плоским и прежним; `groups` — аддитивное поле; контрактный тест | исполнитель задачи 9 |
| `relations graph` меняет форму `nodes` | Н | В | `nodes` остаются строками; границы — отдельное поле `boundary` | исполнитель задачи 11 |
| `disabled_harness` ссылается на несуществующий id | В | Н | `folder.config.unknown_harness_id` уровня `warning`; выдача не падает | исполнитель задачи 15 |
| Миграция теряет файлы при конфликте целевого пути | Н | В | `--preview` обязателен; `apply_move` атомарен; конфликт → `migration.target_exists` до записи | исполнитель задачи 17 |
| План docs-move не влит к моменту задачи 17 | С | С | Задача 17 выполняется после `docs-move-implementation`; фазы 1–3 дают самостоятельный результат | координатор плана |
| Каскад скилов маскирует нужный скил неожиданно | С | С | `shadowed_by` виден в выдаче; `skills read --path` принимает явный путь проекта | исполнитель задачи 15 |
| Плоский датасет случайно получает скоуп | Н | В | Все проверки за `ctx.layout == "projects"`; регрессионный тест на `demo/` | исполнитель задач 9–14 |
| `100%` coverage недостижим из-за ветвей legacy | С | С | Тесты на обе ветки каждой новой функции; исключений в coverage не добавлять | исполнитель всех задач |

## 8. Прогресс и отклонения

- 2026-11-28: план создан из идеи `doc:ideas/multi-project-workspace.md`; открытые вопросы закрыты решениями пользователя (`--with-related` только явно; вместо warning — обязательная группировка по проектам).
- 2026-11-28, аудит перед реализацией. Найдено и исправлено в плане:
  1. `init_dataset` не создавал `dir_types/projects`, `dir_types/project` и правило `projects/*` — свежие датасеты и тестовые фикстуры получали `dir_type: unknown`. Добавлено в задачу 2.
  2. В задаче 3 указаны несуществующие коды диагностик (`folder_config.invalid_field`); заменены на реальные `folder.config.bad_type` и новый `folder.config.unknown_harness_id`.
  3. `relations graph` возвращает `nodes` как список строк; план предлагал объекты. Заменено на отдельное поле `result.boundary`.
  4. Имя `resolve_link_target` уже занято в `markdown.py`; новая функция переименована в `scoped_link_candidates`.
  5. `skills tree` падает с `skills.not_found`, если нет корневого `skills/`; добавлена ветка каскада по умолчанию.
  6. `records create` префиксовал только `record_id`, но `path_template` писал в корневой `tasks/`; добавлен параметр `project` в `create_record_plan`.
  7. В тестах отсутствовала фикстура `projects_root`; добавлена явно.
  8. `selection` курсоров не включал срез скоупа; добавлено требование.
  9. `change open/apply` не были покрыты; добавлены `changes_dirs` и защита артефактов.
  10. Закон «нет файлов вне `projects/`» не проверялся; добавлена диагностика `layout.outside_projects`.
  11. Поля `project` не были добавлены в проекции `docs list/search` и `records`; добавлено.
  12. `_skills_diagnostics` валидировал только корневой vault; добавлена валидация по проектам.
  13. Тест задачи 17 собирал `dataset.json` вручную без типов и правил; переведён на `init_dataset`.
  14. Группировка и `--budget` в `docs search` не были согласованы; зафиксировано правило построения групп по усечённому списку.
  15. `--all-projects` не был запрещён на мутациях; добавлен `project.all_projects_readonly`.
- Задачи ещё не начаты. Отклонения фиксируются здесь: что не собралось, какой тест оказался неверным, какой подход выбран вместо планового и почему. Шаги задним числом не переписываются.
