---
created: 2026-11-24
updated: 2026-11-28
id: doc:state-testing
title: "Состояние: тесты и качество"
doc_type: reference
lang: ru
source: docs/state/10-testing-and-quality.md
copied: true
---

# 10. Тестирование и приёмка

На объединённом дереве `2c0085a` прошли 1699 тестов. Покрытие составило 8724 строки и 3242 ветви без пропусков. Проверка выполнена в WSL на Python 3.14.4. Обзор команд и токенизация проверены отдельными сценариями. [Выпуск и приёмка](../../notes/unified-cli-release.md)

## Проверки перед коммитом

```bash
PYTHONPATH=src .venv/bin/python -m coverage run --branch --source=src/todoc -m pytest -q
.venv/bin/python -m coverage report --fail-under=100
PYTHONPATH=src .venv/bin/python -m todoc --root demo validate --all
PYTHONPATH=src .venv/bin/python tools/render_cli_reference.py --check
.venv/bin/python tools/linkcheck.py
git diff --check
```

Для изменённых исходников обязателен полный pytest с покрытием 100% строк и ветвей. Валидация демо должна вернуть ноль диагностик. В выводе linkcheck нужна строка `broken 0`. Актуальность генерируемого справочника проверяет `--check`.

## Что проверяют тесты

- `tests/cli/test_cli_contract.py` — дерево Click, конверт и справка, ошибки и форматы.
- `test_unified_docs.py`, `test_unified_lists.py`, `test_unified_relations.py` и `test_unified_e2e.py` в `tests/cli/` — метаданные, страницы, чтение, фильтрация, связи, preview и история.
- `tests/unit/test_storage_contracts.py` — встроенные и in-memory реализации, отказ записи и чтения, смена источника и конкурентная публикация.
- Сценарии используют изолированные каталоги. Бенчмарк копирует демо перед проверками.

[Воспроизводимый бенчмарк](15-benchmark.md) · [Точный синтаксис команд](https://github.com/sergey0002/todoc/blob/master/docs/state/cli.md)
