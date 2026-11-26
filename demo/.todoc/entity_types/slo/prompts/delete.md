# Удаление: `slo`

Прямой команды `records delete` нет: убрать файл `records/slos/<slug>.json` одним изменением, затем `validate --all` — 0 диагностик; consumers (`depends_on`/`belongs_to`) перевести раньше.
