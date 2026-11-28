---
title: Preview правки одобряет неисполнимый патч
audit_id: CA-003
bug_id: BUG-049
canonical_path: demo/bugs/bug-049-edit-preview-invalid-ops.md
status: open
severity: major
agent_impact: friction
component: cli
---

# CA-003: Preview правки одобряет неисполнимый патч

## Сводка

`docs edit --preview` проверяет контейнеры JSON, но не выполняет проверку типов и диапазонов операций. Патч со строковым line получает успешный preview, а на apply падает ValueError.

## Шаги воспроизведения

`PYTHONPATH=src python3 .doc/codexaudit/evidence/reproduce.py`, сценарии `invalid_patch_preview` / `invalid_patch_apply`. Сначала CLI создаёт `note.md`. Патч вне DATA_ROOT:

```json
{"ops":[{"line":"not-an-integer","text":"new"}]}
```

Выполнить `todoc --root <temporary-root> docs edit --id doc:note.md --patch-file <patch.json> --preview`, затем ту же команду с `--apply`.

## Ожидаемое поведение

Preview отказывает диагностикой invalid patch до применения. Review-first предполагает проверяемый исполнимый план, а не просто эхо входного JSON.

## Фактическое поведение

Preview: exit 0, `ok:true`, исходные ops. Apply: exit 1, `ValueError("invalid literal for int() with base 10: 'not-an-integer'")`, без конверта. В данном сценарии целевой файл не изменяется: исключение возникает до atomic_write.

## Доказательства

`cli.py:1702–1711` проверяет только object/list/dict и возвращает успешный preview. `write.py:198–203` приводит line к int только при apply. Запись вызывается позднее, `write.py:221–224`.

## Воздействие

Разрешённый review-first шаг даёт ложное подтверждение готовности. Агент делает дополнительный вызов и получает отказ вне контракта; severity major для проверки правок. BUG-014 о нумерации результата и BUG-004 об insert/delete не описывают эту корневую причину.

## Предложение по исправлению

Выделить чистое планирование ops и вызывать его в preview/apply. Проверять line/to/text/op и границы, выдавать патч результата и basis hash. Приёмка: неверные типы, unknown op и выход за диапазон отклоняются уже на preview; валидный preview совпадает с apply при том же hash.

## Заметки

Дедуп 2026-11-28: `edit.invalid_patch`, `apply_edit_ops`; существующие отчёты просмотрены по смыслу. Протокол `.doc/codexaudit/evidence/verification.md`. Фикс не реализован.
