---
id: doc:bugs/bug-027-skills-tree-crash-on-root-skill-md.md
title: "BUG-027: skills tree падает traceback на vault с SKILL.md в корне"
doc_type: bug-report
lang: ru
created: 2026-11-27
updated: 2026-11-28
bug_id: BUG-027
status: fixed
severity: major
agent_impact: friction
component: cli
found: 2026-11-27
---

# BUG-027: skills tree падает traceback на vault с SKILL.md в корне

| Поле | Значение |
|---|---|
| Bug ID | BUG-027 |
| Компонент | cli (`skills tree`, сканер vault `application/skills.py`) |
| Обнаружено | 2026-11-27 — попытка перечислить скилы папки `demo/skill` |
| Окружение | todoc 0.1.0 (master 5e86eb7), Python 3.14.4 (WSL Ubuntu) |

## Сводка

`todoc skills tree --root demo --vault skill` завершается необработанным
`ValueError` и печатает Python-traceback вместо конверта ошибки: любой vault,
в корне которого лежит `SKILL.md` (скил на верхнем уровне хранилища),
неперечислим. `demo/skill` — ровно такой vault (6 скилов).

## Шаги воспроизведения

1. `todoc skills tree --root demo --vault skill`
2. Наблюдать traceback и код возврата `1`; JSON-конверта нет.
3. Контроль: `todoc skills tree --root demo` (vault `skills`, без корневого
   `SKILL.md`) → `ok: true`, `counts.skills: 30`.

## Ожидаемое поведение

1. Скил на верхнем уровне vault либо перечисляется с пустой секцией
   (`section: ""`), либо отвергается диагностикой `skills.vault_root_skill_md`
   в конверте — но не падением.
2. Любой ошибочный сценарий возвращает конверт `{ok: false, diagnostics,
   next_actions}` (контракт `_emit_error`, `src/todoc/cli.py:2369`) — traceback
   Python не является выводом CLI.

Источник ожидания: `AGENTS.md` (правило 7, P15: `guidance` в любом выводе);
`docs`-контракт конверта; соседний сценарий `skills tree` на `skills`-vault
работает штатно.

## Фактическое поведение

```
$ todoc skills tree --root demo --vault skill
Traceback (most recent call last):
  ...
  File ".../src/todoc/application/skills.py", line 134, in scan_skills
    section=folder.parent.relative_to(vault_root).as_posix()
ValueError: '/home/newuser/projects/todoc/demo' is not in the subpath of
            '/home/newuser/projects/todoc/demo/skill'
exit=1
```

## Доказательства

Причина — в выражении для `section` (`src/todoc/application/skills.py:134-135`):

```python
section=folder.parent.relative_to(vault_root).as_posix()
if folder.parent != vault_root else "",
```

Для `SKILL.md` в корне vault `folder == vault_root`, значит `folder.parent` —
родитель vault (`demo`), и `relative_to(vault_root)` бросает `ValueError`.
Охранное условие сравнивает `folder.parent` с `vault_root`, а не `folder`,
поэтому случай «скил в корне vault» не покрыт.

```
$ todoc skills tree --root demo --vault skill ; echo exit=$?
ValueError: '/home/newuser/projects/todoc/demo' is not in the subpath of
            '/home/newuser/projects/todoc/demo/skill'
exit=1

$ todoc skills tree --root demo --output table
skills/  (30 skills, 3 sections, 1 muted)
```

## Воздействие

- Агент не может перечислить `demo/skill` (6 скилов) — единственный способ
  узнать их состав — файловый обход (`Get-ChildItem`/`grep`), то есть выход из CLI.
- Traceback вместо конверта: агент не получает ни `code`, ни `guidance`,
  и вынужден читать исходники, чтобы понять причину.
- Severity major: команда падает на штатных данных демо (`demo/skill` — валидный
  vault по структуре), а не на экзотическом вводе.

## Предложение по исправлению

1. Заменить условие на `folder != vault_root` (или вычислять
   `section = folder.parent.relative_to(vault_root).as_posix() if folder != vault_root else ""`).
2. Обернуть `scan_skills` в try/except и отдавать `skills.scan_failed` в конверте.
3. Тест: vault с `SKILL.md` в корне → `ok: true`, `section: ""` у этого скила.
4. Проверка: `todoc skills tree --root demo --vault skill` перечисляет 6 скилов.

## Заметки

- Связан с BUG-029 (два хранилища скилов: `skills` и `skill/`) и BUG-008
  (`skills tree` — счётчики раздела).
- Поиск перед созданием (2026-11-27): `--type bug-report --query skills` →
  BUG-008 (счётчики), BUG-024 (шум индекса) — падения нет ни в одном.

- 2026-11-28: `fixed` — коммит `7d32813`. `skills tree` сохраняет корневой `SKILL.md` как узел `.` и не падает. Проверка: `tools/bug_acceptance.py --only BUG-027` → `fixed`. Тест: `tests/cli/test_cli_skills_tree.py::test_skills_tree_keeps_a_root_skill_and_inherits_muting`.
