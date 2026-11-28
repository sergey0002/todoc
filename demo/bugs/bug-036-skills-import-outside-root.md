---
id: doc:bugs/bug-036-skills-import-outside-root.md
title: "BUG-036: skills import --into выходит за пределы DATA_ROOT"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-28
bug_id: BUG-036
status: open
severity: critical
agent_impact: none
component: cli
found: 2026-11-28
tags: [bugs, bug-report, cli, skills, security, containment]
---

# BUG-036: skills import --into выходит за пределы DATA_ROOT

| Поле | Значение |
|---|---|
| Bug ID | BUG-036 |
| Компонент | cli (`skills import`, `--into` / `--vault`) |
| Обнаружено | 2026-11-28 — аудит containment путей записи скилов |
| Окружение | todoc 0.1.0 (5e86eb7 + рабочее дерево), Python 3.14.3, Windows 11 + WSL2 Ubuntu |

## Сводка

`todoc skills import --into "../../escaped"` копирует папку скила за пределы
`DATA_ROOT`: `vault_root / section / folder.name` не нормализуется и не
проверяется на containment. Команда сообщает `ok: true` и создаёт файлы
снаружи корня; `--vault` имеет ту же проблему.

## Шаги воспроизведения

1. `todoc init --root "$KB" --dataset-id audit-ds`
2. Подготовить источник `$SRC/SKILL.md` с валидным front matter (`name`, `description`).
3. `todoc skills import --root "$KB" --src "$SRC" --into "../../escaped" --output json`
4. Проверить `$KB/../../escaped/<имя>/SKILL.md` — файл создан вне корня.

Windows-путь, на котором воспроизведено:
`C:\Users\NewUser\AppData\Local\Temp\kilo\todoc-audit` (корень),
`C:\Users\NewUser\AppData\Local\Temp\kilo\escaped\src-skill\SKILL.md` (снаружи).

## Ожидаемое поведение

`--into` — раздел vault внутри `DATA_ROOT`; `--vault` — папка внутри
`DATA_ROOT`. После `resolve()` результат обязан удовлетворять
`is_within_root(root, dest)`. `..`, абсолютные пути и симлинк-выходы должны
отклоняться (`skills.import_outside_root` / `access.outside_data_root`) до
`shutil.copytree`.

## Фактическое поведение

- `vault_root = (ctx.root / vault).resolve()` — `vault` может быть `../..`;
  `src/todoc/cli.py:548-549`.
- `dest = vault_root / section / folder.name` — `section` не проверяется;
  `src/todoc/cli.py:578`.
- `shutil.copytree(folder, dest)` создаёт дерево по этому пути;
  `src/todoc/cli.py:582-583`.
- В ответе путь печатается как `skills/../../escaped/src-skill`, то есть
  выход виден в данных, но не блокируется.

## Доказательства

```
$ todoc skills import --root "$KB" --src "$SRC" --into "../../escaped" --output json
{
  "schema_version": 1,
  "ok": true,
  "data": {
    "imported": [
      {
        "name": "src-skill",
        "path": "skills/../../escaped/src-skill"
      }
    ],
    ...
  }
}

$ test -f "$KB/../../escaped/src-skill/SKILL.md" && echo exists
exists
```

Код: `src/todoc/cli.py:548-549` (`vault_root`), `578-583` (`dest` + `copytree`).

## Воздействие

- `critical`: произвольная запись дерева файлов вне датасета (содержимое
  источника — данные, которые могут быть недоверенными). Нет проверки,
  что путь остаётся в корне; ошибка видна только по косой строке `path`.
- Агент, импортирующий чужой пакет, может создать файлы в домашнем каталоге
  или в рабочем репозитории, не заметив этого.

## Предложение по исправлению

1. Резолвить `vault_root` и `dest`, проверять `is_within_root(ctx.root, dest)`;
   отклонять `section`/`vault` с `..`, абсолютными путями и выходами через симлинки.
2. Нормализовать `path` в ответе к POSIX и показывать только корень-относительный путь.
3. Тест: `--into ../../escaped` → exit 4, снаружи ничего не создано;
   `--into coding/review` работает как раньше.

## Заметки

Поиск перед созданием (2026-11-28): `docs search --type bug-report --query
"skills import into"` — совпадений по containment нет (BUG-027 — падение
`skills tree`, BUG-029 — два хранилища). Связанные: BUG-034 (change apply),
BUG-035 (history).
