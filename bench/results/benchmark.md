# Бенчмарк todoc

Дата: 2026-11-25 15:08:53 · датасет: `/tmp/todoc-bench-corpus` · документов: 256 · записей: 159

**Итоговый балл: 29.5 из 30** (98%)

## Контракт

| ID | Критерий | Статус | Балл | Детали |
|---|---|---|---|---|
| K1 | stdout — ровно один JSON-конверт | pass | 1.0 | exit=0, ключи конверта совпадают: True |
| K2 | Стабильные коды выхода (3 = валидация) | pass | 1.0 | docs read для неизвестного id → exit 3, traceback=False |
| K3 | Ошибка использования → exit 2 | pass | 1.0 | отсутствие обязательного --id → exit 2 |
| K4 | next_actions: ключ всегда, подсказка при успехе и при диагностике | pass | 1.0 | ключ есть везде: True; успех→1, validate→1 (диагностик: 11) |
| K5 | Discovery: types guide описывает типовую систему | pass | 1.0 | символов в guide: 2819 |

## Корректность

| ID | Критерий | Статус | Балл | Детали |
|---|---|---|---|---|
| K6 | Детекция дефектов: precision/recall на seeded-корпусе | pass | 1.0 | precision=1.00, recall=1.00, F1=1.00; TP=9, FN=0, FP=0 |
| K7 | Точные локации (line/column) у диагностик | partial | 0.55 | 6 из 11 диагностик имеют номер строки |
| K8 | Front matter совместим с внешним YAML-парсером | pass | 1.0 | PyYAML: 90 файлов разобрано, 0 с ошибкой |
| K9 | Присвоение doc_type: front matter важнее маски папки | pass | 1.0 | doc_type=guide, rule_source=rule:fm-guide |
| K10 | Валидация записей: схема, тип, целостность отношений | pass | 1.0 | отказы записи: [('missing_field', 'record.schema_violation'), ('unknown_type', 'record.unknown_entity_type')]; файл не создан: True; коды отношений: ['relation.dangling_target', 'relation.unknown_type'] |

## Детерминизм

| ID | Критерий | Статус | Балл | Детали |
|---|---|---|---|---|
| K11 | Повторный scan даёт идентичные данные | pass | 1.0 | совпало: True, размер данных: 102 байт |
| K12 | Чтение не изменяет источники (инвариантность хешей) | pass | 1.0 | изменено: 0, добавлено: 0 |
| K13 | Идентификаторы диагностик стабильны между запусками | pass | 1.0 | тела диагностик идентичны: True; id совпали: True |

## Безопасность

| ID | Критерий | Статус | Балл | Детали |
|---|---|---|---|---|
| K14 | preview не пишет файлы и показывает план | pass | 1.0 | target=records/note/note-bench-safety-f2e9c540.json, файлов изменено: 0 |
| K15 | create-only: повторная запись → конфликт (exit 5) | pass | 1.0 | первая запись exit=0, повторная exit=5 |
| K16 | Containment: --out не пишет вне DATA_ROOT | pass | 1.0 | файл вне корня создан: False, exit=4 |

## Чтение

| ID | Критерий | Статус | Балл | Детали |
|---|---|---|---|---|
| K17 | Чтение без селектора: заголовок и оглавление | pass | 1.0 | заголовков: 69, текст: 4000 символов |
| K18 | Чтение раздела возвращает только раздел (≤40 строк) | pass | 1.0 | раздел '0. Аудит plan.md: цели, возмож': 40 строк |
| K19 | --budget ограничивает объём ответа | pass | 1.0 | возвращено 500 символов при бюджете 500 |
| K20 | JSON Pointer (RFC 6901): значение, вложенность, ошибка | pass | 1.0 | /record_id → 'competitor:anythingllm' (ожидалось 'competitor:anythingllm'); /no_such_field → exit 3 |
| K21 | CSV-проекция: колонки и строки | pass | 1.0 | строк: 5, колонок: ['doc_id', 'doc_type'] |

## Поиск

| ID | Критерий | Статус | Балл | Детали |
|---|---|---|---|---|
| K22 | Recall@3 и MRR на размеченных запросах | pass | 0.97 | Recall@3=0.94, Precision@3=0.94, MRR=1.00, запросов: 12 |
| K23 | Ранжирование детерминировано | pass | 1.0 | порядок совпал: True, результатов: 5 |
| K24 | Пагинация через --cursor продолжает выдачу без повторов | pass | 1.0 | cursor=2, вторая страница вернула 2 из total=33, пересечений с первой: 0 |

## Устойчивость

| ID | Критерий | Статус | Балл | Детали |
|---|---|---|---|---|
| K25 | Враждебный ввод не роняет CLI | pass | 1.0 | exit=3, конверт: True, traceback: False |
| K26 | Некорректные аргументы → конверт, а не traceback | pass | 1.0 | --cursor abc: exit=3, traceback=False; --line-range abc: exit=3, traceback=False |

## Производительность

| ID | Критерий | Статус | Балл | Детали |
|---|---|---|---|---|
| K27 | Латентность команд в пределах бюджета | pass | 1.0 | команд вне бюджета: 0 из 6; медианы: status=156мс, types list=150мс, docs search=646мс, docs read=232мс, records list=256мс, validate=1046мс |

## Качество кода

| ID | Критерий | Статус | Балл | Детали |
|---|---|---|---|---|
| K28 | Тестовый набор проходит | pass | 1.0 | 883 passed |
| K29 | Покрытие кода тестами | pass | 1.0 | покрытие 100%, пропущено инструкций: 0, веток: 0 |

## Портабельность

| ID | Критерий | Статус | Балл | Детали |
|---|---|---|---|---|
| K30 | 8 подкритериев портабельности (максимум 8) | pass | 1.0 | plain-files=да, no-database=да, derived-ignored=да, yaml-front-matter=да, relative-links=да, git-diffable=да, no-vendor-dirs=да, documented-types=да |

## Конкуренты (установленные)

```json
{
  "obsidiantools": {
    "elapsed_s": 7.231,
    "notes": 91,
    "local_md_links": 286,
    "broken_links_detected": 1,
    "broken_samples": [
      "broken-link -> does-not-exist.md"
    ],
    "backlinks": 89,
    "isolated_notes": 87,
    "front_matter_index": 89,
    "available": true,
    "front_matter_warnings": 3
  },
  "open-knowledge": {
    "available": true,
    "commands": {
      "help": {
        "exit_code": 0,
        "elapsed_s": 0.553,
        "stdout_bytes": 4967,
        "stderr_bytes": 0,
        "first_line": "Usage: open-knowledge [options] [file | command]"
      },
      "status": {
        "exit_code": 0,
        "elapsed_s": 0.611,
        "stdout_bytes": 40,
        "stderr_bytes": 0,
        "first_line": "server  not running"
      },
      "diagnose": {
        "exit_code": 1,
        "elapsed_s": 0.543,
        "stdout_bytes": 0,
        "stderr_bytes": 714,
        "first_line": ""
      }
    },
    "version": "0.28.2",
    "subcommands": 12,
    "writes_into_corpus": []
  },
  "open-knowledge-capabilities": {
    "validate": false,
    "search": true,
    "index": false,
    "mcp": true,
    "skills": true,
    "sync": true,
    "ui": true,
    "graph": false,
    "types": false,
    "records": false
  }
}
```

