---
id: doc:bugs/bug-022-no-type-overview-query.md
title: "BUG-022: нет обзорной выборки по типу документа"
doc_type: bug-report
lang: ru
bug_id: BUG-022
status: open
severity: major
agent_impact: [friction, token_overrun]
tokens_extra_est: 15000
component: cli
found: 2026-11-28
created: 2026-11-27
updated: 2026-11-27
tags: [bugs, bug-report, cli, projection, status, overview]
---

# BUG-022: нет обзорной выборки по типу документа

| Поле | Значение |
|---|---|
| Bug ID | BUG-022 |
| Компонент | cli (`docs search/read/status`, `records list`) |
| Обнаружено | 2026-11-28 — вопрос «какие идеи не реализованы» |
| Окружение | todoc 0.1.0 (5e86eb7), Python 3.14.4, Windows 11 + WSL2 Ubuntu |

## Сводка

Нет одного вызова, который перечислит документы типа с их `status` из front
matter. `docs search` не отдаёт `status` в проекции, `docs status` требует
`--id` (только чтение/запись одного документа), `records list --type document`
покрывает лишь зеркальные записи (113 из 461) и не содержит `status`. В итоге
обзор типа стоит N отдельных `docs read`.

## Шаги воспроизведения

1. `todoc docs status --help` — убедиться, что `--id` обязателен и списка нет.
2. `todoc docs search --root demo --type idea --query "идея" --limit 1 --output json`
   — проверить ключи элемента выдачи.
3. `todoc records list --root demo --type document --limit 2 --output json`
   — проверить наличие `status` и охват.
4. `todoc docs tree --root demo --max-depth 2 --output json` — проверить, виден ли `status`.

## Ожидаемое поведение

Обзор типа — базовая операция для агента и должна стоить один вызов, например:

```
todoc docs list --root demo --type idea --status captured --fields id,path,title,status
```

или `docs search` с `status`/`doc_type` в проекции по умолчанию и без
обязательного текстового `--query`.

## Фактическое поведение

- `docs status` — `--id` required, списка нет (`docs status --help`).
- `docs search` возвращает элементы без `status`:
  `item_keys: ['heading_path', 'id', 'matched_terms', 'path', 'rank', 'relevance', 'snippet', 'title']`.
- `docs tree` содержит `status` в элементах документов, но молча усечён до
  50 из 461 (BUG-017), поэтому как обзор непригоден.
- `records list --type document` — 113 записей, `truncated: true`, поля
  `doc_type`/`title`/`source_path` есть, `status` нет.
- Команды `docs list` не существует (`todoc docs --help`).

## Доказательства

```
$ todoc docs status --help
Usage: ... docs status [OPTIONS]
Options:
  --id TEXT     [required]
  --set TEXT    Новое значение статуса (без --set — чтение).

$ todoc docs search --root demo --type idea --query "идея" --limit 1 --output json
item_keys: ['heading_path', 'id', 'matched_terms', 'path', 'rank', 'relevance', 'snippet', 'title']
has_status: False

$ todoc records list --root demo --type document --limit 2 --output json
"total": 113
"truncated": true
# в data записи: record_id, entity_type, title, source_path, doc_type, lang, tags — поля status нет

$ todoc docs --help
Commands: edit, flow, links, new, read, search, status, suggest, tree
# команды list нет
```

## Воздействие

На вопрос «какие идеи не реализованы» пришлось сделать 20 отдельных
`docs read --line-range 1-24` (5 батчей), потому что `status` живёт только в
front matter и в усечённом дереве. Это ~15k токенов и 22 вызова против одного
`docs list --type idea --fields id,path,title,status`.

Дополнительно: отсутствие обзора провоцирует обходные запросы вроде пустого
`--query` (BUG-019) и `records list --type idea` (BUG-020).

## Предложение по исправлению

- Добавить `docs list` с фильтрами `--type`, `--status`, `--within`, `--fields`,
  `--limit`, `--cursor`; `status` брать из индексированных метаданных.
- Включить `status` и `doc_type` в элемент `docs search` (метаданные уже есть в
  индексе: `Document.status` в `src/todoc/service.py:86-89`).
- Проверка: `docs list --type idea --status captured` возвращает 11 документов
  одним вызовом, без чтения тел.

## Заметки

Поиск перед созданием (2026-11-28): `--type bug-report --query "status проекция docs list"` — совпадений нет.
Связанные: BUG-017 (дерево усечено), BUG-019 (пустой query), BUG-020 (неймспейс записей),
идея [`ideas/unified-cli-output.md`](../ideas/unified-cli-output.md).

### Повторный эпизод 2026-11-28: вопрос «какие идеи не выполнены?»

Дедуп: повторно прочитан BUG-022; ранее в этой же сессии поиски
`docs search --root demo --type bug-report --query статус --limit 5`
и `--query guidance --limit 5` нашли BUG-022 и BUG-021.
Корневая причина обзора совпадает с BUG-022; новый номер не создаётся.

#### Измерение и воспроизведение

Источник счётчиков — видимые вызовы exec_command в предыдущем ответе этой беседы,
до запроса пользователя записать рекомендации. Всего 54 запуска команд:
20 неуспешных docs read с --path, затем 20 успешных docs read с --id,
остальные 14 — discovery, HOME, поиск, справка и проверка связанных багов.
Это число запусков команд, а не число внешних tool-сообщений и не 100 запросов.
Оценка дополнительного расхода этого эпизода: около 15000 токенов;
это приблизительная оценка, не измерение API usage.

Точные характерные команды (префикс запуска в WSL: env PYTHONPATH=src python3 -m todoc):
- `todoc docs search --root demo --type idea --limit 100`:
  `usage.error: Missing option '--query'`.
- `todoc docs tree --root demo --within ideas --max-depth 1`:
  total_documents=20; у документов status="ok", хотя в front matter
  action-logging — captured, wave-planning-cli-helpers — planned, agent-state — done.
  Следовательно, status дерева нельзя использовать как статус жизненного цикла.
- `todoc docs read --root demo --path ideas/action-logging.md --line-range 1-22`:
  `usage.error: No such option: --path`, suggested_fixes=[],
  next_actions ведёт только на `todoc --help` (BUG-021).
- Правильный вызов:
  `todoc docs read --root demo --id doc:ideas/action-logging.md --line-range 1-20`.
  Вернул status: captured в data.lines и повторил тот же текст в data.text.
- После дерева потребовались 20 отдельных чтений front matter. Итог:
  11 captured, 2 planned, 6 done, 1 без fm status
  (unified-cli-output: в теле «реализация ещё не согласована»).

Доказательства в данных: `ideas/action-logging.md:6`,
`ideas/wave-planning-cli-helpers.md:8`, `ideas/agent-state.md:6`,
`ideas/unified-cli-output.md:13`; существующие шаги CLI — выше.
Смешение имени status и отсутствие обзорной проекции увеличивают риск неверного ответа.

#### Рекомендации к исправлению CLI — приоритет P1

1. Один обзорный запрос: docs list с --type, фильтрами статуса, --fields,
   limit/cursor; отсутствующий статус возвращать явно как null.
   Предлагаемый контракт, пока НЕ существующая команда:
   `todoc docs list --root demo --type idea --fields id,path,title,status`.
   Для «не выполнено» явно определить включение captured/planned/active/null
   и исключение done/rejected/superseded; не приравнивать null к captured.
2. Развести статус разбора/индекса и статус жизненного цикла:
   parse_status и status (либо другое недвусмысленное именование).
   Поля должны иметь одинаковый смысл в list/search/tree/read.
3. Компактная JSON-проекция метаданных без тела; при чтении не дублировать
   содержимое в lines и text по умолчанию. Явно отдавать completeness,
   total/returned/truncated/cursor, чтобы агент мог остановиться.
4. Локальная guidance на ошибку: готовый argv и справка именно docs read,
   а не только корневой --help. Реализовать в рамках BUG-021/P15.

#### Рекомендации к харнесу — приоритет P1

1. Сначала проверить ОДНУ команду, затем тиражировать. Любой неуспех
   останавливает зависимый пакет; не запускать 20 одинаково ошибочных команд.
   Угаданный --path и массовое повторение — ошибка агента, не дефект CLI.
2. Для вопроса о списке выбирать путь «обзор метаданных → ответ».
   Не загружать HOME, тела всех документов и полный каталог скилов, если
   актуальная полная проекция уже содержит нужные поля. После read-only
   запроса проверять полноту ответа; обратное чтение нужно прежде всего
   для мутаций, иначе правило проверки превращается в рекурсивный обход.
3. Держать в диспетчере компактный маршрут «обзор типа/статусов» и доступные
   команды, подробные инструкции подгружать по ошибке (P15).
4. В среде PowerShell/WSL передавать argv без вложенного bash -lc,
   не угадывать экранирование и не повторять неработающий способ передачи.
5. При повторном известном дефекте сразу ссылаться на BUG-022/021,
   не откладывать фиксацию до замечания пользователя.

#### Критерии приёмки сценария

- На том же датасете обзор показывает 20 идей: 11 captured, 2 planned,
  6 done, 1 null; список незавершённых содержит 14 с оговоркой про null.
- Один вызов данных после discovery, без N отдельных чтений; целевой
  размер обзора — до 2000 токенов на 20 идей.
- Проверка харнеса: намеренно неверный первый read не запускает остальные 19.
- Проверки CLI: полнота/пагинация, отсутствующий status, отличие parse_status,
  корректная guidance и отсутствие двойного текста в компактном режиме.
- Успех измерять на пользовательском сценарии числом команд и объёмом вывода,
  а не только тем, что каждая отдельная команда проходит unit-тест.

Статус остаётся open: это дополнение backlog исправлений, код не исправлен.
