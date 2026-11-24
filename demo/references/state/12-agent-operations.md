---
id: doc:state-agent-ops
title: Состояние: как агенту работать с todoc
doc_type: reference
lang: ru
source: .doc/state/12-agent-operations.md
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
| `ok` | успешность операции (но см. `check`: при ошибках пока возвращает `true`) |
| `data` | полезные данные; состав зависит от команды |
| `diagnostics[]` | проблемы с `code`, `path`, `location`, `evidence` |
| `next_actions[].argv` | готовый массив аргументов следующего шага |

Код выхода важнее текста: 0 успех, 2 использование, 3 валидация, 4 доступ, 5 конфликт, 6 неполнота.

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

## Ремонт

```bash
todoc validate --root KB --all > /tmp/v.json     # ID берём из ЭТОГО вывода
todoc fix --root KB --diagnostic <id> --preview
todoc fix --root KB --diagnostic <id> --apply
```

ID диагностики живёт только в рамках одного запуска `validate` — не сохраняйте его между вызовами.

## Диагностика окружения

- `todoc doctor` — только чтение: `config`, `index`, `python`; ничего не чинит.
- `todoc status` — снимок последнего поколения (не пересобирает индекс).

## Как обходить известные проблемы

| Проблема | Обход |
|---|---|
| ID диагностик нестабильны | выполнять `validate` и `fix` в одном сценарии, ID не кэшировать |
| `--cursor` не работает | увеличивать `--limit` вместо пагинации |
| `--rows` до `--where` | задавать `--rows` с запасом |
| `status` показывает нули | сначала `index rebuild` |
| ошибки без конверта | проверять код выхода и stderr, а не только stdout |
| запись вне корня возможна | не передавать `--out`/`--dir` с `..` и абсолютными путями |

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
