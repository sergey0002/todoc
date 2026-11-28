---
id: doc:bugs/bug-047-malformed-relation-target.md
title: "BUG-047: Неверная форма target отношения обрушает валидацию"
doc_type: bug-report
lang: ru
created: 2026-11-27
updated: 2026-11-28
tags: [bugs, bug-report, relations, validation]
bug_id: BUG-047
status: fixed
severity: major
agent_impact: friction
component: engine
found: 2026-11-28
---

# BUG-047: Неверная форма target отношения обрушает валидацию

## Сводка

Один JSON-документ с `relations[].target` в виде строки приводит к `AttributeError` при сборке контекста. Вместо диагностического конверта команда validate завершается исключением.

## Шаги воспроизведения

Выполнить из корня проекта `PYTHONPATH=src python3 .doc/codexaudit/evidence/reproduce.py`. Сценарий `malformed_relation` создаёт отдельный временный dataset через CLI init, затем фикстуру `bad.json`:

```json
{"record_id":"note:bad","entity_type":"note","title":"bad","relations":[{"type_id":"references","target":"bad-target"}]}
```

Эквивалентная целевая команда: `todoc --root <temporary-root> validate --all`.

## Ожидаемое поведение

`ok:false`, диагностика malformed relation с path/pointer и код выхода валидации. CLI предназначен для выявления дефектов исходных файлов, а не только для уже корректных данных; публичный контракт ошибок описан в `demo/notes/agent-contract.md`.

## Фактическое поведение

Вызов через Click runner возвращает exit 1, stdout без конверта и `AttributeError("'str' object has no attribute 'get'")`. CLI main также не перехватывает этот тип исключения.

## Доказательства

`src/todoc/service.py:114–117`: проверяется тип самого rel, но `(rel.get("target") or {}).get("id")` вызывается без проверки типа target. Результат сохранён в разделе `malformed_relation` протокола `.doc/codexaudit/evidence/verification.md`.

## Воздействие

Повреждённая или импортированная запись мешает валидировать датасет и собирать индекс. Severity major: основная операция завершается вне контракта. Агент вынужден разбирать traceback и искать файл напрямую; это фрикция. Нельзя утверждать удалённый DoS без серверной модели deployment.

## Предложение по исправлению

Нормализовать/проверять тип relations и target до извлечения рёбер; передавать диагностики без повторного небезопасного разбора. Приёмка: строки, числа, null, массив и объект без id не роняют validate, search, records list; корректные отношения продолжают индексироваться.

## Заметки

Дедуп выполнен 2026-11-28 по `relation.malformed` и `service`; исходные результаты сохранены в протоколе. BUG-020 описывает другой механизм (неймспейс типа), это не дубль. Фикс не реализован.

- 2026-11-28: `fixed` — коммит `7d32813`. Некорректная цель связи даёт `relation.*` диагностику, а не исключение. Тест: `tests/unit/test_validator.py`.
