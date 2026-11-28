---
id: doc:plan/docs-move-implementation.md
title: "Транзакционный перенос документов todoc docs move: ссылки, записи, история и откат (план реализации)"
doc_type: plan
lang: ru
status: done
created: 2026-11-28
updated: 2026-11-28
covers: ["doc:ideas/docs-move.md"]
tags: [plan, move, rename, links, wikilinks, history, revert, cli]
related: ["[[docs-move]]", "[[entity-to-folder]]", "[[direct-edit-and-git-sync]]", "[[todocignore]]", "[[agent-contract]]", "[[constitution.md]]"]
---


# Транзакционный перенос документов `todoc docs move`: план реализации после аудита

> **Исполнителю:** реализация v1 выполнена 2026-11-28; результаты приёмки и ограничения — в §8. План закрыт по явной команде пользователя 2026-11-28.
> Работать по задачам 1–10; перед каждым изменением проверять актуальный код.
> Не отмечать задачу до её тестов; завершение идеи/плана — только по подтверждению пользователя.
> Редакция заменяет исходные алгоритмы и примеры целиком; доказательства исходных дефектов — в §8 и BUG-070–074.

**Суть простыми словами:** переносить или переименовывать одну Markdown-страницу вместе с её проверяемыми связями, предварительно показывая изменения. Не терять исходник и не затирать более поздние правки при откате.
**Зачем сейчас:** ручной перенос опасен; будущим папкам-доменам и миграции проектов нужно одно ядро переписывания ссылок, а не несколько несовместимых реализаций.
**На выходе:** preview без записи; защищённый apply; одно событие истории; безопасный обратный перенос; проверяемый контракт ошибок.
**Не делаем:** перенос папок, JSON/CSV-источников, миграцию всего датасета, SQLite, `.todocignore`, новый проектный резолвер или общий автоматический ре-анкоринг.

**Цель:** одиночный перенос Markdown внутри одного явно заданного DATA_ROOT с пересчётом поддержанных ссылок, идентичности, путевых полей записей и механически изменённых якорей, с preview/apply и multi-path revert.
**Спецификация:** [идея docs move](../ideas/docs-move.md), [конституция](constitution.md), [контракт агента](../notes/agent-contract.md), [текущая архитектура](../references/state/02-architecture.md), [форматы](../references/state/05-formats.md), [хранилище](../references/state/09-storage-and-index.md).
**Стек:** Python 3.11+, click, markdown-it-py, jsonschema; без новых runtime-зависимостей. Coverage — 100% всего `src/todoc`, включая ветви, не только нового модуля.

## 1. Критерии успеха

1. Preview и все отказы до apply не меняют ни источники, ни индекс/кэш, ни историю/стейт. Два preview на неизменном корпусе в одну дату дают один `plan_hash`.
2. Apply требует `--if-plan-hash`; хеш связывает весь read-set, конфигурацию, опции, дату и итоговые байты. Изменение нетронутого ранее входящего документа, нового файла или правил после preview блокирует старый план, в том числе при прямом вызове application API.
3. Поддержанные входящие и исходящие ссылки сохраняют цель, фрагмент, title/alt. Текст примеров в коде/HTML не переписывается. Если затронутая форма не может быть безопасно изменена, операция **отказывается**, а не надеется, что валидатор заметит смену смысла.
4. До первой записи виртуальное состояние проходит ту же валидацию и построение mentions, что реальный корпус. Для v1 baseline с error блокирует перенос; warning не равен error. Это **явное сужение** исходной идеи о допуске старых ошибок ради безопасного первого выпуска (см. §8).
5. Одно событие `doc.move` хранит точные before-images и различает отсутствие файла и пустой файл. Revert проверяет post-state всей операции и не уничтожает последующие изменения.
6. Ошибка до публикации события восстанавливает источники. Публикация события — точка коммита. Сбой производного индекса после неё возвращает `applied: true`, `index_published: false`, exit 6 и команды восстановления, а не ложное «ничего не применено».
7. Полный pytest, 100% branch coverage, validate/check-config/linkcheck и полевой сценарий на копии. Все preexisting stale остаются видимыми; новые вторичные stale перечислены, не подтверждены автоматически.

## 2. Вне скоупа

- v1 переносит один `.md`/`.markdown` в **существующую** папку, с тем же расширением. Ассеты не двигаются. Case-only rename отклоняется на всех платформах, а не только Windows.
- Не переносим каталоги, записи, JSON/CSV-документы; не создаём `.config.json` и папки. Пакетный transaction/folderize — отдельная итерация, потребляющая чистые helpers, не цикл готовых независимых `apply_move`.
- Не добавляем `.todocignore` до реализации общего matcher. Проверяем действующие hard-exclude. Не считаем будущие идеи работающими API.
- Не реализуем project visibility/archive/disabled-фильтры. **Целостность проверяется по всему DATA_ROOT**, не по видимому поисковому скоупу; будущий слой фильтрации не должен скрывать входящие ссылки от move.
- Не меняем `tags`, `enabled`, жизненные статусы, `record_id`, `relations[].target.id`, свободный текст и примеры путей в code fences. Не меняем внешний `state.json`, operational logs и конфиги `.todoc/` автоматически.
- Не обещаем переписать все строки, похожие на путь. Для активных `changes/*/deltas` применяем отдельный preflight (§4); произвольные внешние/исторические ссылки вне DATA_ROOT не входят в граф.
- Reference-style, autolink и сложный inline поддерживаются для чтения как раньше. Для move: если их разрешённая цель изменится и нет доказанного editable span — error `move.link_unsupported`. Незатронутые формы оставляем без предупреждения.
- Механический move не выполняет содержательное review зависимого плана и не заменяет будущий `stale reanchor`. Циклические derived_from не ре-анкорим рекурсивно.
- Транзакционность v1 — rollback при обрабатываемых исключениях в одном процессе. **Не crash-atomic** для kill -9, отключения питания или произвольного параллельного внешнего редактора. Несколько файлов не становятся атомарно видимыми всем читателям через `os.replace`.
- Никаких автоматических Git-коммитов/пушей и смены ветки. Указанные тестовые коммиты — действие исполнителя только по действующим правилам окружения.

## 3. Глобальные ограничения

- Истина — файлы/конфигурация. Индекс и кэш пересобираются; **история не пересобирается**, удалять её нельзя (действующий контракт хранилища). Старое утверждение, что история такой же кэш, исключено.
- Тонкий CLI, envelope v2 (`data.meta`/`data.result`, diagnostics, next_actions, guidance), `UnifiedCommand`, наследование output/no-input. Все новые коды — в i18n-каталоге.
- Preview читает через `ctx.read_index`/строгий scan, не через `ensure_index`, не пишет parse-cache, не вызывает observation истории.
- Все пути DATA_ROOT-relative POSIX. Отдельно проверять сырые сегменты до resolve и lstat всей цепочки: абсолютные/drive/UNC-пути, `..`, backslash, symlink (в т.ч. битые), hard-exclude, непереносимые/зарезервированные имена. Проверки повторяются непосредственно перед записью и revert; путь из журнала не доверенный.
- Существующие legacy-имена источников с кириллицей можно переносить; не вводить массовую миграцию имён. Цель должна быть portable (`portable_name` — **санитайзер**, не готовый валидатор: отклонить, если нормализация изменила сегмент).
- Все hash источников — от **байтов**, UTF-8 decode строгий; BOM, CRLF/LF и отсутствие финального newline сохранять. Не читать через нормализующий `read_verified_text` для последующей записи. `created` не меняется; `updated` обновляется движком только если поле существует и дата старее текущей UTC-даты.
- `bump_front_matter_updated` сейчас нормализует строки: сначала исправить его с регрессиями либо вынести сохраняющий байты helper; не использовать старую реализацию слепо.
- Экономный вывод: по умолчанию только счётчики, хеши и первые 20 file-summary. Поля `files_total`, `files_returned`, `files_truncated`; `--verbose` явно запрашивает полный diff. Пагинация/фильтр представления не меняют hash операции.
- Примеры `todoc` ниже в этой песочнице означают `.venv/bin/todoc`; тесты — `.venv/bin/python -m pytest`. WSL-обёртка из AGENTS нужна только на Windows-харнессе, не здесь.

**Review Focus (каждый риск закреплён за задачей):**

| Риск | Обязательное доказательство |
|---|---|
| Настоящая ссылка совпадает с примером в code span; reference съедает соседний span | точный destination-span или отказ, T1 |
| Новый входящий файл/правило после preview; swap symlink | stale/containment refusal до записи, T2/T6 |
| Старый drift исчезает из-за безусловного hash/ack refresh | stale и acknowledgement не «отмываются», T3 |
| Удалённый исходник спутан с пустым файлом; Git без snapshot | exists-flags, exact before-images, обратный ход, T5/T7 |
| fsync истории, индекс или rollback падают в разные фазы | явная таблица состояний, byte-manifest и event-count, T5/T6 |

## 4. Архитектура и файловая карта

### 4.1. Контракты данных

Application-ядро не импортирует click и не печатает. `MovePlan` не принимает caller-provided новые байты без проверки неизменности/целостности плана.

```python
# src/todoc/application/move.py — новые immutable dataclasses
MoveFile(path: str, before: bytes | None, after: bytes | None)
# None означает отсутствие, b"" — существующий пустой файл.
MovePlan(dataset_id: str, source: str, target: str, old_id: str, new_id: str,
         corpus_digest: str, planned_on: str, options: dict[str, bool],
         files: tuple[MoveFile, ...], rewrites: dict[str, int],
         diagnostics: tuple[dict[str, Any], ...], plan_hash: str)
plan_move(ctx: DatasetContext, *, source: str | None, doc_id: str | None,
          target: str, keep_id: bool = False, pin_type: bool = False) -> MovePlan
apply_move(ctx: DatasetContext, plan: MovePlan, *, if_plan_hash: str,
           if_hash: str | None = None) -> dict[str, Any]
# ordinal order files: moved target, deleted source, sorted dependent paths.
```

`plan_hash = selection_key` от версии контракта, dataset_id, source/target, old/new_id, `corpus_digest`, даты, отсортированных опций и `(path, before_hash|null, after_hash|null)` **всех** операций. None и hash пустых байтов не смешиваются. В hash не входят generation_id, абсолютный sandbox-path, время выполнения и оформление вывода. Новый `change_id` — `move:<uuid4hex>` **на успешную попытку**, не короткий hash плана: повтор move→revert→move не склеивает события.

### 4.2. Безопасное переписывание

- Разделить display-координаты текущего `Link` и edit-координаты. `Link.column/end_column` — не достаточное доказательство; `end_column` включительный. Не копировать `_INLINE_LINK_RE` в move.
- Добавить в адаптер чистый `editable_link_spans(text: str) -> list[LinkEditSpan]`, где `LinkEditSpan` хранит `link: Link`, `destination_start: int | None`, `destination_end: int | None`, `syntax: str`; offsets в исходной строке текста, 0-based `[start,end)`. Для недоказуемого destination оба None. Контракт: no guessing/fallback, декодированная цель и fragment сверены с token; спаны не пересекаются и не попадают в code/HTML. Реализация поддержанного subset — один изолированный helper адаптера, не второй общий Markdown-парсер.
- Поддержать простые однострочные inline links/images (plain destination без пробелов/скобок, необязательный double-quoted title) и wikilinks. Остальные затронутые конструкции честно отклонять. Первая задача обязана протестировать повторяющиеся href, inline code на той же строке, reference рядом с inline, изображения-ссылки и percent-encoded path. Не доказано — отказ, а не повреждение.
- Record-target имеет приоритет перед файловым target (`validator.py:367`): `[term](term:x#/title)` и `[[term:x]]` не превращаются в относительные пути. Anchor-only `#part` в самом переносимом документе остаётся anchor-only. Внешние ссылки не переписываются.
- Для каждой локальной ссылки определить **цель до и после**. Исходящую из переносимого документа пересчитать относительно нового родителя; входящую на старый путь — относительно родителя владельца. Сохранить fragment, title, alt; URI-escape пути через quote, чтобы пробел/`#`/`%` в имени не изменили синтаксис. Проверить повторным parse равенство ожидаемых семантических целей.
- Wikilink разрешать тем же basename/stem-resolver, что валидатор, с приоритетом record_id. Проверять коллизии **старого и нового** stem, `.md`/`.markdown`, форму `[[name.md]]`, fragment/alias и `related`. Затронутая неоднозначность — `move.wikilink_ambiguous`; не менять все `[[old]]` при двух старых кандидатах. Семантически неизменившуюся неоднозначность не считать новой.
- `related` переписывать тем же лексическим helper; это слой метаданных, которого не видит Markdown body graph. `covers[]` — точные document IDs: при смене path-shaped ID переписать в Markdown и управляемых JSON-метаданных. Не трогать semantic IDs и произвольные строки.

### 4.3. Записи, зависимости, изменения

- `source_path`, `source`, строки в `sources[]`/`artifacts[]` JSON-записей: только точное равенство старому DATA_ROOT-relative пути. В `baseline.artifacts` меняется **ключ пути**, историческое значение hash остаётся прежним; коллизия ключа — отказ. Непутевые URL/тексты не трогать. JSON менять только при реальном изменении (`json.dumps(indent=2, ensure_ascii=False) + "\n"`), остальные байты файлов оставить.
- JSON-документы с `meta` не переносятся, но их `meta.derived_from`/`meta.covers` — поддержанные входящие метаданные. Учитывать также плоский документный профиль и записи через существующий metadata adapter; не обходить произвольные вложенные строки. `source_path`/`source_anchor` зеркал и mentions проверить вместе.
- `id == 'doc:' + old_path` меняется; semantic id сохраняется. `--keep-id` без явного id материализует старый сгенерированный id во front matter, иначе обещание невозможно. Документ без front matter получает минимальный блок только если запрошены keep-id/pin-type; обычный перенос не создаёт метаданные без нужды.
- `--pin-type` материализует старый inferred doc_type, явный тип не меняет. При отсутствии определённого типа — warning. Без pin-type в preview явно показать old/new doc_type и проверить новую структуру; не вводить автоматический adopt.
- Добавить `fragment_hash_text(text: str, dep: dict[str, Any]) -> tuple[str | None, str]` в `staleness.py`; существующий `fragment_hash(root, dep)` остаётся совместимой оболочкой. File hash для read-set байтовый, а staleness hash использует **существующую** семантику UTF-8/universal-newline, section/pointer/canonical JSON. Нельзя применять дисковый helper к ещё не созданной цели.
- В `derived_from` (строки и объекты) всегда перенести путь. Hash менять **только если expected == before-fragment** и after-fragment разрешим; иначе оставить expected и выдать `move.preexisting_stale`. Не обновлять на текущий hash ранее устаревшую зависимость. Для одного файла/hash, разделяемого несколькими зависимостями, не менять ACK_HASHES глобальным replace: переносить ack только при однозначном механическом соответствии; иначе удалить затронутый ack-hash с warning `move.ack_invalidated`, reason/time не переизобретать.
- Вторичные владельцы зависимостей от переписанных входящих файлов не ре-анкорятся. Выводить `new_stale[]`/счётчик, не обещать общее `stale == 0` или «stale не вырос» при любом переносе. Cyclic/self-derived_from не вычислять до неподвижной точки: отказ `move.dependency_cycle`, если операция требует ре-анкоринга такого цикла.
- `changes` хранят намерение и исторические baselines, не кэш. Кроме artifacts есть физические `changes/<id>/deltas/<target>.md` и патчи: v1 **не переписывает дельты и диапазоны строк**. Если неархивированная change имеет дельту на перемещаемый или другой переписываемый путь, блокировать `move.active_change_conflict`; не разбирать это как свободный Markdown. Проверять фактическую target-mapping функцию `changes.py`, не угадывать target по basename. Архивные дельты не менять; если их ссылки требуют изменения — отказ как historical/unsupported, не переписывание истории молча.
- Generated Markdown-витрину (`derived_from`/generated) можно механически перенести, но не изменять содержательное поле/кодовый payload. Тест регенерации flow/interop после переноса обязан показать ту же семантику; unsupported target внутри payload — отдельная диагностика, не слепой replace.

### 4.4. Карта файлов (пути актуальны; номера строк — только evidence аудита)

| Файл | Действие / ответственность |
|---|---|
| `src/todoc/adapters/formats/markdown.py` | proven edit spans, без ломки Link/parse-cache контракта |
| `src/todoc/application/move.py` (новый) | план, read-set, пути, identity, apply и rollback |
| `src/todoc/application/move_rewrite.py` (новый) | чистые helpers ссылок/метаданных/записей, без записи |
| `src/todoc/application/staleness.py` | text-helper, overlay staleness; старые API совместимы |
| `src/todoc/application/write.py` | byte-preserving updated с тестами существующих callers |
| `src/todoc/application/validator.py`, `src/todoc/service.py` | overlay через **все** readers и сборки проекции |
| `src/todoc/application/history.py` | record_event, exists/tombstones, plan/revert event |
| `src/todoc/application/storage.py`, `src/todoc/adapters/history/store.py`, `src/todoc/adapters/history/journal.py` | атомарная публикация event через порт, совместимость readers |
| `src/todoc/cli.py`, `src/todoc/data/guidance/ru.json` | команда, hidden alias, conditional revert args, error envelope |
| `tests/unit/test_move.py`, `test_move_rewrite.py`, `test_history_move.py` (новые) | planner, rewriter, транзакции/revert |
| `tests/unit/test_markdown.py`, `test_validator.py`, `test_staleness.py`, `test_history.py`, `test_storage_contracts.py` | регрессии существующих контрактов |
| `tests/cli/test_cli_docs_move.py` (новый), существующие unified/output tests | CLI/guidance/discovery/readonly |
| README, корневой и пакетный SKILL, agent-contract, `docs/state/*` и demo-копии, HOME | команды, контракт и факт-счётчики |

## 5. Задачи

Каждая задача: написать перечисленные тесты → подтвердить осмысленный FAIL → минимальная реализация → PASS целевой группы → проверить diff. Это не разрешение оставлять общий набор красным до задачи 10. Коммиты по текущим правилам сессии; файловая карта выше обязательна. Новые unit fixtures держать в `tests/unit/conftest.py` или локальном модуле, а не импортировать `_kb` из соседнего тестового файла.

### Задача 1: доказанные span и сохранение байтов (BUG-070)

**Consumes:** `parse_markdown`, markdown-it tokens, существующий Link. **Produces:** `LinkEditSpan`/`editable_link_spans`, byte-preserving metadata-update helper из §3/§4.2.

- [x] Написать `test_span_excludes_code_and_html`, `test_reference_never_steals_inline_span`, `test_end_column_is_inclusive`, `test_repeated_href_and_image_link`, `test_uri_encoding_roundtrip`, `test_unsupported_span_is_explicit`. Проверять точные `[start,end)` offsets исходного текста, не только итоговый href.
- [x] Добавить `test_updated_preserves_bom_crlf_and_final_newline` для LF/CRLF/no-final-newline и существующих `docs edit/status/sync` callers. Неповреждаемые участки равны byte-for-byte.
- [x] Запустить `.venv/bin/python -m pytest tests/unit/test_markdown.py tests/unit/test_search_write.py -q`; подтвердить FAIL только новых assertions, затем реализовать helper и получить PASS старых и новых тестов. При изменении parse-cache payload поднять его версию и проверить инвалидирование старого payload.

### Задача 2: read-only planner, пути и идентичность (BUG-073)

**Consumes:** T1, `DatasetContext.read_index`, `source_fingerprint`, scanner helpers, `selection_key`. **Produces:** MoveFile/MovePlan, resolve_source/target, plan_move из §4.1; пока без apply.

- [x] Тесты `test_source_exactly_one_selector`, `test_keep_id_without_front_matter`, `test_semantic_id_stable`, `test_pin_type_and_target_type`, `test_target_folder_expansion`, `test_target_existing_and_dangling_symlink`, `test_symlink_parent_and_reserved_segment`, `test_absolute_drive_unc_dotdot_and_backslash`, `test_case_only_rejected_on_all_platforms`, `test_portable_target_names`.
- [x] `test_preview_no_index_cache_history_or_state_writes` на cold/stale/corrupt index и валидном корпусе: snapshot всех байтов DATA_ROOT и внешнего state до/после. Ошибки чтения — отказ, не пропуск возможных входящих ссылок.
- [x] `test_plan_hash_binds_corpus_rules_folder_config_date_and_options`: добавить новый inbound, изменить нетронутый md/тип/папку; hash меняется. Не зависит от формата вывода/порядка аргументов `--id` versus `--from`.
- [x] Реализовать planner по полному проверенному корпусу и live-конфигурации, UTF-8/read failures явные. Комбинации одинаковый путь/занятый target проверять в указанном порядке; expected code важнее текста исключения.
- [x] `.venv/bin/python -m pytest tests/unit/test_move.py -q` — PASS, включая общий cold-index путь.

### Задача 3: rewrite связей, записей, опор (BUG-072)

**Consumes:** T1/T2, текущий metadata adapter/resolver/record_ids. **Produces:** helpers в move_rewrite, `fragment_hash_text`, полные `MovePlan.files` с before/after.

- [x] `test_outgoing_incoming_self_and_assets` использует валидную секцию `## Суть`, реальный sibling, asset и record; проверяет не только строки, но множество разрешённых target+fragment до/после.
- [x] `test_wikilink_old_and_new_ambiguity`: при target `ideas/new2.md` создать занятой stem **`other/new2.md`**, а не `ideas/new.md`. Отдельно старые два `old.md`, `[[old.md#part|alias]]`, `related`, record-shaped target.
- [x] `test_covers_and_document_mirror`, `test_json_meta_dependency`, `test_record_paths_exact_only`, `test_baseline_artifact_key_collision_and_old_hash_kept`, `test_untouched_json_not_reformatted`.
- [x] `test_fragment_hash_text_matches_file_api` (whole/section/pointer; pointer на Markdown = unresolved), `test_move_never_launders_preexisting_stale`, `test_ack_shared_hash_not_globally_replaced`, `test_secondary_stale_reported_not_acked`, `test_dependency_cycle_refused`.
- [x] `test_active_delta_target_blocks_affected_move`, `test_generated_view_semantics_preserved`. Не обещать автоматического rewriting патчей active change.
- [x] После RED реализовать helpers §4.2–4.3, метаданные бампать **до** вычисления final hash. `.venv/bin/python -m pytest tests/unit/test_move_rewrite.py tests/unit/test_staleness.py tests/unit/test_search_write.py -q` — PASS.

### Задача 4: единый виртуальный reader и предвалидация

**Consumes:** T2/T3, `ScannedFile`, validator/service. **Produces:** keyword-only `overlay: dict[str, bytes] | None = None` и `deleted: set[str] | None = None` в `validate_dataset`, `DatasetContext.scan_and_validate`, `build_mentions`; `virtual_scan` возвращает `(folders, files)` с новыми hash/size/status.

- [x] Ввести единый read-helper: deleted запрещает чтение; overlay приоритетнее parse-cache/диска; для нетронутого файла verify hash как сейчас. Не писать overlay в постоянный cache.
- [x] Пробросить его не только в `_read_validation_text`, но в `_collect_record_ids`, `_check_source_anchors`, fallback `_check_link_targets`, `build_mentions`, staleness source/owner reads. Проверить JSON metadata/record parsing и all_paths. Disk-only skills/folder-config validators допустимы только потому, что v1 не изменяет `.config.json`/папки; перенос SKILL.md с vault-семантикой отклонить `move.source_unsupported`, пока нет виртуального skills-scan.
- [x] `test_overlay_equals_real_scan_validate_and_mentions` на временной копии, включая новые target/изменённые records, deleted source, warm poisoned cache и missing anchor. Сравнивать проекции/диагностики, а не только exit.
- [x] `test_baseline_error_blocks_even_if_unrelated`, `test_two_same_code_errors_cannot_hide_new_error`, `test_warning_only_baseline_allowed`, `test_unreadable_dependency_is_not_skipped`.
- [x] v1: если baseline имеет error — `move.baseline_invalid`; никаких множеств `(code,path)` и допущений «старый такой код уже был». После overlay любой error — `move.validation_failed`. Включить реальные диагностики и короткое guidance.
- [x] `.venv/bin/python -m pytest tests/unit/test_move.py tests/unit/test_validator.py tests/unit/test_staleness.py -q` — PASS.

### Задача 5: история с удалением и атомарным event (BUG-071)

**Consumes:** HistoryStore/record_write/legacy readers. **Produces:**

```python
record_event(root: Path, entries: list[dict[str, Any]], *, kind: str,
             change_id: str | None = None, backend: Any = None,
             store: HistoryStore | None = None, basis: str = "") -> str
# entries: path, before: bytes|None, after: bytes|None
# В журнале: path, before(snapshot|null), after(hash|null),
# before_exists: bool, after_exists: bool, ranges, git_head.
```

- [x] `test_event_distinguishes_absent_empty_deleted`, `test_move_forces_before_snapshots_even_with_git`, `test_multi_path_one_event`, `test_record_write_legacy_compatibility`.
- [x] Для move/revert before-снимок **всегда** сохраняется для существовавшего файла; не использовать GitBackend.needs_snapshot для обязательного восстановления. `before=None` legacy означает «нет снимка», не «создан». `record_write` сохраняет сигнатуру/смысл, новые поля аддитивны в schema_version 1.
- [x] Обновить `content_at`, `before_content`, show/diff/blame/log/timeline/gc/observe paths под tombstone. Снимки удалённых файлов достижимы для GC как раньше через before. `test_history_at_before_after_move_and_revert`, legacy Git/embedded события, отсутствующий/битый snapshot — fail closed, не удаление файла по догадке.
- [x] `test_journal_publish_failure_leaves_no_committed_event`: исключения до/во время публикации, в т.ч. после подготовки snapshot. FileHistoryStore публикует полную новую строку атомарно, сохраняя исходные байты префикса журнала; logical append-only, не пересериализация прошлых событий. Порт `append_event` должен иметь явно документированную failure-гарантию; не опираться на обычный append+flush/fsync, который уже мог дописать строку перед исключением.
- [x] `record_event` берёт history transaction ровно один раз; locked helper для apply не захватывает directory lock повторно. Подготовленные, но неиспользованные content-addressed snapshots допустимы как orphan objects; факт перечислить, журнал не переписывать ради «удаления следов».
- [x] `.venv/bin/python -m pytest tests/unit/test_history.py tests/unit/test_history_move.py tests/unit/test_storage_contracts.py -q` — PASS. Новый application-код использует порт, не `journal.jsonl` напрямую.

### Задача 6: apply, граница коммита и rollback

**Consumes:** T2–T5, atomic_write(exclusive=True), file_hash, directory_lock. **Produces:** apply_move из §4.1.

- [x] Под cooperating move-lock `.todoc/locks/move.lock`: проверить live dataset/config, strict corpus fingerprint, hash самого плана, обязательный if-plan-hash, optional if-hash; заново lstat/read all affected paths и проверить before bytes. Зафиксировать canonical order lock acquisition: move-lock → history transaction; не наоборот.
- [x] До записи отклонить plan с error-диагностикой **в application API**, а не только CLI. Дату планирования сравнить с текущей UTC: сменился день — новый preview. Проверить, что target отсутствует; создание исключительно `atomic_write(..., exclusive=True)`.
- [x] Записать updates/target, затем удалить source; при исключении до event восстановить backup bytes и удалить только созданные этой попыткой файлы. Если их успел изменить внешний писатель — не затирать, вернуть rollback_failed с перечнем путей для ручного восстановления. Никаких гарантий против hostile TOCTOU поверх этих portable checks.
- [x] После успешной записи источников опубликовать **одно** событие; это commit point. Затем invalidate parse-cache затронутых путей и `ctx.rebuild_index(observe=False)`: не создавать лишние external.change события вызовом `ensure_index(observe=True)`.
- [x] Тесты `test_apply_rechecks_same_plan_object`, `test_added_inbound_or_rule_invalidates_old_plan`, `test_target_created_concurrently_preserved`, `test_application_rejects_invalid_plan`, `test_new_operation_id_after_revert`, `test_no_extra_observed_events`.
- [x] Параметризованный `test_failure_matrix`: target create, каждый dependent write, source unlink, snapshot, event publish, cache invalidate, index publish; byte-manifest источников, число journal events и result flags соответствуют таблице ниже. Отдельно rollback failure.
- [x] `.venv/bin/python -m pytest tests/unit/test_move.py tests/unit/test_history_move.py -q` — PASS.

| Состояние | Источники / история | Ответ |
|---|---|---|
| Ошибка до записи | без изменений | applied=false, committed=false, код причины |
| Исключение записи/snapshot/event до commit, rollback успешен | before bytes восстановлены; committed-event нет | applied=false, committed=false; move.write_failed/history_failed, exit 6 |
| Rollback не завершился | точный список неопределённых путей | applied=null, committed=false, recovery_required=true; move.rollback_failed, exit 6 |
| Commit event опубликован, cache/index не обновился | after bytes и событие сохранены | applied=true, committed=true, index_published=false; move.index_failed, exit 6; index rebuild/revert в next_actions |
| Успех | after bytes, одно событие, новый индекс | applied=true, committed=true, index_published=true, exit 0 |

### Задача 7: безопасный revert всей операции

**Consumes:** T5/T6, trusted snapshot objects, live source checks. **Produces:**

```python
plan_revert_event(ctx: DatasetContext, change_id: str) -> dict[str, Any]
# actions(path, expected_current_hash|null, before_hash|null), plan_hash, diagnostics
revert_event(ctx: DatasetContext, change_id: str, *, if_plan_hash: str) -> dict[str, Any]
```

- [x] Найти **одно** завершённое move-событие по operation-specific change_id. Отсутствие/несколько совпадений/legacy без exists-флагов → явный отказ, не разворот произвольной истории одной пачкой.
- [x] Сравнить текущее состояние **каждого** пути с event.after/after_exists: source по-прежнему отсутствует, target/dependents совпадают. Позднейшая правка любого пути или повторный revert — conflict, без force в v1.
- [x] Preview revert read-only и возвращает plan_hash, связанный с текущим полным source_fingerprint и исходным rev события. До записи валидирует обратный overlay тем же virtual reader: новая входящая ссылка на target, созданная после move, не должна сломаться незаметно. Apply требует hash, перечитывает состояния/журнал под теми же locks, повторяет virtual validation и проверяет containment всех путей из события. Восстановить точные before bytes, включая CRLF/BOM/no-final-newline и пустой файл. Источник, занятый новой записью, не затирать.
- [x] Записать одно `doc.move.revert` событие со своей идентичностью и `reverts_rev`, сохранив исходное. Та же failure-matrix и index rebuild без observation.
- [x] `test_revert_exact_bytes_and_absence`, `test_revert_refuses_later_edit_and_recreated_source`, `test_repeated_revert_conflicts`, `test_malicious_history_path_symlink_and_missing_snapshot`, `test_revert_stale_plan`, `test_revert_new_inbound_validation_refuses`, `test_legacy_revert_path_unchanged`; `.venv/bin/python -m pytest tests/unit/test_history_move.py tests/unit/test_history.py -q` — PASS.

### Задача 8: CLI и guidance

**Consumes:** T2–T7, UnifiedCommand/Envelope. **Produces:**

```text
todoc docs move --root R (--id ID | --from PATH) --to TARGET
  [--preview|--apply] [--if-plan-hash H] [--if-hash H]
  [--keep-id] [--pin-type] [--verbose] [--output json|table|markdown]
todoc docs mv ...                         # hidden alias
# Legacy сохранён:
todoc revert REV --path P [--expected-hash H] [--preview|--apply]
# Новый safe workflow:
todoc revert --change ID [--preview|--apply] [--if-plan-hash H]
```

- [x] Сделать REV optional на уровне Click, затем проверять комбинации: path требует REV, change запрещает REV/path/expected-hash, ровно один path/change. Нет bypass `--apply` без hash для нового revert; legacy поведение не ужесточать незаметно.
- [x] Preview result: preview=true, applied=false, plan_hash, source/target, old/new_id, old/new_type, rewrites, bounded files-summary и stale-summary. Полные bytes в envelope не выводить. Apply `preview=false` (не наследовать true!), flags из failure-matrix, rev/change_id. `next_actions` у preview — исполнимый argv apply с hash; после apply — read/validate/revert-preview.
- [x] Зарегистрировать hidden alias тем же callback, не вызывать декорированный Click Command как обычную функцию. Discovery не показывает mv, но command-inventory и контрактные тесты учитывают alias.
- [x] Покрыть json/table/markdown успех/ошибку/partial, inheritance global output/no-input, multi-root refusal, missing selector/hash, обе preview/apply, diagnostics/guidance, прогон той же argv-цепочки next_actions. Failures из приложения не теряют applied/committed flags в generic error boundary.
- [x] Guidance для всех кодов §7, включая `move.rollback_failed`; существующие общие usage/access/conflict коды переиспользовать только по смыслу. `.venv/bin/python -m pytest tests/cli/test_cli_docs_move.py tests/cli/test_unified_e2e.py -q` — PASS, затем весь существующий output-contract набор.

### Задача 9: документация и полевой сценарий (BUG-074)

- [x] Обновить README/SKILL и пакетный dispatcher `src/todoc/data/agent-skill/todoc/SKILL.md`, agent-contract, справку CLI и фактические state-документы. Копии `demo/references/state/*` синхронизировать штатным генератором, не править derived-витрины вручную. Счётчики от command_inventory/types/docs list, не фиксированное «+1 команда» с alias.
- [x] Исправления других идей не выдавать за их реализацию. У `docs-move` оставить planned до разрешения закрыть; у смежных планов — статусы без изменений. Держать явный gate T17 multi-project (см. §9).
- [x] Написать integration test `test_demo_copy_move_apply_revert` в новом `tests/cli/test_cli_docs_move.py`: `tempfile.TemporaryDirectory`/pytest tmp_path, `shutil.copytree(demo, copy, ignore=.todoc/index,cache,history)`, никаких `rm -rf` и shell-placeholder `<hash>`.
- [x] На копии создать note `inbox/move-probe.md`, прочитать его ID; добавить в корневой HOME **`[probe](inbox/move-probe.md)`** (не `../inbox`), `sync --apply --root COPY HOME.md`. Снять byte-manifest исходных пользовательских файлов **после** этой подготовки. Запустить baseline validate/links/stale.
- [x] Preview→извлечь hash из JSON→apply→read/tree/links/validate→revert-preview→извлечь новый hash→revert-apply→byte-manifest == baseline. Историю/производный индекс исключить из byte-равенства, но проверить ровно move+revert events. Новый target отсутствует. Второй сценарий — переименование legacy кириллицы в латиницу с реальными inbound/wikilinks/record mirror.
- [x] Для `docs links` проверять `data.meta.total == 0`, `truncated == false`, `next_cursor is None`, а не один exit=0: команда может успешно вернуть непустой список проблем. Для validate/check-config — ok и diagnostics, для linkcheck — текст broken 0 (его exit всегда 0).

### Задача 10: полные гейты и передача на исполнение/закрытие

- [x] Полный набор и покрытие:

```bash
.venv/bin/python -m coverage run --branch --source=src/todoc -m pytest -q
.venv/bin/python -m coverage report -m --fail-under=100
.venv/bin/todoc validate --root demo --all
.venv/bin/todoc check-config --root demo
.venv/bin/todoc docs links --root demo --limit 1000
.venv/bin/python tools/linkcheck.py demo
.venv/bin/todoc stale --root demo
```

- [x] Проверить новые unit/CLI файлы действительно собраны pytest; весь `src/todoc` TOTAL 100%, не только новый файл. Снять сводку реальных leaf-команд/типов/документов.
- [x] Сравнить stale с baseline по owner+dependency, не только счётчик. Старый drift не исчез без review; в контролируемом probe без вторичных зависимостей новых stale нет. Для произвольного корпуса новые вторичные stale перечислены, не замаскированы ack.
- [x] `git diff --check`, проверить только ожидаемые исходники/документы, нет temp datasets/venv/cache в diff. Для Markdown/JSON/CSV изменений датасета — немедленный sync и обратное read.
- [x] В §8 записать результаты и оставшиеся ограничения. Закрывать план/идею/репорты и задачные records только после явного подтверждения; не считать «план подготовлен» реализацией move.

## 6. Definition of Done

- [x] T1–T10 выполнены, контракт §1 доказан именованными тестами, никаких обещаний вне v1.
- [x] Нет редактирования неподтверждённых span, мимо code, непереносимых путей и target overwrite.
- [x] Preview чистый; read-set/CAS/keep-id/pin-type/metadata/record/derived_from поведение проверено.
- [x] Нет старого drift laundering; нет ложного общего требования «stale всегда 0».
- [x] History exists/tombstones/forced snapshots/legacy readers и safe revert покрыты.
- [x] Ошибки precommit/committed-index-failed/rollback-failed различимы машинно; не обещаем crash-atomic multi-file writes.
- [x] Общие pytest и 100% coverage, данные и ссылки зелёные; smoke на копии возвращает байты.
- [x] T17 multi-project и folderize не используют одиночный apply как готовую пакетную транзакцию.
- [x] Документация, реальные счётчики и результаты обновлены; терминальные статусы подтверждены пользователем.


## 7. Риски и митигации

Общие exit: usage=2, validation=3, access=4, conflict=5, incomplete=6; успех=0. Где движок уже имеет подходящий общий код, не создавать несовместимый дубль. Все отказы до commit имеют applied=false; после commit — как в failure-matrix.

| Группа кодов | Exit / смысл |
|---|---|
| `move.source_not_found`, `move.source_ambiguous`, `move.source_not_markdown`, `move.source_unreadable`, `move.source_unsupported` | 3 / источник не удовлетворяет контракту |
| `move.target_outside_root`, `move.source_symlink`, `move.target_symlink`, `move.target_reserved`, `move.path_invalid` | 4 / недопустимая область или форма пути |
| `move.target_dir_missing`, `move.extension_mismatch`, `move.case_only_rename`, `move.target_not_file` | 3 / недопустимая цель |
| `move.same_path` | 2 / no-op usage |
| `move.target_exists`, `move.plan_stale`, `move.hash_mismatch`, `move.active_change_conflict`, `move.metadata_collision` | 5 / конфликт состояния |
| `move.wikilink_ambiguous`, `move.link_unsupported`, `move.baseline_invalid`, `move.validation_failed`, `move.dependency_cycle` | 3 / нельзя доказать безопасный перенос |
| `move.pin_type_unavailable`, `move.preexisting_stale`, `move.ack_invalidated` | warning, сами по себе не error |
| `move.write_failed`, `move.history_failed`, `move.rollback_failed`, `move.index_failed` | 6 / состояние по failure-matrix |
| `move.revert_not_found`, `move.revert_unsupported` | 6 / нет достаточной истории |
| `move.revert_conflict`, `move.revert_ambiguous` | 5 / post-state/уникальность нарушены |

| Остаточный риск | Ограничение / митигация |
|---|---|
| Внешний редактор во время apply | cooperative lock + повторные checks; не обещать общую транзакцию всех писателей, recovery-required при чужих байтах |
| kill -9/питание во время нескольких replace | вне гарантии v1; durable recovery journal — отдельное расширение, не «уже атомарно» |
| Большой корпус | один verified snapshot, чистые helpers; полный scan допустим v1, SQLite пока отсутствует |
| Неподдержанный Markdown/active delta | явный отказ до записи, можно безопасно вручную подготовить источник и снова preview |
| Повторное применение старых планов миграции | T17 preflight, проектная миграция не выпускается без отдельного batch-контракта |

## 8. Прогресс и отклонения

### Итог исполнения v1 — 2026-11-28

- Задачи 1–9 выполнены последовательно, после реализации каждой запускались её тесты. По прямой инструкции пользователя RED-прогоны до реализации задач не выполнялись (приоритет над прежними чекбоксами TDD); исправления после целевого прогона перепроверялись. Задача 10: полный финальный набор **1923 теста PASS**, `coverage run --branch --source=src/todoc -m pytest -q` + `coverage report -m --fail-under=100`: **9627 statements, 3654 branches, 0 misses, 0 partial, TOTAL 100%**.
- Фактический inventory: **69 листовых spellings (68 публичных + hidden `docs mv`)**; типы: 25 dir / 31 doc / 25 entity / 18 relation. Демо: 529 документов / 205 записей. Validate: 0 диагностик; check-config: 0 issues/warnings. `docs links`: 926 ссылок, total=0, complete=true, truncated=false, cursor=null; linkcheck: 913 относительных, broken=0.
- Stale сравнивается по owner+dependency+expected, не по счётчику: сохранены те же две опоры (interop plan → ideas/interop-exports; superseded metadata-overview plan → BUG-022). ACK не добавлялись. Отдельная регрессия `test_secondary_stale_reported_not_acked` доказывает, что новый stale не скрывается за прежним stale другого dependency у того же владельца.
- Именованные доказательства: `test_verified_spans`, `test_uri_encoding_roundtrip`, `test_plan_hash_binds_full_corpus_rules_and_date`, `test_preview_publishes_nothing_with_index_variants`, `test_active_delta_target_blocks_affected_move`, `test_failure_matrix`, `test_transaction_recovery_guards`, `test_move_revert_exact_bytes_and_no_overwrite`, `test_revert_event_history_guards`, `test_demo_copy_move_apply_revert`, `test_generated_view_move_preserves_regenerated_payload`. Проверены byte-manifest round trip на копии demo, legacy кириллица → латиница, зеркало и wikilinks, output/alias/next_actions и committed failure envelopes.
- На финальном review устранены: code+owner-only сравнение stale (теряло второй dependency), target-mapping дельт через `parse_delta`/`contained_delta_target` (нормализуется `..`), разделение URI fragment до unquote (`#` в имени), проверка digest снимка перед revert. Версия parser/cache поднята; fingerprint включает версию, чтобы старые mentions не переживали смену decoder. Общий storage-port architecture gate сохранён.
- Отклонения именования диагностик: лексические пути вне root отклоняются общим `move.path_invalid`; symlink любой цепочки — `move.target_symlink`, в том числе при чтении источника. Отдельные неиспользуемые `target_outside_root`/`source_symlink`/`target_not_file` не вводились; цель-каталог раскрывается по имени источника. Блокируются как активные, так и исторические затронутые дельты — консервативнее минимального запрета active.
- Ограничения v1 сохранены: один Markdown, существующий parent, error-free baseline, отказ затронутых неподтверждённых span/SKILL.md/дельт; без batch/folderize/нового resolver/SQLite/ignore. Возможен rollback при обрабатываемой ошибке, но **не crash-atomic** и не защита от произвольного внешнего редактора. Orphan snapshots до публикации допустимы. Сбой индекса после commit означает сохранённые источники; `recovery_required` требует ручной проверки перечисленных путей.
- На момент технической приёмки коммитов/пушей/смены ветки не было; затем пользователь явно поручил commit/push/merge. Рабочая ветка `arena/618c7963-todoc`. Подробные локальные логи — `tmp_kb_skills_audit/move-execution/` (игнорируются Git); счётчики и результаты также записаны здесь для постоянного контекста.
- На момент технической передачи идея planned, план active, BUG-070–074 open были оставлены до отдельного подтверждения. **Подтверждение получено 2026-11-28:** пользователь поручил закрыть план, закоммитить, отправить и слить в основную ветку. План и идея → done, BUG-070–074 → fixed. T17 multi-project остаётся gated отдельной batch-транзакцией, одиночный apply не выдан за пакетную миграцию.

### Хронология аудита до исполнения

- 2026-11-28: исходный план создан; код не начинался. Идея уже planned, HOME уже содержит план. Эти статусы не доказывают реализацию.
- 2026-11-28, аудит перед исполнением на базе `8b5d281581bbfdda22c745d12a945754faea4716`, ветка `arena/618c7963-todoc`: модуль move и CLI-команда отсутствуют. Исходный план **не был готов** для буквального исполнения. Пересмотрена спецификация/порядок задач; implementation-checkboxes оставлены пустыми.
- [BUG-070](../bugs/bug-070-move-link-spans.md): воспроизведены off-by-one и попадание display-span в inline-code. Для `` `[example](old.md)` [real](old.md) `` текущий Link(real) имеет column=2; срез исходного алгоритма возвращает `[example](old.md`.
- [BUG-071](../bugs/bug-071-move-history-transaction-contract.md): before=None в Git-history не означает creation; after=b"" не означает deletion; исходный revert не имел CAS. Зафиксированы exists/tombstone, exact snapshots, commit point и safe revert. История исключена из перечня удаляемых кэшей.
- [BUG-072](../bugs/bug-072-move-provenance-reanchoring.md): `fragment_hash(root, dep)` читает диск, не новый текст; безусловный reanchor маскирует preexisting drift. Введён text-helper и консервативная ack-политика; исторические baseline hashes сохраняются.
- [BUG-073](../bugs/bug-073-move-review-readset.md): исходный hash не связывал полный корпус/правила; `(code,path)` теряет identity и кратность ошибок. **Изменение скоупа:** безопасный v1 требует error-free baseline; допуск предсуществующих errors отложен до отдельного semantic diagnostic-diff. Это явное ограничение, а не уже выполненное требование исходной идеи.
- [BUG-074](../bugs/bug-074-move-plan-execution-fixtures.md): исправлены неверная collision-fixture (`new` вместо `new2`), несуществующий `#суть`, ссылка `../inbox` из корневого HOME, shell-placeholder hash и отсутствие hash-guard revert. В смежном T17 поставлен gate пакетной миграции.
- Полнота обзора: `docs list --type 'idea|plan' --origin document --limit 1000` вернул **39** документов (25 идей, 14 планов), complete=true, truncated=false, next_cursor=null. Проведён сквозной обзор скоупов/швов; это не означает аудит каждой строки будущего кода всех идей. Релевантные спеки и код move/history/validator/parser/staleness/storage/changes проверены углублённо.
- Baseline до документных правок: полный `.venv/bin/python -m pytest -q` — exit 0; validate — 0 диагностик; docs links — total=0, total_links=868, без усечения; tools/linkcheck demo — 0 битых; `stale=2` (interop-exports plan и superseded metadata-overview plan). Покрытие при этом аудите не измерялось: `src/` не менялся, полный coverage обязателен при реализации.
- Финальная проверка аудита 2026-11-28: полный `.venv/bin/python -m pytest -q` — exit 0; validate — 529 документов, 0 диагностик; check-config — 0 issues/warnings; docs links — total=0, complete=true, truncated=false; tools/linkcheck demo — 913 проверенных относительных ссылок, broken=0; stale=2, состав прежний; `git diff --check` — PASS. Это проверки текущего кода/документов, не тесты ещё не реализованной команды move.
- Передача: план подготовлен как **ready for implementation review**. Реализация не запускалась; пользователь подтверждает контракт v1 и даёт отдельную команду на исполнение. Репорты open до реализации/проверки, не закрыты одной правкой плана.

## 9. Матрица остальных идей и планов

Источник статусов — полный CLI inventory на дату аудита. Будущая возможность не является зависимостью реализации, если ниже явно не сказано обратное. Матрица предотвращает «реализуем всё заодно».

### 9.1. Все 25 идей

| Идея | Отношение к move / решение |
|---|---|
| [docs-move](../ideas/docs-move.md) — planned | основной scope; ограничения v1 из §2/§8 теперь явные |
| [entity-to-folder](../ideas/entity-to-folder.md) — captured | будущий потребитель чистых rewrite helpers; создание папки/config + move требуют общей будущей transaction, не готового apply |
| [multi-project-workspace](../ideas/multi-project-workspace.md) — planned | T17 зависит от move; project-local resolver/видимость пока не существуют; обход integrity всегда полный |
| [sqlite-storage-drivers](../ideas/sqlite-storage-drivers.md) — captured | пользоваться IndexStore/ParseCache/HistoryStore, не писать приложение под JSONL; драйвер не prerequisite |
| [todocignore](../ideas/todocignore.md) — captured | будущий общий matcher; v1 hard-exclude. Не вводить отдельную move-only интерпретацию ignore |
| [type-naming-and-state-dir](../ideas/type-naming-and-state-dir.md) — captured | потребитель будущего batch move references/state; v1 не переименовывает типы и не переносит каталог одной командой |
| [archive-dir-type](../ideas/archive-dir-type.md) — captured | архив не меняет doc_type; integrity видит архивные backlinks, исторические дельты не модифицируются молча |
| [toggleable-rules](../ideas/toggleable-rules.md) — captured | enabled-фильтры не могут скрывать ссылки от move; enabled/status не меняем |
| [typed-tree-projection](../ideas/typed-tree-projection.md) — captured | read-only потребитель обновлённого индекса; новый tree не нужен для v1 |
| [unified-tags-and-tag-graph](../ideas/unified-tags-and-tag-graph.md) — captured | не менять tags при смене папки; виртуальные tag-edges пересобираемы |
| [bitemporal-clocks](../ideas/bitemporal-clocks.md) — captured | valid/known/observed/superseded не переписывать; историю старых фактов не «освежать» |
| [action-logging](../ideas/action-logging.md) — captured | операционные логи вне данных; не заменяют journal/CAS и не реализуются здесь |
| [context-marking-and-session-mining](../ideas/context-marking-and-session-mining.md) — captured | процессный скил, не runtime-предпосылка move; внешний контекст не переименовываем |
| [agent-flows](../ideas/agent-flows.md) — captured | будущий пользователь команды, не новый исполняемый слой в этом плане |
| [dev-lifecycle-flow](../ideas/dev-lifecycle-flow.md) — captured | нуждается в folderize/move; аудит→исполнение остаются разными фазами |
| [wave-planning-cli-helpers](../ideas/wave-planning-cli-helpers.md) — planned | covers и derived_from должны пережить path-ID change; общий bind/reanchor/portfolio не входит в v1 |
| [cli-model-guidance-and-hint-catalog](../ideas/cli-model-guidance-and-hint-catalog.md) — planned | действующий P15/каталог переиспользуется, будущие guided-режимы не prerequisite |
| [direct-edit-and-git-sync](../ideas/direct-edit-and-git-sync.md) — done | произвольные правки + sync; сам move уже финализирует свои файлы, второй sync ему не нужен |
| [unified-cli-output](../ideas/unified-cli-output.md) — done | envelope v2, output inheritance, bounded summary, truth about partial apply |
| [entity-catalog](../ideas/entity-catalog.md) — done | record IDs не равны путям; source mirrors/anchor/mentions обновляются, relations IDs сохраняются |
| [folder-config](../ideas/folder-config.md) — done | .config участвует в fingerprint/поисковой семантике, но не переписывается одиночным move |
| [agent-state](../ideas/agent-state.md) — done | внешний state не truth/read-set move, не хранить там незавершённую транзакцию |
| [skills-engine](../ideas/skills-engine.md) — done | SKILL.md имеет отдельную vault-семантику; отказ v1 до виртуального skills-scan, не обещать поддержку автоматически |
| [documentation-system](../ideas/documentation-system.md) — done | active changes/deltas и document mirrors требуют явного preflight; обновить фактическую документацию после реализации |
| [interop-exports](../ideas/interop-exports.md) — done | generated payload не править regex; проверить регенерацию/derived_from после переноса |

### 9.2. Остальные 13 планов и документация

| План / группа | Совместимость / порядок |
|---|---|
| [multi-project-workspace](multi-project-workspace.md), active | фазы проекта 1–3 независимы; T17 только после move и отдельного batch-контракта; пересчитать ссылки общим состоянием, не набором независимых preview |
| [bmad-wave-planning-skills](bmad-wave-planning-skills.md), active | общие write-hotspots: cli.py, staleness.py, guidance, metadata/covers, SKILL; последовательно интегрировать контракт, не одновременно править одинаковые функции |
| [open-bug-backlog-closure](open-bug-backlog-closure.md), active | BUG-011/028/030–034 остаются актуальными границами. Fixed containment/create-only/read contracts не ослаблять. Новые BUG-070–074 — отдельные дефекты move-плана |
| [direct-edit-and-sync](direct-edit-and-sync.md), done | переиспользовать финализацию/даты, не вводить обязательный docs edit для подготовки данных |
| [entity-catalog-implementation](entity-catalog-implementation.md), done | mentions, record targets и source_anchor — regression suite |
| [folder-config-implementation](folder-config-implementation.md), done | parent configs в source_fingerprint, не новый schema/validator |
| [interop-exports-dmn-asl-rasa](interop-exports-dmn-asl-rasa.md), done | сохранить действующий export/derived контракт; preexisting stale не скрывать |
| [skills-vault-implementation](skills-vault-implementation.md), done | сохранить live skills-validation; виртуальный перенос скилов требует отдельного расширения |
| [agent-state plan](агентский-стейт--state-json-в-движке--v1---текущий-проект.md), done | read-only preview не должен писать внешний стейт |
| [softdoc plan](документирование-софта--типовой-профиль---типы--стартовые-промпты--скилы.md), done | change artifacts/baseline/deltas не путать с кэшем |
| [lifecycle skills plan](скилы-взаимодействия--захват--план--исполнение--переходы--жизненный-цикл.md), done | никакого самовольного done/fixed во время аудита |
| [doc-tags plan](теги-документов-как-aliases-поиска--tags-updated-related-в-front-matter.md), done | tags сохранять; updated без нормализации остального текста |
| [metadata-overview-and-harness-efficiency](metadata-overview-and-harness-efficiency.md), superseded | только исторический контекст; текущие CLI/schema/storage contracts важнее прежних примеров |

Проверенная документационная опора: AGENTS.md, SKILL.md, notes/agent-contract, plan/constitution, весь inventory `references/state/01–19` с приоритетом 02/03/05/06/08/09/10/12/17/19; корневые README/pyproject и текущие src/tests. Документы AS-IS не изменяют требования автоматически: при расхождении в реализации фиксировать evidence и выбирать явно описанный в этом плане контракт, не старый номер строки.
