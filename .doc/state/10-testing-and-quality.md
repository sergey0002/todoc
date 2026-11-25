# 10. Тесты и качество

## Текущие цифры (проверено прогоном 2026-11-25)

| Показатель | Значение |
|---|---|
| Тестов | 332, все проходят |
| Тестовых файлов | 16 (+ `conftest.py`) |
| Строк в `tests/` | 3007 |
| Покрытие инструкций | 2138 / 2138 → 100% |
| Покрытие веток | 698 / 698 → 100% |
| Пропущено | 0 |

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
| `tests/unit/test_formats_hardened.py` | укреплённые адаптеры: токены ссылок, строгий JSON, схемы записей, отношения |

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
