---
title: "План завершения остатка аудита CLI todoc"
date: 2026-11-28
status: "ready: обязательный объём P1–P2; P3 — по решению"
scope: "src/todoc, tests, docs/state; только неисправленные пункты"
sources:
  - ../demo/plan/open-bug-backlog-closure.md
  - ../demo/notes/unified-cli-release.md
  - ../docs/plan/todoc-master-refactoring-plan.md
  - ../docs/state/03-cli-reference.md
  - ../docs/installation.md
---

# План завершения остатка аудита CLI todoc

> Выпуск v2 и правки R1–R4 закрыли конверт, вывод, обзор, курсоры,
> публикацию индекса, create-only и чтение без записи. Ниже — проверенный
> остаток. **Для завершения обязательны только P1 и P2**; P3 — улучшения,
> которые не блокируют закрытие аудита.

> **2026-11-28 — консолидация.** Исходный `.doc/cli_audit.md` удалён: карта
> «закрыто, не переоткрывать», воспроизведения и полный остаток R-A…R-I
> перенесены в [план закрытия бэклога](../demo/plan/open-bug-backlog-closure.md)
> §9. Часть воспроизведений в §1.1 ниже устарела (обход `change_id` больше не
> читает внешний файл, `skills import --into` отклоняется) — актуальный статус
> в §9.2 плана. История удалённого файла — в Git (`d45a064` и рабочее дерево).

## 1. Остаток, подтверждённый кодом

| Пункт | Факт | Место |
|---|---|---|
| `change_id` без грамматики | `change_dir` берёт `change_id.split(":", 1)[-1]` как сегмент пути; `archive_change` строит из него цель `rename`; CLI передаёт аргумент без проверки | [`changes.py:83`](../src/todoc/application/changes.py), [`changes.py:89`](../src/todoc/application/changes.py), [`changes.py:651`](../src/todoc/application/changes.py), [`cli.py:1413`](../src/todoc/cli.py) |
| `derived_from` вне root | `fragment_hash` и `collect_owners` читают `root / rel` без `is_within_root`; путь приходит из front matter/данных | [`staleness.py:62`](../src/todoc/application/staleness.py), [`staleness.py:207`](../src/todoc/application/staleness.py) |
| `plan_ack` теряет CRLF | `splitlines()` + `"\n".join` пересобирает тело; без front matter бросает `ValueError`; `_stale_ack` его не ловит | [`staleness.py:256`](../src/todoc/application/staleness.py), [`cli.py:896`](../src/todoc/cli.py) |
| `missing_root` exit 3 | `resolve_roots` бросает `ValidationError` (exit 3), документация обещает exit 2, тест фиксирует 3 | [`service.py:310`](../src/todoc/service.py), [`installation.md:145`](../docs/installation.md), [`test_cli.py:295`](../tests/cli/test_cli.py) |
| `validate --all` не используется | `all_` принимается и не участвует в обработчике; команда всегда проверяет весь корпус | [`cli.py:360`](../src/todoc/cli.py) |
| `table` ≈ `markdown` | Обе «человеческие» ветки строят `key: value`; различие только у `mermaid` | [`envelope.py:61`](../src/todoc/output/envelope.py) |
| Нет stdin | `--patch-file`, `--query-file`, `--input-file` читают только путь; `-` не поддержан | [`cli.py:2601`](../src/todoc/cli.py) |
| Windows-переносимость | BUG-030/032/033 `open`; нет `stdout.reconfigure`; тест отката пишет через `write_text` | [`test_history.py:189`](../tests/unit/test_history.py) |
| Нет метаданных capability | Инвентарь отдаёт пути и параметры, но не `effect/scope/formats/root_policy` | [`capabilities.py`](../src/todoc/output/capabilities.py) |

### 1.1. Воспроизведено на временных данных

| Проверка | Результат |
|---|---|
| `todoc change show --root demo change:../../../../../../tmp/trav` при существующем `/tmp/trav/change.json` | `ok: true`, в ответе заголовок `SENTINEL-OUTSIDE`: файл вне `DATA_ROOT` прочитан |
| `stale` на документе с `derived_from: ["../secret.md@sha256:deadbeef"]` | `staleness.dependency_changed` с фактическим хешем `/tmp/secret.md`: внешний файл прочитан |
| `stale --ack --apply` на CRLF-документе | `HAS_CRLF False`, тело `line-one\r\nline-two\r\n` не сохранено |
| `todoc check` без root | exit 3 и `usage.missing_root`; [`installation.md`](../docs/installation.md) обещает 2 |

Воспроизведения выполнялись в `/tmp` на временных датасетах; живой `demo` не
менялся. Это подтверждает, что P1 и P2 — дефекты, а не косметика.

## 2. Проверка необходимости правок

| Пункт | Вердикт | Обоснование |
|---|---|---|
| `change_id` | **Обязательно** | Путь из пользовательского аргумента попадает в чтение, запись и `rename`. Это дефект безопасности, а не стиль. |
| `derived_from` | **Обязательно** | Путь из данных читает файл вне `DATA_ROOT`; демо не содержит `..`, поэтому ограничение ничего не ломает. |
| `plan_ack` | **Обязательно** | `ValueError` даёт traceback вместо конверта; пересборка текста меняет CRLF. Оба нарушения контракта. |
| `missing_root` exit | **Обязательно** | Код, документация и тест противоречат друг другу; нужно выбрать одно значение и синхронизировать. |
| `validate --all` | **Кода не требуется** | Флаг избыточен, но не вреден: `validate` и так проверяет всё. **Не добавлять `info`-диагностику** — гейты «0 диагностик» считают все диагностики и сломаются. Достаточно уточнить документацию. |
| `skills tree --all` | **Не требуется** | Флаг работает и показывает muted (`cli.py:461`). Переименование в `--include-muted` — косметика, отдельное решение. |
| `table`/`markdown` | **Условно** | Документация обещает только «выбор сериализации», а не разные макеты. Если нужны реальные таблицы — это улучшение, не дефект. |
| stdin | **Условно** | В документации `-` не обещан. Нужен только для пайплайнов агентов. |
| Windows | **Условно** | README и установка не заявляют Windows как поддерживаемую платформу; контрактные проверки идут через WSL. Правки нужны только при официальной поддержке. |
| Capability metadata | **Не требуется** | Инвентарь Click уже даёт контрактный тест путей/опций; метаданные нужны только для будущей валидации по реестру. |
| F-20 теги, F-26 би-темпоральность | **Вне остатка** | Отдельные gates; менять default без решения нельзя. |

**Вывод.** Чтобы «завершить реализацию» аудита, нужно закрыть четыре пункта:
`change_id`, `derived_from`, `plan_ack`, `missing_root`. Остальное — либо
документация, либо отдельные решения.

## 3. Обязательный объём

### P1. Безопасность путей и ошибок

**P1.1. Грамматика и containment `change_id`.**

1. Добавить в [`changes.py`](../src/todoc/application/changes.py) проверку
   `require_change_id(change_id)`: форма `change:<id>`, где `<id>` —
   `[A-Za-z0-9][A-Za-z0-9._-]*`; запрещены `/`, `\`, `..`, пустая строка,
   абсолютный путь. Ошибка — `TodocError(..., EXIT_USAGE, "usage.invalid_id")`.
2. Вызывать её в `change_dir` до построения пути и в CLI до `load_change`,
   `apply_change`, `archive_change`, `revert`.
3. Дополнительно проверять `is_within_root(root, target)` для активной и
   архивной папки; `archive_change` — до `rename`.
4. `log --change` оставить фильтром, но пропускать через ту же грамматику,
   чтобы ошибка не выглядела пустой выборкой.

**Тесты:** `change show --root demo change:../../x` → `usage.invalid_id`,
exit 2; внешний sentinel не читается и не переименовывается; существующий
`change:pilot-profil-dokumentirovaniya-softa` продолжает работать. Сейчас
тот же вызов с существующим файлом вне root отдаёт `ok: true` и его
содержимое.

**P1.2. Containment `derived_from`.**

1. В `fragment_hash` и `collect_owners` резолвить `root / rel` и проверять
   `is_within_root`; для внешнего пути возвращать статус `outside` и
   диагностику `staleness.dependency_outside_root`, не открывая файл.
2. Симлинк внутри root, ведущий наружу, считать внешним.
3. `stale` показывает диагностику, а не молча пропускает зависимость.

**Тесты:** документ с `derived_from: ["../secret.md@sha256:…"]` не читает
внешний файл; обычный `bench/results/benchmark.json#/…` работает как раньше.

**P1.3. `plan_ack` без потери байтов.**

1. Переписать только блок front matter, сохранив тело и переводы строк
   (`\n` и `\r\n`) без изменений; удобнее работать с исходным текстом и
   `keepends`, а не с `splitlines()` + `"\n".join`.
2. Вместо `ValueError` — `TodocError(..., "staleness.no_front_matter")` или
   `ValidationError` с тем же кодом.
3. `_stale_ack` не должен ловить всё подряд; типизированная ошибка доходит до
   `main` и становится конвертом.

**Тесты:** CRLF-файл после `stale --ack --apply` сохраняет CRLF во всём теле;
файл без front matter даёт `ok: false`, не traceback; preview не пишет.

### P2. Согласование кода выхода `usage.missing_root`

Выбрать **exit 2** (рекомендация): код `usage.*` по карте
[`errors.py`](../src/todoc/errors.py) — usage-ошибка, и
[`installation.md`](../docs/installation.md) уже обещает 2.

1. [`service.py:310`](../src/todoc/service.py): `ValidationError` →
   `TodocError(..., EXIT_USAGE, "usage.missing_root")`.
2. [`test_cli.py:295`](../tests/cli/test_cli.py): ожидать 2.
3. Проверить `next_actions`/guidance: код остаётся `usage.missing_root`,
   подсказка уже есть в [`ru.json`](../src/todoc/data/guidance/ru.json).
4. Пройти по документации и убедиться, что нигде не обещан exit 3.

**Тесты:** `check` без root → exit 2 и конверт `usage.missing_root`;
`docs list` без root — то же; `TODOC_ROOT` из разделителей — то же.

## 4. Опциональный объём (P3)

Каждый пункт делается только после решения из §6.

| Пункт | Что сделать | Триггер |
|---|---|---|
| CAS-имена | Добавить `--expected-hash` как алиас скалярного `--if-hash` в `sync`, `docs edit`, `records edit`, `fix`; конфликт явных значений — ошибка; старый синтаксис — диагностика со сроком | Нужен единый контракт для внешних клиентов |
| Форматы | Реальный `table` для списков; `markdown` оставить Markdown; `--output` валидировать по команде | Нужны человекочитаемые таблицы, а не key-value |
| stdin | `-` в `_load_patch_file`, `_query_spec`, `--input-file`; лимит размера и UTF-8 (`usage.input_too_large`, `usage.invalid_encoding`) | Агенты передают данные через пайп |
| Windows | BUG-033: тест на `write_bytes`; BUG-032: POSIX-пути в выводе; BUG-030: `stdout.reconfigure(encoding="utf-8")` | Windows объявлен поддерживаемым |
| Документация `--all` | Уточнить, что `validate` всегда проверяет весь корпус, а `--all` сохранён для совместимости; не добавлять `info` | Всегда, если трогаем этот раздел |
| Capability metadata | `effect`, `scope`, `formats`, `root_policy` + двусторонний тест с Click | Появится валидация по реестру |

## 5. Приёмка

- [ ] `todoc change show --root demo change:../../x` → `usage.invalid_id`,
      exit 2; sentinel не прочитан и не переименован (сейчас читается с
      `ok: true`).
- [ ] `change:../../x` в `apply`, `archive`, `revert` отклоняется до записи.
- [ ] `derived_from` с `..` не читает файл вне root; диагностика видна в `stale`.
- [ ] `stale --ack --apply` на CRLF сохраняет байты тела; без front matter —
      конверт, не traceback.
- [ ] `check`/`docs list` без root → exit 2, `usage.missing_root`; тест и
      документация совпадают.
- [ ] Существующий `demo/changes/pilot-profil-dokumentirovaniya-softa` читается
      и архивируется как раньше.
- [ ] Новые тесты покрывают ветви ошибок и успеха; покрытие не падает.

## 6. Решения

| ID | Вопрос | Рекомендация | Если иначе |
|---|---|---|---|
| D1 | Код выхода `usage.missing_root` | exit 2 (код и docs уже согласны) | Сменить документацию на 3 и оставить `ValidationError` |
| D2 | CAS-имена | Сохранить оба имени, задокументировать смысл; алиас — позже | Единое имя ломает скрипты без миграции |
| D3 | `table`/`markdown` | Оставить как есть, уточнить документацию | Реализовать реальные форматы отдельным PR |
| D4 | Windows | Не заявлять поддержку, пока BUG-030/032/033 открыты | Закрыть три бага и добавить CI-job |
| D5 | stdin | Не добавлять без запроса | Реализовать `-` с лимитом и UTF-8 |

## 7. Гейты

```bash
cd /home/newuser/projects/todoc
env PYTHONPATH=src python3 -m pytest -q
env PYTHONPATH=src python3 -m coverage run --branch -m pytest -q
python3 -m coverage report --fail-under=100
python3 tools/linkcheck.py
env PYTHONPATH=src python3 -m todoc validate --root demo --all
git diff --check
```

Мутирующие проверки — только на временных датасетах (`tmp_path`), не на
живом `demo`.

## 8. Риски

- **Смена exit code** ломает скрипты, которые проверяют `3`. Обновить тесты и
  документацию в том же изменении.
- **Строгая грамматика `change_id`** может отвергнуть нестандартные, но
  безопасные ID. Поэтому грамматика разрешает `[A-Za-z0-9._-]`, а не только
  нижний регистр; `..` и разделители пути запрещены отдельно.
- **Containment `derived_from`** может сломать легитимные внешние зависимости.
  В демо таких нет; если появятся — вводить явную роль `external_dependency`,
  а не ослаблять проверку.
- **`plan_ack`** легко снова нормализовать при рефакторинге: тест на CRLF
  должен проверять байты, а не строку.
- **`validate --all`**: любая `info`-диагностика сломает гейты «0 диагностик»;
  менять только текст документации.

## 9. Что считать завершением

Аудит закрыт, когда выполнены P1 и P2, зелёные гейты §7 и принято решение по
D1. P3 не входит в закрытие: это отдельные улучшения, каждое со своим
триггером и PR.
