---
id: doc:bugs/bug-029-two-skill-stores-no-unified-listing.md
title: "BUG-029: два хранилища скилов без единой команды обзора"
doc_type: bug-report
lang: ru
created: 2026-11-27
updated: 2026-11-28
bug_id: BUG-029
status: fixed
severity: docs
agent_impact: [friction, token_overrun]
tokens_extra_est: 2500
component: docs
found: 2026-11-27
---

# BUG-029: два хранилища скилов без единой команды обзора

| Поле | Значение |
|---|---|
| Bug ID | BUG-029 |
| Компонент | docs (`demo/skills` vs `demo/skill`; `HOME.md`, `notes/agent-contract.md`) |
| Обнаружено | 2026-11-27 — вопрос «какие скилы тебе доступны» |
| Окружение | todoc 0.1.0 (master 5e86eb7), Python 3.14.4 (WSL Ubuntu) |

## Сводка

В демо два независимых хранилища скилов: vault `demo/skills` (30 скилов,
виден в `todoc skills tree`) и папка документов `demo/skill` с типом `skill`
(6 документов `agent-skill`, не видна ни в `skills tree`, ни в одной сводке).
Плюс скилы самого харнесса, которых в датасете нет вовсе. Команды «покажи все
скилы, доступные агенту» не существует — состав приходится собирать из трёх
источников вручную.

## Шаги воспроизведения

1. `todoc skills tree --root demo --output table` → `skills/ (30 skills,
   3 sections, 1 muted)`; папки `skill` в выдаче нет.
2. `ls demo/skill` → `SKILL.md`, `doc-spec-write/`, `doc-rule-capture/`,
   `doc-task-report/`, `doc-flow-capture/`, `doc-release-notes/` (6 скилов).
3. `todoc explain-path --root demo skill/SKILL.md` → `doc_type: skill`,
   `rule_source: rule:fm-skill`.
4. `todoc explain-path --root demo skill/doc-spec-write/SKILL.md` →
   `doc_type: agent-skill`, `rule_source: rule:fm-agent-skill`.
5. `todoc skills tree --root demo --vault skill` → падение (BUG-027), то есть
   даже точечный обзор второго хранилища недоступен.
6. `todoc docs tree --root demo --within skill --output table` → видно папки,
   но без `name`/`description` скилов.

## Ожидаемое поведение

Один из вариантов:

1. Единая команда обзора: `todoc skills list --root demo --store all` (vault +
   документы типа `skill`/`agent-skill`) с явной пометкой источника каждого скила; или
2. Явное разделение в документации: `HOME.md` и `notes/agent-contract.md`
   описывают оба хранилища, зачем каждое нужно, и как перечислить каждое
   (`skills tree` для vault, `docs tree --within skill` / `docs search --type
   agent-skill` для документов) — с готовыми командами.

Источник ожидания: `AGENTS.md` → «Скилы: подключение движка к агенту»
(«перед нетривиальной задачей — `todoc skills tree` → выбрать скил»);
`demo/HOME.md` — карта содержимого демо, где `skill/` не объяснён.

## Фактическое поведение

1. `skills tree` знает только vault `skills` (параметр `--vault` по умолчанию
   `skills`, `src/todoc/cli.py:323`), документы типа `skill`/`agent-skill`
   в обзор не попадают.
2. `demo/skill` — валидный по структуре vault (корневой `SKILL.md` + 5 подпапок),
   но `--vault skill` падает (BUG-027), а как «документы» он даёт лишь пути без
   описаний.
3. Ни `HOME.md`, ни `notes/agent-contract.md` не объясняют разницу между
   `skills/` и `skill/`; имена отличаются одной буквой, что провоцирует ошибку выбора.
4. Скилы харнесса (например, `graphify`, `kilo-config`) вообще не представлены
   в датасете — их состав агент узнаёт только из своего промпта.

## Доказательства

```
$ todoc skills tree --root demo --output table
skills/  (30 skills, 3 sections, 1 muted)
  process/ — Процессы: Релизы, инциденты и workflow команды. (21)
  ...

$ ls demo/skill
SKILL.md  doc-flow-capture  doc-release-notes  doc-rule-capture
doc-spec-write  doc-task-report

$ todoc explain-path --root demo skill/SKILL.md
{"path": "skill/SKILL.md", "doc_type": "skill", "rule_source": "rule:fm-skill"}

$ todoc explain-path --root demo skill/doc-spec-write/SKILL.md
{"path": "skill/doc-spec-write/SKILL.md", "doc_type": "agent-skill",
 "rule_source": "rule:fm-agent-skill"}

$ todoc skills tree --root demo --vault skill
ValueError: ... (падение, см. BUG-027)
```

Код: `src/todoc/cli.py:323` (`--vault` default `skills`), отсутствие режима
«все хранилища» в `skills tree`.

## Воздействие

- Вопрос «какие скилы доступны» в этой сессии потребовал 8+ вызовов: две
  неудачные попытки запуска, `skills tree`, `ls`, `grep` по front matter,
  `explain-path` ×2, `docs tree`; ответ собирался вручную из трёх источников.
- Агент может пропустить нужный скил: 6 скилов из `demo/skill` невидимы в
  основном обзоре, а имя папок различается одной буквой.
- Цена ≈2.5k токенов на эпизод, повторяется при каждом «что тут есть».

## Предложение по исправлению

1. Добавить режим обзора всех хранилищ: `todoc skills tree --store all`
   (vault `skills` + документы `doc_type: skill|agent-skill`) с полем `store`
   у каждого скила; либо отдельную `todoc skills list`.
2. Починить падение `--vault skill` (BUG-027) — без этого второй обзор невозможен.
3. Описать оба хранилища в `HOME.md` и `notes/agent-contract.md`: назначение,
   команды обзора, правило именования (не создавать `skill`/`skills` в одном датасете).
4. Проверка: одна команда выдаёт 36 скилов с пометкой источника.

## Заметки

- Связан с BUG-027 (падение на vault с корневым `SKILL.md`), BUG-008 (счётчики
  `skills tree`), BUG-024 (шум индекса от документов скилов).
- Поиск перед созданием (2026-11-27): `--type bug-report --query vault` →
  только BUG-007 (упоминание `skills-vault` в DoD); `--query skills` →
  BUG-008, BUG-024 — про счётчики и индекс, не про отсутствие единого обзора.

- 2026-11-28: `fixed` — коммит `7b671e0` (вариант «документированный маршрут»). `docs/state/17-skills-and-vault.md` и `demo/notes/agent-contract.md` дают рабочие команды для `--vault skills` и `--vault skill`, поясняют отсутствие единого обзора и legacy-статус `skill/`. Проверка: `tools/bug_acceptance.py --only BUG-029` → `fixed`.
