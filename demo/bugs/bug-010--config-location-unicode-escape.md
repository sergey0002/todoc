---
id: doc:bug-010-config-location-unicode-escape
title: "BUG-010: диагностика конфигов без location при unicode-escape ключе"
doc_type: bug-report
lang: ru
bug_id: BUG-010
status: fixed
severity: minor
component: validator
agent_impact: friction
tokens_extra_est: 300
found: 2026-11-25
---

# BUG-010: диагностика конфигов без location при unicode-escape ключе

| Поле | Значение |
|---|---|
| Bug ID | BUG-010 |
| Компонент | validator (`folder_config._key_line`; та же логика в `validator._key_location`) |
| Обнаружено | 2026-11-25 — Задача 1/добор coverage плана folder-config: тест на «ключ не найден» дал пустую локацию |
| Окружение | todoc 0.1.0 (19d1130), Python 3.11, Linux |

## Сводка

Локация в диагностике `folder.config.*` ищет литеральную подстроку `"ключ"` в
тексте файла (`_key_line`: needle = `"order"`). Ключ, записанный в JSON как
unicode-escape — `"\u006frder"` вместо `"order"` — литерала в тексте не даёт,
поэтому диагностика получает `location: {}` без строки. Функционально валидация
работает (ключ декодируется json-парсером, код ошибки ставится), но агент,
получив диагностику, не может открыть файл на нужной строке и ищет проблему
перечитыванием. Та же стратегия поиска используется в `validator._key_location`
для прочих диагностик — ограничения системное, не только для конфигов папок.

## Шаги воспроизведения

1. Создать `notes/.config.json`:
   `{"schema_version": 1, "title": "Папка", "\u006frder": true}` (order=true — bool).
2. `todoc validate --root demo --all` → диагностика `folder.config.bad_order`
   («order должен быть int.») с `location: {}`.
3. В эквивалентном конфиге с обычным `"order": true` location содержит строку.

## Ожидаемое поведение

Локация указывает строку всегда: fallback-поиск по декодированному ключу
(последовательность escape-форм `\u00XXrder` и т.п.) или вычисление позиции по
событиям json-парсера; если строку определить невозможно — сообщение явно
говорит «строка не определена», чтобы агент не ждал координат.

## Фактическое поведение

`location: {}` молча; тест
`tests/unit/test_folder_config.py::test_bad_order_key_line_missing`
фиксирует пустую локацию как текущее поведение (специально подобранный
escape-ключ `"\u006frder"`).

## Доказательства

- `src/todoc/application/folder_config.py`, `_key_line` — возврат `None`,
  если литерала не встретилась (`for … continue` / `return None`).
- `src/todoc/application/validator.py`, `_key_location` — та же стратегия
  для остальных диагностик датасета.
- Тест (см. выше) — добавлен при доборе coverage до 100% по `_key_line`.

## Воздействие

Friction: ручной поиск строки в файле (+1–2 чтения файла на диагностику);
для больших конфигов и серий диагностик — заметный перерасход чтений.

## Предложение по исправлению

1. Fallback в `_key_line`/`_key_location`: искать декодированное имя ключа
   с учётом escape-форм, либо брать строку из событий json-парсера.
2. Минимальный вариант: при недоступной строке добавлять в message пометку
   «строка не определена (ключ записан escape-последовательностью)».
3. Регресс-тест: диагностика для `"\u006frder"` несёт строку или явную пометку.

## Исправление (2026-11-25)

Исправлено в commit `f732343` (PR #57) по «Предложению 1»: `_key_line`
(folder_config) и `_key_location` (validator) после неудачи литерального
поиска делают fallback-проход посимвольным шаблоном `(?:c|\uXXXX)` — ключ,
записанный unicode-escape (`"\u006frder"`), находит строку и колонку.
Проверки: `test_key_line_finds_unicode_escaped_key`,
`test_validator_key_location_finds_unicode_escaped_key`,
интеграционный `test_folder_config_bad_order_escaped_key_has_location`
(диагностика `folder.config.bad_order` теперь несёт `{"line": 1}`); ветка
«ключа нет вовсе» сохранена (`None`/`{}`).
