# Установка `todoc`

Каждая команда в этом руководстве выполнена и проверена на снимке от 2026-11-25
(`todoc 0.1.0`, Python 3.11.2, Debian). Ожидаемый вывод указан под командой.

## Требования

| Что | Значение |
|---|---|
| Python | **3.11 или новее** (`requires-python = ">=3.11"` в [`pyproject.toml`](../pyproject.toml)) |
| Зависимости | `click>=8.1`, `jsonschema>=4.18`, `markdown-it-py>=3.0` — ставятся автоматически |
| ОС | Любая с POSIX-семантикой файлов; проверка выполнения — Linux |
| Сборка | `setuptools>=68` (подтягивается самим pip) |

Внешних сервисов, базы данных и фонового процесса нет: `todoc` — это CLI, который читает
и пишет обычные файлы в выбранном каталоге (DATA_ROOT).

Проверить версию Python:

```bash
python3 -V
```

## Установка из исходников

Клонируйте репозиторий и перейдите в него:

```bash
git clone https://github.com/sergey0002/todoc.git
cd todoc
```

### Вариант 1. Editable — для разработки

Изменения в `src/` начинают действовать сразу, без переустановки:

```bash
pip install -e .
```

### Вариант 2. Обычная установка

Пакет копируется в `site-packages`:

```bash
pip install .
```

Проверено: после установки модуль лежит в
`<venv>/lib/python3.11/site-packages/todoc/__init__.py`.

### С зависимостями разработки

Добавляет `pytest>=8.0` и `coverage>=7.4`:

```bash
pip install -e ".[dev]"
```

### В изолированном окружении

Рекомендуемый способ — не трогать системный Python:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Проверка установки

```bash
todoc --version
```

```
todoc, version 0.1.0
```

Консольный скрипт `todoc` объявлен в `[project.scripts]` и попадает в `bin/` окружения.
Тот же результат даёт запуск как модуля — удобно, если скрипта нет в `PATH`:

```bash
python3 -m todoc --version
```

## Запуск без установки

Пакет не обязан быть установленным: достаточно добавить `src/` в `PYTHONPATH`.

```bash
PYTHONPATH=src python3 -m todoc --version
PYTHONPATH=src python3 -m pytest tests
```

Второй вариант проверяет, что окружение пригодно для работы: ожидаемый результат —
`437 passed`.

## Первый датасет

После установки создайте DATA_ROOT. `init` создаёт **только** служебный каталог
`.todoc/` и не трогает, не перемещает и не переименовывает ваши файлы.

```bash
todoc init --root ./knowledge
```

```json
{"ok": true, "data": {"dataset_id": "dataset-6b418a91",
                      "root": "/.../knowledge", "created": ".todoc/"}}
```

Создаётся 79 файлов:

| Что | Типов | Файлов | Состав одного типа |
|---|---|---|---|
| `dataset.json` | — | 1 | конфигурация датасета |
| `dir_types/` | 6 | 6 | `type.json` |
| `doc_types/` | 4 | 24 | `type.json`, `template.md`, 4 CRUD-промпта |
| `entity_types/` | 7 | 42 | `type.json`, `template.json`, 4 CRUD-промпта |
| `relation_types/` | 4 | 4 | `type.json` |
| `rules/` | — | 2 | `directory-rules.json`, `document-rules.json` |
| `queries/` | — | 0 | каталог для сохранённых запросов (пустой) |

Дальше — обычная последовательность:

```bash
todoc check-config  --root ./knowledge    # конфигурация и реестр типов читаются
todoc index rebuild --root ./knowledge    # опубликовать поколение индекса
todoc status        --root ./knowledge    # снимок: документы и записи
todoc validate      --root ./knowledge --all
```

## Как задавать DATA_ROOT

Три равнозначных способа; явный флаг имеет приоритет.

```bash
todoc --root ./knowledge status           # 1. явный флаг
export TODOC_ROOT=./knowledge             # 2. переменная окружения
todoc status
todoc --root ./a --root ./b check         # 3. несколько датасетов за один вызов
```

Без `--root` и без `TODOC_ROOT` команда завершится с `usage.missing_root` (exit 2),
а на каталоге без `.todoc/dataset.json` — с `config.missing_dataset`.

## Обновление и удаление

```bash
git pull && pip install -e .              # обновление editable-установки
pip uninstall todoc                       # удаление
```

После `pip uninstall` консольный скрипт `todoc` исчезает из `bin/`. Данные в DATA_ROOT
при этом не затрагиваются: `.todoc/` и документы остаются на диске.

## Устранение неполадок

| Симптом | Причина и действие |
|---|---|
| `todoc: command not found` | Скрипт установлен в `bin/` того окружения, которое не активно. Активируйте venv или запустите `python3 -m todoc`. |
| `usage.missing_root` (exit 2) | Не задан ни `--root`, ни `TODOC_ROOT`. |
| `config.missing_dataset` | В каталоге нет `.todoc/dataset.json` — выполните `todoc init --root PATH`. |
| `ModuleNotFoundError: todoc` при запуске тестов | Пакет не установлен; запустите с `PYTHONPATH=src`. |
| Установка падает на сборке | Нужен `setuptools>=68`; обновите pip: `pip install -U pip setuptools`. |

## Проверка после установки

Полный набор проверок, который проходит на чистом окружении:

```bash
python3 -m pytest                                     # 437 passed
python3 -m coverage run -m pytest tests               # тесты под coverage
python3 -m coverage report                            # в строке TOTAL: 2510, 0, 874, 0, 100%
todoc --root demo validate --all                      # ok, 0 диагностик
```

Строка `TOTAL` — это инструкции, пропуски, ветки, пропуски веток, покрытие.

## Что не входит в поставку

MVP намеренно не содержит MCP-сервера, векторного поиска, веб-интерфейса, импорта
PDF/DOCX, синхронизации и LSP. Каждое из этих направлений описано отдельным планом
в [`docs/plan/`](plan/). Полный список подтверждённых дефектов —
в [известных проблемах](state/11-known-issues.md).

## Дальше

- [Быстрый старт и все команды](../README.md)
- [Справочник CLI для агента](state/03-cli-reference.md)
- [Как агенту работать безопасно](state/12-agent-operations.md)
- [Устройство демо-датасета](state/13-demo-dataset.md)
