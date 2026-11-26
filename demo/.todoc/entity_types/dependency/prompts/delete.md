# Удаление: `dependency`

Прямой команды `records delete` нет: убрать файл `records/dependencies/<slug>.json` одним изменением, затем `validate --all` — 0 диагностик; consumers (`depends_on`/`belongs_to`) перевести раньше.
