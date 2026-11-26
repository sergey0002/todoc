---
id: doc:skill-release
title: "Скил: релизный срез (changelog, тег, notes)"
doc_type: agent-skill
lang: ru
updated: 2026-11-25
name: release
description: "Режет релиз: changelog, тег и release notes по конвенции репозитория. Use when cutting a release."
created: 2026-11-26
tags: [skill, agent-skill, changelog, релизный]
---

# Скил: релизный срез

## When to Use

- Ветка готова к релизу: тесты зелёные, мержи в master завершены.

## Procedure

1. Определи предыдущий тег: `git describe --tags --abbrev=0`; диапазон: `git log <тег>..HEAD --oneline`.
2. Сгруппируй коммиты по типам (feat/fix/docs) — основа changelog; SemVer по наличию breaking/feat/fix.
3. Обнови файл версии (pyproject.toml `version`) одним коммитом `chore(release): vX.Y.Z`.
4. `git tag -a vX.Y.Z -m "..."` только ПОСЛЕ зелёного полного pytest.
5. Release notes: 3–7 пунктов «что изменилось для пользователя», без внутренних номеров PR.

## Pitfalls

- Не тегай коммит с красным CI даже если локально зелёный.
- Не переписывай существующие теги; forward-only.

## Verification

- `git tag --points-at HEAD` — тег на верном коммите; pytest зелёный на тегированном состоянии.