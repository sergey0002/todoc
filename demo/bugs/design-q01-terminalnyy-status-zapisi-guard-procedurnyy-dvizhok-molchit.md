---
id: doc:bugs/design-q01-terminalnyy-status-zapisi-guard-procedurnyy-dvizhok-molchit.md
title: "DESIGN-Q01: терминальный статус записи — guard процедурный, движок молчит"
doc_type: bug-report
lang: ru
created: 2026-11-26
updated: 2026-11-28
tags: [bugs, bug-report, design-question, lifecycle]
bug_id: DESIGN-Q01
status: open
severity: docs
agent_impact: none
component: constitution
found: 2026-11-26
---

# DESIGN-Q01: терминальный статус записи — guard процедурный, движок молчит

| Поле | Значение |
|---|---|
| ID | DESIGN-Q01 |
| Компонент | constitution (G1, §3) + engine (records status) |
| Обнаружено | 2026-11-26 — сквозной сценарий «скилы-взаимодействия» З8 |
| Окружение | todoc 0.1.0 (master a34068b), Python 3.11.2, Linux |

## Сводка

**Дизайн-вопрос, не дефект** (осознанное P1-решение; фиксируется для явного
решения): `records status --set done` на open-задаче проходит без фразы
пользователя — guard терминальных статусов живёт в скиле execute (процедура,
строки 23–28), движок его не проверяет.

## Шаги воспроизведения

1. `todoc records status --root demo --id task:interop-formats-revision --set done`
   — без явной фразы → `ok: true`, статус `done`.
2. Скил-контракт требует фразы (demo/skills/process/todoc-execute/SKILL.md:23–28),
   но движку это неизвестно.
3. В сессии инцидент произошёл и был откачен (`--set open`).

## Ожидаемое поведение

Вопрос решения (варианты): (a) оставить как есть — конституция G1 запрещает
движку task-менеджмент, guard — дело скилов; (b) предупреждение validate:
«терминальный статус без основания»; (c) движковый блок с явным
`--ack-phrase`. Каждое решение тянет за собой конституционный допуск G1.

## Фактическое поведение

Движок применяет любой статус из enum схемы; контракт терминальности —
только текст скила.

## Доказательства

```
$ todoc records status --root demo --id task:interop-formats-revision --set done
ok: true, status: done          # без фразы пользователя (инцидент 26.11, откачен)
$ sed -n '23,28p' demo/skills/process/todoc-execute/SKILL.md   # guard здесь
```

## Воздействие

- Безопасность процесса держится на дисциплине агента; неверное применение
  движком не ловится (validate = 0 при «неправильном» done).

## Предложение по исправлению

1. Решение на уровне конституции (допуск/запрет движковой проверки) — ADR.
2. Минимум без нарушения G1: warning-диагностика validate для терминальных
   статусов задач без `origin.ack`-поля.

## Заметки

- Сознательно `agent_impact: none`: не попадает в реестр friction —
  это вопрос решения, а не баг. Связан с G1 конституции.
