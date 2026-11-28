---
id: doc:bugs/bug-072-move-provenance-reanchoring.md
title: "BUG-072: план docs move может скрыть старый дрейф зависимостей"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
status: fixed
severity: docs
component: docs
agent_impact: friction
tags: [bugs, bug-report, move, audit]
---

# BUG-072: план docs move может скрыть старый дрейф зависимостей

| Поле | Значение |
|---|---|
| Bug ID | BUG-072 |
| Компонент | docs / план docs move |
| Обнаружено | 2026-11-28 — аудит перед исполнением |
| Окружение | todoc 0.1.0, Python 3.11.2, Linux, base 8b5d281 |

## Сводка

Исходная задача 3 безусловно заменяет hash в derived_from новым текущим hash. Уже устаревший план после механического переноса станет выглядеть актуальным без содержательного review. Также fragment_hash не принимает новый текст и нельзя применять его к отсутствующей цели preview.

## Шаги воспроизведения

Команды исполняются из корня репозитория. Исходную редакцию плана можно получить через `git show 8b5d281:demo/plan/docs-move-implementation.md`; текущая редакция содержит итог аудита в §8.

```bash
.venv/bin/python - <<'PY'
import inspect
from todoc.application.staleness import fragment_hash
print(inspect.signature(fragment_hash))
PY
.venv/bin/todoc stale --root demo
```

## Ожидаемое поведение

Механический перенос не подтверждает прочтение обновлённого источника. Только совпавший с baseline hash можно перенести на механически изменённые байты.

## Фактическое поведение

В алгоритме отсутствует сравнение expected с фактическим before-fragment. Также baseline.artifacts нельзя обновлять до нового hash: это исторический снимок открытия change.

## Доказательства

```text
(root: Path, dep: dict[str, Any]) -> tuple[str | None, str]; на baseline stale=2.
```

`src/todoc/application/staleness.py:64-98,157-229`; `src/todoc/application/changes.py:522-539`. Исходная задача 3 плана, строки 370–382. BUG-011 — отсутствие общего reanchor, а здесь иной дефект: небезопасная автоматическая политика move.

## Воздействие

Блокер подготовки к исполнению: буквальная реализация исходного плана не обеспечивает его критерии успеха. При аудите понадобились отдельная сверка кода и воспроизводящий probe вместо доверия плану. Severity `docs` отражает текущий дефект: move ещё не реализован; эксплуатационную потерю данных этим отчётом не утверждаем. Точное дополнительное число токенов не измерялось.

## Предложение по исправлению

Добавить чистый fragment_hash_text с точной семантикой старого API. Переписывать путь всегда, hash только для совпавшей опоры; старый drift/ack сохранять, неоднозначный ack удалять с warning. См. задачу 3 плана.

[Пересмотренный план](../plan/docs-move-implementation.md). Проверка исправления — соответствующие именованные regression-тесты при реализации, затем полный pytest/coverage.

## Заметки

- Поиск перед созданием (2026-11-28): `docs search --root demo --type bug-report --query "move" --limit 100 --budget 45000 --fields id,path,title` и такой же запрос `--query "план"`; выдачи полны, совпадения по компоненту и корневой причине не найдены.
- 2026-11-28: требования исправлены в плане по результатам аудита; код не менялся, статус оставлен `open` до реализации и проверки. Репорт не удалять.

- 2026-11-28: исправлено и закрыто по явному подтверждению пользователя вместе с v1 docs move. Проверки: полный pytest (1923 теста), 100% branch coverage; подробные regression-сценарии — §8 [плана](../plan/docs-move-implementation.md). Commit реализации: `2c0e829` (`feat(docs): implement transactional document moves and safe revert`).
