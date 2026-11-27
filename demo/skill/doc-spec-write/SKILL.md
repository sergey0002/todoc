---
name: doc-spec-write
description: >
  Написание capability-спеки SHALL + WHEN/THEN с дельтой ADDED/MODIFIED/REMOVED и сверкой с конституцией до сохранения. Применять, когда новое требование фиксируется нормативно.
doc_type: agent-skill
lang: ru
created: 2026-11-26
updated: 2026-11-27
tags: [skill, documentation, agent]
---

# Написание спеки

## Когда применять

- Требование фиксируется нормативно (SHALL) с проверяемыми сценариями;
- изменение вводит дельту требований (OpenSpec-интероп).

## Шаги

1. Эталон: `todoc types prompt spec-doc --op create --root KB`.
2. Гейт до сохранения: сверка с конституцией — `todoc docs read --root KB --id doc:constitution`
   (принципы P1-…); требование противоречит конституции — остановись и доложи.
3. Черновик: `docs new --root KB --type spec-doc --title "<Название>" --path specs/<имя>.md`;
   Requirement: «Система SHALL <проверяемое>» + «Проверка: <тест/команда>»;
   сценарии `#### Scenario: N` с `- **WHEN** / - **THEN**`.
4. Дельта в изменение: SHALL-строки → `requirements_delta` записи `change:<slug>`
   (added/modified/removed) прямой правкой файла + `todoc sync --root KB <путь>`.
5. Проверка: `validate --all` — 0 диагностик; скан заглушек; THEN наблюдаем.

## Стоп-условия

- Требование не проверяемо — вернись к пользователю за критерием.
- Противоречие конституции — не сохраняй, доложи конфликт.
