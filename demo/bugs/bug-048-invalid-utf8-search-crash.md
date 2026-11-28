---
id: doc:bugs/bug-048-invalid-utf8-search-crash.md
title: "BUG-048: Поиск падает на файле с невалидным UTF-8"
doc_type: bug-report
lang: ru
created: 2026-11-27
updated: 2026-11-28
tags: [bugs, bug-report, search, utf-8]
bug_id: BUG-048
status: fixed
severity: major
agent_impact: friction
component: engine
found: 2026-11-28
---

# BUG-048: Поиск падает на файле с невалидным UTF-8

## Сводка

Валидатор корректно распознаёт нечитабельный Markdown, но последующий поиск пытается прочитать его как нормальный документ и падает с UnicodeDecodeError.

## Шаги воспроизведения

`PYTHONPATH=src python3 .doc/codexaudit/evidence/reproduce.py`, сценарии `invalid_utf8_validate` и `invalid_utf8_search`. Временная фикстура `bad.md` содержит байты `b"# bad\n\xff"`. Команды: `todoc --root <temporary-root> validate --all`, затем `todoc --root <temporary-root> docs search --query bad`.

## Ожидаемое поведение

Validate возвращает `file.unreadable`; поиск возвращает контролируемую диагностику либо исключает непригодный документ, явно показывая неполноту. Ни один путь не должен завершаться необработанным исключением на исходном файле.

## Фактическое поведение

Validate: exit 3, `ok:false`, `file.unreadable`. Search: exit 1, `UnicodeDecodeError('utf-8', ..., 6, 7, 'invalid start byte')`, конверта нет.

## Доказательства

`validator.py:573–578` создаёт диагностику. `service.py:86–92` определяет status документа по scanned.status, который при корректном чтении байтов сканером остаётся ok. `search.py:34–37` ловит только OSError; UnicodeDecodeError проходит наружу. В `cli.py:1309` прямое чтение документа также не защищено этим контрактом.

## Воздействие

Один импортированный файл способен нарушить поиск по всему выбранному датасету. Severity major; агент вынужден вручную выяснять кодировку и изолировать файл. Это ошибка входной кодировки, отличная от BUG-030 о кодировании stdout на Windows.

## Предложение по исправлению

Передавать пригодность разбора в статус документа и единообразно обрабатывать ошибки UTF-8 на всех read/search-путях. Приёмка: fixture с `0xff` даёт машинную диагностику, остальные документы доступны; пригодные UTF-8 документы не меняют ранжирование.

## Заметки

Дедуп 2026-11-28: `UnicodeDecodeError`, `file.unreadable`; подходящего по корневой причине отчёта не найдено. Протокол `.doc/codexaudit/evidence/verification.md`. Фикс не реализован.

- 2026-11-28: `fixed` — коммит `7d32813`. Нечитаемый UTF-8 файл даёт `file.unreadable` (exit 6), поиск не падает. Тест: `tests/cli/test_unified_failures.py`.
