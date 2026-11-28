---
title: Сбой rename при публикации уничтожает предыдущий снимок индекса
audit_id: CA-006
bug_id: BUG-052
canonical_path: demo/bugs/bug-052-index-publish-loses-snapshot.md
status: open
severity: major
agent_impact: friction
component: engine
---

# CA-006: Сбой rename при публикации уничтожает предыдущий снимок индекса

## Сводка

RegistryStore.publish удаляет текущий снимок до успешного переключения на новый. Ошибка переименования staging оставляет индекс без current, хотя docstring обещает сохранение старого снимка при отказе.

## Шаги воспроизведения

`PYTHONPATH=src python3 .doc/codexaudit/evidence/reproduce.py`, сценарий `snapshot_failure`. Временный RegistryStore успешно публикует первый снимок. При второй публикации Path.rename для `.tmp-current` подменяется на `OSError("audit injected rename failure")`; затем вызывается load_current.

## Ожидаемое поведение

Предыдущий снимок остаётся читаемым после неудачи. Источник ожидания — `registry.py:125`: «On error, the old one stays».

## Фактическое поведение

До сбоя `before_readable:true`; после — `after_readable:false`, `current_dir_exists:false`.

## Доказательства

`registry.py:148–150`: сначала `shutil.rmtree(self.current_dir)`, затем `tmp_dir.rename(self.current_dir)`. Обработчик `151–154` удаляет staging, но не восстанавливает старое поколение. CURRENT.json при этом может ещё ссылаться на прежние метаданные.

## Воздействие

Временно недоступный/несогласованный производный индекс, дополнительный rebuild и риск отказа concurrent reader. Исходные документы не потеряны, индекс пересобираем; severity major за нарушение обещания публикации, а не critical за потерю исходных данных.

## Предложение по исправлению

Публиковать уникальное готовое поколение, затем атомарно переключать указатель. Удалять старый снимок после коммита. Приёмка: отказ на каждом шаге сохраняет читаемую старую или новую версию; согласованы meta/payload; две публикации не делят общий staging.

## Заметки

Дедуп 2026-11-28: `RegistryStore`, `tmp-current`; совпадения по компоненту без этой причины не дублируются. Подтверждено инъекцией отказа, не реальным дисковым сбоем. Фикс не реализован.
