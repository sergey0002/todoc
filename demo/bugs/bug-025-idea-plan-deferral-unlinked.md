---
id: doc:bugs/bug-025-idea-plan-deferral-unlinked.md
title: "BUG-025: решение плана об отложенной идее не связано с самой идеей"
doc_type: bug-report
lang: ru
bug_id: BUG-025
status: fixed
severity: docs
agent_impact: friction
tokens_extra_est: 2000
component: demo
found: 2026-11-28
created: 2026-11-27
updated: 2026-11-28
tags: [bugs, bug-report, demo, ideas, plan, status, links]
---

# BUG-025: решение плана об отложенной идее не связано с самой идеей

| Поле | Значение |
|---|---|
| Bug ID | BUG-025 |
| Компонент | demo (идеи ↔ планы, front matter) |
| Обнаружено | 2026-11-28 — ответ на вопрос «какие идеи не реализованы» |
| Окружение | todoc 0.1.0 (5e86eb7), Python 3.14.4, Windows 11 + WSL2 Ubuntu |

## Сводка

Идея `action-logging` имеет `status: captured` и текст «не перешла в план», но
план `unified-cli-output-implementation` содержит явное решение отложить её
(«не создавать `trace` и не писать логи»). Машиночитаемой связи между решением
плана и идеей нет: ни поля `plan`/`deferred_by`, ни ссылки в «Связанных
документах». По данным датасета идея выглядит просто нереализованной.

## Шаги воспроизведения

1. `todoc docs read --root demo --id doc:ideas/action-logging.md --output markdown`
   — проверить `status` и «Связанные документы».
2. Прочитать решение плана:
   `demo/plan/unified-cli-output-implementation.md:513`.
3. `todoc docs search --root demo --query "action-logging" --limit 10 --output json`
   — проверить, находит ли поиск связь идея ↔ решение плана.

## Ожидаемое поведение

Статус идеи отражает фактическое решение: `deferred` (или `blocked`) с полем
`deferred_by: doc:plan/unified-cli-output-implementation` и ссылкой в
«Связанных документах». `HOME.md` описывает не «зафиксирована», а «отложена
планом X из-за противоречия с read-only-контрактом». Валидация может требовать,
чтобы решение плана ссылалось на `doc:` идеи.

## Фактическое поведение

- Front matter идеи: `status: captured`; «Связанные документы» — только
  `agent-state`, `constitution`, `bug-012`; плана нет.
- План прямо откладывает идею и запрещает `trace`/логи до отдельного решения.
- В плане идея упомянута лишь строкой манифеста (`:287`) и строкой решения
  (`:513`); обратной ссылки из идеи нет.
- `docs search` находит план только как совпадение по манифесту, не как связь.

## Доказательства

```
# demo/ideas/action-logging.md:6,19
status: captured
- Статус: `captured` (идея зафиксирована, не перешла в план)

# demo/plan/unified-cli-output-implementation.md:513
| `demo/ideas/action-logging.md` — captured | ... | Идея предлагает в режиме `all` писать каждый read в XDG,
а `notice` — preview: это прямо противоречит запрету **любых** записей при read/preview, в том числе в XDG.
До отдельного решения дефолт — без трассировки; не создавать `trace` и не писать логи. ... |

# demo/HOME.md:109
... **Зафиксирована** (fm captured, 2026-11-26).
```

```yaml
# front matter идеи — нет полей plan/deferred_by
related: ["[[agent-state]]", "[[constitution.md]]", "[[bug-012-...]]"]
```

## Воздействие

Агент, отвечая на вопрос о статусе идей, читает front matter и сообщает
«не реализована, плана нет» — что формально верно по данным, но противоречит
принятому решению. Чтобы найти решение, нужен полнотекстовый поиск и чтение
чужого плана. В сессии это дало неверный первый ответ и потребовало
дополнительного раунда поиска (~2k токенов).

## Предложение по исправлению

- Добавить в идею `status: deferred` и `deferred_by: doc:plan/unified-cli-output-implementation`
  (или поле `plan`), плюс ссылку в «Связанных документах».
- Обновить `HOME.md:109` формулировкой об отложенном решении.
- Ввести правило валидации: решение плана, меняющее судьбу идеи, обязано
  содержать `doc:`-ссылку на идею, а идея — обратное поле.
- Проверка: `docs read --id doc:ideas/action-logging.md` показывает `deferred_by`;
  `docs search --query "action-logging"` возвращает идею и план как связанные.

## Заметки

Поиск перед созданием (2026-11-28): `--type bug-report --query "action-logging"` — совпадений нет.
Связанные: идея [`ideas/action-logging.md`](../ideas/action-logging.md),
история выпуска [`notes/unified-cli-release.md`](../notes/unified-cli-release.md),
BUG-022 (нет обзорной выборки по статусу — из-за чего статус читается по одному документу).

2026-11-28. Отложенный объём action-logging указан в самой идее.
Исторический план доступен через [сводку выпуска](../notes/unified-cli-release.md).
Отдельное поле deferred_by и обязательная схема отсрочки остаются в объёме этого репорта.

- 2026-11-28: `fixed` — коммит `7b671e0`. Идея `ideas/action-logging.md` явно фиксирует отсрочку и ссылается на `notes/unified-cli-release.md`; сводка выпуска ссылается обратно в разделе «Связанные работы». Проверка: `tools/bug_acceptance.py --only BUG-025` → `fixed`.
