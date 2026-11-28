---
title: Нулевой limit зацикливает курсор поиска
audit_id: CA-004
bug_id: BUG-050
canonical_path: demo/bugs/bug-050-zero-limit-search-cursor.md
status: open
severity: minor
agent_impact: friction
component: cli
---

# CA-004: Нулевой limit зацикливает курсор поиска

## Сводка

`docs search --limit 0` принимает значение и возвращает неполную страницу с тем же курсором. Клиент, продолжающий выдачу по cursor, не может продвинуться.

## Шаги воспроизведения

`PYTHONPATH=src python3 .doc/codexaudit/evidence/reproduce.py`, сценарии `zero_limit_search` и `zero_limit_search_again`. Во временном root есть один документ с test. Дважды вызвать `todoc --root <temporary-root> docs search --query test --limit 0`; во второй раз добавить `--cursor 0`.

## Ожидаемое поведение

Неположительный limit отклоняется как usage error либо получает явно завершающий контракт count-only без курсора. Продолжение выдачи должно продвигаться.

## Фактическое поведение

Оба вызова exit 0: `{"total":1,"returned":0,"truncated":true,"cursor":"0","items":[]}`.

## Доказательства

`cli.py:1261` использует unrestricted int. `search.py:186` получает пустой slice. `cli.py:1274` вычисляет offset + len(hits), поэтому cursor остаётся 0.

## Воздействие

Автоматический клиент может бесконечно повторять запросы. Severity minor: обычный положительный limit работает, но допустимый CLI-ввод нарушает инвариант пагинации. Связанные BUG-019/BUG-022 относятся к пустому query, BUG-045 — к бюджету ответа, это другие механизмы.

## Предложение по исправлению

Применить `click.IntRange(min=1)` и согласованную верхнюю границу либо явный count-only режим. Приёмка: 0 и отрицательные значения не выдают непродвигающийся cursor; страницы с положительным limit продвигаются до отсутствующего cursor.

## Заметки

Дедуп 2026-11-28 по `cursor 0` и `search_documents`. Полный список совпадений сохранён; совпадения по корневой причине нет. Фикс не реализован.
