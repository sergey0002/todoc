---
id: doc:audit-implementation
title: "Audit: аудит реализации MVP"
doc_type: audit-report
lang: ru
source: docs/plan/audit-implementation.md
copied: true
---

# Аудит реализации todoc (24 ноября 2026)

**Объект:** `src/todoc/` (MVP CLI, коммит `dbfa749`, PR #2) + `SKILL.md`/`references/`/`assets/`.
**Эталоны:** `plan/constitution.md` (P1–P14, S1–S12, FR/NFR, §8 CLI-контракт, §9 конфиги, §10 DoD, §11 структура),
`plan/implementation-plan.md` (Этап 0–7.5, порты E1–E10, §7 DoD, §13 F1–F12, §14 R1–R32, §15 чек-листы),
`docs/guides/cli-for-agents.md` (26 постулатов), `docs/guides/markdown-knowledge-for-agents.md` (§§V–XIII),
`docs/guides/mcp-for-agents.md` + `docs/research/mcp-cli-agents.md`, `plan/competitive-analysis.md`,
`docs/research/knowledge-base-comparative-audit.md`.

**Метод:** построчное чтение всего `src/todoc/` + сверка каждой команды/флага с конституцией §8.1 +
эмпирическая проверка подозрений через установленный CLI (subprocess, отдельные процессы).

## Вердикт

Реализация — **рабочий MVP-скелет, соответствующий архитектуре и духу плана** (envelope, exit codes,
multi-root, resolver-приоритеты, review-first writes, атомарные поколения индекса, aggregate с
provenance). Но есть **5 критических багов (P0)**, из которых 3 ломают заявленные workflow
(`fix`, containment, пагинация), и **~20 существенных отклонений (P1)** от конституции/DoD:
не реализованы record schema validation, folder-local `.todoc.json`, ports E1–E10, CI/contract-тесты;
ошибки в JSON-режиме не возвращают envelope. 100% покрытие тестами при этом **не ловит P0**,
т.к. все тесты in-process (CliRunner) — межпроцессные баги невидимы. До пилота обязательны P0 + P1 №6–№14.

---

## P0 — критические баги (все доказаны эмпирически)

### P0-1. ID диагностик нестабильны между процессами → workflow `validate → fix` сломан

`validator._diag` и `service.scan_and_validate` генерируют ID через Python `hash()`:
`f"diag_{abs(hash((path, code, message))) % 100000:05d}"`. `hash()` строк рандомизирован
(`PYTHONHASHSEED`), поэтому ID разные в каждом процессе.

```
validate run 1: ['diag_89512']
validate run 2: ['diag_88506']   # новый процесс
fix --diagnostic diag_89512 → Error [fix.diagnostic_not_found] (exit 3)
```

Конституция требует stable diagnostic codes/IDs; Этап 6 — `fix --diagnostic <id>` по ID из
предыдущего `validate`. Тесты это не ловят (CliRunner in-process, один hash seed).
**Фикс:** детерминированный ID — `sha256(dataset_id|path|code|line|column|evidence)[:8]`
(или счётчик в порядке детерминированного обхода + хеш). Добавить subprocess-тест.

### P0-2. Containment-утечки: запись за пределы DATA_ROOT

- `docs new --dir ../../outside` → создан `/tmp/outside/escape-test.md` (exit 0, ok).
  `dir_.strip('/')` не отсекает `..`.
- `types guide --out ../../escaped-guide.md` → создан `/tmp/escaped-guide.md`.
  Относительный `--out` приклеивается к root без проверки containment.

Конституция §8.2: «`--out` … (relative проверяется на containment)»; §15.4: «containment» в чек-листе
безопасности. Тот же класс: `create_record_plan` проверяет `../`/`/../`/leading `/`, но пропускает
`records/..` (без завершающего слеша) и backslash-пути.
**Фикс:** единый `resolve_within_root(root, rel)` (resolve + `relative_to`) для всех write-путей:
`docs new`, `types guide --out`, `records create`, `docs edit`, `fix`, `envelope.emit(out_path)`.

### P0-3. Сломана пагинация `--cursor` в `docs search`

`search_documents` уже режет кандидатов по `limit`, затем CLI режет `hits[start:start+limit]`
повторно. При `total=5, limit=2`: page1 `returned=2, cursor=2`; page2 (`--cursor 2`) → `returned=0`.
Cursor-контракт (Этап 5, §15.1.11/20) не работает.
**Фикс:** пагинация должна происходить до limit (или `search_documents` принимает offset).

### P0-4. RecursionError на глубоко вложенном JSON (краш вместо диагностики)

`parse_json('['*5000 + ']'*5000)` → `RecursionError` (и в `json.loads`, и в рекурсивном `_depth`).
Не ловится → traceback, exit 1. Любой пользовательский JSON может уронить CLI.
**Фикс:** ловить `RecursionError` в `parse_json` → `json.too_deep`; `_depth` сделать итеративным.

### P0-5. Двоеточие в именах файлов записей (непереносимо на Windows)

Дефолтный `path_template = "records/{entity_type}/{record_id}.json"` подставляет полный
`record_id` (`workout:2026-11-26-01`) → файл `records/workout/workout:2026-11-26-01.json`.
`:` запрещён в именах файлов на Windows. Портабельность (конкурентный анализ: 15/16) нарушена.
**Фикс:** дефолт на `{slug}` (часть после `:`), как в `path_template` workout-типа.

---

## P1 — существенные отклонения от конституции/плана

### P1-1. Ошибки в JSON-режиме не возвращают envelope

`main()` печатает `Error [code]: message` в stderr; stdout пуст. CLI guide постулат 10:
«единая политика ошибок (JSON envelope + exit code)»; конституция §8.2: «`--output json`: stdout —
только JSON». Агент в JSON-режиме получает непарсябельный текст вместо envelope.
**Фикс:** в `main()` при `--output json` (нужен доступ к выбранному режиму) печатать
`{schema_version, ok: false, data: {}, diagnostics: [{code, message}], next_actions: []}` в stdout
+ exit code. Неожиданные исключения — тоже в envelope (`operation.error`), не traceback.

### P1-2. `check`/`validate`: `ok: true` + exit 3

Envelope говорит «успех», exit code — «ошибка». Для MCP-маппинга (DoD: `issues_found` → успешный
result) `ok: true` осознан, но внутри CLI-контракта это противоречие (постулат 8: 0 — успех).
**Фикс:** решить и зафиксировать: либо `ok: false` при exit 3, либо exit 0 при `issues_found`
(тогда `--strict` — единственный путь к ненулевому exit). Сейчас — худшее из двух.

### P1-3. Record validation отсутствует (FR-6/FR-7 не выполнены)

- JSON Schema записей не проверяется: `schemas/` создаётся в `init`, но никогда не читается;
  `jsonschema` объявлена в зависимостях и **нигде не импортируется** (мёртвая зависимость).
- `entity_type` записи не сверяется с registry (неизвестный тип проходит `validate` молча;
  проверяется только в `records create`).
- Relation types не проверяются: cardinality, source/target type constraints отсутствуют;
  валидируются только dangling targets.
- `records create` после записи не делает post-validation (Этап 6 шаг 2: «повторный parse +
  schema + type + relation validation»).

### P1-4. Folder-local `.todoc.json` не реализован

SKILL/references обещают «Folder-local `<folder>/.todoc.json` holds declarative overrides»,
DoD требует «folder-local `.todoc.json` … задокументированы и протестированы». В коде загрузки
локальных конфигов нет: `custom/.todoc.json` с `{"doc_type": "adr"}` → `doc_type: unknown`.
Приоритет «nearest local config» (§5.1) отсутствует как класс.

### P1-5. Explicit front matter declaration игнорируется без правила

Приоритет §5.1: explicit declaration (front matter) — №2, выше dataset rules. Реализация знает
front matter только через rule match (`front_matter` в rules). Документ с `doc_type: glossary-entry`
без правила → `unknown`. Работает только потому, что дефолтные rules содержат
`glossary-by-front-matter`.

### P1-6. `RESERVED_ALIASES` мёртв

`{"harnes": "harness"}` объявлен, но нигде не используется. DoD: «`harnes` — только при явной
конфигурации/alias». Alias-механизм отсутствует.

### P1-7. Read-команды делают полный rebuild индекса при каждом вызове

`docs search/read`, `records list/query/aggregate/read`, `relations graph` вызывают
`ctx.rebuild_index()` — полный rescan + публикация поколения на **каждое чтение**.
Последствия: O(n) на каждый read (поиск и так перечитывает все файлы, см. P1-8), побочный
эффект записи в `.todoc/index` у read-only операций, рост числа поколений без GC.
План: индекс переиспользуется, `index rebuild` — явная операция; read должен читать CURRENT
(с проверкой staleness по `config_digest`).

### P1-8. Поиск не использует parse cache / индекс

Parse cache пишется в `scan_and_validate`, но **никогда не читается** (write-only).
`search_documents` перечитывает каждый файл целиком при каждом запросе. Этап 5: cache key с
версиями парсера/схем, инвалидация, повреждённый кэш → пересоздание. Сейчас кэш — декорация.

### P1-9. Мёртвые флаги (принимаются, не действуют)

| Флаг | Команда | Факт |
|---|---|---|
| `--all` | `validate` | игнорируется (всегда полный validate) |
| `--if-hash-new` | `records create` | параметр не используется |
| `--template` | `docs new` | только эхо в ответе; контент всегда `# title` |
| `--scope` | `doctor` | не используется |
| `--fix` | `doctor` | только эхо `fix_mode`; ничего не чинит |
| `--max-depth` | `docs tree` | только эхо |

Постулат 2 (одинаковые флаги — одинаковый смысл) и честность контракта нарушены: флаг,
который ничего не делает, хуже отсутствующего.

### P1-10. Нет глобального `--out`/`--report-file`, нет `--details`/`--fields`

Конституция §8.2 вводит `--out` как общий режим; Этап 5/§15.1.12/20 требуют `--report-file`,
`--details`/`--fields`. Есть только `types guide --out` (без containment, см. P0-2).
Большие отчёты `validate` нельзя выгрузить в файл.

### P1-11. Нет группировки ошибок в `validate`

§15.1.19: итоги по severity/category, порог показа (эвристика 5), `total`/`shown`/`truncated`/
cursor/путь к деталям. Сейчас — плоский список всех диагностик. На большой базе вывод
нечитаем для агента.

### P1-12. `records aggregate` расходится с контрактом

- Дефолт `entity_type or "workout"` захардкожен в CLI — магическое значение.
- Конституция §8.1: `--metric monthly_volume_by_muscle` (именованная метрика из дескриптора типа)
  и `--group-by date.month,muscle` (мульти-группировка с date-part). Реализация: `--metric` —
  имя поля, `--group-by` — одно поле, `date.month` даёт `unknown` (строка не индексируется).
- Нет metric definitions / timezone policy из entity type descriptors (Этап 5 шаг 7).

### P1-13. Markdown-ссылки: regex по сырым строкам → ложные срабатывания

Модуль заявляет «headings/links from tokens, never regex», но ссылки извлекаются `_LINK_RE`
по сырым строкам, **включая code fences**. Доказано: `[example](missing-in-code.md)` внутри
`` ``` `` даёт `markdown.link.target_missing`. Также не поддерживаются reference-style
ссылки `[text][ref]` и autolinks. Для валидатора это источник ложных диагностик.

**Статус на 2026-11-25: закрыто.** Ссылки извлекаются из токенного потока markdown-it-py
(`_token_links`, `_code_regions`, `_inline_code_spans` в `adapters/formats/markdown.py`);
`_INLINE_LINK_RE` оставлен только для вычисления колонок уже подтверждённой ссылки и в
обнаружении не участвует. Проверено прогоном: документ с тремя битыми целями — обычной,
внутри ```` ``` ```` и внутри inline-кода — даёт ровно одну диагностику, на обычную ссылку.
Reference-style поддерживается: `[текст][ref]` + `[ref]: ref-missing.md` даёт
`markdown.link.target_missing` с разрешённой целью. Autolink `<https://…>` диагностики
не даёт. Соответствует таблице форматов ссылок в `docs/state/05-formats.md`.

### P1-14. Порты E1–E10 не определены

`ports/__init__.py`, `adapters/indexes/`, `adapters/cache/`, `adapters/search/` — пустые (0 байт).
План §2.2 требует Protocol-порты как точки расширения для `.after.md` (embeddings, MCP, web UI).
Сейчас адаптеры — конкретные модули с прямыми импортами; вставка E4/E5/E6/E8/E10 потребует
рефакторинга, а не подключения.

### P1-15. Нет CI, contract-тестов, LICENSE

- `tests/contract/` и `tests/fixtures/` пусты (план §6: contract tests; §15.4: wheel вне checkout,
  Obsidian smoke, Skill validator).
- Нет `.github/workflows/` (Этап 7.5: CI-gate `validate --strict`, SARIF, retrieval eval).
- Нет файла `LICENSE`, хотя `pyproject.toml` заявляет `license = {text = "MIT"}` — packaging warning.

### P1-16. Skill неполон по Этапу 7

Отсутствуют `references/index.md` (generated оглавление root), `data_structure.md`-аналог
(per-dir derived навигация), `log.md` (append-only derived аудит). `type-system.generated.md` —
статический стаб, а не generated из датасета (команда `types guide` существует, но файл в репо
не сгенерирован и не помечен marker/version).

### P1-17. `doctor` тривиален, `index status` не показывает staleness

Проверки: config loads / index exists / python version. Нет категорий/уровней по §15.1.17,
нет проверки staleness индекса (`config_digest` считается при publish, но нигде не сравнивается).
`--fix` — пустышка (см. P1-9).

### P1-18. Нет dataset-level lock и GC поколений

Этап 5 шаг 1: «Dataset-level lock для параллельных writers» — отсутствует (два параллельных
`index rebuild` могут гоняться на CURRENT). Поколения индекса накапливаются бесконечно.

### P1-19. Необработанные исключения → traceback вместо envelope

- `docs search --cursor abc` → `ValueError` traceback.
- `docs read --line-range abc` → `ValueError` traceback.
- `aggregate`: `float("abc")` → `ValueError`; смешанные типы в `$gte/$lte` → `TypeError`.
- `records query`: `filters` не-dict в QuerySpec → `AttributeError`.
- `main()` ловит только `TodocError`/`ClickException`.

### P1-20. `docs read --section`: `heading_path` неполный; search `heading_path` не breadcrumb

`docs read` возвращает `heading_path: [selected.title]` вместо полного пути от корня.
`search` возвращает первые 3 заголовка документа, а не breadcrumb к совпадению (Этап 5:
«`heading_path` (breadcrumb)»). Нет `matched_count` (§15.1.11).

---

## P2 — частичные реализации, мёртвый код, мелочи

1. **Search matching — substring, не токены:** `t in lowered` («token» матчит «tokens»);
   сниппет ищет подстроку. Для MVP допустимо, но расходится с tokenize-дизайном.
2. **Search ranking примитивен:** `title_hits*10 + len(matched)`, без eval/benchmark
   (Этап 5 шаг 5: FTS5 vs альтернатива, frozen queries, Recall@k/MRR/nDCG). Порты E4/E5 не
   выделены (см. P1-14).
3. **`docs edit`/`fix` preview без diff:** только эхо ops/fix dict; Этап 6 требует preview/diff.
4. **`docs edit` patch-формат недокументирован:** JSON `{"ops": [{"line", "text"}]}` (только
   замена строк, без insert/delete) известен только из тестов; конституция показывает
   `./change.diff`. Нет в README/SKILL.
5. **`records query` QuerySpec не валидируется:** allowlisted AST заявлен (Этап 5 шаг 7),
   фактически — произвольный dict без проверки ключей/операторов.
6. **`service` дублирует парсинг записей** из `validator._validate_records` (два места читают
   JSON records; service использует `json.loads` без dup-key detection).
7. **`validator`: параметр `registry` не используется;** `_check_markdown_links` перечитывает
   файл, уже прочитанный в цикле (двойное чтение).
8. **`service`: смешанные типы в `diags`** (Diagnostic-объекты + dict для folder conflicts),
   `hasattr(d, "to_dict")` костыль; тернарник `status if != "ok" else "ok"` избыточен.
9. **`cli`: модульный глобал `_group_roots`** для fallback `--root` группы — хрупкий дизайн
   (дублирование `--root` на группе и каждой подкоманде). Лучше: только на группе +
   `click.pass_context`.
10. **`cli`: `check`/`validate` используют `sys.exit(3)`** в обход error-модели (см. P1-2);
    `scan` делает полную валидацию вопреки docstring «without writing indexes» (и пишет parse cache).
11. **`cli`: `docs tree` — hardcoded `[:50]`** без cursor; `docs read` CSV без `truncated`.
12. **`envelope` table/markdown mode:** вложенные структуры печатаются Python repr
    (`{'a': 1}`), а не читаемо. «Одни и те же machine facts» — формально да, практически нет.
13. **`types guide` generated файл без marker/version** (§15.4: generated с marker/version/diff).
14. **`config.init_dataset` пишет control files неатомарно** (`write_text`); обрыв посередине →
    полуинициализированный `.todoc/`.
15. **`config`: нет `identities.json`** (Этап 5 шаг 2: versioned identity-map; сейчас ID =
    front matter `id` или путь — переименование файла меняет ID, если нет front matter).
16. **`registry`: meta без parser/type versions** на уровне документов (Этап 5 шаг 1 требует
    parser/type versions в generations).
17. **`scanner`: symlink loop** при `follow_symlinks=true` (терминирует по OSError на длинном
    пути, но с лишней работой); `entry.stat` + повторное открытие в `file_hash` (TOCTOU-мелочь);
    `atomic_write` делает fsync файла, но не директории.
18. **`resolver`: glob `**` вне сегмента** (`a**b` → `a.*b` пересекает `/`); trailing `/`
    «directory only» заявлен в docstring, но не реализован.
19. **`markdown`: YAML-lite** — числа остаются строками (`count: 42` → `"42"`), нет вложенных
    структур; заголовки сохраняют raw markdown (`**Bold**`) в outline.
20. **`csvfmt`: Sniffer** по первым 4096 символам может ошибиться на экзотике; строки с
    wrong width молча выпадают из rows (только error в списке).
21. **`descriptors._load_dir` молча пропускает** директории без `type.json` (нет warning).
22. **`docs new`: нет front matter** (`id`/`title`), slug из кириллицы — кириллический slug
    (допустимо, но стоит зафиксировать политику).
23. **`records create`: запись без `schema_version`** в теле record; нормализации units/date нет
    (Этап 6 шаг 3 требует units/date normalization).
24. **`aggregate`: `completeness: "complete"` захардкожен;** bool является int в Python
    (`True` → 1.0 в сумме) — мелочь, но стоит отсекать.
25. **`query_records`: отрицательный/нулевой limit** не валидируется.
26. **Нет stdin/`-`** для `--input-file`/`--patch-file` (CLI guide постулат 4: «не требовать
    временный файл, если безопасно stdin»).
27. **`check --strict` со warnings-only:** exit 3, но `status: "ok"` — несогласованность
    (см. P1-2).
28. **`pyproject`: нет ruff/mypy-конфига;** `jsonschema` — мёртвая зависимость (см. P1-3);
    `readme = "README.md"` существует ✓, но LICENSE отсутствует (см. P1-15).
29. **`README.md` минимален:** нет архитектуры, портов, списка команд с примерами, политики
    exit codes. Для пилота недостаточно.
30. **`SKILL.md`:** `next_actions` описан как «hints», но по факту их эмитит только `docs search`;
    остальные команды — без подсказок (не нарушение, но несогласованность с §15.1.26).

---

## Что соответствует лучшим традициям (сохранить)

- **Envelope + exit codes:** структура `{schema_version, ok, data, diagnostics, next_actions}`,
  карта 0–6 задокументирована в `errors.py`; `next_actions` — argv-массив (не строка) ✓
  (конституция §8.2, постулат 26).
- **Multi-root изоляция:** каждый результат с `dataset_id`, `--root` повторяется, `TODOC_ROOT` ✓
  (DoD). Релокация DATA_ROOT протестирована (dataset_id переживает переезд) ✓.
- **Resolver:** приоритеты + literal-segments tie-break; равные правила с разными назначениями →
  `config.ambiguous_rule` diagnostic, не silent winner ✓ (§5.1, §15.3.8).
- **Hard-excludes до классификации** (`.todoc`, `.git`, `.obsidian`, …), symlink containment
  в сканере, детерминированный обход (sorted) ✓ (P1, §15.4 безопасность).
- **Registry generations:** temp → validate → rename → atomic CURRENT; при ошибке старое
  поколение остаётся CURRENT; `config_digest` ✓ (Этап 5 шаг 1, за вычетом lock/GC).
- **Review-first writes:** preview default, `expected_hash`, no-overwrite, atomic temp+replace,
  advisory suggestions без auto-apply ✓ (Этап 6, постулат 14).
- **Aggregate:** units/formula/incoming_ids/completeness; unit mismatch → отказ, не угадывание ✓
  (конституция §6.7, постулат 11).
- **Search:** deterministic rank + tie-break by id; `relevance_method: "lexical"` без сырых
  scores; `snippet_truncated`; byte budget ✓ (постулаты 11, 23).
- **Markdown headings через tokens** (не regex), anchors с дедупликацией, heading tree ✓;
  CSV: dialect/header/width/max_rows; JSON: dup-key/depth/RFC6901 pointer ✓ (FR-4).
- **Discovery:** корневой `todoc` без аргументов печатает оглавление ✓ (постулат 16);
  `doctor`/`status` разделены ✓ (постулат 17, за вычетом глубины проверок).
- **Файлы — source of truth**, индекс/кэш — derived и перестраиваемые ✓ (конкурентный анализ:
  portability 15/16 сохранена).
- **100% покрытие тестами** (1797 statements, 544 branches) — как инженерная дисциплина;
  но см. слепоту ниже.

## Системная слепота тестов

100% line/branch coverage при 5 P0-багах: все CLI-тесты идут через `CliRunner` **in-process**
(один `PYTHONHASHSEED`, один процесс), поэтому не ловятся межпроцессные дефекты (P0-1),
а containment/pagination проверялись только на happy path. Для пилота нужны:
subprocess contract-тесты (`todoc` как бинарь), тесты на `PYTHONHASHSEED` variation,
fuzz/property-тесты парсеров (глубокая вложенность, бинарный мусор), security-тесты
(containment для всех write-путей).

---

## Рекомендуемый порядок исправлений

1. **P0-1** детерминированные diagnostic ID + subprocess-тест `validate → fix`.
2. **P0-2** единый `resolve_within_root` для всех write-путей + security-тесты.
3. **P0-3** пагинация в `search_documents` (offset до limit) + тест на 2 страницы.
4. **P0-4** `RecursionError` → `json.too_deep`; итеративный `_depth`.
5. **P0-5** дефолтный `path_template` на `{slug}`.
6. **P1-1/P1-2** единая error-политика: JSON envelope на ошибках; решить ok/exit для check.
7. **P1-3** record validation: jsonschema по `schemas/`, сверка entity_type, relation_types
   (хотя бы dangling + unknown type), post-validation в `records create`.
8. **P1-7/P1-8** read из CURRENT без rebuild; parse cache реально читать (или удалить);
   staleness по `config_digest` в `index status`/`doctor`.
9. **P1-4/P1-5/P1-6** folder-local `.todoc.json`, explicit front matter priority, alias-механизм.
10. **P1-9** удалить или реализовать мёртвые флаги; **P1-10/P1-11** `--report-file`,
    группировка ошибок; **P1-12** aggregate по контракту (без hardcoded workout).
11. **P1-13** ссылки из токенов (или хотя бы пропуск code fences); **P1-14** порты E1–E10
    как Protocols; **P1-15** CI + contract-тесты + LICENSE; **P1-16** Skill index/data_structure/log.
12. **P1-19** валидация всех пользовательских входов (cursor, line-range, QuerySpec, float).

## Что НЕ является нарушением (осознанные MVP-ограничения)

Embeddings/vector/hybrid/rerank, web UI, MCP server, Task/Plan/Idea lifecycle, cloud sync,
YAML/XLSX/PDF/SQLite, OKF profile, SARIF, `link` fetch — всё это в `.after.md` по плану (§8 defer),
их отсутствие — не дефект. FTS5 vs in-memory lexical — выбор backend по benchmark (Этап 5 шаг 5)
ещё не сделан, но lexical MVP допустим; претензия только к отсутствию benchmark и портов.
