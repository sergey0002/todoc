---
id: doc:bugs/bug-028-no-runtime-contract-for-windows-wsl-harness.md
title: "BUG-028: нет runtime-контракта для Windows/WSL-харнесса — пути и кодировка"
doc_type: bug-report
lang: ru
created: 2026-11-27
updated: 2026-11-28
bug_id: BUG-028
status: open
severity: docs
agent_impact: [friction, token_overrun]
tokens_extra_est: 2500
component: docs
found: 2026-11-27
---

# BUG-028: нет runtime-контракта для Windows/WSL-харнесса — пути и кодировка

| Поле | Значение |
|---|---|
| Bug ID | BUG-028 |
| Компонент | docs (`AGENTS.md`: отсутствующий раздел о кодировке и передаче аргументов) |
| Обнаружено | 2026-11-27 — сессия из Windows PowerShell 5.1, рабочая папка — UNC-путь `\\wsl.localhost\Ubuntu\home\newuser\projects\todoc` |
| Окружение | todoc 0.1.0 (master 5e86eb7), Python 3.14.4 (WSL Ubuntu), харнесс — Windows PowerShell 5.1 |

## Сводка

В Windows+WSL-харнессе данные и аргументы портятся молча: не-ASCII вывод
приходит в двух разных искажениях (`РџСЂ…` — UTF-8, прочитанный как CP1251;
`������` — потеря при передаче через пайп PowerShell), а inline-вызов
`wsl -e bash -lc "…"` теряет вложенные кавычки — команда выполняется с
усечёнными аргументами. В этой сессии последнее привело к созданию документа
`inbox/bug-026.md` с заголовком `BUG-026:` и проигнорированным `--path`.
`AGENTS.md` не описывает ни кодировку, ни способ передачи аргументов, поэтому
каждая сессия заново находит это пробой.

## Шаги воспроизведения

1. `Get-Content demo/skills/process/release-flow/SKILL.md -TotalCount 5` →
   `description: "РџСЂРѕРІРѕРґРёС‚ merge-forward …"` (UTF-8 как CP1251).
2. `$env:PYTHONPATH="src"; python -m todoc skills tree --root demo` (Windows-Python
   поверх UNC-пути) → описания вида `"������ ������ �� ��������� �������: Python …"`.
3. Контроль: `wsl -e bash -lc 'cd ~/projects/todoc && PYTHONPATH=src python3 -m todoc skills tree --root demo'`
   → корректная кириллица.
4. `wsl -e bash -lc "cd ~/projects/todoc && PYTHONPATH=src python3 -m todoc docs new --root demo --type bug-report --title \"BUG-026: doctor …\" --path bugs/bug-026-….md"`
   → `{"path": "inbox/bug-026.md", "title": "BUG-026:"}` — кавычки потеряны,
   `--path` проигнорирован, создан лишний документ.
5. Тот же вызов через файл-скрипт (`bash /tmp/mk026.sh`) → корректный путь
   `bugs/bug-026-doctor-environment-checks-hardcoded-pass.md` и полный заголовок.
6. `wsl -e bash -lc "… 2>&1"` → поверх JSON-конверта печатается PowerShell
   `NativeCommandError` (двойной шум на каждую ошибку CLI).

## Ожидаемое поведение

`AGENTS.md` содержит короткий раздел «Runtime-контракт (Windows/WSL-харнесс)»:

- запуск только через WSL-интерпретатор:
  `wsl -e bash -lc 'cd ~/projects/todoc && PYTHONPATH=src python3 -m todoc …'`;
- аргументы с кавычками/кириллицей передавать файлом-скриптом, а не inline;
- вывод читать в UTF-8 (`Get-Content -Encoding utf8` или только WSL-сторона);
- `2>&1` не смешивать с `wsl`;
- Windows-Python по UNC-пути не использовать.

Источник ожидания: `AGENTS.md` — единственная инструкция агента в репозитории;
правило 3 требует, чтобы эксплуатация не стоила лишних вызовов; правило 1
(«только через CLI») невыполнимо без контракта запуска.

## Фактическое поведение

1. Раздел «Установка» (`AGENTS.md:22-30`) описывает только POSIX-пути; про
   кодировку и передачу аргументов — ничего.
2. Два разных искажения кириллицы в одном сеансе, оба без диагностики.
3. Inline-вызов теряет кавычки молча: вместо ошибки аргументов создаётся
   неверный документ (порча данных на мутирующей команде).
4. Ошибки CLI дублируются PowerShell-обёрткой при `2>&1`.

## Доказательства

```
$ Get-Content demo/skills/process/release-flow/SKILL.md -TotalCount 5
description: "РџСЂРѕРІРѕРґРёС‚ merge-forward СЂРµР»РёР·Р° Р±РµР· РєРѕРЅС„Р»РёРєС‚РѕРІ…"

$ $env:PYTHONPATH="src"; python -m todoc skills tree --root demo
"description": "������ ������ �� ��������� �������: Python � ������ .venv ..."

$ wsl -e bash -lc 'cd ~/projects/todoc && PYTHONPATH=src python3 -m todoc skills tree --root demo'
"description": "Ставит пакеты по конвенции проекта: Python — только .venv ..."

# тихая потеря кавычек при inline-вызове:
$ wsl -e bash -lc "… --title \"BUG-026: doctor …\" --path bugs/bug-026-….md"
{ "ok": true, "data": {"path": "inbox/bug-026.md", "title": "BUG-026:"} }
```

## Воздействие

- Агент читает искажённые описания и делает ложные выводы о содержимом датасета;
  чтобы получить чистый текст, он переходит на обход через WSL или файловые
  команды — лишние вызовы и перечитывания (≈2.5k токенов за сессию).
- Потеря кавычек — риск порчи данных: в этой сессии создан лишний документ
  `inbox/bug-026.md` (удалён, индекс пересобран, BUG-026 создан повторно).
  На командах `docs edit`/`records create` такая потеря могла бы испортить
  существующий файл, а не только создать мусор.
- Для человека-новичка: инструкция не предупреждает, что «очевидный» Windows-путь
  даёт искажённые данные.

## Предложение по исправлению

1. Добавить в `AGENTS.md` раздел «Runtime-контракт (Windows/WSL-харнесс)» с
   перечисленными правилами и одним рабочим примером.
2. Дать обёртку `todoc` (скрипт/функция), инкапсулирующую `wsl -e bash -lc`,
   чтобы правило 1 выполнялось без знания платформы (см. BUG-023).
3. В `doctor` добавить проверку кодировки stdout (см. BUG-026).
4. Проверка: новая сессия по контракту получает UTF-8 с первого вызова и не
   создаёт лишних документов при кириллическом `--title`.

## Заметки

- Пересечение с BUG-023 (нет `.venv`/entrypoint, тройное квотирование): там —
  доступность CLI, здесь — кодировка и тихая потеря аргументов с порчей данных.
- Связан с BUG-026 (`doctor` не проверяет окружение).
- Побочный артефакт: `inbox/bug-026.md` удалён в этой же сессии, индекс
  пересобран (`index rebuild --force`), BUG-026 создан с явным `--path`.
- Поиск перед созданием (2026-11-27): `--type bug-report --query encoding` →
  только BUG-004 (про `encoding="utf-8"` в коде правок); `--query venv` — 0.

### Повторный эпизод 2026-11-28: минимальный воспроизводимый пробник

Подтверждён молчаливый обрыв argv при внешних одинарных кавычках и внутренних
двойных — именно в такой форме выполнялись поиски и `docs new`:

```
$ wsl -d Ubuntu -- bash -lc 'printf "[%s]\n" "a b" --limit 5 --fields path,title'
[a]n
$ wsl -d Ubuntu -- bash -lc "printf '[%s]' 'a b' --limit 5 --fields path,title"
[a b][--limit][5][--fields][path,title]
```

Следствия в этой сессии: `docs search --query "…" --limit 3 --fields path,title`
вернул 10 элементов с полной проекцией (хвост потерян, ошибки нет), а
`docs new --title "BUG-058: …" --path bugs/… --apply` спланировал
`inbox/bug-058.md` с заголовком `BUG-058:` (файл не создан только потому, что
вместе с `--path` потерялся `--apply`). Рекомендация к правилу 12 из BUG-058:
запретить внешние одинарные кавычки в `AGENTS.md` и добавить этот `printf`-пробник
как обязательный шаг перед мутирующей командой.
