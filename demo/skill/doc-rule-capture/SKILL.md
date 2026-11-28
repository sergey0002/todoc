---
id: "doc:skill/doc-rule-capture/SKILL.md"
title: "Захват правила"
name: doc-rule-capture
description: >
  Фиксация бизнес-правила с примерами-тестами {given/when/then}: дедуп по statement, новая версия -vN+1 с ребром supersedes. Применять, когда пользователь формулирует правило или правило изменилось.
doc_type: agent-skill
lang: ru
created: 2026-11-26
updated: 2026-11-28
tags: [skill, documentation, agent]
---

# Захват правила

## Когда применять

- Пользователь сформулировал правило («если X, то Y SHALL Z»);
- правило изменилось — нужна новая версия.

## Шаги

1. Прочитать эталон: `todoc types prompt rule --op create --root KB`.
2. Дедуп: `todoc records list --root KB --type rule --output json` — тот же смысл?
   Активная версия существует и меняется → новая запись, не правка.
3. Черновик: `statement` — проверяемая формулировка SHALL; `examples` — минимум один
   `{given, when, then}` (как будущие fixture-тесты); при отказе — код ошибки в `then`;
   ребро `belongs_to` на `flow:<slug>`, если правило принадлежит флоу.
4. Новая версия: `rule:<имя>-vN+1` + `relations: [{type_id: supersedes, target: {id: rule:<имя>-vN}}]`;
   прежней записи ничего не менять (append-only).
5. Review-first: `records create --preview` → `--apply` → `validate --all` — 0 диагностик.

## Стоп-условия

- Нет ни одного примера {given/when/then} — остановись и спроси.
- Правило формулируется не проверяемо («держи консистентно») — переформулируй с пользователем.
