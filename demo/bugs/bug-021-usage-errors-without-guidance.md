---
id: doc:bugs/bug-021-usage-errors-without-guidance.md
title: "BUG-021: usage-ошибки CLI не содержат suggested_fixes и guidance"
doc_type: bug-report
lang: ru
created: 2026-11-27
updated: 2026-11-28
bug_id: BUG-021
status: fixed
severity: minor
agent_impact: friction
component: cli
found: 2026-11-27
---

# BUG-021: usage-ошибки CLI не содержат suggested_fixes и guidance

| Поле | Значение |
|---|---|
| Bug ID | BUG-021 |
| Компонент | cli (конверт ошибок: `usage.error`, `explain.path_not_found`) |
| Обнаружено | 2026-11-27 — разбор дерева демо, вызов `explain-path` с неверной формой аргумента |
| Окружение | todoc 0.1.0 (master 5e86eb7), Python 3.14.4 (WSL Ubuntu), харнесс — Windows PowerShell 5.1 поверх `\\wsl.localhost` |

## Сводка

Ошибочный вызов CLI возвращает `ok: false` с кодом, но пустой
`suggested_fixes` и `next_actions` из одного общего `todoc --help`. Агент,
который угадал форму аргумента, не получает ни правильного вызова, ни намёка
на базу пути — он вынужден идти в `--help` или в код. Второй случай того же
класса: `explain.path_not_found` при пути с префиксом `DATA_ROOT` — тоже без
подсказки, хотя исправление однозначно (убрать префикс).

## Шаги воспроизведения

1. `todoc explain-path --root demo --path skill/doc-spec-write/SKILL.md`
   → `Error [usage.error]: No such option: --path`, `suggested_fixes: []`,
   `next_actions` — только `todoc --help`.
2. `todoc explain-path --root demo demo/skill/doc-spec-write/SKILL.md`
   → `Error [explain.path_not_found]: Path not found in dataset: demo/skill/doc-spec-write/SKILL.md`,
   `suggested_fixes: []`.
3. `todoc explain-path --root demo skill/doc-spec-write/SKILL.md` → `ok: true`,
   `doc_type: agent-skill` (правильная форма: путь позиционный и относителен `DATA_ROOT`).
4. `todoc explain-path --help` → `Usage: ... explain-path [OPTIONS] PATH`.

## Ожидаемое поведение

1. На `usage.error` конверт содержит `suggested_fixes` с готовым argv: например
   `["todoc", "explain-path", "--root", "demo", "skill/doc-spec-write/SKILL.md"]`,
   и/или `guidance` с указанием, что `PATH` — позиционный аргумент.
2. На `explain.path_not_found` — подсказка о базе пути: «путь относителен
   DATA_ROOT (`--root demo`); префикс `demo/` не нужен» + argv-кандидат.
3. Поле `guidance` присутствует в любом выводе (ошибочном и неошибочном) в
   `json/table/markdown` — это требование P15 (`AGENTS.md`, правило 7).

Источник ожидания: `AGENTS.md` → «Железные правила сессии», п. 7 (P15:
`guidance` обязателен, подсказки в i18n-каталоге, покрыты контрактными тестами
CLI); существующий контракт `next_actions` в конверте (`src/todoc/cli.py:59-64`).

## Фактическое поведение

1. `suggested_fixes` — пустой список в обоих случаях.
2. `next_actions` — единственный общий элемент `todoc --help`, не привязанный
   к ошибке; готового argv для исправления нет.
3. Поля `guidance` в конверте нет ни в одном из наблюдавшихся выводов.

## Доказательства

```
$ todoc explain-path --root demo --path skill/doc-spec-write/SKILL.md
Error [usage.error]: No such option: --path
{
  "schema_version": 1, "ok": false, "data": {},
  "diagnostics": [{"code": "usage.error", "severity": "error",
                   "message": "No such option: --path", "suggested_fixes": []}],
  "next_actions": [{"argv": ["todoc", "--help"],
                    "purpose": "Показать список команд и опций"}]
}

$ todoc explain-path --root demo demo/skill/doc-spec-write/SKILL.md
Error [explain.path_not_found]: Path not found in dataset: demo/skill/doc-spec-write/SKILL.md
... "suggested_fixes": []
... "next_actions": [{"argv": ["todoc", "--help"], "purpose": "Показать список команд и опций"}]

$ todoc explain-path --root demo skill/doc-spec-write/SKILL.md
{ "ok": true, "data": {"path": "skill/doc-spec-write/SKILL.md",
  "doc_type": "agent-skill", "rule_source": "rule:fm-agent-skill"} }

$ todoc explain-path --help
Usage: python -m todoc explain-path [OPTIONS] PATH
```

## Воздействие

- Каждая неверная форма аргумента стоит агенту минимум одного лишнего вызова
  (`--help`), а при неочевидной базе пути — ещё одного (`explain-path` с
  обрезанным префиксом). В этой сессии: 2 лишних вызова, ~1.5k токенов.
- Хуже: агент делает вывод «команда не умеет то, что умеет» и уходит в
  файловый обход, нарушая правило 1 (`AGENTS.md`).
- P15 заявлен как контракт, но в коде не реализован — расхождение документации
  и поведения (см. также BUG-016: справки не описывают фактический контракт).

## Предложение по исправлению

1. В обработчике usage-ошибок Click (`main`, `src/todoc/cli.py:2446-2452`)
   перехватывать `click.UsageError`, парсить неизвестную опцию и прикладывать
   `suggested_fixes` с ближайшей валидной формой (позиционный `PATH`, известные флаги).
2. В `explain_path` при `path_not_found`: если путь начинается с имени root —
   предложить путь без префикса; если путь существует относительно cwd —
   предложить его же как относительный к `DATA_ROOT`.
3. Реализовать P15: `guidance` в `_emit_ok`/`_emit_result` из i18n-каталога по
   `code`; контрактный тест на наличие `guidance` в `json/table/markdown`.
4. Проверка: те же два вызова дают `suggested_fixes` с исполняемым argv.

## Заметки

- Связан с BUG-013 (неоднородные id/output-контракты) и BUG-016 (справки не
  описывают фактический контракт).
- Поиск перед созданием (2026-11-27): `--type bug-report --query doctor` — 0;
  `--query explain-path` — только упоминания в BUG-001/002 (там про `unknown`,
  не про пустые подсказки).

2026-11-28. Конверт v2 уже содержит guidance и ссылку на справку.
Отдельная точная подсказка для неверного позиционного PATH и корня explain-path остаётся в объёме репорта.
[Сводка выпуска](../notes/unified-cli-release.md).

- 2026-11-28: `fixed` — коммит `fa3b0dc`. `explain-path` на отсутствующем пути объясняет, что путь относителен DATA_ROOT, и кладёт в `next_actions` исправленный argv (если путь начинался с имени корня) либо `docs tree`; guidance `explain.path_not_found` описывает маршрут. Проверка: `tools/bug_acceptance.py --only BUG-021` → `fixed` (предложенный argv исполняется). Тест: `tests/cli/test_cli.py::test_explain_path_root_prefixed_suggests_a_working_argv`.
