---
id: doc:plan/docs-move-implementation.md
title: "Транзакционный перенос документов todoc docs move: ссылки, записи, история и откат (план реализации)"
doc_type: plan
lang: ru
status: active
created: 2026-11-28
updated: 2026-11-28
covers: ["doc:ideas/docs-move.md"]
tags: [plan, move, rename, links, wikilinks, history, revert, cli]
related: ["[[docs-move]]", "[[entity-to-folder]]", "[[direct-edit-and-git-sync]]", "[[todocignore]]", "[[agent-contract]]", "[[constitution.md]]"]
---

# Транзакционный перенос документов `todoc docs move`: ссылки, записи, история и откат — план реализации

> **Исполнителю (агенту):** план самодостаточен — читай его, а не историю сессии.
> Работай по задачам сверху вниз; шаги отмечаются чекбоксами (`- [ ]`) в том же
> коммите, который делает шаг. Начинай всегда с первого неотмеченного.

**Цель:** реализовать CLI-команду `todoc docs move` (`mv`) для транзакционного переноса/переименования Markdown-документа с автоправкой исходящих и входящих ссылок, wikilinks, `related`, путевых полей JSON-записей, якорей `derived_from`, путевого `id`, `updated`, индекса и истории, с preview/apply, атомарным откатом и обратным откатом всей операции одной командой.
**Спека:** [Идея: `todoc docs move`](../ideas/docs-move.md) (`doc:ideas/docs-move.md`), [Конституция `todoc`](constitution.md) (`doc:constitution`), [Контракт CLI для агента](../notes/agent-contract.md) (`doc:agent-contract`), [Идея `todoc folderize`](../ideas/entity-to-folder.md) (`doc:ideas/entity-to-folder.md` — потребитель ядра).
**Стек:** Python 3.11+, `click`, `markdown-it-py`, `jsonschema`; новых runtime-зависимостей нет; `pytest` + `coverage` с `100%` branch coverage на новых и изменённых модулях `src/todoc/`.

## 1. Критерии успеха

1. `todoc docs move --root <KB> --from <path> --to <path>` без `--apply` возвращает `schema_version: 2`, `data.result.preview: true`, `plan_hash`, `rewrites`, `files[]`, `diagnostics[]`; на диске не меняется ни один байт, история и индекс не пишутся.
2. `todoc docs move ... --apply --if-plan-hash <hash>` переносит документ одной операцией: исходник удалён, цель создана, все входящие/исходящие inline-ссылки и изображения пересчитаны, code fences/indented code/inline code не тронуты, `#anchor`/title/alt сохранены; `validate --root <KB> --all` — 0 новых ошибок; `docs links` — 0 битых; `docs tree` видит документ по новому пути.
3. При переименовании обновлены wikilinks `[[stem]]`/`[[stem#anchor]]`/`[[stem|alias]]` и `related`; при коллизии stem план отклоняется кодом `move.wikilink_ambiguous` (exit 3), а не оставляет неоднозначный wikilink. Путевой `id: doc:<old>` заменяется на `doc:<new>` (кроме `--keep-id`), смысловой `id` не меняется; `updated` бампается у каждого изменённого `.md`.
4. Путевые поля записей обновлены: `source_path`, `source`, `sources[]`, `artifacts[]`, `baseline.artifacts` (ключ и значение), `derived_from` (строки и объекты; пересчёт хеша фрагмента для перемещённого документа). JSON-записи переписаны каноническим `json.dumps(indent=2, ensure_ascii=False) + "\n"`; файлы без изменений не переписываются.
5. Перенос пишет **одно** событие истории с несколькими `paths[]` и `change_id: move:<hash>`; `todoc revert --change <id> --apply` восстанавливает исходник, удаляет цель и возвращает все изменённые документы; инъекция `OSError` на середине коммита откатывает все байты, включая восстановление удалённого исходника.
6. `pytest` зелёный, coverage 100% на `src/todoc/application/move.py` и изменённых ветках; `todoc validate --root demo --all` — 0; `todoc check-config --root demo` — 0; `todoc docs links --root demo` — 0; полевое испытание на копии `demo/` проходит end-to-end; README/SKILL/agent-contract/HOME/CLI-reference обновлены.

## 2. Вне скоупа

- **Перенос папки** (`docs move --dir`) и пакетный `MovePlan` над поддеревом — вторая итерация; v1 переносит ровно один Markdown-документ.
- **`todoc records move`** и физический перенос JSON-записей — не делаем; записи только переписываются по путям.
- **Перенос CSV/JSON-документов** (не Markdown) — не делаем; команда отказывает `move.source_not_markdown`.
- **`.todocignore`** — идея не реализована; v1 проверяет только `HARD_EXCLUDE_DIRS` и containment. Код `move.target_ignored` не вводится.
- **Автоматическая замена папочного тега в `tags`** — в коде нет конвенции «папка → тег»; `tags` не меняются.
- **Перетипизация документа с явным `doc_type`** — не делаем. `--pin-type` только материализует тип, выведенный из правила старой папки, когда явного `doc_type` нет. `--adopt-target-type` не входит в v1.
- **Reference-style ссылки и autolinks** — не переписываются; план выдаёт warning `move.link_unsupported`, а валидатор блокирует применение, если такая ссылка сломалась.
- **`--with-assets`** — не делаем; локальные ассеты остаются на месте, относительные ссылки на них пересчитываются.
- **Case-only rename** (`foo.md` → `Foo.md`) — на case-insensitive ФС (Windows/WSL) отклоняется `move.case_only_rename`; отдельный temp-rename сценарий — позже.
- **Мульти-рут и междатасетный перенос** — не делаем; ровно один `--root`.
- **Рекурсивный ре-анкоринг второго уровня** — `derived_from` пересчитывается для зависимостей, указывающих на перемещённый документ; зависимости от изменённых входящих документов не каскадируются (честно видны в `todoc stale`).
- **Изменение `relations[].target.id`** — не делаем: рёбра ссылаются на `record_id`, а не на путь документа.
- **Автоматический коммит Git** — не делаем; коммит делает исполнитель/пользователь.

## 3. Глобальные ограничения

- **P1/P2 (конституция):** файлы — источник истины; индекс, кэш и история — производные и пересобираемые; никаких скрытых состояний.
- **P3/P10:** никаких фоновых процессов, сети, `eval`; каждое действие детерминировано и воспроизводимо.
- **P7:** дефолтный ответ ограничен: счётчики, пути, хеши; полный построчный diff — только по `--verbose`.
- **P15:** каждый ошибочный код имеет запись в `src/todoc/data/guidance/ru.json` (hint + ссылки на скил/документ).
- **Атомарность:** все новые содержимые собираются и валидируются до первой записи; при любой ошибке — полный откат, включая удаление созданной цели и восстановление исходника.
- **Review-first:** `--preview` — дефолт; `--apply` требует `--if-plan-hash` (защита от устаревшего preview) и принимает `--if-hash` (защита исходника). Оба хеша проверяются до записи.
- **Тонкий CLI:** `src/todoc/application/move.py` не импортирует `click`, не пишет в stdout/stderr и не знает о форматах вывода; CLI только собирает аргументы и рендерит конверт.
- **Конверт:** `schema_version: 2`, `ok`, `data.meta`, `data.result`, `diagnostics`, `next_actions`, `guidance`.
- **Коды выхода:** `0` успех; `1` операционная ошибка; `2` `EXIT_USAGE`; `3` `EXIT_VALIDATION`; `4` `EXIT_ACCESS`; `5` `EXIT_CONFLICT`; `6` `EXIT_INCOMPLETE`.
- **Containment:** источник и цель — внутри `DATA_ROOT`; symlink, `..`, абсолютный путь и сегменты `HARD_EXCLUDE_DIRS` (`scanner.py:12`) отклоняются.
- **Даты:** `created`/`updated` ставит только движок; `updated` бампается `bump_front_matter_updated` (`write.py:181`), руками не правится.
- **Именование:** русский `title` во front matter, файл — латиница/kebab-case; план создан как `plan/docs-move-implementation.md`.
- **История:** журнал append-only, `schema_version: 1`; событие move добавляет несколько `paths[]`, формат обратно совместим.
- **Гейты:** `validate --root demo --all` = 0, `check-config --root demo` = 0, `docs links --root demo` = 0, `pytest` + `coverage report --fail-under=100`.
- **Платформа:** Linux/WSL — основной маршрут; Windows-совместимость путей и запрещённых имён учитывается (`portable_name`, `write.py:33`).
- **Запуск:** запись `todoc …` в плане означает `env PYTHONPATH=src python3 -m todoc …` из `~/projects/todoc`; из харнесса — обёртка `wsl -d Ubuntu -- bash -lc "cd ~/projects/todoc && …"` (см. `AGENTS.md`).

## 4. Архитектура и файловая карта

**Подход.** Планировщик `plan_move` живёт в `src/todoc/application/move.py` и работает только с индексом и текстами: он разрешает источник, цель, читает все Markdown-документы, строит `MovePlan` (новые содержимые, удаления, счётчики, диагностики, `plan_hash`) и валидирует виртуальное состояние через overlay-параметры `validate_dataset`. Коммиттер `apply_move` предвычисляет все байты, пишет через `atomic_write`, удаляет исходник, пишет **одно** multi-path событие истории и пересобирает индекс; при ошибке откатывает все файлы. Обратный откат — `revert_event` по `change_id` (одна команда `todoc revert --change <id>`). Переписывание ссылок идёт по разбору `parse_markdown` и raw-span замене target, а не по `str.replace` всего файла; неподдержанные формы (reference/autolink) дают warning и блокируются валидатором, если ломаются.

**Решения открытых вопросов идеи (закрыты здесь):**

| Вопрос идеи | Решение в плане |
|---|---|
| Различение path-shaped и смыслового `id` | Только точное совпадение `id == f"doc:{old_path}"`; иначе `id` считается смысловым и не меняется. `--keep-id` оставляет даже path-shaped. |
| Коллизия wikilinks | Если новый stem уже занят другим файлом и на старый stem есть wikilink/`related` — ошибка `move.wikilink_ambiguous` (exit 3), запись не выполняется. Если ссылок нет — warning `move.wikilink_collision`. Путь-квалификация `[[dir/stem]]` не поддерживается текущим резолвером. |
| Обновлять ли `related` | Да, всегда при переименовании: это консистентность front matter, хотя валидатор существование целей не проверяет. |
| Путевые поля записей | Явный список `PATH_FIELDS`: `source_path`, `source`, `sources[]`, `artifacts[]`, `baseline.artifacts`; плюс `derived_from` (строки и объекты). Декларация path-полей в схемах типов — позже. |
| `.todocignore` | Вне v1; проверяется только `HARD_EXCLUDE_DIRS`. |
| Перетипизация | Только `--pin-type` для типа, выведенного из правила папки; явный `doc_type` не меняется. |
| Перенос папки | Вне v1. |
| Локальные ассеты | `--with-assets` нет; относительные ссылки на ассеты пересчитываются, файлы не двигаются. |
| `records move` | Вне v1. |
| Multi-path revert | `todoc revert --change <id>`; `--path` и `--change` взаимоисключающие, ровно один обязателен. |
| Case-only rename | Отказ `move.case_only_rename` в v1. |
| Reference-style/autolinks | Не переписываются; warning `move.link_unsupported`; если после move ссылка не резолвится — `markdown.link.target_missing` блокирует apply. |
| Предсуществующие диагностики | Блокируются только **новые** error-диагностики: baseline-ключи `(code, path)` переносятся с `old_path` на `new_path`; старые ошибки не мешают переносу. |

**Коды диагностики и ошибок:**

| Код | Severity / exit | Когда |
|---|---|---|
| `move.source_not_found` | error / 3 | `--id`/`--from` не найден в индексе |
| `move.source_ambiguous` | error / 3 | несколько документов с одним `document_id` |
| `move.source_not_markdown` | error / 3 | источник не `.md`/`.markdown` или `format != markdown` |
| `move.source_unreadable` | error / 3 | parse status не `ok` или файл не читается |
| `move.source_symlink` | error / 4 | источник — symlink |
| `move.target_exists` | error / 5 | цель уже существует (кроме case-only, который отклоняется раньше) |
| `move.target_outside_root` | error / 4 | цель вне `DATA_ROOT` |
| `move.target_symlink` | error / 4 | цель — symlink |
| `move.target_reserved` | error / 4 | сегмент цели в `HARD_EXCLUDE_DIRS` (`.todoc`, `.git`, …) |
| `move.target_dir_missing` | error / 3 | родительская папка цели не существует |
| `move.target_not_file` | error / 3 | у цели нет расширения `.md`/`.markdown` |
| `move.extension_mismatch` | error / 3 | расширение цели не совпадает с исходным |
| `move.same_path` | error / 2 | `--to` совпадает с исходником |
| `move.case_only_rename` | error / 3 | пути различаются только регистром |
| `move.plan_stale` | error / 5 | `--if-plan-hash` не совпал |
| `move.hash_mismatch` | error / 5 | `--if-hash` не совпал или исходник изменился между preview и apply |
| `move.wikilink_ambiguous` | error / 3 | новый stem занят, есть ссылки на старый stem |
| `move.wikilink_collision` | warning | новый stem занят, ссылок на старый stem нет |
| `move.pin_type_unavailable` | warning | `--pin-type`, но старый тип не определён (`unknown`) |
| `move.link_unsupported` | warning | reference-style/autolink не переписан |
| `move.validation_failed` | error / 3 | overlay-валидация дала новые error-диагностики |
| `move.history_failed` | error / 6 | запись истории не удалась, файлы откачены |
| `move.index_failed` | error / 6 | индекс не пересобрался после коммита |
| `move.revert_not_found` | error / 6 | `change_id` не найден в истории |
| `move.revert_unsupported` | error / 3 | событие содержит путь, который нельзя восстановить (нет снимка и не создание) |

**Карта файлов:**

| Файл | Действие | За что отвечает |
|---|---|---|
| `src/todoc/application/move.py` | Create | `MoveFile`, `MovePlan`, `plan_move`, `apply_move`, `rewrite_markdown_links`, `rewrite_related`, `rewrite_records`, `rewrite_derived_from`, `virtual_scan` |
| `src/todoc/application/validator.py` | Modify (`validate_dataset:538`, `_read_validation_text:160`, `_check_source_anchors:218`, `build_mentions:173`) | overlay/deleted: валидация виртуального состояния без записи на диск |
| `src/todoc/service.py` | Modify (`scan_and_validate:62`, `build_mentions:…`) | проброс `overlay`/`deleted` в валидатор и mentions |
| `src/todoc/application/history.py` | Modify (`record_write:79`) | `record_event` (multi-path), `record_write` как обёртка, `plan_revert_event`, `revert_event` |
| `src/todoc/cli.py` | Modify (`docs` группа:1666, `revert_cmd:1141`) | `docs move` + скрытый `mv`, `revert --change`, вывод конверта |
| `src/todoc/data/guidance/ru.json` | Modify | подсказки `move.*` |
| `src/todoc/application/paging.py` | Consume | `selection_key` для `plan_hash` (без изменений) |
| `demo/notes/agent-contract.md`, `SKILL.md`, `README.md`, `demo/HOME.md`, `demo/references/state/03-cli-reference.md` | Modify | команда, контракт, счётчики, ссылка на план |
| `demo/ideas/docs-move.md` | Modify | `status: planned`, ссылка на план |
| `tests/unit/test_move.py` | Create | планировщик, ссылки, id, записи, overlay, коллизии |
| `tests/unit/test_history_move.py` | Create | multi-path event, revert, rollback |
| `tests/cli/test_cli_docs_move.py` | Create | preview/apply, флаги, alias, guidance, revert |
| `tests/unit/test_validator.py` | Modify | overlay/deleted для Markdown/JSON/anchors/mentions |

## 5. Задачи

### Задача 1: каркас `move.py`, разрешение источника/цели, `plan_hash`

**Файлы:**
- Create: `src/todoc/application/move.py`
- Test: `tests/unit/test_move.py`

**Интерфейсы:**
- Consumes: `DatasetContext.read_index` (`service.py:192`), `normalize_scope` (`documents.py:23`), `selection_key` (`paging.py:12`), `HARD_EXCLUDE_DIRS` (`scanner.py:12`), `is_within_root` (`scanner.py:30`), `file_hash` (`scanner.py:22`).
- Produces:
  - `@dataclass(frozen=True) MoveFile(path: str, action: str, before_path: str | None, before_hash: str | None, content: str)`
  - `@dataclass(frozen=True) MovePlan(dataset_id: str, source: str, target: str, old_id: str, new_id: str, source_hash: str, target_hash: str, files: tuple[MoveFile, ...], deleted: tuple[str, ...], rewrites: dict[str, int], diagnostics: tuple[dict[str, Any], ...], plan_hash: str, options: dict[str, Any])`
  - `resolve_source(payload: dict[str, Any], source: str | None, doc_id: str | None) -> dict[str, Any]`
  - `resolve_target(root: Path, source_path: str, target: str) -> str`
  - `plan_move(ctx: DatasetContext, *, source: str | None, doc_id: str | None, target: str, keep_id: bool = False, pin_type: bool = False) -> MovePlan`

- [ ] **Шаг 1: написать падающие тесты разрешения и цели**

```python
# tests/unit/test_move.py
import json
from pathlib import Path
import pytest
from todoc.config import init_dataset
from todoc.errors import ConflictError, TodocError, ValidationError
from todoc.service import DatasetContext
from todoc.application.move import plan_move


def _kb(tmp_path: Path) -> Path:
    kb = tmp_path / "kb"
    kb.mkdir()
    init_dataset(kb)
    (kb / "inbox").mkdir()
    (kb / "notes").mkdir()
    (kb / "inbox" / "draft.md").write_text(
        "---\nid: doc:inbox/draft.md\ntitle: Draft\ndoc_type: note\n"
        "created: 2026-01-01\nupdated: 2026-01-01\n---\n\n# Draft\n\n## Суть\n\nТекст.\n",
        encoding="utf-8",
    )
    (kb / "notes" / "taken.md").write_text("# Taken\n", encoding="utf-8")
    ctx = DatasetContext(kb)
    ctx.rebuild_index(force=True)
    return kb


def test_plan_resolves_by_id_and_by_path(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    ctx = DatasetContext(kb)
    by_id = plan_move(ctx, source=None, doc_id="doc:inbox/draft.md",
                      target="notes/draft.md")
    by_path = plan_move(ctx, source="inbox/draft.md", doc_id=None,
                        target="notes/draft.md")
    assert by_id.source == by_path.source == "inbox/draft.md"
    assert by_id.target == "notes/draft.md"
    assert by_id.files[0].action == "create"
    assert by_id.files[0].path == "notes/draft.md"
    assert by_id.deleted == ("inbox/draft.md",)
    assert by_id.plan_hash == by_path.plan_hash


def test_plan_rejects_bad_targets(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    ctx = DatasetContext(kb)
    with pytest.raises(ConflictError, match="already exists"):
        plan_move(ctx, source="inbox/draft.md", doc_id=None, target="notes/taken.md")
    with pytest.raises(ValidationError, match="parent directory"):
        plan_move(ctx, source="inbox/draft.md", doc_id=None, target="missing/draft.md")
    with pytest.raises(ValidationError, match="same path"):
        plan_move(ctx, source="inbox/draft.md", doc_id=None, target="inbox/draft.md")
    with pytest.raises(ValidationError, match="extension"):
        plan_move(ctx, source="inbox/draft.md", doc_id=None, target="notes/draft.txt")
    with pytest.raises(TodocError, match="outside DATA_ROOT"):
        plan_move(ctx, source="inbox/draft.md", doc_id=None, target="../draft.md")
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `pytest tests/unit/test_move.py -v`
Expected: FAIL с `ModuleNotFoundError: todoc.application.move`

- [ ] **Шаг 3: реализовать разрешение и проверки в `move.py`**

Алгоритм:
1. `resolve_source`: ровно один из `source`/`doc_id`; `source` нормализуется `normalize_scope`; документ ищется в `payload["documents"]` по `path` или `document_id`; при 0 — `move.source_not_found`, при >1 — `move.source_ambiguous`; `format == "markdown"` и `status == "ok"` обязательны; symlink — `move.source_symlink`.
2. `resolve_target`: не использовать `normalize_scope` (он отвергает `..` кодом `docs.invalid_scope`); вычислить `(root / target).resolve()`, проверить `is_within_root` (`move.target_outside_root`, `AccessError`), абсолютный путь — тоже `move.target_outside_root`. Если путь существует и это папка — `target = folder / Path(source).name`; если raw target оканчивается `/`, но папки нет — `move.target_dir_missing`. Иначе точный путь. Родитель цели обязан существовать (`move.target_dir_missing`). Цель не должна существовать (`move.target_exists`), не должна быть symlink (`move.target_symlink`), не должна содержать `HARD_EXCLUDE_DIRS` (`move.target_reserved`), расширение обязано совпадать (`move.extension_mismatch`); `source == target` — `move.same_path`; `source.lower() == target.lower()` — `move.case_only_rename`.
3. `plan_move` собирает `MoveFile(path=target, action="create", before_path=None, before_hash=None, content=<новый текст>)`, `deleted=(source,)`, `source_hash=file_hash(root / source)`, `target_hash=sha256(new_content)`; пока без переписывания ссылок; `plan_hash = selection_key([ctx.dataset_id, plan.to_dict()])`, где `to_dict()` содержит `source_hash`/`target_hash` и `files[]` с `path`/`action`/`before_hash`/`new_hash` (без полного содержимого).

- [ ] **Шаг 4: убедиться, что тесты проходят**

Run: `pytest tests/unit/test_move.py -v`
Expected: PASS

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/move.py tests/unit/test_move.py
git commit -m "feat(move): каркас планировщика docs move и проверки путей"
```

### Задача 2: переписывание Markdown-ссылок, wikilinks и `related`

**Файлы:**
- Modify: `src/todoc/application/move.py`
- Test: `tests/unit/test_move.py`

**Интерфейсы:**
- Consumes: `parse_markdown` (`markdown.py:286`), `resolve_link_target` (`markdown.py:341`), `Link` (`markdown.py:36`), `PurePosixPath`, `posixpath.relpath`.
- Produces:
  - `rewrite_markdown_links(text: str, *, doc_path: str, new_doc_path: str, old_target: str, new_target: str, renamed: bool) -> tuple[str, dict[str, int], list[dict[str, Any]]]`
  - `rewrite_related(front_matter: dict[str, Any], *, old_stem: str, new_stem: str, renamed: bool) -> tuple[dict[str, Any], int]`
  - `_replace_inline_link_target(raw_line: str, link: Link, replacement: str) -> str | None`
  - `_replace_wikilink_stem(raw: str, old_stem: str, new_stem: str) -> str | None`
  - `_set_front_matter_list(text: str, key: str, values: list[Any]) -> str` — точечная замена строки `key:` через `json.dumps(values, ensure_ascii=False)`, остальной front matter не переписывается.

Алгоритм:
- Для каждого документа: `doc = parse_markdown(text)`; ссылки обрабатываются в порядке убывания `(line, column)`, чтобы не сдвигать колонки.
- Inline-ссылка/изображение: взять raw-line span `[column-1:end_column-1]`; проверить `_INLINE_LINK_RE` (копия из `markdown.py:20`), заменить только group 2 (target), сохранив title/alt. Если span не матчится — `move.link_unsupported` warning.
- `resolved = resolve_link_target(doc_path, link.target)`.
  - Для самого переносимого документа (`doc_path == old_target`): если `resolved` не None и не external — новая цель `posixpath.relpath(resolved, parent(new_doc_path))`; если `resolved == old_target` — `posixpath.relpath(new_target, parent(new_doc_path))`.
  - Для входящих документов: только если `resolved == old_target` — `posixpath.relpath(new_target, parent(doc_path))`.
  - `#fragment` и title сохраняются.
- Wikilink: если `renamed` и `link.target == old_stem` — заменить stem в raw-span, сохранив `#anchor` и `|alias`. Если `new_stem` занят другим путём: при наличии ссылок — error `move.wikilink_ambiguous`; иначе warning `move.wikilink_collision`.
- `related`: для каждого `[[stem]]`/`[[stem#anchor]]`/`[[stem|alias]]` заменить stem при `renamed`; `[[doc:…]]` не трогать. Запись — `_set_front_matter_list` (не `rewrite_markdown_attributes`: он переписывает все изменённые поля и меняет кавычки).
- `updated` бампается после переписывания через `bump_front_matter_updated` (точечная замена строки `updated:`).

- [ ] **Шаг 1: падающие тесты переписывания**

```python
def test_rewrite_self_and_inbound_links_preserves_code_and_fragments(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    moved = kb / "inbox" / "draft.md"
    moved.write_text(
        "---\nid: doc:inbox/draft.md\ntitle: Draft\ndoc_type: note\n"
        "created: 2026-01-01\nupdated: 2026-01-01\n---\n\n# Draft\n\n"
        "[runbook](../ops/runbook.md#steps), [sibling](./sibling.md) and ![img](../assets/a.png)\n\n"
        "```md\n[runbook](../ops/runbook.md)\n```\n\n"
        "`[runbook](../ops/runbook.md)`\n",
        encoding="utf-8",
    )
    (kb / "inbox" / "sibling.md").write_text("# Sibling\n", encoding="utf-8")
    (kb / "ops").mkdir()
    (kb / "ops" / "runbook.md").write_text("# Runbook\n\n## Steps\n", encoding="utf-8")
    (kb / "assets").mkdir()
    (kb / "assets" / "a.png").write_bytes(b"png")
    (kb / "notes" / "index.md").write_text(
        "---\nid: doc:notes/index.md\ntitle: Index\ndoc_type: note\n"
        "created: 2026-01-01\nupdated: 2026-01-01\n---\n\n"
        "# Index\n\n[черновик](../inbox/draft.md#суть) и [[draft|черновик]]\n",
        encoding="utf-8",
    )
    ctx = DatasetContext(kb)
    ctx.rebuild_index(force=True)
    plan = plan_move(ctx, source="inbox/draft.md", doc_id=None, target="notes/draft.md")
    contents = {f.path: f.content for f in plan.files}
    new_draft = contents["notes/draft.md"]
    assert "[runbook](../ops/runbook.md#steps)" in new_draft
    assert "[sibling](../inbox/sibling.md)" in new_draft
    assert "![img](../assets/a.png)" in new_draft
    assert "```md\n[runbook](../ops/runbook.md)\n```" in new_draft
    assert "`[runbook](../ops/runbook.md)`" in new_draft
    assert "[черновик](draft.md#суть)" in contents["notes/index.md"]
    assert "[[draft|черновик]]" in contents["notes/index.md"]  # имя не менялось
```

```python
def test_rename_updates_wikilinks_and_related_and_blocks_collision(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    (kb / "ideas").mkdir()
    (kb / "ideas" / "old.md").write_text(
        "---\nid: doc:ideas/old.md\ntitle: Old\ndoc_type: note\n"
        "created: 2026-01-01\nupdated: 2026-01-01\n---\n\n# Old\n\n## Суть\n\nТекст.\n",
        encoding="utf-8",
    )
    (kb / "notes" / "hub.md").write_text(
        "---\nid: doc:notes/hub.md\ntitle: Hub\ndoc_type: note\n"
        "related: [\"[[old]]\"]\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n\n"
        "# Hub\n\n[[old#Суть|старое]]\n",
        encoding="utf-8",
    )
    ctx = DatasetContext(kb)
    ctx.rebuild_index(force=True)
    plan = plan_move(ctx, source="ideas/old.md", doc_id=None, target="ideas/new.md")
    contents = {f.path: f.content for f in plan.files}
    assert "[[new#Суть|старое]]" in contents["notes/hub.md"]
    assert 'related: ["[[new]]"]' in contents["notes/hub.md"]
    assert contents["ideas/new.md"].count("id: doc:ideas/new.md") == 1

    (kb / "ideas" / "new.md").write_text("# Occupied\n", encoding="utf-8")
    ctx = DatasetContext(kb)
    ctx.rebuild_index(force=True)
    with pytest.raises(ValidationError, match="wikilink"):
        plan_move(ctx, source="ideas/old.md", doc_id=None, target="ideas/new2.md")
```

- [ ] **Шаг 2: убедиться, что тесты падают** (`ImportError: rewrite_markdown_links`)
- [ ] **Шаг 3: реализовать переписывание** (алгоритм выше; raw-span, обратный порядок, сохранение title/fragment/alias).
- [ ] **Шаг 4: тесты проходят**

Run: `pytest tests/unit/test_move.py -v`
Expected: PASS

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/move.py tests/unit/test_move.py
git commit -m "feat(move): переписывание ссылок, wikilinks и related по разбору"
```

### Задача 3: идентичность, записи, `derived_from`, `updated`

**Файлы:**
- Modify: `src/todoc/application/move.py`
- Test: `tests/unit/test_move.py`

**Интерфейсы:**
- Consumes: `bump_front_matter_updated` (`write.py:181`), `parse_anchor`/`format_anchor` (`staleness.py:100`, `:125`), `fragment_hash` (`staleness.py:64`), `parse_json` (`jsonfmt.py`), `json.dumps`.
- Produces:
  - `rewrite_records(records: list[dict[str, Any]], *, old_path: str, new_path: str, old_id: str, new_id: str) -> tuple[dict[str, str], int]` — путь записи → новое содержимое; счётчик изменённых записей.
  - `rewrite_derived_from(text: str, *, old_path: str, new_path: str, new_target_text: str) -> tuple[str, int]` — обновляет `derived_from` в front matter и пересчитывает хеш фрагмента из нового текста цели.
  - `rewrite_identity(text: str, *, old_path: str, new_path: str, keep_id: bool) -> tuple[str, str, str]` — возвращает `(new_text, old_id, new_id)`.
  - `_set_front_matter_scalar(text: str, key: str, value: str) -> str` — точечная замена `key: …` с сохранением кавычек, если значение было в кавычках.
  - `_insert_front_matter_scalar(text: str, key: str, value: str) -> str` — вставка `key: value` перед `lang:` (или перед закрывающим `---`), если ключа нет.
  - `PATH_FIELDS = ("source_path", "source", "sources", "artifacts")`

Алгоритм:
- `id`: если `front_matter["id"] == f"doc:{old_path}"` и не `keep_id` — заменить на `doc:{new_path}` через `_set_front_matter_scalar`. Если `id` нет — `old_id = f"doc:{old_path}"`, `new_id = f"doc:{new_path}"`, front matter не трогается. Смысловой `id` не меняется.
- `--pin-type`: если `doc_type` во front matter отсутствует и старый resolved-тип не `unknown` — вставить `doc_type: <old_type>` через `_insert_front_matter_scalar`; если тип `unknown` — warning `move.pin_type_unavailable`, документ не меняется.
- `updated`: для каждого изменённого Markdown — `bump_front_matter_updated(text)`; если поле отсутствует — не добавлять (как `docs status`).
- Записи: для каждой `record` из `payload["records"]` (поле `data` — распарсенный JSON) обойти `PATH_FIELDS`:
  - строка == `old_path` → `new_path`;
  - список строк → заменить элементы;
  - `baseline.artifacts` — словарь: если ключ `old_path`, переименовать ключ (значение хеша не меняется);
  - `derived_from` — строки через `parse_anchor`/`format_anchor`, объекты через `path`; хеш пересчитать только если `dep["path"] == old_path`: `fragment_hash` по новому тексту цели (для whole-file — хеш нового файла; для section/pointer — хеш фрагмента нового текста); `stale_ack_hashes` у владельца: если содержит старый хеш — заменить на новый (механический ре-анкор).
- JSON-запись переписывается только если `data` изменился: `json.dumps(data, indent=2, ensure_ascii=False) + "\n"`.

- [ ] **Шаг 1: падающие тесты**

```python
def test_path_shaped_id_and_records_are_rewritten(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    for type_id, fields in {
        "document": ["record_id", "entity_type", "title", "source_path"],
        "decision": ["record_id", "entity_type", "title"],
    }.items():
        d = kb / ".todoc" / "entity_types" / type_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "type.json").write_text(json.dumps({
            "schema_version": 1, "type_id": type_id, "version": "1.0",
            "kind": "entity_type", "description": type_id,
            "format": "json", "required_fields": fields,
        }, indent=2) + "\n", encoding="utf-8")
    (kb / "records" / "documents").mkdir(parents=True)
    (kb / "records" / "documents" / "draft.json").write_text(json.dumps({
        "schema_version": 1, "record_id": "document:draft", "entity_type": "document",
        "title": "Draft", "source_path": "inbox/draft.md", "doc_type": "note",
        "tags": ["note"],
    }, indent=2) + "\n", encoding="utf-8")
    (kb / "records" / "decisions").mkdir(parents=True)
    (kb / "records" / "decisions" / "d1.json").write_text(json.dumps({
        "schema_version": 1, "record_id": "decision:d1", "entity_type": "decision",
        "title": "D1", "status": "accepted", "decision": "x", "rationale": "y",
        "sources": ["inbox/draft.md"],
    }, indent=2) + "\n", encoding="utf-8")
    ctx = DatasetContext(kb)
    ctx.rebuild_index(force=True)
    plan = plan_move(ctx, source="inbox/draft.md", doc_id=None, target="notes/draft.md")
    contents = {f.path: f.content for f in plan.files}
    assert contents["notes/draft.md"].count("id: doc:notes/draft.md") == 1
    mirror = json.loads(contents["records/documents/draft.json"])
    assert mirror["source_path"] == "notes/draft.md"
    decision = json.loads(contents["records/decisions/d1.json"])
    assert decision["sources"] == ["notes/draft.md"]
    assert plan.rewrites["records"] == 2


def test_semantic_id_and_keep_id_are_stable(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    path = kb / "inbox" / "draft.md"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "id: doc:inbox/draft.md", "id: doc:draft-semantic"), encoding="utf-8")
    ctx = DatasetContext(kb)
    ctx.rebuild_index(force=True)
    plan = plan_move(ctx, source="inbox/draft.md", doc_id=None, target="notes/draft.md")
    assert "id: doc:draft-semantic" in plan.files[0].content
    assert plan.new_id == "doc:draft-semantic"

    plan_keep = plan_move(ctx, source="inbox/draft.md", doc_id=None,
                          target="notes/draft.md", keep_id=True)
    assert "id: doc:draft-semantic" in plan_keep.files[0].content
```

- [ ] **Шаг 2: тесты падают**
- [ ] **Шаг 3: реализовать** `rewrite_identity`, `rewrite_records`, `rewrite_derived_from`, бамп `updated`.
- [ ] **Шаг 4: тесты проходят**

Run: `pytest tests/unit/test_move.py -v`
Expected: PASS

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/move.py tests/unit/test_move.py
git commit -m "feat(move): id, записи, derived_from и updated при переносе"
```

### Задача 4: overlay-валидация виртуального состояния

**Файлы:**
- Modify: `src/todoc/application/validator.py` (`validate_dataset:538`, `_read_validation_text:160`, `_check_source_anchors:218`, `build_mentions:173`)
- Modify: `src/todoc/service.py` (`scan_and_validate:62`, `build_mentions:…`)
- Modify: `src/todoc/application/move.py`
- Test: `tests/unit/test_move.py`, `tests/unit/test_validator.py`

**Интерфейсы:**
- `validate_dataset(..., overlay: dict[str, str] | None = None, deleted: set[str] | None = None)`
- `_read_validation_text(root, scanned, verify, overlay=None) -> str | None`
- `_check_source_anchors(..., overlay=None)`
- `build_mentions(..., overlay=None, deleted=None)`
- `DatasetContext.scan_and_validate(..., overlay=None, deleted=None)`
- `virtual_scan(ctx: DatasetContext, plan: MovePlan) -> tuple[list[Any], list[ScannedFile]]`

Алгоритм:
- В `validate_dataset` пропускать `scanned.rel_path in deleted`; для overlay-пути брать текст из `overlay` и не писать parse-cache; для Markdown парсить `overlay`-текст; для JSON/CSV — из overlay.
- `_check_source_anchors` читает витрину `source_path` из overlay, если она там есть.
- `build_mentions` пропускает deleted и парсит overlay-текст; `all_paths` — виртуальный набор.
- `virtual_scan` заменяет хеши/размеры изменённых файлов и добавляет новые пути; формат — по `FORMAT_BY_SUFFIX`.
- `plan_move` вызывает `ctx.scan_and_validate(scanned=virtual_scan(...), overlay=..., deleted=..., write_cache=False, verify_sources=True)`, сравнивает `(code, path)` с baseline (с маппингом `old_path → new_path`) и при новых error-диагностиках возвращает `move.validation_failed`.

- [ ] **Шаг 1: падающие тесты overlay**

```python
def test_overlay_validation_blocks_new_error_and_allows_preexisting(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    # Правило теста: ideas/*.md получает doc_type idea; документ без doc_type
    # получит тип idea и ошибку отсутствующих секций.
    (kb / "ideas").mkdir()
    (kb / ".todoc" / "doc_types" / "idea").mkdir(parents=True)
    (kb / ".todoc" / "doc_types" / "idea" / "type.json").write_text(json.dumps({
        "schema_version": 1, "type_id": "idea", "version": "0.1", "kind": "doc_type",
        "description": "idea", "format": "markdown",
        "required_sections": ["Суть", "Проблема", "Предложение"],
    }, indent=2) + "\n", encoding="utf-8")
    (kb / ".todoc" / "rules" / "document-rules.json").write_text(json.dumps({
        "schema_version": 1, "rules": [{
            "id": "ideas", "match": {"kind": "file", "glob": "**/ideas/*.md"},
            "assign": {"doc_type": "idea"}, "priority": 100,
        }],
    }, indent=2) + "\n", encoding="utf-8")
    (kb / "inbox" / "bare.md").write_text(
        "---\nid: doc:inbox/bare.md\ntitle: Bare\n"
        "created: 2026-01-01\nupdated: 2026-01-01\n---\n\n# Bare\n\n## Суть\n\nТекст.\n",
        encoding="utf-8",
    )
    ctx = DatasetContext(kb)
    ctx.rebuild_index(force=True)
    plan = plan_move(ctx, source="inbox/bare.md", doc_id=None, target="ideas/bare.md")
    assert any(d["code"] == "markdown.section.missing" for d in plan.diagnostics)
    assert any(d["severity"] == "error" for d in plan.diagnostics)
```

```python
def test_overlay_deleted_source_is_not_validated(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    ctx = DatasetContext(kb)
    plan = plan_move(ctx, source="inbox/draft.md", doc_id=None, target="notes/draft.md")
    assert not any(d["path"] == "inbox/draft.md" for d in plan.diagnostics)
```

- [ ] **Шаг 2: тесты падают** (`TypeError: validate_dataset() got an unexpected keyword argument 'overlay'`)
- [ ] **Шаг 3: реализовать overlay/deleted** в валидаторе и сервисе; в `plan_move` — `virtual_scan` и сравнение с baseline.
- [ ] **Шаг 4: тесты проходят**

Run: `pytest tests/unit/test_move.py tests/unit/test_validator.py -v`
Expected: PASS

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/validator.py src/todoc/service.py src/todoc/application/move.py tests/unit/test_move.py tests/unit/test_validator.py
git commit -m "feat(move): overlay-валидация виртуального состояния"
```

### Задача 5: multi-path событие истории

**Файлы:**
- Modify: `src/todoc/application/history.py` (`record_write:79`)
- Test: `tests/unit/test_history_move.py`

**Интерфейсы:**
- `record_event(root: Path, entries: list[dict[str, Any]], *, kind: str, actor: str = "cli", basis: str = "", change_id: str | None = None, backend: Any | None = None, git_head: str | None = None, extra: dict[str, Any] | None = None, store: HistoryStore | None = None) -> str | None`
- `entries` item: `{"path": str, "before": bytes | None, "after": bytes}`.
- `record_write(...)` сохраняет прежнюю сигнатуру и делегирует `record_event` с одним элементом.

Алгоритм:
- Один `storage.transaction()`; один `head`; для каждого entry — snapshot `before` (если не None) через `backend.needs_snapshot`, `after` — `_content_hash`, `ranges` — `changed_ranges` или `[]`; `paths[]` — все элементы; один `append_event`.
- `before=None` — создание: `ranges=[]`, как сейчас.

- [ ] **Шаг 1: падающий тест**

```python
from todoc.application.history import record_event, log
from todoc.adapters.history.store import FileHistoryStore

def test_record_event_writes_one_event_with_multiple_paths(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    store = FileHistoryStore(kb)
    rev = record_event(kb, [
        {"path": "inbox/draft.md", "before": b"old", "after": b""},
        {"path": "notes/draft.md", "before": None, "after": b"new"},
        {"path": "notes/index.md", "before": b"index-old", "after": b"index-new"},
    ], kind="doc.move", change_id="move:abc123", basis="test move", store=store)
    assert rev
    events, total, _ = log(kb, change_id="move:abc123")
    assert total == 1
    assert [p["path"] for p in events[0]["paths"]] == [
        "inbox/draft.md", "notes/draft.md", "notes/index.md"]
    assert events[0]["kind"] == "doc.move"
```

- [ ] **Шаг 2: тест падает** (`ImportError: record_event`)
- [ ] **Шаг 3: реализовать `record_event`, переписать `record_write` как обёртку**
- [ ] **Шаг 4: тесты проходят; существующие тесты истории зелёные**

Run: `pytest tests/unit/test_history.py tests/unit/test_history_move.py -v`
Expected: PASS

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/history.py tests/unit/test_history_move.py
git commit -m "feat(history): multi-path событие для атомарных операций"
```

### Задача 6: атомарный `apply_move` с откатом

**Файлы:**
- Modify: `src/todoc/application/move.py`
- Test: `tests/unit/test_move.py`, `tests/unit/test_history_move.py`

**Интерфейсы:**
- Consumes: `atomic_write` (`scanner.py:53`), `file_hash` (`scanner.py:22`), `os.unlink`, `record_event` (Задача 5), `ctx.ensure_index` (`service.py:276`), `ctx.parse_cache.invalidate`.
- Produces: `apply_move(ctx: DatasetContext, plan: MovePlan, *, if_plan_hash: str | None = None, if_hash: str | None = None) -> dict[str, Any]`.
- Возврат: `{"applied": True, "change_id": str, "rev": str, "moved": {...}, "rewrites": {...}, "index": {...}, "files": [...]}`.

Алгоритм:
1. Проверить `if_plan_hash is not None` и `plan.plan_hash == if_plan_hash` (`move.plan_stale`; без `--if-plan-hash` — `usage.error`), исходник существует и `file_hash(source) == plan.source_hash` (если `if_hash` задан — ещё и `if_hash`), цель не существует, и для каждого `MoveFile` с `before_hash` — `file_hash(path) == before_hash` (иначе `move.hash_mismatch`).
2. Снять оригиналы всех затрагиваемых путей (`bytes | None`).
3. Записать все `action in ("create", "update")` через `atomic_write`; удалить `plan.deleted` через `os.unlink` после успешной записи цели.
4. Записать одно событие `record_event(..., kind="doc.move", change_id=change_id)`; `change_id = "move:" + sha256(plan.plan_hash)[:8]`.
5. `ctx.parse_cache.invalidate` для всех путей (source, target, изменённые документы и записи), затем `ctx.ensure_index()`.
6. При любом `OSError`/`TodocError` — восстановить все оригиналы (включая удалённый исходник) и удалить созданные файлы; если откат не удался — `move.rollback_failed` (exit 6).
7. При сбое истории — откатить файлы; `move.history_failed`; при сбое индекса — `move.index_failed` (файлы и история уже записаны, честно сообщить).

- [ ] **Шаг 1: падающие тесты apply/rollback**

```python
def test_apply_move_writes_target_deletes_source_and_one_history_event(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    ctx = DatasetContext(kb)
    plan = plan_move(ctx, source="inbox/draft.md", doc_id=None, target="notes/draft.md")
    result = apply_move(ctx, plan, if_plan_hash=plan.plan_hash)
    assert result["applied"] is True
    assert not (kb / "inbox" / "draft.md").exists()
    assert (kb / "notes" / "draft.md").is_file()
    events, total, _ = log(kb, change_id=result["change_id"])
    assert total == 1
    assert events[0]["kind"] == "doc.move"


def test_apply_move_rolls_back_all_bytes_on_mid_commit_error(tmp_path: Path, monkeypatch) -> None:
    import todoc.application.move
    kb = _kb(tmp_path)
    (kb / "notes" / "index.md").write_text(
        "---\nid: doc:notes/index.md\ntitle: Index\ndoc_type: note\n"
        "created: 2026-01-01\nupdated: 2026-01-01\n---\n\n# Index\n\n## Суть\n\n"
        "[черновик](../inbox/draft.md)\n",
        encoding="utf-8",
    )
    ctx = DatasetContext(kb)
    ctx.rebuild_index(force=True)
    plan = plan_move(ctx, source="inbox/draft.md", doc_id=None, target="notes/draft.md")
    assert len(plan.files) == 2  # target + inbound notes/index.md
    originals = {p: (kb / p).read_bytes() for p in ["inbox/draft.md", "notes/index.md"]}
    real_write = todoc.application.move.atomic_write
    calls = {"n": 0}

    def flaky(path, content, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("disk full")
        return real_write(path, content, **kwargs)

    monkeypatch.setattr(todoc.application.move, "atomic_write", flaky)
    with pytest.raises(TodocError):
        apply_move(ctx, plan, if_plan_hash=plan.plan_hash)
    for path, data in originals.items():
        assert (kb / path).read_bytes() == data
    assert not (kb / "notes" / "draft.md").exists()
```

- [ ] **Шаг 2: тесты падают**
- [ ] **Шаг 3: реализовать `apply_move`** (предвычисление, запись, удаление, история, индекс, откат).
- [ ] **Шаг 4: тесты проходят**

Run: `pytest tests/unit/test_move.py tests/unit/test_history_move.py -v`
Expected: PASS

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/move.py tests/unit/test_move.py tests/unit/test_history_move.py
git commit -m "feat(move): атомарный apply с multi-path историей и откатом"
```

### Задача 7: обратный откат `todoc revert --change`

**Файлы:**
- Modify: `src/todoc/application/history.py`
- Modify: `src/todoc/cli.py` (`revert_cmd:1141`)
- Test: `tests/unit/test_history_move.py`, `tests/cli/test_cli_docs_move.py`

**Интерфейсы:**
- `plan_revert_event(root: Path, change_id: str, *, store: HistoryStore | None = None, backend: Any | None = None) -> dict[str, Any]`
- `revert_event(root: Path, change_id: str, *, apply: bool = False, history: Any = None, store: HistoryStore | None = None, parse_cache: ParseCache | None = None) -> dict[str, Any]`
- CLI: `todoc revert [REV] [--path P | --change ID] [--preview|--apply]`; `REV` обязателен для `--path` и запрещён для `--change`; ровно один из `--path`/`--change`; `--change` вызывает `revert_event`. Существующий вызов `revert <rev> --path P` сохраняется без изменений.

Алгоритм:
- Найти все события с `change_id` (в порядке журнала). Для каждого события в обратном порядке, для каждого `paths[]`:
  - `before` — snapshot digest: восстановить байты;
  - `before is None` — файл был создан: удалить.
- Preview: список `{path, action: restore|delete, current_hash, target_hash}`.
- Apply: снять оригиналы, выполнить действия, записать одно событие `kind: "move.revert"` с `change_id: None`, `basis: revert <id>`; при ошибке — откат; `ensure_index`.
- Если `change_id` не найден — `move.revert_not_found` (exit 6). Если для restore нет snapshot — `move.revert_unsupported` (exit 3).

- [ ] **Шаг 1: падающие тесты revert**

```python
def test_revert_change_restores_source_and_removes_target(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    ctx = DatasetContext(kb)
    plan = plan_move(ctx, source="inbox/draft.md", doc_id=None, target="notes/draft.md")
    result = apply_move(ctx, plan, if_plan_hash=plan.plan_hash)
    preview = revert_event(kb, result["change_id"], apply=False, store=ctx.history_store)
    assert {a["action"] for a in preview["actions"]} == {"restore", "delete"}
    revert_event(kb, result["change_id"], apply=True, history=ctx.history_recorder(),
                 store=ctx.history_store, parse_cache=ctx.parse_cache)
    assert (kb / "inbox" / "draft.md").is_file()
    assert not (kb / "notes" / "draft.md").exists()
```

- [ ] **Шаг 2: тесты падают**
- [ ] **Шаг 3: реализовать `plan_revert_event`/`revert_event` и CLI-ветку `--change`**
- [ ] **Шаг 4: тесты проходят**

Run: `pytest tests/unit/test_history_move.py tests/cli/test_cli_docs_move.py -v`
Expected: PASS

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/application/history.py src/todoc/cli.py tests/unit/test_history_move.py tests/cli/test_cli_docs_move.py
git commit -m "feat(revert): откат multi-path move по change_id"
```

### Задача 8: CLI `docs move` / `mv` и guidance

**Файлы:**
- Modify: `src/todoc/cli.py` (группа `docs:1666`)
- Modify: `src/todoc/data/guidance/ru.json`
- Test: `tests/cli/test_cli_docs_move.py`

**Интерфейсы:**
- `docs move --root R (--id ID | --from PATH) --to TARGET [--preview|--apply] [--if-plan-hash H] [--if-hash H] [--keep-id] [--pin-type] [--verbose] [--output json|table|markdown]`
- Скрытая команда `mv` с теми же параметрами (делегирует `docs_move`).
- `next_actions`: `docs read --id <new_id>`, `validate --all`, `revert --change <id>`.

Вывод:
- Preview: `data.result = {preview: true, applied: false, plan_hash, from, to, old_id, new_id, rewrites, files, diagnostics: len, new_errors: len, diff?: str}`.
- Apply: `data.result += {applied: true, change_id, rev, index: {generation_id, diagnostics, new_diagnostics}}`.
- `--verbose` добавляет `diff` (unified diff по всем изменённым файлам).
- Если `plan.diagnostics` содержит error — конверт `ok: false`, `diagnostics`, `guidance`, exit 3; `--apply` не выполняется.
- Ошибки — конверт `ok: false`, `diagnostics`, `guidance`; `next_actions` содержат исправленный argv, если он известен.

- [ ] **Шаг 1: падающие CLI-тесты**

```python
def test_cli_docs_move_preview_apply_and_revert(tmp_path: Path) -> None:
    runner = CliRunner()
    kb = tmp_path / "kb"
    assert _run(runner, ["init", "--apply", "--root", str(kb)]).exit_code == 0
    assert _run(runner, ["docs", "new", "--apply", "--root", str(kb), "--type", "note",
                         "--title", "Draft", "--path", "inbox/draft.md"]).exit_code == 0
    (kb / "notes").mkdir()

    preview = _run(runner, ["docs", "move", "--root", str(kb),
                            "--from", "inbox/draft.md", "--to", "notes/draft.md"])
    assert preview.exit_code == 0
    body = json.loads(preview.output)
    assert body["data"]["result"]["preview"] is True
    plan_hash = body["data"]["result"]["plan_hash"]
    assert (kb / "inbox" / "draft.md").is_file()

    applied = _run(runner, ["docs", "move", "--root", str(kb), "--from", "inbox/draft.md",
                            "--to", "notes/draft.md", "--apply", "--if-plan-hash", plan_hash])
    assert applied.exit_code == 0, applied.output
    result = json.loads(applied.output)["data"]["result"]
    assert result["applied"] is True and result["change_id"].startswith("move:")
    assert not (kb / "inbox" / "draft.md").exists()
    assert (kb / "notes" / "draft.md").is_file()

    reverted = _run(runner, ["revert", "--root", str(kb), "--change", result["change_id"], "--apply"])
    assert reverted.exit_code == 0, reverted.output
    assert (kb / "inbox" / "draft.md").is_file()
```

- [ ] **Шаг 2: тесты падают** (`No such command 'move'`)
- [ ] **Шаг 3: реализовать команду и alias; добавить `move.*` в guidance**
- [ ] **Шаг 4: тесты проходят**

Run: `pytest tests/cli/test_cli_docs_move.py -v`
Expected: PASS

- [ ] **Шаг 5: коммит**

```bash
git add src/todoc/cli.py src/todoc/data/guidance/ru.json tests/cli/test_cli_docs_move.py
git commit -m "feat(cli): docs move/mv с preview, apply и guidance"
```

### Задача 9: документация, статус идеи, полевое испытание на копии демо

**Файлы:**
- Modify: `README.md` (таблица команд `docs move`)
- Modify: `SKILL.md` (маршрут переноса)
- Modify: `demo/notes/agent-contract.md` (правило «перенос — через `docs move`, не ручной rename»)
- Modify: `demo/references/state/03-cli-reference.md` (контракт `docs move`/`revert --change`)
- Modify: `demo/HOME.md` (план уже добавлен в список; проверить счётчики)
- Modify: `demo/ideas/docs-move.md` (идея уже переведена в `status: planned` при создании плана; проверить ссылку)

- [ ] **Шаг 1: обновить документацию** — добавить строку `docs move` в таблицу `README.md:117-125`, маршрут в `SKILL.md:29`, правило в `agent-contract.md` рядом с правилом 1, контракт в `03-cli-reference.md:52-59`; сверить счётчики в `HOME.md`.
- [ ] **Шаг 2: полевое испытание на копии демо**

```bash
rm -rf /tmp/demo-move && cp -r demo /tmp/demo-move
# Создать временный документ и ссылку на него
todoc --root /tmp/demo-move docs new --apply --type note --title "Move probe" --path inbox/move-probe.md
printf '\n[probe](../inbox/move-probe.md)\n' >> /tmp/demo-move/HOME.md
todoc --root /tmp/demo-move sync --apply HOME.md
# Preview → apply → проверки
todoc --root /tmp/demo-move docs move --from inbox/move-probe.md --to notes/move-probe.md
todoc --root /tmp/demo-move docs move --from inbox/move-probe.md --to notes/move-probe.md \
  --apply --if-plan-hash <hash>
todoc --root /tmp/demo-move validate --all          # 0
todoc --root /tmp/demo-move docs links --limit 1000 # 0 битых
todoc --root /tmp/demo-move revert --change move:<id> --apply
todoc --root /tmp/demo-move validate --all          # 0
```

- [ ] **Шаг 3: проверить `validate`/`check-config`/`docs links` на `demo/`**

```bash
todoc --root demo validate --all
todoc --root demo check-config
todoc --root demo docs links --limit 1000
```

Expected: 0 диагностик, 0 битых ссылок.

- [ ] **Шаг 4: коммит**

```bash
git add README.md SKILL.md demo/notes/agent-contract.md demo/references/state/03-cli-reference.md demo/HOME.md demo/ideas/docs-move.md
git commit -m "docs(move): команда docs move, статус идеи и полевое испытание"
```

### Задача 10: покрытие, гейты и закрытие

**Файлы:**
- Test: все новые/изменённые тесты
- Modify: `demo/plan/docs-move-implementation.md` (чекбоксы и §8)

- [ ] **Шаг 1: полный прогон**

```bash
.venv/bin/python -m coverage run --branch --source=src/todoc -m pytest -q
.venv/bin/python -m coverage report -m --fail-under=100
```

Expected: `TOTAL 100%`, все тесты PASS.

- [ ] **Шаг 2: гейты данных**

```bash
todoc --root demo validate --all
todoc --root demo check-config
todoc --root demo docs links --limit 1000
todoc --root demo stale
```

Expected: 0 диагностик, 0 битых ссылок; `stale` не вырос относительно baseline (пере-анкор `derived_from` для перемещённого документа).

- [ ] **Шаг 3: обновить §8 плана** — фактические команды, отклонения, номера коммитов.
- [ ] **Шаг 4: коммит**

```bash
git add demo/plan/docs-move-implementation.md
git commit -m "chore(plan): закрыть docs move — прогресс и гейты"
```

## 6. Definition of Done

- [ ] `docs move` и `mv` зарегистрированы в CLI; `--help` показывает все опции; `docs --help` перечисляет `move`.
- [ ] Preview не меняет ни один байт, не пишет историю и индекс; `plan_hash` стабилен между вызовами при неизменном корпусе.
- [ ] Apply требует `--if-plan-hash`; при несовпадении — exit 5, диск не тронут.
- [ ] Перенос/переименование: исходник удалён, цель создана, `validate --all` — 0 новых ошибок, `docs links` — 0 битых.
- [ ] Исходящие и входящие inline-ссылки/изображения пересчитаны; `#anchor`, title, alt сохранены; code fences/indented code/inline code не тронуты.
- [ ] Wikilinks и `related` обновлены при переименовании; коллизия — `move.wikilink_ambiguous`, запись не выполнена.
- [ ] Path-shaped `id` обновлён; смысловой `id` стабилен; `--keep-id` работает.
- [ ] `updated` бампнут у каждого изменённого `.md`; `created` не тронут.
- [ ] Записи: `source_path`, `source`, `sources[]`, `artifacts[]`, `baseline.artifacts`, `derived_from` обновлены; JSON без изменений не переписан.
- [ ] `derived_from` перемещённого документа: путь и хеш фрагмента обновлены; `stale` не даёт ложной тревоги на этот документ.
- [ ] История: одно событие `doc.move` с несколькими `paths[]` и `change_id: move:<hash>`; `todoc log --change` показывает его.
- [ ] `todoc revert --change <id> --apply` восстанавливает исходник, удаляет цель и возвращает все изменённые документы; preview показывает действия.
- [ ] OSError на середине коммита откатывает все байты; сбой истории откатывает файлы; ошибки имеют коды `move.history_failed`/`move.index_failed`/`move.rollback_failed`.
- [ ] `guidance` содержит `move.*` для всех error-кодов; контрактный тест проверяет наличие.
- [ ] `pytest` + `coverage report --fail-under=100` — PASS.
- [ ] `validate --root demo --all` — 0; `check-config --root demo` — 0; `docs links --root demo` — 0; `stale` не вырос.
- [ ] README, SKILL, agent-contract, CLI-reference, HOME и идея обновлены; счётчики совпадают с фактическим CLI.
- [ ] Полевое испытание на копии `demo/` прошло end-to-end, включая revert.

## 7. Риски и митигации

| Риск | Вероятность × влияние | Митигация | Владелец |
|---|---|---|---|
| Переписывание ссылок портит текст (сдвиг колонок, title/alt) | С × В | Замена по raw-span в обратном порядке; тесты на title/alt/fragment/code; `move.link_unsupported` для неподдержанных форм; валидатор блокирует поломку | исполнитель Задачи 2 |
| Overlay-валидация расходится с диском | С × В | Тест «overlay-результат == validate после apply»; `verify_sources=True`; один и тот же `validate_dataset` | исполнитель Задачи 4 |
| Откат на Windows/WSL неполный (занятый файл, case-only) | С × С | Восстановление байтов через `atomic_write`; case-only rename отклоняется; тест с инъекцией `OSError`; WSL-маршрут как основной | исполнитель Задачи 6 |
| Multi-path событие ломает существующую историю | Н × В | `schema_version: 1` не меняется, `paths[]` уже список; `record_write` делегирует с одним элементом; все старые тесты истории | исполнитель Задачи 5 |
| `derived_from` хеш не совпадает после переписывания ссылок | С × С | Пересчёт `fragment_hash` по новому тексту; тест section/pointer; `stale` в DoD | исполнитель Задачи 3 |
| Коллизия wikilinks остаётся незамеченной | С × С | Явная проверка `new_stem` по индексу; error при ссылках; warning без ссылок | исполнитель Задачи 2 |
| Предсуществующие ошибки блокируют перенос | С × С | Baseline-ключи `(code, path)` с маппингом `old → new`; блок только новых error | исполнитель Задачи 4 |
| Индекс не видит новый путь после коммита | Н × С | `ensure_index` после записи; `parse_cache.invalidate` старого и нового путей; тест `docs tree`/`docs read` | исполнитель Задачи 6 |
| `--to` с несуществующей папкой создаёт «полуперенос» | Н × С | `move.target_dir_missing` до записи; тест | исполнитель Задачи 1 |
| Ссылки в reference-style/autolinks не переписаны | С × Н | Warning + валидатор блокирует, если цель сломалась; явно вне скоупа | исполнитель Задачи 2 |
| Счётчики README/HOME расходятся с CLI | С × Н | Задача 9 сверяет фактические команды/документы; гейт `docs list` | исполнитель Задачи 9 |

## 8. Прогресс и отклонения

<!-- Resume-безопасность: исполнитель новой сессии начинает с первого
     неотмеченного чекбокса и читает этот раздел. Любое отклонение от плана —
     здесь: что не собралось, какой тест оказался неверным, какой подход выбран
     вместо планового и почему. Шаги задним числом не переписывать. -->

- 2026-11-28: план создан; код не начинался. Идея `doc:ideas/docs-move.md` переведена в `status: planned`, план добавлен в `demo/HOME.md`; Задача 9 сверяет документацию и счётчики.
