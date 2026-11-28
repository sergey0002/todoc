---
id: doc:bugs/bug-013-neodnorodnye-id-i-output-kontrakty-rezolv-identifikatora-trebuet-ruchnogo-grep.md
title: "BUG-013: неоднородные id и output-контракты — резолв идентификатора требует ручного grep"
doc_type: bug-report
lang: ru
created: 2026-11-26
updated: 2026-11-28
bug_id: BUG-013
status: fixed
severity: minor
agent_impact: friction, token_overrun
tokens_extra_est: 1500
component: cli
found: 2026-11-26
---

# BUG-013: неоднородные id и output-контракты — резолв идентификатора требует ручного grep

| Поле | Значение |
|---|---|
| Bug ID | BUG-013 |
| Компонент | cli (docs new / records get / docs read — id и output-контракты) |
| Обнаружено | 2026-11-26 — баг-репорты и записи плана «Интероп-экспорты» |
| Окружение | todoc 0.1.0 (master a34068b), Python 3.11.2, Linux |

## Сводка

Идентификатор одного документа неоднороден (md: fm `id: doc:bugs/…translit….md`;
запись: `document:bug-…` с другим слагом), `docs new` не возвращает `id` в data,
а при ошибке id под `2>/dev/null` CLI печатает error-envelope, который парсится
как `data: {}` и неотличим от пустого успеха. Резолв любого id — grep по файлам.

## Шаги воспроизведения

1. `todoc docs new --type bug-report --title T --dir bugs | jq .data.id` →
   KeyError `id` (ключа нет; id достаётся повторным чтением файла).
2. Один документ = два id: `doc:bugs/bug-011-…translit…md` (fm) и
   `document:bug-011-…` (запись); кросс-резолв — только руками по `source_path`.
3. `todoc records get --id X 2>/dev/null | jq .data` → `{}` — error-envelope
   (`records.not_found`) парсится как пустой успех, если не проверять `ok`.

## Ожидаемое поведение

- `docs new` возвращает `id` (и `record_id` записи при наличии) в data —
  как `records create` возвращает путь.
- Либо единый id у md и записи, либо машинка кросс-резолва (`docs read --id`
  понимает document:-id по source_path).
- Error-envelope выводится и в stderr, и в stdout-JSON с `"ok": false`;
  потребитель обязан проверять `ok` — контракт должен это фиксировать явно
  (README/справка), а `2>/dev/null` не должен превращать ошибку в пустой успех.

## Фактическое поведение

`docs new` возвращает path без id; два идентификационных пространства md-доков
и записей существуют параллельно без моста; при перенаправлении stderr
error-envelope уходит в stdout и обманчиво похож на пустой результат.

## Доказательства

```
$ todoc docs new … | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['id'])"
KeyError: 'id'                                   # трижды за сессию
$ todoc records get --id document:bug-011-… 2>/dev/null | jq .data
{}                                               # ошибка спрятана в envelope
$ grep -m1 '^id:' demo/bugs/bug-011-*.md         # резолв fm-id — внешним grep
```

## Воздействие

- Каждый новый документ: KeyError + grep файла (~300–500 токенов сверху);
  за сессию — 10+ документов (баг-репорты, план, задачи).
- Ловушка `{}` вместо ошибки — источник ложных выводов (в сессии дважды).

## Предложение по исправлению

1. `docs new`: добавить `id`/`record_id`/`hash` в data.
2. Кросс-резолв: `docs read/records get` принимают чужой namespace id
   (resolve по `source_path`) либо возвращают `related_record_id` в data.
3. Документировать контракт envelope: `ok` обязателен к проверке; рассмотреть
   дублирование error-envelope в stdout при любом `--output json`.

## Заметки

- Связан с BUG-006 (транслит-слаги) — id наследует путь вместо семантики.

- 2026-11-28: `fixed` — коммит `ab84bfb`. `docs new --apply` возвращает `id` и `record_id` (null без зеркала); `docs read --id` принимает id записи и разрешает его через `source_path` (`resolved_from`), неизвестный id остаётся `docs.not_found`; контракт error-envelope (`ok: false` в stdout и stderr) зафиксирован в `docs/state/03-cli-reference.md`. Проверка: `tools/bug_acceptance.py --only BUG-013` → `fixed`. Тесты: `tests/cli/test_unified_docs.py::test_docs_new_returns_canonical_id`, `test_docs_read_resolves_record_id_via_source_path`.
