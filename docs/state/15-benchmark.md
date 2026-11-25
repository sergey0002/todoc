# 15. Бенчмарк качества и сравнение с конкурентами

Дата измерения: **2026-11-25**. Прогон: `python3 bench/run_benchmark.py --venv /tmp/comp`
(если venv с конкурентами недоступен — `--competitors-from bench/results/benchmark.json`: блок
конкурентов берётся из прошлого прогона и помечается `reused_from`).
Критерии: [bench/criteria.md](../../bench/criteria.md) (K1–K30). Результаты:
[bench/results/benchmark.json](../../bench/results/benchmark.json) и
[bench/results/benchmark.md](../../bench/results/benchmark.md).

Корпус: копия демо-датасета в `/tmp/todoc-bench-corpus` — **256 документов, 159 записей,
140 отношений** (248 документов демо: 90 md + 1 csv + 157 json; плюс 8 файлов с намеренно
внесёнными дефектами как ground truth).
`demo/` при прогоне не изменяется; входные файлы для проверок записи лежат вне DATA_ROOT.

## 1. Итог

**29.5 из 30 (98 %)**. 29 критериев `pass`, один `partial` (K7 — точные локации).

| Группа | Критерии | Балл |
|---|---|---|
| Контракт | K1–K5 | 5.0 / 5 |
| Корректность | K6–K10 | 4.55 / 5 |
| Детерминизм | K11–K13 | 3.0 / 3 |
| Безопасность записи | K14–K16 | 3.0 / 3 |
| Ограниченное чтение | K17–K21 | 5.0 / 5 |
| Поиск | K22–K24 | 2.97 / 3 |
| Устойчивость | K25–K26 | 2.0 / 2 |
| Производительность | K27 | 1.0 / 1 |
| Качество кода | K28–K29 | 2.0 / 2 |
| Портабельность | K30 | 1.0 / 1 |

Ключевые измеренные значения:

- **Детекция дефектов:** precision 1.00, recall 1.00, **F1 1.00** (TP=9, FN=0, FP=0) на 9 внесённых дефектах.
- **Поиск:** Recall@3 0.94, Precision@3 0.94, **MRR 1.00** на 12 запросах с независимой разметкой.
- **Латентность (медианы):** `status` 158 мс, `types list` 150 мс, `validate` 1002 мс, `records list` 1060 мс,
  `docs read` 1085 мс, `docs search` 1627 мс — все в бюджете, но чтение/поиск упираются в пересборку индекса (см. §5).
- **Тесты:** 420 passed, покрытие **100 %** (2491 инструкция, 868 веток, 0 пропущенных).
- **Портабельность:** 8 из 8 подкритериев; front matter всех 89 md-файлов разбирается внешним PyYAML.

## 2. Дефекты, которые нашёл бенчмарк, и что сделано

Каждый пункт воспроизведён командой до и после; «проверено» — критерий бенчмарка, который закрыл проблему.

| № | Дефект (было) | Стало | Проверено |
|---|---|---|---|
| 1 | `id` диагностик считался через `hash()` → разный в каждом процессе; `fix --diagnostic` по сохранённому ID не работал | `stable_id()` = SHA-256 от `path + code + message` (12 символов) | K13 |
| 2 | `types guide --out /tmp/...` писал вне DATA_ROOT (exit 0, файл создан) | `_contained_out()`: resolved-путь обязан лежать в корне, иначе `access.outside_data_root`, **exit 4**; `../..` тоже отклоняется | K16 |
| 3 | `docs new --dir ../../outside` падал сырым `PermissionError` с traceback | тот же containment, конверт и exit 4 | тест `test_docs_new_dir_cannot_escape_root` |
| 4 | `--cursor` возвращался, но не применялся: вторая страница — 0 результатов при `total 42` | `search_documents(..., offset=…)`, `truncated` считается от смещения | K24 |
| 5 | `--cursor abc` и `--line-range abc` → `ValueError`, exit 1, пустой stdout | `_parse_offset()`/`_parse_line_range()`: `usage.invalid_cursor`, `usage.invalid_line_range`, exit 3, конверт | K26 |
| 6 | Ошибки уходили в stderr текстом, stdout пуст | `_emit_error()`: один JSON-конверт с `ok: false`, диагностикой и `next_actions` + человекочитаемая строка в stderr | K2, тест `test_error_is_a_json_envelope` |
| 7 | `check`/`validate` возвращали `ok: true` при exit 3, а диагностики лежали только внутри `data` | `_emit_result()`: `ok` согласован с кодом выхода, диагностики — в конверте, `next_actions` ведёт в `fix --preview` | K4 |
| 8 | `docs read --section` резал фиксированные 41 строку и залезал в следующий раздел; `heading_path` = `[заголовок]` | граница раздела = следующий заголовок того же уровня или выше; окно ≤ 40 строк; `truncated`, `line_start`/`line_end`; breadcrumb через `heading_path_for()` | K18 |
| 9 | `heading_path` в поиске = первые три заголовка документа, а не путь к совпадению | `_breadcrumb()`: путь к заголовку, содержащему строку совпадения | K22 |
| 10 | Номера строк в сниппетах поиска считались по синтетическому тексту (`title + headings + text`) → сдвиг на 2 | `_document_text()` возвращает `(match_text, source_text)`; provenance — по исходному файлу | K22 |
| 11 | `records create` проверял только `required_fields`: значение вне `enum` схемы записывалось в файл | схема сущности применяется при создании → `record.schema_violation`, exit 3, файл не создаётся | K10, тест `test_records_create_enforces_the_entity_schema` |
| 12 | `records aggregate` сверял единицы **до** группировки: любой разнородный набор метрик давал `query.unit_mismatch`, даже с `--group-by` | проверка на группу, в ответе `group_units`; смешение единиц внутри одной группы по-прежнему ошибка | тест `test_aggregate_mixed_units_across_groups_is_allowed` |
| 13 | `docs edit --patch-file` с JSON не той формы (`[...]` вместо `{"ops": [...]}`) падал с `AttributeError` и traceback | проверка формы патча → `edit.invalid_patch`, exit 3, конверт | тест `test_docs_edit_patch_shape_is_validated_in_process` |
| 14 | `docs new --template` принимал значение и возвращал его в ответе, но содержимое всегда было `# <заголовок>` | флаг принимает id типа или путь к шаблону; `create_document_plan()` подставляет плейсхолдеры и проверяет структуру типа до записи (`types.template_invalid`) | тест `test_docs_new_uses_the_type_template` |
| 15 | Неизвестные поля в `type.json` принимались молча: `required_sections` проходило `check-config`, отображалось в `types show` и никогда не применялось | `KIND_FIELDS` — список допустимых полей на вид типа; `check-config` даёт `config.unknown_field`, `config.invalid_schema`, `config.template_missing`, `config.prompt_missing`, exit 3 | тест `test_check_config_reports_unknown_field_and_missing_template` |
| 16 | `id` диагностик `config.ambiguous_rule` для папок всё ещё считался через `hash()` (остаток дефекта №1) | тот же `stable_id()`; проверено четырьмя запусками — id совпадают | тест `test_ambiguous_rule_ids_are_stable` |
| 17 | У JSON-диагностик и диагностик записей не было локаций | `JsonError` (подкласс `str`, чтобы не ломать существующие потребители) несёт `line`/`column` из `JSONDecodeError`; у записей — строка ключа; у отношений — RFC 6901 pointer `/relations/N` | K7 (частично, см. §3) |

Побочно найденное и исправленное в демо: 46 из 144 записей имели `title` в литеральных кавычках
(генератор копировал сырую строку front matter) — исправлено, `validate --all` даёт 0 диагностик.

## 3. Единственный не закрытый критерий: K7 (локации)

6 из 11 диагностик несут номер строки; у остальных адрес всё равно точный, но другого типа:

| Диагностика | Адрес | Почему |
|---|---|---|
| `markdown.link.target_missing`, `markdown.front_matter.yaml_unsafe` | `line`, `column` | есть |
| `json.syntax_error` | `line`, `column` | есть (из `JSONDecodeError`) |
| `record.schema_violation` ×3 | `line` ключа + `pointer` | есть |
| `relation.unknown_type`, `relation.dangling_target` | `pointer` `/relations/N[/target/id]` | строки нет: связь адресуется структурно, это точнее строки |
| `json.duplicate_key`, `json.invalid_constant`, `json.too_deep` | — | `object_pairs_hook` и `parse_constant` в `json` не получают позицию; нужен свой сканер |

Порог K7 (≥ 0.90) сознательно оставлен недостижимым без токенизатора JSON: занижать требование
к себе означало бы спрятать разрыв с FR-4.3 («точные ranges у каждой диагностики»).

## 4. Сравнение с конкурентами (измерено, не по документации)

Устанавливались и запускались в этой среде только два инструмента; оба прогнаных на той же копии демо.

### 4.1 Измеренные факты

| Показатель | **todoc** | `obsidiantools` 0.11.0 | `open-knowledge` (`ok`) 0.28.2 |
|---|---|---|---|
| Интерфейс | CLI, 26 команд, JSON-конверт | Python API (нет CLI) | CLI, 12 подкоманд + сервер |
| Время на корпусе 256 док. | `validate` 0.97 с | `gather().connect()` **7.11 с** | `status` 0.61 с, `diagnose` 0.52 с |
| Заметок/документов распознано | 256 (md 90 + csv 1 + json 157 + дефекты) | 90 (только `.md`) | не применимо (не индексатор) |
| Битые ссылки | 1 (внесённая) | **1** — та же (`broken-link -> does-not-exist.md`) | не проверяет |
| Front matter | 89/89 разбираются, 0 предупреждений | 88 записей, **3 предупреждения** о неразобранном YAML | не проверяет |
| Backlinks / граф | `relations graph` по типизированным рёбрам (127 отношений) | `backlinks_index` 88, `isolated_notes` 86 | нет |
| Записи в корпус при чтении | 0 (K12) | 0 | 0 |
| Работа без сети/БД | да (K30: 8/8) | да | нет: сервер, эмбеддинги, git-sync |
| `diagnose`/валидация | 11 диагностик с кодами и локациями | нет кодов/локаций (предупреждения в stderr) | `ok diagnose` — **exit 1** вне инициализированного проекта |

Совпадение по битой ссылке — содержательный результат: независимый инструмент на том же корпусе
находит ровно тот дефект, который todoc заявляет в ground truth, а «3 предупреждения» obsidiantools —
это тот самый YAML-небезопасный front matter, из-за которого в этой итерации появилось правило
кавычек (K8) и диагностика `markdown.front_matter.yaml_unsafe`.

### 4.2 Возможности: кто что умеет

| Возможность | todoc | obsidiantools | open-knowledge |
|---|---|---|---|
| Валидация с кодами и локациями | ● | ◐ (предупреждения) | ○ (`diagnose` падает) |
| Типовая система (dir/doc/entity/relation + JSON Schema) | ● | ○ | ○ |
| Ограниченное чтение (section/pointer/columns/rows/budget) | ● | ◐ (`get_readable_text`) | ◐ |
| Детерминированный поиск без эмбеддингов | ● | ○ | ◐ (нужен ключ провайдера) |
| Граф/backlinks | ◐ (типизированные рёбра, нет метрик графа) | ● (backlinks, isolated, graph) | ○ |
| Запись с review-first планом | ● | ○ | ◐ (`ok` пишет, план не показывает) |
| MCP-сервер | ○ | ○ | ● |
| Agent Skills / SKILL.md | ○ | ○ | ● (`ok skills`, `repair-skills`) |
| Sync/шаринг | ○ (git вручную) | ○ | ● (`sync/push/pull/share`) |
| UI/превью | ○ | ○ | ● (`ok preview`, `ok ui`) |
| Портабельность (plain files, без БД/сервера) | ● | ● | ○ |

● — есть, ◐ — частично, ○ — нет. Флаги `mcp/skills/sync/ui/search` у `open-knowledge` взяты из
фактического `ok --help` (см. `open-knowledge-capabilities` в JSON результатов); `validate`,
`index`, `graph`, `types`, `records` в нём отсутствуют.

### 4.3 Вывод

todoc выигрывает там, где заявлен: переносимость, контракт для агента, типовая система и
валидация с локациями — и это единственные пункты, где конкуренты либо молчат, либо падают.
Проигрывает в «обвязке»: нет MCP-сервера, SKILL.md, синхронизации, UI и метрик графа.
Отклонены как невоспроизводимые здесь: `basic-memory` (Python ≥ 3.12, 49 зависимостей),
`khoj` (`torch`/`transformers`, 79 зависимостей), `okf` 0.1.0 (заглушка), `mdkb` (нет на PyPI).

## 5. Что улучшать дальше и что для этого нужно

| Приоритет | Улучшение | Цель по критериям | Что нужно |
|---|---|---|---|
| P0 | Индекс не пересобирается на каждое чтение: валидация по хешу поколения | K27: `docs search` 1.63 с → < 200 мс | ничего внешнего: `generation_id` + `mtime`/`hash`-проверка в `DatasetContext` |
| P0 | Сборка мусора поколений и рабочий кэш парсинга | K27, место на диске (в демо 36 поколений) | ничего внешнего |
| P1 | Позиции в JSON-диагностиках (`duplicate_key`, `invalid_constant`, `too_deep`) | K7: 0.55 → 1.0 | свой сканер JSON **или** `jsonscanner`/`ijson` (внешняя зависимость, офлайн-режим сохраняется) |
| P1 | Метрики графа: backlinks, isolated notes, центральность | новая группа критериев K31+ | ничего внешнего (обход по `relations`); для визуализации — `graphviz` (опционально) |
| P1 | CI + LICENSE | K28 в автоматическом режиме | GitHub Actions (без новых зависимостей) |
| P2 | MCP-адаптер | закрывает разрыв с `open-knowledge` | `mcp` (официальный SDK) — только для optional extra `todoc[mcp]` |
| P2 | Семантический поиск как второй метод ранжирования | K22 на длинных запросах | `sqlite-vec` **или** `sentence-transformers` (тяжело, ~2 ГБ) — только optional extra, лексика остаётся дефолтом |
| P2 | SKILL.md + авто-ремонт навыков | parity с `ok skills` | ничего внешнего |
| P2 | Санитизация `record_id` в именах файлов (двоеточие) | K30 на Windows | ничего внешнего |

Правило для внешних зависимостей: ядро остаётся офлайновым и без БД (K30), всё тяжёлое —
в optional extras. Иначе теряется главное измеренное преимущество перед `open-knowledge`.

## 6. Как воспроизвести

```bash
python3 bench/run_benchmark.py --venv /tmp/comp   # 30 критериев + конкуренты (~90 с)
python3 bench/run_benchmark.py --quick            # меньше повторов латентности
python3 bench/run_benchmark.py --skip-competitors # только todoc
```

Прогон сам создаёт копию датасета, вносит 9 дефектов, измеряет латентность медианой по повторам
и пишет `bench/results/`. Код выхода: 0 если нет `fail`, иначе 1.

## Связанные разделы

- [01-overview.md](01-overview.md) — цели и границы продукта, под которые написаны критерии.
- [02-architecture.md](02-architecture.md) — границы портов и адаптеров.
- [11-known-issues.md](11-known-issues.md) — что осталось неисправленным.
- [13-demo-dataset.md](13-demo-dataset.md) — устройство демо-датасета, на котором идёт измерение.
- [../../demo/competitors/basic-memory.md](../../demo/competitors/basic-memory.md) — пример карточки конкурента (всего их 30 в `demo/competitors/`).
- [../plan/competitive-analysis.md](../plan/competitive-analysis.md) — критерии C1–C16, из которых выведены K*.
