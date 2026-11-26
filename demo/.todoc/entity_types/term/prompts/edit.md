# Правка: `term`

Термин — живой словарный объект, но правки консервативны: глоссарий — нормативный
словарь датасета. Правка — review-first: patch + предпросмотр + hash.

## Типичные правки

- **Уточнение определения**: только вместе с glossary-страницей (source_path) —
  одна правка = один патч, определение и витрина синхронны.
- **Алиасы**: добавление фактического варианта имени (`aliases[]`).
- **Рёбра**: `part_of` — по иерархии из факта; `uses_term` добавляет не термин,
  а потребляющая запись (у термина ребро не редактируется).

## Как

```bash
todoc records read --root KB --id term:<slug> --output json      # текущий hash/содержимое
# подготовить patch-file с построчными заменами
todoc docs edit --root KB --id <document_id> --patch-file patch.txt --preview
todoc docs edit --root KB --id <document_id> --patch-file patch.txt --apply --if-hash <hash>
```

Поля `record_id`/`entity_type` не меняются (идентичность термина); slug переименованием
не правится — вместо этого новая запись + supersedes/удаление старой.
