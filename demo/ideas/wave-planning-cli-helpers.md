---
id: doc:ideas/wave-planning-cli-helpers.md
title: "Идея: CLI-команды волнового планирования (todoc stale anchor/reanchor, todoc plan portfolio и пакетный todoc plan bind)"
doc_type: idea
lang: ru
created: 2026-11-27
updated: 2026-11-28
status: planned
tags: [idea, cli, planning, roadmap, staleness, skills, планирование]
related: ["[[skills-engine]]", "[[plan-lifecycle-skills]]", "[[trace-traversal]]", "[[entity-to-folder]]", "[[multi-project-workspace]]", "[[bmad-v6-wave-planning-skills]]", "[[bmad-wave-planning-skills]]"]
---

# Идея: CLI-команды волнового планирования (`todoc stale anchor/reanchor`, `todoc plan portfolio` и пакетный `todoc plan bind`)

- Тип: `idea`
- Создан: 2026-11-27
- Идентификатор: `doc:ideas/wave-planning-cli-helpers.md`
- Статус: `captured` (идея, не перешла в план)

## Суть

Вынести в CLI `todoc` детерминированную механику конвейера волнового планирования (`bmad-*` / `todoc-plan`): вычисление и перепривязку секционных хэш-якорей (`todoc stale anchor` и `todoc stale reanchor`), сводный рентген портфеля идей, сирот, очереди готовых волн и файловых коллизий (`todoc plan portfolio`), пакетную привязку `1..K` идей к плану волны с переводом статусов (`todoc plan bind` + мульти-`--id` в `todoc docs status`), секционную замену текста в `todoc docs edit` (`replace_section`) и проверку затронутых коммитами документов реальности (`todoc stale --git-range`).

## Проблема

По принципу `AGENTS.md` (*«Механика — в CLI, семантика — в скилах»*) и практике эталонных SDD-систем (`BMAD v6/v7` `sprint_plan.py` / `lint_spine.py`, `gsd-build/get-shit-done` `gsd-tools`, `Beads` `bd ready`), агент расходует лишний контекст и ошибается там, где скил заставляет LLM глазами обходить десятки файлов и вручную считать инварианты:
1. **Нет CLI-команды вычисления якорей `derived_from` (`BUG-011`):** `src/todoc/application/staleness.py` проверяет якоря `path#section:<H>@sha256:...`, а `src/todoc/cli.py:622` умеет делать только проверку и `--ack` — для первичной генерации якоря на `1..K` идей в front matter нового плана волны агенту приходится писать одноразовый Python-скрипт с вызовом `fragment_hash`.
2. **Слепой `O(N)` обход пула идей и планов перед нарезкой волн:** при запуске `bmad-slice-roadmap`, `bmad-wave-plan` и `bmad-adversarial-review` агенту нужно знать: (а) какие идеи в статусе `captured` остались сиротами вне волн (`100% coverage` из `GSD`), (б) не попала ли одна идея сразу в два активных плана, (в) не пересекаются ли `files_touched` у параллельных планов (`Collisions` из `BMAD slice.md`), и (г) какие волны разблокированы по `depends_on_waves` (`bd ready` из `Beads`).
3. **Пакетные переходы волны требуют серии вызовов:** когда план волны покрывает `3–5` идей, агенту приходится отдельно редактировать `derived_from`/`covers` и вызывать `todoc docs status` по одному `--id` на каждую идею.
4. **Построчные номера в `todoc docs edit` при секционных правках:** скилы `bmad-forge-idea`, `bmad-wave-plan` и `spec-kit converge` чаще всего перезаписывают или дописывают конкретную секцию (`## Предложение`, `## 5. Задачи`), где ручной подсчёт номеров строк хрупок.
5. **Риск пропустить обновление `state/` на приёмке волны (`bmad-wave-retro`):** после серии коммитов волны полезно за один вызов увидеть, какие документы реальности `state/` / `architecture/` упоминают изменённые файлы `src/...`, но сами ещё не актуализированы.

## Предложение

### 1. Секционные якоря свежести: `todoc stale anchor` и `todoc stale reanchor`

- `todoc stale anchor --root KB --id doc:ideas/a.md [--id doc:ideas/b.md ...] [--section Предложение]`
  - Вызывает `fragment_hash` + `format_anchor` из `staleness.py` и возвращает в `data.anchors` готовый массив строк `["ideas/a.md#section:Предложение@sha256:...", ...]` за `< 10 мс`.
- `todoc stale reanchor --root KB --id doc:plan/wave-01.md [--only doc:ideas/a.md] [--preview | --apply]`
  - В отличие от `--ack` (который пишет `acknowledged_hashes`, оставляя старый якорь в `derived_from`), штатно обновляет сами SHA-256 якорей в `derived_from` после содержательной синхронизации плана с обновлённой идеей (`--preview` → `--apply`).

### 2. Детерминированный рентген портфеля и коллизий: `todoc plan portfolio`

Read-only команда `todoc plan portfolio --root KB [--project <slug>]` за один проход по индексу (`< 20 мс`) возвращает структуру для скилов планирования и ревью:
- `ideas_by_status` — группировка всех `doc_type: idea` по `captured / planned / in_progress / done` с `id`, `title`, `tags`, числом открытых вопросов в `## Открытые вопросы` и `related`;
- `coverage` — детерминированный `Coverage & Orphan Check` (по образцу `gsd-roadmapper` и `spec-kit analyze`):
  - `orphan_ideas` — `captured`-идеи, не покрытые ни одним активным `roadmap` / `plan` (`covers` или `derived_from`);
  - `duplicate_assignments` — идеи, привязанные сразу к нескольким незавершённым планам волн;
- `file_collisions` — пересечения затрагиваемых путей кода между незавершёнными планами (из опционального массива `files_touched` во front matter и строк `- Create: \`...\`` / `- Modify: \`...\`` в секциях 4–5 планов);
- `ready_waves` — планы/волны, у которых все зависимости в `depends_on_waves` находятся в статусе `done`.

### 3. Пакетная привязка идей к плану волны: `todoc plan bind` и мульти-`--id` в `todoc docs status`

- В `todoc docs status` поддержать повторяющийся `--id` (`--id doc:a --id doc:b --set planned [--preview | --apply]`).
- Добавить `todoc plan bind --root KB --plan doc:plan/wave-01.md --idea doc:ideas/a.md [--idea doc:ideas/b.md ...] [--section Предложение] [--set-status planned] [--preview | --apply]`, который атомарно прописывает `covers` + секционные якоря `derived_from` в план и переводит связанные идеи в `planned`.

### 4. Секционные операции в `todoc docs edit` (`replace_section` / `append_section`)

- Расширить `apply_edit_ops` в `src/todoc/application/write.py` двумя декларативными операциями поверх заголовков `parse_markdown`:
  - `{"op": "replace_section", "heading": "Предложение", "text": [...]}` — заменяет тело секции между заголовком и следующим заголовком того же или более высокого уровня;
  - `{"op": "append_section", "heading": "5. Задачи", "text": [...]}` — дописывает блок в конец секции (идеально для append-only доводки `Convergence` по паттерну `spec-kit converge`).

### 5. Детектор дрейфа `git diff → state/`: `todoc stale --git-range <base>..HEAD`

- Сопоставляет `git diff --name-only <base>..HEAD` с `source_anchor` и упоминаниями путей `src/...` в документах `state/` и `architecture/`, возвращая список документов реальности `AS-IS`, которые требуют проверки в `bmad-wave-retro`.

### 6. Детерминированный режим подробности скилов: `agent.guidance_mode` и `todoc skills read --mode`

- Сама LLM не способна надёжно оценить собственную силу (слабая модель из самоуверенности пропускает примеры, а сильная тратит токены на лишнее чтение). Поэтому выбор глубины подсказок переносится в CLI и стейт сессии:
  - в `ALLOWED_KEYS_V1` (`src/todoc/application/state.py`) добавляется ключ `agent.guidance_mode` со значениями `auto` (по умолчанию), `compact` (для сильных моделей) и `guided` (для слабых / быстрых моделей);
  - в `todoc skills read` добавляется опция `--mode [auto|compact|guided]`: в режиме `compact`/`auto` отдаётся только компактный `SKILL.md`, а в режиме `guided` CLI автоматически доклеивает в выдачу `references/worked-example.md` этого скила за один вызов;
  - **поведенческая авто-эскалация (`auto`):** если при проверке `todoc plan portfolio` (`wave_cards_lint`) или `todoc validate` модель допустила структурную ошибку (пропустила один из 4 тезисов резюме волны, вынесла `.py` / `doc:` в человеческое описание или оставила сироту), CLI возвращает в `next_actions` команду `todoc skills read --path ... --mode guided`, принудительно выдавая модели эталонный образец только тогда, когда она реально ошиблась.

## Открытые вопросы

- Опциональные поля волны (`roadmap`, `wave`, `covers`, `depends_on_waves`, `files_touched`) размещаются прямо во front matter существующего `doc_type: plan` без заведения отдельного `doc_type: wave_plan` — да, валидируются как необязательные типизированные поля.

## Связь с выпущенным CLI

Общие статусы, диагностика и review-first операции выпущены. Команды планирования волн остаются в своей итерации.
[Результаты выпуска](../notes/unified-cli-release.md).
