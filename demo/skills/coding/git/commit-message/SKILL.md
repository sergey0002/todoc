---
id: doc:skill-commit-message
title: "Скил: commit message из staged diff"
doc_type: agent-skill
lang: ru
updated: 2026-11-25
name: commit-message
description: "Пишет commit message из staged diff по конвенции репозитория. Use when committing."
created: 2026-11-26
tags: [skill, agent-skill, message, commit]
---

# Скил: commit message из staged diff

## When to Use

- Агент собирается выполнить `git commit`, и сообщение ещё не сформулировано.
- Несколько разнородных изменений — сначала предложить разбить коммиты.

## Procedure

1. `git diff --staged --stat` — что войдёт в коммит; `git log --oneline -8` — стиль истории репо.
2. Прочитай сам дифф `git diff --staged`; тип: feat/fix/docs/refactor/test/chore.
3. Сформулируй: строка ≤72 символов — «тип(область): что изменено по сути», затем пустая строка и тело «почему», если нетривиально.
4. Не выдумывай факты: в сообщении только то, что реально в диффе; ссылки на задачи — если есть в описании ветки.
5. Коммить с heredoc, не флагом -m с интерполяцией:
   ```bash
   git commit -m "$(cat <<'EOF'
   feat(skills): ...
   EOF
   )"
   ```

## Pitfalls

- Не перечисляй файлы («updated files») — describe суть, git и так знает файлы.
- Не смешивай переформатирование с логикой: предложи два коммита.
- Кириллица в теле — норма этого репо; в имени ветки — латиница.

## Verification

- `git log -1 --stat` показывает ровно задуманные файлы; сообщение читается без контекста.