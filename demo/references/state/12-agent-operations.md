---
id: doc:state-agent-ops
title: "Состояние: как агенту работать с todoc"
doc_type: reference
lang: ru
source: docs/state/12-agent-operations.md
copied: true
---
# 12. Как агенту работать с `todoc`

Раздел для агента: последовательности команд, что читать из ответа, чего не делать.

## Базовый цикл

```bash
todoc check-config --root KB                 # конфигурация цела?
todoc index rebuild --root KB                # опубликовать поколение
todoc status --root KB                       # сколько документов и записей
todoc docs search --root KB --query "..." --limit 3
todoc docs read --root KB --id <id> --section "<заголовок>"
```

## Правило чтения: сводка → оглавление → ветка

1. `docs search --limit 3` — кандидаты и фрагменты.
2. `docs read --id <id>` без селектора — заголовок и список разделов (`headings[]` с `line` и `anchor`).
3. `docs read --id <id> --section "<заголовок>"` — только нужный раздел (окно до 40 строк).

Не читайте документ целиком «на всякий случай»: `--budget` ограничивает байты, но не отменяет
стоимость пересборки индекса.

## Что читать из конверта

| Поле | Зачем |
|---|---|
| `ok` | успешность операции; согласован с кодом выхода — при ненулевом коде всегда `false` |
| `data` | полезные данные; состав зависит от команды |
| `diagnostics[]` | проблемы с `code`, `path`, `location`, `evidence` |
| `next_actions[].argv` | готовый массив аргументов следующего шага |

Код выхода важнее текста: 0 успех, 2 использование, 3 валидация, 4 доступ, 5 конфликт, 6 неполнота.

## Стартовые промпты и шаблоны типа

У каждого типа документа и записи в его папке лежат четыре промпта — по одному на операцию.
Берите промпт той операции, которую собираетесь выполнить, а не один общий текст:

```bash
todoc types prompt --root KB guide --op read      # как читать документ этого типа
todoc types prompt --root KB guide --op create    # как создать
todoc types prompt --root KB guide --op edit      # как править (hash-предусловие)
todoc types prompt --root KB guide --op delete    # как снять с публикации
todoc types show --root KB guide                  # пути template/prompts + exists
```

Создание документа — из шаблона типа, а не «с чистого листа»:

```bash
todoc docs new --root KB --type guide --title "Как читать конверт" --dir guides
```

Шаблон подставляет `{title}`, `{slug}`, `{date}`, `{type_id}`, `{id}`, `{format}` как текст.
Если шаблон нарушает структуру своего типа (`required_sections`/`section_rules`), команда
откажет кодом `types.template_invalid` и ничего не запишет — чините шаблон, не обходите проверку.

## Запись: только через предпросмотр

```bash
todoc records create --root KB --type note --input-file note.json --preview
# проверить plan.target_path и plan.new_content
todoc records create --root KB --type note --input-file note.json --apply
```

Правила:

- перезапись существующей записи невозможна (create-only, конфликт → exit 5);
- правка документа — `docs edit --patch-file` с `--preview`, затем `--apply`;
- для защиты от гонок используйте `--if-hash <hash из docs read>`;
- никогда не стройте shell-команду из текста модели и не передавайте секреты аргументами.

## Широкая правка: через изменение

Одиночную правку делайте как раньше — `docs edit` и `fix` работают без церемонии. Но если
правка затрагивает несколько файлов, ведите её как изменение: сначала намерение, потом дельты,
потом применение одной транзакцией.

```bash
todoc change open --root KB --title "Обновить суть" --artifact notes/a.md --artifact notes/b.md
# положить дельты в changes/<change-id>/deltas/*.md
todoc change validate KB:change:obnovit-sut     # применимость к живому состоянию
todoc change apply change:obnovit-sut           # план (review-first)
todoc change apply change:obnovit-sut --apply   # всё или ничего
todoc change verify change:obnovit-sut          # completeness / correctness / coherence
todoc change archive change:obnovit-sut --tag v1.2
```

Порядок обязателен: `validate` до `apply`, потому что он ловит дрейф якоря и `base_hash`
**до** записи, а не после. Если две дельты правят один файл, задайте `order` во front matter —
иначе порядок применения неоднозначен и вы получите `change.apply_order_ambiguous`.

Контекст задачи берите одним вызовом, а не серией чтений:

```bash
todoc context --root KB --change change:obnovit-sut --budget 8000 --with-diff
```

Ответ ограничен бюджетом байт; если кусок не влез, взведётся `truncated` — тогда сузьте
задачу или поднимите бюджет, но не игнорируйте флаг.

Откат — `todoc change revert <id> --apply`: артефакты возвращаются к базовой линии изменения.
Если после применения файл правили ещё раз, `todoc revert` предупредит
`history.range_conflict`: откат возможен, но сотрёт более поздние правки.

## Ремонт

```bash
todoc validate --root KB --all > /tmp/v.json     # ID берём из ЭТОГО вывода
todoc fix --root KB --diagnostic <id> --preview
todoc fix --root KB --diagnostic <id> --apply
```

ID диагностики — SHA-256 от `path + code + message` (`stable_id`), поэтому он одинаков в каждом
запуске и `fix` находит его заново своим сканом. Но он описывает конкретный дефект: как только
файл изменён, прежний ID становится недействительным (`fix.diagnostic_not_found`).

## Диагностика окружения

- `todoc doctor` — только чтение: `config`, `index`, `python`; ничего не чинит.
- `todoc status` — снимок последнего поколения (не пересобирает индекс).

## Как обходить известные проблемы

| Проблема | Обход |
|---|---|
| `--rows` применяется до `--where` | задавать `--rows` с запасом |
| `status` показывает нули до первой пересборки | сначала `index rebuild` |
| Индекс пересобирается на каждую команду чтения | читать пачкой, а не по одному документу |
| Любой `.json` в DATA_ROOT считается записью | входные и временные файлы держать вне DATA_ROOT |

Закрыты и обхода больше не требуют: ID диагностик стабильны между запусками, `--cursor`
продолжает выдачу без повторов, ошибки возвращаются конвертом, запись вне DATA_ROOT
отклоняется (`access.outside_data_root`, exit 4).

## Чего агенту не делать

1. Не удалять и не править `.todoc/` в обход команд, кроме сознательного редактирования типов и правил.
2. Не считать `.todoc/index/` и `.todoc/cache/` источниками истины — они пересобираемые.
3. Не полагаться на `relevance` как на семантическую близость: ранжирование лексическое.
4. Не применять `suggested_fixes` без `--preview` и без проверки `basis`.
5. Не ожидать MCP: в MVP его нет, весь контракт — CLI.

## Связанные разделы

- [03-cli-reference.md](03-cli-reference.md) — точные флаги и формы ответа.
- [06-validation-and-diagnostics.md](06-validation-and-diagnostics.md) — коды и фиксы.
- [11-known-issues.md](11-known-issues.md) — что пока сломано.
