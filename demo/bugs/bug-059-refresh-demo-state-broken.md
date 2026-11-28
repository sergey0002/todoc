---
id: doc:bugs/bug-059-refresh-demo-state-broken.md
title: "BUG-059: tools/refresh_demo_state.py не запускается и расходится с demo-копиями"
doc_type: bug-report
lang: ru
bug_id: BUG-059
status: open
severity: minor
agent_impact: [friction, token_overrun]
tokens_extra_est: 4000
component: docs
found: 2026-11-28
created: 2026-11-28
updated: 2026-11-28
tags: [bugs, bug-report, docs, demo, tooling, refresh-demo-state]
---

# BUG-059: tools/refresh_demo_state.py не запускается и расходится с demo-копиями

| Поле | Значение |
|---|---|
| Bug ID | BUG-059 |
| Компонент | docs (`tools/refresh_demo_state.py`, `demo/references/state/`) |
| Обнаружено | 2026-11-28 — применение правок BUG-058 к `docs/state/*` |
| Окружение | todoc 0.1.0, Python 3.14.4, WSL2 Ubuntu |

## Сводка

`tools/refresh_demo_state.py` — единственный способ обновить производные
`demo/references/state/*` из `docs/state/*` — не запускается: он требует demo-копию
для каждого `docs/state/*.md`, но у сгенерированного `docs/state/cli.md` её нет,
и скрипт выходит с кодом 1 до записи. Обход через частичный запуск показал ещё
три дефекта: теряются `created`/`updated` (валидатор даёт
`document.schema_violation`), после front matter пропадает пустая строка
(перезаписываются все 20 файлов), а ссылки на repo-only цели (`../../ideas`,
`../../src/...`) становятся битыми в demo (10 × `markdown.link.target_missing`).

## Шаги воспроизведения

1. `python3 tools/refresh_demo_state.py` → `no demo copy for: ['cli.md']`,
   exit 1, ни один файл не обновлён.
2. Обойти проверку и обновить один файл тем же кодом → front matter теряет
   `created`/`updated` → `todoc validate --root demo --all` даёт
   `document.schema_violation` на `references/state/07-search-and-read.md`.
3. `python3 tools/refresh_demo_state.py` после обхода → пишет `---\n#` без
   пустой строки, поэтому «refreshed 20 of 21» при отсутствии смысловых правок.
4. После обновления `demo/references/state/13-demo-dataset.md` →
   `markdown.link.target_missing` для `[Идеи](../../ideas)`, `[планы](../../plan)`
   и ещё 6 каталогов, `[ru.json](../../src/todoc/data/guidance/ru.json)`.

## Ожидаемое поведение

- Скрипт пропускает `docs/state/cli.md` (или явно перечисляет файлы без
  demo-копии) и завершается успешно, если остальные копии актуальны.
- `created`/`updated` сохраняются из существующей demo-копии.
- Формат вывода идемпотентен: повторный запуск без изменений источника не
  меняет файлы.
- Ссылки, у которых нет цели внутри demo, де-линкуются или остаются GitHub-URL,
  а не превращаются в битые относительные пути.

## Фактическое поведение

- Жёсткий выход на `cli.md`; инструмент нельзя использовать по назначению.
- Front matter пересобирается из пяти полей, даты теряются.
- Нет пустой строки после `---`, поэтому диффы «на весь каталог».
- `REMAP`/`DELINK` не покрывают repo-root каталоги и `src/`, из-за чего demo
  перестаёт проходить `validate`.

## Доказательства

```
$ python3 tools/refresh_demo_state.py
no demo copy for: ['cli.md']
$ echo $?
1

# обход: тот же код для одного файла
$ todoc validate --root demo --all
document.schema_violation: 'created' is a required property
document.schema_violation: 'updated' is a required property

# после обхода и записи
refreshed 20 of 21: ['01-overview.md', ..., 'README.md']

$ todoc validate --root demo --all
diagnostic_count: 10
markdown.link.target_missing: "[Идеи](../../ideas)"
markdown.link.target_missing: "[ru.json](../../src/todoc/data/guidance/ru.json)"
```

## Воздействие

Обновление demo-копий после правки `docs/state/*` требует ручного скрипта,
чистки 10 файлов и повторной валидации; в этом эпизоде ~15 вызовов и ≈4000
токенов вместо одного запуска инструмента. Риск: несогласованные копии
`docs/state` и `demo/references/state` (источник и витрина расходятся).

## Предложение по исправлению

- `NO_DEMO_COPY = {"cli.md"}` — пропускать в проверке и цикле.
- Сохранять `created`/`updated` из существующей demo-копии.
- `rendered = f"{front}\n\n{new_body}"`.
- Де-линковать repo-only цели (`../../ideas`, `../../plan`, `../../src/...`,
  `cli.md`) или оставлять абсолютный GitHub-URL.
- Тест: временный каталог с `docs/state/cli.md` + одной копией; повторный
  запуск не меняет байты; `validate` на demo — 0 диагностик.

## Заметки

Поиск перед созданием (2026-11-28): `--type bug-report --query "refresh demo
state tool"` — совпадений нет. Связанные: BUG-058 (правки docs/state и
demo-копий), BUG-007 (`docs links` вместо linkcheck), BUG-024 (шум скилов в
индексе). Инструмент возвращён к HEAD; правки demo-копий 03/07 сделаны вручную
и проверены `validate` (0 диагностик).
