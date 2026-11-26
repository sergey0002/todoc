---
id: doc:skill-release-flow
title: "Скил: merge-forward релиза"
doc_type: agent-skill
lang: ru
updated: 2026-11-25
name: release-flow
description: "Проводит merge-forward релиза без конфликтов: порядок мержей, rebase, проверки. Use when merging release branches."
created: 2026-11-26
tags: [skill, agent-skill, forward, релиза]
---

# Скил: merge-forward релиза

## When to Use

- Несколько фича-веток/планов идут в master одновременно и мержатся последовательно.

## Procedure

1. Порядок мержей зафиксируй ДО начала (в плане — риск-таблица); по этому репо: doc-tags → softdoc → skills → lifecycle.
2. Перед каждым мержем: `git fetch origin && git merge origin/master` в ветку — конфликты решаются В ветке, не в master.
3. Конфликтующие зоны known заранее (cli.py, validator.py, document-rules.json) — читай обе стороны, не бери «нашу» вслепую.
4. После каждого мержа: полный pytest + validate до push; PR мержится, затем fetch перед следующим.
5. Если план мержа сломался (не mergeable) — синхронизируй ветку с master и повтори.

## Pitfalls

- «Мержить поверх устаревшего master» — главный источник конфликтов; fetch перед каждым шагом.
- Не мержи два PR параллельно: race на journal.jsonl и правилах.

## Verification

- После последнего мержа: origin/master содержит все ветки, pytest/validate зелёные на master.