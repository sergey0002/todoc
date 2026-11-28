---
id: doc:bugs/bug-070-move-link-spans.md
title: "BUG-070: план docs move доверяет неточным координатам ссылок"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
status: fixed
severity: major
component: docs
agent_impact: friction
tags: [bugs, bug-report, move, audit]
---

# BUG-070: план docs move доверяет неточным координатам ссылок

| Поле | Значение |
|---|---|
| Bug ID | BUG-070 |
| Компонент | docs / план docs move |
| Обнаружено | 2026-11-28 — аудит перед исполнением |
| Окружение | todoc 0.1.0, Python 3.11.2, Linux, base 8b5d281 |

## Сводка

Алгоритм перезаписи в исходной задаче 2 использует display-координаты Link как точные и отрезает последний символ. Парсер может привязать настоящую ссылку к примеру внутри inline code. Это дефект контракта плана и ограничение адаптера, а не падение ещё несуществующего docs move.

## Шаги воспроизведения

Команды исполняются из корня репозитория. Исходную редакцию плана можно получить через `git show 8b5d281:demo/plan/docs-move-implementation.md`; текущая редакция содержит итог аудита в §8.

```bash
.venv/bin/python - <<'PY'
from todoc.adapters.formats.markdown import parse_markdown
for text in ['[a](old.md#part)', '`[example](old.md)` [real](old.md)']:
    link = parse_markdown(text).links[0]
    print(link.text, link.column, repr(text[link.column-1:link.end_column-1]))
PY
```

## Ожидаемое поведение

Менять только доказанный destination-token настоящей ссылки; code spans и закрывающая скобка сохраняются (план, критерий успеха 2).

## Фактическое поведение

Срез неполный, а второй результат указывает внутрь code span. Дополнительно fallback для reference-ссылки может забрать span соседней inline-ссылки.

## Доказательства

```text
a 1 '[a](old.md#part'
real 2 '[example](old.md'
```

`src/todoc/adapters/formats/markdown.py:216-267` (`_locate_columns`), `:36-44` (`Link`). Исходный план на базе `8b5d281`: задача 2, строки 253–260. BUG-046 относится к fix, не обеспечивает безопасность нового move.

## Воздействие

Блокер подготовки к исполнению: буквальная реализация исходного плана не обеспечивает его критерии успеха. При аудите понадобились отдельная сверка кода и воспроизводящий probe вместо доверия плану. Severity `major` отражает текущий дефект: move ещё не реализован; эксплуатационную потерю данных этим отчётом не утверждаем. Точное дополнительное число токенов не измерялось.

## Предложение по исправлению

Ввести отдельные доказанные edit-spans адаптера, не копировать regex в move; неоднозначную или затронутую неподдержанную форму блокировать до записи. См. задачу 1 пересмотренного плана.

[Пересмотренный план](../plan/docs-move-implementation.md). Проверка исправления — соответствующие именованные regression-тесты при реализации, затем полный pytest/coverage.

## Заметки

- Поиск перед созданием (2026-11-28): `docs search --root demo --type bug-report --query "move" --limit 100 --budget 45000 --fields id,path,title` и такой же запрос `--query "план"`; выдачи полны, совпадения по компоненту и корневой причине не найдены.
- 2026-11-28: требования исправлены в плане по результатам аудита; код не менялся, статус оставлен `open` до реализации и проверки. Репорт не удалять.

- 2026-11-28: исправлено и закрыто по явному подтверждению пользователя вместе с v1 docs move. Проверки: полный pytest (1923 теста), 100% branch coverage; подробные regression-сценарии — §8 [плана](../plan/docs-move-implementation.md). Commit реализации: `2c0e829` (`feat(docs): implement transactional document moves and safe revert`).
