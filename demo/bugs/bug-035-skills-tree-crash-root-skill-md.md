---
id: doc:bugs/bug-035-skills-tree-crash-root-skill-md.md
title: "BUG-035: DUPLICATE of BUG-027: skills tree падает при наличии SKILL.md в корне vault"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
tags: [bugs, bug-report, skills-tree, duplicate]
bug_id: BUG-035
status: duplicate
severity: major
agent_impact: friction
tokens_extra_est: 0
component: cli
found: 2026-11-28
---

# BUG-035: DUPLICATE of BUG-027: skills tree падает при наличии SKILL.md в корне vault

| Поле | Значение |
|---|---|
| Bug ID | BUG-035 |
| Компонент | cli (`src/todoc/application/skills.py:134`, `src/todoc/cli.py:336`) |
| Обнаружено | 2026-11-28 — `todoc skills tree --root demo --vault skill` |
| Окружение | todoc 0.1.0, Python 3.14.3, Windows 11 + WSL2 Ubuntu |

## Сводка

**ДУБЛИКАТ BUG-027**. Команда `skills tree` падает с `ValueError` при сканировании vault, в корне которого лежит `SKILL.md`.

## Шаги воспроизведения

1. `python -m todoc skills tree --root demo --vault skill`

## Ожидаемое поведение

`skills tree` должен корректно обрабатывать скилы в корне vault (section == "").

## Фактическое поведение

```
ValueError: '\\wsl.localhost\Ubuntu\home\newuser\projects\todoc\demo' is not in the subpath of '\\wsl.localhost\Ubuntu\home\newuser\projects\todoc\demo\skill'
  File "...\todoc\application\skills.py", line 134, in scan_skills
    section=folder.parent.relative_to(vault_root).as_posix()
```

## Доказательства

BUG-027 (doc:bugs/bug-027-skills-tree-crash-on-root-skill-md.md) описывает ту же проблему с теми же шагами воспроизведения и тем же местом в коде (`src/todoc/application/skills.py:134`).

## Воздействие

См. BUG-027.

## Предложение по исправлению

См. BUG-027. Исправить условие в `skills.py:134` с `folder.parent != vault_root` на `folder != vault_root`.

## Заметки

- **ДУБЛИКАТ BUG-027** (status: open, создан 2026-11-27).
- Этот репорт создан во время аудита 2026-11-28, дубликат обнаружен при поиске перед созданием (но поиск не нашёл из-за отличия в названии vault: `skill` vs `skills`).
- Закрыт как duplicate 2026-11-28.
