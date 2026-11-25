# Чтение: `bug-report`

Баг-репорт читается по секциям — как обычный markdown-документ.

## Команды

```bash
# Карта репорта: заголовки и мета
todoc docs read --root KB --id doc:bugs/<файл>

# Конкретная секция (окно до 40 строк; смотри флаг truncated, дальше — --line-range)
todoc docs read --root KB --id doc:bugs/<файл> --section "Доказательства"

# Статус и критичность — во front matter: см. ответ docs read (поле front_matter
# попадает в индекс; для файла — docs read без --section, поле text содержит шапку)
```

## Подсказки

- Список всех репортов и статусов: `todoc docs search --root KB --type bug-report --query "BUG-" --limit 20`
  или `todoc docs tree --root KB --within bugs`.
- Доказательства не воспроизводятся? Сначала воспроизведи шаги из репорта,
  потом делай выводы; расхождение — новый репорт или дополнение этого.
