---
id: doc:bugs/bug-068-docs-read-headings-bypass-budget.md
title: "BUG-068: docs read без --fields отдаёт все headings вне бюджета — шапка плана стоит 9-13 КБ при --budget 120"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
tags: [bugs, bug-report, docs-read, budget]
bug_id: BUG-068
status: open
severity: minor
agent_impact: [friction, token_overrun]
tokens_extra_est: 12000
component: cli
found: 2026-11-28
tags: [bugs, bug-report, cli, read, budget, truncation, headings]
---

# BUG-068: docs read без --fields отдаёт все headings вне бюджета — шапка плана стоит 9-13 КБ при --budget 120

| Поле | Значение |
|---|---|
| Bug ID | BUG-068 |
| Компонент | cli |
| Обнаружено | 2026-11-28 — сессия «какие планы и идеи не реализованы»: агент читал шапки планов, чтобы узнать статус |
| Окружение | todoc 0.1.0, Python 3.14, WSL Ubuntu, `env PYTHONPATH=src python3 -m todoc` |

## Сводка

`--budget` у `docs read` ограничивает только `result.text`, но не метаданные ответа: `headings`, `tags`, `related`. Поэтому чтение шапки плана с `--budget 120` отдаёт 9–13 КБ и `truncated: true` по тексту, хотя сам текст обрезан до 120 символов. Обходной путь (`--fields id,title,updated`) уменьшает ответ до 1,2 КБ, но ни справка `docs read`, ни `guidance` на него не указывают.

## Шаги воспроизведения

1. `todoc docs read --root demo --id 'doc:plan/bmad-wave-planning-skills.md' --budget 120 | wc -c` → `9030` байт; в `result.headings` — 24 заголовка.
2. `todoc docs read --root demo --id 'doc:plan/open-bug-backlog-closure.md' --budget 120 | wc -c` → `12779` байт; в `result.headings` — 55 заголовков.
3. `todoc docs read --root demo --id 'doc:plan/bmad-wave-planning-skills.md' --fields id,title,updated --budget 120 | wc -c` → `1197` байт, `headings` отсутствуют.

## Ожидаемое поведение

Бюджет обязан быть честным для всего ответа, а не только для `text`: либо `headings` входят в `--budget`, либо при заданном `--budget` метаданные проецируются по умолчанию, либо ответ сообщает `meta.budget` и подсказку перейти на `--fields`/`--section`. Опора: исправленные репорты того же класса — BUG-005 (`--section` игнорирует `--budget`), BUG-018 (`docs read` без `--section` игнорирует `--budget`), BUG-045 (`docs search --budget` не ограничивает ответ). Контракт «budget ограничивает ответ» уже принят системой; `headings` — единственный оставшийся неохваченный блок.

## Фактическое поведение

1. `text` обрезается до 120 символов, но `headings` отдаются целиком и не влияют на бюджет.
2. `result.truncated: true` говорит только про текст; размер ответа при этом превышает бюджет в 75–106 раз (9 030 и 12 779 байт против 120 символов текста).
3. Справка `docs read` описывает `--budget` как «Maximum number of Unicode characters of text content» и не упоминает, что метаданные им не покрыты и что есть `--fields`.
4. `guidance` в ответе пуст (`items: []`), хотя ситуация — типовой перерасход.

## Доказательства

```
$ todoc docs read --root demo --id 'doc:plan/bmad-wave-planning-skills.md' --budget 120 | wc -c
9030
$ todoc docs read --root demo --id 'doc:plan/open-bug-backlog-closure.md' --budget 120 | wc -c
12779
$ todoc docs read --root demo --id 'doc:plan/bmad-wave-planning-skills.md' --fields id,title,updated --budget 120 | wc -c
1197
```

`headings` в первом ответе: 24 элемента (`Волна 0…`, `1. Критерии успеха`, …, `8. Прогресс и отклонения`). Во втором — 55 элементов (`Закрытие открытого бэклога…` … `9. Карта находок CLI`).

## Воздействие

Сценарий «узнать статус/раздел плана» — массовый: любой обзор бэклога начинается с чтения шапок. В эпизоде 2026-11-28 агент сделал три таких чтения подряд (9,0 + 12,8 + ~8 КБ ≈ 30 КБ ≈ 7,5 тыс. токенов) только чтобы получить `status`, который уже был в `docs list`. После этого понадобились ещё шесть чтений секции с `--budget 120/200/300` (все `truncated`) и два с `--line-range` — итого ~12 тыс. токенов перерасхода (`tokens_extra_est: 12000`). Прямой путь без CLI — один `grep -n status`/`head -20` по файлу. Severity `minor`: результат не искажается, но стоимость обзора растёт кратно.

## Предложение по исправлению

1. В `src/todoc/cli.py` (обработчик `docs read`) при заданном `--budget` включать сериализованные `headings`/`tags`/`related` в счёт бюджета или проецировать их только по явному `--fields`; отдавать `data.meta.budget = {limit, used_bytes, exhausted}` по образцу BUG-045.
2. Добавить в `src/todoc/data/guidance` подсказку `docs.read.metadata_budget`: «шапка не входит в бюджет — используйте `--fields` или `--section`», с `next_actions` на точный argv.
3. Проверка: `docs read --id <план> --budget 120 | wc -c` укладывается в бюджет либо содержит `meta.budget.exhausted: true`; контрактный тест в `tests/cli/test_unified_docs.py`.

## Заметки

- Поиск перед созданием (2026-11-28): полный инвентарь `docs list --root demo --type bug-report --origin document --limit 1000` (68 репортов). Прямых дублей нет; ближайшие BUG-005, BUG-018, BUG-045 — все `fixed`, но про `text`/`search`, не про метаданные `docs read`.
- Связанный репорт: BUG-069 (обзор планов/идей) — этот дефект был одной из причин перерасхода в том же эпизоде.
- `docs read --fields` работает и даёт 1,2 КБ — то есть фикс может быть только в подсказке и дефолте, без изменения модели данных.
