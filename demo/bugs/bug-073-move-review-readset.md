---
id: doc:bugs/bug-073-move-review-readset.md
title: "BUG-073: план docs move не связывает preview со всем прочитанным корпусом"
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

# BUG-073: план docs move не связывает preview со всем прочитанным корпусом

| Поле | Значение |
|---|---|
| Bug ID | BUG-073 |
| Компонент | docs / план docs move |
| Обнаружено | 2026-11-28 — аудит перед исполнением |
| Окружение | todoc 0.1.0, Python 3.11.2, Linux, base 8b5d281 |

## Сводка

plan_hash исходной задачи 1 включает только изменяемые файлы. После preview можно добавить новый входящий документ или поменять правило типа: объект старого плана и проверки before_hash затронутых файлов этого не заметят. Сравнение диагностик только по (code,path) также скрывает новую ошибку того же класса.

## Шаги воспроизведения

Команды исполняются из корня репозитория. Исходную редакцию плана можно получить через `git show 8b5d281:demo/plan/docs-move-implementation.md`; текущая редакция содержит итог аудита в §8.

```bash
.venv/bin/todoc docs read --root demo --id doc:plan/docs-move-implementation.md --section '8. Прогресс и отклонения' --budget 12000
.venv/bin/python - <<'PY'
from todoc.application.fingerprint import source_fingerprint
import inspect
print(inspect.signature(source_fingerprint))
print(len({('markdown.link.target_missing', 'notes/hub.md'), ('markdown.link.target_missing', 'notes/hub.md')}))
PY
```

## Ожидаемое поведение

Тот же объект MovePlan нельзя применить к изменившемуся read-set; новая ошибка обязана блокировать запись, даже если её code/path уже были в baseline.

## Фактическое поведение

Исходные apply-проверки не включают появление нетронутых документов и изменение .todoc; множество (code,path) теряет кратность и различие повреждённых целей.

## Доказательства

```text
(root: Path, folders: list[Any], files: list[Any]) -> str; set из двух разных по смыслу ошибок с одним code/path имеет длину 1.
```

`src/todoc/application/fingerprint.py:48-58`; `src/todoc/service.py:192-230`. Исходный план: задача 1, строка 225; задача 4, строка 470; задача 6, строка 588.

## Воздействие

Блокер подготовки к исполнению: буквальная реализация исходного плана не обеспечивает его критерии успеха. При аудите понадобились отдельная сверка кода и воспроизводящий probe вместо доверия плану. Severity `docs` отражает текущий дефект: move ещё не реализован; эксплуатационную потерю данных этим отчётом не утверждаем. Точное дополнительное число токенов не измерялось.

## Предложение по исправлению

Включить source_fingerprint и дату планирования, revalidate live configuration и corpus при apply; для v1 использовать безопасную политику отказа на любом error baseline вместо некорректного baseline-diff. См. задачи 2/4/6 плана.

[Пересмотренный план](../plan/docs-move-implementation.md). Проверка исправления — соответствующие именованные regression-тесты при реализации, затем полный pytest/coverage.

## Заметки

- Поиск перед созданием (2026-11-28): `docs search --root demo --type bug-report --query "move" --limit 100 --budget 45000 --fields id,path,title` и такой же запрос `--query "план"`; выдачи полны, совпадения по компоненту и корневой причине не найдены.
- 2026-11-28: требования исправлены в плане по результатам аудита; код не менялся, статус оставлен `open` до реализации и проверки. Репорт не удалять.

- 2026-11-28: исправлено и закрыто по явному подтверждению пользователя вместе с v1 docs move. Проверки: полный pytest (1923 теста), 100% branch coverage; подробные regression-сценарии — §8 [плана](../plan/docs-move-implementation.md). Commit: включён в общий коммит `feat(docs): implement transactional document moves and safe revert` этой ветки.
