---
id: doc:bugs/bug-066-derived-from-outside-root.md
title: "BUG-066: derived_from читает файлы вне DATA_ROOT без проверки границы"
doc_type: bug-report
lang: ru
status: fixed
severity: critical
component: engine
agent_impact: friction
created: 2026-11-28
updated: 2026-11-28
tags: [bugs, bug-report, staleness, derived-from, containment]
---

# BUG-066: `derived_from` читает файлы вне DATA_ROOT без проверки границы

| Поле | Значение |
|---|---|
| Bug ID | BUG-066 |
| Компонент | engine (`application/staleness.py`) |
| Обнаружено | 2026-11-28 — аудит остатка CLI, R-D |
| Окружение | todoc 0.1.0, Python 3.14.4, Ubuntu (WSL) |

## Сводка

`fragment_hash` собирал путь как `root / dep["path"]` и сразу читал файл.
Якорь `../secret.md@sha256:…` или абсолютный путь заставлял `todoc stale`
хешировать (а через `section`/pointer — разбирать) файл вне датасета.

## Шаги воспроизведения

1. В документе датасета: `derived_from: ["../secret.md@sha256:<64 нуля>"]`.
2. `env PYTHONPATH=src python3 -m todoc --root <root> index rebuild --apply`
3. `env PYTHONPATH=src python3 -m todoc --root <root> stale`

## Ожидаемое поведение

Зависимость вне DATA_ROOT — ошибка `staleness.dependency_outside_root`
(severity `error`); файл не читается и не хешируется. Отсутствующий файл внутри
корня остаётся `staleness.dependency_missing`.

## Фактическое поведение

До исправления файл вне корня читался и хешировался, а диагностика не отличала
недопустимый путь от обычного дрейфа.

## Доказательства

После исправления:

```
$ env PYTHONPATH=src python3 -m todoc --root <root> stale
"diagnostics": [{"code": "staleness.dependency_outside_root", "severity": "error", ...}]
```

Тесты: `tests/unit/test_staleness.py::test_fragment_hash_rejects_paths_outside_root`,
`test_check_owner_reports_outside_dependency`,
`tests/cli/test_cli_stale.py::test_stale_reports_dependency_outside_root`.

## Воздействие

`critical`/`friction`: `derived_from` — авторские данные и внешний ввод; без
границы агент или документ мог получить хеш содержимого вне датасета.

## Предложение по исправлению

`fragment_hash` проверяет `is_within_root` до `is_file()` и чтения; пустой путь,
`..`, абсолютный путь и симлинк наружу дают статус `outside`. `check_owner`
выдаёт отдельный код с guidance.

## Заметки

- 2026-11-28: `fixed` — коммит `fe0efbd`. Связанные: BUG-034, BUG-065.
