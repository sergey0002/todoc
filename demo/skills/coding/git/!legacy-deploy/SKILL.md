---
id: doc:skill-legacy-deploy
title: "Скил: деплой legacy-стенда (замьючен)"
doc_type: agent-skill
lang: ru
updated: 2026-11-25
name: legacy-deploy
description: "Мьютнутый скил: деплой на legacy-стенд. Исключён из дерева и поиска; включается --all."
---

# Скил: деплой legacy-стенда (замьючен)

> Папка называется `!legacy-deploy` — мьют по конвенции vault: скил исключён
> из дефолтного `skills tree` и из `docs search`; виден только с `--all`.
> Стандартное поле `name` остаётся валидным по стандарту Agent Skills.

## When to Use

- Только по явной просьбе пользователя «задеплой на legacy-стенд».

## Procedure

1. Проверь доступ: `ssh legacy-stand 'echo ok'` (без ключей — стоп, попроси у пользователя).
2. `rsync -av --dry-run dist/ legacy-stand:/srv/app/` — покажи план, затем без --dry-run.
3. Перезапусти сервис: `ssh legacy-stand 'systemctl --user restart app'`.

## Pitfalls

- Стенд общий: не деплой поверх чужой сессии; спроси, чья сейчас активна.

## Verification

- `curl -fsS http://legacy-stand/healthz` отвечает 200 с новой версией в payload.
