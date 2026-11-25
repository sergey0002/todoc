# Хронология, дельты изменений и редизайн индекса — план реализации

**Статус:** план, к реализации не приступали.
**Дата:** 2026-11-25.
**Область:** `application/registry.py`, `application/write.py`, `service.py`, `cli.py`,
новый `application/history.py`, новый `application/changes.py`, новый `adapters/history/`.

**Связанные документы:** [`constitution.md`](constitution.md) — принципы P1–P10, решения C25–C32;
[`09-storage-and-index.md`](../state/09-storage-and-index.md) — текущее разделение «истина / производное»;
[`02-architecture.md`](../state/02-architecture.md) — слои и поток данных;
[`11-known-issues.md`](../state/11-known-issues.md) — P1-1, P1-2, P1-3;
[`memory-llm-wiki.after.md`](memory-llm-wiki.after.md) — Шаг 5 «Bundle-транзакции»;
[`competitive-analysis.md`](competitive-analysis.md) — Zep/Graphiti, Mem0, OpenSpec.

---

## 1. Проблема, измеренная

Текущий механизм публикует **полный снимок состояния на каждый запуск**, независимо от того,
менялось ли что-нибудь. Замер на копии `demo/` (2026-11-25):

| Измерение | Значение | Команда |
|---|---|---|
| Поколений после 5 команд `docs search` | **5** | `ls .todoc/index/generations \| wc -l` |
| Уникальных содержимых среди них | **1** | SHA-256 по 5 файлам каждого поколения |
| Размер одного поколения | 285 КБ | `du -sh` |
| `.todoc/index` в демо | **26 МБ** (93 поколения) | `du -sh demo/.todoc/index` |
| Сами документы (истина) | **2.4 МБ** | `du -sh --exclude=.todoc demo` |
| Метка времени в `meta.json` | **отсутствует** | ключи: `schema_version`, `dataset_id`, `generation_id`, `config_digest` |

Выводы:

1. **Снимок на запуск — это не история.** Пять идентичных снимков несут ноль информации.
   Правильная единица истории — **событие записи**, а не факт запуска команды.
2. **Производное в 11 раз больше истины** и растёт неограниченно (P1-2: сборки мусора нет).
3. **Историю нельзя даже отсортировать по времени.** `generation_id = uuid.uuid4().hex[:12]`
   (`registry.py:70`) — случайный, не упорядоченный; `created_at` в метаданных нет.
   Единственное использование `datetime` во всём `src/todoc` — `_utc_date()` в `cli.py:312`,
   и оно нужно для плейсхолдера `{date}` в шаблонах, не для истории.
4. Пересборка вызывается из **15 мест** в `cli.py` (`rebuild_index()`), при том что
   `load_index()` используется в 10. Это же — причина P1-1.

**Тезис редизайна:** индекс — это кэш, он один и инвалидируется по содержимому.
История — это журнал событий, дописываемый за O(1). Эти две роли сейчас смешаны в одном
механизме, и отсюда обе проблемы.

---

## 2. Три хронологии, которые нельзя смешивать

Задача распадается на три независимых вопроса. Каждый существующий инструмент решает ровно один:

| Вопрос | Механизм | Кто решает |
|---|---|---|
| **A. Как файл выглядел раньше?** (откат) | контентно-адресуемые снимки | git; OpenSpec — нет; Zep — нет |
| **B. Зачем и в рамках какой задачи?** (намерение) | дельты, proposal, жизненный цикл | OpenSpec; git — частично |
| **C. Что было правдой на дату X?** (факты) | би-темпоральные интервалы | Zep/Graphiti; git — нет |

Смешивание даёт систему, плохо делающую всё три. Поэтому — слои, каждый проверяем отдельно.

---

## 3. Ограничения, которые план не нарушает

| Принцип | Как соблюдается |
|---|---|
| **P1** Файлы — истина | Журнал и снимки не заменяют файлы; источник истины не меняется |
| **P2** Портабельность | Только relative paths; `dataset_id` переживает move; `history/` переносится вместе с папкой |
| **P3** Декларативность | Дельты и `derived_from` — JSON/Markdown-данные, никакого кода в DATA_ROOT |
| **P5** Детерминированное ядро | Никакого LLM в поиске противоречий; инвалидация факта только явная |
| **P6** Review-first | `revert`, `change apply` — preview по умолчанию, `--apply` + `expected_hash` |
| **P7** Bounded context | `log`/`diff`/`stale` отдают `truncated`, `cursor`, `--limit` |
| **P8** Точные locations | Каждая запись журнала несёт path + изменённые диапазоны строк |
| **P9** Явные связи | `blocked_by`, `derived_from` — данные в источнике, граф производный |
| **P10** Только установленный код | Дельты не исполняются; применяется только разрешённый набор операций |

**Требуется поправка в конституцию (отдельная задача, до Фазы 1).** Таблица в
[`09-storage-and-index.md`](../state/09-storage-and-index.md) делит всё на «истина» и
«производное, удаляемое». Появляется третья категория — **необратимое производное**:
`.todoc/history/` нельзя пересобрать из файлов. Значит этот каталог должен отслеживаться
git'ом или явно бэкапиться. Решение принято (подтверждено 2026-11-25), но в документах
ещё не зафиксировано.

---

## 4. Целевая раскладка

```
DATA_ROOT/
├── .todoc/
│   ├── dataset.json                    # + секция history
│   ├── index/                          # КЭШ: один снимок, не серия
│   │   ├── CURRENT.json                # + corpus_digest, created_at
│   │   ├── current/                    # папки folders/documents/records/relations/diagnostics
│   │   └── stats.json                  # path → {hash, mtime, size} (быстрая инвалидация)
│   ├── history/                        # НЕОБРАТИМОЕ ПРОИЗВОДНОЕ
│   │   ├── journal.jsonl               # append-only, одна строка = событие
│   │   ├── objects/<2hex>/<rest>       # zlib-снапшоты «до», имя = sha256 содержимого
│   │   └── refs.json                   # {head, tags: {name: {rev, at}}}
│   ├── cache/parse/                    # без изменений
│   └── generated/                      # без изменений
└── changes/                            # В DATA_ROOT: это знание, а не кэш
    ├── <change-id>/
    │   ├── change.json                 # машиночитаемое состояние
    │   ├── proposal.md
    │   ├── tasks.md
    │   └── deltas/<target-path>.md
    └── archive/<YYYY-MM-DD>-<change-id>/
```

`changes/` намеренно в DATA_ROOT: намерение человека должно версионироваться git'ом,
читаться в Obsidian и проходить review. В `.todoc/` оно было бы невидимым.

---

## 5. Схемы

### 5.1 Событие журнала

```json
{"schema_version":1,"rev":"a1b2c3d4e5f6","at":"2026-11-25T10:42:29Z",
 "kind":"doc.edit","actor":"cli","change_id":"change:fix-p1-10",
 "paths":[{"path":"docs/state/09-storage-and-index.md",
           "before":"sha256:aa…","after":"sha256:bb…","ranges":[[31,58]]}],
 "basis":"docs edit --patch-file patch.json","generation_id":"04c087be9380"}
```

- `rev` = SHA-256 строки журнала (12 hex) — стабилен, не требует счётчика.
- Порядок — порядок строк в файле; `at` — вторичная сортировка.
- `kind`: `doc.create` | `doc.edit` | `doc.fix` | `record.create` | `record.edit`
  | `change.open` | `change.apply` | `change.archive` | `change.revert`
  | `external.change` | `snapshot` | `gc`.
- `ranges` — изменённые диапазоны строк; без них невозможна лента по разделу.

Формат JSONL выбран потому, что дописка атомарна одним `write`+`fsync` без
read-modify-write, файл грепается и диффится в git, и не нужна БД.

### 5.2 Снимок

`.todoc/history/objects/<2hex>/<rest>` — zlib-сжатые байты, имя = SHA-256 несжатого
содержимого (тот же формат `sha256:`, что уже возвращает `file_hash`).

**Храним только образ «до».** Образ «после» уже лежит на диске. Содержимое файла на
ревизии R восстанавливается как образ «до» первого изменения после R, либо текущий файл,
если изменений не было. Это вдвое уменьшает объём без потери возможности.

### 5.3 Запись изменения

`change` предлагается сделать **обычным `entity_type`**, а не отдельной сущностью:

```json
{"schema_version":1,"record_id":"change:add-history","entity_type":"change",
 "title":"Журнал изменений и откат","status":"proposed",
 "created_at":"2026-11-25T10:00:00Z","applied_at":null,
 "artifacts":["docs/state/09-storage-and-index.md"],
 "relations":[{"type_id":"blocked_by","target":{"kind":"record","id":"change:index-redesign"}}]}
```

Тогда бесплатно достаются: валидация схемы, `records query --where status=proposed`,
типизированные отношения с cardinality и обход графа зависимостей через существующий
`relations graph`. Это прямое использование P9 вместо нового механизма.

`status`: `proposed` → `in_progress` → `blocked` → `applied` → `archived` | `reverted`.

### 5.4 Дельта

```markdown
---
target: docs/state/09-storage-and-index.md
base_hash: sha256:aa…        # опционально, для строгой проверки
---

## MODIFIED: ## Поколение индекса
…новое тело раздела…

## ADDED: ## Журнал событий
…

## REMOVED: ## Устаревшее
```

Якорь — путь заголовков; markdown уже разбирается на секции (`docs read --section`,
`SECTION_MAX_LINES=40` в `cli.py:50`), поэтому парсер секций переиспользуется.

**Здесь todoc сильнее OpenSpec.** `openspec validate` проверяет *формат* дельты.
`todoc change validate` проверяет *применимость к живому состоянию*: целевой файл
существует, якорь найден, `base_hash` совпадает, а пробное применение не добавляет
диагностик в `validate --all`. У OpenSpec валидатора состояния нет.

### 5.5 Би-темпоральные поля

На отношении (опционально, обратно совместимо):

```json
{"type_id":"employs","target":{"kind":"record","id":"person:sergei"},
 "valid_from":"2024-01-01","valid_to":"2026-06-30",
 "observed_at":"2026-11-25T10:00:00Z","superseded_at":null}
```

- `valid_from`/`valid_to` — когда было правдой в мире (у Graphiti это `valid_at`/`invalid_at`).
- `observed_at`/`superseded_at` — когда todoc узнал / когда заменил (`created_at`/`expired_at`).
- **Инвалидация, а не удаление**: противоречащий факт закрывает старый `superseded_at`.
  Именно Mem0 критикуют за разрушающий `DELETE`, теряющий историю.
- Точка во времени: `valid_from <= T AND (valid_to IS NULL OR T < valid_to)`.

Оговорка: у Zep противоречие ищет LLM, у todoc ядро детерминированное (P5), поэтому
инвалидация **явная** — через `change` или правку записи. Система не догадывается.

### 5.6 Зависимости артефактов

```json
{"record_id":"metric:bench-2026-11-25","entity_type":"metric",
 "derived_from":[{"path":"bench/results/benchmark.json","hash":"sha256:cc…"}]}
```

`todoc stale` сравнивает записанный хеш с текущим. Механизм уже есть в кодовой базе как
прецедент: `config_digest` (`registry.py:16-27`) — SHA-256 по конфигурации, чтобы понять,
менялась ли она между поколениями. Тот же приём, применённый к произвольным зависимостям.

---

## 6. Фаза 0 — редизайн индекса (предпосылка)

Без неё журнал будет дублировать накопление поколений.

1. **Один снимок вместо серии.** `.todoc/index/current/` публикуется через тот же
   tmp+rename, что и сейчас (`registry.py:70-95`), но перезаписывается на месте.
   История поколений удаляется — её роль переходит журналу.
2. **Инвалидация по `corpus_digest`.** SHA-256 по отсортированным парам
   `(rel_path, content_hash)` плюс `config_digest`. Совпал — снимок не переиздаётся,
   диагностики берутся из существующего. Это закрывает и P1-1.
3. **`stats.json`** (path → hash, mtime, size) позволяет считать дайджест через `stat()`
   без перечитывания содержимого неизменённых файлов.
4. **`created_at` в `CURRENT.json`** — сейчас времени нет нигде.

Закрывает: P1-1, P1-2. Убирает 26 МБ производного в демо.

---

## 7. CLI-контракт

Все команды — в существующем конверте (`ok`, `data`, `diagnostics`, `next_actions`),
с `truncated`, `cursor` и бюджетом по P7.

```
todoc index rebuild [--force]

todoc log [--path P] [--section H] [--change ID] [--tag T] [--kind K]
          [--since ISO] [--until ISO] [--limit N] [--cursor C]
todoc show <rev> [--path P] [--section H]
todoc diff [<rev-a>] [<rev-b>] [--path P] [--section H] [--context N]
todoc blame --path P [--section H]
todoc revert <rev> [--path P] [--apply] [--expected-hash H]
todoc tag <name> [--rev R] [--message M]

todoc change list [--status S]
todoc change open --title T [--blocked-by ID] [--artifact P]
todoc change show <id>
todoc change validate <id>          # применимость дельт к живому состоянию
todoc change apply <id> [--apply]   # bundle-транзакция
todoc change archive <id> [--tag T]
todoc change revert <id> [--apply]

todoc stale [--path P] [--severity S]
todoc timeline [--as-of D] [--path P]
todoc records query --as-of D
todoc history gc [--keep-objects N] [--purge-before ISO] [--dry-run]
```

Соответствие ментальной модели git:

| git | todoc |
|---|---|
| `git log` / `log --follow` | `todoc log` / `log --path` |
| — | `todoc log --section "## Решение"` (git так не умеет) |
| `git show <rev>:<path>` | `todoc show <rev> --path` |
| `git diff a b` | `todoc diff a b` |
| `git blame` | `todoc blame` |
| `git revert` | `todoc revert --apply` |
| `git tag` | `todoc tag` / `change archive --tag` |
| ветка | `change` — «ветка намерения», не содержимого |
| `git bisect` | `todoc stale` + `todoc timeline` |

**Лента по разделу** — то, чего git не даёт: фильтрация записей журнала по пересечению
`ranges` с границами секции. Парсер секций уже есть.

**Перехват записи.** Все три точки записи — `apply_write_plan` (`write.py:107`),
`apply_fix` (`write.py:126`), `apply_edit_ops` (`write.py:142`) — уже идут через
`atomic_write` и принимают `expected_hash`. Журнал пишется в одной транзакции с ними.

---

## 8. Коды диагностик

| Код | Смысл |
|---|---|
| `history.journal_unreadable` | строка не разбирается как JSON |
| `history.journal_truncated_line` | последняя строка оборвана (допустимо, игнорируется) |
| `history.object_missing` | снимок отсутствует в `objects/` |
| `history.revision_unknown` | неизвестный `rev` |
| `history.range_conflict` | файл изменён после снимаемой ревизии |
| `change.not_found` / `change.id_invalid` | — |
| `change.delta_target_missing` | целевой файл дельты не существует |
| `change.delta_anchor_missing` | заголовок-якорь не найден |
| `change.base_hash_mismatch` | файл ушёл из-под дельты |
| `change.blocked_by_unresolved` | зависимость не в `archived` |
| `change.already_applied` | повторное применение |
| `change.post_apply_invalid` | пробное применение добавляет диагностики |
| `temporal.invalid_interval` | `valid_to <= valid_from` |
| `staleness.dependency_changed` | хеш зависимости разошёлся |
| `staleness.dependency_missing` | файл зависимости удалён |

Лимиты в `dataset.json` (по образцу `DEFAULT_LIMITS` в `config.py`):
`max_journal_bytes`, `max_history_objects`, `max_diff_lines`.

---

## 9. Фазы и критерии приёмки

Номера фаз — как в обсуждении. Порядок исполнения предложен с учётом зависимостей.

### Фаза 0. Редизайн индекса — **предпосылка для всех**

- **K31**: повторная команда чтения на неизменном корпусе не переиздаёт снимок (0 новых записей).
- **K32**: после `history gc` в `.todoc/index` ровно один снимок; размер не растёт от числа запусков.
- Приёмка: 5 команд чтения на демо → 1 снимок, а не 5.

### Фаза 4. Зависимости и устаревание — **рекомендованный старт**

Не зависит от журнала: нужны только хеши, которые уже считаются. Самая дешёвая и бьёт
в боль, которую уже наблюдали: числа `420 passed`, `2491 инструкция`, `868 веток`
разошлись по семи файлам, и искали их грепом.

- `derived_from` в записях и front matter; `todoc stale`.
- **K33**: recall обнаружения устаревания = 1.0 на засеянном дрейфе (10 засеянных расхождений).
- **K34**: 0 ложных срабатываний на неизменённых зависимостях.

### Фаза 1. Журнал и откат

- `application/history.py`, `adapters/history/` (пустая заглушка `adapters/` уже зарезервирована).
- `log`, `show`, `diff`, `blame`, `revert`, `tag`, `history gc`.
- Режим по умолчанию `observed` (решение принято): при сканировании расхождение хеша без
  объясняющей записи журнала фиксируется как `external.change`.
- **K35**: `revert` восстанавливает содержимое байт-в-байт на 20 засеянных правках.
- **K36**: объём `history/` после `gc` ≤ 2× от объёма документов.
- **K37**: лента по разделу отдаёт только события, пересекающие границы секции.

### Фаза 2. Записи изменений и дельты (в core — решение принято)

Это те самые bundle-транзакции, которые конституция (G3) и
[`memory-llm-wiki.after.md`](memory-llm-wiki.after.md) (Шаг 5) называют гейтом перед
широкими записями агента. Не новая идея — закрытие уже заявленного пробела.

- `entity_type: change`, `relation_type: blocked_by`, `changes/` в DATA_ROOT.
- `change open/show/validate/apply/archive/revert`.
- **K38**: `change validate` ловит дрейф якоря и `base_hash` до применения (recall 1.0).
- **K39**: `change apply` атомарен: при ошибке ни один файл не изменён.

### Фаза 3. Би-темпоральность

- Поля из §5.5, `--as-of`, инвалидация вместо удаления.
- **K40**: point-in-time запрос корректен на засеянных интервалах (точно, без допусков).
- **K41**: противоречащий факт закрывает старый, старый остаётся читаемым.

---

## 10. Миграция

1. Существующие `generations/` не конвертируются — они не содержат ни времени, ни порядка,
   ни намерения, то есть восстанавливать из них нечего. Команда `todoc history adopt`
   снимает текущее состояние как базовую ревизию `rev=baseline` и удаляет `generations/`.
2. `dataset.json` получает секцию `history` с дефолтами; отсутствие секции = `mode: "observed"`.
3. Старые записи без темпоральных полей ведут себя точно как сейчас — поля опциональны.
4. Обратная совместимость CLI не нарушается: все новые команды добавляются, существующие
   сигнатуры не меняются.

---

## 11. Риски

| Риск | Мера |
|---|---|
| Рост объёма `history/` | zlib + дедупликация по хешу + `history gc --keep-objects` |
| **Приватность**: история хранит удалённое | `history gc --purge-before`; без него «удалил» ≠ «удалил» |
| Повреждение журнала | append-only + оборванная последняя строка игнорируется, не валит команду |
| История не пересобирается | явная третья категория хранения; требование бэкапа в конституции |
| `changes/` попадает под сканер | `HARD_EXCLUDE_DIRS` (`scanner.py:10`) его не исключает — нужно правило `dir_type` и решение, валидируются ли дельты как документы |
| `change.json` без `record_id` не станет записью | `service.py:87` пропускает JSON без `record_id` — намеренно, чтобы не смешивать |
| Конкурентная запись | не решается: single-writer, C33 (multi-user) — WON'T |

---

## 12. Чего сознательно нет

- **Веток, слияний, 3-way merge, packing с дельта-сжатием, remote.** Это git; переделывать
  его хуже бессмысленно. История todoc линейна.
- **LLM-извлечения фактов** (Mem0 phase 1). Нарушает P5; остаётся за пределами ядра.
- **Graph DB.** Убивает переносимость; в [`competitive-analysis.md`](competitive-analysis.md)
  Zep отмечен именно за это («портабельность: низкая, graph DB — истина»).
- **Автообнаружения противоречий.** Только явная инвалидация.
- **Разделения на «истину» и «копию» документов.** Файлы остаются единственной истиной (P1).

Что взято у каждого источника:

| Источник | Взято | Не взято |
|---|---|---|
| OpenSpec | `changes/` как единица работы; ADDED/MODIFIED/REMOVED; архив с датой; `blocked_by` | их CLI-обвязка, переписывание спеки целиком |
| Zep/Graphiti | би-темпоральность; инвалидация вместо удаления; point-in-time | graph DB, LLM-поиск противоречий |
| Mem0 | аудит-лог каждой мутации `old → new + event + actor`; словарь операций | LLM-extract, разрушающий `DELETE` |
| git | контентная адресация blob/commit; oplog как JSONL | ветки, merge, packing, remote |

---

## 13. Открытые вопросы

1. Валидируются ли файлы в `changes/` как обычные документы? Если да — нужен `doc_type`
   для дельт и правило в `rules/document-rules.json`.
2. Снимать ли снапшот на каждом скане в режиме `observed`? Это даёт «до» для внешних
   правок, но удваивает объём. Альтернатива — снимать только при обнаружении расхождения.
3. Нужен ли `todoc log` в MCP-контракте сразу, или после стабилизации CLI.
4. Хранить `history/` в git по умолчанию или оставить на усмотрение пользователя
   (тогда нужна явная команда `todoc history export`).

---

## 14. Источники

- OpenSpec — структура `specs/` + `changes/`, формат дельт, семантика архива:
  [concepts](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md),
  [getting-started](https://github.com/Fission-AI/OpenSpec/blob/main/docs/getting-started.md).
- Zep/Graphiti — би-темпоральная модель `valid_at/invalid_at` + `created_at/expired_at`,
  инвалидация вместо удаления, оговорка «invalidation only happens when a contradicting
  episode arrives»: [temporal model](https://mintlify.wiki/getzep/graphiti/concepts/temporal-model),
  [facts](https://help.getzep.com/v4/facts).
- Mem0 — двухфазный extract→update, ADD/UPDATE/DELETE/NOOP, аудит-лог `old_memory → new_memory`,
  критика разрушающего DELETE:
  [обзор](https://www.hubbleflow.ai/resources/magazine/mem0-memory-layer),
  [сравнение](https://www.digitalapplied.com/blog/open-source-agent-memory-mem0-letta-zep-compared).
- Контентно-адресуемое хранилище — модель blob/tree/commit, шардирование `objects/<2hex>/`,
  oplog как JSONL, `{mtime, size}` для пропуска перечитывания:
  [Git data model](https://missing.csail.mit.edu/2026/version-control/),
  [построение VCS в TypeScript](https://medium.com/@jaykarvashu/building-drift-a-content-addressed-vcs-in-typescript-29cda4890c31).
