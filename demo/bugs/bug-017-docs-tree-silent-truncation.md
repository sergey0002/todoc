---
id: doc:bugs/bug-017-docs-tree-silent-truncation.md
title: "BUG-017: docs tree молча усекает дерево до 50 папок и 50 документов без truncated"
doc_type: bug-report
lang: ru
created: 2026-11-27
updated: 2026-11-28
bug_id: BUG-017
status: fixed
severity: major
agent_impact: [friction, token_overrun]
tokens_extra_est: 9000
component: cli
found: 2026-11-27
---

# BUG-017: docs tree молча усекает дерево до 50 папок и 50 документов без truncated

| Поле | Значение |
|---|---|
| Bug ID | BUG-017 |
| Компонент | cli (`docs tree`) |
| Обнаружено | 2026-11-27 — обзор демо-датасета (вопрос «какие скилы доступны») |
| Окружение | todoc 0.1.0 (master 5e86eb7), Python 3.14.4 (WSL Ubuntu), харнесс — Windows PowerShell 5.1 поверх `\\wsl.localhost` |

## Сводка

`todoc docs tree` возвращает не больше 50 папок и 50 документов независимо от
`--max-depth` и без признака усечения в конверте: `total_folders`/`total_documents`
показывают 86 и 470 (на момент замера; число документов растёт с каждым новым
репортом), а в `folders`/`documents` лежит по 50 элементов, поля `truncated` нет. Флаг `--max-depth` принимается, попадает в ответ как эхо
(`"max_depth": 1`) и не влияет на выдачу.

## Шаги воспроизведения

1. `todoc docs tree --root demo --max-depth 1 --output json > /tmp/t1.json`
2. `grep -nE total_ /tmp/t1.json` → `total_folders: 86`, `total_documents: 470`, `max_depth: 1`
3. `grep -c folder_id /tmp/t1.json` → `150` (50 своих `folder_id` + 50 `parent_folder_id` папок + 50 `parent_folder_id` документов), `grep -c document_id` → `50`
4. `todoc docs tree --root demo --max-depth 0 --output json > /tmp/t0.json`
5. `todoc docs tree --root demo --max-depth 9 --output json > /tmp/t9.json`
6. `diff /tmp/t0.json /tmp/t9.json` → единственное различие — эхо-поле `max_depth`

## Ожидаемое поведение

- `--max-depth` ограничивает глубину выдачи: `--max-depth 1` — только папки
  верхнего уровня и их документы; `--max-depth 0` — только корень.
- Усечение выдачи объявляется машинно-читаемо (`truncated: true` +
  `returned`/`total`), как в `docs search` (`total`, `returned`, `truncated`,
  `cursor`), либо ограничивается явным `--limit` с тем же контрактом.
- `--output table` печатает таблицу, а не repr словарей (см. «Фактическое поведение», п. 3).

Источник ожидания: `--help` команды объявляет `--max-depth` как рабочий флаг
(`src/todoc/cli.py:1469`), а P7 «bounded output» в контракте CLI требует
объявлять усечение, а не резать молча.

## Фактическое поведение

1. `max_depth` вычисляется в сигнатуре, но не используется: в ответе он только
   эхо-поле (`src/todoc/cli.py:1493-1494`), а срез жёстко `[:50]` для обеих коллекций.
2. Усечение не объявлено: ключа `truncated` в конверте нет, `total_*` есть —
   агент видит 50 из 470 и не знает об этом.
3. `--output table` на этой команде печатает сырые repr: `folders: [{'folder_id': ...}]`
   одной строкой (~47 КБ), то есть table-режим здесь не читаем и не экономит токены.

## Доказательства

```
$ todoc docs tree --root demo --max-depth 1 --output json > /tmp/t1.json
$ grep -nE total_ /tmp/t1.json
1210:    "total_folders": 86,
1211:    "total_documents": 470,
1212:    "max_depth": 1
$ grep -c folder_id /tmp/t1.json      # 50 своих + 100 parent_folder_id
150
$ grep -c document_id /tmp/t1.json
50

$ diff /tmp/t0.json /tmp/t9.json      # --max-depth 0 против --max-depth 9
1212c1212
<     "max_depth": 0
---
>     "max_depth": 9
```

Код: `src/todoc/cli.py:1469` (`--max-depth` в опциях), `src/todoc/cli.py:1472`
(`max_depth` в сигнатуре), `src/todoc/cli.py:1493-1494`
(`"folders": folders[:50], "documents": documents[:50]`, `max_depth` только в payload).

## Воздействие

- Агент, которому нужна карта верхнего уровня (например, «где лежат скилы»),
  получает 50 папок + 50 документов без признака неполноты и делает вывод
  «больше нет» — ровно так в этой сессии была пропущена часть дерева.
- Цена эпизода: 1 вызов (~47 КБ JSON ≈ 12k токенов) + 2–3 вызова на выяснение
  факта усечения (`wc`, `grep`, `diff`) ≈ 1–2k токенов; прямой путь без CLI —
  один `ls`/`find -maxdepth 1` (~200 токенов). Перерасход ≈ 9k токенов.
- Обход: агент начинает вызывать `--within` по каждой папке по очереди —
  серия вызовов вместо одного дерева.

## Предложение по исправлению

1. Реализовать `--max-depth` фильтром по глубине пути (как в `skills tree`,
   `src/todoc/cli.py:360`) до среза.
2. Добавить `--limit` (default 50) и поля `returned`/`total`/`truncated` в конверт;
   `total_*` оставить.
3. Для `--output table` — табличный рендер (или явный отказ с диагностикой
   `output.unsupported`, а не repr).
4. Тест: `--max-depth 0` даёт только корень; `truncated: true` при `total > limit`.

## Заметки

- Тот же класс дефекта, что BUG-005 (`docs read --section` принимает `--budget`
  и игнорирует) и BUG-008 (`skills tree` — счётчики/глубина раздела).
- Поиск перед созданием (2026-11-27): `--type bug-report --query max-depth` —
  найден только BUG-008 (другой компонент, `skills tree`); `--query truncated` — совпадений нет.

- 2026-11-28: `fixed` — коммит `7d32813`. `docs tree` сообщает `truncated` и `next_cursor`; проверка: `--limit 5` → `total=474 returned=5 truncated=True`. Тест: `tests/cli/test_unified_docs.py::test_tree_cursor_traverses_every_row_and_rejects_scope_changes`.
