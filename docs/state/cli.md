# CLI `todoc` — полный справочник команд и атрибутов

> **Статус:** актуально на 2026-11-28. Источник истины — `src/todoc/cli.py`,
> вывод `todoc --help` / `todoc <путь> --help` и реальные запуски на демо-датасете.
> Снимок: 63 листовые команды, `todoc, version 0.1.0`.
>
> **Назначение файла:** одна точка входа для человека и агента: что делает каждая
> команда, какие атрибуты принимает, что возвращает, где применяется — в скилах,
> правилах агента и в контексте сущностей датасета.

## Содержание

1. [Как читать справочник](#1-как-читать-справочник)
2. [Глобальный контракт CLI](#2-глобальный-контракт-cli)
3. [Индекс всех 63 команд](#3-индекс-всех-63-команд)
4. [Инициализация, здоровье, валидация, ремонт](#4-инициализация-здоровье-валидация-ремонт)
5. [Индекс и производные артефакты](#5-индекс-и-производные-артефакты)
6. [Документы: `docs …`](#6-документы-docs-)
7. [Записи: `records …`](#7-записи-records-)
8. [Связи: `relations …`](#8-связи-relations-)
9. [Типы: `types …`](#9-типы-types-)
10. [История: `log` / `show` / `diff` / `blame` / `timeline` / `revert` / `tag` / `history …`](#10-история-log--show--diff--blame--timeline--revert--tag--history-)
11. [Изменения: `change …` и `context`](#11-изменения-change--и-context)
12. [Дрейф зависимостей: `stale`](#12-дрейф-зависимостей-stale)
13. [Скилы: `skills …`](#13-скилы-skills-)
14. [Агентский стейт: `state …`](#14-агентский-стейт-state-)
15. [Интероп-экспорты: `interop export`](#15-интероп-экспорты-interop-export)
16. [Карта применения: скилы, правила, сущности](#16-карта-применения-скилы-правила-сущности)
17. [Типовые последовательности](#17-типовые-последовательности)
18. [Связанные документы](#18-связанные-документы)

---

## 1. Как читать справочник

### 1.1. Формат записи команды

Каждая команда описана одинаково:

| Блок | Что содержит |
|---|---|
| **Путь CLI** | полная команда от `todoc`, например `todoc docs search` |
| **Назначение** | что команда делает по-русски, одной фразой |
| **Синтаксис** | аргументы и опции в порядке применения |
| **Атрибуты** | все специфичные опции: тип, допустимые значения, default, обязательность |
| **Вывод** | поля `data` и форма конверта |
| **Пример** | реальная команда и фрагмент реального ответа |
| **Особенности** | инварианты, коды ошибок, ограничения |
| **Где применяется** | скилы, правила агента, сущности, для которых команда предназначена |

### 1.2. Соглашения

- `todoc` — entrypoint; эквивалент `python -m todoc` (при `PYTHONPATH=src`).
- `<…>` — обязательное значение, `[…]` — необязательное.
- `--root` можно повторять: каждая команда выполняет работу по всем корням
  изолированно и возвращает `data.datasets[]`.
- Если `--root` не задан, используется `TODOC_ROOT`; иначе —
  `usage.missing_root` (exit 2).
- Все листовые команды, кроме `init`, принимают общие опции
  `--root`, `--output`, `--no-input`. Они описаны один раз в
  [§2.1](#21-глобальные-и-командные-опции) и в таблицах команд не повторяются.
- Значения `default` приведены из `--help`; пустой default означает `None`.

### 1.3. Быстрая проверка справки

```bash
todoc --help
todoc docs --help
todoc docs read --help
todoc records --help
```

---

## 2. Глобальный контракт CLI

### 2.1. Глобальные и командные опции

| Атрибут | Тип / значения | По умолчанию | Назначение |
|---|---|---|---|
| `--root PATH` | путь, **повторяемый** | `TODOC_ROOT` | Корень датасета (`DATA_ROOT`). Можно указать несколько корней; каждый обрабатывается отдельно. У `init` — обязательный одиночный `--root`. |
| `--output [json\|table\|markdown]` | enum | `json` | Формат вывода. У части команд набор уже: `skills tree` — `json\|table`; `skills read` — `json\|markdown`; `docs suggest`, `docs links`, `skills attach`, `skills import` — `json\|table`. |
| `--no-input` | флаг | `false` | Неинтерактивный режим. Команды и так не задают вопросов; флаг оставлен для совместимости и скриптов. |
| `--version` | флаг | — | Печатает `todoc, version 0.1.0` и выходит. |
| `--help` | флаг | — | Справка Click по текущей группе/команде. |

> **Важно:** `--root` объявлен и на глобальном уровне, и на каждой листовой
> команде. Поэтому допустимы обе формы:
> `todoc --root demo status` и `todoc status --root demo`.
> Для нескольких корней: `todoc --root A --root B validate`.

### 2.2. Коды выхода

| Код | Смысл | Класс ошибки |
|---|---|---|
| `0` | успех | — |
| `1` | операционная ошибка | `TodocError` |
| `2` | ошибка использования CLI | `click.ClickException` / `usage.*` |
| `3` | ошибка валидации данных/конфига | `ValidationError` |
| `4` | отказ в доступе (выход за `DATA_ROOT`) | `AccessError` |
| `5` | конфликт (хеш, существующий файл, перезапись) | `ConflictError` |
| `6` | незавершённая генерация/неполнота | `IncompleteError` |

Код выхода важнее текста: при ненулевом коде `ok` всегда `false`.

### 2.3. Конверт ответа

Успешный ответ (`--output json`) — ровно один JSON-текст в stdout:

```json
{
  "schema_version": 1,
  "ok": true,
  "data": {},
  "diagnostics": [],
  "next_actions": []
}
```

| Поле | Назначение |
|---|---|
| `schema_version` | версия контракта конверта (сейчас `1`) |
| `ok` | успех операции; согласован с кодом выхода |
| `data` | полезная нагрузка; состав зависит от команды |
| `diagnostics[]` | диагностики: `{dataset_id, id, code, severity, path, location, evidence, message, suggested_fixes[]}` |
| `next_actions[]` | готовые следующие шаги: `{argv: [...], purpose: "…"}` |
| `guidance` | опциональный блок прогрессивной опоры для модели (P15); появляется, когда есть что подсказать |

Ошибка возвращается тем же конвертом с `ok: false`, заполненными
`diagnostics[]` и `next_actions[]`; traceback в stdout не попадает.

### 2.4. Форматы вывода

| Формат | Поведение |
|---|---|
| `json` | машинный контракт; единственный JSON-текст в stdout |
| `table` | человекочитаемая таблица; поля те же, что в `data` |
| `markdown` | markdown-представление; у `skills read` — тело `SKILL.md`, у `types guide` — сгенерированный справочник |

Для агента канон — `--output json`; `table`/`markdown` нужны человеку.

### 2.5. Общие инварианты

1. **Review-first.** Мутирующие команды по умолчанию показывают план:
   `docs edit`, `records create`, `change apply`, `change revert`,
   `revert`, `stale --ack`. Запись — только с `--apply`.
2. **CAS.** `--if-hash` / `--expected-hash` защищают от гонки: если файл ушёл,
   команда отказывает с exit 5, а не перезаписывает.
3. **Create-only.** `records create` не перезаписывает существующую запись;
   `docs new` не перезаписывает документ.
4. **Bounded output.** Поиск, чтение, дерево, скилы и контекст ограничены
   `--limit`/`--budget`; `truncated` и `cursor` — часть контракта.
5. **Детерминизм.** Порядок результатов стабилен; производные артефакты
   (индекс, кэш, история) пересобираемы.
6. **Изоляция корней.** Ошибка в одном `--root` не отменяет обработку остальных;
   результат по каждому корню — отдельный элемент `data.datasets[]`.

---

## 3. Индекс всех 63 команд

| № | Путь CLI | Что делает по-русски | Ключевые атрибуты | Основной вывод |
|---:|---|---|---|---|
| 1 | `todoc init` | Создаёт переносимые управляющие файлы `.todoc/` | `--root`, `--dataset-id` | `dataset_id, root, created` |
| 2 | `todoc check-config` | Проверяет конфиги и реестр типов до работы | — | `datasets[]` с `issues` |
| 3 | `todoc check` | Короткая сводка здоровья датасета | `--strict` | `documents, errors, warnings, status` |
| 4 | `todoc scan` | Детерминированный обход без записи индекса | — | `folders, documents, diagnostics` |
| 5 | `todoc validate` | Подробный отчёт файл/правило/локация | `--all` | `diagnostics[]` |
| 6 | `todoc index status` | Состояние опубликованного поколения | — | `generation_id, current, corpus_digest` |
| 7 | `todoc index rebuild` | Пересобирает и публикует индекс | `--force` | `generation_id, reused, counts` |
| 8 | `todoc skills tree` | Оглавление хранилища скилов | `--vault`, `--within`, `--query`, `--all`, `--limit`, `--max-depth` | `skills[]`, `counts` |
| 9 | `todoc skills read` | Читает `SKILL.md` внутри vault | `--path`, `--line-range`, `--budget`, `--vault` | `content`, `truncated` |
| 10 | `todoc skills attach` | Ставит диспетчер-скил `todoc` в платформу | `--to`, `--root`, `--force` | `installed, root_embedded` |
| 11 | `todoc skills import` | Импортирует чужие скилы в vault | `--src`, `--into`, `--skill`, `--dry-run`, `--adopt` | `imported[]`, `skipped[]` |
| 12 | `todoc stale` | Ищет дрейф зависимостей `derived_from` | `--path`, `--severity`, `--ack`, `--reason`, `--apply` | `stale`, `diagnostics[]` |
| 13 | `todoc log` | Журнал событий записи | `--path`, `--section`, `--kind`, `--change`, `--tag`, `--since`, `--until`, `--limit`, `--cursor` | `events[]`, `total` |
| 14 | `todoc show` | Содержимое файла на ревизии | `REV`, `--path`, `--budget` | `path, rev, content` |
| 15 | `todoc diff` | Разница ревизий файла | `REV_A [REV_B]`, `--path`, `--context`, `--budget` | `changed, lines, diff[]` |
| 16 | `todoc blame` | Кто и когда менял файл/раздел | `--path`, `--section` | `entries[]` |
| 17 | `todoc timeline` | Единая лента событий и фактов | `--as-of`, `--path`, `--limit` | `entries[]` |
| 18 | `todoc revert` | Откат файла к ревизии | `REV`, `--path`, `--apply`, `--expected-hash` | план/`applied` |
| 19 | `todoc tag` | Метка на ревизии | `NAME`, `--rev`, `--message` | `tag, rev, at` |
| 20 | `todoc history gc` | Сборка мусора журнала и снимков | `--keep-objects`, `--purge-before`, `--dry-run` | счётчики удаления |
| 21 | `todoc history adopt` | Снимок текущего состояния как базовая линия | — | `rev, paths` |
| 22 | `todoc history export` | Бэкап `.todoc/history/` | `--to` | `exported, to` |
| 23 | `todoc change list` | Список изменений | `--status` | `changes[]` |
| 24 | `todoc change open` | Открывает изменение и снимает baseline | `--title`, `--blocked-by`, `--artifact` | `change_id, path, status` |
| 25 | `todoc change show` | Запись изменения и её дельты | `ID` | `record, deltas[]` |
| 26 | `todoc change validate` | Применимость дельт к живому состоянию | `ID` | `applicable, errors` |
| 27 | `todoc change verify` | Completeness / correctness / coherence | `ID` | `findings[], clean` |
| 28 | `todoc change apply` | Применение bundle-транзакцией | `ID`, `--apply`, `--if-hash` | план/`applied` |
| 29 | `todoc change archive` | Закрывает изменение и архивирует папку | `ID`, `--tag` | статус `archived` |
| 30 | `todoc change revert` | Возврат артефактов к baseline | `ID`, `--apply` | план/`applied` |
| 31 | `todoc context` | Весь контекст задачи в бюджете байт | `--change`, `--tag`, `--budget`, `--with-diff` | `record, deltas, events, files` |
| 32 | `todoc explain-path` | Объясняет тип и правило для пути | `PATH`, `--match` | `doc_type`/`dir_type`, `rule_source` |
| 33 | `todoc docs new` | Создаёт документ из шаблона типа | `--title`, `--dir`, `--path`, `--type`, `--template` | `path, doc_type, hash` |
| 34 | `todoc docs search` | Ограниченный лексический поиск | `--query`, `--type`, `--limit`, `--within`, `--budget`, `--cursor`, `--tag` | `items[]`, `cursor` |
| 35 | `todoc docs read` | Ограниченное чтение проекции | `--id`, `--section`, `--anchor`, `--line-range`, `--pointer`, `--columns`, `--rows`, `--where`, `--budget` | зависит от формата |
| 36 | `todoc docs suggest` | Куда положить/где искать | `--query`, `--limit` | `candidates[]`, `discarded[]` |
| 37 | `todoc docs links` | Инвентаризация локальных ссылок | `--limit` | `total, broken, items[]` |
| 38 | `todoc docs tree` | Компактная карта папок и документов | `--within`, `--max-depth`, `--match` | `folders[], documents[]` |
| 39 | `todoc docs flow render` | Витрина флоу из записи | `--id`, `--section`, `--write` | `section, text` |
| 40 | `todoc docs flow walk` | Обход дерева решений флоу | `--id`, `--at`, `--all-paths` | `steps[]` |
| 41 | `todoc docs status` | Чтение/смена статуса md-документа | `--id`, `--set` | `id, status` |
| 42 | `todoc docs edit` | Патчевая правка документа | `--id`, `--patch-file`, `--preview`, `--apply`, `--if-hash` | `preview`/`applied` |
| 43 | `todoc records create` | Создаёт JSON-запись (create-only) | `--type`, `--input-file`, `--preview`, `--apply` | `plan`/`created` |
| 44 | `todoc records undo-relation` | Точечно откатывает ребро | `--id`, `--pointer`, `--apply`, `--expected-hash` | план/`applied` |
| 45 | `todoc records list` | Список записей с фильтрами | `--type`, `--since`, `--until`, `--relation`, `--limit` | `items[]`, `total` |
| 46 | `todoc records status` | Чтение/смена статуса записи | `--id`, `--set` | `id, status` |
| 47 | `todoc records query` | Декларативный QuerySpec | `--query-file`, `--as-of` | `items[]`, `total` |
| 48 | `todoc records aggregate` | Сумма метрики с provenance | `--metric`, `--type`, `--group-by` | `groups`, `units`, `formula` |
| 49 | `todoc records read` | Читает одну запись/проекцию | `--id`, `--view` | `record_id, data` |
| 50 | `todoc interop export` | Экспорт витрины в DMN/ASL/Rasa | `--kind`, `--id`, `--write` | `artifact` |
| 51 | `todoc relations graph` | BFS по типизированным рёбрам | `--from`, `--type`, `--depth`, `--limit` | `edges[]`, `total` |
| 52 | `todoc relations tree` | Вложенное дерево связей | `--from`, `--type`, `--depth`, `--limit` | `groups[]` |
| 53 | `todoc types list` | Каталог всех типов | — | `dir_types, doc_types, entity_types, relation_types` |
| 54 | `todoc types show` | Описатель типа, шаблон, промпты, схема | `TYPE_ID` | `type, template, prompts, schema` |
| 55 | `todoc types prompt` | Стартовый промпт операции | `TYPE_ID`, `--op` | `path, prompt, chars` |
| 56 | `todoc types guide` | Сгенерированный справочник типов | `--format`, `--out` | markdown/json напрямую |
| 57 | `todoc fix` | Применяет предложенный фикс | `--diagnostic`, `--preview`, `--apply`, `--if-hash` | `fix`/`applied` |
| 58 | `todoc doctor` | Read-only диагностика окружения | `--check`, `--scope`, `--fix` | `checks[]`, `passed` |
| 59 | `todoc status` | Быстрый снимок опубликованного индекса | — | `index_built, documents, records` |
| 60 | `todoc state set` | Записывает переменную стейта | `KEY`, `VALUE` | `key, value, updated_at` |
| 61 | `todoc state get` | Читает переменную стейта | `KEY` | `key, value` |
| 62 | `todoc state list` | Список переменных стейта | `--prefix` | `vars` |
| 63 | `todoc state unset` | Удаляет переменную стейта | `KEY` | `key, removed` |

---

## 4. Инициализация, здоровье, валидация, ремонт

### 4.1. `todoc init`

**Путь CLI:** `todoc init`

**Назначение:** создаёт переносимый управляющий каталог `.todoc/` (датасет,
правила, каталоги типов, шаблоны, CRUD-промпты, `queries/`). Пользовательские
данные не сканирует и не перемещает.

**Синтаксис:**

```bash
todoc init --root PATH [--dataset-id ID] [--output json|table|markdown]
```

**Атрибуты:**

| Атрибут | Тип / значения | Обязателен | Назначение |
|---|---|---|---|
| `--root PATH` | путь | да | Корень нового датасета. У `init` это одиночный обязательный `--root`, а не повторяемый. |
| `--dataset-id ID` | строка | нет | Идентификатор датасета. Без него — случайный `dataset-<8 hex>`; явное значение делает демо и фикстуры воспроизводимыми. Пробелы обрезаются; пустое значение отклоняется. |
| `--output` | `json\|table\|markdown` | нет | Формат ответа. |
| `--no-input` | флаг | нет | Неинтерактивный режим. |

**Вывод:**

```json
{
  "schema_version": 1,
  "ok": true,
  "data": {
    "dataset_id": "example",
    "root": "/tmp/kb_example",
    "created": ".todoc/"
  },
  "diagnostics": [],
  "next_actions": []
}
```

**Пример:**

```bash
todoc init --root /tmp/kb_example --dataset-id example
```

**Особенности:**

- Повторный вызов — `config.already_initialized`, exit 3; существующие данные не трогаются.
- Пустой/некорректный `--dataset-id` — `config.invalid_schema`, exit 3.
- После `init` индекс ещё не собран: `index status` вернёт `generation_id: null`.

**Где применяется:**

- Скил `todoc` (`SKILL.md`): «если в папке нет `.todoc/dataset.json` — сначала `init`».
- Новый `DATA_ROOT` в правилах агента; демо-фикстуры и тесты.
- Сущности: создаёт реестры `dir_types`, `doc_types`, `entity_types`, `relation_types`.

### 4.2. `todoc check-config`

**Путь CLI:** `todoc check-config`

**Назначение:** проверяет конфигурацию датасета и реестр типов до начала работы:
неизвестные поля описателей, битые правила, отсутствующие шаблоны и промпты.

**Синтаксис:**

```bash
todoc check-config [--root PATH]… [--output json|table|markdown]
```

**Атрибуты:** только общие (`--root`, `--output`, `--no-input`).

**Вывод:** `data.datasets[]`:

```json
{
  "dataset_id": "example",
  "ok": true,
  "warnings": 0,
  "dir_types": 6,
  "doc_types": 5,
  "entity_types": 8,
  "relation_types": 5,
  "issues": 0
}
```

**Пример:**

```bash
todoc check-config --root /tmp/kb_example
```

**Особенности:**

- Любая находка — ошибка (exit 3): `config.unknown_field`, `config.invalid_schema`,
  `config.template_missing`, `config.prompt_missing`, `config.schema_missing`,
  `config.duplicate_asset`.
- `warnings` — счётчик находок `severity: warning`; сейчас таких кодов нет, поле
  оставлено для расширения контракта.

**Где применяется:**

- Первый шаг базового цикла агента ([12-agent-operations.md](12-agent-operations.md)).
- Правило AGENTS.md: типы и правила — данные, менять их только осознанно и
  проверять `check-config`/`validate`.
- Сущности: все описатели типов и правила резолва.

### 4.3. `todoc check`

**Путь CLI:** `todoc check`

**Назначение:** короткая сводка здоровья: сколько документов, ошибок и
предупреждений, общий статус.

**Синтаксис:**

```bash
todoc check [--strict] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `--strict` | флаг | `false` | Превращает предупреждения в провал (ненулевой exit). |

**Вывод:** элемент `data.datasets[]`:

```json
{
  "dataset_id": "dataset-80c70868",
  "documents": 505,
  "errors": 0,
  "warnings": 0,
  "status": "ok"
}
```

**Пример:**

```bash
todoc check --root demo
todoc check --root demo --strict
```

**Особенности:** не заменяет `validate`; для локаций и кодов диагностик нужен
подробный отчёт.

**Где применяется:** первый быстрый гейт в скиле `todoc` и в CI-ритуалах.

### 4.4. `todoc scan`

**Путь CLI:** `todoc scan`

**Назначение:** детерминированный обход корпуса без публикации индекса. Показывает,
что будет увидено, но не пишет derived-артефакты.

**Синтаксис:**

```bash
todoc scan [--root PATH]…
```

**Атрибуты:** только общие.

**Вывод:** элемент `data.datasets[]`:

```json
{
  "dataset_id": "dataset-80c70868",
  "folders": 86,
  "documents": 505,
  "diagnostics": 0
}
```

**Пример:**

```bash
todoc scan --root demo
```

**Особенности:** счётчики — результат обхода, а не опубликованного поколения;
`index status` может отличаться до пересборки.

**Где применяется:** диагностика расхождений «файлы есть, индекс старый»;
подготовка к `index rebuild`.

### 4.5. `todoc validate`

**Путь CLI:** `todoc validate`

**Назначение:** полная валидация корпуса: схемы, front matter, структура разделов,
ссылки, записи, отношения, типы. Возвращает точные локации и доказательства.

**Синтаксис:**

```bash
todoc validate [--all] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `--all` | флаг | `false` | Валидировать весь датасет, а не только затронутое/инкрементальное подмножество. В агентских сценариях используется всегда. |

**Вывод:** `data.datasets[]`:

```json
{
  "dataset_id": "dataset-80c70868",
  "documents": 505,
  "diagnostics": []
}
```

Каждая диагностика:

```json
{
  "dataset_id": "example",
  "id": "diag_c54fb85d9032",
  "code": "markdown.link.target_missing",
  "severity": "error",
  "path": "notes/example-note.md",
  "location": {"line": 20, "column": 1, "end_column": 19},
  "evidence": "[битая](missing.md)",
  "message": "Локальная цель ссылки не найдена.",
  "suggested_fixes": []
}
```

**Пример:**

```bash
todoc validate --root demo --all
```

**Особенности:**

- Exit 3, если есть хотя бы одна ошибка; предупреждения сами по себе не роняют.
- `id` диагностики — SHA-256 от `path + code + message`; стабилен между запусками,
  пока файл не изменён. После правки старый `id` даёт `fix.diagnostic_not_found`.
- Каталог кодов — [06-validation-and-diagnostics.md](06-validation-and-diagnostics.md).

**Где применяется:**

- Железное правило AGENTS.md: после изменений данных `validate --root demo --all` = 0 диагностик.
- Анти-дубликат баг-репортов: перед созданием репорта — поиск по `bug-report`.
- Гейт перед коммитом; источник `id` для `fix`.
- Сущности: документы, записи, отношения, типы, ссылки.

### 4.6. `todoc fix`

**Путь CLI:** `todoc fix`

**Назначение:** применяет один поддерживаемый фикс из `suggested_fixes`
диагностики. Работает review-first.

**Синтаксис:**

```bash
todoc fix --diagnostic ID [--preview] [--apply] [--if-hash H] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `--diagnostic ID` | `diag_…` | да | ID диагностики из **этого же** вывода `validate`. |
| `--preview` | флаг | нет | Показать план фикса без записи. |
| `--apply` | флаг | нет | Применить фикс. |
| `--if-hash H` | `sha256:…` | нет | CAS-предусловие: файл не должен измениться. |

**Вывод:**

- preview: `{diagnostic, preview: true, fix}`;
- apply: `{diagnostic, applied: true, new_hash}`.

**Пример:**

```bash
todoc validate --root KB --all
todoc fix --root KB --diagnostic diag_0042 --preview
todoc fix --root KB --diagnostic diag_0042 --apply
```

**Особенности:**

- Неизвестный/устаревший ID — `fix.diagnostic_not_found`, exit 3.
- Фикс не «лечит всё»: применяется ровно один предложенный вариант; после записи
  нужен повторный `validate`.

**Где применяется:** ремонт по правилу AGENTS.md; только после `--preview`.

### 4.7. `todoc doctor`

**Путь CLI:** `todoc doctor`

**Назначение:** read-only диагностика окружения и датасета: конфиг, индекс,
Python. Ничего не чинит автоматически.

**Синтаксис:**

```bash
todoc doctor [--check IDS] [--scope dataset|environment|all] [--fix] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип / значения | По умолчанию | Назначение |
|---|---|---|---|
| `--check IDS` | список ID через запятую | — | Конкретные проверки: `config`, `index`, `python`. |
| `--scope` | `dataset\|environment\|all` | — | Группа проверок. Неизвестное значение — `usage.error`, exit 2. |
| `--fix` | флаг | `false` | Отдельный режим ремонта (dry-run по умолчанию); не заменяет `fix` для диагностик. |

**Вывод:** элемент `data.datasets[]`:

```json
{
  "dataset_id": "dataset-80c70868",
  "scope": "dataset",
  "checks_total": 2,
  "passed": 2,
  "checks": [
    {"id": "config", "status": "pass", "message": "Dataset config loads."},
    {"id": "index", "status": "pass", "message": "Index generation is current."}
  ],
  "fix_mode": false
}
```

**Пример:**

```bash
todoc doctor --root demo --scope dataset
todoc doctor --root demo --check config,index
```

**Особенности:** `--scope` и `--check` сочетаются: сначала группа, затем
конкретные ID. `doctor` не пересобирает индекс и не меняет файлы.

**Где применяется:** стартовая диагностика окружения в скиле `todoc`; отличие
`doctor` (проверки) от `status` (снимок индекса).

### 4.8. `todoc status`

**Путь CLI:** `todoc status`

**Назначение:** быстрый снимок опубликованного поколения: собран ли индекс,
сколько документов и записей.

**Синтаксис:**

```bash
todoc status [--root PATH]…
```

**Атрибуты:** только общие.

**Вывод:** элемент `data.datasets[]`:

```json
{
  "dataset_id": "dataset-80c70868",
  "index_built": true,
  "generation_id": "044d5c044f30",
  "documents": 505,
  "records": 205
}
```

**Пример:**

```bash
todoc status --root demo
```

**Особенности:**

- До первой пересборки: `index_built: false`, `documents: null`, `records: null`
  (не `0` — ноль читался бы как «пустой датасет»).
- В этом случае конверт несёт `next_actions` с `todoc index rebuild`.
- Не пересобирает индекс; для этого — `index rebuild`.

**Где применяется:** быстрый снимок в скиле и в базовом цикле агента.

---

## 5. Индекс и производные артефакты

### 5.1. `todoc index status`

**Путь CLI:** `todoc index status`

**Назначение:** читает опубликованный снимок индекса, не пересобирая его.

**Синтаксис:**

```bash
todoc index status [--root PATH]…
```

**Атрибуты:** только общие.

**Вывод:** `data.datasets[]`:

```json
{
  "dataset_id": "example",
  "generation_id": null,
  "current": false,
  "corpus_digest": null,
  "created_at": null
}
```

**Пример:**

```bash
todoc index status --root /tmp/kb_example
```

**Особенности:** до первой пересборки `generation_id: null`. Снимок один и
перезаписывается на месте — `.todoc/index/` не растёт от числа запусков.

**Где применяется:** проверка «индекс опубликован?» перед чтением; диагностика
расхождений с `scan`.

### 5.2. `todoc index rebuild`

**Путь CLI:** `todoc index rebuild`

**Назначение:** пересобирает индекс из файлов и публикует новое поколение.

**Синтаксис:**

```bash
todoc index rebuild [--force] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `--force` | флаг | `false` | Пересчитать даже при неизменном `corpus_digest`. |

**Вывод:**

```json
{
  "dataset_id": "example",
  "generation_id": "50e4e7eff48c",
  "corpus_digest": "sha256:8d3f3dbf…",
  "reused": false,
  "folders": 1,
  "documents": 0,
  "records": 0,
  "relations": 0,
  "diagnostics": 0
}
```

**Пример:**

```bash
todoc index rebuild --root /tmp/kb_example
todoc index rebuild --root /tmp/kb_example --force
```

**Особенности:**

- Без `--force` валидный снимок переиспользуется: `reused: true`.
- Индекс — производный артефакт; источник истины — файлы.
- После импорта/мьюта скилов правило агента требует пересборки.

**Где применяется:** после `init`, `skills import`, массовых правок; перед
`status`/чтением, если индекс отсутствует.

---

## 6. Документы: `docs …`

> Ко всем командам группы применимы общие опции `--root`, `--output`,
> `--no-input`; ниже перечислены только специфичные атрибуты.

### 6.1. `todoc docs new`

**Путь CLI:** `todoc docs new`

**Назначение:** создаёт новый markdown-документ из стартового шаблона типа.
Create-only: существующий файл не перезаписывается.

**Синтаксис:**

```bash
todoc docs new --title T [--dir DIR] [--path P] [--type T] [--template NAME|PATH] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `--title T` | строка | — (обязателен) | Заголовок документа; попадает в `title` front matter. Из одних пробелов — `docs.empty_title`, exit 3. |
| `--dir DIR` | путь | `inbox` | Каталог назначения. Игнорируется, если задан `--path`. |
| `--path P` | относительный путь | — | Явный путь вместо `--dir` + slug. Нужен для кириллических заголовков: слаг наследует кириллицу (BUG-006). |
| `--type T` | `doc_type` | — | Тип документа: шаблон и структурные правила берутся из папки типа. |
| `--template` | ID типа или путь | — | Источник шаблона. Путь должен лежать внутри `DATA_ROOT`. |

**Вывод:**

```json
{
  "dataset_id": "example",
  "path": "notes/example-note.md",
  "title": "Пример заметки",
  "doc_type": "note",
  "template": ".todoc/doc_types/note/template.md",
  "hash": "sha256:96456391…"
}
```

**Пример:**

```bash
todoc docs new --root /tmp/kb_example --type note \
  --title "Пример заметки" --path notes/example-note.md
```

**Особенности:**

- Плейсхолдеры шаблона подставляются как текст: `{title}`, `{slug}`, `{date}`,
  `{type_id}`, `{id}`, `{format}`; неизвестные остаются как есть.
- Если тип не объявил шаблон — создаётся `# <заголовок>`.
- Ошибки: `types.unknown`, `types.template_missing`, `types.template_invalid`
  (шаблон нарушает структуру типа — файл не создаётся), `docs.target_exists`
  (exit 5), `access.outside_data_root` (exit 4).
- `docs new` **не пишет статус**: fm-статус добавляется отдельным `docs edit`
  (конвенция жизненного цикла; BUG-011/013 контекст).

**Где применяется:**

- Скилы жизненного цикла `skills/process/todoc-{capture,plan,…}`:
  `--type idea`, `--type plan`.
- Правило именования: русский `title` в метаданных, английский kebab-case файл —
  явный `--path`.
- Сущности: `doc_type` и его `template`/`required_sections`.

### 6.2. `todoc docs search`

**Путь CLI:** `todoc docs search`

**Назначение:** ограниченный лексический поиск по документам с provenance:
почему найден, какие термины совпали, где фрагмент.

**Синтаксис:**

```bash
todoc docs search --query Q [--type T] [--limit N] [--within PATH] [--budget BYTES] [--cursor C] [--tag TAG] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `--query Q` | строка | — (обязателен) | Поисковый запрос; кириллица поддерживается. |
| `--type T` | `doc_type` | — | Ограничить тип документов. |
| `--limit N` | int | `10` | Максимум результатов. |
| `--within PATH` | путь | — | Ограничить папкой/префиксом. |
| `--budget BYTES` | int | — | Бюджет объёма сниппетов. |
| `--cursor C` | строка-смещение | — | Следующая страница без пересечений. Нецелое — `usage.invalid_cursor`, exit 3. |
| `--tag TAG` | строка | — | Точный пост-фильтр по тегу front matter. |

**Вывод:** `data`:

```json
{
  "dataset_id": "dataset-80c70868",
  "total": 37,
  "returned": 2,
  "truncated": true,
  "cursor": "2",
  "items": [
    {
      "id": "doc:after-mcp-adapter",
      "path": "plan/after/mcp-adapter.after.md",
      "title": "AFTER: MCP-адаптер",
      "heading_path": ["Перспектива (НЕ сейчас): MCP-адаптер"],
      "rank": 1,
      "relevance": {"method": "lexical", "matched_by": ["lexical"]},
      "matched_terms": ["валидатор"],
      "snippet": {"text": "…", "line_start": 56, "line_end": 57}
    }
  ]
}
```

**Пример:**

```bash
todoc docs search --root demo --query "валидатор" --limit 3
todoc docs search --root demo --query "валидатор" --limit 3 --cursor 3
```

**Особенности:**

- `relevance` — лексическая, **не** семантическая; не трактовать как смысловую близость.
- `truncated: true` и `cursor` — часть контракта: top-N не равен полному результату.
- Пустой `--query` — `usage.error` (BUG-019 fixed).

**Где применяется:**

- Первый шаг правила чтения «сводка → оглавление → ветка».
- Анти-дубликат баг-репортов: поиск по симптому и компоненту.
- Сущности: документы и их `doc_type`/теги.

### 6.3. `todoc docs read`

**Путь CLI:** `todoc docs read`

**Назначение:** ограниченное чтение документа или его проекции: раздел, якорь,
диапазон строк, JSON Pointer, колонки/строки CSV.

**Синтаксис:**

```bash
todoc docs read --id ID \
  [--section S | --anchor A | --line-range N-M | --pointer P | \
   --columns C [--rows R] [--where K=V]] \
  [--budget BYTES] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `--id ID` | `doc:…` | — (обязателен) | Идентификатор документа. |
| `--section S` | строка | — | Раздел markdown по заголовку; окно до 40 строк (BUG-005). |
| `--anchor A` | строка | — | Раздел по anchor. |
| `--line-range N-M` | `N-M` | — | Диапазон строк, 1-based включительно. Некорректный — `usage.invalid_line_range`, exit 3. |
| `--pointer P` | JSON Pointer | — | Значение по RFC 6901 в JSON-документе. |
| `--columns C` | список | — | Колонки CSV (через запятую). |
| `--rows R` | int | — | Максимум строк CSV **после** `--where`. |
| `--where K=V` | `K=V` | — | Фильтр CSV; применяется до `--rows`. |
| `--budget BYTES` | int | `4000` для полного md | Бюджет текста. |

**Вывод зависит от формата:**

- Markdown без селектора: `{title, headings[], text}`; `headings[]` содержит
  `title`, `level`, `line`, `anchor`.
- Markdown с `--section`/`--anchor`: `{section, heading_path[], line_start,
  line_end, lines[], section_total_lines, truncated, text}`.
- Markdown с `--line-range`: `{lines[], text}`.
- JSON: `{value}`; с `--pointer` — значение по указателю.
- CSV: `{columns[], rows[], total, matched, truncated}`.
- Общие поля: `{dataset_id, id, path, format, doc_type, hash}`.

**Пример:**

```bash
todoc docs read --root demo --id doc:architecture-system --section "Слои"
```

```json
{
  "dataset_id": "dataset-80c70868",
  "id": "doc:architecture-system",
  "path": "architecture/system-architecture.md",
  "format": "markdown",
  "doc_type": "architecture-doc",
  "hash": "sha256:f10ccd8a…",
  "section": "Слои",
  "heading_path": ["Архитектура todoc: слои и адаптеры", "Слои"],
  "line_start": 13,
  "line_end": 23,
  "lines": ["## Слои", "", "| Слой | Каталог | Ответственность |"],
  "truncated": false,
  "text": "## Слои\n\n| Слой | Каталог | …"
}
```

**Пример CSV:**

```bash
todoc docs read --root demo --id doc:attachments/docs-inventory.csv \
  --columns doc_type --rows 2
```

**Особенности:**

- `--where` применяется **до** `--rows`: `--rows 3 --where k=v` вернёт три
  подходящие строки, а не три первые с последующей фильтрацией.
- `matched` — сколько строк подошло под условие; `total` — сколько их в файле.
- Полное чтение без селектора по умолчанию ограничено `--budget` (BUG-018).
- Ошибки: `docs.not_found`, `docs.section_not_found`, `usage.invalid_line_range`.

**Где применяется:**

- Правило чтения «не читать документ целиком на всякий случай».
- Скилы `todoc-docs` и `todoc` для bounded-чтения.
- Сущности: markdown-разделы, JSON-поля, CSV-строки.

### 6.4. `todoc docs tree`

**Путь CLI:** `todoc docs tree`

**Назначение:** компактная производная карта: папки и документы с типами,
правилами и метаданными папок.

**Синтаксис:**

```bash
todoc docs tree [--within PATH] [--max-depth N] [--match Q] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `--within PATH` | путь | — | Ограничить поддеревом. |
| `--max-depth N` | int | `3` | Глубина дерева. |
| `--match Q` | строка | — | Фильтр папок скорингом Фазы A (`.config.json`, score ≥ 0.25; порядок score → order → путь). |

**Вывод:** `data`:

```json
{
  "dataset_id": "dataset-80c70868",
  "folders": [
    {
      "folder_id": "folder:bugs",
      "path": "bugs",
      "parent_folder_id": "folder:.",
      "dir_type": "bugs",
      "rule_source": "rule:demo-dir-bugs",
      "title": "Баг-репорты",
      "description": "Дефекты движка и эксплуатации с воспроизведением.",
      "order": null
    }
  ],
  "documents": [
    {
      "document_id": "doc:architecture-system",
      "path": "architecture/system-architecture.md",
      "format": "markdown",
      "doc_type": "architecture-doc",
      "rule_source": "rule:fm-architecture-doc",
      "hash": "sha256:f10ccd8a…",
      "size": 2087,
      "title": "Архитектура todoc: слои и адаптеры",
      "status": "ok"
    }
  ],
  "total_folders": 86,
  "total_documents": 505,
  "max_depth": 1
}
```

**Пример:**

```bash
todoc docs tree --root demo --max-depth 2
todoc docs tree --root demo --match "баг"
```

**Особенности:** дерево молча усекается до 50 папок и 50 документов без флага
`truncated` (BUG-017); для полного состава используйте `--within`/`--max-depth`
или `scan`.

**Где применяется:** карта демо (`demo/HOME.md`), выбор папки, `docs suggest`.

### 6.5. `todoc docs suggest`

**Путь CLI:** `todoc docs suggest`

**Назначение:** подсказывает, куда положить документ или где искать: скоринг
папок по `.config.json` (Фаза A, детерминированно).

**Синтаксис:**

```bash
todoc docs suggest --query Q [--limit N] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `--query Q` | строка | — (обязателен) | Запрос; кириллица работает. |
| `--limit N` | int | `5` | Максимум кандидатов. |

**Вывод:** `data`:

```json
{
  "query": "баг-репорт",
  "threshold": 0.25,
  "truncated": false,
  "candidates": [
    {
      "path": "bugs",
      "title": "Баг-репорты",
      "score": 1.0,
      "score_raw": 0.2,
      "reason": "title/desc/tags: баг",
      "order": null
    }
  ],
  "discarded": [
    {"path": "plan", "title": "Планы реализации", "score": 0.0, "score_raw": 0.0, "reason": "", "order": null}
  ]
}
```

**Пример:**

```bash
todoc docs suggest --root demo --query "баг-репорт" --limit 2
```

**Особенности:** `score` нормирован к максимуму — единственный кандидат всегда
получает `1.0` (BUG-009); сравнивайте `score_raw`. `discarded[]` показывает, что
не прошло порог.

**Где применяется:** правило «куда положить/где искать» в контракте скилов;
выбор `--dir` для `docs new`.

### 6.6. `todoc docs links`

**Путь CLI:** `todoc docs links`

**Назначение:** инвентаризация локальных ссылок: сколько всего, сколько битых,
где именно.

**Синтаксис:**

```bash
todoc docs links [--limit N] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `--limit N` | int | `20` | Максимум элементов в `items[]`. |

**Вывод:**

```json
{
  "total": 753,
  "broken": 10,
  "items": [
    {
      "path": "glossary/data-root.md",
      "target": "term:data-root",
      "kind": "wikilink",
      "line": 13
    }
  ],
  "truncated": true
}
```

**Пример:**

```bash
todoc docs links --root demo --limit 20
```

**Особенности:** тот же резолв, что в `validate`; `broken` — счётчик, `items[]`
может быть усечён. Это замена отсутствовавшей команды linkcheck (BUG-007).

**Где применяется:** гейт `tools/linkcheck.py` и проверка ссылок перед коммитом.

### 6.7. `todoc docs flow render`

**Путь CLI:** `todoc docs flow render`

**Назначение:** строит витрину флоу из записи `flow`: state machine, таблицу
решений, mermaid, lineage, термины.

**Синтаксис:**

```bash
todoc docs flow render --id FLOW_ID [--section state|table|mermaid|lineage|terms] \
  [--write PATH] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип / значения | Обязателен | Назначение |
|---|---|---|---|
| `--id FLOW_ID` | `flow:…` | да | Запись флоу. |
| `--section` | `state\|table\|mermaid\|lineage\|terms` | нет | Одна секция вместо полного markdown. |
| `--write PATH` | путь | нет | Материализовать витрину в md с `derived_from`. |

**Вывод:** `{dataset_id, id, section, text}`.

**Пример:**

```bash
todoc docs flow render --root demo --id flow:order-placement --section state
```

```json
{
  "dataset_id": "dataset-80c70868",
  "id": "flow:order-placement",
  "section": "state",
  "text": "## Жизненный цикл\n\nstateDiagram-v2\n[*] --> created\n…"
}
```

**Особенности:**

- `--write` пишет только derived-цель (`docs.flow_render_not_derived`);
  перезапись разрешена только для derived, дрейф ловит `stale`.
- Front matter витрины ссылается на фрагменты записи (`/states`, `/outcomes`,
  `/tree`, `/relations`).

**Где применяется:** витрины `demo/flows/`, интероп-экспорты, документация
бизнес-флоу; сущность `flow`.

### 6.8. `todoc docs flow walk`

**Путь CLI:** `todoc docs flow walk`

**Назначение:** проходит дерево решений флоу: ветви по приоритету, свойства
развилок, основной путь или все ациклические пути до терминалов.

**Синтаксис:**

```bash
todoc docs flow walk --id FLOW_ID [--at NODE] [--all-paths] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Назначение |
|---|---|---|
| `--id FLOW_ID` | `flow:…` | Запись флоу (обязателен). |
| `--at NODE` | id узла | Старт обхода с узла. |
| `--all-paths` | флаг | Все ациклические пути до терминалов вместо основного. |

**Вывод:**

```json
{
  "dataset_id": "dataset-80c70868",
  "id": "flow:order-placement",
  "at": null,
  "steps": [
    {"node_id": "start", "type": "action", "prompt": "Покупатель подтверждает оплату заказа", "mode": "auto"},
    {"node_id": "q-account", "type": "question", "prompt": "Аккаунт покупателя заблокирован?", "mode": "auto"},
    {"node_id": "out-acc-blocked", "type": "terminal", "prompt": "Заказ отклоняется", "mode": "auto"}
  ]
}
```

**Пример:**

```bash
todoc docs flow walk --root demo --id flow:order-placement
todoc docs flow walk --root demo --id flow:order-placement --all-paths
```

**Особенности:** обход детерминирован; при `--all-paths` результат содержит все
пути, а не только первый.

**Где применяется:** анализ сценариев, генерация ASL, проверка достижимости
терминалов; сущность `flow.tree`.

### 6.9. `todoc docs status`

**Путь CLI:** `todoc docs status`

**Назначение:** читает или меняет `status` во front matter markdown-документа.

**Синтаксис:**

```bash
todoc docs status --id ID [--set VALUE] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `--id ID` | `doc:…` | да | Документ. |
| `--set VALUE` | строка | нет | Новое значение статуса; без `--set` — чтение. |

**Вывод:** `{dataset_id, id, status}`.

**Пример:**

```bash
todoc docs status --root demo --id doc:architecture-system
todoc docs status --root demo --id doc:plan-… --set active
```

**Особенности:**

- Набор значений — `allowed_statuses` doc_type (`docs.status_not_allowed`, exit 3).
- Документ без поля `status` не получает его молча (`docs.no_status_field`).
- Запись точечная: меняется строка статуса + бампается `updated:`; CAS и
  history-ревизия.
- Ошибки: `docs.not_found`, `usage.error` (пробелы вокруг значения).

**Где применяется:** скилы жизненного цикла (capture → plan → transitions);
сущности `doc_type.allowed_statuses`.

### 6.10. `todoc docs edit`

**Путь CLI:** `todoc docs edit`

**Назначение:** патчевая правка markdown-документа: замена строк по номерам.
Review-first: без `--apply` — только план.

**Синтаксис:**

```bash
todoc docs edit --id ID --patch-file F [--preview] [--apply] [--if-hash H] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `--id ID` | `doc:…` | да | Документ. |
| `--patch-file F` | путь к JSON | да | Патч: `{"ops":[{"line":12,"text":"новая строка"}]}`. |
| `--preview` | флаг | нет | Показать план без записи. |
| `--apply` | флаг | нет | Применить патч. |
| `--if-hash H` | `sha256:…` | нет | CAS-предусловие; несовпадение — exit 5. |

**Вывод:**

- preview: `{dataset_id, id, path, preview: true, ops[]}`;
- apply: `{applied: true, new_hash}`.

**Пример:**

```bash
todoc docs edit --root /tmp/kb_example --id doc:notes/example-note.md \
  --patch-file patch.json --preview
```

```json
{
  "dataset_id": "example",
  "id": "doc:notes/example-note.md",
  "path": "notes/example-note.md",
  "preview": true,
  "ops": [{"line": 2, "text": "id: doc:notes/example-note.md"}]
}
```

**Особенности:**

- Только **замена** существующих строк (1-based); вставки и удаления не
  поддерживаются (BUG-004).
- `--preview` не показывает нумерацию результата — сверяйте строки повторным
  чтением (BUG-014).
- Для широкой правки нескольких файлов используйте `change`, а не серию `edit`.

**Где применяется:** правка fm-статусов после `docs new`, точечные исправления,
re-anchor `derived_from`; сущности — markdown-документы.

### 6.11. `todoc explain-path`

**Путь CLI:** `todoc explain-path` (команда верхнего уровня; относится к
типизации документов и папок)

**Назначение:** объясняет, какое правило сработало для пути: `doc_type` для
документа или `dir_type` для папки, формат, источник правила, идентификатор.

**Синтаксис:**

```bash
todoc explain-path PATH [--match Q] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `PATH` | positional | да | Путь документа или папки относительно `DATA_ROOT`. |
| `--match Q` | строка | нет | Участвовать в скоринге Фазы A (как `docs tree --match`). |

**Вывод для документа:**

```json
{
  "dataset_id": "dataset-80c70868",
  "path": "plan/after/mcp-adapter.after.md",
  "doc_type": "after-plan",
  "format": "markdown",
  "rule_source": "rule:fm-after-plan",
  "document_id": "doc:after-mcp-adapter",
  "title": "Планы реализации",
  "description": "Планы работ и дорожки исполнения задач.",
  "order": null
}
```

**Вывод для папки:**

```json
{
  "dataset_id": "dataset-80c70868",
  "path": "bugs",
  "folder": true,
  "dir_type": "bugs",
  "rule_source": "rule:demo-dir-bugs",
  "title": "Баг-репорты",
  "description": "Дефекты движка и эксплуатации с воспроизведением.",
  "order": null
}
```

**Пример:**

```bash
todoc explain-path plan/after/mcp-adapter.after.md --root demo
todoc explain-path bugs --root demo
```

**Особенности:**

- `rule_source` показывает, какое правило сработало: `rule:<id>`, `reserved`,
  `default`, `ambiguous`.
- Для папки поля `title/description/order` берутся из её `.config.json`.
- Несуществующий путь — `explain.path_not_found`, exit 3.

**Где применяется:**

- Отладка резолва `doc_type`/`dir_type`; объяснение, почему документ попал в
  `unknown` (BUG-001).
- Скил `todoc` и правило «перепроверяй каждый шаг».
- Сущности: `doc_type`, `dir_type`, правила front matter и папочные конфиги.

---

## 7. Записи: `records …`

> Общие опции (`--root`, `--output`, `--no-input`) применимы ко всем командам
> группы; ниже — только специфичные атрибуты.

### 7.1. `todoc records create`

**Путь CLI:** `todoc records create`

**Назначение:** создаёт JSON-запись типа `entity_type` из входного файла.
Create-only: дубль `record_id` или занятый путь отклоняются.

**Синтаксис:**

```bash
todoc records create --type T --input-file F [--preview] [--apply] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `--type T` | `entity_type` | да | Тип записи из реестра. |
| `--input-file F` | путь к JSON | да | Черновик записи. |
| `--preview` | флаг | нет | Показать план без записи. |
| `--apply` | флаг | нет | Создать запись. |

**Вывод:**

- preview: `{dataset_id, preview: true, plan: {target_path, expected_hash,
  new_hash, basis, validations}}`;
- apply: `{created, new_hash}`.

**Пример:**

```bash
todoc records create --root /tmp/kb_example --type note \
  --input-file note.json --preview
```

```json
{
  "dataset_id": "example",
  "preview": true,
  "plan": {
    "target_path": "records/note/example.json",
    "expected_hash": null,
    "new_hash": "sha256:d12effc4…",
    "basis": "Create note record note:example",
    "validations": ["schema", "relations", "no-overwrite"]
  }
}
```

**Особенности:**

- Входной JSON парсится строго: дубли ключей и `NaN` отклоняются.
- Путь строится из `path_template` с `{record_id}`/`{slug}`; имена
  санитизируются `portable_name()` (Windows-зарезервированные имена, `<>:"/\|?*`).
- Ошибки: `record.duplicate_id` (exit 5), `record.target_exists` (exit 5),
  неизвестный тип (exit 3), `record.unsafe_path`.
- Флага `--if-hash-new` больше нет (P1-4): гарантия create-only безусловна.

**Где применяется:**

- Скилы жизненного цикла: `--type task` с `implements`/`subtask_of`.
- Правило AGENTS.md: записи — только `--preview` → `--apply`.
- Сущности: `entity_type`, `schema.json`, `required_fields`, `path_template`.

### 7.2. `todoc records list`

**Путь CLI:** `todoc records list`

**Назначение:** список записей с фильтрами по типу, времени и отношению.

**Синтаксис:**

```bash
todoc records list [--type T] [--since D] [--until D] [--relation TYPE=ID] [--limit N] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `--type T` | `entity_type` | — | Тип записи. |
| `--since D` | дата/ISO | — | Нижняя граница. |
| `--until D` | дата/ISO | — | Верхняя граница. |
| `--relation TYPE=ID` | `type_id=record_id` | — | Фильтр по ребру. |
| `--limit N` | int | `200` | Максимум записей. |

**Вывод:** `{dataset_id, total, returned, truncated, items[]}`; элемент —
`{record_id, entity_type, dataset_id, path, hash, data}`.

**Пример:**

```bash
todoc records list --root demo --type task --limit 2
todoc records list --root demo --relation "implements=document:plan-interop-exports"
```

**Особенности:** `--type` ожидает `entity_type`, не `doc_type`; для `doc_type`
используйте `records query` (BUG-020 — пустой успех вместо диагностики неймспейса).

**Где применяется:** обзор задач, планов, метрик; скилы исполнения.

### 7.3. `todoc records query`

**Путь CLI:** `todoc records query`

**Назначение:** выполняет сохранённый декларативный QuerySpec с фильтрами,
лимитом и опциональным срезом по времени правды.

**Синтаксис:**

```bash
todoc records query --query-file F [--as-of D] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `--query-file F` | путь к JSON | да | QuerySpec. |
| `--as-of D` | ISO-8601 | нет | Только записи, бывшие правдой на момент T. |

**Формат QuerySpec:**

```json
{
  "schema_version": 1,
  "name": "tasks-by-project",
  "entity_type": "task",
  "filters": {"status": "done"},
  "sort_hint": "record_id",
  "limit": 100
}
```

**Фильтры:**

| Оператор | Смысл |
|---|---|
| `"field": value` | точное равенство |
| `{"$in": [...]}` | вхождение в список |
| `{"$gte": v, "$lte": v}` | диапазон (можно вместе) |

**Вывод:** `{dataset_id, as_of, total, truncated, items[]}`.

**Пример:**

```bash
todoc records query --root demo \
  --query-file demo/.todoc/queries/tasks-by-project.json
```

**Особенности:**

- `--as-of` — полуоткрытый интервал `valid_from <= T < valid_to`; записи без
  темпоральных полей видны всегда. Неразбираемая дата — `temporal.invalid_instant`,
  exit 3.
- Пути к полям — через точку (`volume.unit`).
- Никаких `eval`, SQL и shell.

**Где применяется:** анализ багов по `agent_impact`, решения, метрики;
сущности с темпоральными полями.

### 7.4. `todoc records read`

**Путь CLI:** `todoc records read`

**Назначение:** читает одну запись, опционально — проекцию `--view`.

**Синтаксис:**

```bash
todoc records read --id ID [--view NAME] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `--id ID` | `type:slug` | да | Идентификатор записи. |
| `--view NAME` | имя view | нет | Список полей из `views` описателя типа. |

**Вывод:** `{dataset_id, record_id, path, data, mentioned_in[]}`; `mentioned_in`
— где запись упомянута в документах (`file`, `line`, `fragment`).

**Пример:**

```bash
todoc records read --root demo --id term:data-root
todoc records read --root demo --id document:constitution --view summary
```

**Особенности:** `--view` не меняет файл; это проекция ответа. Неизвестный view —
ошибка использования.

**Где применяется:** чтение сущностей `flow`, `rule`, `term`, `task`, `change`;
скилы и агентские проверки.

### 7.5. `todoc records aggregate`

**Путь CLI:** `todoc records aggregate`

**Назначение:** суммирует числовую метрику по записям с обязательным
provenance: единицы, формула, группы, исходные ID, полнота.

**Синтаксис:**

```bash
todoc records aggregate --metric FIELD [--type T] [--group-by FIELD] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `--metric FIELD` | поле | да | Числовое поле или объект `{value, unit}`. |
| `--type T` | `entity_type` | нет | Ограничить тип. |
| `--group-by FIELD` | поле | нет | Группировка; отсутствующее значение → группа `unknown`. |

**Вывод:**

```json
{
  "entity_type": "metric",
  "metric": "value",
  "units": "",
  "group_units": {"benchmark": "ratio", "performance": "ms", "tests": "count"},
  "formula": "sum(value)",
  "groups": {"benchmark": 4.473, "performance": 10706.0, "tests": 3933.0},
  "incoming_ids": ["metric:bench-defect-f1", "metric:bench-locations"],
  "completeness": "complete",
  "dataset_id": "dataset-80c70868"
}
```

**Пример:**

```bash
todoc records aggregate --root demo --type metric --metric value --group-by aspect
```

**Особенности:**

- Смешение единиц в одной агрегации — `query.unit_mismatch`, exit 3.
- Нечисловое поле — `query.unknown_metric`; нет записей типа — `query.no_records`.
- `units` пуст, когда единицы в группах различаются; смотрите `group_units`.
- `incoming_ids` и `completeness` позволяют проверить, из чего сложилась сумма.

**Где применяется:** метрики бенчмарка, покрытие, счётчики; скил `todoc` требует
отчитываться units/formula/provenance и воздерживаться при неизвестной метрике.

### 7.6. `todoc records status`

**Путь CLI:** `todoc records status`

**Назначение:** читает или меняет **только** поле `status` JSON-записи.

**Синтаксис:**

```bash
todoc records status --id ID [--set VALUE] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `--id ID` | `type:slug` | да | Запись. |
| `--set VALUE` | строка | нет | Новое значение; без `--set` — чтение. |

**Вывод:** `{dataset_id, id, status}`.

**Пример:**

```bash
todoc records status --root demo --id task:interop-converters-cli
todoc records status --root demo --id task:… --set done
```

**Особенности:**

- Набор — enum статуса из `schema.json`; pre-check `records.status_not_allowed`,
  файл не трогается.
- Атомарная запись поверх CAS + history-ревизия.
- Терминальный `done` — только по явной фразе пользователя (конвенция, не guard).

**Где применяется:** скил `todoc-execute`; сущность `task.status`.

### 7.7. `todoc records undo-relation`

**Путь CLI:** `todoc records undo-relation`

**Назначение:** точечно откатывает одно ребро из ревизий журнала.

**Синтаксис:**

```bash
todoc records undo-relation --id ID --pointer /relations/N \
  [--apply] [--expected-hash H] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `--id ID` | `type:slug` | да | Запись. |
| `--pointer P` | `/relations/N` | да | Путь ребра в массиве. |
| `--apply` | флаг | нет | Записать откат; без него — preview. |
| `--expected-hash H` | `sha256:…` | нет | CAS-предусловие. |

**Вывод:** preview — план; apply — `{applied: true, new_hash}`.

**Пример:**

```bash
todoc records undo-relation --root demo --id task:… \
  --pointer /relations/0 --apply
```

**Особенности:** подходит для ошибочных `implements`, `subtask_of`,
`belongs_to`; файл не перезаписывается целиком.

**Где применяется:** исправление графа задач/планов; сущности и `relations`.

---

## 8. Связи: `relations …`

### 8.1. `todoc relations graph`

**Путь CLI:** `todoc relations graph`

**Назначение:** BFS по типизированным рёбрам от записи; обход ненаправленный.

**Синтаксис:**

```bash
todoc relations graph --from ID [--type T] [--depth N] [--limit N] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `--from ID` | `type:slug` | — (обязателен) | Стартовая запись. |
| `--type T` | `relation_type` | — | Только рёбра этого типа. |
| `--depth N` | int | `1` | Глубина BFS. |
| `--limit N` | int | `100` | Максимум рёбер. |

**Вывод:**

```json
{
  "dataset_id": "dataset-80c70868",
  "from": "flow:order-placement",
  "edges": [
    {"type_id": "depends_on", "from": "flow:order-placement", "to": "dep:billing"},
    {"type_id": "belongs_to", "from": "flow:order-placement", "to": "rule:account-blocked-v1"}
  ],
  "total": 10
}
```

**Пример:**

```bash
todoc relations graph --root demo --from flow:order-placement --depth 1
```

**Особенности:** ребро видно с обоих концов; `limit` ограничивает ответ, а не
граф.

**Где применяется:** зависимости флоу, задачи→планы, трассировка изменений;
скил `todoc`.

### 8.2. `todoc relations tree`

**Путь CLI:** `todoc relations tree`

**Назначение:** вложенное дерево связей с группировкой по `type_id` и пометкой
направления.

**Синтаксис:**

```bash
todoc relations tree --from ID [--type T] [--depth N] [--limit N] [--root PATH]…
```

**Атрибуты:** те же, что у `relations graph`.

**Вывод:**

```json
{
  "dataset_id": "dataset-80c70868",
  "root": "flow:order-placement",
  "groups": [
    {
      "type_id": "depends_on",
      "edges": [
        {"direction": "out", "id": "dep:billing"},
        {"direction": "out", "id": "dep:pricing"}
      ]
    }
  ],
  "truncated": false
}
```

**Пример:**

```bash
todoc relations tree --root demo --from flow:order-placement --depth 1
```

**Особенности:** `direction` — `in`/`out` относительно корня; mention помечен.

**Где применяется:** обзор окружения сущности, объяснение связей в отчётах.

---

## 9. Типы: `types …`

### 9.1. `todoc types list`

**Путь CLI:** `todoc types list`

**Назначение:** каталог всех зарегистрированных типов: папки, документы, записи,
отношения.

**Синтаксис:**

```bash
todoc types list [--root PATH]…
```

**Атрибуты:** только общие.

**Вывод:** `{dataset_id, dir_types[], doc_types[], entity_types[], relation_types[]}`.

**Пример:**

```bash
todoc types list --root demo
```

**Особенности:** это источник истины для счётчиков типов; README-числа сверяются
с этим выводом (AGENTS.md, правило 5).

**Где применяется:** выбор `--type` для `docs new`/`records create`; аудит
реестра.

### 9.2. `todoc types show`

**Путь CLI:** `todoc types show`

**Назначение:** показывает описатель типа, путь к шаблону, четыре CRUD-промпта
и схему с признаком существования.

**Синтаксис:**

```bash
todoc types show TYPE_ID [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `TYPE_ID` | positional | да | ID типа. |

**Вывод:** `{dataset_id, kind, type{…}, template{path, exists}, prompts{read,create,edit,delete}, schema{path, exists}}`.

**Пример:**

```bash
todoc types show task --root demo
```

**Особенности:** отсутствующий файл виден как `exists: false`, а не исчезает из
ответа; `schema` равен `null` у типов, кроме записи.

**Где применяется:** проверка полноты типа перед созданием; сущности
`doc_type`/`entity_type`/`dir_type`/`relation_type`.

### 9.3. `todoc types prompt`

**Путь CLI:** `todoc types prompt`

**Назначение:** выдаёт стартовый промпт типа для одной CRUD-операции.

**Синтаксис:**

```bash
todoc types prompt TYPE_ID [--op read|create|edit|delete] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `TYPE_ID` | positional | — (обязателен) | ID типа. |
| `--op` | `read\|create\|edit\|delete` | `create` | Операция. |

**Вывод:** `{dataset_id, type_id, kind, operation, path, prompt, chars}`.

**Пример:**

```bash
todoc types prompt bug-report --op create --root demo
```

**Особенности:** ошибки `types.prompt_missing`, `types.unknown` (exit 3);
неизвестная операция — exit 2. Промпт — это инструкция, а не шаблон файла.

**Где применяется:** правило AGENTS.md «стартовый промпт типа перед созданием»;
анти-дубликат баг-репортов; сущности типов.

### 9.4. `todoc types guide`

**Путь CLI:** `todoc types guide`

**Назначение:** генерирует полный справочник типовой системы.

**Синтаксис:**

```bash
todoc types guide [--format markdown|json] [--out PATH] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `--format` | `markdown\|json` | `markdown` | Формат сгенерированного справочника. |
| `--out PATH` | путь | — | Записать справочник в файл вместо stdout. |

**Вывод:** сам справочник (markdown или JSON) **без конверта**; при `--out` —
файл.

**Пример:**

```bash
todoc types guide --root demo --format markdown
todoc types guide --root demo --format json --out /tmp/types.json
```

**Особенности:** это единственная команда, которая печатает не конверт, а
сгенерированный документ; `--output` при этом не влияет на содержимое.

**Где применяется:** генерация `references/type-system.generated.md`, аудит
типов, документация для агента.

---

## 10. История: `log` / `show` / `diff` / `blame` / `timeline` / `revert` / `tag` / `history …`

Журнал живёт в `.todoc/history/` и пишется **по одному событию на запись файла**,
а не на запуск команды. Событие несёт `rev` (12 знаков SHA-256), `kind`, `actor`,
`change_id`, `basis` и по каждому пути `{path, before, after, git_head, ranges}`.

`kind`: `doc.create`, `doc.edit`, `doc.fix`, `record.create`, `record.edit`,
`change.open`, `change.apply`, `change.archive`, `change.revert`, `snapshot`,
`external.change`.

### 10.1. `todoc log`

**Путь CLI:** `todoc log`

**Назначение:** журнал событий записи: что, когда и в каких строках менялось.

**Синтаксис:**

```bash
todoc log [--path P] [--section S] [--kind K] [--change C] [--tag T] \
  [--since D] [--until D] [--limit N] [--cursor C] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `--path P` | путь | — | Только события этого файла. |
| `--section S` | заголовок | — | Только события, пересекающие раздел; требует `--path`. |
| `--kind K` | вид события | — | Фильтр по `kind`. |
| `--change C` | `change:…` | — | События изменения. |
| `--tag T` | имя метки | — | События с меткой. |
| `--since D` / `--until D` | дата/ISO | — | Диапазон. |
| `--limit N` | int | `20` | Размер страницы. |
| `--cursor C` | строка | — | Следующая страница. |

**Вывод:** `{events[], total, truncated, cursor}`; свежие первыми.

**Пример:**

```bash
todoc log --root demo --limit 2
todoc log --root demo --path docs/state/03-cli-reference.md --section "Команды"
```

**Особенности:** `--section` без `--path` — ошибка использования; `ranges` —
1-based включительные диапазоны строк.

**Где применяется:** аудит правок, BUG-012 (history-ревизии загрязняют git),
контекст изменения.

### 10.2. `todoc show`

**Путь CLI:** `todoc show`

**Назначение:** содержимое файла **на** ревизии (без `REV` — текущее).

**Синтаксис:**

```bash
todoc show [REV] --path P [--budget B] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `REV` | positional | нет | Ревизия; без неё — текущее состояние. |
| `--path P` | путь | да | Файл. |
| `--budget B` | int | — | Бюджет содержимого. |

**Вывод:** `{path, rev, content}`.

**Пример:**

```bash
todoc show c9e578daaf4d --root demo --path docs/state/03-cli-reference.md
```

**Особенности:** семантика как `git show <rev>:<path>` — состояние **после**
события. Если снимка нет — `history.revision_unknown`.

**Где применяется:** проверка «что было», восстановление контекста.

### 10.3. `todoc diff`

**Путь CLI:** `todoc diff`

**Назначение:** разница между двумя ревизиями файла; без `REV_B` — против
текущего состояния.

**Синтаксис:**

```bash
todoc diff REV_A [REV_B] --path P [--context N] [--budget B] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `REV_A` | positional | — (обязателен по смыслу) | Базовая ревизия. |
| `REV_B` | positional | текущее | Вторая ревизия. |
| `--path P` | путь | — (обязателен) | Файл. |
| `--context N` | int | `3` | Контекстных строк. |
| `--budget B` | int | — | Бюджет диффа; также `limits.max_diff_lines`. |

**Вывод:** `{changed, lines, diff[]}`.

**Пример:**

```bash
todoc diff c9e578daaf4d --root demo --path docs/state/03-cli-reference.md
```

**Особенности:** дифф ограничен `limits.max_diff_lines` (2000); при превышении
обрезается.

**Где применяется:** проверка правок перед `change apply`, аудит.

### 10.4. `todoc blame`

**Путь CLI:** `todoc blame`

**Назначение:** кто и когда менял файл или раздел.

**Синтаксис:**

```bash
todoc blame --path P [--section S] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `--path P` | путь | да | Файл. |
| `--section S` | заголовок | нет | Только раздел. |

**Вывод:** `{entries[]}` с `rev`, `at`, `kind`, `actor`, `ranges`.

**Пример:**

```bash
todoc blame --root demo --path docs/state/03-cli-reference.md
```

**Особенности:** пустая история — пустой `entries[]`, не ошибка.

**Где применяется:** атрибуция решений, поиск автора изменения.

### 10.5. `todoc timeline`

**Путь CLI:** `todoc timeline`

**Назначение:** единая лента событий записи (время знания) и интервалов фактов
(время правды) в одном хронологическом порядке.

**Синтаксис:**

```bash
todoc timeline [--as-of D] [--path P] [--limit N] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `--as-of D` | ISO-8601 | — | Срез обеих половин одним моментом. |
| `--path P` | путь | — | Только события и факты файла. |
| `--limit N` | int | `200` | Максимум записей. |

**Вывод:** `{dataset_id, as_of, path, count, truncated, entries[]}`; запись имеет
`kind` (`fact` или вид события) и `entry` (`fact`/`event`).

**Пример:**

```bash
todoc timeline --root demo --as-of 2026-11-26 --limit 20
```

**Особенности:** закрытый `superseded_at` факт остаётся в ленте и файле —
инвалидация вместо удаления; сортировка детерминированная.

**Где применяется:** «что было известно на дату T»; би-темпоральный анализ.

### 10.6. `todoc revert`

**Путь CLI:** `todoc revert`

**Назначение:** откат файла к ревизии. Без `--apply` — только план.

**Синтаксис:**

```bash
todoc revert REV --path P [--apply] [--expected-hash H] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `REV` | positional | да | Ревизия. |
| `--path P` | путь | да | Файл. |
| `--apply` | флаг | нет | Записать откат. |
| `--expected-hash H` | `sha256:…` | нет | CAS-предусловие. |

**Вывод:** план `{applied: false, current_hash, new_hash, range_conflict}`;
apply — запись + своё событие.

**Пример:**

```bash
todoc revert c9e578daaf4d --root demo --path inbox/bug-055.md --apply
```

**Особенности:**

- Семантика как `git revert`: образ **до** события. Для создания файла/базовой
  линии состояния «до» нет — `history.revision_unknown`.
- Если файл менялся после `REV`, появляется предупреждение
  `history.range_conflict`: откат сотрёт более поздние правки.

**Где применяется:** точечный откат ошибочной правки; не путать с `change revert`
(откат всего изменения к baseline).

### 10.7. `todoc tag`

**Путь CLI:** `todoc tag`

**Назначение:** ставит метку на ревизию — привязка истории к релизу.

**Синтаксис:**

```bash
todoc tag NAME [--rev R] [--message M] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `NAME` | positional | — (обязателен) | Имя метки. |
| `--rev R` | ревизия | последнее событие | На что ставить метку. |
| `--message M` | строка | `""` | Сообщение. |

**Вывод:** `{dataset_id, tag, rev, at, message}`.

**Пример:**

```bash
todoc tag v0.1 --root demo --message "первый срез"
```

**Особенности:** имя метки разрешается вместо `rev` в `log --tag` и `context --tag`.

**Где применяется:** релизы, `change archive --tag`, контекст задачи по метке.

### 10.8. `todoc history gc`

**Путь CLI:** `todoc history gc`

**Назначение:** удаляет события и снимки, на которые больше никто не ссылается.

**Синтаксис:**

```bash
todoc history gc [--keep-objects N] [--purge-before D] [--dry-run] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `--keep-objects N` | int | `limits.max_history_objects` (20000) | Сколько снимков оставить. |
| `--purge-before D` | дата/ISO | — | Стереть события старше даты. |
| `--dry-run` | флаг | `false` | Показать план без удаления. |

**Вывод:** `{removed_events, kept_events, objects_before, objects_referenced,
orphans_removed, trimmed_for_size, objects_trimmed, dry_run}`.

**Пример:**

```bash
todoc history gc --root demo --dry-run
```

**Особенности:** потолки берутся из `limits` датасета; обрезка снимков настоящая:
`show`/`revert` у затёртой ревизии честно отвечают `history.object_missing`.

**Где применяется:** обслуживание `.todoc/history/`, ритуал BUG-012.

### 10.9. `todoc history adopt`

**Путь CLI:** `todoc history adopt`

**Назначение:** снимает текущее состояние как базовую линию журнала (миграция
существующего датасета).

**Синтаксис:**

```bash
todoc history adopt [--root PATH]…
```

**Атрибуты:** только общие.

**Вывод:** `{rev, paths}`.

**Пример:**

```bash
todoc history adopt --root demo
```

**Особенности:** создаёт событие `snapshot`; откат к базовой линии невозможен.

**Где применяется:** подключение истории к датасету, где её раньше не было.

### 10.10. `todoc history export`

**Путь CLI:** `todoc history export`

**Назначение:** копирует `.todoc/history/` целиком — бэкап для embedded-бэкенда.

**Синтаксис:**

```bash
todoc history export --to PATH [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `--to PATH` | путь | да | Куда копировать; только внутри `DATA_ROOT`. |

**Вывод:** `{exported, to}`.

**Пример:**

```bash
todoc history export --root demo --to .todoc/history-backup
```

**Особенности:** путь вне корня — `access.outside_data_root`, exit 4.

**Где применяется:** бэкап перед `history gc`, перенос истории.

---

## 11. Изменения: `change …` и `context`

Изменение — обычная запись `entity_type: change`, поэтому ему доступны валидация
схемы, `records query --where status=…` и обход `blocked_by`. Папка изменения
живёт в `DATA_ROOT`, а не в `.todoc/`:

```text
changes/<change-id>/
├── change.json          # машиносостояние
├── proposal.md          # зачем это изменение
├── tasks.md             # пункты `- [ ] …`, их считает verify
└── deltas/<target>.md   # дельты: что меняется в целевых файлах
changes/archive/<YYYY-MM-DD>-<change-id>/   # после change archive
```

Статусы: `proposed` → `in_progress` → `blocked` → `applied` → `archived` |
`reverted`. Дельта — markdown с front matter и операциями по якорям:

```markdown
---
target: docs/state/09-storage-and-index.md
base_hash: sha256:aa…      # опционально
order: 1                   # опционально
---

## MODIFIED: ## Поколение индекса
…новое тело раздела…

## ADDED: ## Журнал событий
…

## REMOVED: ## Устаревшее
```

### 11.1. `todoc change list`

**Путь CLI:** `todoc change list`

**Назначение:** список изменений; `--status` фильтрует по жизненному циклу.

**Синтаксис:**

```bash
todoc change list [--status S] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Назначение |
|---|---|---|
| `--status S` | статус | Фильтр: `proposed`, `in_progress`, `blocked`, `applied`, `archived`, `reverted`. |

**Вывод:** `{changes[]}` — активные и архивные.

**Пример:**

```bash
todoc change list --root demo --status proposed
```

**Особенности:** архивные не исчезают из списка.

**Где применяется:** обзор незавершённых работ; сущность `change`.

### 11.2. `todoc change open`

**Путь CLI:** `todoc change open`

**Назначение:** открывает изменение и снимает базовую линию: хеши артефактов и
список диагностик.

**Синтаксис:**

```bash
todoc change open --title T [--blocked-by ID]… [--artifact P]… [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `--title T` | строка | да | Заголовок; из него выводится `change-id` (транслитерация, при неудаче — `change-<8 hex>`). |
| `--blocked-by ID` | `change:…`, повторяемый | нет | Зависимость. |
| `--artifact P` | путь, повторяемый | нет | Файл, который изменится. |

**Вывод:** `{dataset_id, change_id, path, status, artifacts, next}`.

**Пример:**

```bash
todoc change open --root /tmp/kb_example --title "Пример изменения" \
  --artifact notes/example-note.md
```

```json
{
  "dataset_id": "example",
  "change_id": "change:primer-izmeneniya",
  "path": "changes/primer-izmeneniya/change.json",
  "status": "proposed",
  "artifacts": ["notes/example-note.md"],
  "next": "положите дельты в changes/<id>/deltas/*.md"
}
```

**Особенности:** создаёт папку и запись; baseline фиксирует хеши и диагностики
на момент открытия.

**Где применяется:** широкая правка нескольких файлов (правило
[12-agent-operations.md](12-agent-operations.md)); сущности `change` и `blocked_by`.

### 11.3. `todoc change show`

**Путь CLI:** `todoc change show`

**Назначение:** запись изменения и её дельты.

**Синтаксис:**

```bash
todoc change show ID [--root PATH]…
```

**Атрибуты:** `ID` — positional, обязателен.

**Вывод:** `{dataset_id, record, deltas[]}`.

**Пример:**

```bash
todoc change show change:primer-izmeneniya --root demo
```

**Где применяется:** чтение намерения и дельт перед применением.

### 11.4. `todoc change validate`

**Путь CLI:** `todoc change validate`

**Назначение:** проверяет **применимость** дельт к живому состоянию, а не только
формат.

**Синтаксис:**

```bash
todoc change validate ID [--root PATH]…
```

**Атрибуты:** `ID` — positional, обязателен.

**Вывод:** `{dataset_id, change_id, applicable, errors, warnings}` + диагностики.

**Пример:**

```bash
todoc change validate change:primer-izmeneniya --root demo
```

**Особенности:** коды `change.delta_target_missing`, `change.delta_anchor_missing`,
`change.base_hash_mismatch`, `change.blocked_by_unresolved`,
`change.apply_order_ambiguous`, `change.post_apply_invalid`.

**Где применяется:** обязательный шаг **до** `change apply`; CI-гейт.

### 11.5. `todoc change verify`

**Путь CLI:** `todoc change verify`

**Назначение:** детерминированная проверка трёх измерений без модели:
completeness, correctness, coherence.

**Синтаксис:**

```bash
todoc change verify ID [--root PATH]…
```

**Атрибуты:** `ID` — positional, обязателен.

**Вывод:** `{dataset_id, change_id, found, status, findings[], clean}`.

**Пример:**

```bash
todoc change verify change:primer-izmeneniya --root demo
```

**Особенности:**

- completeness — все пункты `tasks.md` закрыты, артефакты изменены;
- correctness — текущее состояние соответствует дельтам (для `applied`/`in_progress`);
- coherence — `validate --all` не даёт новых диагностик относительно baseline.

**Где применяется:** проверка после применения, воспроизводимый CI-гейт.

### 11.6. `todoc change apply`

**Путь CLI:** `todoc change apply`

**Назначение:** применяет bundle-транзакцию «всё или ничего».

**Синтаксис:**

```bash
todoc change apply ID [--apply] [--if-hash PATH=sha256:…]… [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `ID` | positional | да | Изменение. |
| `--apply` | флаг | нет | Записать; без него — план. |
| `--if-hash` | `PATH=sha256:…`, повторяемый | нет | Отказ, если файл ушёл. |

**Вывод:** без `--apply` — `{applied: false, preview: true, files: []}`; с
`--apply` — `{applied: true, files: [...]}`.

**Пример:**

```bash
todoc change apply change:primer-izmeneniya --root demo
todoc change apply change:primer-izmeneniya --root demo --apply
```

**Особенности:** сначала считаются все новые содержимые и проверяются все дельты,
затем идёт запись; при сбое уже записанные файлы возвращаются к исходным байтам.

**Где применяется:** широкая правка; сущности `change`, `deltas`.

### 11.7. `todoc change archive`

**Путь CLI:** `todoc change archive`

**Назначение:** закрывает изменение: статус `archived`, папка уносится в
`changes/archive/`.

**Синтаксис:**

```bash
todoc change archive ID [--tag T] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Назначение |
|---|---|---|
| `ID` | positional | Изменение (обязателен). |
| `--tag T` | имя метки | Ставит метку истории на последнее событие. |

**Вывод:** запись со статусом `archived` и путём архива.

**Пример:**

```bash
todoc change archive change:primer-izmeneniya --root demo --tag v1.2
```

**Где применяется:** завершение изменения, релизная метка.

### 11.8. `todoc change revert`

**Путь CLI:** `todoc change revert`

**Назначение:** возвращает артефакты к базовой линии изменения.

**Синтаксис:**

```bash
todoc change revert ID [--apply] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Назначение |
|---|---|---|
| `ID` | positional | Изменение (обязателен). |
| `--apply` | флаг | Записать; без него — план. |

**Вывод:** план/`applied`.

**Пример:**

```bash
todoc change revert change:primer-izmeneniya --root demo --apply
```

**Особенности:** откат только для `applied`/`in_progress`; иначе
`change.id_invalid`. Восстановление идёт по baseline, а не по обратным дельтам.

**Где применяется:** отмена широкой правки.

### 11.9. `todoc context`

**Путь CLI:** `todoc context`

**Назначение:** весь контекст задачи одним вызовом в пределах бюджета байт:
запись → дельты → события → файлы → диффы.

**Синтаксис:**

```bash
todoc context --change ID | --tag NAME [--budget N] [--with-diff] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `--change ID` | `change:…` | — | Изменение. Взаимоисключим с `--tag`. |
| `--tag NAME` | метка | — | Контекст по метке. |
| `--budget N` | int (байты) | `8000` | Честный бюджет ответа. |
| `--with-diff` | флаг | `false` | Добавить диффы. |

**Вывод:** `{dataset_id, change_id, tag, budget, truncated, record, deltas[],
events[], files[], used_bytes}` + `diffs[]` при `--with-diff`.

**Пример:**

```bash
todoc context --root demo --change change:pilot-profil-dokumentirovaniya-softa \
  --budget 8000 --with-diff
```

**Особенности:** порядок заполнения фиксирован; когда кусок не влезает,
`truncated: true`, ответ не превышает бюджет. Дифф ограничен
`limits.max_diff_lines`.

**Где применяется:** агентский контекст задачи вместо серии чтений; сущности
`change`, `tag`, история.

---

## 12. Дрейф зависимостей: `stale`

### 12.1. `todoc stale`

**Путь CLI:** `todoc stale`

**Назначение:** находит документы, чьи зависимости `derived_from` изменились,
или подтверждает, что дрейф нерелевантен.

**Синтаксис:**

```bash
todoc stale [--path P] [--severity S] [--root PATH]…
todoc stale --ack P --reason R [--apply] [--expected-hash H] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `--path P` | путь | нет | Только этот владелец (документ/запись). |
| `--severity S` | `warning\|error` | нет | Фильтр диагностик. |
| `--ack P` | путь | да с `--ack` | Подтвердить дрейф этого владельца. |
| `--reason R` | строка | да с `--ack` | Почему дрейф нерелевантен. |
| `--apply` | флаг | нет | Записать подтверждение (по умолчанию preview). |
| `--expected-hash H` | `sha256:…` | нет | CAS-предусловие. |

**Вывод:** `{dataset_id, path, stale}`; диагностики
`staleness.dependency_changed` и `staleness.dependency_missing` (severity
`warning`).

**Пример:**

```bash
todoc stale --root demo
todoc stale --root demo --ack docs/state/15-benchmark.md \
  --reason "изменение не влияет на вывод" --apply
```

**Особенности:**

- Якорь зависимости — `путь[#фрагмент]@sha256:…`, где фрагмент — JSON Pointer
  (`/meta/date`) или `section:<заголовок>`; хеш считается от фрагмента.
- `--ack` без `--apply` показывает план; с `--apply` дописывает во front matter
  `stale_acknowledged_at`, `stale_ack_reason`, `stale_ack_hashes`.
- Подтверждение сбрасывается, когда любой из хешей меняется снова.

**Где применяется:** derived-витрины, интероп-экспорты, `derived_from`-документы;
ритуал BUG-011.

---

## 13. Скилы: `skills …`

### 13.1. `todoc skills tree`

**Путь CLI:** `todoc skills tree`

**Назначение:** оглавление хранилища скилов на лету, без индекса (live-scan).

**Синтаксис:**

```bash
todoc skills tree [--vault V] [--within P] [--query Q] [--all] \
  [--limit N] [--max-depth N] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `--vault V` | путь относительно `DATA_ROOT` | `skills` | Каталог vault. |
| `--within P` | префикс пути | — | Срез раздела (например, `coding/git`). |
| `--query Q` | строка | — | Lowercase-подстрока по name+description+пути; кириллица работает. |
| `--all` | флаг | `false` | Показать мьютнутые `!`-папки с пометкой `[!]`. |
| `--limit N` | int | `100` | Ограничение вывода. |
| `--max-depth N` | int | `6` | Глубина печатаемого дерева. |

**Вывод:** `{dataset_id, vault, counts{skills,sections,muted}, skills[],
section_meta{}, truncated}`; элемент скила — `{name, path, section, description,
muted, refs, scripts, assets}`.

**Пример:**

```bash
todoc skills tree --root demo --limit 8
```

**Особенности:** мьют — папка `!имя`, исключённая из дефолтного дерева и из
`docs search`; содержимое не меняется. Счётчик секции — только собственные
файлы (BUG-008 fixed).

**Где применяется:** первый шаг правила «перед нетривиальной задачей — `skills tree`».

### 13.2. `todoc skills read`

**Путь CLI:** `todoc skills read`

**Назначение:** читает `SKILL.md`; путь резолвится только внутри vault
(confinement).

**Синтаксис:**

```bash
todoc skills read --path P [--line-range A-B] [--budget B] [--vault V] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `--path P` | путь | да | Папка скила или путь к `SKILL.md`; можно с префиксом vault. |
| `--line-range A-B` | `A-B` | нет | Диапазон строк. |
| `--budget B` | int (байты) | нет | Максимум содержимого. |
| `--vault V` | путь | нет | Каталог vault. |

**Вывод:** `{path, name, description, muted, content, truncated}`.

**Пример:**

```bash
todoc skills read --root demo --path coding/git/commit-message --budget 300
```

**Особенности:** ошибки `skills.not_found`, `skills.path_escape`,
`skills.not_a_skill`. Чтение не меняет скил.

**Где применяется:** второй шаг правила скилов; скилы жизненного цикла.

### 13.3. `todoc skills attach`

**Путь CLI:** `todoc skills attach`

**Назначение:** ставит диспетчер-скил `todoc` в платформенный каталог скилов,
подставляя `DATA_ROOT` вместо `{ROOT}`. Витрина целиком не монтируется.

**Синтаксис:**

```bash
todoc skills attach --to DIR [--root PATH]… [--force] [--output json|table]
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `--to DIR` | путь | да | Каталог скилов платформы (`.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, …). |
| `--root PATH` | путь | нет | `DATA_ROOT`, вшиваемый в тело диспетчера. |
| `--force` | флаг | нет | Перезаписать существующий скил `todoc`. |

**Вывод:** `{installed, skill, files, root_embedded, mount_hint}`.

**Пример:**

```bash
todoc skills attach --root demo --to /tmp/platform_skills
```

**Особенности:** без `--force` существующий скил — `skills.attach_exists`.

**Где применяется:** подключение движка к агенту; правило скилов в AGENTS.md.

### 13.4. `todoc skills import`

**Путь CLI:** `todoc skills import`

**Назначение:** офлайн-импорт чужих скилов: папки со `SKILL.md`; обвязка пакетов
не переносится.

**Синтаксис:**

```bash
todoc skills import --src S --into SECTION [--skill NAME] [--vault V] \
  [--dry-run] [--adopt] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `--src S` | путь | да | Локальная папка-скил или репо-пакет (`**/SKILL.md`). |
| `--into SECTION` | путь | да | Раздел vault, куда класть (например, `coding/review`). |
| `--skill NAME` | имя | нет | Копировать один скил по имени папки. |
| `--vault V` | путь | нет | Каталог vault. |
| `--dry-run` | флаг | нет | Показать план без записи. |
| `--adopt` | флаг | нет | Источник уже в vault: валидировать и отчитаться без копии. |

**Вывод:** `{imported[], adopted[], skipped[], diagnostics[], dry_run, audit_note}`.

**Пример:**

```bash
todoc skills import --root demo --src demo/skills/coding/git/commit-message \
  --into coding/git --dry-run
```

**Особенности:** после импорта нужен `index rebuild`. Чужие скилы аудируются:
`scripts/` — код, `SKILL.md` — недоверенные данные.

**Где применяется:** подключение внешних скилов; правило скилов.

---

## 14. Агентский стейт: `state …`

Стейт живёт в `.todoc/state.json` — **вне данных**, это память рабочего
состояния между сессиями. Белый список v1: только `context.current_project`.

### 14.1. `todoc state get`

**Путь CLI:** `todoc state get`

**Назначение:** читает переменную стейта; `value: null` — не установлена.

**Синтаксис:**

```bash
todoc state get KEY [--root PATH]…
```

**Атрибуты:** `KEY` — positional, обязателен.

**Вывод:** `{ok, key, value}`.

**Пример:**

```bash
todoc state get context.current_project --root demo
```

**Где применяется:** workflow-скилы, восстановление текущего проекта.

### 14.2. `todoc state set`

**Путь CLI:** `todoc state set`

**Назначение:** записывает переменную стейта (белый список v1).

**Синтаксис:**

```bash
todoc state set KEY VALUE [--root PATH]…
```

**Атрибуты:** `KEY`, `VALUE` — positional, обязательны.

**Вывод:** `{ok, key, value, updated_at}`.

**Пример:**

```bash
todoc state set context.current_project demo-proj --root demo
```

**Особенности:** другой ключ — `state.key_not_allowed`, exit 3. Файл
перезаписывается атомарно, формат `{schema_version, vars}`.

**Где применяется:** скилы жизненного цикла; демо `.todoc/state.json`.

### 14.3. `todoc state list`

**Путь CLI:** `todoc state list`

**Назначение:** список переменных стейта с сортировкой по ключу.

**Синтаксис:**

```bash
todoc state list [--prefix P] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Назначение |
|---|---|---|
| `--prefix P` | строка | Фильтр по префиксу ключа (секции). |

**Вывод:** `{ok, vars}`.

**Пример:**

```bash
todoc state list --root demo
todoc state list --root demo --prefix context.
```

### 14.4. `todoc state unset`

**Путь CLI:** `todoc state unset`

**Назначение:** удаляет переменную; `removed: false` — не была установлена.

**Синтаксис:**

```bash
todoc state unset KEY [--root PATH]…
```

**Атрибуты:** `KEY` — positional, обязателен.

**Вывод:** `{ok, key, removed}`.

**Пример:**

```bash
todoc state unset context.current_project --root demo
```

---

## 15. Интероп-экспорты: `interop export`

### 15.1. `todoc interop export`

**Путь CLI:** `todoc interop export`

**Назначение:** превращает запись-источник в артефакт внешнего формата:
`flow` → ASL, `rule` → DMN 1.3, `term` → Rasa NLU YML. Экспорт — derived-артефакт.

**Синтаксис:**

```bash
todoc interop export --kind dmn|asl|rasa [--id RECORD_ID] \
  [--write exports/…md] [--root PATH]…
```

**Атрибуты:**

| Атрибут | Тип | Обязателен | Назначение |
|---|---|---|---|
| `--kind` | `dmn\|asl\|rasa` | да | Целевой формат. |
| `--id RECORD_ID` | `type:slug` | для dmn/asl | Источник; для `rasa` можно опустить — экспортируется весь глоссарий. |
| `--write PATH` | путь | нет | Записать markdown-документ в `exports/`; без него артефакт в stdout. |

**Вывод:** `{dataset_id, kind, record_id, id, artifact}`; с `--write` — запись
файла и метаданные.

**Пример:**

```bash
todoc interop export --root demo --kind dmn --id rule:account-blocked-v1
```

```json
{
  "dataset_id": "dataset-80c70868",
  "kind": "dmn",
  "record_id": "rule:account-blocked-v1",
  "id": "doc:export-dmn-account-blocked-v1",
  "artifact": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>…"
}
```

**Пример с записью:**

```bash
todoc interop export --root demo --kind asl --id flow:order-placement \
  --write exports/asl-order-placement.md
```

**Особенности:**

- `--write` только внутри `exports/` (`interop.write_outside_exports`);
  containment — `access.outside_data_root`.
- Перезапись поверх CAS разрешена только для derived-целей
  (`interop.target_not_derived`).
- Ошибки: `records.not_found`, `interop.wrong_entity_type`,
  `interop.flow_missing`, `interop.no_error_code`,
  `interop.no_terminal_for_code`, `interop.no_terms`,
  `interop.anchor_failed`, `usage.error` (без `--id` для asl/dmn).
- Front matter экспорта содержит `derived_from` с якорями на фрагменты записи;
  дрейф ловит `stale`.

**Где применяется:** витрины `demo/exports/`, обмен с DMN/ASL/Rasa; сущности
`flow`, `rule`, `term`.

---

## 16. Карта применения: скилы, правила, сущности

### 16.1. Команды и скилы

| Скил / зона | Команды |
|---|---|
| `SKILL.md` (`todoc`) — выбор корня и валидация | `init`, `check`, `validate --all`, `doctor`, `status` |
| `SKILL.md` — поиск и чтение | `docs search`, `docs read`, `docs tree` |
| `SKILL.md` — маршрутизация скилов | `skills tree`, `skills read`, `skills attach` |
| `SKILL.md` — записи и граф | `records list`, `records aggregate`, `relations graph` |
| `SKILL.md` — захват | `records create --preview` → `--apply` |
| `skills/process/todoc-capture` | `docs new --type idea`, `docs edit`, `docs status --set` |
| `skills/process/todoc-plan` | `docs new --type plan`, `records create --type task`, `records query` |
| `skills/process/todoc-execute` | `records status --set`, `docs edit`, `validate` |
| `skills/process/todoc-transitions` | `docs status --set`, `stale`, `docs edit` (re-anchor) |
| `skills/docs/todoc-docs` | `docs search`, `docs read` |
| `skills/coding/review/security-review` | `skills import`, аудит `scripts/` |

### 16.2. Команды и железные правила AGENTS.md

| Правило | Команды |
|---|---|
| 1. Работа только через CLI | все команды; прямое редактирование — только тело свежего скелета `docs new` (BUG-004) |
| 2. Перепроверяй каждый шаг | обратное чтение (`docs read`, `records read`, `explain-path`), `validate --all` |
| 3. Фиксируй баги сразу | `docs search --type bug-report`, `docs new --type bug-report`, `types prompt bug-report --op create` |
| 4. Review-first | `records create --preview` → `--apply`, `docs edit --preview` → `--apply`, `--if-hash` |
| 5. Счётчики — от факта | `types list`, `status`, `scan`, `validate` |
| 6. Гейты перед коммитом | `validate --root demo --all`, `docs links`, pytest/coverage |
| 7. Прогрессивная опора P15 | `guidance` в конверте, `types prompt` |

### 16.3. Команды и сущности

| Сущность / артефакт | Основные команды |
|---|---|
| `doc_type` (markdown) | `docs new`, `docs read`, `docs edit`, `docs status`, `types show`, `types prompt` |
| `dir_type` (папка) | `explain-path`, `docs tree`, `docs suggest` |
| `entity_type` (JSON-запись) | `records create`, `records read`, `records list`, `records query`, `records status`, `types show` |
| `relation_type` (ребро) | `relations graph`, `relations tree`, `records undo-relation` |
| `change` | `change *`, `context`, `log --change`, `records query` |
| `flow` | `docs flow render`, `docs flow walk`, `interop export --kind asl` |
| `rule` | `interop export --kind dmn` |
| `term` | `interop export --kind rasa`, `records read` |
| `metric` | `records aggregate`, `records query` |
| история / ревизии | `log`, `show`, `diff`, `blame`, `timeline`, `revert`, `tag`, `history *` |
| производные артефакты | `stale`, `index *`, `docs flow render --write`, `interop export --write` |
| агентский стейт | `state get/set/list/unset` |
| скилы | `skills tree/read/attach/import` |

### 16.4. Кто что читает и кто что пишет

| Операция | Чтение | Запись |
|---|---|---|
| Документ | `docs read`, `docs search`, `docs tree` | `docs new`, `docs edit`, `docs status`, `fix` |
| Запись | `records read`, `records list`, `records query` | `records create`, `records status`, `records undo-relation` |
| Изменение | `change show`, `change validate`, `change verify`, `context` | `change open`, `change apply`, `change archive`, `change revert` |
| История | `log`, `show`, `diff`, `blame`, `timeline` | `revert`, `tag`, `history gc/adopt/export` |
| Типы | `types list`, `types show`, `types prompt`, `types guide` | `.todoc/` вручную, осознанно |
| Скилы | `skills tree`, `skills read` | `skills attach`, `skills import` |
| Стейт | `state get`, `state list` | `state set`, `state unset` |
| Индекс | `index status`, `status` | `index rebuild` |

---

## 17. Типовые последовательности

### 17.1. Первый запуск нового датасета

```bash
todoc init --root KB --dataset-id my-kb
todoc check-config --root KB
todoc index rebuild --root KB
todoc status --root KB
todoc validate --root KB --all
```

### 17.2. Поиск и чтение

```bash
todoc docs search --root KB --query "refresh token" --limit 3
todoc docs read --root KB --id doc:design
todoc docs read --root KB --id doc:design --section "Decision"
todoc docs read --root KB --id doc:design --line-range 40-60
```

### 17.3. Создание и правка

```bash
todoc types prompt note --op create --root KB
todoc docs new --root KB --type note --title "Заметка" --path notes/note.md
todoc docs edit --root KB --id doc:notes/note.md --patch-file patch.json --preview
todoc docs edit --root KB --id doc:notes/note.md --patch-file patch.json --apply
todoc validate --root KB --all
```

### 17.4. Запись и граф

```bash
todoc records create --root KB --type task --input-file task.json --preview
todoc records create --root KB --type task --input-file task.json --apply
todoc records list --root KB --type task --limit 10
todoc relations graph --root KB --from task:example --depth 2
```

### 17.5. Широкая правка через изменение

```bash
todoc change open --root KB --title "Обновить суть" \
  --artifact notes/a.md --artifact notes/b.md
# положить дельты в changes/<change-id>/deltas/*.md
todoc change validate change:obnovit-sut --root KB
todoc change apply change:obnovit-sut --root KB
todoc change apply change:obnovit-sut --root KB --apply
todoc change verify change:obnovit-sut --root KB
todoc change archive change:obnovit-sut --root KB --tag v1.2
```

### 17.6. Контекст и откат

```bash
todoc context --root KB --change change:obnovit-sut --budget 8000 --with-diff
todoc log --root KB --path notes/a.md --limit 10
todoc diff <rev> --root KB --path notes/a.md
todoc revert <rev> --root KB --path notes/a.md --apply
```

### 17.7. Скилы

```bash
todoc skills tree --root KB
todoc skills read --root KB --path coding/review/code-review
todoc skills attach --root KB --to .claude/skills
todoc skills import --root KB --src /path/to/skill --into coding/review --dry-run
todoc index rebuild --root KB
```

### 17.8. Ремонт

```bash
todoc validate --root KB --all
todoc fix --root KB --diagnostic diag_0042 --preview
todoc fix --root KB --diagnostic diag_0042 --apply
todoc validate --root KB --all
```

---

## 18. Связанные документы

- [03-cli-reference.md](03-cli-reference.md) — компактный справочник сигнатур и форм ответа.
- [04-config-and-types.md](04-config-and-types.md) — `dataset.json`, правила, типы, резолвер.
- [05-formats.md](05-formats.md) — Markdown/JSON/CSV и контракт YAML-lite.
- [06-validation-and-diagnostics.md](06-validation-and-diagnostics.md) — каталог кодов и фиксов.
- [07-search-and-read.md](07-search-and-read.md) — поиск, скоринг, бюджетное чтение.
- [08-records-and-relations.md](08-records-and-relations.md) — записи, статусы, отношения, запросы.
- [09-storage-and-index.md](09-storage-and-index.md) — индекс, кэш, история.
- [10-testing-and-quality.md](10-testing-and-quality.md) — тесты и покрытие.
- [11-known-issues.md](11-known-issues.md) — подтверждённые дефекты.
- [12-agent-operations.md](12-agent-operations.md) — как агенту работать с CLI.
- [13-demo-dataset.md](13-demo-dataset.md) — состав демо-датасета.
- [14-glossary.md](14-glossary.md) — термины.
- [17-skills-and-vault.md](17-skills-and-vault.md) — скилы: vault, Agent Skills, жизненный цикл.
- [18-agent-state-and-context.md](18-agent-state-and-context.md) — `state.json`, `context`, би-темпоральность.
- [19-interop-exports.md](19-interop-exports.md) — DMN 1.3 / ASL / Rasa NLU.
- [SKILL.md](../../SKILL.md) — точка входа навыка `todoc`.
- [demo/notes/agent-contract.md](../../demo/notes/agent-contract.md) — контракт CLI для агента.
- [AGENTS.md](../../AGENTS.md) — железные правила сессии.

