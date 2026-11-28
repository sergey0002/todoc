---
id: doc:ideas/action-logging.md
title: "Идея: настраиваемое логирование всех действий и вызовов CLI (error / warning / notice / all) вне данных"
doc_type: idea
lang: ru
status: captured
created: 2026-11-26
updated: 2026-11-28
tags: [ideas, idea, logging, trace, debug, cli, observability, отладка]
related: ["[[agent-state]]", "[[constitution.md]]", "[[bug-012-history-revizii-mutiruyuschih-komand-zagryaznyayut-git-status]]"]
---

# Идея: настраиваемое логирование всех действий и вызовов CLI (`error` / `warning` / `notice` / `all`)

- Тип: `idea`
- Создан: 2026-11-26
- Идентификатор: `doc:ideas/action-logging.md`
- Статус: `captured` (идея зафиксирована, не перешла в план)

## Суть

Ввести **настраиваемое операционное логирование действий и вызовов `todoc`** с уровнями детализации **`error`**, **`warning`**, **`notice`** и **`all`** (плюс `off`). В режиме `all` фиксируются абсолютно все вызовы CLI (включая read-only команды `search`, `read`, `tree`, `validate`) и внутренние фазы движка (`scan`, reuse/rebuild индекса, длительность в мс, код возврата, размер ответа в байтах) в структурированный JSONL-файл **вне `DATA_ROOT`** (`~/.local/state/todoc/logs/`), не загрязняя `stdout`-конверт агента и `git status` репозитория данных.

## Проблема

1. **Слепая зона при отладке агентских сессий.** Сейчас `history/journal.jsonl` фиксирует только успешные записи файлов на диск. Когда агент в сессии делает 30 вызовов `docs search` / `docs read`, натыкается на `usage.error` или `docs.not_found`, теряет контекст на `truncated: true`, гоняет холостую пересборку индекса или делает `--preview` без `--apply` — следов этих вызовов нигде не остаётся. Разобрать постфактум «что именно вызывал агент, с какими флагами, сколько мс и байт ушло и на чём он споткнулся» невозможно.
2. **Нельзя писать операционные логи внутрь `DATA_ROOT`.** Любая попытка логировать вызовы чтения внутрь `<DATA_ROOT>/.todoc/` приведёт к постоянному загрязнению `git status` (см. [BUG-012](../bugs/bug-012-history-revizii-mutiruyuschih-komand-zagryaznyayut-git-status.md)) и лишним срабатываниям обходчиков.
3. **Нельзя смешивать отладочный лог со стандартным выводом `stdout`.** Контракт CLI `todoc` требует, чтобы в `stdout` всегда шёл чистый машиночитаемый JSON-конверт (`schema_version: 1`). Произвольные текстовые `print`/лог-строки в `stdout` сломают парсинг у агентов.

## Принципы

1. **Лог процесса — вне данных и вне Git (по паттерну [`state.json`](agent-state.md)).** По умолчанию логи пишутся в `{XDG_STATE_HOME|~/.local/state}/todoc/logs/<dataset_id>.jsonl` (а ошибки до определения `--root` — в `global.jsonl`). Данные датасета и `corpus_digest` остаются неизменными.
2. **Чистота `stdout` и fail-open.** В `stdout` всегда идёт только штатный конверт ответа команды. Дублирование лога в терминал включается только явным флагом `--log-stderr` (строго в `stderr`). Если файловая система логов недоступна (`read-only` sandbox), логгер деградирует молча (fail-open) и никогда не роняет основную команду.
3. **Структурированный JSONL (одна строка = одно событие) + ротация.** Никаких неразбираемых многострочных простыней: каждая запись — компактный JSON с таймингом, `call_id`, уровнем, командой, усечёнными аргументами, `exit_code` и диагностиками. Размер ограничен автоматической ротацией.
4. **Ноль новых внешних зависимостей.** Реализуется поверх стандартного модуля Python `logging` (`RotatingFileHandler`) + тонкого JSON-форматтера.

## Предложение

### 1. Шкала уровней логирования

Каждый уровень включает события всех более строгих уровней (`error ⊂ warning ⊂ notice ⊂ all`, плюс `off` для полного отключения):

| Уровень | Что записывается в лог | Когда включать |
|---|---|---|
| `off` | Ничего не пишется. | Среды с жёстким запретом записи на диск / чистые микробенчмарки. |
| `error` | Только завершившиеся ошибкой вызовы (`ok: false`, `exit_code != 0`: `TodocError`, `ClickException`, необработанные исключения) и сработавшие `error`-диагностики `validate`/`check-config`. | Минимальный продакшен-контроль сбоев. |
| `warning` | Всё из `error` + предупреждения: диагностики с `severity: "warning"`, деградация бэкенда истории (`degraded: true`), повреждённый/пересозданный кеш, усечение ответа по лимиту/бюджету (`truncated: true`). | Повседневный тихий режим с отловом фрикции и переполнений бюджета. |
| `notice` | Всё из `warning` + все значимые действия и мутации состояния (успешные `--apply` и сухие `--preview`): `docs new/edit/status/move`, `records create/status/undo-relation`, `folderize`, `skills import/attach`, `state set/unset`, `index rebuild`, `change *`, `fix`, `revert`, `stale --ack`. | **Рекомендуемый дефолт:** видна вся хронология действий без шума от чтения. |
| `all` | **Абсолютно все вызовы CLI** (включая все read-команды: `docs search/read/tree/suggest/links/flow`, `records list/read/query/aggregate`, `skills tree/read`, `relations *`, `explain-path`, `status`, `doctor`, `validate`, `timeline`, `context`) + внутренние метрики фаз движка (`scan_ms`, `files_scanned`, `hash_cache_hits`, `index_reused`, `bytes_out`, `duration_ms`). | **Режим отладки (`debug`):** полный «чёрный ящик» сессии агента и профилирование тормозов/токенов. |

### 2. Цепочка настройки (приоритет сверху вниз)

1. **Флаг вызова CLI:** `todoc --log-level <off|error|warning|notice|all> [--log-file <path>] [--log-stderr] ...`
2. **Переменные окружения:** `TODOC_LOG_LEVEL` и `TODOC_LOG_FILE` (удобно включить `TODOC_LOG_LEVEL=all` на время теста или отладки конкретной агентской сессии).
3. **Персистентная настройка в агентском стейте (`state.py`):** расширение белого списка ключей `state.json` ключом `log.level` (`todoc state set log.level all` — запоминается для данного `dataset_id` между сессиями без правки Git-файлов).
4. **Опциональный блок в `.todoc/dataset.json`:** `"logging": {"level": "notice", "max_bytes": 10485760, "backup_count": 3}`.
5. **Встроенный дефолт движка:** `notice`.

### 3. Формат JSONL-записи и защита от раздувания

Пример одной строки в `~/.local/state/todoc/logs/dataset-80c70868.jsonl` при уровне `all`:

```json
{
  "schema_version": 1,
  "ts": "2026-11-26T18:45:12.104Z",
  "call_id": "call_9f21a8c4",
  "level": "all",
  "dataset_id": "dataset-80c70868",
  "command": "docs search",
  "argv": ["--root", "demo", "docs", "search", "--query", "todocignore", "--type", "idea"],
  "ok": true,
  "exit_code": 0,
  "duration_ms": 18.4,
  "metrics": {
    "scan_ms": 4.1,
    "files_scanned": 447,
    "index_reused": true,
    "bytes_out": 1142,
    "truncated": false
  },
  "diagnostics": []
}
```

Правила гигиены и безопасности:
- Ротация: по умолчанию `max_bytes = 10 МБ`, `backup_count = 3` (`<dataset_id>.jsonl`, `.1`, `.2`, `.3`).
- Длинные значения аргументов усекаются до `256` символов; содержимое `--patch-file` / `--input-file` целиком в операционный лог не копируется (пишется только путь, размер и итоговый хеш).
- Для связки с журналом ревизий данных: если мутирующая команда породила событие в `history/journal.jsonl`, в JSONL-запись операционного лога пишется тот же `change_id` / `rev`.

### 4. Сквозные точки перехвата в коде и CLI просмотра (`todoc trace`)

Поскольку команда верхнего уровня `todoc log` уже занята журналом контентных ревизий файлов (`history_log`), для чтения и управления операционным логом вводится группа **`todoc trace`**:

- **Единый перехватчик в `src/todoc/cli.py` (`main()` + контекст Click):** оборачивает любой запуск CLI на входе и выходе (фиксирует старт, перехватывает `TodocError` / `ClickException` / `SystemExit`, снимает код возврата, счётчики `diagnostics`, `truncated` и `bytes_out` из `output/envelope.py`), а `DatasetContext.scan()` / `ensure_index()` складывают метрики `scan_ms` и `index_reused` в контекст текущего вызова.
- **Команды просмотра и управления (`todoc trace`):**
  - `todoc trace tail --root KB [--limit 50] [--level error|warning|notice|all] [--command "docs search"] [--since ISO]` — чтение последних записей в стандартном JSON/table конверте;
  - `todoc trace stats --root KB [--since ISO]` — агрегированная сводка по сессии: сколько вызовов сделано, топ самых частых/медленных команд, сколько раз сработал `error` или `truncated: true`, суммарный `bytes_out` (прямой инструмент поиска фрикции агента!);
  - `todoc trace clear --root KB` — очистка файлов операционного лога датасета.

## План внедрения

1. **Фаза 1 — Модуль `src/todoc/application/action_log.py` и интеграция со `state.py`:**
   - Шкала уровней `off < error < warning < notice < all`, резолвер уровня (`CLI → ENV → state.json → dataset.json → default`), JSONL-писатель с ротацией и fail-open при `OSError`.
   - Добавление ключа `log.level` в разрешённые ключи `state.py`.
   - *Acceptance:* unit-тесты фильтрации каждого из 5 уровней, усечения длинных аргументов, ротации по размеру и fail-open на недоступной директории.
2. **Фаза 2 — Сквозной перехват в `cli.py`, `envelope.py` и `service.py`:**
   - Глобальные опции `--log-level`, `--log-file`, `--log-stderr`; автоматическая запись каждого вызова в `main()` (включая `usage.error` и `TodocError`), сбор метрик `scan_ms`, `index_reused`, `bytes_out`, `truncated`.
   - *Acceptance:* при `TODOC_LOG_LEVEL=all` любой вызов (`docs search`, `validate`, ошибочный флаг) оставляет точную JSONL-запись с `duration_ms` и `exit_code`, при этом `stdout` остаётся валидным JSON-конвертом, а `git status` в `DATA_ROOT` чист.
3. **Фаза 3 — CLI-группа `todoc trace` (`tail`, `stats`, `clear`):**
   - Команды чтения, фильтрации и агрегации операционного лога для разбора сессий агента.
   - *Acceptance:* `100%` branch coverage, `todoc validate --root demo --all` = `0` диагностик.

## Открытые вопросы

- **Дефолтный уровень из коробки:** сделать дефолтом `notice` (сразу логируются ошибки, предупреждения и мутации без ручного включения) или `off`/`error` (нулевой дисковый след в `~/.local/state/todoc/logs/` до явного включения)? Рекомендация — `notice` с компактным лимитом ротации.
- **Корреляция вызовов одной агентской сессии (`session_id`):** стоит ли поддерживать необязательную переменную окружения `TODOC_SESSION_ID` (которую агент или обёртка может выставить один раз на сессию), чтобы `todoc trace stats` умел группировать вызовы по конкретной сессии?

## Связанные документы

- [Идея: агентский стейт — `state.json` вне данных (`~/.local/state/todoc/`)](agent-state.md)
- [BUG-012: ревизии мутирующих команд в `.todoc/history/` загрязняют `git status`](../bugs/bug-012-history-revizii-mutiruyuschih-komand-zagryaznyayut-git-status.md)
- [Конституция `todoc` (§8: тонкий CLI, детерминированный конверт ответа и коды выхода)](../plan/constitution.md)

## Связь с выпуском единого CLI

Чистый stdout и отсутствие записи при read и preview подтверждены. Операционная трассировка остаётся отдельной идеей.
[Сводка выпуска единого CLI](../notes/unified-cli-release.md).
