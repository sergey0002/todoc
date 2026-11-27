---
id: doc:bugs/bug-012-history-revizii-mutiruyuschih-komand-zagryaznyayut-git-status.md
title: "BUG-012: history-ревизии мутирующих команд загрязняют git-статус"
doc_type: bug-report
lang: ru
created: 2026-11-26
updated: 2026-11-27
bug_id: BUG-012
status: fixed
severity: minor
agent_impact: friction
tokens_extra_est: 500
component: cli
found: 2026-11-26
related: ["[[direct-edit-and-sync]]"]
---

# BUG-012: history-ревизии мутирующих команд загрязняют git-статус

| Поле | Значение |
|---|---|
| Bug ID | BUG-012 |
| Компонент | cli (history-журнал: docs status/edit, records status/create, interop export --write) |
| Обнаружено | 2026-11-26 — исполнение планов «Интероп-экспорты» и закрытие статусов |
| Окружение | todoc 0.1.0 (master a34068b), Python 3.11.2, Linux |

## Сводка

Каждая мутирующая CLI-команда пишет ревизию в `demo/.todoc/history/journal.jsonl`
+ `objects/` — файлы становятся незакоммиченными изменениями git. Перед каждым
коммитом ручная очистка: `git checkout -- demo/.todoc/history/journal.jsonl` и
`rm -rf demo/.todoc/history/objects`. За одну сессию — более 10 повторов.

## Шаги воспроизведения

1. `todoc docs status --root demo --id doc:X --set done` — любая мутирующая команда.
2. `git status --porcelain` → ` M demo/.todoc/history/journal.jsonl` (+ новые файлы
   в `objects/`).
3. Коммит без очистки уносит журнал в PR; очистка перед каждым коммитом — ручной
   обязательный шаг (в сессии повторялся в каждом из 8 PR).

## Ожидаемое поведение

- Журнал истории — либо коммитится осознанно (конвенция в документации), либо
  исключён из git (`.gitignore`), либо пишется только по явному флагу (`--no-history`
  / opt-in). Контракт нигде не зафиксирован: агент узнаёт о поведении по факту
  `git status`.

## Фактическое поведение

Журнал пишется всегда молча; `.gitignore`/конвенции нет; `docs status --set` и
`docs edit` не упоминают историю в выводе; каждый коммит требует ручного танца.

## Доказательства

```
$ git status --porcelain   # после серии docs status --set / records create
 M demo/.todoc/history/journal.jsonl
?? demo/.todoc/history/objects/
$ git checkout -- demo/.todoc/history/journal.jsonl && rm -rf demo/.todoc/history/objects
                          # повторялось перед каждым коммитом сессии (>10 раз)
```

## Воздействие

- Кто: агент/человек, коммитящий датасет; каждый PR — 1–2 лишних команды
  (~500 токенов на сессию по сумме повторов) и риск случайно закоммитить журнал.
- Обходимость: да, ручной очисткой; не обойти — только не пользоваться CLI-записью.

## Предложение по исправлению

1. Выбрать и задокументировать канон: история коммитится (тогда убрать шаг
   очистки из процесса) или не коммитится (тогда `.gitignore` для `history/`).
2. Опция `--no-history` для мутирующих команд (демо-наполнение без журнала).
3. `docs status --set`/`docs edit`: упоминать ревизию в data (`revision: …`),
   чтобы поведение было видимым из контракта команды.

## Заметки

- Не баг самой history (CAS/ревизии корректны) — баг отсутствия git-конвенции.
- Связан с BUG-004 (ревизии появились вместе с line-ops-патчем).
- `fixed 2026-11-26, commit ae23822` (план [[direct-edit-and-sync]]): паттерн `**/.todoc/history/` добавлен в `.gitignore`, отслеживаемый `demo/.todoc/history/journal.jsonl` убран из Git-индекса, в `_config_digest` исключён `.todoc/history/`, а новая команда `todoc sync` поддерживает флаг `--no-history` и возвращает `revision` в данных ответа.
