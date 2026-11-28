---
id: doc:bugs/bug-056-no-tag-listing-or-record-filter.md
title: "BUG-056: Нет CLI-команды для списка тегов и фильтра записей по тегу"
doc_type: bug-report
lang: ru
bug_id: BUG-056
status: open
severity: major
agent_impact: friction
tokens_extra_est: 4000
created: 2026-11-28
updated: 2026-11-28
---

# BUG-056: Нет CLI-команды для списка тегов и фильтра записей по тегу

| Поле | Значение |
|---|---|
| Bug ID | BUG-056 |
| Компонент | cli |
| Обнаружено | 2026-11-28 — сессия по идее `archive` (вопрос «какие теги есть в системе») |
| Окружение | todoc 0.1.0, Python 3.14, WSL Ubuntu (Windows 11) |

## Сводка

В CLI нет команды, которая перечисляет теги датасета, и нет способа отфильтровать записи по тегу. Единственный теговый фильтр — `docs search --tag`, но он работает только для markdown front matter, требует обязательный `--query` и не умеет «только по тегу». Чтобы получить список тегов, пришлось читать файлы напрямую скриптом.

## Шаги воспроизведения

1. `PYTHONPATH=src python3 -m todoc --help` → среди команд нет `tags` (есть `tag`, но это метка ревизии истории).
2. `PYTHONPATH=src python3 -m todoc docs search --root demo --query "zzzznotfound" --tag security` → `total: 0`: без текстового совпадения тег не работает.
3. `PYTHONPATH=src python3 -m todoc docs search --root demo --query "qmd" --tag authored` → `total: 0`: теги JSON-записей (`records/documents/qmd.json` → `"tags": ["authored", ...]`) не участвуют в `--tag`.
4. `PYTHONPATH=src python3 -m todoc records list --root demo --type document --limit 3` → фильтра `--tag` нет.
5. QuerySpec с `"filters": {"tags": {"$in": [["ru"]]}}` → `total: 0`; фильтр сравнивает массив целиком, а не вхождение элемента.

## Ожидаемое поведение

1. `todoc tags list --root demo` (или `todoc types tags`) возвращает все теги с числом документов/записей и источником.
2. Единый фильтр `--tag` (или `--tag-in "a|b"`) работает в `docs search`, `records list` и `docs tree`; для `docs search` он не требует текстового совпадения, если задан только тег.
3. Теги JSON-записей и markdown front matter имеют одинаковую семантику; регистр не важен.

## Фактическое поведение

1. `--tag` есть только у `docs search` (`src/todoc/cli.py:1264`) и является точным пост-фильтром после лексического совпадения (`src/todoc/application/search.py:158`–`:160`).
2. Для JSON `_document_text` возвращает пустой front matter (`src/todoc/application/search.py:26`–`:30`), поэтому `--tag` отсекает все JSON-записи.
3. `records list` объявляет только `--type`, `--since`, `--until`, `--relation`, `--limit` (`src/todoc/cli.py`, команда `records list`).
4. `records query` (`src/todoc/application/query.py:15`–`:27`) не умеет проверять вхождение в массив: `$in` сравнивает значение целиком.
5. Команда `todoc tag` (`src/todoc/cli.py:822`) — это метка на ревизии истории, а не тег документа; `todoc context --tag` — тоже релизная метка.

## Доказательства

```
$ todoc docs search --root demo --query "qmd" --tag authored
{"ok": true, "data": {"total": 0, "returned": 0, "items": []}, "diagnostics": []}

$ todoc docs search --root demo --query "zzzznotfound" --tag security
{"ok": true, "data": {"total": 0, "returned": 0, "items": []}, "diagnostics": []}

$ todoc records query --root demo --query-file /tmp/q-tag.json
{"ok": true, "data": {"total": 0, "items": []}, "diagnostics": []}
```

Реальный объём тегов (получен обходом файлов, CLI-способа нет): 225 markdown-документов с тегами, 403 уникальных md-тега; 113 JSON-записей с тегами, 56 уникальных; объединение — 417 тегов.

## Воздействие

Агент не может ответить «какие теги есть» и «найди всё по тегу» одним вызовом CLI. Обход — читать front matter всех файлов скриптом (в этой сессии: отдельный Python-скрипт + ручной разбор), это дороже и обходит валидатор. `--tag` без `--query` не работает, поэтому «покажи всё с тегом archive» невозможно; JSON-теги вообще недоступны фильтру.

## Предложение по исправлению

1. Добавить `todoc tags list` (counts, источники, сортировка) и `--tag`/`--tag-in` в `docs search`, `records list`, `docs tree`; для поиска разрешить тег как самостоятельный фильтр без `--query`.
2. В `search_documents` брать теги из JSON-записей так же, как из markdown front matter (или из индекса), а не только из `front_matter`.
3. В `records query` поддержать `$contains`/`$has` для массивов (или `tags` как специальное поле).
4. Тесты: список тегов, тег без query, тег JSON-записи, `--tag-in`, неизвестный тег — диагностика, не тихий ноль.

## Заметки

- Идея полной системы: [Сквозная система тегов](../ideas/unified-tags-and-tag-graph.md) — `todoc tags`, `has_tag`, `--tag-in`.
- Связано с BUG-055 (неизвестные фильтры поиска дают тихий ноль).
- Закрытие: смена `status` во front matter с датой и коммитом.
