---
id: doc:ideas/docs-move.md
title: "Идея: todoc docs move — транзакционный перенос документа с автоправкой ссылок, связей и индекса"
doc_type: idea
lang: ru
status: planned
created: 2026-11-26
updated: 2026-11-28
tags: [ideas, idea, move, refactor, links, relations, cli, перенос]
related: ["[[entity-catalog]]", "[[folder-config]]", "[[agent-state]]", "[[todocignore]]", "[[entity-to-folder]]", "[[direct-edit-and-git-sync]]", "[[docs-move-implementation]]", "[[constitution.md]]"]
---

# Идея: `todoc docs move` — транзакционный перенос и переименование документа

- Тип: `idea`
- Создан: 2026-11-26
- Идентификатор: `doc:ideas/docs-move.md`
- Статус: `planned` (план создан 2026-11-28: [docs-move-implementation](../plan/docs-move-implementation.md))
- Аудит кода: 2026-11-28 — команды и модуля реализации в коде нет; ниже идея сверена с фактическим состоянием `src/todoc/`.

## Суть

Добавить CLI-команду **`todoc docs move`** (и алиас `mv`), которая **одной транзакционной операцией** переносит или переименовывает Markdown-документ внутри `DATA_ROOT`, автоматически пересчитывает входящие и исходящие ссылки, wikilinks, `related`, путевые поля записей, якоря `derived_from`, при необходимости меняет путевой `id`, пересобирает индекс и прогоняет валидацию. В ответ команда выдаёт компактный стандартный конверт (`ok: true` со счётчиками правок либо `ok: false` с `diagnostics[]` и полным откатом без следов на диске), экономя контекст агента.

## Проблема

1. **В CLI нет механизма переноса и переименования.** В группе `todoc docs` сейчас только `new`, `list`, `search`, `read`, `suggest`, `links`, `tree`, `flow`, `status`, `edit` (`src/todoc/cli.py:1666`; проверено `todoc docs --help`). Единственное перемещение данных в коде — `source.rename(target)` при архивации change-папки (`src/todoc/application/changes.py:694`); переименования в `src/todoc/application/registry.py:195` относятся к служебным каталогам индекса и граф ссылок датасета не трогают.
2. **Огромный перерасход токенов и вызовов при ручном переносе.** Чтобы перенести заметку из `inbox/` в профильную папку или переименовать legacy-файл с кириллическим именем, агенту приходится вручную искать все упоминания, пересчитывать относительные пути `../`, готовить десятки JSON-патчей `docs edit` для `HOME.md`, планов, карточек записей `records/documents/*.json` и `derived_from`, пересобирать индекс и запускать `validate --all`.
3. **Связи `todoc` многослойны, но не все слои одинаково реализованы.** Фактически документ связан с базой через: исходящие Markdown-ссылки и изображения, входящие относительные ссылки, wikilinks, `related` во front matter, `id` документа, путевые поля JSON-записей (`source_path`, `source`, `sources`, `artifacts`), якоря `derived_from` и индекс. При этом `related` проверяется только по форме, а не по существованию цели (`src/todoc/application/validator.py:423`), а `relations[].target.id` указывает на `record_id`, а не на путь документа (`src/todoc/application/validator.py:882`). Пропуск реально проверяемого слоя ломает `validate --all`; пропуск непроверяемого оставляет скрытый дрейф.
4. **Риск полуперенесённого состояния.** При ручной серии правок сбой на 5-м файле из 10 оставляет датасет с разорванными ссылками. Готового многопроходного отката для такой операции нет: `changes.apply_change` умеет откатывать запись файлов (`src/todoc/application/changes.py:614`), но не удаление исходника и не переименование; `todoc revert` работает с одним путём (`src/todoc/cli.py:1141`).

## Аудит соответствия коду (2026-11-28)

| Утверждение идеи | Факт в коде | Вердикт |
|---|---|---|
| Команды `docs move` нет | Группа `docs` объявлена в `src/todoc/cli.py:1666`; подкоманды перечислены выше. Модуля `application/move.py` нет. | Подтверждено: реализации нет. |
| Перенос — это только `source.rename` в `changes.py` | `src/todoc/application/changes.py:694` — архивация change-папки; `src/todoc/application/registry.py:195` — перестановка каталогов индекса. | Подтверждено с уточнением: оба перемещения служебные/узкие. |
| Ссылки и wikilinks парсятся AST, а не слепым replace | `parse_markdown` (`src/todoc/adapters/formats/markdown.py:286`) использует markdown-it-py; code fences/indented code/HTML исключаются (`_code_regions`, строка 154), wikilinks ищутся вне code-регионов и inline-code (`_wikilinks`, строка 270), относительные цели нормализует `resolve_link_target` (строка 341). | Подтверждено. Но `Link` не хранит `title`, признак изображения и точный raw-span; для перезаписи нужен helper или расширение модели. |
| Wikilinks можно квалифицировать путём `[[new-dir/stem]]` | `_wikilink_candidates` (`src/todoc/application/validator.py:72`) ищет только по basename/stem; путь в цели не поддерживается. Диагностики `markdown.link.ambiguous` в коде нет. | **Неверно.** При коллизии имён путь-квалификация не сработает; нужна отдельная политика. |
| `related` во front matter ломает `validate` | `_check_meta_fields` (`src/todoc/application/validator.py:423`) проверяет только форму `[[...]]`; существование цели явно не проверяется. `related` выводится в `docs read` (`src/todoc/cli.py:2236`), но граф ссылок на него не опирается. | **Уточнить:** обновлять `related` нужно для консистентности, но это не гейт валидатора. |
| `id` бывает смысловым и автогенерированным | `_document_id` (`src/todoc/service.py:296`) берёт `id` из front matter, иначе синтезирует `doc:<rel_path>`. `docs new` всегда пишет `id: doc:<rel>` в front matter (`src/todoc/application/write.py:472`). Отдельного маркера «автогенерированный» нет. | **Уточнить:** различать можно только по точному совпадению `id == f"doc:{old_path}"`; иначе считать смысловым. |
| `relations[].target.id` и `source_id` в записях ссылаются на документ | `validate_relations` (`src/todoc/application/validator.py:882`) проверяет `target.id` по множеству `record_id`; `source_id` есть только в производном индексе `relations.json`, в исходных записях его нет. | **Неверно для переноса документа:** рёбра `relations` менять не нужно; меняются путевые поля записей и `source_path` зеркал. |
| Путевые поля записей — это в основном `source_path` | Фактически в демо есть `source_path` (`document`, `guide`, `term`), `source` (`competitor`), `sources[]` (`decision`), `artifacts`/`baseline.artifacts` (`change`). Схемы: `demo/.todoc/entity_types/*/schema.json`. | **Уточнить:** нужен явный список полей, а не «любые строки пути». |
| `derived_from` — это `path#fragment@sha256:…` | `parse_anchor`/`format_anchor` (`src/todoc/application/staleness.py:100`, `:125`) поддерживают `path@sha256:…`, `path#section:<heading>@sha256:…` и `path#/json/pointer@sha256:…`. Хешируются фрагменты, а не всегда файл (`fragment_hash`, строка 64). | **Уточнить синтаксис:** `#fragment` в идее слишком общий; для секции — `#section:`, для JSON — JSON Pointer. |
| Папочные правила лежат в `directory-rules.json` / `document-rules.json` | Пути заданы в `demo/.todoc/dataset.json` и по умолчанию равны `.todoc/rules/directory-rules.json` и `.todoc/rules/document-rules.json` (`src/todoc/config.py:34`). | **Уточнить путь:** это `.todoc/rules/*`, а не файлы в корне. |
| Перенос в `ideas/` автоматически делает документ `idea` и требует секции | `resolve_type` (`src/todoc/typing_system/resolver.py:117`) даёт **высший приоритет явному `doc_type` во front matter**; правило папки срабатывает только без явного типа. В демо все 301 `.md` имеют `doc_type`. | **Неверно для демо:** типом управляет front matter; перетипизация возможна только для документа без `doc_type` или через отдельный флаг. |
| Папочный тег в `tags` заменяется автоматически | В коде нет вывода тегов из папки. `tags` — свободный список 0–8 kebab-тегов; проверяется только формат (`src/todoc/application/validator.py:432`). | **Не реализовано:** автоматическую замену тега обещать нельзя. |
| `.todocignore` можно проверить при переносе | `.todocignore` пока только идея (`demo/ideas/todocignore.md`); в коде его нет. Сканер исключает только `HARD_EXCLUDE_DIRS` (`src/todoc/adapters/filesystem/scanner.py:12`). | **Зависимость не реализована:** в v1 проверять только hard-exclude и containment. |
| `state.json` хранит указатели путей | `state.json` — внешний агентский стейт с `vars` и белым списком ключей (`src/todoc/application/state.py:30`); путевых указателей в v1 нет. | **Уточнить:** обновлять нечего; путь в `state` не хранится. |
| Открытые `changes/*/change.json` надо обновлять | `change.json` хранит `artifacts[]` и `baseline.artifacts` с путями (`src/todoc/application/changes.py:155`, `:522`). | Подтверждено, но только для этих полей. |
| Валидацию можно прогнать «в памяти» | `validate_dataset` читает файлы с диска через `_read_validation_text` (`src/todoc/application/validator.py:160`) или parse-cache; API виртуального overlay нет. | **Требует доработки:** нужен overlay-параметр или временный корень. |
| Индекс пересобирается после записи | `DatasetContext.ensure_index`/`rebuild_index` (`src/todoc/service.py:253`, `:276`), публикация снапшота — `RegistryStore.publish` (`src/todoc/application/registry.py:164`). | Подтверждено. |
| История даёт откат всей операции | `record_write` пишет событие с одним `paths[]`-элементом (`src/todoc/application/history.py:79`); `todoc revert` откатывает один путь (`src/todoc/cli.py:1141`); `change revert` — только change-сущность (`src/todoc/cli.py:1534`). | **Не реализовано:** для атомарного move нужен multi-path event и multi-path revert. |
| Конверт `schema_version: 1` и `data.applied` | `Envelope.result` отдаёт `schema_version: 2` и `data = {meta, result}` (`src/todoc/output/envelope.py:14`, `:35`); `guidance` включается всегда. | **Уточнить формат ответа.** |
| Код конфликта — `4` | `EXIT_ACCESS = 4`, `EXIT_CONFLICT = 5` (`src/todoc/errors.py:19`). | **Неверно:** конфликт — `5`; `4` — доступ/выход за `DATA_ROOT`. |
| BUG-006 и BUG-007 ещё открыты | BUG-006 `fixed` (слаг транслитерируется, `src/todoc/cli.py:1670`); BUG-007 `fixed` (`docs links`, `src/todoc/cli.py:2390`). BUG-011 `open`. | **Обновить ссылки и статусы.** |

## Принципы

1. **Атомарность «всё или ничего».** Все новые версии затрагиваемых файлов собираются и валидируются до коммита. Если целевое состояние порождает новую ошибку схемы, типа, ссылки или конфликт хеша — на диске не меняется ни один байт. Это должно включать удаление исходника и запись истории, а не только запись новых файлов: текущий `apply_write_plan` пишет файл до `history.record` (`src/todoc/application/write.py:112`), а `changes.apply_change` откатывает только ошибки записи файлов (`src/todoc/application/changes.py:644`).
2. **Review-first по канону CLI (`--preview` → `--apply`).** Без `--apply` команда работает как сухой прогон: возвращает компактную сводку предстоящих переписываний и результат предвалидации без модификации файлов, истории и индекса. Для защиты от устаревшего preview используется `--if-plan-hash`, как в `docs new`/`docs status`; для защиты исходника — `--if-hash`.
3. **Экономия контекста агента (Bounded Envelope).** В дефолтном ответе — счётчики, пути и хеши, без многокилобайтных диффов. Полный дифф — только по явному `--verbose`.
4. **Правка ссылок по разбору, а не слепым `replace`.** Ссылки внутри fenced/indented code и inline-code не переписываются: это уже обеспечивает `parse_markdown` (`src/todoc/adapters/formats/markdown.py:154`, `:270`). Для перезаписи нужно сохранять title, alt и вид ссылки; текущий `Link` этого не содержит, поэтому нужен helper на raw-line span или расширение `Link`.
5. **Стабильность явной идентичности.** Смысловой `id` (`doc:home`, `competitor:mem0`) не меняется. Путевой `id: doc:<old_path>` (точное совпадение с текущим путём) по умолчанию меняется на `doc:<new_path>`; `--keep-id` оставляет старый. Других способов отличить «автогенерированный» id в коде нет.
6. **Единое событие в истории.** Перенос файла, правки ссылок и записей должны попадать в `history` под одним `change_id` (например, `move:<hash>`) и, желательно, одним событием с несколькими `paths[]`; текущий API пишет одно событие на один путь, поэтому нужен новый метод записи.

## Предложение

### 1. Контракт команды CLI

```bash
# Предпросмотр (по умолчанию) по id или текущему пути:
todoc docs move --root KB --id doc:inbox/draft.md --to notes/caching-strategy.md
todoc docs move --root KB --from inbox/draft.md --to notes/

# Применение с проверкой preview и исходника:
todoc docs move --root KB --from inbox/draft.md --to notes/caching-strategy.md \
  --apply --if-plan-hash <hash> --if-hash sha256:...
```

- Вход: ровно один из `--id <doc_id>` / `--from <rel_path>` плюс обязательный `--to <rel_path_or_existing_dir>`.
- Область v1: только Markdown-документы (`.md`, `.markdown`). JSON-зеркала `records/documents/*.json` обновляются как записи, но сами не переносятся; CSV/JSON-документы и папки — вне v1.
- `--to` с существующей папкой сохраняет имя файла; путь с несуществующей папкой трактуется как точный путь файла. Расширение цели должно совпадать с исходным.
- Опции: `--preview` (дефолт) / `--apply`, `--if-hash <sha256>` (оптимистическая блокировка исходника), `--if-plan-hash <hash>` (защита preview), `--keep-id`, `--pin-type` (материализовать текущий тип в front matter, если он выведен из правила старой папки), `--adopt-target-type` (принять тип целевой папки; обсуждается), `--verbose` (полный дифф), `--output json|table|markdown`.
- Коды возврата: `0` — успех; `1` — операционная ошибка; `2` — `EXIT_USAGE`; `3` — `EXIT_VALIDATION` (новая ошибка после симуляции); `4` — `EXIT_ACCESS` (цель/источник вне `DATA_ROOT`, symlink, `.todoc`); `5` — `EXIT_CONFLICT` (цель существует, `hash_mismatch`, устаревший plan hash); `6` — `EXIT_INCOMPLETE` (сбой индекса/истории).

### 2. Матрица автокоррекции с учётом фактического кода

| Контур | Факт в коде | Что должна делать `docs move` |
|---|---|---|
| **1. Исходящие ссылки и изображения внутри переносимого `.md`** | `parse_markdown` отдаёт `Link` с `target`, `fragment`, `line`, `column`, `end_column`; code-регионы исключены (`src/todoc/adapters/formats/markdown.py:286`). `Link` не хранит title/alt и вид ссылки. | Пересчитать относительные цели от новой папки, сохранить `#fragment`, title и alt. Для inline-ссылок/изображений — замена target в raw-span; reference-style/autolink в v1 либо поддержать отдельно, либо не переписывать и сообщить диагностикой. |
| **2. Входящие относительные ссылки во всех `.md`** | Валидатор и `build_mentions` нормализуют цели через `resolve_link_target` (`src/todoc/application/validator.py:344`, `:173`). | Найти все ссылки, чья нормализованная цель равна `old_path`, и заменить на путь относительно папки каждого документа-источника с сохранением фрагмента. |
| **3. Wikilinks `[[...]]` и `related`** | Wikilinks парсятся вне code (`markdown.py:270`), но резолвятся только по basename/stem (`validator.py:72`); `related` проверяется только по форме (`validator.py:423`). | При смене имени файла обновить stem в wikilinks и `related`. При коллизии stem путь-квалификация **не работает**: нужна политика — диагностика `docs.move_wikilink_ambiguous`, `--force`, либо конвертация в относительную Markdown-ссылку. |
| **4. `id` документа и `relations` записей** | `id` из front matter имеет приоритет (`service.py:296`); `docs new` пишет `doc:<rel>` (`write.py:472`). `relations[].target.id` проверяется по `record_id` (`validator.py:882`), `source_id` — только в производном индексе. | Менять `id` только при точном совпадении `id == f"doc:{old_path}"`; `--keep-id` отключает. Рёбра `relations` не переписывать: они ссылаются на `record_id`, а не на путь. |
| **5. Путевые поля JSON-записей** | Реальные поля: `source_path` (`document`, `guide`, `term`), `source` (`competitor`), `sources[]` (`decision`), `artifacts[]`/`baseline.artifacts` (`change`). Валидатор проверяет только `source_path` при заданном `source_anchor` (`validator.py:218`). | Обновлять явный список путевых полей, а не все строки. Для `artifacts`/`baseline.artifacts` менять и значение, и ключ baseline. |
| **6. Якоря `derived_from` и `stale_ack_hashes`** | `parse_anchor`/`format_anchor` (`staleness.py:100`, `:125`); `fragment_hash` хеширует секцию/pointer/файл (`staleness.py:64`); подтверждения хранятся в `stale_ack_hashes` (`staleness.py:33`). | Обновить путь в строковых и объектных зависимостях. Пересчитывать хеш только если фрагмент реально изменился; не «освежать» подтверждение молча — при механическом изменении секции либо обновить `stale_ack_hashes`, либо снять подтверждение и показать диагностику. |
| **7. Правила папки, `doc_type`, `tags`, `updated`** | Правила лежат в `.todoc/rules/*.json` (`config.py:34`); явный `doc_type` во front matter важнее правила папки (`resolver.py:117`). В демо все `.md` имеют `doc_type`. Папочного тега в коде нет; `updated` бампает `bump_front_matter_updated` (`write.py:181`). | Проверить структуру целевого типа только если тип реально меняется (нет `doc_type` или включён `--adopt-target-type`). `--pin-type` фиксирует текущий тип. `updated` бампать у каждого изменённого `.md`, не только у перенесённого. |
| **8. Containment, `.todoc`, индекс и валидация** | `atomic_write` и `is_within_root` (`scanner.py:53`, `:30`); hard-exclude `HARD_EXCLUDE_DIRS` (`scanner.py:12`); `ensure_index`/`publish` (`service.py:276`, `registry.py:164`). `.todocignore` в коде нет. | Запрещать цель вне `DATA_ROOT`, symlink и любой сегмент `.todoc`/`.git`/другой hard-exclude. `.todocignore` проверять только после его реализации. После записи — `ensure_index`; диагностики сравнивать с baseline, чтобы не блокировать перенос из-за уже существующих ошибок. |

### 3. Формат ответа CLI

Успешный `--apply` (фактический конверт v2, `data.meta` + `data.result`):

```json
{
  "schema_version": 2,
  "ok": true,
  "data": {
    "meta": {
      "command": "docs move",
      "scope": {"dataset_id": "dataset-80c70868", "root": "/path/to/KB"}
    },
    "result": {
      "preview": false,
      "applied": true,
      "plan_hash": "9f1c…",
      "moved": {
        "id": "doc:notes/caching-strategy.md",
        "old_id": "doc:inbox/draft.md",
        "from": "inbox/draft.md",
        "to": "notes/caching-strategy.md",
        "old_hash": "sha256:1111…",
        "new_hash": "sha256:2222…"
      },
      "rewrites": {
        "outbound_links": 3,
        "inbound_docs": 4,
        "inbound_links": 5,
        "wikilinks": 2,
        "records": 2,
        "derived_from": 1
      },
      "index": {"generation_id": "a9c01f22e81b", "diagnostics": 0, "new_diagnostics": 0},
      "change_id": "move:7f3a91c0"
    }
  },
  "diagnostics": [],
  "next_actions": [
    {"argv": ["todoc", "--root", "/path/to/KB", "docs", "read", "--id", "doc:notes/caching-strategy.md"], "purpose": "Прочитать перенесённый документ"},
    {"argv": ["todoc", "--root", "/path/to/KB", "validate", "--all"], "purpose": "Проверить датасет после переноса"}
  ],
  "guidance": {"profile": "ru", "mode": "compact", "items": []}
}
```

Отказ (например, новая ошибка структуры целевого типа; диск не тронут):

```json
{
  "schema_version": 2,
  "ok": false,
  "data": {
    "meta": {"command": "docs move", "scope": {"dataset_id": "dataset-80c70868", "root": "/path/to/KB"}},
    "result": {"preview": false, "applied": false, "plan_hash": "9f1c…"}
  },
  "diagnostics": [
    {
      "dataset_id": "dataset-80c70868",
      "id": "diag_8a12bc90",
      "code": "markdown.section.missing",
      "severity": "error",
      "path": "ideas/caching-strategy.md",
      "location": {"line": 1, "column": 1},
      "evidence": "doc_type declares required_sections: Проблема",
      "message": "Required section missing: Проблема",
      "suggested_fixes": []
    }
  ],
  "next_actions": [],
  "guidance": {"profile": "ru", "mode": "on_error", "items": []}
}
```

Пример ошибки структуры корректен только для документа без явного `doc_type` или при `--adopt-target-type`: в демо все документы объявляют `doc_type`, и перенос в `ideas/` сам по себе тип не меняет.

## План внедрения

1. **Фаза 1 — планировщик `src/todoc/application/move.py` (без записи на диск):**
   - `MovePlan`: исходный и целевой пути, список `files[]` с `before_hash`/`after_text`, список удалений, изменения `id`, счётчики переписываний, диагностики, `plan_hash`.
   - Разрешение источника через `DatasetContext.read_index` (`service.py:192`), проверка формата, `--if-hash`, уникальности `id`, containment и hard-exclude.
   - Переписывание ссылок на основе `parse_markdown` и `resolve_link_target`; для raw-span нужен helper `replace_link_target` или расширение `Link` (`is_image`, `title`, raw span). Wikilinks — через `_wikilinks`/regex с сохранением alias/fragment; при коллизии — диагностика.
   - Обновление `id`, `related`, `source_path`/`source`/`sources`, `artifacts`, `derived_from`; `updated` для каждого изменённого `.md`.
   - Предвалидация: добавить overlay-параметр в `validate_dataset` (path → text) или валидировать во временном корне; сравнить диагностики с baseline. Без этого «в памяти» текущий валидатор не работает.
   - *Acceptance:* unit-тесты `tests/unit/test_move.py` на перенос вверх/вниз, переименование, `#anchor`, code fences/inline code, id path-shaped vs semantic, коллизию wikilinks, `derived_from` section/pointer, отказ без записи.
2. **Фаза 2 — транзакционный коммиттер, история и индекс:**
   - Предвычислить все байты; записать новые/изменённые файлы через `atomic_write`; удалить старый путь; при ошибке вернуть все файлы и восстановить удалённый из резервной копии. Использовать rollback-паттерн `changes.apply_change` (`changes.py:644`), но с удалением.
   - Добавить в `history` запись одного события с несколькими `paths[]` (новый `record_event`/`record_move` рядом с `record_write`, `history.py:79`); при сбое истории откатить файлы.
   - `ensure_index`/`rebuild_index` после успешного коммита; `parse_cache.invalidate` для старого и нового путей.
   - *Acceptance:* инъекция `OSError` на середине коммита откатывает все файлы; сбой `history.record` тоже откатывает; `todoc log --change <id>` показывает одно событие; multi-path revert восстанавливает исходник и удаляет новый файл; 100% branch coverage.
3. **Фаза 3 — CLI `todoc docs move` / `mv` и полевое испытание:**
   - Подключить команду в `src/todoc/cli.py` с `UnifiedCommand`, `--preview`/`--apply`, `--if-hash`, `--if-plan-hash`, `--keep-id`, `--pin-type`, `--verbose`, `--output`.
   - Алиас `mv`: в текущем `DiscoverableGroup` механизма алиасов нет; нужен либо скрытый `mv`-command, либо расширение группы.
   - Добавить коды и подсказки в `src/todoc/data/guidance/ru.json` (`move.*`) и контрактные тесты `guidance`.
   - Полевое испытание: переименовать legacy-файл с кириллицей одной командой; `validate --root demo --all` = 0, `docs links --root demo` = 0 битых; `git diff` содержит только ожидаемые файлы; `todoc revert --change <id>` возвращает состояние.
   - *Acceptance:* CLI-тесты в `tests/cli/test_unified_docs.py`; 100% покрытие.

## Открытые вопросы

- **Различение path-shaped и смыслового `id`:** в коде нет маркера; предлагается точное совпадение `id == f"doc:{old_path}"`. Достаточно ли этого, или нужен явный `provisional: true` в front matter?
- **Коллизия wikilinks:** путь-квалификация `[[dir/stem]]` текущим резолвером не поддерживается. Что делать по умолчанию — диагностика и отказ, `--force` с оставлением неоднозначного wikilink, или конвертация в относительную Markdown-ссылку?
- **`related`:** обновлять всегда (консистентность) или только по явному флагу, учитывая, что валидатор существование целей не проверяет?
- **Путевые поля записей:** ограничиться списком `source_path`/`source`/`sources`/`artifacts` или ввести декларацию path-полей в схеме типа записи?
- **`.todocignore`:** проверять цель после реализации идеи `todocignore` или в v1 ограничиться hard-exclude? Код `move.target_ignored` сейчас не существует.
- **Перетипизация:** нужен ли `--adopt-target-type` (принять тип целевой папки и проверить секции) в дополнение к `--pin-type`?
- **Перенос папки:** `todoc docs move --dir <old_dir> --to <new_dir>` — вторая итерация или v1?
- **Локальные ассеты:** `--with-assets` для картинок рядом с документом или только пересчёт относительных ссылок?
- **Симметричный `todoc records move`:** нужен ли для JSON-записей с `source_path`/`artifacts`?
- **Multi-path revert:** расширять `todoc revert` флагом `--change <id>` или делать отдельную команду `todoc history revert-change`?
- **Case-only rename:** на case-insensitive ФС (Windows/WSL) `os.replace` может не изменить регистр; нужен отдельный temp-rename сценарий?
- **Reference-style links/autolinks:** переписывать определения ссылок или в v1 оставлять их с диагностикой?
- **Предсуществующие диагностики:** блокировать перенос только новыми ошибками (baseline diff) или требовать чистый `validate --all`?

## Связанные документы

- [План реализации `todoc docs move`](../plan/docs-move-implementation.md)
- [Конституция `todoc` (FR-1, FR-5.4–5.5)](../plan/constitution.md)
- [Идея: справочник сущностей системы и единый граф ссылок `u-graph`](entity-catalog.md)
- [Идея: `.config.json` — самоописание папок](folder-config.md)
- [Идея: `.todocignore` — исключение посторонних файлов и папок из индексации](todocignore.md)
- [Идея: `todoc folderize` — преобразование сущности в папку-домен](entity-to-folder.md)
- [Идея: прямая правка и финализация `todoc sync`](direct-edit-and-git-sync.md)
- [BUG-006: `docs new` создаёт кириллические имена файлов](../bugs/bug-006--docs-new-создаёт-кириллические-имена-файлов-из-кириллического-заголовка.md) — `fixed`
- [BUG-007: `docs links` — инвентаризация локальных ссылок](../bugs/bug-007--linkcheck-command-missing.md) — `fixed`
- [BUG-011: дрейф `derived_from` требует ручного ре-анкоринга](../bugs/bug-011-dreyf-derived-from-pri-smene-statusa-tela-ishodnika-trebuet-ruchnogo-re-ankoringa.md) — `open`

## Связь с выпуском единого CLI

В выпуске единого CLI конверт уже переведён на `schema_version: 2` с `data.meta`/`data.result`, `diagnostics`, `next_actions` и `guidance`; `docs move` в выпуск не входил и остаётся идеей. Перенос документа, переписывание ссылок и re-anchor остаются в объёме этой идеи.

[Сводка выпуска единого CLI](../notes/unified-cli-release.md).
