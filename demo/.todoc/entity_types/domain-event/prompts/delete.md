# Удаление: `domain-event`

Прямой команды `records delete` нет: убрать файл `records/events/<slug>.json` одним изменением, затем `validate --all` — 0 диагностик; consumers (`depends_on`/`belongs_to`) перевести раньше.
