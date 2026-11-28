---
id: doc:bugs/bug-026-doctor-environment-checks-hardcoded-pass.md
title: "BUG-026: doctor --scope environment рапортует pass без проверки окружения"
doc_type: bug-report
lang: ru
created: 2026-11-27
updated: 2026-11-27
bug_id: BUG-026
status: open
severity: major
agent_impact: [friction, token_overrun]
tokens_extra_est: 2000
component: cli
found: 2026-11-27
---

# BUG-026: doctor --scope environment рапортует pass без проверки окружения

| Поле | Значение |
|---|---|
| Bug ID | BUG-026 |
| Компонент | cli (`doctor`) |
| Обнаружено | 2026-11-27 — проверка окружения перед работой с демо |
| Окружение | todoc 0.1.0 (master 5e86eb7), Python 3.14.4 (WSL Ubuntu), харнесс — Windows PowerShell 5.1 поверх `\\wsl.localhost` |

## Сводка

`todoc doctor` — единственная read-only диагностика окружения — не проверяет
окружение: обе проверки (`config`, `python`) захардкожены в `True`, а
`--scope environment` состоит ровно из одной из них. В результате при полностью
нерабочем окружении (нет `.venv`, нет `todoc` в `PATH`, `python3` — заглушка
Microsoft Store) `doctor` показывает `3/3 pass`, и агент считает окружение готовым.

## Шаги воспроизведения

1. `todoc doctor --root demo` → `checks_total: 3, passed: 3`, все `status: pass`.
2. `todoc doctor --root demo --scope environment` → `checks_total: 1, passed: 1`,
   единственная проверка `python` — `"Python 3.14.4."`.
3. В том же окружении: `Test-Path .venv` → `False`, `Get-Command todoc` → пусто,
   `python3 --version` → заглушка Store (см. BUG-023, шаги 1–3).
4. `todoc doctor --root demo --check entrypoint` → `checks_total: 0, passed: 0`,
   `ok: true` (неизвестный `id` молча отфильтровывается).

## Ожидаемое поведение

`--scope environment` содержит реальные проверки со стабильными `id` и честным
`status`, например:

| id | что проверяет |
|---|---|
| `entrypoint` | `todoc` достижим из оболочки харнесса (PATH/venv/обёртка) |
| `python` | версия ≥ 3.11 (а не константа) |
| `venv` | наличие `.venv` там, где его предписывает `AGENTS.md` |
| `encoding` | stdout в UTF-8 (без mojibake на не-ASCII данных) |
| `data_root` | `DATA_ROOT` существует и читается |

Каждая провалившаяся проверка — `status: fail` + `suggested_fixes` с готовой
командой исправления. Неизвестный `--check <id>` — `usage.error`, а не пустой
успех.

Источник ожидания: docstring команды — «Read-only environment diagnostics
(stable IDs, never auto-repairs)» (`src/todoc/cli.py:2312`); `--scope` объявлен
как «Группа проверок: dataset | environment | all» (`src/todoc/cli.py:2309`);
правило 2 `AGENTS.md` («перепроверяй каждый шаг») опирается на диагностику,
которой можно верить.

## Фактическое поведение

1. `config` и `python` — литерал `True` в списке проверок
   (`src/todoc/cli.py:2323-2326`): они не могут провалиться ни при каком окружении.
2. `DOCTOR_SCOPES["environment"] = ("python",)` (`src/todoc/cli.py:2365-2366`) —
   группа «environment» не содержит ни entrypoint, ни venv, ни кодировки.
3. Неизвестный `--check` даёт `checks_total: 0` и `ok: true` — молчаливый успех
   вместо диагностики опечатки.

## Доказательства

```
$ todoc doctor --root demo --scope environment --output table
ok: True
datasets: [{'dataset_id': 'dataset-80c70868', 'scope': 'environment',
            'checks_total': 1, 'passed': 1,
            'checks': [{'id': 'python', 'status': 'pass',
                        'message': 'Python 3.14.4.'}], 'fix_mode': False}]

$ todoc doctor --root demo
{"checks": [{"id": "config", "status": "pass"},
            {"id": "index", "status": "pass"},
            {"id": "python", "status": "pass", "message": "Python 3.14.4."}]}

# при этом окружение нерабочее (BUG-023):
$ Test-Path .venv            -> False
$ Get-Command todoc          -> (пусто)
$ python3 --version          -> Microsoft Store alias stub
```

Код: `src/todoc/cli.py:2323-2327` (`checks = [("config", True, ...), ("index",
ctx.store.current_generation_id() is not None, ...), ("python", True, ...)]`),
`src/todoc/cli.py:2365-2366` (`DOCTOR_SCOPES`).

## Воздействие

- Агент начинает сессию с `doctor` (правило 2) и получает ложное «всё готово» —
  дальше 3–4 неудачных вызова, пока не выяснится, что CLI недоступен. Цена ≈2k
  токенов за эпизод, и это повторяется в каждой новой сессии.
- Диагностика обесценена: если `doctor` не ловит «нет CLI вообще», он не поймает
  и более тонкие расхождения (кодировка, недостижимый `DATA_ROOT`).
- Риск для человека: «зелёный» отчёт скрывает незавершённую установку.

## Предложение по исправлению

1. Заменить литералы `True` на реальные проверки (entrypoint через
   `shutil.which("todoc")` или проверку entrypoint модуля, версия Python из
   `sys.version_info`, наличие `.venv`, `sys.stdout.encoding`, доступность root).
2. Расширить `DOCTOR_SCOPES["environment"]` этими `id`; неизвестный `--check`
   → `usage.error` с `suggested_fixes`.
3. Каждый `fail` — с `suggested_fixes` (готовая команда установки/обёртки).
4. Тесты: окружение без `.venv`/PATH даёт `fail` по `entrypoint`; неизвестный
   `--check` даёт ненулевой exit.

## Заметки

- Прямая причина, почему BUG-023 (CLI недоступен) и BUG-028 (нет runtime-контракта)
  не были замечены автоматически.
- Поиск перед созданием (2026-11-27): `--type bug-report --query doctor` — 0 совпадений.
