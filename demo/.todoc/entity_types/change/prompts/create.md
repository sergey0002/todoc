# Создание: `change`

Изменение: движок-контракт жизненного цикла (application/changes.py) плюс опциональная OpenSpec-дельта требований (requirements_delta SHALL).

## Два пути создания

1. **Рабочий (основной)** — движок создаёт папку и запись сам:

   ```bash
   todoc change open --root KB --title "<что меняется>"
   ```

   `change_id` = `change:<транслитерация заголовка>` (slugify); рядом создаются
   `proposal.md`, `tasks.md` (fm `doc_type: note`) и `deltas/`. Зависимость от
   другого изменения — `change open --blocked-by change:<slug>`.

2. **Capture-уровень (OpenSpec-интероп)** — заполнить `requirements_delta`:
   SHALL-строки из дифа требований по операциям `added`/`modified`/`removed`.
   Правка через `docs edit --preview/--apply` по `document_id` записи.

## Правила качества

- Заголовок — «что меняется», глагол + объект; slug переименованию не подлежит.
- Статусы — только из STATUS_FLOW движка; движок сам ведёт `created_at`/`applied_at`.
- `requirements_delta` заполняется только из фактического дифа, не из памяти.

## Запрещённые заглушки

- TBD/TODO в SHALL-строках; «улучшить» без критерия. Нет дифа — поля нет.

## Самопроверка

- `todoc change show --root KB --id <record_id>` читает запись и дельты.
- `todoc validate --root KB --all` — 0 диагностик.
