---
id: doc:bugs/bug-069-no-plans-ideas-implementation-overview.md
title: "BUG-069: нет обзора планов и идей с признаком реализации — статусы типов несравнимы, after-plan без status"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
tags: [bugs, bug-report, plans, overview]
bug_id: BUG-069
status: open
severity: minor
agent_impact: [friction, token_overrun]
tokens_extra_est: 120000
component: cli
found: 2026-11-28
tags: [bugs, bug-report, cli, plan, idea, status, overview, portfolio]
---

# BUG-069: нет обзора планов и идей с признаком реализации — статусы типов несравнимы, after-plan без status

| Поле | Значение |
|---|---|
| Bug ID | BUG-069 |
| Компонент | cli |
| Обнаружено | 2026-11-28 — запрос пользователя «какие планы и идеи не реализованы, дай список» |
| Окружение | todoc 0.1.0, Python 3.14, WSL Ubuntu, `env PYTHONPATH=src python3 -m todoc` |

## Сводка

Запрос «что из планов и идей не реализовано» не решается ни одной командой: `docs list` фильтрует по одному `--type`, статусы трёх типов несравнимы (`plan: active|done|superseded`, `idea: captured|planned|done`, у `after-plan` поля `status` нет вовсе), а отрицательного фильтра (`--status-not`) не существует. Приходится перебирать типы, читать шапки, сверять с кодом и вручную доопределять «реализовано/нет».

## Шаги воспроизведения

1. `todoc docs list --root demo --type plan --origin document --fields id,path,title,status --limit 1000` → 12 планов, статусы `active|done|superseded`.
2. `todoc docs list --root demo --type idea --origin document --fields id,path,title,status --limit 1000` → 25 идей, статусы `captured|planned|done`.
3. `todoc docs list --root demo --type after-plan --origin document --fields id,path,title,status --limit 1000` → 6 after-планов, у всех `"status": null`.
4. `todoc docs list --help` → есть `--status` и `--status-missing`, отрицания (`--status-not`/`--not-status`) нет.
5. `todoc plan --help` → `usage.error: No such command 'plan'.`
6. `todoc types list --root demo | wc -c` → `30306` байт, потому что имена типов для шага 1 искались полным дампом каталога.

## Ожидаемое поведение

1. Один вызов даёт плоский обзор «тип + путь + статус» по нескольким типам. Механизм уже есть: `docs list --type` принимает альтернативы через `|` — `docs list --root demo --type 'plan|idea|after-plan' --origin document --fields id,doc_type,status --limit 1000` возвращает все 43 документа за один вызов (8 735 байт). Но ни `AGENTS.md` («Быстрая шпаргалка»), ни `guidance` этот синтаксис не показывают; в шпаргалке есть только пример с одним `--type bug-report`.
2. Каждый тип, участвующий в обзоре «сделано/не сделано», имеет поле `status` и `allowed_statuses`. `after-plan` его лишён, поэтому выпадает из любого статус-фильтра.
3. Есть способ выразить «всё, кроме done/fixed» (`--status-not` или `--status '!done'`), иначе «не реализовано» собирается только перебором.
4. Для волнового портфеля существует `todoc plan portfolio` — он уже спроектирован (Задача 3 плана `bmad-wave-planning-skills`, идея `wave-planning-cli-helpers`) и является штатным ответом на этот запрос.

## Фактическое поведение

1. Обзор собирается только серией вызовов: 2 `docs list` по планам/идеям + 1 по after-plan + 1 `docs list --within plan` (дублирующий) + 2 `ls` по папкам.
2. `after-plan` не имеет `status`, поэтому «не реализован» для шести AFTER-планов приходится выводить из самого факта отсутствия статуса — машинно это не фильтруется.
3. Имена типов добывались полным `types list` (30 306 байт), хотя нужен был `types list --kind doc_type --fields type_id`; подсказки об этом в маршруте нет.
4. `todoc plan` отсутствует, хотя план `bmad-wave-planning-skills` в статусе `active` описывает `plan portfolio`/`plan bind` как штатную механику.
5. Итог: чтобы ответить на один вопрос, агент сделал ~30 вызовов, из них 10 — дампы `--help` (проверка наличия `plan`, `tags`, `stale anchor`, `docs move`, `folderize`, `--dir-type`), и израсходовал ~124 тыс. токенов контекста.

## Доказательства

```
$ todoc docs list --root demo --type 'plan|idea|after-plan' --origin document --fields id,doc_type,status --limit 1000 > /tmp/x.json
$ wc -c < /tmp/x.json
8735
```

```
$ todoc types list --root demo | wc -c
30306
$ todoc types list --root demo --kind doc_type | wc -c
11486
```

Статусы (из `docs list`):
- `plan` (12): `bmad-wave-planning-skills` — `active`; `open-bug-backlog-closure` — `active`; `теги-документов…` — `active`; `metadata-overview-and-harness-efficiency` — `superseded`; остальные 8 — `done`.
- `idea` (25): 15 — `captured`, 2 — `planned` (`cli-model-guidance-and-hint-catalog`, `wave-planning-cli-helpers`), 7 — `done`, 1 — без статуса (`interop-exports`).
- `after-plan` (6): `status: null` у всех шести (`mcp-adapter`, `memory-llm-wiki`, `plugins-formats-import`, `search-embeddings-vector`, `sync-collab-export`, `web-ui`).

```
$ todoc plan --help
{"ok": false, ... "code": "usage.error", "message": "No such command 'plan'."}
```

## Воздействие

Сценарий повторяемый: любой вопрос «что не сделано / что дальше» упирается в тот же перебор. Цена эпизода 2026-11-28: 30 вызовов, из них 6 листингов, 3 чтения шапок (см. BUG-068), 6 повторных чтений секции, 10 `--help`-дампов и 2 `grep` по `src/`. Прямой путь без CLI — 3 `grep -l '^status:' demo/{plan,ideas}/**/*.md` и один `sed` по шапкам, то есть единицы тысяч токенов. Перерасход ≈ 120 тыс. токенов (`tokens_extra_est: 120000`). Severity `minor`: данные не искажаются, но ответ на простой вопрос стоит как полный аудит.

## Предложение по исправлению

1. `demo/.todoc/doc_types/after-plan/type.json`: добавить `status` + `allowed_statuses` (`active|done|superseded`), чтобы AFTER-планы участвовали в обзорах; миграция шести файлов — через `todoc sync`.
2. `docs list`: добавить отрицательный фильтр (`--status-not`/`--not-status`) и поддержать его в `--status` через `!`; обновить справку.
3. Документация и guidance: в `AGENTS.md` («Быстрая шпаргалка») и в подсказку `docs.list.type_alternatives` добавить пример `--type 'plan|idea|after-plan'`; в guidance для `types list` — совет `--kind doc_type --fields type_id`.
4. Реализовать Задачу 3 плана `bmad-wave-planning-skills` (`todoc plan portfolio`, `todoc plan bind`) — это и есть штатный ответ на «что не реализовано»; до неё в guidance `docs.list` давать `next_actions` с готовым argv трёхтипового обзора.
5. Проверка: один вызов возвращает 43 документа со статусами; `validate --root demo --all` = 0; контрактный тест в `tests/cli/test_unified_docs.py`.

## Заметки

- Поиск перед созданием (2026-11-28): полный инвентарь `docs list --root demo --type bug-report --origin document --limit 1000` (68 репортов). Прямых дублей нет; смежные: BUG-022 (обзорная выборка по типу — `fixed`), BUG-057 (обзор открытых багов — `fixed`), BUG-060 (`--status` с `|` — `fixed`), BUG-058 (маршрутизация инструкций к обзору статусов — `open`, другое корневое место: тексты инструкций, не модель статусов).
- Связанные документы: план `plan/bmad-wave-planning-skills.md` (Задача 3), идея `ideas/wave-planning-cli-helpers.md`, идея `ideas/type-naming-and-state-dir.md` (слой `state` как ответ «что реально работает»).
- Связанный репорт: BUG-068 (стоимость чтения шапок) — вторая половина перерасхода того же эпизода.
- Причина, по которой `after-plan` без статуса не поймана валидацией: `status` для типа необязателен, `allowed_statuses` не задан — предлагается закрыть вместе с п.1 фикса.
