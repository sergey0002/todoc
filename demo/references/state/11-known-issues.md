---
id: doc:state-known-issues
title: Состояние: известные проблемы
doc_type: reference
lang: ru
source: .doc/state/11-known-issues.md
copied: true
---
# 11. Известные проблемы

Каждый пункт проверен запуском команды 2026-11-24; приведено воспроизведение. Полный исторический
список находок — в [аудите реализации](../../plan/audit-implementation.md).

## Критичные (P0)

### P0-1. Идентификаторы диагностик нестабильны между процессами

`id` считается через `hash()`, который рандомизирован в каждом процессе Python.

```bash
todoc validate --root KB --all   # → diag_81899
todoc validate --root KB --all   # → diag_47107   (та же диагностика)
```

Последствие: цепочка `validate` → `fix --diagnostic` работает только внутри одного вывода;
внешний агент, сохранивший ID, получит `fix.diagnostic_not_found` (exit 3).
Решение: детерминированный ID (например, SHA-256 от `path + code + location + evidence`).

### P0-2. Выход за пределы DATA_ROOT

```bash
todoc types guide --root KB --out /tmp/escaped-guide.md   # exit 0, файл создан вне корня
todoc docs new --root KB --title X --dir ../../outside    # путь не ограничен корнем
```

Проверено: `/tmp/escaped-guide.md` создан (3928 байт, exit 0). `docs new` с выходом за корень
падает неорганизованно (`PermissionError`), то есть проверка containment отсутствует, а не срабатывает.
Решение: проверять `is_within_root` для всех целей записи и возвращать exit 2/4.

### P0-3. `--cursor` не продолжает выдачу

```bash
todoc docs search --root KB --query "портабельность" --limit 2   # returned 2, cursor "3"
todoc docs search --root KB --query "портабельность" --limit 2 --cursor 2   # returned 0, total 42
```

Курсор возвращается, но не применяется к выборке. Решение: смещение `cursor` до среза `[:limit]`.

### P0-4. `record_id` с двоеточием даёт непереносимое имя файла

```bash
# record_id: "note:with:colons" → target: records/note/note:with:colons.json
```

Двоеточие недопустимо в именах файлов Windows. Решение: санитизация `{slug}` в `path_template`.

### Исправлено в этой итерации

- **Ссылки из регулярных выражений** → токены парсера: ссылки в code fence и инлайновом коде больше
  не дают ложных `markdown.link.target_missing`, reference-style и autolink находятся.
- **`RecursionError` на глубоко вложенном JSON**: итеративный подсчёт глубины в `parse_json` и
  замена сырого `json.loads` на `parse_json` в `service.py`. Проверено: файл из 5000 вложенных
  массивов даёт `json.too_deep`, exit 3, валидный конверт (ранее — traceback и пустой stdout).

## Важные (P1)

### P1-1. Необрабатываемые исключения вместо конверта

```bash
todoc docs search --root KB --query x --cursor abc      # ValueError, exit 1, stdout пуст
todoc docs read --root KB --id doc:home --line-range abc   # то же
```

В JSON-режиме stdout обязан содержать конверт даже при ошибке.

### P1-2. Ошибки в JSON-режиме уходят в stderr текстом

При исключении stdout пуст, сообщение — в stderr. Агент, читающий только stdout, получает пустоту.

### P1-3. `check` возвращает `ok: true` при ошибках

```bash
todoc check --root KB   # exit 3, но {"ok": true, ... "errors": 1, "status": "issues_found"}
```

`ok` должен отражать наличие ошибок.

### P1-4. Индекс пересобирается на каждую команду чтения

`docs read/search`, `records *`, `relations graph`, `fix`, `docs edit` вызывают `rebuild_index()`.
На демо (234 документа, 144 записи) серия команд занимает секунды.

### P1-5. Поколения индекса не удаляются

В демо накопилось 23 поколения и 5,5 МБ в `.todoc/index/`. Сборки мусора нет.

### P1-6. Кэш парсинга только пишется

248 файлов в `.todoc/cache/parse/` демо; на скорость парсинга не влияет.

### P1-7. Мёртвые флаги

| Флаг | Поведение |
|---|---|
| `doctor --scope` | игнорируется: `--scope nonsense` всё равно выполняет все 3 проверки |
| `records create --if-hash-new` | принимается, не используется |
| `docs new --template` | возвращается в ответе, но содержимое всегда `# <заголовок>` |

### P1-8. `docs read`: `--rows` применяется до `--where`

`--rows 3 --where doc_type=guide` вернул 0 строк, `--rows 75 --where doc_type=guide` — 3.

### P1-9. `status` показывает нули до первой пересборки

`status` читает опубликованное поколение; сразу после `init` — `generation_id: null`, `documents: 0`.

### P1-10. Нет CI, контрактных тестов и лицензии

Проверено: нет `.github/workflows`, нет `LICENSE`. Тесты запускаются только локально.

## Незначительные (P2)

- Пустые порты-заглушки (`ports/`, `adapters/indexes/`, `adapters/cache/`, `adapters/search/`) —
  контракт портов не описан кодом.
- `RESERVED_ALIASES` объявлен, но в резолве не участвует.
- Фрагмент поиска строится по первому совпадению, а не по наиболее релевантному.
- `heading_path` в результатах поиска ограничен первыми тремя заголовками документа, а не путём к совпадению.
- `dataset_id` генерируется случайно при `init`, что мешает воспроизводимым демо-датасетам.

## Приоритет исправлений

1. P0-1 (детерминированные ID) — без него `fix` непригоден для агента.
2. P0-2 (containment) — безопасность записи.
3. P1-1/P1-2 (конверт при ошибке) — агентский контракт.
4. P0-3 (cursor) и P1-8 (порядок `--rows`/`--where`) — предсказуемость выборки.
5. P1-4/P1-5/P1-6 — производительность и место на диске.

## Связанные разделы

- [03-cli-reference.md](03-cli-reference.md) — ожидаемое поведение команд.
- [12-agent-operations.md](12-agent-operations.md) — как обходить проблемы сейчас.
