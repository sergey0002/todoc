---
id: doc:bugs/bug-034-change-apply-target-outside-root.md
title: "BUG-034: change apply пишет за пределы DATA_ROOT по target дельты"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
bug_id: BUG-034
status: fixed
severity: critical
agent_impact: none
component: engine
found: 2026-11-28
tags: [bugs, bug-report, engine, changes, security, containment]
---

# BUG-034: change apply пишет за пределы DATA_ROOT по target дельты

| Поле | Значение |
|---|---|
| Bug ID | BUG-034 |
| Компонент | engine (`change validate` / `change apply`, `application/changes.py`) |
| Обнаружено | 2026-11-28 — аудит containment путей записи |
| Окружение | todoc 0.1.0 (5e86eb7 + рабочее дерево), Python 3.14.3, Windows 11 + WSL2 Ubuntu |

## Сводка

`change apply --apply` пишет в файл, заданный полем `target` front matter дельты,
без проверки, что путь остаётся внутри `DATA_ROOT`. Дельта с `target: ../outside.md`
проходит `change validate` как применимая (`applicable: true`) и командой
`change apply --apply` изменяет файл за пределами датасета.

## Шаги воспроизведения

Все шаги — в отдельном временном датасете, чтобы не трогать `demo/`:

1. `todoc init --root "$KB" --dataset-id audit-ds`
2. Создать файл вне корня: `$KB/../outside.md` с произвольным текстом.
3. `todoc change open --root "$KB" --title "Traversal"` → `change:traversal`.
4. Положить `changes/traversal/deltas/d.md`:

   ```markdown
   ---
   target: ../outside.md
   order: 1
   ---

   ## ADDED: ## Внешний раздел

   Текст, добавленный дельтой, чья цель лежит вне DATA_ROOT.
   ```

5. `todoc change validate --root "$KB" traversal --output json` → `applicable: true`, `errors: 0`.
6. `todoc change apply --root "$KB" traversal --apply --output json` → `applied: true`, `path: "../outside.md"`.
7. Прочитать `$KB/../outside.md` — в конец файла добавлен раздел «Внешний раздел».

Windows-путь, на котором воспроизведено: `C:\Users\NewUser\AppData\Local\Temp\kilo\todoc-audit`;
внешний файл — `C:\Users\NewUser\AppData\Local\Temp\kilo\outside.md`.

## Ожидаемое поведение

Любая запись CLI обязана оставаться внутри `DATA_ROOT` — это уже заявлено для
`--out` (`src/todoc/cli.py:107-120`), `docs flow render --write`
(`src/todoc/cli.py:1545-1548`), `interop export --write` (`src/todoc/cli.py:1979-1983`)
и `skills read` (path-confinement). `target` дельты — такой же путь записи:
`..`-сегменты и абсолютные пути должны отклоняться до записи с диагностикой
(`change.delta_target_outside_root` / `access.outside_data_root`), а
`change validate` должен показывать `applicable: false`.

## Фактическое поведение

- `validate_change` проверяет только существование `root / target` и читает файл:
  `src/todoc/application/changes.py:368-378`. Нормализации и containment-проверки нет.
- `plan_apply` и `apply_change` используют тот же `target` и пишут по нему:
  `src/todoc/application/changes.py:525-536`, `571-579`.
- В результате `target: ../outside.md` пишет в файл-сосед корня; `target: /tmp/x.md`
  или `../../x.md` дадут тот же эффект.
- Проверка `change validate` возвращает `applicable: true`, то есть система считает
  такой план допустимым.

## Доказательства

```
$ todoc change validate --root "$KB" traversal --output json
    "applicable": true,
    "errors": 0,

$ todoc change apply --root "$KB" traversal --apply --output json
  "ok": true,
    "applied": true,
    "status": "applied",
        "path": "../outside.md",
        "new_hash": "sha256:ad4b71dac6151ab7197ac5a5d19c396ff04e6dc563ff25b5594ca20e5c74b895"

$ cat "$KB/../outside.md"
# Outside

Этот файл лежит ВНЕ DATA_ROOT и не должен меняться командами todoc.

## Внешний раздел

Текст, добавленный дельтой, чья цель лежит вне DATA_ROOT.
```

Код:

- `src/todoc/application/changes.py:368` — `target_path = root / target` без containment.
- `src/todoc/application/changes.py:525-530` — `path = root / target` и `read_text`.
- `src/todoc/application/changes.py:571-574` — `atomic_write(path, item["content"])`.

## Воздействие

- `critical`: произвольная запись файлов от имени пользователя, запустившего CLI.
  Change-бандл — это данные (дельты могут прийти из импортированного пакета или
  быть сгенерированы агентом), а `change apply` позиционируется как
  review-first транзакция; containment-обход ломает эту гарантию.
- Обход не требует прав администратора и не оставляет диагностики: `validate`
  заранее говорит «применимо».
- Агентский сценарий: агент готовит изменение по чужому шаблону/пакету, запускает
  `validate` → `apply` и невольно перезаписывает файл вне датасета.

## Предложение по исправлению

1. В `validate_change`/`plan_apply` резолвить `target` и проверять
   `is_within_root(root, root / target)`; отклонять `..`, абсолютные пути и
   симлинк-выходы диагностикой `change.delta_target_outside_root` (severity error).
2. В `apply_change` повторно проверять containment непосредственно перед
   `atomic_write` (TOCTOU: файл мог стать симлинком после валидации).
3. Тест: дельта с `target: ../outside.md` → `applicable: false`, `apply` не меняет
   внешний файл; `target: notes/x.md` внутри корня работает как раньше.

## Заметки

Поиск перед созданием (2026-11-28): `docs search --type bug-report --query
"containment path traversal DATA_ROOT"` и `--query "change apply target"` —
совпадений по корневой причине нет (BUG-031/032 — Windows-пути, BUG-021 — guidance).
Связанные: BUG-035 (history читает вне корня), BUG-036 (skills import пишет вне корня).

- 2026-11-28: `fixed` — коммит `06d2a7b`. `validate_change` резолвит цель дельты через `contained_delta_target`: пустой/абсолютный путь, `..` и симлинк наружу дают `change.delta_target_outside_root` (exit 3) до чтения, хеширования и записи. Проверка: `tools/bug_acceptance.py --only BUG-034-change` → `fixed`; файл вне корня не читается и не меняется. Тесты: `tests/unit/test_changes.py::test_validate_rejects_target_outside_root`, `tests/cli/test_cli_changes.py::test_apply_refuses_delta_target_outside_root`.
