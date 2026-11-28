---
id: doc:skills/process/todoc-backlog/SKILL.md
title: "Скил: обзор бэклога репортов и идей"
doc_type: agent-skill
lang: ru
created: 2026-11-28
updated: 2026-11-28
name: todoc-backlog
description: "Use when asked «what is still open / what is not fixed / what to do next» over bug reports, ideas, or plans. Builds the list in one docs list call with --status/--fields, separates md documents from records/documents JSON mirrors, and reports counts with the source of each number. Never uses records list for doc_type and never greps front matter."
---

# Скил: обзор бэклога репортов и идей

## When to Use

- «Какие багфиксы не закрыты», «что открыто», «что чинить следующим»,
  «какие идеи не реализованы» — обзор по типу и статусу.
- Не использовать для: одной записи (`docs read`), планирования
  (`todoc-plan`), смены статуса (`todoc-transitions`).

## Procedure

1. Один обзор метаданных, без чтения тел:

   ```bash
   todoc docs list --root demo --type bug-report --status open \
     --fields id,path,title,status --limit 1000
   ```

   Для нескольких типов: `--type 'bug-report|idea'`; для нескольких статусов:
   `--status 'open|triaged|in_progress'`. Проверь `data.meta.complete`,
   `truncated`, `next_cursor` и дочитай страницы, если нужно.
2. Разделяй источники. `docs list` без `--origin` включает JSON-зеркала
   `records/documents/`: `--origin document` оставляет только md,
   `--status-missing` возвращает ровно зеркала. В ответе подписывай, что считал.
3. Неизвестный статус/тип не считай пустым ответом: сверь имя с
   `todoc types list --root demo` и `docs list --type <t> --filter-fields`.
4. Сгруппируй результат по `severity`/`agent_impact`, если пользователь просит
   приоритет: `--attr-severity major`, `--attr-agent_impact friction`.
5. Тела читай только для отобранных пунктов: `docs read --id … --section
   "Сводка" --budget 1500`.
6. Не меняй статусы в рамках обзора. Закрытие — только по явной фразе
   пользователя, через `todoc-transitions`.

## Pitfalls

- `records list --type bug-report` даёт `query.namespace_mismatch`
  (BUG-020 исправлен), а не пустой `ok`: для документов используй `docs list`.
- `docs search` отдаёт `status`/`doc_type`, но для обзора по статусу используй
  `docs list` (пагинация и `--origin`).
- Не считай технический `status: ok` из `docs tree` жизненным статусом
  документа.
- Не агрегируй статусы shell-циклом через обёртку Windows→WSL: argv молча
  теряется (BUG-028). Один `docs list` дешевле и безопаснее.
- Один и тот же вопрос не перепроверяй повторным обходом: для read-only
  достаточно `complete`/`truncated`/`next_cursor`.

## Verification

- Число открытых в ответе совпадает с `data.meta.total` вызова `docs list`
  с тем же фильтром; источник каждого числа назван.
- Для каждого упомянутого пункта есть `path`/`id`, открываемый `docs read`.
