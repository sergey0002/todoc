---
id: doc:bugs/bug-051-create-only-concurrent-overwrite.md
title: "BUG-051: Конкурентное создание нарушает гарантию create-only"
doc_type: bug-report
lang: ru
created: 2026-11-27
updated: 2026-11-28
tags: [bugs, bug-report, create-only, concurrency]
bug_id: BUG-051
status: fixed
severity: critical
agent_impact: none
component: engine
found: 2026-11-28
---

# BUG-051: Конкурентное создание нарушает гарантию create-only

## Сводка

Между проверкой отсутствия файла в apply_write_plan и его заменой существует окно гонки. Если другой писатель создаёт цель в этом окне, его содержимое молча перезаписывается.

## Шаги воспроизведения

`PYTHONPATH=src python3 .doc/codexaudit/evidence/reproduce.py`, сценарий `create_only_race`. В одноразовом каталоге создаётся WritePlan для отсутствующего `record.json`. Через unittest.mock в момент вызова atomic_write имитируется запись второго участника (`second writer`), затем выполняется исходный atomic_write первого участника (`first writer`).

Это детерминированная проверка interleaving, а не запуск двух реальных процессов. Она точно размещает конкурирующую запись после exists-check и до os.replace.

## Ожидаемое поведение

Существующая к моменту коммита цель не перезаписывается, первый участник получает конфликт. В `write.py:65` и справке `records create` заявлена unconditional no-overwrite гарантия.

## Фактическое поведение

apply_write_plan возвращает успех. Итоговый текст `first writer\n`; данные `second writer\n` потеряны. Повторная проверка существования до вызова atomic_write не защищает последующую замену.

## Доказательства

`write.py:118–132`: exists/hash check отделён от записи. `scanner.py:41–47`: tempfile + безусловный `os.replace(tmp_name, path)`. В воспроизводителе `competing_content_lost:true`.

## Воздействие

Потеря данных другого агента/процесса при совместной работе. Severity critical по проектной шкале «данные/безопасность»; это не заявление о критической удалённой уязвимости. Вероятность в реальной нагрузке не измерена. Одиночная последовательная работа не воспроизводит окно без конкурента.

## Предложение по исправлению

Обеспечить эксклюзивный commit создания средствами ОС либо координацией писателей, охватывающей проверку и запись. Для edits отдельно обеспечить compare-and-swap по хешу. Приёмка: реальный двухпроцессный тест даёт одного победителя и один конфликт, без перезаписи; fault injection подтверждает тот же результат.

## Заметки

Дедуп 2026-11-28: `apply_write_plan`, `write.target_exists`; отчёта с этой гонкой не найдено. BUG-034 — другой механизм, выход за DATA_ROOT. Фикс не реализован.

- 2026-11-28: `fixed` — коммит `7d32813` (код уже был в рабочем дереве). Эксклюзивное создание использует `os.link` и при конкуренте даёт `write.target_exists`; чужие байты сохраняются, временный файл не остаётся. Проверка: `tools/bug_acceptance.py --only BUG-051` → `fixed`. Регрессия: `tests/unit/test_storage_contracts.py::test_atomic_write_plan_keeps_a_competing_creation`.
