---
id: doc:bugs/bug-071-move-history-transaction-contract.md
title: "BUG-071: план docs move не задаёт безопасную историю удаления и отката"
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

# BUG-071: план docs move не задаёт безопасную историю удаления и отката

| Поле | Значение |
|---|---|
| Bug ID | BUG-071 |
| Компонент | docs / план docs move |
| Обнаружено | 2026-11-28 — аудит перед исполнением |
| Окружение | todoc 0.1.0, Python 3.11.2, Linux, base 8b5d281 |

## Сводка

Исходные задачи 5–7 кодируют удаление как after=b"", считают before=None созданием, хотя GitBackend может не сохранять before существующего файла, и откатывают без проверки последующих правок. Ошибка fsync журнала после дописки и ошибка индекса имеют противоречивые границы коммита.

## Шаги воспроизведения

Команды исполняются из корня репозитория. Исходную редакцию плана можно получить через `git show 8b5d281:demo/plan/docs-move-implementation.md`; текущая редакция содержит итог аудита в §8.

```bash
.venv/bin/todoc docs read --root demo --id doc:plan/docs-move-implementation.md --section '8. Прогресс и отклонения' --budget 12000
.venv/bin/python - <<'PY'
import inspect
from todoc.application.history import record_write
from todoc.adapters.history.backends import GitBackend
print(inspect.signature(record_write))
print(inspect.getsource(GitBackend.needs_snapshot))
PY
```

## Ожидаемое поведение

История различает absent и empty, хранит точные before-images независимо от Git; откат не уничтожает посторонние изменения; precommit failure и committed-but-index-failed имеют разные ответы.

## Фактическое поведение

В исходном плане after=b"" не отличим от пустого файла; before=None не доказывает создание. revert применяет снимки без CAS, а apply одновременно обещает откат любой ошибки и сохранение коммита при сбое индекса.

## Доказательства

```text
record_write(... before: bytes | None, after: bytes, ...); GitBackend.needs_snapshot: return last_revision == self.head() (если last_revision задан).
```

`src/todoc/application/history.py:79-118,167-208,342-373`; `src/todoc/adapters/history/backends.py:86-90`; `src/todoc/adapters/history/journal.py:37-55`; `src/todoc/adapters/history/store.py:26-28`. Исходный план: задачи 5–7, строки 530–682.

## Воздействие

Блокер подготовки к исполнению: буквальная реализация исходного плана не обеспечивает его критерии успеха. При аудите понадобились отдельная сверка кода и воспроизводящий probe вместо доверия плану. Severity `docs` отражает текущий дефект: move ещё не реализован; эксплуатационную потерю данных этим отчётом не утверждаем. Точное дополнительное число токенов не измерялось.

## Предложение по исправлению

Явные before_exists/after_exists и deletion tombstone, принудительные before-снимки, атомарная публикация строки журнала, общий CAS revert, чёткая точка коммита и failure-matrix. См. задачи 5–7 плана.

[Пересмотренный план](../plan/docs-move-implementation.md). Проверка исправления — соответствующие именованные regression-тесты при реализации, затем полный pytest/coverage.

## Заметки

- Поиск перед созданием (2026-11-28): `docs search --root demo --type bug-report --query "move" --limit 100 --budget 45000 --fields id,path,title` и такой же запрос `--query "план"`; выдачи полны, совпадения по компоненту и корневой причине не найдены.
- 2026-11-28: требования исправлены в плане по результатам аудита; код не менялся, статус оставлен `open` до реализации и проверки. Репорт не удалять.

- 2026-11-28: исправлено и закрыто по явному подтверждению пользователя вместе с v1 docs move. Проверки: полный pytest (1923 теста), 100% branch coverage; подробные regression-сценарии — §8 [плана](../plan/docs-move-implementation.md). Commit: включён в общий коммит `feat(docs): implement transactional document moves and safe revert` этой ветки.
