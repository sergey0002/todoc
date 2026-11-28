---
id: doc:bugs/bug-057-open-bugs-list-not-discoverable.md
title: "BUG-057: обзор открытых баг-репортов не получается одной командой — docs list не подсказывается, records list отдаёт пустой успех"
doc_type: bug-report
lang: ru
bug_id: BUG-057
status: open
severity: minor
agent_impact: [friction, token_overrun]
tokens_extra_est: 6000
component: cli
found: 2026-11-28
created: 2026-11-28
updated: 2026-11-28
tags: [bugs, bug-report, cli, discoverability, docs-list, status, overview]
---

# BUG-057: обзор открытых баг-репортов не получается одной командой — docs list не подсказывается, records list отдаёт пустой успех

| Поле | Значение |
|---|---|
| Bug ID | BUG-057 |
| Компонент | cli (`docs search`, `docs list`, `records list`, справка) |
| Обнаружено | 2026-11-28 — вопрос пользователя «какие багфиксы не закрыты» |
| Окружение | todoc 0.1.0, Python 3.14.4, Windows 11 + WSL2 Ubuntu |

## Сводка

Команда обзора по типу и статусу существует (`docs list --type … --status …`,
появилась по BUG-022), но ни один очевидный путь к ней не ведёт. `records list
--type bug-report` отвечает `ok: true` с `total: 0` (BUG-020), `docs search
--type bug-report` отдаёт 78 строк без поля `status` (60 md + 18 JSON-зеркал),
усечённых до 50, а `docs search --help` упоминает только `--attr-NAME` и не
подсказывает `docs list`. В итоге вопрос «какие багфиксы не закрыты» решался
не одной командой, а серией вызовов и ручным `grep` по front matter.

## Шаги воспроизведения

1. `todoc records list --root demo --type bug-report --output json` — вернул
   `ok: true`, `total: 0`, `items: []`; ни диагностики, ни подсказки.
2. `todoc docs search --root demo --type bug-report --limit 50 --output json` —
   `total: 78`, `returned: 50`, `truncated: true`; в элементах только
   `id`, `path`, `title` — поля `status` нет, поэтому «что не закрыто» не видно.
3. `todoc docs --help` — команда `list` есть, но ни один предыдущий вывод на неё
   не сослался; `docs search --help` показывает лишь generic `--attr-NAME`,
   без `--status` и без примера обзора статусов.
4. `todoc docs list --root demo --type bug-report --status open --limit 1000` —
   `total: 47` (правильный ответ найден только после угадывания команды).
5. `todoc docs list --root demo --type bug-report --limit 1000 --fields path` —
   `total: 78`; из них 18 путей ведут в `records/documents/*.json`
   (`--status-missing` = ровно 18), то есть в выдачу попадают JSON-зеркала
   тех же репортов без `status`.
6. Попытки агрегировать статусы shell-циклом через обёртку
   `wsl -d Ubuntu -- bash -lc "…"` провалились на экранировании (см.
   «Доказательства»): `printf` напечатал `MISSINGtn` вместо строки, `sed` и
   `awk` получили искажённый скрипт. Пришлось отказаться от цикла и считать
   статусы вручную: `grep -H "^status:" demo/bugs/bug-*.md`.

## Ожидаемое поведение

Обзор типа/статуса — базовая операция агента и должна стоить один вызов
(это уже зафиксировано в приёмке BUG-022). Минимально достаточно любого из:

- `docs search` включает `status` и `doc_type` в элемент выдачи (метаданные уже
  в индексе, BUG-022 ссылался на `Document.status` в `src/todoc/service.py`),
  чтобы `--attr-status open` был виден прямо в ответе;
- пустой `records list` по `doc_type` возвращает диагностику с `suggested_fixes`
  и готовым argv `docs list --type … --status …` (BUG-020, BUG-021);
- `docs search --help` перечисляет доступные `--attr-*` (минимум `--status`)
  и даёт пример «список документов типа по статусу» (BUG-016);
- `docs list` не смешивает md-документы и JSON-зеркала в одной выдаче без
  пометки, а отсутствующий `status` отдаёт явно (`null`), а не скрывает запись.

## Фактическое поведение

- `records list` для `doc_type` — пустой успех без диагностики и без указания
  на `docs list`; выглядит как «репортов нет».
- `docs search` не отдаёт `status`; кроме того, `--type bug-report` считает
  и JSON-зеркала: 78 = 60 md + 18 `records/documents/*.json`, из-за чего
  число «репортов» в ответе не совпадает с числом файлов в `bugs/`.
- `docs list` без `--status` тоже возвращает 78, и 18 из них — зеркала без
  статуса; без `--status-missing` непонятно, почему часть строк «без статуса».
- Справка не подсказывает переход: `docs search --help` не упоминает
  `--status`/`docs list`, `next_actions` пустого `records list` пуст.
- Вложенные скрипты в обёртке Windows→WSL молча портятся (см. доказательства),
  поэтому даже ручная агрегация статусов требует отдельного раунда отладки.

## Доказательства

```
$ todoc records list --root demo --type bug-report --output json
"total": 0, "returned": 0, "truncated": false
# diagnostics: [], guidance.items: [] — ни намёка на docs list

$ todoc docs search --root demo --type bug-report --limit 50 --output json
"total": 78, "returned": 50, "truncated": true
# item keys: id, path, title  (status отсутствует)

$ todoc docs search --help
--type TEXT            Effective document type; separate alternatives by |.
--query TEXT
--budget INTEGER RANGE ...
# строки --status нет; упомянут только generic --attr-NAME в описании

$ todoc docs --help
Commands: edit, flow, links, list, new, read, search, status, suggest, tree

$ todoc docs list --root demo --type bug-report --limit 1000 --fields path
"total": 78
# 18 путей: records/documents/*.json (например bug-001-fm-doc-type-unknown.json)

$ todoc docs list --root demo --type bug-report --status-missing --limit 1000 --fields path
"total": 18   # ровно JSON-зеркала

$ todoc docs list --root demo --type bug-report --status open --limit 1000
"total": 47

$ grep -l '^status: open' demo/bugs/bug-*.md | wc -l
45            # glob bug-* не покрывает design-q01/q02 → 47 против 45
```

Провалы экранирования в обёртке (PowerShell → `wsl -d Ubuntu -- bash -lc`):

```
# цикл с awk/printf напечатал по одному "MISSINGtn" на файл, без имён и ошибки
MISSINGtnMISSINGtnMISSINGtn...

# sed с "$" внутри двойных кавычек PowerShell разобрал как переменную:
/bin/bash: line 1: s/"$// | sort > /tmp/cli_open.txt; grep -H ^status:: No such file or directory

# awk получил обрезанный скрипт:
awk: cmd. line:1: {print
awk: cmd. line:1:       ^ unexpected newline or end of string
```

Источник ожидания: приёмка BUG-022 (`docs list --type idea --status captured`
= 11 одним вызовом, `60b9f29`/`9c255fd`), контракт `docs search`/`docs list`
в `src/todoc/cli` и правило P15 (guidance на ошибку).

## Воздействие

Агент задаёт естественный вопрос «что не закрыто» и получает три разных числа:
78 (search/list без фильтра, с JSON-зеркалами), 47 (`docs list --status open`)
и 45 (grep по `bug-*.md`, без design-документов). Любое из них можно принять за
ответ, поэтому есть риск неверного числа и повторных перепроверок.

Цена эпизода: 10+ вызовов CLI (2 пробных списка, 3 справки, 3 неудачных
shell-агрегации, 2 контрольных запроса), плюс ручной grep и сравнение JSON
через временный Python-скрипт. Прямой путь без CLI — один `grep`/`awk` по
`demo/bugs/*.md`, то есть система оказалась дороже файлов. Оценка перерасхода
≈ 6000 токенов. Частота: каждый обзор бэклога репортов.

Severity `minor`: неверных данных не пишется, но обзор — базовая операция, и
без неё агент обходит CLI. Корневой дефект пустого успеха `records list` уже
зафиксирован как BUG-020 (`major`), здесь — его последствие для discoverability.

## Предложение по исправлению

- `docs search`: добавить `status` и `doc_type` в элемент выдачи (или включить
  в дефолтную проекцию при `--type`); метаданные уже индексируются.
- `records list` по `doc_type`: вернуть диагностику `records.unknown_entity_type`
  с `suggested_fixes: [docs list --type <type> --status <status>]` (BUG-020/021).
- `docs list`: поле `origin`/`source` (`document` | `record`) и режим обзора,
  который по умолчанию исключает JSON-зеркала либо явно их помечает; статус
  отсутствующего — `null`, а не выкидывание строки.
- Справка `docs search --help` и `docs list --help`: перечислить доступные
  `--attr-*`/`--status` и дать пример обзора по типу и статусу (BUG-016).
- Проверка: `docs list --type bug-report --status open` = 47 без зеркал;
  `--status-missing` = 18 с `origin: record`; `docs search --type bug-report
  --limit 5` содержит `status`; пустой `records list` даёт `suggested_fixes`.
- Для обёртки Windows→WSL: не требовать вложенных `bash -lc` скриптов, дать
  argv-безопасный способ (см. BUG-028).

## Заметки

Поиск перед созданием (2026-11-28): `--type bug-report --query "список открытых
баг-репортов одной командой"` и `--query "docs list discoverability help
status filter"` — точного дубликата нет. Найдены связанные: BUG-022 (обзор по
типу; `fixed`, команда `docs list` уже есть), BUG-020 (пустой успех
`records list` по `doc_type`, `open`), BUG-013 (ручной grep для резолва),
BUG-016 (фильтры не документированы), BUG-021 (usage-ошибки без guidance),
BUG-028 (runtime-контракт Windows/WSL), BUG-017 (молчаливое усечение дерева).

Числа на 2026-11-28: в `demo/bugs/` 60 md с `doc_type: bug-report`
(58 `bug-*` + design-q01/q02); `status`: 47 open, 12 fixed, 1 duplicate;
плюс 18 JSON-зеркал в `demo/records/documents/` без `status`.

### Применено 2026-11-28 (рабочее дерево, до коммита)

- `docs search` отдаёт `doc_type` и `status` в проекции (по умолчанию и в
  `--fields`), проверено на `--type bug-report`.
- `docs list` получил поле `origin` (`document` | `record`) и фильтр
  `--origin document`, который исключает JSON-зеркала; `--status-missing`
  по-прежнему показывает ровно зеркала.
- Неизвестные `--type`/`--status` в `docs list` теперь дают
  `docs.unknown_type`/`docs.unknown_status` с guidance (exit 2).
- `AGENTS.md` и скил `docs/todoc-docs` дополнены маршрутом `docs list`;
  диспетчер смонтирован в `.kilo/skills/todoc/SKILL.md`.
- Тесты: `tests/cli/test_unified_docs.py` (проекция статуса, origin,
  неизвестные тип/статус), полный `pytest` — зелёный.
- Остаётся: пустой успех `records list` по `doc_type` (BUG-020) и
  discoverability справки search. Статус `open` до ревью и коммита.
