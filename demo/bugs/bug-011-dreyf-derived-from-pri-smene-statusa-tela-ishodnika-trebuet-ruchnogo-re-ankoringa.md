---
id: doc:bugs/bug-011-dreyf-derived-from-pri-smene-statusa-tela-ishodnika-trebuet-ruchnogo-re-ankoringa.md
title: "BUG-011: дрейф derived_from при смене статуса/тела исходника требует ручного ре-анкоринга"
doc_type: bug-report
lang: ru
created: 2026-11-26
updated: 2026-11-26
bug_id: BUG-011
status: open
severity: minor
agent_impact: friction, token_overrun
tokens_extra_est: 2000
component: cli
found: 2026-11-26
---

# BUG-011: дрейф derived_from при смене статуса/тела исходника требует ручного ре-анкоринга

| Поле | Значение |
|---|---|
| Bug ID | BUG-011 |
| Компонент | cli (stale, docs status, docs edit — пере-якорение зависимостей) |
| Обнаружено | 2026-11-26 — закрытие плана «Интероп-экспорты» (fm-статусы идея/план + пометка тела) |
| Окружение | todoc 0.1.0 (master a34068b), Python 3.11.2, Linux |

## Сводка

Любое изменение файла-источника (fm `status` через `docs status --set` или правка
тела через `docs edit`) меняет его sha256, после чего каждый зависимый документ
с fm-якорем `derived_from: ["путь@sha256:…"]` становится stale. Перепривязка —
полностью ручная: хеш нового состояния вычисляется вне CLI, номер fm-строки
зависимого документа ищется вручную, патч replace идёт через `docs edit`. В одной
сессии на паре идея → план это потребовалось трижды; ошибка в одном эпизоде
(якорь на промежуточный хеш) обнаруживается только повторным `stale`.

## Шаги воспроизведения

1. `todoc docs status --root demo --id doc:ideas/interop-exports.md --set done` —
   хеш идеи изменился → `todoc stale --root demo` = 1 (`staleness.dependency_changed`,
   владелец `demo/plan/interop-exports-dmn-asl-rasa.md`).
2. Ручной ре-анкоринг: `python3 -c "import hashlib; print(hashlib.sha256(open('demo/ideas/interop-exports.md','rb').read()).hexdigest())"`
   (вне CLI!), затем `docs edit` replace fm-строки 10 плана на
   `derived_from: ["ideas/interop-exports.md@sha256:<новый>"]` → stale 0.
3. Правка тела той же идеи (вставка пометки «Реализация: …») → снова stale 1 →
   шаг 2 повторяется целиком.
4. Детерминированно: любой `--set`/`edit` исходника при живом зависимом с whole-file
   якорем даёт тот же цикл (в этой сессии — 3 эпизода: captured→planned, planned→done,
   пометка тела).

## Ожидаемое поведение

- По докстрокам `staleness.py` якорь — это *фрагмент* (pointer/section), whole-file —
  легальная форма; `stale` обязан ловить дрейф — это by design и не баг.
- Баг в другом: диагностика `staleness.dependency_changed` не содержит материала
  для исправления (текущий хеш фрагмента, готовый anchor для replace), поэтому
  каждый эпизод = внешний sha256 + ручной поиск строки + повторный stale.
- Контракт `docs/status`/`docs edit` не упоминает зависимые якоря вообще: агент
  узнаёт о дрейфе постфактум из `stale`.

## Фактическое поведение

`check_owner` (`src/todoc/application/staleness.py`, блок `dependency_changed`)
кладёт в `evidence` только СТАРЫЙ anchor (`format_anchor(dep)` с прошившим хешем);
актуальный хеш в диагностике отсутствует. `docs status --set` и `docs edit` не
предупреждают о владельцах, чьи якоря указывают на файл, и не предлагают re-anchor.

## Доказательства

```
$ todoc stale --root demo          # после пометки тела идеи (эпизод 3)
stale: 1  staleness.dependency_changed demo/plan/interop-exports-dmn-asl-rasa.md
  ← ideas/interop-exports.md@sha256:31e0868d…   # только старый хеш
$ sha256sum demo/ideas/interop-exports.md   # хеш для якоря — вне CLI
$ todoc docs edit … replace line 10 …       # ручной replace fm-строки
stale: 0
```

Эпизоды сессии: (1) идея captured→planned → ре-анкор; (2) planned→done → ре-анкор;
(3) пометка тела идеи → повторный ре-анкор. В эпизоде (2) первый ре-анкор был
сделан на хеш после `--set`, но до правки тела — второй `stale` это поймал.

## Воздействие

- Кто: агент/человек, ведущий derived-документы (планы, витрины, экспорты).
- Частота: каждый ре-анкор = 4–6 CLI-вызовов + внешний hash + перечитывание файла
  ради номера строки; ~2000 токенов на эпизод против ~0 при поддержке CLI.
- Обходимость: да (ручной патч), но именно она и есть фрикция; при N зависимостях
  у одного исходника стоимость растёт линейно (демо: экспорт rasa-glossary несёт
  10 якорей на definition — правка одного термина даст 10 стейл-владельцев).

## Предложение по исправлению

1. `staleness.check_owner`: в `dependency_changed` добавить актуальный хеш фрагмента
   и готовый anchor: `format_anchor({**dep, "hash": actual})` в `message` или
   `suggested_fixes` — ре-анкоринг без внешнего sha256.
2. `docs status --set` / `docs edit` (apply): после записи пересобрать владельцев
   (`collect_owners` по якорям на этот path) и приложить next_action
   «перепривяжите N якорей» с готовыми anchor-строками.
3. Опционально: `todoc stale --re-anchor PATH --apply` — review-first замена
   якорей владельца на актуальные (surface как docs edit ops, с history).
Проверка: после шага 1 эпизод ре-анкоринга = stale → взять anchor из diagnostics →
docs edit → stale 0; без внешних вычислений.

## Заметки

- Не баг самой механики stale (дрейф ловится корректно, stale_ack существует для
  случая «дрейф намеренный») — баг отсутствия пути от диагностики к исправлению.
- Связанные: BUG-004 (docs edit line-ops — благодаря ему ре-анкоринг внутри CLI
  хотя бы возможен), план «скилы-взаимодействия» §8 (уроки про дрейф якоря).
