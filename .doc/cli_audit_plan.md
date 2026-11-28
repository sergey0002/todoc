---
title: "План по аудиту CLI todoc: проверенный контракт, безопасность и порядок работ"
date: 2026-11-28
status: "audited-draft: готов к реализации после решений §7"
scope: "src/todoc, tests, docs/state, demo/plan, demo/ideas; срез 5e86eb7 + рабочее дерево"
sources:
  - .doc/cli_audit.md
  - docs/plan/todoc-master-refactoring-plan.md
  - demo/notes/unified-cli-release.md
  - demo/notes/agent-contract.md
  - demo/ideas/cli-model-guidance-and-hint-catalog.md
  - demo/plan/bmad-wave-planning-skills.md
  - docs/state/cli.md
  - .doc/codexaudit/08-remediation.md
---

# План по аудиту CLI todoc

> **Статус: проект плана, прошедший финальный аудит. Реализация не начата и этим
> документом не разрешена.** Это не второй бэклог и не замена мастер-плана.
> Порядок этапов задаёт [мастер-план](../docs/plan/todoc-master-refactoring-plan.md)
> (Э0–Э4), детальный контракт —
> [unified-план](https://github.com/sergey0002/todoc/blob/2c0085a0440f06148e9edc574e274c686e5b0259/demo/plan/unified-cli-output-implementation.md) (З0-S, З1–З9),
> а [аудит](cli_audit.md) — карту находок. Этот документ — **проверенный слой**:
> что подтверждается кодом, где формулировки аудита нужно поправить, в каком
> порядке вносить правки и какими тестами доказывать каждую.

## 0. Финальный аудит плана

### 0.1. Вердикт

План технически состоятелен: все F-01…F-26 подтверждены чтением кода, этапы
соответствуют мастер-плану, гейты измеримы. Финальный аудит нашёл **шесть
пробелов**, которые закрыты в этой редакции:

1. **BUG-033 сформулирован неточно.** Продакшн-путь `revert` пишет байты через
   `atomic_write` и **сохраняет CRLF**; ломается тест, который пишет через
   `Path.write_text` на Windows. Нельзя «чинить» `atomic_write` повторно — это
   создаст двойное преобразование. Исправлять нужно тест и пути, которые
   пересобирают текст (`apply_edit_ops`, `apply_ops`, `docs status`,
   `records status`, `plan_ack`).
2. **`change apply` не является all-or-nothing.** Текущий docstring обещает
   больше, чем код: файлы пишутся до истории, откат неполный, отчёт может быть
   `ok: true` при `applied: false`. План переводит это в честный
   `planned|applied|partial|failed`.
3. **Не покрыты ошибки разбора и чтения.** `docs read` игнорирует ошибки
   `parse_json`/`parse_csv`, многие чтения не ловят `UnicodeDecodeError`, а
   `main` не является границей ошибок. Это шире CA-001/CA-002; добавлены
   F-27…F-32.
4. **Не покрыт traversal через `change_id`, `--vault`, `--into` и
   `derived_from`.** Добавлены F-28…F-30.
5. **Публикация индекса имеет гонку staging и рассинхрон `CURRENT.json`.**
   F-31 уточняет исправление: поколения + атомарный указатель, а не два
   rename.
6. **Baseline и CI описаны историческими числами.** В этой редакции —
   фактический прогон: 1279 passed, 21 skipped; coverage локально не измерен;
   `linkcheck` в рабочем дереве даёт 4 битые ссылки в untracked `.doc`;
   CI проверяет только Ubuntu 3.11/3.12.

### 0.2. Фактический baseline (2026-11-28)

| Параметр | Факт | Следствие |
|---|---|---|
| Git | `5e86eb7`, 62 изменённых/untracked пути | Рабочее дерево грязное; backup обязателен |
| Python | 3.14.4 (system), pytest 9.2.0 | CI targets 3.11/3.12; 3.14 — не доказательство CI |
| `.venv` | есть, но без `pytest`/`click` | Для гейтов ставить `[dev]` в изолированном окружении |
| `pytest` | **1279 passed, 21 skipped, 84.09 s** | Это baseline текущего дерева, не master |
| coverage | `No module named coverage` | Гейт 100% не измерен; установить `coverage` |
| `validate` | на копии `demo` — `ok: true`, 0 диагностик | Источник демо чист; копия в `/tmp` |
| `linkcheck` | 1224 ссылки, **4 битые** в `.doc/codexaudit` | `.doc` untracked; CI без него не увидит |
| Click | **63 листа**, включая `docs flow render/walk` | Тест `_leaf_commands` видит только 2 уровня (CA-007) |
| CI | Ubuntu, Python 3.11/3.12, pytest + coverage 100% + linkcheck + validate | Windows-гейта нет |

**Вывод:** baseline зелёный по тестам, но не по coverage/linkcheck в рабочем
дереве. План не имеет права объявлять «всё зелено» до установки `coverage`,
решения по `.doc` и отдельного Windows-прогона.

### 0.3. Что изменено в плане после финального аудита

- Добавлены F-27…F-32 и их приёмка.
- Исправлена трактовка BUG-033 (§2.12).
- Уточнён `change apply` и добавлен `change archive` (§2.9, F-28).
- Добавлены work packages, матрица мутаций и точные файлы тестов (§4).
- Добавлены baseline, CI-ограничения и readiness checklist (§0.2, §11).
- Решения §7 переведены в формат «рекомендация + блокирует ли этап».
- Capability-путь зафиксирован как `src/todoc/output/capabilities.py`
  (канон unified), а не два разных пути.

### 0.4. Готовность к реализации

| Готово | Не готово / блокирует |
|---|---|
| Все F-находки проверены по коду | Backup рабочего дерева (W0.1) |
| Этапы и зависимости определены | Решения D1–D5, D10–D14 (§7) |
| Файлы, тесты и гейты перечислены | `coverage` не установлен; Windows CI отсутствует |
| Baseline тестов снят | Судьба `.doc` в linkcheck не решена |
| Матрица мутаций и миграция описаны | Первый PR ещё не начат |

**Рекомендуемый первый PR:** W1.1 + W1.2 + W1.6 (PathPolicy, atomic create,
error boundary) + тесты. Он не меняет публичный контракт, закрывает critical
риски и не конфликтует с остальными этапами.

---

## 1. Проверка аудита по коду

### 1.1. Метод

Проверялись не утверждения аудита, а фактическое поведение:

- `src/todoc/cli.py` — объявления Click, обработчики, `_emit_*`, `main`;
- `src/todoc/output/envelope.py` — конверт, форматы, запись в файл;
- `src/todoc/service.py`, `application/{registry,validator,write,changes,history,temporal,staleness}.py`;
- `adapters/{filesystem/scanner,history/journal}.py`;
- `docs/state/cli.md`, `demo/notes/agent-contract.md`;
- `tests/cli/test_cli_contract.py`, `tests/unit/test_history.py`;
- существующие BUG/CA-отчёты.

Дополнительно снят baseline: полный `pytest`, `validate` на копии `demo`,
`linkcheck`, рекурсивный обход Click. Результаты — §0.2.

### 1.2. Сводная таблица

| ID | Приоритет | Вердикт | Ключевое доказательство | Что делать по плану |
|---|---|---|---|---|
| F-01 | P0 | Подтверждено | `cli.py:155,180,190,232…`; `_group_output` только в `_emit_error` (`cli.py:2380`) | Единый контекст вызова, листовой `--output` без дефолта, разрешение по источнику параметра |
| F-02 | P0 | Подтверждено, дизайн уточнён | Общие опции повторяются на 63 листьях; реестра нет | Метаданные возможностей + контрактный тест с Click; **не** второй регистратор команд |
| F-03 | P0 | Подтверждено, рекомендация исправлена | `--if-hash` скалярный в `docs edit`/`fix` (`cli.py:1681,2270`) и `PATH=HASH` в `change apply` (`cli.py:1021`); `--expected-hash` в `stale`/`revert`/`undo-relation` | Два разных контракта: скалярный CAS и набор предусловий; не объединять по имени |
| F-04 | P0 | Подтверждено, усилено | `--preview` принимается, но **не читается** (`docs_edit`, `records_create`, `fix`); работает только `--apply`; оба флага не конфликтуют | Реальный `Plan → Apply`; `--preview` + `--apply` — ошибка; `--dry-run` — только где эффект тот же |
| F-05 | P0 | Подтверждено, уточнено | `--type` — 3 namespace; `--tag` — doc/history; `--section` — md/flow; `--path` — файл/цель; `--all` у `validate` — **мёртвый флаг** | Разводить только реальные коллизии; `--all` у `validate` — deprecated no-op или реализовать; `skills tree --all` → `--include-muted` |
| F-06 | P1 | Подтверждено | `docs search`, `records list`, `records query`, `docs read --where`; `records list` фильтрует `until/relation` **после** limit (`cli.py:1803-1812`) | Один типизированный query pipeline; фильтры до limit; QuerySpec валидировать по схеме |
| F-07 | P1 | Подтверждено, усилено | Курсор только у `docs search`/`log`; `records list` отдаёт `truncated` без cursor; `docs tree` режет 50/50 без `truncated`; `--limit 0` даёт cursor `"0"` | Единый cursor + честные `total/returned/truncated`; отдельно полнота источника и усечение контента |
| F-08 | P1 | Подтверждено, уточнено | `types guide --format json` печатает сырой JSON (`cli.py:2238-2260`); `skills read --output markdown` — сырое тело (`cli.py:471-473`) | Всегда envelope; raw-режим убрать/мигрировать; `--out` — отдельный transport |
| F-09 | P1 | Подтверждено | `Envelope` (`output/envelope.py:11-26`) без `guidance`; `schema_version: 1`; контракт агента обещает `guidance` | v2-envelope + каталог `code → hint/skills/docs`; контрактный тест покрытия кодов |
| F-10 | P1 | Подтверждено | `emit` пишет в файл (`envelope.py:35-60`); `types guide --out` пишет напрямую (`cli.py:2253-2256`) | Чистый `render` + отдельный transport; `--out` — явный эффект с областью |
| F-11 | P2 | Подтверждено, расширено | Наборы `json|table|markdown` 53, `json|table` 9, `json|markdown` 1; **table/markdown в `emit` — одинаковый key-value**, не реальные форматы | Форматы — часть capability; рендеры форматов сделать различными; не молча урезать |
| F-12 | P1 | Подтверждено | `--input-file`, `--patch-file`, `--query-file` только путь; `--no-input` объявлен везде и почти нигде не используется | `-` как stdin с лимитом/UTF-8; `--no-input` оставить группой как no-op или реализовать prompts |
| F-13 | P1 | Подтверждено | `records read --view nosuch` отдаёт всю запись (`cli.py:1934-1938`); `records aggregate` без `--type` берёт `workout` (`cli.py:1908`); неизвестный фильтр — пустой успех | Валидация enum/namespace до выполнения; убрать скрытые defaults; ошибка вместо «пусто» |
| F-14 | P1 | Подтверждено, уточнено | `--limit 0`; `skills read --line-range abc` — `ValueError`; `--line-range 9999-10000` — пустой успех; единицы `--budget` разные | Типы Click с диапазонами; явные единицы и границы; `usage.*`, exit 2/3 |
| F-15 | P1 | Подтверждено | `status` отдаёт `next_actions` с `action/reason` (`cli.py:2359-2361`); `_emit_error` с пустым `dataset_id` и generic help | `NextAction{argv,purpose}` + схема; заполнять известные `dataset_id/path/location/guidance` |
| F-16 | P0 | Подтверждено, расширено | `_contained_out` только для `--out/--write/--to`; `changes.py:368,527,533,656`; `history.py:195,408`; `stale --ack --path`; `skills import --into` | Единая политика ролей путей; проверка и для путей из данных; sentinel-тесты |
| F-17 | P0 | Подтверждено, расширено | `apply_write_plan` проверяет `exists()` и затем `atomic_write` (`write.py:118-132`); `atomic_write` — безусловный `os.replace` (`scanner.py:41-47`) | Атомарное create-only (`O_EXCL`/`link`), а не «проверить и заменить»; гонка `docs new`/`import` тоже |
| F-18 | P1 | Подтверждено частично | `str(Path)` даёт `\` на Windows; stdout не перенастраивается на UTF-8; `apply_edit_ops`/`change apply`/`docs status` пересобирают текст через `splitlines` + `\n` | POSIX-пути в выводе, UTF-8 stdout, байты в history; **`revert` сам по себе сохраняет CRLF** (§2.12) |
| F-19 | P2 | Подтверждено | `docs/state/cli.md` §6.11 документирует `explain-path --match`, которого нет; §2.3 — guidance как опция; §2.5 п.6 — multi-root isolation, которой нет | Генерировать справку из реестра/Click; CI-сверка; устаревшее помечать |
| F-20 | P2 | Подтверждено | Нет `tags list`/фильтра записей по тегу; `--tag` только у `docs search` | Не добавлять сейчас; отдельный gate unified-tags; пространства имён различать |
| F-21 | P0 | Подтверждено, расширено | `ensure_index` публикует индекс/stats/observe (`service.py:190-212`); `validator.py:568-582` пишет parse-cache; это делают `search`, `read`, `tree`, `validate`, `scan`, `check`, `docs links` | ReadModel без записи; parse-cache только read; публикация — явная операция; provenance/полнота |
| F-22 | P0 | Подтверждено, расширено | `publish` удаляет `current` до `rename` (`registry.py:148-150`); `apply_write_plan` пишет файл до history (`write.py:131-141`); `change apply` откат неполный (`changes.py:569-595`) | Публикация через поколения + указатель; честный `partial`; не обещать all-or-nothing без механизма |
| F-23 | P0/P1 | Подтверждено, расширено | `_contexts(...)[0]` в большинстве обработчиков; `_effective_roots` — module globals; `usage.missing_root` — `ValidationError` (exit 3); `init`/`skills attach` особые | Контекст вызова, кардинальность root на команду, запись только в один root, `usage.missing_root` exit 2 |
| F-24 | P1 | Подтверждено, расширено | `docs list` не зарегистрирован; `docs tree --max-depth` только эхо (`cli.py:1493`); `Document.status` — parse-статус; селекторы `docs read` конфликтуют молча | `docs list` с lifecycle/parse status; применить depth; матрица селекторов; валидировать QuerySpec |
| F-25 | P1 | Подтверждено, расширено | `iter_events` пропускает битые строки и `errors="replace"` (`journal.py:52-69`); `journal_diagnostics` видит только последнюю строку (`history.py:609-617`) | Strict/tolerant режимы; диагностика пропусков; strict для apply/revert/gc/export; порты ролей |
| F-26 | P1 | Подтверждено, уточнено | `visible_at` не проверяет нижнюю границу `observed_at` (`temporal.py:145-151`); `records_as_of/relations_as_of(None)` возвращают всё (`:161-172`) | Отдельный gate би-темпоральности; не менять default молча; тесты границ/зон |
| F-27 | P0 | **Новое** | `docs read` игнорирует ошибки `parse_json`/`parse_csv` (`cli.py:1366,1375`); чтения без обработки UTF-8; `main` ловит только `TodocError`/`ClickException` | Единый read/parse-контракт и граница ошибок |
| F-28 | P0 | **Новое** | `change_id` без грамматики попадает в `change_dir`/`record_path`; `archive_change` делает `rename` по пути из `change_id` (`changes.py:86-96,610-616`) | Валидировать ID, канонизировать путь, containment |
| F-29 | P0 | **Новое** | `--vault`/`--into` не проверяются: `vault_root = ctx.root / vault`, `dest = vault_root / section / name` (`cli.py:334,441,549,571,578`) | Vault — один сегмент; section — внутри vault; containment |
| F-30 | P1 | **Новое** | `derived_from`-путь читается как `root / rel` (`staleness.py:70-71,220`); `plan_ack` нормализует CRLF и бросает `ValueError` (`:264-278`) | Path policy для зависимостей; байт-точное front matter; typed error |
| F-31 | P0 | **Новое** | `publish` использует фиксированный `.tmp-current` и `rmtree(current)` до `rename`; `CURRENT.json` пишется после (`registry.py:127,148-155`) | Уникальный staging + поколения + атомарный указатель |
| F-32 | P1 | **Новое** | `status`/`index status` читают `load_current`/meta без проверки digest и полноты (`cli.py:2348-2362,296-303`) | ReadModel с `source/complete/stale`, не выдавать старый снимок за актуальный |

### 1.3. Что аудит недооценил

1. **`--preview` — не «третий стиль», а мёртвый флаг.** В `docs_edit`,
   `records_create`, `fix` параметр `preview` не участвует в ветвлении;
   ветвление идёт по `apply_`. Агент может передать `--preview --apply` и
   получить запись.
2. **`validate --all` — мёртвый флаг.** `all_` принимается и не используется:
   `validate` и так проверяет весь корпус.
3. **`records list` не просто без cursor.** `until` и `relation` применяются
   после `limit`, затем `total = len(items)`, `truncated = False`
   (`cli.py:1803-1812`). Это ложный `total`, а не только неполная пагинация.
4. **`types guide` имеет три поведения.** `--format json` — сырой JSON;
   `--format markdown --output json` — envelope; иначе — сырой текст.
5. **`emit` не различает table и markdown.** В `envelope.py:45-60` обе
   «человеческие» ветки строят `key: value`; настоящие таблицы/Markdown есть
   только в отдельных обработчиках.
6. **`--budget` — четыре единицы.** `docs read --section` — байты, полный
   `docs read`/`show` — символы, `diff` — строки, `skills read`/`context` —
   байты.
7. **Containment шире трёх BUG.** Вне области читают/пишут `change_id`,
   `--vault`, `--into`, `derived_from`, `history --path`; внешние входы
   (`--src`, `--patch-file`, `--input-file`, `--query-file`) — отдельная роль.
8. **`change apply` не all-or-nothing.** Файлы пишутся до `history.record`;
   откат неатомарен; уже записанные события истории не откатываются.
9. **`records_as_of/relations_as_of(None)` противоречат `visible_at(None)`.**
   Один путь фильтрует закрытые факты, другой возвращает всё.
10. **`main` не граница ошибок.** Ловятся только `TodocError` и
    `ClickException`; `ValueError`, `AttributeError`, `UnicodeDecodeError` из
    парсеров/данных дают traceback.
11. **Дубликаты BUG-номеров.** В `demo/bugs/` два `bug-034` и два `bug-035`;
    `bug-035-skills` уже помечен duplicate BUG-027. Ссылаться на «BUG-034» без
    пути нельзя.
12. **Multi-root заявлен, но не реализован.** `docs/state/cli.md` §2.5 п.6
    обещает изоляцию; фактически циклятся только `check/check-config/scan/
    validate/explain-path/doctor/status`, остальные берут первый.

### 1.4. Дополнительные находки (F-27…F-32)

#### F-27. Ошибки разбора и чтения превращаются в успех или traceback — P0

**Симптом**

- `docs read` на битом JSON: `value, _errors = parse_json(text)` —
  `_errors` игнорируются (`cli.py:1366`), ответ `ok: true`, `value: null`.
- `docs read` на битом CSV: `parse_csv(text)` — `csv_doc.errors` не
  проверяются (`cli.py:1375`), ответ `ok: true` с частичными строками.
- `docs read`, `docs status`, `skills read`, `types prompt`, чтение шаблонов
  и существующих целей (`cli.py:459,1205,1218,1309,1551,1631,1987,2221`)
  не ловят `UnicodeDecodeError`.
- `search._document_text` ловит только `OSError` (`search.py:34-37`), поэтому
  один битый файл роняет поиск.
- `records query` ловит только `OSError`/`JSONDecodeError`
  (`cli.py:1883-1885`), но не `UnicodeDecodeError`, не non-object spec, не
  non-int `limit`, не non-dict `filters`.
- `stale --ack` вызывает `plan_ack`, который бросает `ValueError` без
  front matter (`staleness.py:267,270`); `_stale_ack` не перехватывает.
- `main` ловит только `TodocError`/`ClickException` (`cli.py:2446-2452`).

**Корень:** нет единого helper'а «прочитать текст/разобрать структуру и вернуть
диагностику»; каждый обработчик решает сам.

**Исправление**

1. `application/read.py` (или `adapters/formats/read.py`): `read_text(path,
   role) -> str` с `OSError`/`UnicodeDecodeError` → `TodocError` с кодом
   `file.unreadable`/`usage.invalid_encoding`.
2. `parse_json_checked`/`parse_csv_checked` возвращают `(value, diagnostics)`;
   обработчик обязан добавить диагностики в конверт и не выдавать `ok: true`
   при ошибке разбора (или выдавать `ok: false` по политике).
3. `main` конвертирует известные `ValueError`/`AttributeError` из парсеров в
   `internal.error`/`usage.error` без traceback в stdout; тест «нет traceback»
   на всех листьях.
4. Не использовать широкий `except Exception`; типизировать причины.

**Приёмка:** CT-16; fixture с `0xff` в md/json/csv даёт машинную диагностику,
остальные документы доступны; `docs read` битого JSON/CSV — `ok:false` или
`diagnostics` с кодом, не `null`/частичный успех; `stale --ack` без front
matter — `ok:false`, не traceback.

#### F-28. `change_id` — путь без грамматики — P0

**Симптом:** `change_dir` берёт `change_id.split(":", 1)[-1]` как сегмент пути
(`changes.py:86`); `record_path` = `change_dir/change.json`; `load_change`
читает, `set_status` пишет, `archive_change` делает `rename` по этому пути
(`changes.py:610-616`). `change_id` приходит из CLI (`change show/validate/
verify/apply/archive/revert`) без проверки. `validate_change` делает
`relative_to(root)` (`:333`) и может бросить `ValueError` для внешнего пути.

**Исправление:** валидировать `change_id` по грамматике (`change:<slug>` или
существующий ID из `change list`); канонизировать и проверять containment до
любого чтения/записи/rename; `relative_to` заменить на безопасный helper.

**Приёмка:** CT-17; `change show --id change:../../x` → `usage.invalid_id`/exit 2;
внешний sentinel не читается и не переименовывается.

#### F-29. `--vault`/`--into` — путь без границы — P0

**Симптом:** `skills_tree`/`skills_read`/`skills_import` строят
`vault_root = ctx.root / vault` (`cli.py:334,441,549`), затем
`dest = vault_root / section / name` (`:571,578`). `--vault ../..` и
`--into ../../outside` выводят чтение/копирование за `DATA_ROOT`.

**Исправление:** `--vault` — один сегмент (`^[A-Za-z0-9._-]+$`, без `.`/`..`);
`--into` — относительный путь внутри vault; containment на канонизированном
пути; ошибки `access.outside_vault`/`usage.invalid_path`.

**Приёмка:** CT-17; `--vault ../..` и `--into ../../x` отклоняются до `scan`/
`copytree`; внешний sentinel не меняется.

#### F-30. `derived_from` и `plan_ack` — чтение/запись без политики — P1

**Симптом:** `_anchor_hash` читает `root / rel` для пути из front matter
(`staleness.py:70-71`); `collect_owners` читает `root / rel` (`:220`).
Документ с `derived_from: ["../secret.md@sha256:…"]` заставляет `stale`
читать вне root. `plan_ack` (`:264-278`) читает файл, делает
`splitlines()` + `"\n".join`, то есть **нормализует CRLF** и не сохраняет
тело байт-в-байт, хотя docstring обещает обратное; без front matter бросает
`ValueError`.

**Исправление:** применить PathPolicy к путям зависимостей; `plan_ack`
переписывать только front matter, сохраняя исходные line endings и тело;
возвращать `TodocError` с кодом `staleness.no_front_matter`.

**Приёмка:** CT-17; `derived_from` с `..` не читает внешний файл; `stale --ack`
на CRLF-файле сохраняет CRLF; отсутствие front matter — конверт, не traceback.

#### F-31. `RegistryStore.publish` — гонка staging и рассинхрон указателя — P0

**Симптом:** `tmp_dir = index_dir / ".tmp-current"` фиксирован (`registry.py:127`);
два публикатора делят staging. `publish` делает `rmtree(current)` до
`rename` (`:148-150`); при ошибке `rename` старый снимок уже удалён.
`CURRENT.json` пишется после `rename` (`:155`); при ошибке указатель может
ссылаться на старые метаданные при новом `current`.

**Исправление:** уникальный staging на публикацию; писать поколение в
`index/generations/<id>/`; валидировать шарды; атомарно переключать
`CURRENT.json`; удалять старое поколение после успешного переключения.
Две публикации не делят staging; читатель всегда видит целое поколение.

**Приёмка:** CT-9/CT-18; fault injection на каждом шаге; concurrent publish;
`load_current` не возвращает смешанные meta/payload.

#### F-32. `status`/`index status` не доказывают свежесть — P1

**Симптом:** `status` вызывает `store.load_current()` (`cli.py:2348`) и
сообщает `index_built: true` по наличию payload; `index_status` читает meta
(`cli.py:296-303`) и `current: generation_id is not None`. Ни один не сверяет
`corpus_digest`/`config_digest` с текущим сканом; устаревший снимок выглядит
актуальным.

**Исправление:** ReadModel отдаёт `source: published|memory`, `complete`,
`stale`, `provenance`; `status`/`index status` не заявляют свежесть без
проверки; при недоступности — диагностика, не `true`.

**Приёмка:** CT-11/CT-19; после внешней правки `status` показывает
`stale: true` или пересчитывает; битый/неполный снимок — `complete: false`.

---

## 2. Поправки к рекомендациям аудита

### 2.1. CAS: один смысл — не одно имя

| Команда | Флаг | Что сравнивается | Тип |
|---|---|---|---|
| `docs edit`, `fix` | `--if-hash` | хеш одного целевого файла | скаляр |
| `stale --ack`, `revert`, `records undo-relation` | `--expected-hash` | хеш одного целевого файла | скаляр |
| `change apply` | `--if-hash` | набор предусловий по нескольким файлам | `PATH=sha256:…`, повторяемый |

Решение:

- скалярный CAS: `--expected-hash HASH` для всех одноцелевых операций;
- многофайловые предусловия: `--if-hash PATH=HASH` только у `change apply`
  (или отдельное `--expect`, если решим уйти от исторического имени);
- старый скалярный `--if-hash` у `docs edit`/`fix` — алиас с диагностикой и
  сроком удаления; конфликт явных значений — ошибка;
- контрактный тест проверяет не только имя, но и **тип/семантику**.

### 2.2. `--preview` должен стать реальным режимом

- `Plan` строится всегда (чистая функция), preview показывает его;
- `--apply` применяет **тот же** план после повторной проверки предусловий;
- `--preview` + `--apply` — `usage.error`, exit 2;
- `--dry-run` мигрируется в `--preview` только там, где эффект совпадает
  (`history gc`, `skills import`), с алиасом и предупреждением;
- `--write`, `--out`, `--force`, `--fix`, `--adopt` не заменяют `--apply`.

### 2.3. `--all` у `validate` — не перегрузка, а отсутствие реализации

`validate` всегда проверяет весь корпус. Рекомендация: оставить `--all` как
**скрытый deprecated no-op** с диагностикой `info` («validate всегда проверяет
весь корпус»), убрать из документации и новых примеров. Удаление без алиаса
сломает скрипты; реализовывать вторую семантику без решения нельзя.
`skills tree --all` переименовать в `--include-muted` (алиас на время миграции).

### 2.4. Форматы: сначала рендер, потом реестр

Недостаточно объявить `formats` в capability. Сейчас `table` и `markdown` в
`emit` неотличимы. Порядок:

1. чистый `render(envelope, fmt) -> str` с разными ветками;
2. `table` — реальные таблицы/секции, `markdown` — Markdown, JSON — один объект;
3. для `skills read`/`types guide` убрать raw-ветки; `--out` — transport;
4. только после этого `formats` в capability и валидация `--output`.

### 2.5. `--budget`: единицы объявлять, а не унифицировать молча

| Команда/вариант | Текущая единица | Целевое объявление |
|---|---|---|
| `docs read --section` | UTF-8 байты окна | `unit: bytes`, `scope: content` |
| `docs read` (полный текст) | символы (`text[:budget or 4000]`) | `unit: chars` или миграция на bytes |
| `show --budget` | символы | `unit: chars` |
| `diff --budget` | строки (`budget // 40`) | `unit: lines` или `--max-diff-lines` |
| `skills read --budget` | UTF-8 байты | `unit: bytes` |
| `context --budget` | байты сериализации | `unit: bytes`, `scope: serialized_response` |
| `docs search --budget` | байты сниппетов | `unit: bytes`, `scope: snippets` |

`--limit` — элементы, `--depth` — уровни, `--budget` — не токены. `--budget 0`
и отрицательные значения — `usage.invalid_budget` (или явный count-only режим).

### 2.6. Containment: роли путей, а не один `_contained_out`

| Роль | Пример | Правило |
|---|---|---|
| `dataset_source` | `--path` у `show/diff/blame/revert`, цель дельты, путь из индекса | только внутри `DATA_ROOT`, symlink/`..` отклоняются |
| `dataset_write` | `--out`, `--write`, `docs new --path` | внутри `DATA_ROOT`, atomic write |
| `vault` | `skills read/tree/import` | внутри `<root>/<vault>`; vault — один сегмент |
| `vault_section` | `skills import --into` | относительный путь внутри vault |
| `external_input` | `--patch-file`, `--input-file`, `--query-file`, `--src` | разрешён внешний файл, лимит/UTF-8; не доверенный |
| `external_output` | `skills attach --to` | платформенный каталог; отдельное явное разрешение/роль |
| `xdg_state` | `state set` | XDG, не `DATA_ROOT`; изоляция в тестах |
| `change_id` | `change show/apply/archive` | грамматика ID, затем путь внутри `changes/` |
| `dependency` | `derived_from` | внутри `DATA_ROOT`; иначе диагностика |

Проверка — в application/policy на канонизированном пути; фактический доступ —
в адаптере. Канонизация не защищает от TOCTOU; это записать в ограничения.

### 2.7. Публикация индекса: поколения + указатель

- писать новое поколение в `index/generations/<id>/` с уникальным staging;
- валидировать все шарды;
- атомарно переключать `CURRENT.json` на новое поколение;
- удалять старое поколение только после успешного переключения (или по GC);
- читатель всегда получает либо старое, либо новое целое поколение;
- `meta` и `payload` не могут разойтись; concurrent publish не делит staging.

### 2.8. Чтение без записи: граница проходит через validator

`ensure_index` — не единственная запись. `validate_dataset` пишет parse-cache
(`validator.py:568-582`), а `validate`, `scan`, `check`, `docs links` вызывают
его. Поэтому:

- `ReadModel`/`scan_and_validate` получает флаг/порт `write_cache=False`;
- parse-cache читается, но не пишется в read/preview;
- публикация индекса — отдельный `IndexPublisher`, не метод чтения;
- `observe_history` — только явная операция (`index rebuild`/`history adopt`);
- при cold/stale/corrupt индексе чтение считает в памяти и честно помечает
  provenance/полноту.

### 2.9. `change apply`: честный outcome вместо обещания all-or-nothing

- `Plan` содержит все целевые пути, старые/новые хеши и содержимое;
- перед записью проверяются все предусловия (включая containment);
- запись и history — стадии с фиксацией фактических эффектов;
- при отказе возвращать `applied: false`/`partial` и список затронутых путей;
- `--apply` при неприменимом плане — ненулевой exit и `ok: false`, а не
  `_emit_ok` с `applied: false`;
- `change archive`: путь из `change_id` проверяется до `rename`; при ошибке
  переноса статус и папка не должны расходиться молча.

### 2.10. Multi-root: кардинальность на команду

В capability для каждой команды:

- `single` — ровно один root; >1 → `usage.multiple_roots`, exit 2;
- `multi` — цикл с изолированными `datasets[]` и общей политикой exit;
- `optional` — `TODOC_ROOT` fallback;
- `init`/`skills attach` — собственная кардинальность, не наследовать group root.

Правило позиций: явный листовой `--root` **заменяет** явный групповой;
повторяемые roots на одном уровне сохраняются; оба явных и разные — по
документированному приоритету (рекомендация: лист сильнее, группа не
добавляется). Запись никогда не выбирает первый root молча.
`usage.missing_root` — `TodocError(EXIT_USAGE, "usage.missing_root")`, а не
`ValidationError` (exit 3).

### 2.11. `docs list`: статус жизненного цикла ≠ parse-статус

- `status` — lifecycle из front matter, отсутствие → `null`;
- `parse_status` — `ok|unreadable|unsupported|permission_denied|...`;
- неизвестный статус не превращать в `done`/`captured`;
- `total/returned/truncated` — по странице, полнота источника — отдельно.

### 2.12. Line endings: проверять по путям, а не одной фразой

**Исправление BUG-033.** `revert_plan` возвращает текст из байтового снимка;
CLI `revert` пишет через `_write_whole` → `atomic_write`, который кодирует
строку в UTF-8 и пишет **байты** (`os.fdopen(fd, "wb")`). Поэтому продакшн
`revert` сохраняет CRLF. Ломается тест
`tests/unit/test_history.py::test_revert_plan_and_byte_exact_restore`: он
делает `doc.write_text(plan["content"], encoding="utf-8")`, а `Path.write_text`
на Windows переводит `\n` в `\r\n`, получая `\r\r\n`.

План:

1. исправить тест на `doc.write_bytes(plan["content"].encode("utf-8"))`;
2. не добавлять `newline=""` в `atomic_write` — он уже пишет байты; повторное
   изменение создаст двойное преобразование;
3. чинить реальные текстовые пересборки: `apply_edit_ops` (`splitlines`+`\n`),
   `apply_ops` (`changes.py:276-283`), `docs status` (`cli.py:1662`),
   `records status` (`cli.py:1858`), `plan_ack` (`staleness.py:265-278`);
4. для `stale --ack` сохранять тело и line endings, меняя только front matter.

### 2.13. Ошибки чтения и разбора — единый контракт

- `read_text` helper с `OSError`/`UnicodeDecodeError` → `TodocError`;
- `parse_json`/`parse_csv` возвращают диагностики; обработчик не игнорирует;
- `main` конвертирует известные ошибки в envelope; traceback не в stdout;
- тест «нет traceback» на всех 63 листьях и на битых fixture.

### 2.14. Граница ошибок `main`

`main` сейчас ловит только `TodocError`/`ClickException`. Добавить:

- `click.exceptions.Abort` → exit 1/2 по политике;
- `UnicodeEncodeError` при записи stdout → UTF-8 reconfigure/fallback;
- известные `ValueError`/`AttributeError` из парсеров → `internal.error` с
  безопасным сообщением;
- неизвестные исключения — `internal.error`, exit 1, без traceback в stdout;
- тест subprocess на каждый класс.

---

## 3. Архитектурные решения

### 3.1. Click остаётся парсером; реестр — метаданные

- Click — единственный источник синтаксиса (имена, типы, required, default,
  enum, help). Не генерировать команды из реестра.
- `src/todoc/output/capabilities.py` (канон unified) хранит `effect`
  (`read|plan|write|admin`), `scope` (`dataset|vault|history|state`),
  `formats`, `root_policy`, `limits` с единицами, `supports`.
- Декларация и Click-объект связываются декоратором или явной таблицей; тест
  обходит Click **рекурсивно** (включая `docs flow render/walk`) и сверяет
  пути/опции/типы/default/required/enum в обе стороны.
- Если для F-01 достаточно `ctx.obj` и `default=None`, не строить реестр
  big-bang: вводить по семействам.

### 3.2. Один контекст вызова вместо module globals

- `CliContext` (immutable dataclass) в `src/todoc/cli_context.py`:
  `roots`, `output`, `no_input`, `root_policy`, `format`, `dataset_scope`.
- Разрешение `--root`/`--output`: явное значение листа > явное значение группы >
  default; `click.Context.get_parameter_source`, не `None`/`""` эвристики.
- Листовые `--output`/`--root` объявляются без «перебивающего» дефолта.
- `_emit_error` использует разрешённый output из контекста; при ошибке разбора
  до контекста — безопасный JSON.
- Убрать `_group_roots`/`_group_output`.

### 3.3. Политика путей

- `src/todoc/application/paths.py`: `PathPolicy` с ролями §2.6; канонизация
  `resolve(strict=False)` + `relative_to`; для записи — `atomic_write`/
  `atomic_create`.
- Пути из данных (delta target, history path, `derived_from`, index path)
  проверяются так же, как CLI-пути.
- Внешние входы — отдельная роль с лимитом и UTF-8.
- Ошибки: `access.outside_data_root`, `access.outside_vault`,
  `usage.invalid_path`; exit 4/2 по смыслу.
- Ограничения ОС/ФС и TOCTOU записать в документации.

### 3.4. Чтение, индекс, кэш, история

- `src/todoc/application/read_model.py`: `ReadSnapshot` с `payload`,
  `source: published|memory`, `complete`, `stale`, `diagnostics`, `provenance`.
- `read_snapshot()` не пишет; если published актуален — использует его; если
  stale/corrupt/missing — считает в памяти; публикация — только `index rebuild`
  или явная операция.
- parse-cache: read-only в read/preview; запись — только rebuild/явная операция.
- history: `strict` для apply/revert/gc/export; `tolerant` для чтения с
  диагностикой пропусков; отдельные порты event/object/admin.
- `RegistryStore` — поколения + указатель (§2.7).

### 3.5. Мутации: `Plan → Apply → Outcome`

- Расширить `WritePlan` (`domain/models.py`): `effect`, `targets`,
  `preconditions`, `basis`, `diagnostics`; не создавать второй тип плана.
- `src/todoc/application/mutation.py`: `MutationPlan`/`Outcome`
  (`planned|applied|partial|failed`, `affected_paths`, `diagnostics`).
- Preview рендерит план, не пишет ничего (source/cache/index/history/XDG/
  external target).
- Apply повторно проверяет область, права, актуальность плана и хеши; create-only
  — атомарный no-replace.
- `ok == (exit_code == 0)`; отказ apply — ошибка, не успех.

### 3.6. Конверт, guidance, renderer

- `schema_version: 2` по умолчанию; `data.meta`/`data.result` по unified §4.
- `guidance: {profile, mode, items}` обязателен; успех — `mode=compact`,
  `items=[]`; ошибка — `code → {hint, skills, docs}` из каталога.
- `src/todoc/resources/guidance/<profile>.json`; fallback; package data.
- `next_actions[]` строго `{argv: list[str], purpose: str}`; `NextAction`
  в `domain/models.py`; шаблоны с незаполненными значениями — отдельно.
- `src/todoc/output/render.py` — чистая функция; `output/transport.py` —
  stdout/file; `--out` — явный эффект.
- `executed: false` для discovery/неполного вызова; `ok: true` только если
  безопасно выполнено или это информационный ответ.

### 3.7. Query и cursor

- `src/todoc/application/query.py`: `QuerySpec` (schema_version, scope, types,
  filters, temporal, order, limit, cursor, fields) и `QueryResult`
  (`items, total, returned, truncated, next_cursor, provenance, diagnostics`).
- `src/todoc/application/documents.py` или `query.py`: `docs list` metadata.
- `Cursor` value object: `{dataset_id, snapshot_digest, filters, order, offset,
  algo_version}`; несовпадение — `usage.stale_cursor`.
- Фильтры до limit; `total` только если известен; `--limit >= 1`.
- Полнота источника и усечение контента — разные поля/диагностики.

### 3.8. Ошибки

- `errors.py`: добавить `EXIT_USAGE`-совместимые коды для `usage.*`; не
  использовать `ValidationError` для `usage.missing_root`/`usage.invalid_cursor`.
- `cli.main`: typed boundary (§2.14).
- `file.unreadable`/`usage.invalid_encoding` — единые коды.

---

## 4. Этапы, work packages и зависимости

### 4.1. Граф зависимостей

```text
W0.1 backup → W0.2 inventory → W0.3 decisions
W1.1 paths → W1.2 atomic create → W1.3 publish → W1.4 read model → W1.5 history → W1.6 errors
W2.1 context → W2.2 capabilities → W2.3 envelope → W2.4 next actions → W2.5 render
W3.1 docs list → W3.2 query → W3.3 cursor → W3.4 validation → W3.5 stdin/raw
W4.1 CAS → W4.2 preview/apply → W4.3 names → W4.4 change outcome
W5.1 portability → W5.2 formats → W5.3 docs
W6 release
```

W2.3 можно начинать после W2.1; W3 — после W2.3; W4 — после W2.3 и W1.2;
W5 — после W4. Каждый WP — отдельный PR; не смешивать контрактные и
безопасностные изменения в одном PR без необходимости.

### 4.2. Work packages

| ID | Работа | Файлы | Тесты | Зависит | Гейт |
|---|---|---|---|---|---|
| W0.1 | Backup/сохранность | — | — | — | Восстановление проверено |
| W0.2 | Инвентарь Click и baseline | `tests/cli/test_cli_contract.py` | рекурсивный обход | W0.1 | 63 листа, nested flow |
| W0.3 | Решения §7 | этот план | — | W0.2 | D1–D5, D10–D14 |
| W1.1 | PathPolicy + containment | `application/paths.py`, `cli.py`, `changes.py`, `history.py`, `staleness.py`, `skills` | `test_paths_policy.py`, `test_cli_path_containment.py` | W0.3 | CT-9, CT-17 |
| W1.2 | Atomic create-only | `adapters/filesystem/scanner.py`, `write.py`, `changes.py`, `cli.py` | `test_atomic_create.py` | W1.1 | CT-8, concurrency |
| W1.3 | Publish поколения | `application/registry.py`, `service.py` | `test_registry_publish.py` | W1.1 | CT-9, CT-18 |
| W1.4 | ReadModel без записи | `application/read_model.py`, `service.py`, `validator.py`, `cli.py` | `test_cli_read_only.py`, `test_scanner_registry.py` | W1.3 | CT-11 |
| W1.5 | History strict/tolerant | `adapters/history/journal.py`, `application/history.py` | `test_journal_strict.py` | W1.4 | CT-13 |
| W1.6 | Error boundary | `errors.py`, `cli.py`, `search.py`, `staleness.py` | `test_cli_error_boundary.py` | W1.1 | CT-16 |
| W2.1 | CliContext/output | `cli_context.py`, `cli.py` | `test_cli_context.py` | W1.6 | CT-2 |
| W2.2 | Capabilities | `output/capabilities.py`, `cli.py` | `test_capabilities.py` | W2.1 | CT-1 |
| W2.3 | Envelope v2 + guidance | `output/envelope.py`, `output/guidance.py`, `resources/guidance/` | `test_unified_envelope.py`, `test_unified_guidance.py` | W2.2 | CT-3, CT-4, CT-10 |
| W2.4 | NextAction | `domain/models.py`, `output/envelope.py`, `cli.py` | `test_unified_envelope.py` | W2.3 | CT-4 |
| W2.5 | Render/transport | `output/render.py`, `output/transport.py`, `cli.py` | `test_render.py`, `test_unified_formats.py` | W2.3 | CT-3, CT-12 |
| W3.1 | `docs list` | `cli.py`, `application/documents.py` | `test_cli_docs_list.py` | W2.3 | CT-5, CT-6 |
| W3.2 | Query pipeline | `application/query.py`, `cli.py` | `test_query_spec.py` | W3.1 | CT-6 |
| W3.3 | Cursor/pagination | `application/query.py`, `cli.py`, `search.py` | `test_unified_pagination.py` | W3.2 | CT-5 |
| W3.4 | Numeric/enum validation | `cli.py`, `application/query.py` | `test_cli_numeric_validation.py` | W3.2 | CT-20 |
| W3.5 | stdin/raw migration | `cli.py`, `output/` | `test_cli_stdin.py`, `test_unified_formats.py` | W2.5 | CT-3, CT-16 |
| W4.1 | CAS contract | `cli.py`, `application/write.py` | `test_cli_cas.py` | W2.3 | CT-8 |
| W4.2 | Preview/apply matrix | `application/mutation.py`, `cli.py` | `test_cli_preview_apply.py`, `test_cli_mutation_matrix.py` | W1.2, W2.3, W4.1 | CT-7, CT-14 |
| W4.3 | Flag names | `cli.py`, `output/capabilities.py` | `test_cli_names.py` | W2.2 | CT-1 |
| W4.4 | Change outcome | `application/changes.py`, `cli.py` | `test_cli_changes.py` | W4.2 | CT-14 |
| W5.1 | Portability | `cli.py`, `write.py`, `changes.py`, `output/` | `test_cli_portability.py` | W4.4 | CT-12 |
| W5.2 | Formats | `output/render.py`, `cli.py`, `capabilities.py` | `test_unified_formats.py` | W2.5 | CT-21 |
| W5.3 | Docs generated | `docs/state/cli.md`, `README`, `SKILL.md`, `tools/` | `test_docs_reference_sync.py` | W4.4 | CT-15 |
| W6 | Release | — | все | W5.3 | DoD |

### 4.3. Матрица мутаций

| Команда | Сейчас | Целевое | Флаги | Обязательный тест |
|---|---|---|---|---|
| `init` | пишет сразу | explicit action (D14) или preview/apply | `--root`, `--dataset-id` | повторный init не перезаписывает |
| `index rebuild` | пишет сразу | preview/plan_hash → `--apply` | `--force`, `--apply` | preview не публикует |
| `docs new` | пишет сразу | preview default, `--apply` (D2); create-only | `--title`, `--dir`, `--path`, `--apply` | гонка, существующая цель |
| `docs edit` | `--apply` пишет, `--preview` мёртв | preview default, `--apply` | `--preview`, `--apply`, `--if-hash` | preview не пишет; invalid ops отклонены |
| `docs status --set` | пишет сразу | preview default, `--apply` | `--set`, `--apply` | GET чист; SET CAS |
| `docs flow render --write` | пишет сразу | `--write` target + `--apply` (D13) | `--write`, `--apply` | preview не пишет |
| `records create` | `--apply` пишет, `--preview` мёртв | preview default, `--apply` | `--preview`, `--apply` | create-only race |
| `records status --set` | пишет сразу | preview default, `--apply` | `--set`, `--apply` | enum, CAS |
| `records undo-relation` | preview default | сохранить + `--apply` | `--expected-hash` | preview не пишет |
| `fix` | `--apply` пишет, `--preview` мёртв | preview default, `--apply` | `--preview`, `--apply`, `--if-hash` | preview не пишет |
| `revert` | preview default | сохранить + `--apply` | `--expected-hash` | preview не пишет |
| `stale --ack` | preview default | сохранить + `--apply` | `--reason`, `--apply`, `--expected-hash` | CRLF, no front matter |
| `change open` | пишет сразу | explicit action (D14) | `--title` | существующий ID |
| `change apply` | preview default; отказ = `ok:true` | preview default; отказ = `ok:false` | `--apply`, `--if-hash` | partial/failed |
| `change revert` | preview default | сохранить | `--apply` | preview не пишет |
| `change archive` | пишет сразу | preview default или explicit (D14) | `--tag`, `--apply` | containment `change_id` |
| `history gc` | `--dry-run` | preview default, `--apply`; `--dry-run` alias | `--keep-objects`, `--purge-before`, `--apply` | preview не удаляет |
| `history adopt` | пишет сразу | preview/plan → `--apply` | `--apply` | preview не пишет |
| `history export` | пишет сразу | `--to` target + `--apply` (D13) | `--to`, `--apply` | containment |
| `interop export --write` | пишет сразу | `--write` target + `--apply` (D13) | `--write`, `--apply` | preview не пишет |
| `types guide --out` | пишет сразу | `--out` target + `--apply` (D13) | `--out`, `--apply` | containment |
| `skills attach` | пишет сразу | `--to` target + `--apply` (D13) | `--to`, `--force`, `--apply` | external target |
| `skills import` | `--dry-run` | preview default, `--apply`; `--dry-run` alias | `--src`, `--into`, `--apply` | vault containment |
| `state set/unset` | пишет сразу | explicit action (D14) или preview | `--apply` | XDG isolation |
| `tag` | пишет сразу | explicit action (D14) | `--rev`, `--message` | history tag |
| `validate`/`scan`/`check` | пишут parse-cache | не писать | — | CT-11 |
| `doctor --fix` | не ремонтирует | explicit action или убрать | `--fix` | не выдавать pass |

### 4.4. Этапы

#### Этап 0 — база и сохранность

- [ ] W0.1: backup tracked/untracked/history; проверка восстановления.
- [ ] W0.2: baseline и рекурсивный инвентарь Click; зафиксировать 63 листа,
      nested `docs flow render/walk`.
- [ ] W0.3: решения §7; зафиксировать D1–D5, D10–D14.
- [ ] Разрешить дубликаты BUG-034/035 по путям, не по номерам; карта F→BUG.

**Гейт 0:** backup проверен; baseline записан; инвентарь полный; решения есть
или этап блокирован.

#### Этап 1 — P0: данные и чтение

- [ ] W1.1 PathPolicy: `change_id`, delta target, history path, `--vault`,
      `--into`, `derived_from`, index paths; sentinel/fault tests.
- [ ] W1.2 Atomic create-only: `records create`, `docs new`, `change open`,
      `init`, `skills import`; `O_EXCL`/`link`.
- [ ] W1.3 Publish: поколения + указатель; concurrent publish; fault injection.
- [ ] W1.4 ReadModel: read/preview не пишут source/cache/index/history/XDG;
      `validate`/`scan` не пишут parse-cache.
- [ ] W1.5 History strict/tolerant; диагностика пропусков; strict для
      apply/revert/gc/export.
- [ ] W1.6 Error boundary: read/parse helpers, `main`, UTF-8, no traceback.

**Гейт 1:** CT-7/8/9/11/13/16/17/18/19; полный pytest + coverage; sentinel и
fault injection.

#### Этап 2 — контракт вызова и вывода

- [ ] W2.1 CliContext; `--output`/`--root` обе позиции; `usage.missing_root`
      exit 2; убрать globals.
- [ ] W2.2 Capabilities; рекурсивный contract-тест; `formats`, `effect`,
      `root_policy`, `limits`.
- [ ] W2.3 Envelope v2 + guidance; каталог кодов; `executed`.
- [ ] W2.4 NextAction; `status` без `action/reason`; заполнение `dataset_id`.
- [ ] W2.5 Render/transport; `types guide`/`skills read` в envelope; `--out`
      отдельный эффект.

**Гейт 2:** CT-1/2/3/4/10; все листья; ошибки разбора; renderer без I/O.

#### Этап 3 — чтение, обзор, query

- [ ] W3.1 `docs list`: lifecycle/parse status, null, filters, page.
- [ ] W3.2 Query pipeline: `records list` filters до limit; QuerySpec schema;
      `docs read` selector matrix; parse errors.
- [ ] W3.3 Cursor: `docs tree` truncated/cursor; `log` no cursor on last page;
      `--limit 0` error; property pages.
- [ ] W3.4 Numeric/enum validation: all `--limit/--depth/--rows/--budget/
      --line-range/--max-depth`; `records read --view`; `records aggregate`
      default; namespace mismatch.
- [ ] W3.5 stdin/raw migration: `-` for file inputs; limit/UTF-8; `--no-input`.

**Гейт 3:** CT-5/6/7/14/16; docs list 20 идей; filters after limit; no-write.

#### Этап 4 — мутации и CAS

- [ ] W4.1 CAS contract: `--expected-hash` scalar; `--if-hash PATH=HASH`
      multi only `change apply`.
- [ ] W4.2 Preview/apply matrix (§4.3); `--preview` + `--apply` error;
      `--dry-run` alias; no-write.
- [ ] W4.3 Flag names: `--include-muted`, `--history-tag`, `docs new --path`
      target, flow section; `validate --all` deprecated no-op.
- [ ] W4.4 Change outcome: `planned|applied|partial|failed`; `change archive`
      containment.

**Гейт 4:** CT-7/8/14; preview no writes; apply reports actual paths; CAS.

#### Этап 5 — переносимость, форматы, документация

- [ ] W5.1 POSIX paths, UTF-8 stdout, history bytes; CRLF tests; Win+Linux.
- [ ] W5.2 Real table/markdown; `formats` validation; `skills read`/`state`.
- [ ] W5.3 Generate `docs/state/cli.md`/help; counters; linkcheck; update
      README/SKILL/prompts/benchmark.

**Гейт 5:** CT-12/15; Win+Linux; linkcheck 0; counters; help no removed flags.

#### Этап 6 — выпуск

- [ ] Full pytest, coverage 100%, Python 3.11/3.12; Windows smoke.
- [ ] `validate --root demo --all` = 0; `linkcheck` = 0.
- [ ] All F-findings status; BUG duplicates resolved; reports not deleted.
- [ ] Migration table; benchmark; user review before commit/PR.

---

## 5. Матрица тестов и гейты

| ID | Проверка | Этап | Не считается доказательством |
|---|---|---|---|
| CT-1 | Реестр == Click рекурсивно: пути/опции/типы/default/required/enum | 2 | Число листьев |
| CT-2 | `--output` до/после команды; успех/ошибка; invalid format | 2 | Ручной запуск одной команды |
| CT-3 | Все листья + группы + корень; help/version/parse error отдельно | 2 | Только `validate` |
| CT-4 | `next_actions={argv,purpose}`, `guidance` схема | 2 | Наличие поля без схемы |
| CT-5 | Страницы: progress, source completeness, clipping раздельно | 3 | Наличие `truncated` |
| CT-6 | Фильтры до limit; одинаковые входы → одна выборка | 3 | Ручное сравнение |
| CT-7 | Мутация без `--apply` не пишет (source/index/cache/history/XDG/external) | 1,4 | Отсутствие ошибки |
| CT-8 | CAS/создание: конфликт, неизменность цели, concurrency | 1,4 | Только happy path |
| CT-9 | Containment: root/vault/symlink/`..`/внешний sentinel | 1 | `grep` по коду |
| CT-10 | Каждый `code` есть в guidance-каталоге | 2 | Выборочная проверка |
| CT-11 | Read purity: cold/warm/stale/corrupt; no-write | 1 | «Команда называется read» |
| CT-12 | Portability: POSIX paths, UTF-8, CRLF bytes, Win+Linux | 5 | Один запуск WSL |
| CT-13 | History strict/tolerant: середина/конец, unknown fields, object missing | 1 | Отсутствие ошибки |
| CT-14 | Outcome: planned/applied/partial/failed; отказ apply ≠ ok | 4 | `ok:true` без applied |
| CT-15 | Docs generated/counters/linkcheck | 5 | Ручная правка справки |
| CT-16 | Parse/UTF-8 errors: битый md/json/csv, no traceback | 1 | Только happy path |
| CT-17 | Traversal: `change_id`, `--vault`, `--into`, `derived_from` | 1 | `grep` по коду |
| CT-18 | Publish: concurrent, fault injection, meta/payload согласованы | 1 | Один успешный rebuild |
| CT-19 | Freshness: `status`/`index status` не выдают stale за current | 1,3 | `index_built: true` |
| CT-20 | Numeric/enum: `--limit/--depth/--rows/--budget/--line-range/--max-depth`, `--view`, namespace | 3 | Только happy path |
| CT-21 | Formats: `table` и `markdown` различаются, `--output` валидируется | 5 | Одинаковый key-value |

Дополнительно:

- **Subprocess:** `python -m todoc`, `stdout/stderr/exit`, Click parse errors,
  multi-root; не только `CliRunner`.
- **Fixtures:** `tmp_path`, `PYTHONDONTWRITEBYTECODE=1`, `XDG_STATE_HOME` в tmp;
  не мутировать реальный `demo`.
- **Fault injection:** rename/fsync/OSError на каждой стадии; проверять
  фактические байты и журнал.
- **Golden:** JSON/table/markdown на фиксированном датасете; изменение формы —
  отдельное решение.
- **Negatives:** неполный вызов, неверный флаг/enum, границы чисел, невалидный
  UTF-8, большой stdin, пустой/частичный результат.
- **Windows:** symlink/chmod tests skip on unsupported OS; separate smoke.

### 5.1. Команды гейтов

```bash
cd /home/newuser/projects/todoc
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q
PYTHONPATH=src python3 -m coverage run --branch --source=src/todoc -m pytest -q
PYTHONPATH=src python3 -m coverage report -m --fail-under=100
python3 tools/linkcheck.py
PYTHONPATH=src python3 -m todoc --root /tmp/todoc-audit --output json validate --all
```

Для `coverage` установить `[dev]` в изолированном окружении. Не запускать
мутирующие проверки на реальном `demo`; использовать копию/`tmp_path`.

---

## 6. Миграция и совместимость

| Изменение | Старое поведение | Новое | Миграция |
|---|---|---|---|
| Глобальный `--output` | Игнорировался успехом | Работает в обеих позициях | Скрипты, получавшие JSON, получат запрошенный формат |
| `--preview` | Мёртвый флаг | Явный preview | `--preview --apply` → ошибка; обновить вызовы |
| `--dry-run` | Свой стиль | Алиас preview где эквивалентно | Предупреждение + срок |
| `--if-hash` скаляр | Работал в edit/fix | `--expected-hash` | Алиас + диагностика |
| `--if-hash PATH=HASH` | Только change apply | Сохраняется как multi | Не смешивать со скаляром |
| `--all` validate | Мёртвый | Deprecated no-op / реализован | Убрать из docs/скриптов |
| `skills tree --all` | Показать muted | `--include-muted` | Алиас |
| `records aggregate` без `--type` | `workout` | Ошибка/явный default | Указать тип |
| `records read --view nosuch` | Вся запись | Ошибка/fallback | Обновить вызовы |
| `--limit 0` | Cursor без прогресса | Usage error | Исправить клиентов |
| `docs tree --max-depth` | Игнорировался | Ограничивает | Вывод может стать меньше |
| `usage.missing_root` | exit 3 | exit 2 | Обновить проверки exit |
| `status` next_actions | `action/reason` | `argv/purpose` | Обновить парсеры |
| `change apply --apply` отказ | `ok:true` | `ok:false`/exit | Обновить клиентов |
| raw `types guide`/`skills read` | Сырой текст | Envelope | Обновить pipe-клиентов |
| multi-root write | Первый root | Ошибка/один root | Указать root явно |
| `--out`/`--write`/`--to` | Писали сразу | Требуют `--apply` (D13) | Обновить вызовы |
| `stale --ack` | Нормализовал CRLF | Сохраняет байты | Проверить CRLF |
| `change_id` traversal | Работал | Ошибка ID | Исправить ID |

**Принцип:** сохранять только однозначные алиасы с диагностикой и сроком; не
возвращать опасный старый эффект; breaking changes перечислить в migration guide.

---

## 7. Открытые решения

| ID | Решение | Рекомендация | Блокирует | Если не подтверждено |
|---|---|---|---|---|
| D1 | Текущее дерево или чистый master | Текущее дерево (иначе теряются правки/баги) | W0.2 | Повторить инвентарь на выбранной базе |
| D2 | Review-first для всех мутаций | Да, кроме D14 | W4.2 | Оставить explicit action для исключений |
| D3 | CAS-имена | `--expected-hash` scalar; `--if-hash PATH=HASH` multi | W4.1 | Не переименовывать без миграции |
| D4 | Multi-root | `single` для записи, `multi` для чтения | W2.1 | Отказ при >1 root |
| D5 | Внешние пути | Роли §2.6; `--allow-outside-root` не вводить | W1.1 | Запретить внешние пути |
| D6 | `docs list` статус | lifecycle + parse_status | W3.1 | Не добавлять `docs list` |
| D7 | History strict | strict для apply/revert/gc/export | W1.5 | Tolerant + диагностика |
| D8 | Би-темпоральность | Отдельный gate; не менять default | — | Не трогать F-26 |
| D9 | Теги | Отдельный gate unified-tags | — | Не добавлять `tags list` |
| D10 | Форматы | Реальные table/markdown | W5.2 | Оставить текущий `emit` |
| D11 | Версия контракта | Только v2 по умолчанию | W2.3 | Не вводить второй API |
| D12 | `--all` validate | Deprecated no-op + info | W4.3 | Удалить с breaking change |
| D13 | `--write/--out/--to` | Target + `--apply` | W4.2 | Оставить explicit write |
| D14 | Admin actions (`init`, `state`, `tag`, `change open`, `change archive`) | Explicit action, документировать исключение | W4.2 | Сделать preview/apply |

D1–D5, D10–D14 нужно подтвердить до соответствующего WP. D6–D9 можно отложить,
но тогда F-20/F-24/F-26 остаются открытыми и не входят в DoD базового выпуска.

---

## 8. Связь с существующими идеями и планами

| Источник | Что берём | Что не делаем сейчас |
|---|---|---|
| Мастер-план Э0–Э4 | Порядок, сохранность, storage seam, release gates | Не запускать Э5–Э12 без отдельного решения |
| Unified З0-S/З1–З9 | v2-envelope, capability, query/cursor, preview/apply, миграция | Не создавать второй контракт/реестр |
| BUG-022 / metadata-overview | `docs list`, lifecycle/parse status, один запрос | Не запускать отдельный metadata-overview backlog |
| `cli-model-guidance-and-hint-catalog`, Wave 0 | `guidance`, каталог кодов, `--mode guided` | Не дублировать P15 вторым каталогом |
| `bitemporal-clocks` | Отдельный gate F-26 | Не менять default времени в базовом выпуске |
| `unified-tags-and-tag-graph` | Пространства тегов, фильтры | Не добавлять `tags list`/граф сейчас |
| `todocignore` | Scope/ignore | Не вводить matcher до решения |
| `sqlite-storage-drivers` | Задел портов | Не реализовывать SQLite/FTS сейчас |
| `action-logging` | Диагностики без default телеметрии | Не писать телеметрию при read |
| `docs-move`, `entity-to-folder` | Будущие планы | Не обещать move/rollback сейчас |
| AFTER (MCP/Web/embeddings/plugins) | Будущие transport/фичи | Не входят в этот план |

**Явные non-goals:** переименование 63 команд ради косметики; SQLite/MCP/Web/
embeddings; новые типы датасета; массовая миграция тегов; автоматическое
исправление датасета; скрытая сеть/фоновые процессы.

---

## 9. Карта BUG и дубликатов

- В рабочем дереве **61 файл** в `demo/bugs`; есть дубликаты номеров:
  `bug-034-change-apply-target-outside-root.md` и
  `bug-034-history-tests-windows-chmod-line-endings.md`;
  `bug-035-history-path-outside-root.md` и
  `bug-035-skills-tree-crash-root-skill-md.md` (последний уже `duplicate`
  BUG-027).
- Ссылаться на BUG по пути/ID, а не только по номеру. Перед закрытием —
  разрешить коллизию; репорты не удалять/не переименовывать.
- Карта F→BUG (проверять перед изменением статуса):
  F-01→BUG-037; F-04→BUG-049/design-q02; F-06→BUG-041/042;
  F-07→BUG-017/050; F-09→BUG-021/044; F-13→BUG-038/039/055/020;
  F-14→BUG-040/043/050; F-15→BUG-044; F-16→BUG-034/035/036;
  F-17→BUG-051; F-18→BUG-030/032/033; F-19→BUG-054;
  F-20→BUG-056; F-22→BUG-052; F-24→BUG-022/019/042;
  F-27→CA-001/CA-002/BUG-048; F-28→BUG-034 (change); F-29→BUG-036;
  F-30→BUG-035 (history)/BUG-033; F-31→BUG-052; F-32→BUG-052/BUG-022.
  F-25/F-26 — проверить наличие репорта; не создавать дубль.

---

## 10. Definition of Done

- [ ] CT-1…CT-21 проходят для актуального дерева и всех применимых вариантов.
- [ ] Общие опции имеют один источник семантики и проверенный приоритет.
- [ ] Один CAS-контракт по смыслу (скаляр/набор), один preview/apply, один
      набор канонических имён.
- [ ] Полнота доказуема; `--limit 0` отклоняется; cursor не выдумывается.
- [ ] `guidance` есть в конверте и каталоге для каждого кода.
- [ ] Машинные операции не обходят конверт; raw-клиенты мигрированы.
- [ ] Containment, create-only, publish, read-purity доказаны негативными и
      fault-injection тестами.
- [ ] Пути POSIX, stdout UTF-8, history побайтово; Win+Linux golden.
- [ ] `validate --root demo --all` = 0; `tools/linkcheck.py` = 0; coverage 100%.
- [ ] `docs/state/cli.md` и `--help` сгенерированы из реестра/Click.
- [ ] Миграционная таблица и обновлённые потребители; BUG-статусы и дубликаты
      разрешены; репорты не удалены.
- [ ] Пользователь подтвердил решения §7 и выпуск; commit/PR — только по
      отдельному разрешению.

---

## 11. Readiness checklist и первый срез

### 11.1. Перед началом

- [ ] D1–D5, D10–D14 подтверждены или выбраны defaults.
- [ ] Backup рабочего дерева проверен восстановлением.
- [ ] `[dev]` установлен в изолированном окружении; `coverage` доступен.
- [ ] CI Windows job добавлен или CT-12 помечен как not_run.
- [ ] Решено, входит ли `.doc` в `linkcheck`; иначе 4 битые ссылки — baseline.
- [ ] Дубликаты BUG-034/035 разрешены по путям.

### 11.2. Первый PR (безопасный)

W1.1 + W1.2 + W1.6:

- `application/paths.py` + containment для `change_id`, delta, history,
  `--vault`, `--into`, `derived_from`;
- `atomic_create` для `records create`, `docs new`, `change open`, `init`,
  `skills import`;
- read/parse helper + `main` error boundary;
- тесты: `test_paths_policy.py`, `test_cli_path_containment.py`,
  `test_atomic_create.py`, `test_cli_error_boundary.py`;
- гейт: полный pytest + coverage + sentinel/fault injection.

Этот PR не меняет публичный JSON/exit; он закрывает critical-риски и создаёт
фундамент для остальных WP.

### 11.3. Второй PR

W1.3 + W1.4 + W1.5: публикация поколениями, ReadModel без записи, strict
history. Гейт CT-9/11/13/18/19.

### 11.4. Третий PR

W2.1 + W2.2 + W2.3: контекст, capabilities, v2-envelope/guidance. Гейт
CT-1/2/3/4/10.

Дальше — W3 (docs list/query), W4 (preview/apply), W5 (portability/docs),
W6 (release). Не начинать W4 до W1.2 и W2.3: иначе preview/apply будет
опираться на неатомарную запись и старый конверт.
