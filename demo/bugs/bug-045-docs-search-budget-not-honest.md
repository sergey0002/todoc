---
id: doc:bugs/bug-045-docs-search-budget-not-honest.md
title: "BUG-045: docs search --budget не ограничивает ответ — считается только текст сниппета"
doc_type: bug-report
lang: ru
created: 2026-11-28
updated: 2026-11-27
bug_id: BUG-045
status: open
severity: minor
agent_impact: [friction, token_overrun]
tokens_extra_est: 1500
component: cli
found: 2026-11-28
tags: [bugs, bug-report, cli, search, budget, truncation]
---

# BUG-045: docs search --budget не ограничивает ответ — считается только текст сниппета

| Поле | Значение |
|---|---|
| Bug ID | BUG-045 |
| Компонент | cli (`docs search --budget`, `application/search.py`) |
| Обнаружено | 2026-11-28 — аудит bounded-чтения и бюджета |
| Окружение | todoc 0.1.0 (5e86eb7 + рабочее дерево), Python 3.14.3, Windows 11 + WSL2 Ubuntu |

## Сводка

`docs search --budget 50` не укладывает ответ в 50 байт и не сообщает, что
бюджет исчерпан: в `used_bytes` попадает только текст сниппета, но не метаданные
(`id`, `path`, `title`, `heading_path`, `matched_terms`, `rank`, envelope), а
первый хит добавляется даже если его сниппет больше бюджета. Ответ на
`--budget 50` — ~1350 символов, сниппет — ~240 символов, `truncated: true`
относится к числу хитов, а не к бюджету.

## Шаги воспроизведения

1. `todoc docs search --root demo --query "контракт" --limit 1 --budget 50 --output json > out.json`
2. Длина ответа — ~1350 символов (в UTF-8 байт больше); бюджет — 50.
3. Разобрать `data.items[0].snippet.text` — ~240 символов, хотя бюджет 50.
4. Проверить `data.truncated` — `true` (есть ещё хиты), `snippet.snippet_truncated` —
   `true` (окно 240 символов), отдельного признака «бюджет исчерпан» нет.

## Ожидаемое поведение

`--budget` — «честный бюджет»: либо ответ (или документированная часть ответа)
укладывается в лимит, либо в `data` есть `budget_exhausted: true`/`truncated`
именно по бюджету. Если бюджет меньше минимального сниппета — вернуть пустой
список с диагностикой или один сниппет, обрезанный до бюджета, но не 240
символов при лимите 50. Контракт bounded output — P7; для `docs read --section`
бюджет уже считается по байтам (`src/todoc/cli.py:1336-1349`).

## Фактическое поведение

- `search_documents` считает `cost = len(snippet.encode("utf-8"))` и добавляет
  хит, даже если `used_bytes + cost > budget` и `hits` пуст:
  `src/todoc/application/search.py:188-195`.
- Метаданные хита и конверт в бюджет не входят.
- `truncated` вычисляется как `total > offset + len(hits)`
  (`search.py:216`), то есть означает «есть ещё хиты», а не «бюджет исчерпан».
- Сниппет ограничен `max_chars=240` (`search.py:51`), независимо от `--budget`.

## Доказательства

```
$ todoc docs search --root demo --query "контракт" --limit 1 --budget 50 --output json > out.json
# длина ответа (JSON-текст):
1350 символов

# data.items[0].snippet:
{'text': '--- id: doc:note-agent-contract title: Контракт CLI для агента ... - Фо',
 'line_start': 1, 'line_end': 15, 'snippet_truncated': True}
# длина text ≈ 240 символов при --budget 50
# data.truncated = true (это «есть ещё хиты», а не «бюджет»)
```

Код: `src/todoc/application/search.py:188-195`, `216`; `src/todoc/cli.py:1272-1278`.

## Воздействие

- `friction`: агент задаёт бюджет, получает ответ в 27 раз больше и не знает,
  что лимит не соблюдён; приходится вручную резать/перечитывать.
- `token_overrun`: при серии поисков с малым бюджетом лишние килобайты
  метаданных и сниппетов; эпизод ≈ 1–2k токенов.
- Ложное `truncated: true` смешивает два разных смысла (хиты vs бюджет), что
  мешает автоматическому циклу «дочитывай, пока truncated».

## Предложение по исправлению

1. Считать бюджет по сериализуемой проекции хита (сниппет + обязательные
   метаданные) и выставлять `budget_exhausted: true`, когда хит не влез.
2. Если бюджет меньше минимального сниппета — вернуть `items: []` +
   `budget_exhausted: true` + `suggested_budget`.
3. Разделить `truncated` (есть ещё хиты) и `budget_exhausted` (ответ урезан
   бюджетом); задокументировать оба в README.
4. Тест: `--budget 50` → размер ответа ≤ 50 + фиксированные метаданные,
   `budget_exhausted: true`; `--budget 100000` — все хиты.

## Заметки

Поиск перед созданием (2026-11-28): `docs search --type bug-report --query
"docs search budget"` — найден BUG-018 (`docs read` без `--section`), другой
код-путь; BUG-005 — секция. Связанные: BUG-018, BUG-005, BUG-043.
