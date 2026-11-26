---
id: doc:state-benchmark
title: "Состояние: бенчмарк качества и сравнение с конкурентами"
doc_type: reference
lang: ru
source: docs/state/15-benchmark.md
copied: true
created: 2026-11-26
updated: 2026-11-26
tags: [references, reference, конкурентами, состояние]
---

# 15. Бенчмарк качества и сравнение с конкурентами

Дата измерения: **2026-11-25**. Прогон: `python3 bench/run_benchmark.py --venv /tmp/comp`
(если venv с конкурентами недоступен — `--competitors-from bench/results/benchmark.json`: блок
конкурентов берётся из прошлого прогона и помечается `reused_from`).
Критерии: bench/criteria.md (K1–K30). Результаты:
bench/results/benchmark.json и
bench/results/benchmark.md.

Корпус: копия демо-датасета в `/tmp/todoc-bench-corpus` — **266 документов, 161 записей,
140 отношений** (258 документов демо: 98 md + 1 csv + 159 json; плюс 8 файлов с намеренно
внесёнными дефектами как ground truth).
`demo/` при прогоне не изменяется; входные файлы для проверок записи лежат вне DATA_ROOT.

## 1. Итог

**30.0 из 30 (100 %)**. Все 30 критериев `pass`.

Последним закрыт K7 (точные локации): доля диагностик с номером строки была 0.55, стала
**1.00** — см. [P1-8](11-known-issues.md).

| Группа | Критерии | Балл |
|---|---|---|
| Контракт | K1–K5 | 5.00 / 5 |
| Корректность | K6–K10 | 5.00 / 5 |
| Детерминизм | K11–K13 | 3.00 / 3 |
| Безопасность записи | K14–K16 | 3.00 / 3 |
| Ограниченное чтение | K17–K21 | 5.00 / 5 |
| Поиск | K22–K24 | 2.97 / 3 |
| Устойчивость | K25–K26 | 2.00 / 2 |
| Производительность | K27 | 1.00 / 1 |
| Качество кода | K28–K29 | 2.00 / 2 |
| Портабельность | K30 | 1.00 / 1 |

Ключевые измеренные значения:

- **Детекция дефектов:** precision 1.00, recall 1.00, **F1 1.00** (TP=9, FN=0, FP=0) на 9 внесённых дефектах.
- **Поиск:** Recall@3 0.94, Precision@3 0.94, **MRR 1.00** на 12 запросах с независимой разметкой.
- **Латентность (медианы):** `status` 128 мс, `types list` 153 мс, `docs read` 150 мс,
  `records list` 150 мс, `validate` 248 мс, `docs search` 642 мс — все в бюджете. Пересборки
  индекса на каждое чтение больше нет (закрыто P1-1/P1-2), поэтому чтение подешевело
  на порядок против прогона `10:42:29` (там `docs read` 1085 мс, `docs search` 1627 мс).
- **Тесты:** 988 passed, покрытие **100 %** (4570 инструкций, 1676 веток, 0 пропущенных) —
  на момент прогона `2026-11-25 18:56:48`.
- **Портабельность:** 8 из 8 подкритериев; front matter всех 98 md-файлов разбирается внешним PyYAML.

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
| 17 | У JSON-диагностик и диагностик записей не было локаций | `JsonError` (подкласс `str`, чтобы не ломать существующие потребители) несёт `line`/`column`; у записей — строка ключа; у отношений — RFC 6901 pointer + строка ключа | K7 (закрыт, см. §3) |

Побочно найденное и исправленное в демо: 46 из 144 записей имели `title` в литеральных кавычках
(генератор копировал сырую строку front matter) — исправлено, `validate --all` даёт 0 диагностик.

## 3. Локации диагностик: как закрыли K7

На первом прогоне K7 был `partial`: номер строки был у 6 диагностик из 11, порог — ≥ 0.90.
Причина была структурной, а не косметической: `object_pairs_hook` и `parse_constant` в `json`
получают уже разобранные значения, так что позиция терялась ещё до диагностики.

Что сделано — два независимых шага, оба без внешних зависимостей:

| Шаг | Что дал | Результат |
|---|---|---|
| Свой позиционный сканер JSON в jsonfmt.py (`_iter_tokens`, `_line_col`, `_duplicate_key_offset`, `_constant_offset`, `_depth_limit_offset`) | `json.duplicate_key`, `json.invalid_constant`, `json.too_deep` получают `line`/`column` | 9 из 11 |
| Тексты записей передаются в `validate_relations` | `relation.unknown_type`, `relation.dangling_target`, `relation.missing_target`, `relation.malformed` получают `line`/`column` вдобавок к точному `pointer` | 11 из 11 → K7 = 1.0 |

Теперь номер строки есть у всех 11 диагностик корпуса, включая JSON-коды и отношения:

| Диагностика | Адрес |
|---|---|
| `markdown.link.target_missing`, `markdown.front_matter.yaml_unsafe` | `line`, `column` |
| `json.syntax_error` | `line`, `column` (из `JSONDecodeError`) |
| `json.duplicate_key`, `json.invalid_constant`, `json.too_deep` | `line`, `column` (из сканера) |
| `record.schema_violation` ×3 | `line` ключа + `pointer` |
| `relation.unknown_type`, `relation.dangling_target` | `pointer` `/relations/N[/target/id]` + `line`/`column` ключа |

Сканер не дублирует разбор и не решает валидность — он только считает смещения, никогда не
бросает исключение и не влияет на семантику. Позиции ищутся в уже найденном месте и
подставляются в исключение перед его созданием.

## 4. Сравнение с конкурентами (измерено, не по документации)

Устанавливались и запускались в этой среде только два инструмента; оба прогнаных на той же копии демо.

### 4.1 Измеренные факты

| Показатель | **todoc** | `obsidiantools` 0.11.0 | `open-knowledge` (`ok`) 0.28.2 |
|---|---|---|---|
| Интерфейс | CLI, 46 команд, JSON-конверт | Python API (нет CLI) | CLI, 12 подкоманд + сервер |
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
| ~~P0~~ ✅ | Индекс не пересобирается на каждое чтение: валидация по дайджесту корпуса | K27 | закрыто (P1-1): один снимок в `.todoc/index/current/`, инвалидация по `corpus_digest` |
| ~~P0~~ ✅ | Сборка мусора поколений и рабочий кэш парсинга | K27, место на диске | закрыто: поколения заменены одним снимком (P1-2), кэш парсинга читается и сбрасывается при записи (P1-3), 3.17× на демо |
| ~~P1~~ ✅ | Позиции в JSON-диагностиках (`duplicate_key`, `invalid_constant`, `too_deep`) | K7: 0.55 → 1.0 | свой сканер JSON; внешняя зависимость не понадобилась — см. §3 |
| P1 | Метрики графа: backlinks, isolated notes, центральность | новая группа критериев K31+ | ничего внешнего (обход по `relations`); для визуализации — `graphviz` (опционально) |
| ~~P1~~ ✅ | CI + LICENSE | K28 в автоматическом режиме | `.github/workflows/tests.yml` + корневой `LICENSE` (MIT) |
| P2 | MCP-адаптер | закрывает разрыв с `open-knowledge` | `mcp` (официальный SDK) — только для optional extra `todoc[mcp]` |
| P2 | Семантический поиск как второй метод ранжирования | K22 на длинных запросах | `sqlite-vec` **или** `sentence-transformers` (тяжело, ~2 ГБ) — только optional extra, лексика остаётся дефолтом |
| P2 | SKILL.md + авто-ремонт навыков | parity с `ok skills` | ничего внешнего |

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

Ставить нужно вместе с `extras [dev]` (`python3 -m pip install -e ".[dev]"`): оттуда берётся
PyYAML, которым K8 проверяет front matter внешним парсером. Без него критерий нечего измерять,
и он честно помечается `fail` с пометкой «не измерено» — а не засчитывается как пройденный по
нулю ошибок.

## Связанные разделы

- [01-overview.md](01-overview.md) — цели и границы продукта, под которые написаны критерии.
- [02-architecture.md](02-architecture.md) — границы портов и адаптеров.
- [11-known-issues.md](11-known-issues.md) — что осталось неисправленным.
- [13-demo-dataset.md](13-demo-dataset.md) — устройство демо-датасета, на котором идёт измерение.
- [../../demo/competitors/basic-memory.md](../../competitors/basic-memory.md) — пример карточки конкурента (всего их 30 в `demo/competitors/`).
- [../plan/competitive-analysis.md](../../plan/competitive-analysis.md) — критерии C1–C16, из которых выведены K*.