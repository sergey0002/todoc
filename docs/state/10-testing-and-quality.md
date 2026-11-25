# 10. Тесты и качество

## Текущие цифры (проверено прогоном 2026-11-25)

| Показатель | Значение |
|---|---|
| Тестов | 953 проходят |
| Тестовых файлов | 28 (+ `conftest.py`) |
| Строк в `tests/` | 8872 |
| Покрытие инструкций | 4466 / 4466 → 100% |
| Покрытие веток | 1628 / 1628 → 100% |
| Пропущено | 18 (все — `tests/cli/test_cli_contract.py`) |

Все 18 пропусков имеют одну причину: параметризованная проверка K48 («отказ — это конверт»)
применима только к команде, которая завершилась неуспехом. Из 46 листовых команд 28 в пустом
датасете отдают отказ и проверяются на форму конверта, а 18 завершаются успешно — там
проверять нечего, и тест честно это говорит вместо ложного «прошёл». Новый `timeline` попал
в обе проверки автоматически, без правки теста: перечень команд вычитывается из CLI.

Измерение качества формализовано в бенчмарке: 30 критериев, текущий балл 29.5/30 —
см. [15-benchmark.md](15-benchmark.md) и `bench/criteria.md`.

## Как запускать

```bash
# тесты
PYTHONPATH=src python3 -m pytest tests

# покрытие (branch-режим включён в pyproject.toml)
PYTHONPATH=src python3 -m coverage run -m pytest tests
PYTHONPATH=src python3 -m coverage report -m

# установка и живой CLI
pip install -e .
todoc --version
```

Те же гейты выполняет CI (`.github/workflows/tests.yml`, Python 3.11 и 3.12): `pytest`,
`coverage report --fail-under=100`, `tools/linkcheck.py` и `validate --all` на демо-датасете.
Покрытие здесь — порог сборки, а не отчёт: падение ниже 100 % останавливает прогон.

Конфигурация в `pyproject.toml`: `testpaths = ["tests"]`, `addopts = "-q"`,
`[tool.coverage.run] branch = true`, `source = ["src/todoc"]`.

## Версии окружения

| Пакет | Версия |
|---|---|
| Python | 3.11.2 |
| click | 8.5.1 |
| jsonschema | 4.26.0 |
| markdown-it-py | 4.3.0 |
| pytest | 9.2.0 |
| coverage | 7.17.5 |

## Состав тестов

| Каталог | Что покрывает |
|---|---|
| `tests/unit/` | домен, конфиг, сканер, адаптеры форматов, валидатор, поиск, запросы, запись, реестр, envelope |
| `tests/cli/` | все команды через `CliRunner`, включая коды выхода и форму конверта |
| `tests/integration/` | сквозной сценарий: init → check → search → read |
| `tests/unit/test_history.py` | журнал, снимки, `content_at`, диффы, план отката, `gc`, лимиты |
| `tests/unit/test_changes.py` | жизненный цикл изменения, дельты, `validate`/`verify`, атомарность |
| `tests/unit/test_context.py` | сборка контекста, бюджет байт, усечение диффов |
| `tests/cli/test_cli_history.py` | команды истории через CLI, включая `observed` и предупреждения |
| `tests/cli/test_cli_changes.py` | команды изменений через CLI: K42 (один вызов) и K43 (бюджет) |
| `tests/unit/test_temporal.py` | K40 (точные интервалы), K41 (инвалидация), лента |
| `tests/cli/test_cli_temporal.py` | `timeline`, `records query --as-of`, коды `temporal.*` |
| `tests/cli/test_cli_contract.py` | K47 и K48 параметризованы по всему перечню команд |
| `tests/unit/test_formats_hardened.py` | укреплённые адаптеры: токены ссылок, строгий JSON, схемы записей, отношения |

`test_cli_contract.py` вычитывает перечень команд из самого `todoc.cli.cli`, а не держит его
списком: команда, добавленная позже, попадает в проверку автоматически, а
`test_every_leaf_command_is_covered` запрещает списку сузиться. Этот файл запускает команды
через `subprocess`, поэтому он **проверяет контракт, а не даёт покрытие** — цифры покрытия
несут тесты, идущие в процессе.

Отдельные тесты фиксируют поведение, найденное при аудите: ссылки внутри code fence не считаются
ссылками, reference-style ссылки находятся, враждебная вложенность JSON не роняет процесс,
нечёткая подсказка не предлагается при постороннем имени файла.

## Что покрытие НЕ гарантирует

100% покрытие не означает отсутствие дефектов: тесты работают в процессе через `CliRunner`,
поэтому часть контракта (реальный stdout/stderr, коды выхода из `main()`, поведение на большом
датасете) проверяется только ручными прогонами. Именно так были найдены проблемы из
[11-known-issues.md](11-known-issues.md).

Практическое правило: любой новый дефект получает **сначала** тест-воспроизведение, потом исправление.

## Ручная проверка (smoke)

```bash
todoc init --root /tmp/kb --output json
todoc check --root /tmp/kb
todoc docs new --root /tmp/kb --title "Design" --dir notes
todoc docs search --root /tmp/kb --query "design"
todoc validate --root /tmp/kb --all
```

Дополнительно демо-датасет в репозитории служит живым smoke-тестом:
`todoc validate --root demo --all` обязан возвращать ноль диагностик.

## Связанные разделы

- [02-architecture.md](02-architecture.md) — что именно покрывают модули.
- [11-known-issues.md](11-known-issues.md) — что тесты пока не ловят.
