---
id: doc:bugs/bug-060-status-filter-pipe-rejected.md
title: "BUG-060: docs list --status не принимает альтернативы через |, хотя примеры справки и скила используют этот синтаксис"
doc_type: bug-report
lang: ru
bug_id: BUG-060
status: fixed
severity: minor
agent_impact: [friction, token_overrun]
tokens_extra_est: 1200
component: cli
found: 2026-11-28
created: 2026-11-28
updated: 2026-11-28
tags: [bugs, bug-report, cli, docs-list, filters, status, documentation]
---

# BUG-060: docs list --status не принимает альтернативы через `|`, хотя примеры справки и скила используют этот синтаксис

| Поле | Значение |
|---|---|
| Bug ID | BUG-060 |
| Компонент | cli (`docs list --status`), docs (`03-cli-reference.md`, скил `todoc-docs`) |
| Обнаружено | 2026-11-28 — составление плана закрытия бэклога багов |
| Окружение | todoc 0.1.0, Python 3.14.4, WSL2 Ubuntu |

## Сводка

`--type` и `--attr-status` принимают альтернативы через `|`, а `--status` — нет:
`docs list --type idea --status 'captured|planned'` завершается `docs.unknown_status`
с сообщением `Unknown document statuses: captured|planned`. При этом именно такая
форма записана в актуальной справке (`docs/state/03-cli-reference.md`) и в
примерах скила `docs/todoc-docs`, а `docs list --help` для `--status` не
описывает синтаксис вообще. Агент копирует пример из справки и получает ошибку.

## Шаги воспроизведения

1. `todoc docs list --root demo --type idea --status 'captured|planned' --limit 2`
   → `ok: false`, `docs.unknown_status`, `Unknown document statuses: captured|planned`.
2. `todoc docs list --root demo --type idea --attr-status 'captured|planned' --limit 2`
   → `ok: true`, `total: 16` (pipe работает для атрибута).
3. `todoc docs list --root demo --type 'bug-report|idea' --limit 2` → `ok: true`
   (pipe работает для типа).
4. `todoc docs list --root demo --type idea --status captured --status planned --limit 2`
   → `ok: true`, `total: 16` (работает только повтор флага).
5. `todoc docs list --help` → у `--status` нет описания синтаксиса, у `--type`
   есть «separate alternatives by |».

## Ожидаемое поведение

Один из двух вариантов, одинаково согласованный с документацией:

- `--status` принимает `a|b` так же, как `--type` и `--attr-status` (предпочтительно:
  один синтаксис альтернатив во всех фильтрах); пример из справки работает как
  записан.
- Либо `--status` документирует только повтор флага, а примеры в
  `docs/state/03-cli-reference.md` и скилах переписаны на
  `--status captured --status planned`; `--help` описывает синтаксис.

## Фактическое поведение

Pipe отклоняется диагностикой, справка и примеры обещают обратное, `--help`
молчит о синтаксисе.

## Доказательства

```
$ todoc docs list --root demo --type idea --status 'captured|planned' --limit 2
"ok": false
"code": "docs.unknown_status", "message": "Unknown document statuses: captured|planned."

$ todoc docs list --root demo --type idea --attr-status 'captured|planned' --limit 2
"ok": true, "total": 16

$ todoc docs list --root demo --type idea --status captured --status planned --limit 2
"ok": true, "total": 16

# docs/state/03-cli-reference.md:25
todoc --root demo docs list --type idea --status 'captured|planned' --status-missing
```

## Воздействие

Каждый обзор по нескольким статусам: одна лишняя итерация (ошибка → повтор
флагами) и потеря доверия к примерам справки. Оценка перерасхода ≈ 1200 токенов;
частота — каждый обзор бэклога и каждая сверка статусов.

## Предложение по исправлению

- В `src/todoc/cli.py` для `docs list --status` разворачивать значения по `|`
  (как у `--type`), обновить `--help` («separate alternatives by |»).
- Тест: `docs list --type idea --status 'captured|planned'` = `docs list --type idea
  --status captured --status planned` (одинаковый `total`).
- Синхронизировать примеры: `docs/state/03-cli-reference.md`,
  `demo/references/state/03-cli-reference.md`, скил `docs/todoc-docs`.
- Проверка: `validate --all` = 0, `linkcheck` = 0, pytest зелёный.

## Заметки

Поиск перед созданием (2026-11-28): `--type bug-report --query "status pipe
альтернативы docs list"` — точного дубликата нет; найдены BUG-057 (обзор),
BUG-016 (фильтры не документированы), BUG-055 (`--type` в search). Связанные:
BUG-013 (контракты фильтров), BUG-016. В плане
`plan/open-bug-backlog-closure.md` — задача 3.10.

- 2026-11-28: `fixed` — коммит `9895249`. `docs list --status` разбивает значения по `|` до валидации и фильтрации, поэтому документированная форма `a|b` эквивалентна повтору флага; неизвестный статус в списке даёт `docs.unknown_status`. Проверка: `tools/bug_acceptance.py --only BUG-060` → `fixed` (`pipe total` = `repeated total`). Тест: `tests/cli/test_unified_docs.py::test_docs_list_status_accepts_pipe_and_repeated_flags`.
