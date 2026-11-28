# 19. Интероп-экспорты: DMN 1.3, ASL, Rasa NLU

Реализовано (Задачи 1–2, DoD 3/3). Источники: идея
[«Интероп-экспорты»](../../demo/ideas/interop-exports.md) (fm done) → план
[interop-exports-dmn-asl-rasa](../../demo/plan/interop-exports-dmn-asl-rasa.md)
(fm done, PR #85/#86); задачи `task:interop-formats-revision`,
`task:interop-converters-cli` (fm done). Модуль: `application/interop.py`
и CLI `interop export`. Вне скоупа (§2 плана):
импорт (обратные конвертеры), runtime-исполнение экспортов, чужие датасеты.

## Принцип

Запись — единственная истина; экспорт — **derived-артефакт**. Генераторы чистые
(строки/структуры, без I/O), без новых зависимостей (генерация шаблонами, валидность
форматов — структурные тесты). `fm derived_from` с якорями
`путь#/json-поинтер@sha256:…` на фрагменты записей-источников: правка записи →
`todoc stale` ловит дрейф (проверено на демо: правка flow → stale 4 → откат → 0).

## Контракт маппинга (докстроки `interop.py`, тест-контракты `tests/unit/test_interop.py`)

| Источник | Формат | Маппинг |
|---|---|---|
| `flow` (tree) | **ASL** (Amazon States Language, JSON) | `StartAt` — узел без входящих рёбер; question → `Choice` (ветви по `when`, порядок `priority`, безусловное ребро → `Default`); action → `Task` (`Resource: todoc:<node>`, `Next`/`End`); terminal с `props.error_code` → `Fail`, без кода → `Succeed` |
| `rule` (+ флоу по `belongs_to`) | **DMN 1.3** (XML) | decision table `hitPolicy="UNIQUE"`: входы «Ситуация» (example.given), «Условие» (example.when), «Режим» (props.mode вопроса отказа) → выход «Исход»; строка на example → код отказа (первый ALLCAPS-токен statement, RFC-2119 слова исключены); комплементарная строка ветви «да» → успешный исход; исход отказа — terminal **или action** с `error_code` (компенсации вида PAYMENT_RETRY) |
| `term` (definition) | **Rasa NLU YML** (`version: "3.1"`) | интент `term_<slug>`, examples — предложения definition; без `--id` — весь глоссарий одним YML |

## Команда

`todoc interop export --kind dmn|asl|rasa --id RECORD_ID [--write exports/…md]`

- без `--write`: артефакт печатается в stdout (`data.result.artifact`);
- с `--write` без `--apply`: предпросмотр и `plan_hash`. С `--write` и `--apply`: Markdown-документ `doc_type: export` (fm `derived_from`, теги
  `[export, interop, <kind>]`, артефакт в fenced-блоке) — путь **только внутри
  `exports/`** (`interop.write_outside_exports`), контainment проверяется как везде
  (`access.outside_data_root`);
- перезапись поверх CAS разрешена **только для derived-целей**
  (`interop.target_not_derived` для ручных файлов) — конвенция `docs flow render --write`;
- ошибки: `records.not_found`, `interop.wrong_entity_type`, `interop.flow_missing`,
  `interop.no_error_code`, `interop.no_terminal_for_code`, `interop.no_terms`,
  `interop.anchor_failed`, `usage.error` (без `--id` для asl/dmn).

## Реестр типов и демо

doc_type `export` (`demo/.todoc/doc_types/export/`) + правило `fm-export`
(doc_types 30→31). Витрины демо в `demo/exports/`: `asl-order-placement.md`
(машина из 8 состояний), `dmn-{no-funds,gateway-down,account-blocked}-v1.md`,
`rasa-glossary.md` (10 интентов). Для перегенерации используйте тот же `--write` с новым preview и `--apply`. История ревизий доступна через `todoc log`.

## Связанные разделы

- [06-validation-and-diagnostics.md](06-validation-and-diagnostics.md) — `staleness.*`.
- [08-records-and-relations.md](08-records-and-relations.md) — flow/rule/term записи.
- [03-cli-reference.md](03-cli-reference.md) — сигнатура команды.
