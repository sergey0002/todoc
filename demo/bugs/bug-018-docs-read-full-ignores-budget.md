---
id: doc:bugs/bug-018-docs-read-full-ignores-budget.md
title: "BUG-018: docs read без --section игнорирует --budget"
doc_type: bug-report
lang: ru
bug_id: BUG-018
status: fixed
severity: minor
agent_impact: [friction, token_overrun]
tokens_extra_est: 3000
component: cli
found: 2026-11-28
created: 2026-11-27
updated: 2026-11-28
tags: [bugs, bug-report, cli, read, budget, truncation]
---

# BUG-018: docs read без --section игнорирует --budget

| Поле | Значение |
|---|---|
| Bug ID | BUG-018 |
| Компонент | cli (`docs read`, ветки default и line-range) |
| Обнаружено | 2026-11-28 — чтение 20 документов идей с бюджетом |
| Окружение | todoc 0.1.0 (5e86eb7), Python 3.14.4, Windows 11 + WSL2 Ubuntu |

## Сводка

В ветке чтения всего документа `--budget` режет только поле `text`, но не
выставляет `truncated` и не ограничивает массив `headings`. В ветке
`--line-range` бюджет не применяется вовсе. Итог: при `--budget 400` ответ
весит 3778 байт и не сообщает, что текст обрезан.

## Шаги воспроизведения

1. Полное чтение с бюджетом:

   `todoc docs read --root demo --id doc:ideas/action-logging.md --budget 400 --output json`

2. Контроль — та же команда с `--section`:

   `todoc docs read --root demo --id doc:ideas/action-logging.md --section Суть --budget 400 --output json`

3. Сравнить размер ответа и наличие `truncated`.

## Ожидаемое поведение

`--budget` — «честный бюджет»: либо ответ укладывается в лимит, либо в `data`
есть `truncated: true`, чтобы агент знал о неполноте. Это уже реализовано для
секции после BUG-005: `src/todoc/cli.py:1336-1349` ограничивает окно секции
по байтам и выставляет `data["truncated"]` (`src/todoc/cli.py:1354`).

## Фактическое поведение

- Ветка полного документа: `data["text"] = text[: budget or 4000]`
  (`src/todoc/cli.py:1361-1364`), `data["headings"]` — все заголовки документа,
  `truncated` не выставляется.
- Ветка `--line-range` (`src/todoc/cli.py:1351-1356`) бюджет не читает вообще.
- Результат: `--budget 400` → файл ответа 3778 байт (в 9.4 раза больше бюджета),
  `text_len: 400`, `lines_count: 0`, `has_truncated: False`.

## Доказательства

```
### --budget 400 (полный документ)
3778            # размер ответа в байтах
0               # вхождений "truncated"
data_keys: ['dataset_id', 'doc_type', 'format', 'hash', 'headings', 'id', 'path', 'related', 'tags', 'text', 'title', 'updated']
text_len: 400
lines_count: 0
has_truncated: False

### --budget 400 --section Суть
1098            # размер ответа в байтах
"truncated": true
```

```python
# src/todoc/cli.py:1361-1364
else:
    data["title"] = md.title
    data["headings"] = [{"title": h.title, "level": h.level, "line": h.line, "anchor": h.anchor} for h in md.headings]
    data["text"] = text[: budget or 4000]
```

## Воздействие

Агент не может отличить полный текст от обрезанного: при `text_len: 400` без
`truncated` ответ выглядит целым, и модель делает выводы по первым 400 символам.
Обходной путь — повторное чтение с большим бюджетом или `--section`, то есть
двойная стоимость на каждый документ. В сессии на 20 документов это лишние
вызовы и перерасход порядка 3k токенов.

## Предложение по исправлению

- В ветках default и `--line-range` (`src/todoc/cli.py:1351-1364`) считать
  `used_bytes` по сериализуемой проекции и выставлять
  `data["truncated"] = len(encoded) > budget`.
- `headings` либо входит в бюджет, либо явно помечается как метаданные вне
  бюджета (поле `headings_truncated`).
- `--line-range` должен уважать `--budget` и сообщать `truncated`.
- Проверка: `docs read --budget 400` → размер ≤ ~400 байт + метаданные,
  `truncated: true`; `--line-range` с бюджетом ведёт себя так же.

## Заметки

Поиск перед созданием (2026-11-28): `--type bug-report --query "budget"` — найден BUG-005
(`docs read --section игнорирует --budget`), другой код-путь (секция уже исправлена,
полное чтение и line-range — нет), поэтому отдельный репорт.
Связанные: BUG-005 (исправлен), BUG-017 (тот же класс молчаливого усечения).

- 2026-11-28: `fixed` — коммит `7d32813`. `docs read` без `--section` укладывает текст в бюджет и помечает обрезку: `--budget 100` → `text_len=100 truncated=True`. Тест: `tests/cli/test_unified_docs.py::test_search_metadata_and_unicode_budget`.
