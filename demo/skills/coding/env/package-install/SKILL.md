---
id: doc:skill-package-install
title: "Скил: установка CLI-пакетов в систему"
doc_type: agent-skill
lang: ru
updated: 2026-11-25
name: package-install
description: "Ставит пакеты по конвенции проекта: Python — только .venv (PEP 668), Node — npm/npx, с проверкой версии. Use when installing tools."
created: 2026-11-26
tags: [skill, agent-skill, установка, пакетов]
---

# Скил: установка CLI-пакетов в систему

## When to Use

- Задаче нужен новый CLI/библиотека; агент собирается выполнить pip/npm install.

## Procedure

1. Определи экосистему. **Python**: глобальный pip в этом окружении заблокирован PEP 668
   (внешне управляемая среда) — ставь ТОЛЬКО в venv:
   ```bash
   .venv/bin/pip install <пакет>       # уже существующий venv проекта
   python3 -m venv .venv && .venv/bin/pip install <пакет>   # если venv нет
   ```
   Флаг `--break-system-packages` не использовать.
2. **Node**: `npm install` внутри проекта; одноразовые CLI — `npx <пакет>`, без `-g` без нужды.
3. Системные бинарники — через пакетный менеджер платформы, никогда `sudo curl | sh`.
4. Чужие install-скрипты — сначала прочитать (см. скил security-review), потом решать.
5. Проверь результат: `command -v <bin> && <bin> --version` (или `.venv/bin/<bin> --version`).
6. Зафиксируй: добавь пакет в pyproject.toml/package.json проекта, не в глобальные списки.

## Pitfalls

- «pip install» без venv → `error: externally-managed-environment` — это НЕ повод добавлять флаг, это сигнал использовать venv.
- npx с опечаткой ставит похожий пакет (typosquatting): проверяй точное имя по реестру.

## Verification

- Команда `--version` отвечает; путь бинарника лежит внутри .venv/node_modules или пакетного менеджера платформы — не в ~/.local/bin вне venv для Python-пакетов.