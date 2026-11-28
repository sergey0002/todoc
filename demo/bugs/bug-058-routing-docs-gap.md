---
id: doc:bugs/bug-058-routing-docs-gap.md
title: "BUG-058: инструкции и маршрутизация скилов не выводят на обзор статусов — AGENTS.md, описания скилов и CLI расходятся"
doc_type: bug-report
lang: ru
bug_id: BUG-058
status: open
severity: minor
agent_impact: [friction, token_overrun]
tokens_extra_est: 9000
component: docs
found: 2026-11-28
created: 2026-11-28
updated: 2026-11-28
tags: [bugs, bug-report, docs, skills, agents-md, routing, discoverability, cli]
---

# BUG-058: инструкции и маршрутизация скилов не выводят на обзор статусов — AGENTS.md, описания скилов и CLI расходятся

| Поле | Значение |
|---|---|
| Bug ID | BUG-058 |
| Компонент | docs (`AGENTS.md`, `SKILL.md`, skills vault, `demo/HOME.md`), cli (help/guidance) |
| Обнаружено | 2026-11-28 — вопрос «какие багфиксы не закрыты» |
| Окружение | todoc 0.1.0, Python 3.14.4, Windows 11 + WSL2 Ubuntu, Kilo CLI |

## Сводка

Правильная команда обзора существует (`docs list --type <t> --status <s>`,
появилась по BUG-022) и описана в двух местах — `SKILL.md:21-23` и
`demo/skills/docs/todoc-docs/SKILL.md:21`, — но ни один из этих маршрутов не
сработал: диспетчер-скил `todoc` не смонтирован в платформу (`.kilo/skills`
отсутствует), описание `todoc-docs` не упоминает обзор статусов, а
`AGENTS.md` в шпаргалке `docs list` не показывает и в подводном камне про
`records list` не даёт альтернативы. В итоге агент пошёл по
`records list` → `docs search` → ручной `grep`, хотя ответ стоил одного вызова.

## Шаги воспроизведения

1. Вопрос пользователя: «какие багфиксы не закрыты».
2. `todoc records list --root demo --type bug-report` → `ok: true`, `total: 0`,
   `items: []`, `guidance.items: []` (BUG-020). Ничего не подсказывает `docs list`.
3. `todoc docs search --root demo --type bug-report --limit 50` → `total: 79`,
   `returned: 50`, `truncated: true`; в элементах только `id`, `path`, `title` —
   `status` нет, поэтому вопрос не решается.
4. `todoc docs search --root demo --type bug-report --fields path,status` →
   `ok: false`, `fields.unknown: status`; `next_actions` ведёт только на
   `docs search --help`, хотя `guidance` уже знает про `docs list --fields-help`.
5. `todoc docs list --root demo --type bug-report --status open --limit 1000` →
   `total: 48` (правильный ответ, но команда найдена только после `docs --help`).
6. `todoc docs list --root demo --type bug-report --limit 1000 --fields path` →
   `total: 79`; 18 путей — `records/documents/*.json` (JSON-зеркала тех же
   репортов), `--status-missing` = ровно 18.
7. `todoc skills attach --root demo --to .kilo/skills --preview` → план
   устанавливает ровно 1 файл `SKILL.md` (работает, но никем не запущен).
8. Попытка агрегировать статусы циклом через обёртку
   `wsl -d Ubuntu -- bash -lc '…'` провалилась молча (см. «Доказательства»):
   `printf` вернул `MISSINGtn` вместо строки, `sed`/`awk` получили искажённый
   скрипт. Пришлось считать вручную `grep -H "^status:" demo/bugs/*.md`.

## Ожидаемое поведение

1. Агент, задавший вопрос «что не закрыто», получает маршрут к `docs list`
   хотя бы из одного источника, который он реально читает:
   `AGENTS.md` (шпаргалка), `SKILL.md`/скил-диспетчер или `guidance` CLI.
2. `records list` по `doc_type` не выглядит как «данных нет»: пустой успех
   заменён диагностикой с готовым argv `docs list --type … --status …`
   (BUG-020/021).
3. `docs search` либо отдаёт `status`/`doc_type` в проекции, либо честно
   говорит, что для статусов есть `docs list` (BUG-022 не закрыт для search).
4. Неизвестные `--type`/`--status` в `docs list` дают диагностику, а не
   `ok: true, total: 0` (BUG-055 покрывает только `docs search`).
5. Обзор по типу не смешивает md-документы и JSON-зеркала без пометки:
   нужен `origin`/`source` или фильтр, иначе «сколько репортов» имеет
   три разных ответа (79 / 61 / 48).
6. Внешняя обёртка Windows→WSL не теряет аргументы молча: либо argv доходит
   целиком, либо команда падает (BUG-028).

## Фактическое поведение

- **Диспетчер не смонтирован.** `.kilo/kilo.jsonc` содержит только
  `snapshot: false`; каталога `.kilo/skills` нет. В списке доступных скилов
  платформы — только сторонние `graphify` и `kilo-config`; `todoc`-скила нет.
  `AGENTS.md:156-161` предписывает `todoc skills attach --to <каталог скилов>`,
  но для этого чекаута команда ни разу не выполнялась.
- **Описание скила не матчит задачу.** `demo/skills/docs/todoc-docs/SKILL.md:8`
  обещает «bounded search/read»; про обзор по типу/статусу (тело, строка 21)
  в описании нет ни слова, поэтому при выборе по описанию скил не находится.
  Отдельного скила «бэклог/триаж/что открыто» в vault нет.
- **AGENTS.md не содержит маршрута.** Шпаргалка (`AGENTS.md:163-215`) даёт
  `docs search`, `docs read`, `docs tree`, `records list`, `types`, `sync`,
  `validate` — `docs list` отсутствует. Подводный камень `AGENTS.md:210-212`
  констатирует «`records list --type bug-report` вернёт пустой `ok` — это
  BUG-020, не считай результат «нет данных»», но не говорит, чем заменить.
- **Справка CLI не подсказывает переход.** `todoc --help` перечисляет 30
  команд без карты «намерение → команда»; `docs search --help` упоминает
  только generic `--attr-NAME`, а `status` недоступен в `--fields`.
- **Две копии диспетчера разошлись.** `SKILL.md` (корень) содержит абзац про
  `docs list` (строка 23), а `demo/skill/SKILL.md` — старая копия без него
  (разные sha256); какая из них попадёт агенту, зависит от источника attach.
- **Шпаргалка скила устарела.** `demo/skills/docs/todoc-docs/references/query-cheatsheet.md`
  имеет `doc_type: unknown`, не содержит строки про `docs list` и советует
  `records list --type document` — ровно тот неймспейс, который даёт пустой
  успех.
- **Обёртка теряет аргументы молча.** Форма с внешними одинарными кавычками и
  внутренними двойными (естественная для bash) обрезает всё после первого
  значения с пробелом и снимает `\n`; ошибки нет, результат выглядит
  правдоподобно. В одном случае это привело к плану `docs new` с путём
  `inbox/bug-058.md` и заголовком `BUG-058:` вместо заданных — файл не создан
  только потому, что вместе с `--path` потерялся и `--apply`.

## Доказательства

```
$ cat .kilo/kilo.jsonc
{ "$schema": "https://app.kilo.ai/config.json", "snapshot": false }
$ ls .kilo
kilo.jsonc  update-from-git.ps1  update-from-git.sh  .gitignore

$ todoc skills attach --root demo --to .kilo/skills --preview
"path": "/home/newuser/projects/todoc/.kilo/skills/todoc",
"files": 1, "applied": false        # маршрут рабочий, но не применён

$ todoc records list --root demo --type bug-report
"total": 0, "returned": 0, "items": []   # diagnostics: [], guidance.items: []

$ todoc docs search --root demo --type bug-report --limit 50
"total": 79, "returned": 50, "truncated": true
# item keys: id, path, title — status отсутствует

$ todoc docs search --root demo --type bug-report --fields path,status
"ok": false, diagnostics: [{ "code": "fields.unknown", "message": "Unknown fields: status" }]
next_actions: [todoc docs search --help]
guidance: "Для списка документов доступен docs list --fields-help."

$ todoc docs list --root demo --type bug-report --limit 1000 --fields path
"total": 79      # 61 md + 18 JSON-зеркал records/documents/*.json
$ todoc docs list --root demo --type bug-report --status-missing --limit 1000
"total": 18
$ todoc docs list --root demo --type bug-report --status open --limit 1000
"total": 48
$ grep -l "^status: open" demo/bugs/*.md | wc -l
48
$ grep -l "^doc_type: bug-report" demo/bugs/*.md | wc -l
61

$ todoc docs list --root demo --type nope --limit 3
"ok": true, "total": 0     # и с --status zzz то же самое
```

Обрыв аргументов в обёртке (PowerShell → `wsl -d Ubuntu -- bash -lc`):

```
# внешние одинарные кавычки, внутренние двойные — хвост потерян, \n съеден
$ wsl -d Ubuntu -- bash -lc 'printf "[%s]\n" "a b" --limit 5 --fields path,title'
[a]n

# форма из AGENTS.md (внешние двойные, внутренние одинарные) — всё на месте
$ wsl -d Ubuntu -- bash -lc "printf '[%s]' 'a b' --limit 5 --fields path,title"
[a b][--limit][5][--fields][path,title]

# та же потеря на мутирующей команде: --path/--apply/хвост заголовка исчезли
$ todoc docs new --root demo --type bug-report --title "BUG-058: инструкции …" --path bugs/bug-058-routing-docs-gap.md --apply
target_path: "inbox/bug-058.md", title: "BUG-058:", applied: false
```

Источники ожидания: `AGENTS.md:163-215` (шпаргалка), `AGENTS.md:156-161`
(подключение скилов), `SKILL.md:21-23` (`docs list` для обзора),
`demo/notes/agent-contract.md` (скилы — одна точка входа), приёмка BUG-022
(`60b9f29`, `9c255fd`).

## Воздействие

Вопрос «какие багфиксы не закрыты» — типовой обзор бэклога, он возникает
регулярно. В этом эпизоде агент сделал ~20 вызовов CLI (2 списка, 3 справки,
2 неудачные shell-агрегации, 2 контрольных запроса, 2 обхода через временные
скрипты) плюс ручной `grep`; правильная команда найдена на 5-м шаге и не
через документацию, а через `docs --help`. Перерасход ≈ 9000 токенов; прямой
путь — один `docs list --type bug-report --status open` (48 строк, ~1.2k
токенов) или, без CLI, один `grep -H '^status:' demo/bugs/*.md`.

Отдельный риск — неверный ответ: для «сколько репортов» есть три числа
(79 с зеркалами, 61 md-файлов, 48 открытых), и ни одно не подписано.
Ещё один риск — молчаливая потеря аргументов: та же форма команды, что
привела к плану `inbox/bug-058.md`, при живом `--apply` создала бы документ
не туда и с обрезанным заголовком.

Severity `minor`: данные не портятся (в эпизоде — по счастливой случайности),
но маршрут к базовой операции отсутствует в трёх местах сразу.

## Предложение по исправлению

Приоритет P0 (дешёво, снимает основной обрыв):

1. Смонтировать диспетчер и зафиксировать это в setup:
   `todoc skills attach --root demo --to .kilo/skills --apply`, файл
   `.kilo/skills/todoc/SKILL.md` — в репозиторий (или в скрипт
   `.kilo/update-from-git.sh`). Проверка: скил `todoc` виден платформе.
2. `AGENTS.md`, шпаргалка: добавить строку
   `docs list --type bug-report --status open --fields id,path,title,status`
   и в подводном камне BUG-020 дописать «вместо `records list` используй
   `docs list --type … --status …`».
3. `demo/skills/docs/todoc-docs/SKILL.md`: в `description` добавить
   «список документов по типу/статусу (`docs list`)», а не только
   «bounded search/read». Проверка: `skills tree` ищется по «статус».
4. Новый скил `process/todoc-backlog` (или раздел в `todoc-docs`): обзор
   открытых баг-репортов/идей, правило счёта (только md, `--status-missing`
   отдельно), ссылка на BUG-057/058.

Приоритет P1 (контракт CLI):

5. `docs search`: разрешить `status`/`doc_type` в `--fields` или включать их
   при `--type` (остаток BUG-022); в `next_actions` ошибки `fields.unknown`
   добавить `docs list --fields-help`.
6. `docs list`: поле `origin` (`document` | `record`) и режим без JSON-зеркал
   (или `--origin document`); отсутствующий статус — `null`, а не пропуск.
7. Неизвестные `--type`/`--status` в `docs list` → диагностика +
   `suggested_fixes` (расширить BUG-055 на `docs list`).
8. `records list` по `doc_type` → диагностика с argv `docs list …` (BUG-020/021).

Приоритет P2 (гигиена документации):

9. Удалить/перегенерировать устаревшую копию `demo/skill/SKILL.md` из
   `src/todoc/data/agent-skill/todoc/SKILL.md` (BUG-029), чтобы копии не
   расходились.
10. `query-cheatsheet.md`: добавить строку `docs list`, убрать
    `records list --type document`, исправить `doc_type: unknown`.
11. `AGENTS.md` правило 2: обратное чтение — после мутаций; для read-only
    достаточно проверить `complete`/`truncated`/`cursor` (иначе каждый обзор
    удваивает вызовы).
12. Обёртка Windows→WSL: либо `tools/todoc-wsl.sh` с готовым argv, либо в
    `AGENTS.md` явно запретить внешние одинарные кавычки и дать probe
    `printf '[%s]' 'a b' --limit 5`, чтобы ловить потерю аргументов до
    мутирующей команды (BUG-028).

## Заметки

Поиск перед созданием (2026-11-28): `docs search --type bug-report --query
"AGENTS.md docs list cheatsheet missing"` и `--query "skill description
routing status overview"` — точного дубликата нет; найдены BUG-029 (два
хранилища скилов), BUG-024 (шум скилов в индексе), BUG-021 (guidance),
BUG-017 (усечение дерева). Связанные: BUG-057 (CLI-обзор), BUG-022
(`docs list` как таковой), BUG-020 (`records list` пустой успех), BUG-013
(ручной grep для резолва), BUG-016 (фильтры не документированы), BUG-028
(обёртка Windows/WSL).

Числа на 2026-11-28 после BUG-057: 61 md-документ `bug-report`, из них 48
`open`, 12 `fixed`, 1 `duplicate`; 18 JSON-зеркал в `demo/records/documents/`
без `status`; `docs list` без фильтра статуса = 79.

### Применено 2026-11-28 (рабочее дерево, до коммита)

- `.kilo/skills/todoc/SKILL.md` смонтирован командой
  `todoc skills attach --root demo --to .kilo/skills --apply` (1 файл).
- `AGENTS.md`: в шпаргалку добавлен `docs list --type … --status … --fields …`;
  подводный камень BUG-020 получил альтернативу; правило 2 ограничено
  мутациями (read-only — `complete`/`truncated`/`cursor`); добавлен запрет
  внешних одинарных кавычек в обёртке и `printf`-пробник.
- `demo/skills/docs/todoc-docs/SKILL.md`: описание упоминает обзор по
  типу/статусу, процедура переведена на прямую правку + `todoc sync`,
  добавлены pitfall-ы про `origin`, `--status-missing` и неизвестные тип/статус.
- Новый скил `process/todoc-backlog`: обзор бэклога одним `docs list`,
  разделение md и JSON-зеркал, правило счёта.
- `references/query-cheatsheet.md`: `doc_type: reference`, добавлены
  `docs list`/`--origin`, убран `records list --type document`.
- `docs/state/07-search-and-read.md` и `03-cli-reference.md` описывают
  `origin`, `status`/`doc_type` в search и диагностики `docs.unknown_*`;
  `docs/state/cli.md` перегенерирован.
- Статус `open` до ревью и коммита.

### Дополнение 2026-11-28 (эпизод «список нереализованных планов и идей»)

- Шпаргалка после правки учит только одному `--type`; альтернативы `--type 'plan|idea|after-plan'` не упомянуты, маршрута «что из планов/идей не реализовано» нет. Цена эпизода: ~30 вызовов, 10 дампов `--help`, `types list` 30 306 байт, ~124 тыс. токенов контекста.
- Разбор вынесен в отдельные репорты: BUG-069 (несравнимые статусы типов, `after-plan` без `status`, нет отрицательного фильтра, нет `todoc plan portfolio`) и BUG-068 (стоимость чтения шапки `docs read`).
- Статус остаётся `open`: правка `AGENTS.md` не покрыла кросс-типовой обзор и отрицательный фильтр статуса.
