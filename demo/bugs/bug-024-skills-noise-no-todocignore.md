---
id: doc:bugs/bug-024-skills-noise-no-todocignore.md
title: "BUG-024: индекс демо зашумлён 51 unknown-документом скилов, .todocignore отсутствует"
doc_type: bug-report
lang: ru
bug_id: BUG-024
status: open
severity: minor
agent_impact: [friction, token_overrun]
tokens_extra_est: 8000
component: engine
found: 2026-11-28
created: 2026-11-27
updated: 2026-11-28
tags: [bugs, bug-report, engine, scanner, todocignore, index, noise]
---

# BUG-024: индекс демо зашумлён 51 unknown-документом скилов, .todocignore отсутствует

| Поле | Значение |
|---|---|
| Bug ID | BUG-024 |
| Компонент | engine (scanner/index) |
| Обнаружено | 2026-11-28 — поиск по коду и документам во время анализа идей |
| Окружение | todoc 0.1.0 (5e86eb7), Python 3.14.4, Windows 11 + WSL2 Ubuntu |

## Сводка

Исключения путей захардкожены в `HARD_EXCLUDE_DIRS`, декларативного
`.todocignore` нет. В индекс демо попадает 51 вспомогательный `.md` из
`demo/skills/**` с `doc_type: unknown`, а в репозитории лежит вендоренный каталог
`tmp_kb_skills_audit/` (38 МБ), из-за которого рекурсивный поиск раздувается и
усекается.

## Шаги воспроизведения

1. `rg -l '^doc_type: unknown' demo --glob '*.md'` → 51 файл, все внутри `demo/skills`.
2. `test -f demo/.todocignore` → нет файла.
3. `rg --files -g '*.md'` → 553 файла в репозитории против 233 в `demo/`.
4. `du -sh tmp_kb_skills_audit` → 38M.
5. `rg -n "def tree" src/todoc` → вывод усечён из-за минифицированных SVG внутри
   `tmp_kb_skills_audit/`.

## Ожидаемое поведение

Состав индекса задаётся данными рядом с данными: `.todocignore` в корне
`DATA_ROOT` и в подпапках (идея
[`ideas/todocignore.md`](../ideas/todocignore.md)). Вспомогательные промпты,
шаблоны и скрипты паков скилов не должны попадать в общий счётчик `documents`
и в выдачу `docs search`, а вендоренные каталоги — в обход дерева репозитория.

## Фактическое поведение

- Список исключений захардкожен:
  `HARD_EXCLUDE_DIRS = {".todoc", ".git", "__pycache__", "node_modules", ".obsidian", ".venv", "venv"}`
  (`src/todoc/adapters/filesystem/scanner.py:10`, используется в `:94` и
  `src/todoc/application/folder_config.py:95`).
- `.todocignore` не существует (`demo/.todocignore` отсутствует).
- 51 документ `demo/skills/**` индексируется как `doc_type: unknown`.
- `tmp_kb_skills_audit/` (38 МБ, вне датасета) не исключён из поиска по
  репозиторию: `rg` по `src` и `tests` возвращает тысячи строк из SVG/JSON этого
  каталога.

## Доказательства

```
unknown_fm_total: 51
unknown_fm_skills: 51
has_todocignore: no
repo_md_files: 553
demo_md_files: 233
audit_dir_size: 38M
```

```python
# src/todoc/adapters/filesystem/scanner.py:10
HARD_EXCLUDE_DIRS = {".todoc", ".git", "__pycache__", "node_modules", ".obsidian", ".venv", "venv"}
```

```
$ rg -n "def tree" src/todoc
... (вывод усечён; в него попали строки tmp_kb_skills_audit/**/*.svg)
```

## Воздействие

Шум в индексе меняет ранжирование `docs search` и раздувает `total_documents`
(461 вместо ~410 полезных). Вендоренный каталог ломает поиск по коду: вывод
приходится сохранять в файл и читать частями, а релевантные строки тонут в
минифицированных SVG. Обходной путь — точечные `rg --glob '*.py' src/todoc`,
то есть выход за пределы CLI и лишние вызовы. Оценка перерасхода — около 8k
токенов за сессию.

## Предложение по исправлению

- Реализовать идею `todocignore` (matcher на `pathspec`, каскад корень →
  подпапка) и завести `demo/.todocignore` с исключением вспомогательных файлов
  паков скилов.
- В корне репозитория — `.todocignore`/`.gitignore`-запись для
  `tmp_kb_skills_audit/` либо вынести каталог из чекаута.
- Проверка: `docs tree` показывает `total_documents` без unknown-документов
  скилов; `rg -n "def tree" src/todoc` возвращает только совпадения из `src/`.

## Заметки

Поиск перед созданием (2026-11-28): `--type bug-report --query "todocignore индексация"` — совпадений нет.
Связанные: идея [`ideas/todocignore.md`](../ideas/todocignore.md) (не реализована),
BUG-003 (счётчики демо расходятся с фактом), BUG-017 (дерево усечено).
