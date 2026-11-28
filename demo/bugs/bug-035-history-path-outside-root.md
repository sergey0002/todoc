---
id: doc:bugs/bug-035-history-path-outside-root.md
title: "BUG-035: history show/diff/blame читают файлы вне DATA_ROOT по --path"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
bug_id: BUG-035
status: fixed
severity: major
agent_impact: none
component: cli
found: 2026-11-28
tags: [bugs, bug-report, cli, history, security, containment]
---

# BUG-035: history show/diff/blame читают файлы вне DATA_ROOT по --path

| Поле | Значение |
|---|---|
| Bug ID | BUG-035 |
| Компонент | cli (`show`, `diff`, `blame`; `application/history.py`) |
| Обнаружено | 2026-11-28 — аудит containment путей чтения |
| Окружение | todoc 0.1.0 (5e86eb7 + рабочее дерево), Python 3.14.3, Windows 11 + WSL2 Ubuntu |

## Сводка

Команды истории принимают `--path` без проверки containment: `todoc show
--root demo --path ../README.md` возвращает содержимое файла, лежащего вне
`DATA_ROOT`, а `diff`/`blame --section` читают его тем же путём. Это нарушает
заявленный path-confinement датасета и позволяет агенту/скрипту читать
произвольные файлы через `todoc`.

## Шаги воспроизведения

1. `todoc show --root demo --path ../README.md --output json`
2. `todoc diff --root demo --path ../README.md --output json`
3. (для полноты) `todoc blame --root demo --path ../README.md --section "Установка" --output json`

## Ожидаемое поведение

Путь чтения истории — такой же путь датасета, как у `docs read`: он обязан
резолвиться внутри `DATA_ROOT`. Внешний путь должен давать
`access.outside_data_root` / `history.path_outside_root` (exit 4/3), а не
содержимое. Это тот же принцип, что в `_contained_out`
(`src/todoc/cli.py:107-120`) и `is_within_root` (`src/todoc/adapters/filesystem/scanner.py:28-34`).

## Фактическое поведение

- `show_cmd` передаёт `--path` как есть в `history_show` → `content_at`:
  `src/todoc/cli.py:703-713`, `src/todoc/application/history.py:195-201`.
- `content_at` для текущего состояния делает `target = root / rel_path` и
  читает файл (`history.py:195-200`) — `..` не нормализуется и не проверяется.
- `diff_cmd` использует тот же `history_show` для обеих ревизий
  (`src/todoc/cli.py:728-735`).
- `blame --section` вызывает `_section_bounds`, который читает `root / rel_path`
  (`src/todoc/application/history.py:321-328`).
- `revert` пишет по тому же пути через `_write_whole` (`src/todoc/cli.py:814`),
  но для записи нужна ревизия с таким путём в журнале; чтение достижимо всегда.

## Доказательства

```
$ todoc show --root demo --path ../README.md --output json
{
  "schema_version": 1,
  "ok": true,
  "data": {
    "dataset_id": "dataset-80c70868",
    "path": "../README.md",
    "rev": null,
    "content": "# todoc\n\nПереносимый типизированный слой знаний ..."

$ todoc diff --root demo --path ../README.md --output json
  "ok": true,
    "path": "../README.md",
    "changed": false,
    "lines": 0,
```

Файл `demo/../README.md` — README репозитория, вне `demo/`.

Код: `src/todoc/application/history.py:195` (`target = root / rel_path`),
`src/todoc/cli.py:708` (`history_show(ctx.root, resolved, path, ...)`),
`src/todoc/cli.py:730-731` (diff).

## Воздействие

- `major`: произвольное чтение файлов, доступных процессу, через команду,
  которая позиционируется как чтение истории датасета. Утечка секретов
  (`.env`, ключи, чужие проекты) в вывод агента/лог.
- Не требует прав и не оставляет следов; `validate` не участвует.
- Для агента это ещё и ложная модель мира: `show` выглядит как операция над
  датасетом, поэтому выход за корень не замечается.

## Предложение по исправлению

1. В `content_at`, `before_content`, `blame`, `diff`, `revert_plan` и
   `_section_bounds` резолвить путь и проверять `is_within_root(root, target)`;
   внешний путь — `AccessError("access.outside_data_root")`.
2. Отдельно проверить `--path` в CLI до вызова истории, чтобы ошибка была
   usage/access, а не «файл не найден».
3. Тест: `show --path ../README.md` → exit 4, содержимое не печатается;
   `show --path notes/ok.md` работает как раньше.

## Заметки

Поиск перед созданием (2026-11-28): `docs search --type bug-report --query
"history show path outside"` — совпадений по containment нет (BUG-012 — git status,
BUG-031/032 — Windows-пути). Связанные: BUG-034 (запись вне корня через
`change apply`), BUG-036 (skills import).

- 2026-11-28: `fixed` — коммит `06d2a7b`/`22db1df` (решение по преемникам). Вложенных `history show/diff/blame` больше нет: старый вызов даёт `usage.error` (exit 2). Заменяющие их верхнеуровневые `show/diff/blame` отклоняют путь вне DATA_ROOT (`docs.invalid_scope`/`access.outside_data_root`) до чтения, а `history export` проверяет границу отдельно. Проверка: `tools/bug_acceptance.py --only BUG-035-history` → `fixed`. Регрессия: `tests/cli/test_cli_history.py::test_history_successors_refuse_paths_outside_root`.
