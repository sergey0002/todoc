---
id: doc:plan/direct-edit-and-sync.md
title: "Прямое редактирование файлов, команда финализации todoc sync и отказ от обязательного docs edit в правилах и промптах"
doc_type: plan
lang: ru
created: 2026-11-27
updated: 2026-11-27
status: in_progress
covers: ["doc:ideas/direct-edit-and-git-sync.md"]
derived_from: ["ideas/direct-edit-and-git-sync.md#section:Суть@sha256:1505299b674277e48f5ea8a2592df3c3d93618ecc032f4c69bf42d11ab9df0c5", "ideas/direct-edit-and-git-sync.md#section:Предложение@sha256:885618969a8d226b352d3e58468f182fbf6d711a560f10d3839c956328f7909f", "ideas/direct-edit-and-git-sync.md#section:Решённые вопросы (закрыты при переходе в план)@sha256:9335031491c3e57caf2040d9e061f3c2afc0bb6751adf3abfc88631cf70f9d66"]
tags: [plan, direct-edit, sync, cli, prompts, rules, history, guidance]
related: ["[[direct-edit-and-git-sync]]", "[[cli-model-guidance-and-hint-catalog]]", "[[agent-contract]]", "[[constitution.md]]", "[[bug-004--docs-edit-не-умеет-вставку-и-удаление-строк]]", "[[bug-012-history-revizii-mutiruyuschih-komand-zagryaznyayut-git-status]]", "[[bug-014-docs-edit-preview-ne-pokazyvaet-numeraciyu-rezultata]]"]
---

# Прямое редактирование файлов, команда финализации `todoc sync` и отказ от обязательного `docs edit` в правилах и промптах — план реализации

> **Резюме для занятого человека (без погружения в контекст):**
> - **Суть простыми словами:** снимаем с ИИ-агента и человека обязанность править тексты через тяжёлые команды с номерами строк — теперь любые файлы в базе знаний редактируются напрямую как обычный текст, а следом запускается одна быстрая команда `todoc sync`, которая сама приводит метаданные и проверки в порядок.
> - **Зачем делаем сейчас:** старый способ правки через файлы-патчи сжигал в 5–10 раз больше токенов, постоянно промахивался по номерам строк и заставлял вручную вычищать служебный мусор из Git перед каждым сохранением работы.
> - **Что получим на выходе:** 1) быструю команду `todoc sync`, которая за долю секунды обновляет дату правки, историю изменений, поисковый индекс и останавливает случайную порчу автособираемых витрин с понятной подсказкой; 2) чистый Git без служебных файлов локальной истории; 3) обновлённые правила, скилы и шпаргалки всех 56 типов без навязывания патчей.
> - **Чего в этом плане ТОЧНО НЕ делаем:** не удаляем старую команду `docs edit` (оставляем для совместимости скриптов) и не делаем здесь автоматический обход коммитов Git, авто-документирование и авто-код-ревью — они пойдут отдельным вторым этапом поверх готового ядра `sync`.

> **Исполнителю (агенту):** план самодостаточен — читай его, а не историю сессии.
> Работай по задачам сверху вниз; шаги отмечаются чекбоксами (`- [ ]`) в том же
> коммите, который делает шаг. Начинай всегда с первого неотмеченного.

**Цель:** реализовать ядро `todoc.application.sync` и CLI-команду `todoc sync`, исключить служебный каталог локальной истории `**/.todoc/history/` из трекинга Git и дайджеста конфигурации (`BUG-012`), защитить автособираемые файлы-витрины от случайной ручной правки с понятной подсказкой `guidance` (`P15`) и перевести все правила (`AGENTS.md`, `SKILL.md`, `agent-contract.md`), скилы и стартовые промпты всех 56 типов (`31 doc_types + 25 entity_types`) с обязательного `docs edit --patch-file` на связку «прямая правка + `todoc sync <path>`».
**Спека:** [Идея: прямое редактирование файлов и короткая команда финализации `todoc sync <path>`](../ideas/direct-edit-and-git-sync.md) (`doc:ideas/direct-edit-and-git-sync.md`), [Конституция `todoc` (`P1`, `P11`, `P15`)](constitution.md) (`doc:constitution`), [Контракт CLI для агента](../notes/agent-contract.md) (`doc:agent-contract`), [`BUG-012`](../bugs/bug-012-history-revizii-mutiruyuschih-komand-zagryaznyayut-git-status.md).
**Стек:** Python 3.11+ (`click`, `jsonschema`, `markdown-it-py` — без новых runtime-зависимостей; `pytest` + `coverage` со `100%` branch coverage на новых и изменённых модулях `src/todoc/`).

## 1. Критерии успеха

1. Команда `todoc sync --root <PATH> [PATHS...] [--dirty] [--if-hash H] [--allow-derived] [--no-history]` работает как с путями от корня базы (`ideas/foo.md`), так и с путями от текущей рабочей директории (`demo/ideas/foo.md`), за один вызов бампит `updated:` при содержательном изменении `.md`, пишет событие истории `before/after + ranges`, сбрасывает `parse_cache`, обновляет индекс и возвращает компактный JSON-конверт (`ok`, `data.synced`, `diagnostics`, `guidance`).
2. При прямой ручной правке автособираемого файла-витрины (тип с `"generated": true` в `type.json`, документ с `generated: true` во front matter или рендер `flow render --write` с маркером `<!-- СГЕНЕРИРОВАНО:`) `todoc sync` без флага `--allow-derived` останавливается с ошибкой `docs.derived_edited_directly` (код выхода `3`, `EXIT_VALIDATION`) и заполненным полем `guidance`, указывающим на записи-источники из `derived_from`, при этом обычные авторские документы с якорями свежести `derived_from` (`doc_type: plan`) синхронизируются без блокировки.
3. Служебная папка `**/.todoc/history/` добавлена в `.gitignore` и исключена из `_config_digest` в `registry.py`, файл `demo/.todoc/history/journal.jsonl` снят с индекса Git (`git rm --cached`), повторные вызовы `todoc sync` / `docs status` оставляют `git status --porcelain` полностью чистым (`BUG-012` переведён в `fixed`), а `GitBackend.read_at` корректно читает `HEAD:./<rel_path>`, когда `DATA_ROOT` расположен в подпапке репозитория (`demo/`).
4. Генератор дефолтных препромптов `src/todoc/typing_system/prompts.py`, `AGENTS.md`, `SKILL.md`, `demo/skill/SKILL.md`, `demo/notes/agent-contract.md`, скилы в `demo/skills/` и `demo/skill/` и все `56` типов в `demo/.todoc/{doc_types,entity_types}/` (`12` стандартных + `43` кастомных + `doc_types/export/prompts/edit.md`) переведены на прямую правку + `todoc sync <path>` с полным сохранением предметных правил в `43` кастомных типах.
5. Все тесты `pytest` проходят со **`100%` branch coverage** на `src/todoc/application/sync.py` и всех изменённых модулях `src/todoc/`, `todoc check-config --root demo` — `0` диагностик, `todoc validate --root demo --all` — `0` диагностик, `todoc stale --root demo` — `0` устаревших документов, `tools/linkcheck.py` — `0` битых ссылок.

## 2. Вне скоупа

- Удаление команд `todoc docs edit` и `todoc records create` — **не делаем**: они сохраняются для обратной совместимости и внешних без-агентных скриптов.
- Обход коммитов Git (`todoc sync --from-git` по диапазону `last_synced_head..HEAD`), установка Git-хуков (`pre-commit` / `post-merge`), а также пост-коммитные конвейеры `auto-docs`, `auto-review` и `plan-drift` — **не делаем в этом плане** (отложены на Этап 2 поверх готовой функции `sync_file`).
- Миграция хранилища истории на SQLite (`history.sqlite`) — **не делаем** (отдельная идея `sqlite-storage-drivers.md`).

## 3. Глобальные ограничения

- Python `3.11+`, только стандартная библиотека и текущие зависимости `pyproject.toml` (`click`, `jsonschema`, `markdown-it-py`) — никаких новых пакетов.
- **`100%` branch coverage** (`pytest --cov=todoc --cov-branch`) на новом модуле `src/todoc/application/sync.py` и на всех затронутых строках/ветках `src/todoc/`.
- **Тонкий слой CLI** (шов прямой совместимости с `docs/plan/todoc-master-refactoring-plan.md` Э2–Э3): модуль `src/todoc/application/sync.py` не импортирует `click` и не пишет в `stdout`/`stderr`, возвращая чистую структуру результата, список `Diagnostic` и словарь `guidance`.
- Поля `created` и `updated` во front matter существующих документов `demo/` руками не редактируются — их обновляет только движок (`todoc sync` / `docs new`).
- В `43` кастомных файлах `demo/.todoc/{doc_types,entity_types}/*/prompts/{create,edit}.md` запрещено затирать предметные секции (`Правила`, `Типичные правки`, `Запрещено`, `Структура`) шаблонной рыбой `build_prompts` — меняется строго инструкция механики правки (`## Как` / `## Как править`) и примечание о бампe `updated`.
- Счётчики в корневом `README.md` (число листовых и верхнеуровневых команд CLI, число документов и записей в `demo/`) обязаны совпадать с фактическим выводом CLI (`BUG-003`).

## 4. Архитектура и файловая карта

Вся логика пост-финализации сосредотачивается в чистом модуле прикладного слоя `src/todoc/application/sync.py`, который переиспользует существующие примитивы записи (`atomic_write`), истории (`record_write`, `content_at`, `GitBackend`), кэша (`invalidate_parse_cache`, `DatasetContext.rebuild_index`) и валидации (`validate_dataset`). Отличие автособираемых файлов-витрин от обычных документов с якорями свежести задаётся декларативным булевым полем `"generated": true` в `type.json` типа документа (`KIND_FIELDS["doc_type"]`), а `GitBackend.read_at` получает префикс `./` в `git show {revision}:./{rel_path}`, чтобы безошибочно доставать образ «до» в подкаталогах Git-репозитория (`demo/`).

| Файл | Действие | Ответственность |
|---|---|---|
| `.gitignore` | Modify (`:18-23`) | Исключение `**/.todoc/history/` из трекинга Git наравне с `index/`, `cache/`, `generated/` (`BUG-012`). |
| `src/todoc/application/registry.py` | Modify (`:17-27`) | Исключение `.todoc/history/*.json` (`refs.json`) из `_config_digest`, чтобы запись в локальную историю не сбрасывала `corpus_digest` индекса. |
| `src/todoc/adapters/history/backends.py` | Modify (`:76-88`) | Починка `GitBackend.read_at`: вызов `git show {revision}:./{rel_path}` для работы `DATA_ROOT` в подпапках репозитория. |
| `src/todoc/typing_system/descriptors.py` | Modify (`:93-105`, `:235-265`) | Разрешение опционального поля `"generated": bool` в `KIND_FIELDS["doc_type"]` и его проверка в `descriptor_diagnostics`. |
| `src/todoc/application/write.py` | Modify (`:165-230`) | Выделение переиспользуемой функции `bump_front_matter_updated(text: str, today: str | None = None) -> tuple[str, bool]` (используется и в `apply_edit_ops`, и в `sync_files`). |
| `src/todoc/application/sync.py` | Create | Чистый сервис синхронизации: `normalize_sync_path`, `detect_dirty_paths`, `sync_files`, 3-ступенчатая защита автособираемых витрин, расчёт `before/after + ranges`, фильтрация диагностик и сборка подсказки `guidance` (`P15`). |
| `src/todoc/service.py` | Modify (`:165-188`) | Опциональный параметр `observe: bool = True` в `DatasetContext.rebuild_index`, чтобы `--no-history` не создавал `.todoc/history/` при пересборке индекса. |
| `src/todoc/output/envelope.py` | Modify (`:13-60`) | Поля `guidance: dict[str, Any] | None = None` и `include_guidance: bool = False` в `@dataclass Envelope`, сериализация в `to_dict()` и рендер в режимах `table`/`markdown`. |
| `src/todoc/cli.py` | Modify (`:45-75`, `:610-625`) | Регистрация верхнеуровневой команды `todoc sync` и проброс поля `guidance` в конверт ответа. |
| `src/todoc/typing_system/prompts.py` | Modify (`:95-225`) | Новые шаблоны `create_prompt` и `edit_prompt`: прямая правка файла + `todoc sync --root KB <path>` вместо сборки `patch.json` и пересоздания записей через удаление. |
| `demo/.todoc/doc_types/export/type.json` и `demo/.todoc/doc_types/export/prompts/edit.md` | Modify / Create | Пометка `"generated": true` на `export` и явная шпаргалка о запрете ручной правки автособираемой витрины. |
| `AGENTS.md`, `SKILL.md`, `demo/skill/SKILL.md`, `demo/skill/doc-flow-capture/SKILL.md`, `demo/skill/doc-spec-write/SKILL.md`, `demo/notes/agent-contract.md`, `demo/skills/docs/todoc-docs/SKILL.md`, `demo/skills/process/{todoc-capture,todoc-plan,todoc-execute}/SKILL.md`, `demo/.todoc/{doc_types,entity_types}/*/prompts/{create,edit}.md`, `README.md`, `demo/bugs/bug-012-*.md` | Modify | Перевод правил, скилов и всех 56 типов на прямую правку + `todoc sync`, закрытие `BUG-012` и синхронизация фактических счётчиков `README.md` (`64` листовых команды). |
| `tests/unit/test_sync_foundations.py`, `tests/unit/test_sync.py`, `tests/cli/test_cli_sync.py`, `tests/unit/test_type_assets.py`, `tests/unit/test_demo_prompts_policy.py` | Create / Modify | Полное модульное, CLI- и политическое покрытие (`100%` веток) без единой заглушки. |

## 5. Задачи

### Задача 1: Починка `GitBackend.read_at` в подпапке репозитория, изоляция `.todoc/history/` из `_config_digest` и Git (`BUG-012`) и флаг `"generated": bool` в `doc_type`

**Файлы:**
- Modify: `.gitignore:18-23`
- Modify: `src/todoc/application/registry.py:17-27`
- Modify: `src/todoc/adapters/history/backends.py:76-88`
- Modify: `src/todoc/typing_system/descriptors.py:93-105` и `:235-265`
- Modify: `src/todoc/application/write.py:165-205`
- Modify: `demo/.todoc/doc_types/export/type.json`
- Test: `tests/unit/test_sync_foundations.py`

**Интерфейсы:**
- Consumes: `GitBackend(root: Path)`, `RegistryStore(root: Path).config_digest()`, `descriptor_diagnostics(root, dataset, kind, descriptor, rel_config)`
- Produces:
  - `GitBackend.read_at(revision: str | None, rel_path: str) -> bytes | None` (читает `f"{revision}:./{clean_rel}"` относительно `cwd=self.root`)
  - `_config_digest(root: Path) -> str` в `registry.py` игнорирует `"history" in path.parts`
  - `"generated"` в `KIND_FIELDS["doc_type"]` (валидируется как `bool`: не-`bool` даёт диагностику `config.invalid_schema`)
  - `bump_front_matter_updated(text: str, today: str | None = None) -> tuple[str, bool]` в `src/todoc/application/write.py`

- [x] **Шаг 1: написать падающий тест** в `tests/unit/test_sync_foundations.py`

```python
from __future__ import annotations

import subprocess
from pathlib import Path

from todoc.adapters.history.backends import GitBackend
from todoc.application.registry import RegistryStore
from todoc.application.write import bump_front_matter_updated
from todoc.typing_system.descriptors import descriptor_diagnostics


def test_git_backend_read_at_resolves_dataset_inside_repo_subdir(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    kb = tmp_path / "demo"
    (kb / "ideas").mkdir(parents=True)
    doc = kb / "ideas" / "sample.md"
    doc.write_text("# v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
    doc.write_text("# v2\n", encoding="utf-8")

    backend = GitBackend(kb)
    head = backend.head()
    assert head is not None
    assert backend.read_at(head, "ideas/sample.md") == b"# v1\n"
    assert backend.read_at(head, "./ideas/sample.md") == b"# v1\n"


def test_config_digest_ignores_history_refs_json(tmp_path: Path) -> None:
    (tmp_path / ".todoc").mkdir()
    (tmp_path / ".todoc" / "dataset.json").write_text('{"schema_version": 1}\n', encoding="utf-8")
    store = RegistryStore(tmp_path)
    before = store.config_digest()
    refs = tmp_path / ".todoc" / "history" / "refs.json"
    refs.parent.mkdir(parents=True)
    refs.write_text('{"head": "rev-1", "tags": {}}\n', encoding="utf-8")
    assert store.config_digest() == before


def test_doc_type_generated_field_accepts_bool_and_rejects_non_bool(tmp_path: Path) -> None:
    dataset = {"document_types": "doc_types"}
    type_dir = tmp_path / ".todoc" / "doc_types" / "export"
    type_dir.mkdir(parents=True)
    for op in ("read", "create", "edit", "delete"):
        p = type_dir / "prompts" / f"{op}.md"
        p.parent.mkdir(exist_ok=True)
        p.write_text(f"# {op}\n", encoding="utf-8")

    ok_diags = descriptor_diagnostics(
        tmp_path, dataset, "doc_type",
        {"schema_version": 1, "type_id": "export", "version": "1.0", "kind": "doc_type",
         "description": "d", "format": "markdown", "generated": True},
        ".todoc/doc_types/export/type.json",
    )
    assert ok_diags == []

    bad_diags = descriptor_diagnostics(
        tmp_path, dataset, "doc_type",
        {"schema_version": 1, "type_id": "export", "version": "1.0", "kind": "doc_type",
         "description": "d", "format": "markdown", "generated": "yes"},
        ".todoc/doc_types/export/type.json",
    )
    assert any(d["code"] == "config.invalid_schema" and "generated" in d["message"] for d in bad_diags)


def test_bump_front_matter_updated_handles_present_same_unclosed_and_absent_fm() -> None:
    src = "---\nid: doc:a\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n\n# A\n"
    new_text, bumped = bump_front_matter_updated(src, today="2026-11-27")
    assert bumped is True
    assert "updated: 2026-11-27\n" in new_text

    same_text, bumped_again = bump_front_matter_updated(new_text, today="2026-11-27")
    assert bumped_again is False
    assert same_text == new_text

    no_updated_key = "---\nid: doc:b\n---\n\n# B\n"
    unchanged_fm, bumped_no_key = bump_front_matter_updated(no_updated_key, today="2026-11-27")
    assert bumped_no_key is False
    assert unchanged_fm == no_updated_key

    no_fm, bumped_no_fm = bump_front_matter_updated("# Plain\n", today="2026-11-27")
    assert bumped_no_fm is False
    assert no_fm == "# Plain\n"
```

- [x] **Шаг 2: убедиться, что тест падает**

Run: `.venv/bin/pytest tests/unit/test_sync_foundations.py -v`
Expected: FAIL (`ImportError: cannot import name 'bump_front_matter_updated'`, а после добавления заглушки — падение `read_at` в подпапке, изменение `config_digest` и `Unknown field 'generated'`).

- [x] **Шаг 3: реализовать изменения в `registry.py`, `backends.py`, `descriptors.py`, `write.py`, `export/type.json` и `.gitignore`**
  1. В `src/todoc/application/registry.py:21` добавить `"history"` в условие пропуска служебных папок: `if any(p in path.parts for p in ("index", "cache", "generated", "history")): continue`.
  2. В `src/todoc/adapters/history/backends.py:82` нормализовать путь `clean_rel = rel_path.lstrip("./")` и вызывать `("git", "show", f"{revision}:./{clean_rel}")`.
  3. В `src/todoc/typing_system/descriptors.py` добавить `"generated"` в `KIND_FIELDS["doc_type"]`, а в `descriptor_diagnostics` проверить: если `"generated" in descriptor` и `not isinstance(descriptor["generated"], bool)`, добавить диагностику `config.invalid_schema` (`"generated must be a boolean."`).
  4. В `src/todoc/application/write.py` вынести `bump_front_matter_updated(text: str, today: str | None = None) -> tuple[str, bool]` (аккуратно обходя строки до закрывающего `---` и не меняя текст при `bumped == False`) и переиспользовать её внутри `apply_edit_ops`.
  5. В `demo/.todoc/doc_types/export/type.json` добавить `"generated": true` и создать `demo/.todoc/doc_types/export/prompts/edit.md` (так как у `export` раньше не было `edit.md`!).
  6. В `.gitignore` добавить строку `**/.todoc/history/` сразу под `**/.todoc/generated/` и выполнить `git rm --cached demo/.todoc/history/journal.jsonl` (оставив локальный файл на диске).

- [x] **Шаг 4: убедиться, что тесты проходят со 100% покрытием**

Run: `.venv/bin/pytest tests/unit/test_sync_foundations.py tests/unit/test_history.py tests/unit/test_type_assets.py -v --cov=todoc.adapters.history.backends --cov=todoc.application.registry --cov=todoc.typing_system.descriptors --cov=todoc.application.write --cov-branch`
Expected: PASS, `.venv/bin/todoc check-config --root demo` возвращает `"ok": true` и `0` диагностик.

- [x] **Шаг 5: коммит**

```bash
git add .gitignore src/todoc/application/registry.py src/todoc/adapters/history/backends.py src/todoc/typing_system/descriptors.py src/todoc/application/write.py demo/.todoc/doc_types/export/ tests/unit/test_sync_foundations.py
git commit -m "feat(core): fix subdir GitBackend.read_at, isolate .todoc/history (BUG-012), and add doc_type generated flag"
```

---

### Задача 2: Реализация сервисного ядра `src/todoc/application/sync.py` и поля `guidance` в `Envelope`

**Файлы:**
- Create: `src/todoc/application/sync.py`
- Modify: `src/todoc/service.py:165-188`
- Modify: `src/todoc/output/envelope.py:13-60`
- Test: `tests/unit/test_sync.py`

**Интерфейсы:**
- Consumes:
  - `DatasetContext` из `src/todoc/service.py`
  - `bump_front_matter_updated` из `src/todoc/application/write.py`
  - `invalidate_parse_cache` из `src/todoc/application/registry.py`
  - `open_backend`, `record_write` из `src/todoc/application/history.py`
  - `journal.read_events`, `objects.read_snapshot` из `src/todoc/adapters/history/`
- Produces:
  - В `src/todoc/output/envelope.py`:
    ```python
    @dataclass
    class Envelope:
        ok: bool
        data: dict[str, Any] = field(default_factory=dict)
        diagnostics: list[dict[str, Any]] = field(default_factory=list)
        next_actions: list[dict[str, Any]] = field(default_factory=list)
        schema_version: int = 1
        guidance: dict[str, Any] | None = None
        include_guidance: bool = False
    ```
    `to_dict()` включает `"guidance": self.guidance`, когда `self.include_guidance or self.guidance is not None`; `emit()` в текстовом режиме добавляет строку `guidance: ...`, когда `envelope.guidance` не `None`.
  - В `src/todoc/service.py`: `DatasetContext.rebuild_index(self, force: bool = True, observe: bool = True) -> dict[str, Any]`.
  - В `src/todoc/application/sync.py`:
    - `normalize_sync_path(root: Path, raw_path: str, cwd: Path | None = None) -> str`
    - `detect_dirty_paths(ctx: DatasetContext) -> list[str]`
    - `sync_files(ctx: DatasetContext, raw_paths: Sequence[str] = (), *, dirty: bool = False, expected_hash: str | None = None, allow_derived: bool = False, record_history: bool = True, cwd: Path | None = None) -> dict[str, Any]`

**Точный алгоритм `sync_files` (без двусмысленностей):**
1. **Нормализация пути (`normalize_sync_path`):** если `raw_path` абсолютный — проверяется принадлежность `root.resolve()`; если относительный — сначала проверяется `(cwd / raw_path).resolve()` (если он лежит внутри `root.resolve()` и отличается от самого `root.resolve()`, например `demo/notes/a.md` при запуске из корня репо), иначе интерпретируется как `(root / raw_path).resolve()`. Выход за пределы `root` поднимает `AccessError(..., "access.outside_data_root")`; путь с первым сегментом `.todoc` поднимает `ValidationError(..., "sync.internal_path")`.
2. **Вычисление списка целей (`detect_dirty_paths`):**
   - Из `current = ctx.store.load_current()` строится словарь `indexed = {d["path"]: d["hash"] for d in (current or {}).get("documents") or []}` (в `current["documents"]` лежат все отсканированные файлы `.md`, `.json`, `.csv`).
   - Прогоняется `scanned_files = ctx.scan()[1]`, `scanned = {f.rel_path: f.hash for f in scanned_files}`.
   - Грязными считаются `sorted([p for p, h in scanned.items() if indexed.get(p) != h] + [p for p in indexed if p not in scanned])`.
   - Если передан `expected_hash is not None` и `len(targets) != 1` — бросается `ValidationError("--if-hash requires exactly one target path", "sync.if_hash_multi_target")`.
3. **Образ `before` и проверка `--if-hash`:**
   - Предыдущий хеш `prev_hash` берётся из `indexed.get(rel_path)` (или последней записи `after` в `journal.read_events(ctx.root)`). Образ байтов `before_bytes` достаётся из `backend.read_at(backend.head(), rel_path)` (для `GitBackend`) или последнего снимка в `objects` при наличии.
   - Если задан `expected_hash`, он сравнивается с `current_disk_hash` и с `prev_hash`: если ни один не совпал — бросается `ConflictError(..., "write.hash_mismatch")`.
4. **3-ступенчатая защита автособираемых файлов-витрин (`docs.derived_edited_directly`):**
   - Для существующего `.md`-файла читаются `front_matter` и тело (`parse_markdown`), а его `doc_type` вычисляется через `resolve_type(ctx.doc_rules, ...)` / `front_matter.get("doc_type")`.
   - Файл признаётся автособираемой витриной, если выполняется хотя бы одно из трёх условий:
     1) дескриптор его `doc_type` в `ctx.registry_types.doc_types` содержит `"generated": True` (например, `export`);
     2) во `front_matter` явно указано `"generated": True`;
     3) в теле присутствует генераторная метка `"<!-- СГЕНЕРИРОВАНО:"` (либо `doc_type == "flow-doc"` и во `front_matter` есть `"derived_from"`).
   - Авторские документы (`doc_type: plan`, `spec-doc`, `idea` и др.) без `"generated": True` и без метки `"<!-- СГЕНЕРИРОВАНО:"` **не блокируются**, даже когда несут `derived_from` для контроля свежести.
   - Если автособираемая витрина изменена (`prev_hash != current_disk_hash`) и `allow_derived is False`, файл **не перезаписывается**, добавляется диагностика `code="docs.derived_edited_directly"`, `severity="error"`, `path=rel_path`, а в `guidance` пишется `{"code": "sync.derived_view_blocked", "sources": derived_sources, "fix_hint": "..."}`.
5. **Автобамп `updated:`, история, кэш и диагностики:**
   - Если файл удалён с диска (`not target.exists()`): вызывается `invalidate_parse_cache(ctx.root, rel_path)`, при `record_history` пишется `record_write(..., before_bytes, b"", kind="file.delete", basis="todoc sync")`, статус элемента `{"path": rel_path, "status": "deleted", "hash": None, "updated_bumped": False}`.
   - Если файл существует и `prev_hash == current_disk_hash`: статус `"unchanged"`, диск и история не трогаются.
   - Если файл существует и изменился (и не заблокирован защитой витрин): для `.md` вызывается `bump_front_matter_updated(text)` и при `bumped == True` выполняется `atomic_write(target, new_text)`. Сбрасывается `invalidate_parse_cache(ctx.root, rel_path)`, при `record_history` вызывается `record_write(ctx.root, rel_path, before_bytes, final_bytes, kind="doc.sync" if suffix == ".md" else "record.sync", basis="todoc sync", backend=backend)`.
   - В конце вызывается `ctx.rebuild_index(force=True, observe=record_history)`, из нового снимка индекса выбираются диагностики по `target_set` (плюс заблокированные витрины). При наличии ошибок с `severity == "error"` возвращается `ok: False` и `guidance` (`"sync.derived_view_blocked"` или `"sync.validation_failed"`).

- [x] **Шаг 1: написать полный падающий модульный тест** в `tests/unit/test_sync.py`

```python
from __future__ import annotations

import subprocess
from pathlib import Path
import pytest

from todoc.adapters.filesystem.scanner import file_hash
from todoc.application.sync import detect_dirty_paths, normalize_sync_path, sync_files
from todoc.config import init_dataset
from todoc.errors import AccessError, ConflictError, ValidationError
from todoc.output.envelope import emit, make_envelope
from todoc.service import DatasetContext


def _init_git_kb(tmp_path: Path) -> tuple[Path, Path]:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    kb = tmp_path / "demo"
    init_dataset(kb)
    # Регистрируем тип export с generated: true и тип plan без generated
    exp_dir = kb / ".todoc" / "doc_types" / "export"
    exp_dir.mkdir(parents=True, exist_ok=True)
    (exp_dir / "type.json").write_text(
        '{"schema_version": 1, "type_id": "export", "version": "1.0", "kind": "doc_type", '
        '"description": "Generated export", "format": "markdown", "generated": true}\n',
        encoding="utf-8",
    )
    (kb / "notes").mkdir(parents=True, exist_ok=True)
    (kb / "exports").mkdir(parents=True, exist_ok=True)
    (kb / "plan").mkdir(parents=True, exist_ok=True)
    (kb / "notes" / "hello.md").write_text(
        "---\nid: doc:notes/hello.md\ntitle: Привет\ndoc_type: note\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n\n# Привет\n\n## Суть\n\nТекст v1.\n",
        encoding="utf-8",
    )
    (kb / "exports" / "view.md").write_text(
        '---\nid: doc:exports/view.md\ntitle: Экспорт\ndoc_type: export\nderived_from: ["notes/hello.md@sha256:111"]\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n\n# Экспорт\n\nv1\n',
        encoding="utf-8",
    )
    (kb / "plan" / "p1.md").write_text(
        '---\nid: doc:plan/p1.md\ntitle: План\ndoc_type: note\nderived_from: ["notes/hello.md@sha256:111"]\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n\n# План\n\n## Суть\n\nШаг 1\n',
        encoding="utf-8",
    )
    ctx = DatasetContext(kb)
    ctx.rebuild_index(force=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path, kb


def test_normalize_sync_path_accepts_root_relative_cwd_relative_and_guards_bounds(tmp_path: Path) -> None:
    repo, kb = _init_git_kb(tmp_path)
    assert normalize_sync_path(kb, "notes/hello.md", cwd=repo) == "notes/hello.md"
    assert normalize_sync_path(kb, "demo/notes/hello.md", cwd=repo) == "notes/hello.md"
    assert normalize_sync_path(kb, str(kb / "notes" / "hello.md"), cwd=repo) == "notes/hello.md"
    with pytest.raises(AccessError):
        normalize_sync_path(kb, "../outside.md", cwd=kb)
    with pytest.raises(ValidationError):
        normalize_sync_path(kb, ".todoc/dataset.json", cwd=kb)


def test_sync_files_bumps_updated_records_ranges_and_is_idempotent(tmp_path: Path) -> None:
    repo, kb = _init_git_kb(tmp_path)
    note = kb / "notes" / "hello.md"
    note.write_text(note.read_text(encoding="utf-8").replace("Текст v1.", "Текст v2."), encoding="utf-8")

    ctx = DatasetContext(kb)
    res = sync_files(ctx, ["demo/notes/hello.md"], cwd=repo)
    assert res["ok"] is True
    assert res["diagnostics"] == []
    assert res["guidance"] is None
    assert res["synced"][0]["path"] == "notes/hello.md"
    assert res["synced"][0]["status"] == "synced"
    assert res["synced"][0]["updated_bumped"] is True
    assert "updated: 2026-01-01" not in note.read_text(encoding="utf-8")

    res2 = sync_files(ctx, ["notes/hello.md"], cwd=repo)
    assert res2["synced"][0]["status"] == "unchanged"
    assert res2["synced"][0]["updated_bumped"] is False


def test_sync_blocks_generated_view_unless_allow_derived_and_allows_plan_with_derived_from(tmp_path: Path) -> None:
    repo, kb = _init_git_kb(tmp_path)
    exp = kb / "exports" / "view.md"
    exp.write_text(exp.read_text(encoding="utf-8").replace("v1", "ручная правка"), encoding="utf-8")
    plan = kb / "plan" / "p1.md"
    plan.write_text(plan.read_text(encoding="utf-8").replace("Шаг 1", "Шаг 1 выполнен"), encoding="utf-8")

    ctx = DatasetContext(kb)
    # Авторский документ с derived_from проходит без блокировки
    res_plan = sync_files(ctx, ["plan/p1.md"], cwd=repo)
    assert res_plan["ok"] is True
    assert res_plan["synced"][0]["updated_bumped"] is True

    # Автособираемая витрина блокируется с ошибкой и guidance
    res_exp = sync_files(ctx, ["exports/view.md"], cwd=repo)
    assert res_exp["ok"] is False
    assert any(d["code"] == "docs.derived_edited_directly" for d in res_exp["diagnostics"])
    assert res_exp["guidance"] is not None
    assert res_exp["guidance"]["code"] == "sync.derived_view_blocked"
    assert "notes/hello.md@sha256:111" in res_exp["guidance"]["sources"]

    # С флагом allow_derived=True проходит
    res_allow = sync_files(ctx, ["exports/view.md"], allow_derived=True, cwd=repo)
    assert res_allow["ok"] is True


def test_sync_dirty_mode_deleted_file_if_hash_and_no_history(tmp_path: Path) -> None:
    repo, kb = _init_git_kb(tmp_path)
    note = kb / "notes" / "hello.md"
    old_hash = file_hash(note)
    note.write_text(note.read_text(encoding="utf-8").replace("Текст v1.", "Текст v3."), encoding="utf-8")

    ctx = DatasetContext(kb)
    assert "notes/hello.md" in detect_dirty_paths(ctx)

    # Неверный --if-hash -> ConflictError; несколько целей с --if-hash -> ValidationError
    with pytest.raises(ValidationError):
        sync_files(ctx, ["notes/hello.md", "plan/p1.md"], expected_hash=old_hash, cwd=repo)
    with pytest.raises(ConflictError):
        sync_files(ctx, ["notes/hello.md"], expected_hash="sha256:deadbeef", cwd=repo)

    # Старый хеш до прямой правки принимается!
    res_ok = sync_files(ctx, ["notes/hello.md"], expected_hash=old_hash, record_history=False, cwd=repo)
    assert res_ok["ok"] is True

    # Удаление файла и автоматический режим без путей (--dirty)
    (kb / "plan" / "p1.md").unlink()
    res_del = sync_files(ctx, (), dirty=True, record_history=False, cwd=repo)
    assert any(item["path"] == "plan/p1.md" and item["status"] == "deleted" for item in res_del["synced"])


def test_envelope_guidance_backward_compatible_and_table_emit(capsys) -> None:
    plain = make_envelope(True, {"a": 1})
    assert "guidance" not in plain.to_dict()

    with_null = make_envelope(True, {"a": 1}, include_guidance=True)
    assert "guidance" in with_null.to_dict() and with_null.to_dict()["guidance"] is None

    with_obj = make_envelope(False, {"a": 1}, guidance={"code": "x", "summary": "fix it"}, include_guidance=True)
    emit(with_obj, "table")
    out = capsys.readouterr().out
    assert "guidance:" in out
```

- [x] **Шаг 2: убедиться, что тест падает**

Run: `.venv/bin/pytest tests/unit/test_sync.py -v`
Expected: FAIL с `ModuleNotFoundError: No module named 'todoc.application.sync'`.

- [x] **Шаг 3: реализовать `src/todoc/application/sync.py`, обновить `DatasetContext.rebuild_index(..., observe: bool = True)` в `src/todoc/service.py` и `Envelope` в `src/todoc/output/envelope.py`**

- [x] **Шаг 4: убедиться, что модульные тесты проходят со 100% branch coverage**

Run: `.venv/bin/pytest tests/unit/test_sync.py -v --cov=todoc.application.sync --cov=todoc.output.envelope --cov-branch --cov-report=term-missing`
Expected: PASS, покрытие `src/todoc/application/sync.py` и `src/todoc/output/envelope.py` — `100%` веток (`0` пропущенных).

- [x] **Шаг 5: коммит**

```bash
git add src/todoc/application/sync.py src/todoc/service.py src/todoc/output/envelope.py tests/unit/test_sync.py
git commit -m "feat(sync): implement sync_files engine with updated bump, history ranges, and generated-view guard"
```

---

### Задача 3: Регистрация тонкой CLI-команды `todoc sync` и интеграционные тесты CLI

**Файлы:**
- Modify: `src/todoc/cli.py:45-75` и `:610-625`
- Test: `tests/cli/test_cli_sync.py`

**Интерфейсы:**
- Consumes: `sync_files` из `src/todoc/application/sync.py`, `_contexts`, `emit`, `make_envelope` из `src/todoc/cli.py` / `envelope.py`, `EXIT_VALIDATION` из `src/todoc/errors.py`
- Produces: листовая верхнеуровневая команда Click:
  ```text
  todoc sync [--root PATH] [PATHS]... [--dirty] [--if-hash TEXT] [--allow-derived] [--no-history] [--output json|table|markdown] [--out FILE]
  ```
  Коды выхода: `0` при `ok: true`, `3` (`EXIT_VALIDATION`) при `ok: false` (ошибки валидации или `docs.derived_edited_directly`), `5` (`EXIT_CONFLICT`) при `ConflictError` (`--if-hash`), `4` (`EXIT_ACCESS`) при выходе пути за пределы `DATA_ROOT`.

- [ ] **Шаг 1: написать полный падающий CLI-тест** в `tests/cli/test_cli_sync.py` (с использованием обёртки `_run(runner, args)` для трансляции `TodocError.exit_code`, как в `tests/cli/test_cli.py:9`)

```python
from __future__ import annotations

import json
from pathlib import Path
from click.testing import CliRunner

from todoc.cli import cli
from todoc.errors import TodocError


def _run(runner: CliRunner, args: list[str]):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


def test_cli_sync_direct_edit_dirty_derived_block_and_conflicts(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    kb = tmp_path / "kb"
    assert _run(runner, ["init", "--root", str(kb)]).exit_code == 0
    res_new = _run(runner, ["docs", "new", "--root", str(kb), "--type", "note",
                            "--title", "Заметка", "--path", "notes/n1.md"])
    assert res_new.exit_code == 0

    note = kb / "notes" / "n1.md"
    lines = [ln for ln in note.read_text(encoding="utf-8").splitlines() if "<!--" not in ln]
    lines.append("Содержательный абзац.")
    note.write_text("\n".join(lines) + "\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    # 1. Путь относительно CWD (kb/notes/n1.md)
    res_sync = _run(runner, ["sync", "--root", "kb", "kb/notes/n1.md"])
    assert res_sync.exit_code == 0, res_sync.output
    payload = json.loads(res_sync.output)
    assert payload["ok"] is True
    assert payload["data"]["synced"][0]["path"] == "notes/n1.md"
    assert payload["guidance"] is None

    # 2. Режим без аргументов (автопоиск грязных файлов) + --output table
    note.write_text(note.read_text(encoding="utf-8") + "\nЕщё строка.\n", encoding="utf-8")
    res_auto = _run(runner, ["sync", "--root", "kb", "--no-history", "--output", "table"])
    assert res_auto.exit_code == 0
    assert "ok: True" in res_auto.output

    # 3. Блокировка рендера с меткой <!-- СГЕНЕРИРОВАНО: (exit 3 + guidance) и обход --allow-derived
    gen_doc = kb / "notes" / "rendered.md"
    gen_doc.write_text(
        '---\nderived_from: ["notes/n1.md@sha256:000"]\n---\n\n<!-- СГЕНЕРИРОВАНО: flow render -->\n\n# Витрина\n\n## Суть\n\nv1\n',
        encoding="utf-8",
    )
    assert _run(runner, ["index", "rebuild", "--root", "kb"]).exit_code == 0
    gen_doc.write_text(gen_doc.read_text(encoding="utf-8").replace("v1", "ручная правка"), encoding="utf-8")

    res_blocked = _run(runner, ["sync", "--root", "kb", "notes/rendered.md"])
    assert res_blocked.exit_code == 3
    blocked_json = json.loads(res_blocked.output)
    assert blocked_json["ok"] is False
    assert blocked_json["guidance"]["code"] == "sync.derived_view_blocked"

    res_allowed = _run(runner, ["sync", "--root", "kb", "notes/rendered.md", "--allow-derived"])
    assert res_allowed.exit_code == 0

    # 4. Коды ошибок: --if-hash (exit 5) и выход за пределы DATA_ROOT (exit 4)
    assert _run(runner, ["sync", "--root", "kb", "notes/n1.md", "--if-hash", "sha256:bad"]).exit_code == 5
    assert _run(runner, ["sync", "--root", "kb", "../outside.md"]).exit_code == 4
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `.venv/bin/pytest tests/cli/test_cli_sync.py -v`
Expected: FAIL с `No such command 'sync'` (`exit_code == 2`).

- [ ] **Шаг 3: добавить тонкий обработчик `@cli.command("sync")` в `src/todoc/cli.py`**
  - Импортировать `EXIT_VALIDATION` из `todoc.errors` и `sync_files` из `todoc.application.sync`.
  - Поддержать `--out` через существующий `_contained_out(ctx.root, out)`.
  - Сформировать конверт через `make_envelope(res["ok"], {"dataset_id": res["dataset_id"], "synced": res["synced"], "diagnostics_count": len(res["diagnostics"])}, res["diagnostics"], next_actions, guidance=res["guidance"], include_guidance=True)` и при `not res["ok"]` завершать с `sys.exit(EXIT_VALIDATION)`.

- [ ] **Шаг 4: убедиться, что CLI-тесты и весь существующий набор CLI-тестов зелёные**

Run: `.venv/bin/pytest tests/cli/test_cli_sync.py tests/cli/ -v --cov=todoc.application.sync --cov-branch`
Expected: PASS (`100%` branch coverage на `sync.py` и всех новых ветках обработчика `sync` в `cli.py`).

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/cli.py tests/cli/test_cli_sync.py
git commit -m "feat(cli): add 'todoc sync' command for post-direct-edit finalization"
```

---

### Задача 4: Обновление генератора дефолтных препромптов `src/todoc/typing_system/prompts.py`

**Файлы:**
- Modify: `src/todoc/typing_system/prompts.py:95-225`
- Modify: `tests/unit/test_type_assets.py:290-315`

**Интерфейсы:**
- Consumes: `build_prompts(type_id, kind, description, descriptor)`
- Produces: обновлённые функции `read_prompt`, `create_prompt` и `edit_prompt` для `doc_type` и `entity_type`:
  - `create_prompt("doc_type")`: `todoc docs new --type {type_id} --title "<Заголовок>" --path <папка>/<english-slug>.md` → прямое заполнение разделов файла (убрать `<!-- ... -->`, не трогать `created`/`updated`) → `todoc sync --root KB <путь>`.
  - `edit_prompt("doc_type")`: при необходимости прочитать секцию через `todoc docs read --section` → отредактировать файл напрямую штатным редактором (не трогая `created`/`updated`; для автособираемых витрин `"generated": true` править источник, а не витрину) → `todoc sync --root KB <путь>` (убедиться, что `ok: true` и `diagnostics: []`).
  - `edit_prompt("entity_type")`: прочитать запись `todoc records read --id <record_id> --view full` → отредактировать JSON-файл записи напрямую, сохранив `record_id` и `entity_type` (больше никакого анти-паттерна «удалить старый файл, чтобы пересоздать через `records create`»!) → `todoc sync --root KB <путь>`.

- [ ] **Шаг 1: обновить тест в `tests/unit/test_type_assets.py` и убедиться в его падении**

```python
def test_build_prompts_uses_direct_edit_and_todoc_sync():
    doc_edit = build_prompts("spec", "doc_type", "d", SPEC)["edit"]
    assert "todoc sync" in doc_edit
    assert "--patch-file" not in doc_edit

    rec_edit = build_prompts("note", "entity_type", "d", {"type_id": "note"})["edit"]
    assert "todoc sync" in rec_edit
    assert "Удалить старый файл" not in rec_edit
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `.venv/bin/pytest tests/unit/test_type_assets.py -k "prompts" -v`
Expected: FAIL (`assert "todoc sync" in doc_edit`).

- [ ] **Шаг 3: обновить `read_prompt`, `create_prompt` и `edit_prompt` в `src/todoc/typing_system/prompts.py`**

- [ ] **Шаг 4: убедиться, что все тесты `test_type_assets.py` проходят со 100% покрытием**

Run: `.venv/bin/pytest tests/unit/test_type_assets.py -v --cov=todoc.typing_system.prompts --cov-branch`
Expected: PASS (`100%` branch coverage на `prompts.py`).

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/typing_system/prompts.py tests/unit/test_type_assets.py
git commit -m "feat(prompts): switch default type create/edit prompts from docs edit patches to direct edit + todoc sync"
```

---

### Задача 5: Перевод правил, скилов, всех 56 типов в `demo/.todoc/`, закрытие `BUG-012` и финальная сверка счётчиков

**Файлы:**
- Modify: `AGENTS.md`, `SKILL.md`, `demo/skill/SKILL.md`, `demo/notes/agent-contract.md`
- Modify: `demo/skills/docs/todoc-docs/SKILL.md`, `demo/skills/process/todoc-capture/SKILL.md`, `demo/skills/process/todoc-plan/SKILL.md`, `demo/skills/process/todoc-execute/SKILL.md`, `demo/skill/doc-flow-capture/SKILL.md`, `demo/skill/doc-spec-write/SKILL.md`
- Modify: `demo/.todoc/doc_types/*/prompts/{create,edit}.md` (`31` тип) и `demo/.todoc/entity_types/*/prompts/{create,edit}.md` (`25` типов): `12` стандартных перегенерируются из `build_prompts`; в `43` кастомных хирургически заменяется только блок `docs edit --patch-file` / `records create` при правке на прямую правку + `todoc sync --root KB <path>`, с полным сохранением секций `Правила`, `Типичные правки`, `Запрещено`; для `export` и `flow-doc` в `edit.md` явно прописывается запрет ручной правки автособираемой витрины и пересборка из записи-источника
- Modify: `demo/bugs/bug-012-history-revizii-mutiruyuschih-komand-zagryaznyayut-git-status.md` (`status: fixed`)
- Modify: `README.md`
- Test: `tests/unit/test_demo_prompts_policy.py`

**Интерфейсы:**
- Consumes: работающая команда `.venv/bin/todoc sync --root demo`, обновлённый `build_prompts`
- Produces: консистентные правила, скилы и промпты всех `56` типов без принудительного `docs edit --patch-file` и тест-инвариант `test_demo_prompts_policy.py`, защищающий от регрессии.

- [ ] **Шаг 1: написать падающий тест политики промптов и правил** в `tests/unit/test_demo_prompts_policy.py`

```python
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_all_56_demo_types_have_edit_prompt_without_mandatory_patch_file() -> None:
    type_dirs = sorted((REPO_ROOT / "demo" / ".todoc" / "doc_types").iterdir()) + sorted(
        (REPO_ROOT / "demo" / ".todoc" / "entity_types").iterdir()
    )
    type_dirs = [d for d in type_dirs if d.is_dir()]
    assert len(type_dirs) == 56

    offenders: list[str] = []
    for tdir in type_dirs:
        edit_md = tdir / "prompts" / "edit.md"
        assert edit_md.is_file(), f"Missing edit.md in {tdir}"
        text = edit_md.read_text(encoding="utf-8")
        if "--patch-file" in text:
            offenders.append(str(edit_md.relative_to(REPO_ROOT)))
        if tdir.name not in {"export", "flow-doc"}:
            assert "todoc sync" in text, f"{edit_md} must instruct running todoc sync"
    assert offenders == [], f"Prompts still mandating --patch-file: {offenders}"


def test_rules_contracts_and_skills_reference_todoc_sync_without_patch_file_mandate() -> None:
    for rel in (
        "AGENTS.md",
        "SKILL.md",
        "demo/skill/SKILL.md",
        "demo/notes/agent-contract.md",
        "demo/skills/docs/todoc-docs/SKILL.md",
        "demo/skills/process/todoc-capture/SKILL.md",
        "demo/skills/process/todoc-plan/SKILL.md",
        "demo/skills/process/todoc-execute/SKILL.md",
        "demo/skill/doc-flow-capture/SKILL.md",
        "demo/skill/doc-spec-write/SKILL.md",
    ):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "todoc sync" in text, f"{rel} must document todoc sync"
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `.venv/bin/pytest tests/unit/test_demo_prompts_policy.py -v`
Expected: FAIL (промпты и скилы ещё содержат `--patch-file` и не упоминают `todoc sync`).

- [ ] **Шаг 3: обновить правила, скилы, все `56` типов в `demo/.todoc/`, закрыть `BUG-012` и прогнать `todoc sync --root demo` на живом датасете**
  1. Обновить `AGENTS.md` (правила 1 и 4 + таблица команд), `SKILL.md`, `demo/skill/SKILL.md`, `demo/notes/agent-contract.md`, `demo/skills/docs/todoc-docs/SKILL.md`, `demo/skills/process/{todoc-capture,todoc-plan,todoc-execute}/SKILL.md` и `demo/skill/{doc-flow-capture,doc-spec-write}/SKILL.md`.
  2. Обновить `12` стандартных и `43` кастомных `prompts/{create,edit}.md` в `demo/.todoc/` (сохранив все доменные правила типов), а в `export/prompts/edit.md` и `flow-doc/prompts/edit.md` зафиксировать правку источника + пересборку витрины.
  3. Перевести `demo/bugs/bug-012-history-revizii-mutiruyuschih-komand-zagryaznyayut-git-status.md` в `status: fixed`.
  4. Вычислить точные счётчики команд и тестов для корневого `README.md` (`64 листовых (29 верхнего уровня, 10 групп)` + фактическое число тестов `pytest` и документов `demo/`):
     ```bash
     .venv/bin/python -c 'import click; from todoc.cli import cli; leaves = lambda g: sum(leaves(c) if isinstance(c, click.Group) else 1 for c in g.commands.values()); grps = sum(isinstance(c, click.Group) for c in cli.commands.values()); print(f"{leaves(cli)} листовых ({len(cli.commands)} верхнего уровня, {grps} групп)")'
     ```
  5. Выполнить живую dogfooding-проверку: `.venv/bin/todoc sync --root demo` и убедиться, что `git status --porcelain` не содержит `.todoc/history/`.

- [ ] **Шаг 4: прогнать полный end-to-end гейт репозитория**

Run: `.venv/bin/pytest -v --cov=todoc --cov-branch && .venv/bin/todoc check-config --root demo && .venv/bin/todoc validate --root demo --all && .venv/bin/todoc stale --root demo && .venv/bin/python tools/linkcheck.py`
Expected:
- `pytest`: все тесты зелёные, `100%` branch coverage на `src/todoc/application/sync.py` и всех изменённых модулях `src/todoc/`;
- `check-config` и `validate --all`: `"ok": true`, `"diagnostics": []`;
- `stale`: `"stale": 0`;
- `linkcheck.py`: `broken 0`.

- [ ] **Шаг 5: финальный коммит**

```bash
git add AGENTS.md SKILL.md README.md demo/ tests/unit/test_demo_prompts_policy.py
git commit -m "docs(rules,prompts): adopt direct file editing + todoc sync across rules, skills, and all 56 types"
```

## 6. Definition of Done

- [ ] Все 5 задач раздела 5 выполнены и отмечены `[x]`.
- [ ] Новый модуль `src/todoc/application/sync.py` и все затронутые файлы `src/todoc/` имеют **`100%` branch coverage** в `pytest --cov=todoc --cov-branch`.
- [ ] В `src/todoc/application/sync.py` нет импорта `click` и прямого ввода-вывода в консоль (соблюдён шов под модульный рефакторинг CLI).
- [ ] Прямая правка `.md` и `.json` в `demo/` с последующим `todoc sync --root demo <path>` проверена end-to-end: обновляет `updated:`, историю и индекс за один вызов, блокирует ручную правку автособираемых витрин с заполненным `guidance`, не блокирует планы с `derived_from` и оставляет `git status` чистым от `.todoc/history/`.
- [ ] `todoc check-config --root demo` (`0` диагностик), `todoc validate --root demo --all` (`0` диагностик), `todoc stale --root demo` (`0` устаревших), `tools/linkcheck.py` (`0` битых ссылок).
- [ ] Счётчики команд (`64` листовых), тестов и документов в корневом `README.md` сверены с фактическим выводом CLI.
- [ ] После явного подтверждения пользователя идея `doc:ideas/direct-edit-and-git-sync.md` и этот план `doc:plan/direct-edit-and-sync.md` переводятся в статус `done`.

## 7. Риски и митигации

| Риск | Вероятность × Влияние | Митигация | Владелец |
|---|---|---|---|
| Потеря предметных правил в `43` кастомных `prompts/edit.md` при массовой замене текста промптов | **С × В** | Не перезаписывать кастомные типы выводом `build_prompts`: заменять только секцию `## Как` / `## Как править` и примечание о дате `updated`, проверяя `git diff demo/.todoc/` и тест `test_demo_prompts_policy.py`. | Исполнитель Задачи 5 |
| Ложная блокировка авторских документов (`plan`), у которых во front matter указан `derived_from` для отслеживания свежести | **В × В** | Признак автособираемой витрины опирается на 3 точных маркера (`"generated": true` в `type.json`, `"generated": true` во front matter или метку `<!-- СГЕНЕРИРОВАНО:` в теле), что покрыто отдельным тестом на `plan` с `derived_from` в Задаче 2. | Исполнитель Задачи 2 |
| Ложный отказ `--if-hash`, когда агент передаёт хеш документа **до** своей прямой правки на диске | **С × С** | В `sync_files` сверять `expected_hash` как с текущим хешем файла, так и с последним заиндексированным хешем `prev_hash` из опубликованного снимка/истории, отклоняя запрос только если база реально разошлась до правки агента. | Исполнитель Задачи 2 |
| Рассинхрон существующих тестов конверта CLI из-за нового поля `"guidance"` в `Envelope` | **С × С** | Включать ключ `"guidance"` в `Envelope.to_dict()` по параметру `include_guidance=True` (активен в `todoc sync`, до глобального внедрения `P15` во все команды), сохраняя 100% обратную совместимость старых ассертов. | Исполнитель Задачи 2 |

## 8. Прогресс и отклонения

- `2026-11-27` — План создан на основе зафиксированной и согласованной спеки `doc:ideas/direct-edit-and-git-sync.md` (`status: planned`).
- `2026-11-27` — Проведён финальный предреализационный аудит плана против реального кода репозитория (`src/todoc/`, `tests/`, `demo/.todoc/`): устранены 7 скрытых ловушек (утечка `.todoc/history/refs.json` в `registry.py:_config_digest`, детекция рендеров `flow render --write` вне папки `flows/` по метке `<!-- СГЕНЕРИРОВАНО:`, точная сигнатура `@dataclass Envelope`, хелпер `_run` для `TodocError` в `CliRunner`, точные пути скилов в `demo/skill/` и отсутствие `export/prompts/edit.md` — все `56` типов учтены, полные коды всех тестов без текстовых сокращений, фактический счётчик `64` листовых команд CLI для `README.md`). План на `100%` готов к пошаговой реализации с Задачи 1.

