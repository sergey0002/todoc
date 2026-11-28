---
id: doc:bugs/bug-046-fix-applies-wrong-occurrence.md
title: "BUG-046: fix --apply заменяет первое вхождение цели в тексте, а не сломанную ссылку"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
bug_id: BUG-046
status: fixed
severity: major
agent_impact: friction
tokens_extra_est: 700
component: engine
found: 2026-11-28
tags: [bugs, bug-report, engine, fix, links, data-integrity]
---

# BUG-046: fix --apply заменяет первое вхождение цели в тексте, а не сломанную ссылку

| Поле | Значение |
|---|---|
| Bug ID | BUG-046 |
| Компонент | engine (`fix --apply`, `application/write.py::apply_fix`) |
| Обнаружено | 2026-11-28 — аудит автофиксов ссылок |
| Окружение | todoc 0.1.0 (5e86eb7 + рабочее дерево), Python 3.14.3, Windows 11 + WSL2 Ubuntu |

## Сводка

`todoc fix --apply` заменяет **первое вхождение** строки-цели в файле
(`text.replace(old_target, new_target, 1)`), а не ссылку, на которую указала
диагностика. Если тот же текст встречается в прозе раньше ссылки, правится
проза, а сломанная ссылка остаётся; `validate` после «исправления» снова
показывает ту же диагностику.

## Шаги воспроизведения

В отдельном временном датасете:

1. `todoc init --root "$KB" --dataset-id fix-ds`
2. Создать `runbook.md` (существующая цель) и `source.md`:

   ```markdown
   # Source

   В тексте уже упомянут runbok.md как пример опечатки.

   Ссылка: [runbook](runbok.md).
   ```

3. `todoc validate --root "$KB" --all --output json` → диагностика
   `markdown.link.target_missing`, `location.line: 5`, `suggested_fixes[0].replacement: runbook.md`.
4. `todoc fix --root "$KB" --diagnostic <id> --apply --output json` → `applied: true`.
5. Прочитать `source.md` и повторить `validate`.

## Ожидаемое поведение

Фикс должен менять именно найденную ссылку — по `location.line`/`column`/
`end_column` из диагностики (или по точному span ссылки), а не первое
вхождение подстроки. После `fix --apply` диагностика исчезает, проза не
меняется.

## Фактическое поведение

- `apply_fix` делает `new_text = text.replace(old_target, new_target, 1)`
  (`src/todoc/application/write.py:155-157`), игнорируя `location` диагностики.
- В примере `runbok.md` встречается в прозе (строка 3) и в ссылке (строка 5);
  правится строка 3, ссылка на строке 5 остаётся `runbok.md`.
- `validate` после фикса снова возвращает `markdown.link.target_missing` на
  строке 5 — «исправление» не исправило, но изменило текст.

## Доказательства

```
# source.md до
# Source

В тексте уже упомянут runbok.md как пример опечатки.

Ссылка: [runbook](runbok.md).

$ todoc validate --root "$KB" --all --output json
  "code": "markdown.link.target_missing",
  "location": { "line": 5, "column": 9, ... },
  "evidence": "[runbook](runbok.md)",
  "suggested_fixes": [{ "replacement": "runbook.md", ... }]

$ todoc fix --root "$KB" --diagnostic diag_... --apply --output json
  "ok": true,
  "applied": true

# source.md после
# Source

В тексте уже упомянут runbook.md как пример опечатки.

Ссылка: [runbook](runbok.md).        # ссылка НЕ исправлена

$ todoc validate --root "$KB" --all --output json
  "ok": false,
  "code": "markdown.link.target_missing",
  "location": { "line": 5, ... },
  "evidence": "[runbook](runbok.md)",
```

Код: `src/todoc/application/write.py:145-164` (`apply_fix`), диагностика с
`location` — `src/todoc/application/validator.py:127-137`.

## Воздействие

- `major`: автофикс портит не тот участок текста и не устраняет дефект;
  повторный `validate` падает, агент вынужден откатывать и править вручную.
- Риск тихой порчи данных: прозаическое упоминание заменяется, а ссылка
  остаётся битой; в большом документе это заметно не сразу.
- `friction`: цикл validate → fix → validate не сходится; 1–2 лишних вызова
  плюс ручная правка ≈ 700 токенов.

## Предложение по исправлению

1. Передавать в `apply_fix` `location` (line/column/end_column) и заменять
   только span ссылки на этой строке; проверять, что по этому span
   действительно `old_target`.
2. Если span не найден — `fix.target_not_found` без записи файла (не делать
   fallback на `replace` по всему тексту).
3. Тест: два вхождения цели, правится только ссылка на указанной строке;
   `validate` после `fix --apply` — 0 диагностик.

## Заметки

Поиск перед созданием (2026-11-28): `docs search --type bug-report --query
"fix apply link"` — совпадений по корневой причине нет (BUG-007 — linkcheck,
BUG-013 — id). Связанные: BUG-007, BUG-004 (docs edit).

- 2026-11-28: `fixed` — коммит `7d32813` (поведение уже было в рабочем дереве). Автофикс правит ссылку на диагностической строке, совпадающий текст в прозе не меняется, повторная валидация чистая. Проверка: `tools/bug_acceptance.py --only BUG-046` → `fixed`. Тест: `tests/cli/test_cli.py`.
