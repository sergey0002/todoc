---
created: 2026-11-24
updated: 2026-11-28
id: doc:state-known-issues
title: "Состояние: известные проблемы"
doc_type: reference
lang: ru
source: docs/state/11-known-issues.md
copied: true
---

# 11. Реестр известных дефектов

Ниже статусы из `docs list --type bug-report` на момент обновления документации.
Даты, доказательства и условия закрытия хранятся в репортах. BUG‑022 закрыт
после проверки общего обзора и пагинации.

```bash
todoc --root demo docs list --type bug-report --fields id,path,title,status
todoc --root demo docs list --type bug-report --status 'open|triaged|in_progress' --status-missing
```

| Репорт | Статус в датасете |
|---|---|
| [BUG-001: Явный doc_type без fm-правила резолвится в unknown](../../bugs/bug-001--явный-doc_type-без-fm-правила-резолвится-в-unknown.md) | fixed |
| [BUG-002: change open создаёт файлы с doc_type note без правила — резолвится в unknown](../../bugs/bug-002--change-open-создаёт-файлы-с-doc_type-note-без-правила---резолвится-в-unknown.md) | fixed |
| [BUG-003: Счётчики демо в README разошлись с фактом](../../bugs/bug-003--счётчики-демо-в-readme-разошлись-с-фактом.md) | fixed |
| [BUG-004: docs edit не умеет вставку и удаление строк](../../bugs/bug-004--docs-edit-не-умеет-вставку-и-удаление-строк.md) | fixed |
| [BUG-005: docs read --section игнорирует --budget](../../bugs/bug-005--docs-read---section-игнорирует---budget.md) | fixed |
| [BUG-006: docs new создаёт кириллические имена файлов из кириллического заголовка](../../bugs/bug-006--docs-new-создаёт-кириллические-имена-файлов-из-кириллического-заголовка.md) | fixed |
| [BUG-007: linkcheck из DoD планов не существует как команда CLI](../../bugs/bug-007--linkcheck-command-missing.md) | fixed |
| [BUG-008: skills tree показывает счётчик только собственных скилов раздела](../../bugs/bug-008--skills-tree-section-count-own-only.md) | fixed |
| [BUG-009: docs suggest нормирует score к максимуму — единственный кандидат всегда 1.0](../../bugs/bug-009--suggest-score-normalized-to-max.md) | fixed |
| [BUG-010: диагностика конфигов без location при unicode-escape ключе](../../bugs/bug-010--config-location-unicode-escape.md) | fixed |
| [BUG-011: дрейф derived_from при смене статуса/тела исходника требует ручного ре-анкоринга](../../bugs/bug-011-dreyf-derived-from-pri-smene-statusa-tela-ishodnika-trebuet-ruchnogo-re-ankoringa.md) | open |
| [BUG-012: history-ревизии мутирующих команд загрязняют git-статус](../../bugs/bug-012-history-revizii-mutiruyuschih-komand-zagryaznyayut-git-status.md) | fixed |
| [BUG-013: неоднородные id и output-контракты — резолв идентификатора требует ручного grep](../../bugs/bug-013-neodnorodnye-id-i-output-kontrakty-rezolv-identifikatora-trebuet-ruchnogo-grep.md) | open |
| [BUG-014: docs edit --preview не показывает нумерацию результата](../../bugs/bug-014-docs-edit-preview-ne-pokazyvaet-numeraciyu-rezultata.md) | open |
| [BUG-015: YAML-lite front matter не обрабатывает backslash-escape кавычек](../../bugs/bug-015-yaml-lite-front-matter-ne-obrabatyvaet-backslash-escape-kavychek.md) | fixed |
| [BUG-016: фильтры records query не документированы в справках](../../bugs/bug-016-filtry-records-query-ne-dokumentirovany-v-spravkah.md) | open |
| [BUG-017: docs tree молча усекает дерево до 50 папок и 50 документов без truncated](../../bugs/bug-017-docs-tree-silent-truncation.md) | fixed |
| [BUG-018: docs read без --section игнорирует --budget](../../bugs/bug-018-docs-read-full-ignores-budget.md) | fixed |
| [BUG-019: docs search с пустым --query возвращает ok:true и total 0](../../bugs/bug-019-docs-search-empty-query.md) | fixed |
| [BUG-020: records list по doc_type возвращает пустой успех вместо диагностики неймспейса](../../bugs/bug-020-records-list-wrong-namespace.md) | fixed |
| [BUG-021: usage-ошибки CLI не содержат suggested_fixes и guidance](../../bugs/bug-021-usage-errors-without-guidance.md) | open |
| [BUG-022: нет обзорной выборки по типу документа](../../bugs/bug-022-no-type-overview-query.md) | fixed |
| [BUG-023: CLI недоступен из харнеса — нет venv и entrypoint](../../bugs/bug-023-cli-not-reachable-from-harness.md) | open |
| [BUG-024: индекс демо зашумлён 51 unknown-документом скилов, .todocignore отсутствует](../../bugs/bug-024-skills-noise-no-todocignore.md) | open |
| [BUG-025: решение плана об отложенной идее не связано с самой идеей](../../bugs/bug-025-idea-plan-deferral-unlinked.md) | open |
| [BUG-026: doctor --scope environment рапортует pass без проверки окружения](../../bugs/bug-026-doctor-environment-checks-hardcoded-pass.md) | open |
| [BUG-027: skills tree падает traceback на vault с SKILL.md в корне](../../bugs/bug-027-skills-tree-crash-on-root-skill-md.md) | fixed |
| [BUG-028: нет runtime-контракта для Windows/WSL-харнесса — пути и кодировка](../../bugs/bug-028-no-runtime-contract-for-windows-wsl-harness.md) | open |
| [BUG-029: два хранилища скилов без единой команды обзора](../../bugs/bug-029-two-skill-stores-no-unified-listing.md) | open |
| [BUG-030: UnicodeEncodeError на Windows при выводе JSON/table с не-ASCII символами](../../bugs/bug-030-unicode-encode-error-windows-stdout.md) | open |
| [BUG-031: Тест test_open_reports_path_and_status падает на Windows из-за разделителей путей](../../bugs/bug-031-windows-path-separator-test-failure.md) | open |
| [BUG-032: CLI возвращает Windows-пути с backslash в JSON вместо POSIX](../../bugs/bug-032-cli-returns-windows-paths-with-backslash.md) | open |
| [BUG-033: History revert не сохраняет line endings (CRLF на Windows)](../../bugs/bug-033-history-revert-line-endings-windows.md) | open |
| [BUG-034: change apply пишет за пределы DATA_ROOT по target дельты](../../bugs/bug-034-change-apply-target-outside-root.md) | fixed |
| [BUG-034: Тесты истории падают на Windows из-за chmod и line endings](../../bugs/bug-034-history-tests-windows-chmod-line-endings.md) | open |
| [BUG-035: history show/diff/blame читают файлы вне DATA_ROOT по --path](../../bugs/bug-035-history-path-outside-root.md) | open |
| [BUG-035: DUPLICATE of BUG-027: skills tree падает при наличии SKILL.md в корне vault](../../bugs/bug-035-skills-tree-crash-root-skill-md.md) | duplicate |
| [BUG-036: skills import --into выходит за пределы DATA_ROOT](../../bugs/bug-036-skills-import-outside-root.md) | fixed |
| [BUG-037: глобальный --output игнорируется подкомандами](../../bugs/bug-037-global-output-ignored.md) | fixed |
| [BUG-038: records read --view с неизвестным именем молча возвращает всю запись](../../bugs/bug-038-records-read-unknown-view.md) | fixed |
| [BUG-039: records aggregate без --type молча выбирает тип workout](../../bugs/bug-039-records-aggregate-hidden-default.md) | fixed |
| [BUG-040: skills read падает traceback на некорректном --line-range и принимает --budget -1](../../bugs/bug-040-skills-read-invalid-range.md) | fixed |
| [BUG-041: records list --until/--relation фильтруют после limit — total и truncated врут](../../bugs/bug-041-records-list-post-limit-filters.md) | fixed |
| [BUG-042: records query падает traceback на некорректном QuerySpec](../../bugs/bug-042-records-query-invalid-spec.md) | fixed |
| [BUG-043: docs read --line-range вне файла возвращает пустой успех](../../bugs/bug-043-docs-read-line-range-out-of-bounds.md) | fixed |
| [BUG-044: status отдаёт next_actions с ключами action/reason вместо argv/purpose](../../bugs/bug-044-status-next-actions-contract.md) | fixed |
| [BUG-045: docs search --budget не ограничивает ответ — считается только текст сниппета](../../bugs/bug-045-docs-search-budget-not-honest.md) | fixed |
| [BUG-046: fix --apply заменяет первое вхождение цели в тексте, а не сломанную ссылку](../../bugs/bug-046-fix-applies-wrong-occurrence.md) | fixed |
| [BUG-047: Неверная форма target отношения обрушает валидацию](../../bugs/bug-047-malformed-relation-target.md) | fixed |
| [BUG-048: Поиск падает на файле с невалидным UTF-8](../../bugs/bug-048-invalid-utf8-search-crash.md) | fixed |
| [BUG-049: Preview правки одобряет неисполнимый патч](../../bugs/bug-049-edit-preview-invalid-ops.md) | fixed |
| [BUG-050: Нулевой limit зацикливает курсор поиска](../../bugs/bug-050-zero-limit-search-cursor.md) | fixed |
| [BUG-051: Конкурентное создание нарушает гарантию create-only](../../bugs/bug-051-create-only-concurrent-overwrite.md) | fixed |
| [BUG-052: Сбой rename при публикации уничтожает предыдущий снимок индекса](../../bugs/bug-052-index-publish-loses-snapshot.md) | fixed |
| [BUG-053: Контрактные тесты пропускают вложенные команды flow](../../bugs/bug-053-contract-tests-missing-nested-leaves.md) | fixed |
| [BUG-054: Актуальная справка описывает отменённое поведение поиска и CSV](../../bugs/bug-054-current-docs-search-csv-drift.md) | open |
| [BUG-055: Неизвестный --type/--within в docs search даёт тихий пустой результат](../../bugs/bug-055-unknown-search-filter-silent-empty.md) | open |
| [BUG-056: Нет CLI-команды для списка тегов и фильтра записей по тегу](../../bugs/bug-056-no-tag-listing-or-record-filter.md) | open |
| [BUG-057: Обзор открытых баг-репортов не получается одной командой](../../bugs/bug-057-open-bugs-list-not-discoverable.md) | open |
| [BUG-058: Инструкции и маршрутизация скилов не выводят на обзор статусов](../../bugs/bug-058-routing-docs-gap.md) | open |
| [BUG-059: tools/refresh_demo_state.py не запускается и расходится с demo-копиями](../../bugs/bug-059-refresh-demo-state-broken.md) | open |
| [BUG-060: docs list --status не принимает альтернативы через pipe](../../bugs/bug-060-status-filter-pipe-rejected.md) | open |
| [BUG-064: usage.missing_root отдаёт exit 3 вместо обещанных 2](../../bugs/bug-064-missing-root-exit-code.md) | fixed |
| [BUG-065: change_id без валидации грамматики](../../bugs/bug-065-change-id-grammar.md) | fixed |
| [BUG-066: derived_from читает файлы вне DATA_ROOT без проверки границы](../../bugs/bug-066-derived-from-outside-root.md) | fixed |
| [BUG-067: stale --ack перезаписывает CRLF и завершающий newline тела](../../bugs/bug-067-stale-ack-line-endings.md) | fixed |
| [DESIGN-Q01: терминальный статус записи — guard процедурный, движок молчит](../../bugs/design-q01-terminalnyy-status-zapisi-guard-procedurnyy-dvizhok-molchit.md) | open |
| [DESIGN-Q02: review-first двойной вызов — стоимость для агента против контроля](../../bugs/design-q02-review-first-dvoynoy-vyzov-stoimost-dlya-agenta-protiv-kontrolya.md) | open |
| [BUG-001: Явный doc_type без fm-правила резолвится в unknown](../../records/documents/bug-001-fm-doc-type-unknown.json) | поле отсутствует |
| [BUG-002: change open создаёт файлы с doc_type note без правила — резолвится в unknown](../../records/documents/bug-002-change-open-note-unknown.json) | поле отсутствует |
| [BUG-003: Счётчики демо в README разошлись с фактом](../../records/documents/bug-003-readme-counters-stale.json) | поле отсутствует |
| [BUG-004: docs edit не умеет вставку и удаление строк](../../records/documents/bug-004-docs-edit-line-ops.json) | поле отсутствует |
| [BUG-005: docs read --section игнорирует --budget](../../records/documents/bug-005-section-ignores-budget.json) | поле отсутствует |
| [BUG-006: docs new создаёт кириллические имена файлов из кириллического заголовка](../../records/documents/bug-006-cyrillic-slug-docs-new.json) | поле отсутствует |
| [BUG-007: linkcheck из DoD планов не существует как команда CLI:friction, token_overrun:1500](../../records/documents/bug-007-linkcheck-command-missing.json) | поле отсутствует |
| [BUG-008: skills tree показывает счётчик только собственных скилов раздела:friction:400](../../records/documents/bug-008-skills-tree-section-count-own-only.json) | поле отсутствует |
| [BUG-009: docs suggest нормирует score к максимуму — единственный кандидат всегда 1.0:friction:300](../../records/documents/bug-009-suggest-score-normalized-to-max.json) | поле отсутствует |
| [BUG-010: диагностика конфигов без location при unicode-escape ключе:friction:300](../../records/documents/bug-010-config-location-unicode-escape.json) | поле отсутствует |
| [BUG-011: дрейф derived_from при смене статуса/тела исходника требует ручного ре-анкоринга](../../records/documents/bug-011-derived-from-drift-reanchoring.json) | поле отсутствует |
| [BUG-012: history-ревизии мутирующих команд загрязняют git-статус](../../records/documents/bug-012-history-journal-git-pollution.json) | поле отсутствует |
| [BUG-013: неоднородные id и output-контракты — резолв идентификатора требует ручного grep](../../records/documents/bug-013-id-resolve-output-contracts.json) | поле отсутствует |
| [BUG-014: docs edit --preview не показывает нумерацию результата](../../records/documents/bug-014-edit-preview-no-line-numbers.json) | поле отсутствует |
| [BUG-015: YAML-lite front matter не обрабатывает backslash-escape кавычек](../../records/documents/bug-015-yaml-lite-quote-escape.json) | поле отсутствует |
| [BUG-016: фильтры records query не документированы в справках](../../records/documents/bug-016-query-filters-undocumented.json) | поле отсутствует |
| [DESIGN-Q01: терминальный статус записи — guard процедурный, движок молчит (дизайн-вопрос)](../../records/documents/design-q01-terminal-status-guard.json) | поле отсутствует |
| [DESIGN-Q02: review-first двойной вызов — стоимость для агента против контроля (дизайн-вопрос)](../../records/documents/design-q02-review-first-cost.json) | поле отсутствует |

[Запись диагностик](06-validation-and-diagnostics.md) · [Связанные работы](16-leftovers-report.md)
