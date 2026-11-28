---
id: doc:bugs/bug-015-yaml-lite-front-matter-ne-obrabatyvaet-backslash-escape-kavychek.md
title: "BUG-015: YAML-lite front matter не обрабатывает backslash-escape кавычек"
doc_type: bug-report
lang: ru
created: 2026-11-26
updated: 2026-11-28
bug_id: BUG-015
status: fixed
severity: minor
agent_impact: friction
tokens_extra_est: 600
component: engine
found: 2026-11-25
---

# BUG-015: YAML-lite front matter не обрабатывает backslash-escape кавычек

| Поле | Значение |
|---|---|
| Bug ID | BUG-015 |
| Компонент | engine (adapters/formats/markdown.py — YAML-lite парсер fm) |
| Обнаружено | 2026-11-25 — наполнение идей/планов с кавычками в title |
| Окружение | todoc 0.1.0 (master a34068b), Python 3.11.2, Linux |

## Сводка

YAML-lite не разбирает `\"`-эскейп в кавыченных значениях fm: значение остаётся
с буквальными backslash-ами (не соответствуя намерению) и без предупреждения —
`yaml_unsafe` не выдаётся. Канон «raw-кавычки» пришлось выучить по факту.

## Шаги воспроизведения

1. Файл с fm `title: "a \"b\" c"`.
2. `parse_markdown(text).front_matter` → `{'title': 'a \"b\" c'}` — backslash-ы
   сохранены, предупреждения нет.
3. Агент пишет эскейп по привычке YAML → значение тихо отличается от намерения.

## Ожидаемое поведение

Либо парсинг `\"` как `"` (как в YAML), либо диагностик
`markdown.front_matter.yaml_unsafe`/специализированная с указанием места.
Контракт «в fm-строках raw-кавычки, `"` внутри запрещено» — в справке.

## Фактическое поведение

Тихое сохранение backslash-ов: значение искажено, диагностики нет, справки нет.

## Доказательства

```python
from todoc.adapters.formats.markdown import parse_markdown
text = '---\ntitle: "a \\"b\\" c"\ndoc_type: note\n---\n\n# x\n'
doc = parse_markdown(text)
doc.front_matter  # {'title': 'a \"b\" c', ...}  — backslash-ы остались
doc.warnings      # []  — предупреждения нет
```

## Воздействие

- Заголовки с кавычками (цитаты, термины) пишутся с «каноном raw-кавычек»
  по памяти сессии; ошибка тихая — данные искажены без диагностики.

## Предложение по исправлению

1. Минимум: диагностика на `\"`-эскейп в fm-строках (как yaml_unsafe).
2. Максимум: поддержка `\"` по правилам YAML.
3. Справка `references/`: контракт YAML-lite (raw-кавычки, списки `[a, b]`).

## Заметки

- Урок зафиксирован в памяти сессий 25–26.11 («raw-кавычки — канон YAML-lite»).

- 2026-11-28: `fixed` — коммит `7d32813`. YAML-lite снимает экранирование кавычек: заголовок `a "b" c` разбирается целиком. Проверка: `tools/bug_acceptance.py --only BUG-015` → `fixed`. Тест: `tests/unit/test_formats_hardened.py`.
