---
id: doc:bug-002-change-open-note-unknown
title: "BUG-002: change open создаёт файлы с doc_type note без правила — резолвится в unknown"
doc_type: bug-report
lang: ru
bug_id: BUG-002
status: triaged
severity: major
component: engine
found: 2026-11-25
---

# BUG-002: change open создаёт файлы с doc_type note без правила — резолвится в unknown

| Поле | Значение |
|---|---|
| Bug ID | BUG-002 |
| Компонент | engine (application/changes.py + дефолтные ассеты config.py) |
| Обнаружено | 2026-11-25 — подготовка пилота плана `doc:plan-softdoc-profile` |
| Окружение | todoc 0.1.0 (4b6ae47), Python 3.11.2, Linux |

## Сводка

`todoc change open` создаёт в папке изменения файлы `proposal.md` и `tasks.md`
с `doc_type: note` во front matter, но ни дефолтные ассеты `init`, ни демо не
содержат fm-правило для `note` — в типовой папке `changes/<slug>/` (на которую
glob-правила `notes/**` не действуют) оба файла резолвятся в `unknown`.

## Шаги воспроизведения

1. В свежем датасете: `todoc init --root kb && todoc change open --root kb --title "Проверка"`
2. `todoc explain-path --root kb "changes/проверка/proposal.md"`
3. `todoc validate --root kb --all` — 0 диагностик (молча).

## Ожидаемое поведение

Файлы, создаваемые самим движком, типируются без участия правил датасета — либо
дефолтные ассеты `init` включают fm-правило `doc_type: note → note` (движок
сам пишет этот тип в свои файлы, значит обязан уметь его резолвить).

## Фактическое поведение

`doc_type: unknown` для `proposal.md` и `tasks.md` в каждом датасете, где нет
локального fm-правила `note`. Проверка по коду: `application/changes.py`
(создание proposal/tasks, шаблон с `doc_type: note`); дефолтные правила в
`config.py` fm-правила для note не содержат.

## Доказательства

Код создания шаблона — `src/todoc/application/changes.py` (функция `open_change`):

```python
proposal = folder / "proposal.md"
if not proposal.exists():
    atomic_write(proposal, f"---\ntitle: \"{title}\"\ndoc_type: note\n---\n\n"
                           f"# {title}\n\n## Суть\n\nОпишите, зачем это изменение.\n")
```

Правила демо (`demo/.todoc/rules/document-rules.json`) и дефолтные правила
`init` не содержат правила с `"front_matter": {"doc_type": "note"}` — проверено
`grep`. Папка `changes/<slug>/` не покрывается ни одним glob-правилом.

## Воздействие

- Систематический дефект: каждый `change open` в каждом датасете без локального
  правила даёт два unknown-документа — «предложение» и «задачи» изменения
  невидимы для типовых фильтров и не проверяются структурно.
- Противоречит замыслу §4 движка: «папка изменения — намерение человека, оно
  читается в Obsidian и проходит review» — review-first без типа ослаблен.
- Обходимо одним fm-правилом, но правило должно быть в ассетах по умолчанию.

## Предложение по исправлению

1. В `config.py` (дефолтные правила `init`) добавить fm-правило
   `doc_type: note → note`, приоритет 200.
2. В демо — то же правило (внесено в план `doc:plan-softdoc-profile`, задача 1).
3. Регресс-тест: init → change open → validate → explain-path proposal.md =
   `note`.

## Заметки

- Родительский дефект: BUG-001 (явный doc_type без правила → unknown).
- Связано с планом `doc:plan-softdoc-profile` (решение D3) и с пилотом
  (задача 5, шаг 3 — прогон `change open` на демо).
