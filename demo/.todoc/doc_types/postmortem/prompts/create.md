# Создание: `postmortem`

Блеймлесс-разбор инцидента: системные факторы, не персональные. Машиночитаемый итог — запись incident с ребром fixes от release (D10).

## Как создавать

1. Источники — только существующие данные; каждый факт со ссылкой на источник.
2. Создать (папка по типу: contracts/ для api-contract, ops/runbooks/ для runbook,
   ops/postmortems/ для postmortem):

   ```bash
   todoc docs new --root KB --type postmortem --title "<Название>" --path <путь>/<имя>.md
   todoc validate --root KB --all   # 0 диагностик
   ```

3. Наполнить по шаблону (`.todoc/doc_types/postmortem/template.md`); правки —
   `docs edit --patch-file ... --preview/--apply`; чтение назад — `docs read --section`.

- **Порядок**: запись incident создаётся после утверждения разбора; ребро fixes — от release, когда фикс поедет.
## Запрещённые заглушки

- TBD/TODO; unverified-команды в runbook; Timeline без UTC; Action items без owner/due.

## Самопроверка

- `docs read --section` по каждой обязательной секции; скан заглушек пуст;
  консистентность ID (api-endpoint:/incident:/dep: с записями).
- `todoc validate --root KB --all` — 0 диагностик.

## Именование файла

- Русский `title`, файл — латиница-дефисы; канон: `notes/agent-contract.md`.
