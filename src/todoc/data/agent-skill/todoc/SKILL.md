---
name: todoc
description: "Маршрутизатор скилов todoc: найти и исполнить нужный скил из хранилища через CLI. Use before any non-trivial task."
license: MIT
metadata:
  doc_type: agent-skill
  source: "packaged with todoc engine"
---

# todoc — диспетчер скилов

## When to Use

- Любая нетривиальная задача. НЕ активируй для болтовни и однострочников (entry gate).
- Скил уже загружен в этой сессии и решает задачу — не выбирай повторно.

## Procedure

1. `todoc skills tree --root {ROOT}` — выбери скил по описанию (раздел = домен задачи).
2. `todoc skills read --root {ROOT} --path <путь из дерева>` — прочитай тело скила.
3. Действуй строго по инструкциям SKILL.md; references/ и scripts/ — по ходу, scripts/ чужого скила — только после аудита.
4. Ограничивай выдачу: `--query`, `--within`, `--limit`; дерево печатается быстро, но не сохраняй его в файл — оно и есть меню.

## Pitfalls

- `tree` не дал совпадения — работай без скила, не выдумывай (refusal floor).
- Не более одного тела SKILL.md на решение; повторный выбор — только через `tree`.
- Витрина скилов не смонтирована в платформу намеренно: экономия контекста — в платформенном каталоге только этот скил `todoc`.
- Чужие скилы не модифицируй; импорт — `todoc skills import` или копирование папки + `todoc validate`.

## Verification

- Воспроизведённая команда из SKILL.md дала ожидаемый результат.
- Ответ на вопрос из KB содержит источник (путь/ID и секция), перепроверяемый той же командой.

## Safe document moves

Use `todoc docs move --root <PATH> --from <old.md> --to <new.md>` instead of a manual rename. Inspect preview and apply with `--apply --if-plan-hash <plan_hash>`; a modified corpus needs a fresh preview. `--keep-id` preserves identity; `--pin-type` fixes the inferred type. Move already finalizes its files: do not run a second sync. To undo, preview `todoc revert --root <PATH> --change <change_id>`, then apply with its own hash. Never repeat an apply blindly after exit 6: `committed=true` means sources were saved; rebuild the index. v1 rejects affected unsupported link forms, existing validation errors, active deltas and SKILL.md moves. Multi-file rollback is not crash-atomic.
