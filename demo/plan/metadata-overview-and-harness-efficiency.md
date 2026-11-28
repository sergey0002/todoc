---
id: doc:plan/metadata-overview-and-harness-efficiency.md
title: "Обзор знаний за один запрос: метаданные, статусы и экономный маршрут агента"
doc_type: plan
lang: ru
created: 2026-11-27
updated: 2026-11-28
status: superseded
derived_from: ["bugs/bug-022-no-type-overview-query.md@sha256:518608bdc1cbfb9b422f0035114fafc6f5dd43cb1a060dde21611cc0b6db071a"]
tags: [plan, cli, metadata, status, harness, performance]
related: ["[[bug-022-no-type-overview-query]]", "[[unified-cli-release]]", "[[bmad-wave-planning-skills]]"]
---

> **Историческое исследование.** Реализация объединена с единым CLI.
> Приёмка и ссылка на закрытый план в Git находятся в [сводке выпуска](../notes/unified-cli-release.md).
> При работе используйте [актуальный CLI](../references/state/03-cli-reference.md).


# Обзор знаний за один запрос: метаданные, статусы и экономный маршрут агента

> Результат для пользователя: вопрос «какие идеи не выполнены?» получает полный
> список со статусами и источниками за один запрос данных после discovery.
> Ошибка первой команды не превращается в двадцать одинаковых ошибок.
> Основание — BUG-022; планирование запрошено 2026-11-28.
> На момент исследования команды docs list не было. Текущий выпуск содержит обзор.

**Цель:** устранить N отдельных чтений документов для обзора типа и доказать стоимость сценария на воспроизводимой проверке CLI и маршрута агента.
**Спека:** [BUG-022](../bugs/bug-022-no-type-overview-query.md), особенно «Повторный эпизод 2026-11-28».
**Стек:** Python 3.11+, Click, существующий парсер Markdown, pytest/coverage; без новых runtime-зависимостей.
**Статус:** active означает готовность плана к последующему исполнению, а не начало реализации.

## 1. Критерии успеха

1. Один вызов ниже возвращает все 20 идей контрольного снимка: 11 captured,
   2 planned, 6 done, 1 null. Агент сообщает 14 незавершённых/несогласованных,
   отдельно оговаривая отсутствие статуса. Эти числа — fixture эпизода, не
   вечные счётчики live demo. CLI не зашивает слово idea или «не выполнено».

~~~bash
todoc docs list --root demo --type idea --fields id,path,title,status --limit 100
~~~

2. Отбор по метаданным не вызывает docs read/search для каждого результата.
   Холодный запуск вправе разобрать файлы один раз внутри единого снимка;
   это не обещание нулевого файлового I/O. Актуальный снимок переиспользуется.
3. total/returned/truncated/next_cursor и область выборки достоверны;
   потеря файла/ошибка парсинга не превращаются в «полный список».
   При отсутствии fm status возвращается null, parse_status="ok" не означает done.
4. Весь stdout — один JSON-конверт; JSON/Markdown/table сохраняют одни факты.
   Цель объёма выбранной проекции: ≤ 12000 UTF-8 байт на fixture из 20 идей.
   Цель ≤ 2000 токенов проверяется только указанным в отчёте токенизатором;
   при его отсутствии поле tokens=null, а токенный гейт честно не измерен.
5. Новый read-путь не меняет corpus/index/cache/history/state/XDG.
   Для cold/stale/corrupt индекса это проверяется отдельно.
6. Scripted conformance подтверждает контракт команд; реальный LLM-прогон,
   если выполнен, отдельно подтверждает следование маршруту.
   Инструкция сама по себе не является техническим запретом ошибочного пакета.

## 2. Вне скоупа

- Полная переделка CLI, деревьев/графов, всех команд discovery и общего schema_version.
- SQLite/FTS5/BM25, полный storage seam, новые драйверы истории, мультипроектность.
- Полная система tags/has_tag, folderize/docs move и агентская автономная запись.
- Полный logging/trace и учёт API usage: измерительный стенд пишет только свой
  явно указанный отчёт; обычный read ничего не логирует на диск.
- Массовая смена статусов идей и устранение расхождений текста/fm во всём корпусе.
- Реализация, коммиты, ветки и публикация в рамках текущего запроса составить план.

## 3. Глобальные ограничения

- «Файлы — источник истины; индекс и кэш — производные и пересобираемые.»
- «Никаких фоновых процессов, скрытой сети и eval; каждый шаг воспроизводим.»
- «JSON stdout — ровно один JSON»; next_actions[].argv — данные, не shell.
- «Все предусмотренные поля выдаются по умолчанию; проекции задаёт пользователь.»
- «Только запрошенная выборка: фильтрация до лимита, явное усечение».
- «Проходят полный pytest, 100% branch coverage, todoc validate --root demo --all
  без диагностик и tools/linkcheck.py без битых ссылок».
- Любые изменения demo — CLI, preview → apply → обратное чтение → validate.
- Чужие импортированные superpowers-скилы не менять. Диспетчер и собственные
  todoc-docs/agent-contract — допустимые точки адаптации.
- Статус fixed/done не выставлять автоматически; закрытие BUG-022 — после
  проверки результата и явного подтверждения пользователя.

## 4. Архитектура и файловая карта

### 4.1. Что исследовано и как это меняет решение

| Источник | Вывод | Применение |
|---|---|---|
| [BUG-022](../bugs/bug-022-no-type-overview-query.md), разделы «Воздействие», «Повторный эпизод» | 54 запуска, 20 неверных + 20 отдельных корректных read | З1 baseline, З3 список, З6 маршрут |
| [BUG-021](../bugs/bug-021-usage-errors-without-guidance.md) | Ошибки ведут на общий help, нет конкретного исправления | З5 локальная guidance |
| [BUG-028](../bugs/bug-028-no-runtime-contract-for-windows-wsl-harness.md) | Не определён единый запуск PowerShell/WSL | З6 argv и проверка реальной среды |
| [Идея единого CLI](../ideas/unified-cli-output.md), «Принципы», «Поля, ограничения и фильтры» | Все поля по умолчанию; явная проекция; отбор до лимита | Не скрывать поля ради метрики; --fields и общий pipeline |
| [План единого CLI](../notes/unified-cli-release.md), §4, З0-S, З2–З5, З9 | Уже владеет общей архитектурой views/capabilities/read-only/миграции | Этот план — ограниченный инкремент З3/З5/З9, а не второй универсальный CLI |
| [Guidance/i18n](../ideas/cli-model-guidance-and-hint-catalog.md), «Предложение» | Коды отдельно от текстов; compact при успехе | З5 использует один каталог и envelope |
| [План волн](bmad-wave-planning-skills.md), З2–З3 | Уже планирует guidance и несколько id у docs status | Пакетный status не заменяет фильтр типа; ядро guidance не реализовывать дважды |
| [Теги](../ideas/unified-tags-and-tag-graph.md), «Принципы» | Таксономия отличается от history tag | Пока только существующие fm tags; будущие has_tag не выдумывать |
| [Типизированное дерево](../ideas/typed-tree-projection.md), «Суть» | Иерархическая проекция — самостоятельное развитие | docs list остаётся flat; дерево не требуется для списка статусов |
| [SQLite](../ideas/sqlite-storage-drivers.md), «Суть» | Хранение должно быть заменяемым | Чистый фильтр получает dict-снимок, не открывает JSON/SQLite |
| [Логирование](../ideas/action-logging.md), «Суть» | Измерения нужны, но логи вне знаний | Стенд с явным --report; runtime trace не внедрять |
| [Конституция](constitution.md), P12/P13/P15 | Offline, объяснимость, прогрессивная опора | Без web/LLM в read; guidance и ссылки на источники |
| [Контракт агента](../notes/agent-contract.md), «Что агент может считать стабильным» | Стабильные коды, argv-массивы | Проверки реального subprocess, не только CliRunner |

Проверенный код на 2026-11-28:
- src/todoc/domain/models.py:74–105: Document.status — технический статус файла.
- src/todoc/service.py:52–100: scan_and_validate уже имеет front_matter,
  но сохраняет только title и технический status в Document.
- src/todoc/service.py:190–218: ensure_index при cache miss публикует индекс,
  статистику и observed history; нельзя назвать новый список чистым read,
  просто вызвав ensure_index.
- src/todoc/application/validator.py: путь parse cache содержит write_parse_cache.
  In-memory snapshot должен отключать и эту вложенную запись.
- src/todoc/cli.py:1265–1373: search требует query; read повторяет lines/text.
- src/todoc/cli.py:1472 и src/todoc/output/envelope.py:12: дерево и конверт
  требуют явной проекции, а не ошибочного толкования status.
Номера — навигация по текущему checkout; перед исполнением сверять определения.

### 4.2. Выбранный подход и альтернативы

Выбран аддитивный docs list с метаданными и общими чистыми примитивами;
существующие search/read продолжают работать. Это закрывает пользовательский
сценарий без ожидания всей перестройки CLI. Отказ от обязательного query в
search смешал бы лексический поиск и перечисление; batch read оставил бы
лишние тела, догадки о полях и затратный маршрут.
Полная миграция envelope v2 и переименование старого tree.status принадлежат
плану единого CLI. Здесь новые результаты однозначны: status — жизненный цикл,
parse_status — техническое состояние; старый tree.status не переопределяется молча.

### 4.3. Контракт данных и CLI

Внутри снимка добавить lifecycle_status: str|null, tags: list[str],
updated: str|null к документу; прежний status="ok" сохраняет технический смысл.
Публичный новый элемент: id, dataset_id, path, title, doc_type, status,
parse_status, tags, updated, hash. id — реальный document_id, не догадка из пути.
Отсутствующий/пустой fm status → null; неверный тип → диагностика metadata.invalid_status.
Массово исправлять исходники нельзя.

~~~text
docs list --root ROOT [--type TYPE] [--within DIR] [--tag TAG]
          [--status VALUE ...] [--status-missing]
          [--fields a,b] [--exclude-fields a,b]
          [--limit N] [--cursor CURSOR] [--output json|markdown|table]
~~~

Повтор --status = OR; --status-missing добавляет null в то же OR.
Остальные фильтры соединяются AND, тег точный; within сравнивается по компонентам
пути, а не строковому префиксу. limit default=50, диапазон 1..1000.
Незнакомое значение статуса разрешено как точное значение, поскольку enum
принадлежит типу; нет совпадений → полная пустая выборка. Незнакомый type/field,
конфликт include/exclude, limit=0 → явная ошибка с guidance.
id/path — обязательные поля выбранной файловой формы.

data = {dataset_id, items, total, returned, truncated, next_cursor,
snapshot_digest, scope:{within,doc_type}, complete}.
total — число совпадений ДО страницы, complete — полнота сборки источника,
truncated — наличие следующей страницы. complete=false не подменяет cursor.
Сортировка (path,id); cursor содержит версию, digest и fingerprint фильтров,
проверяется на подмену области/устаревание. Это токен навигации, не средство ACL.
Смена полей/формата допустима между страницами; смена фильтра/snapshot — ошибка.
Невозможность прочесть/разобрать источник → diagnostics, complete=false,
ok=false и exit 6; не выдавать частичный список за полный.

--fields применяется к items, а не удаляет метаданные полноты и guidance.
У list нет тела по определению; все перечисленные поля метаданных включены
без --fields. Дублирование lines/text в старом read устраняется явной
проекцией --fields/--exclude-fields, не незаметной потерей legacy-поля.

### 4.4. Файлы и владельцы общих частей

| Файл | Изменение и ответственность |
|---|---|
| src/todoc/domain/models.py | Аддитивные метаданные документа |
| src/todoc/service.py | read_index и перенос fm в снимок |
| src/todoc/application/validator.py, registry.py | Режим parse cache без записи; версия метаданных снимка |
| src/todoc/application/documents.py (новый) | Чистый list_documents, фильтры, страница |
| src/todoc/output/views.py (новый или существующий после merge) | Общая project_fields из большого плана; не вторая реализация |
| src/todoc/output/capabilities.py (новый или существующий) | Поля и опции docs list/read, локальное discovery |
| src/todoc/output/envelope.py, cli.py | Тонкий обработчик, проекции, guidance, ошибки Click |
| src/todoc/output/guidance.py, resources/guidance/ru.json | Загрузчик и компактный каталог P15 из плана волн |
| SKILL.md, src/todoc/data/agent-skill/todoc/SKILL.md | Собственный диспетчер, маршрут обзора |
| demo/skills/docs/todoc-docs/SKILL.md, demo/notes/agent-contract.md | Канонические правила чтения/проверки |
| tools/eval_metadata_overview.py (новый) | Offline-измерения на временных fixture, явный отчёт |
| tests/unit/test_document_metadata.py, test_document_listing.py | Метаданные, чистые фильтры и курсоры |
| tests/cli/test_cli_docs_list.py, test_metadata_read_only.py | CLI/совместимость/отсутствие записи |
| tests/cli/test_overview_guidance.py, test_metadata_overview_e2e.py | Ошибки, форматы и сценарий |

Перед реализацией проверить текущую ветку: если views/capabilities/guidance/read_index
уже появились из связанных планов, расширять их, а не копировать под новыми именами.
З0-S большого плана остаётся владельцем storage seam; этот инкремент не объявляет
его исполненным. При интеграции через готовый seam вызывать его snapshot API.

## 5. Задачи

Каждый цикл: написать указанные проверки → запустить до изменения (FAIL по
ожидаемой причине) → реализовать интерфейс → повторить (PASS). Отмечать только
проверенные шаги. Коммит возможен при отдельной авторизации и прохождении гейтов.

### Задача 1: Контрольный корпус и измеримый baseline

**Файлы:** создать tests/cli/test_metadata_overview_e2e.py,
tools/eval_metadata_overview.py; использовать tests/conftest.py:root.
**Consumes:** существующий subprocess python -m todoc.
**Produces:** build_overview_fixture(root: Path) -> dict[str, str] в новом
тестовом модуле; 20 Markdown-идей и правила типа через init/fixture API.
Стенд: main() -> None с --root (только временный fixture), --report PATH.

- [ ] Fixture содержит 11 captured, 2 planned, 6 done, 1 отсутствующий status,
  один custom id, русские title и вложенные ideas/archive/; не копировать live demo.
- [ ] Сохранить baseline: команды, exit, stdout_bytes, stderr_bytes, wall_ms,
  успешно выполненные/ошибочные вызовы отдельно, Python/OS/commit.
  Токены — только с названием/версией токенизатора, иначе null.
- [ ] Тест сценария: ожидаемый docs list пока не существует; FAIL из-за команды,
  а не из-за сломанной fixture.
- [ ] Верификация: .venv/bin/python -m pytest tests/cli/test_metadata_overview_e2e.py -q.
  На этом этапе зафиксировать ожидаемый FAIL; финальный PASS — З7.

### Задача 2: Метаданные в актуальном снимке без скрытых записей

**Файлы:** изменить models.py:74–105, service.py:52–100,190–218,
application/validator.py и registry.py; тесты test_document_metadata.py,
test_metadata_read_only.py.
**Consumes:** существующие validate_dataset, corpus_digest, RegistryStore.
**Produces:** DatasetContext.read_index() -> dict[str, Any];
scan_and_validate(..., *, read_only: bool = False) с существующим возвратом,
который переносит lifecycle_status/tags/updated из уже разобранного fm.
Параметр read_only проходит до parse cache; запись запрещена во всех вложенных путях.

- [ ] Проверки: одинаковые id/title/lifecycle_status в fresh/missing/stale/corrupt
  индексе, custom id сохраняется, null отличается от строкового "null".
  Старый снимок без новых полей несовместим и пересобирается в памяти.
- [ ] Снимки root/index/cache/history/state/XDG до и после read_index побайтово
  равны; перехват write_parse_cache/publish/write_stats/observe_history запрещает
  вызовы записи даже если итоговый файл совпал бы.
- [ ] Реализовать read_index: проверить fingerprint данных/конфига и версию
  метаданных; reuse только валидного снимка, иначе сбор в памяти с диагностиками.
  Явные write/rebuild используют существующий путь публикации.
- [ ] Проверки на исчезновение файла во время scan и неверный тип status:
  incomplete/диагностика, а не молчаливое исключение.
- [ ] Run: .venv/bin/python -m pytest tests/unit/test_document_metadata.py
  tests/cli/test_metadata_read_only.py -q; ожидается PASS.

### Задача 3: Чистая обзорная выборка и курсор

**Файлы:** создать application/documents.py и tests/unit/test_document_listing.py.
**Consumes:** dict-снимок с corpus_digest и полями З2.
**Produces:** list_documents(payload: dict[str, Any], *, doc_type: str | None = None,
within: str | None = None, tag: str | None = None, statuses: tuple[str, ...] = (),
include_missing_status: bool = False, limit: int = 50, cursor: str | None = None)
-> dict[str, Any]. Функция не читает файлы и не открывает backend.

- [ ] Минимальная проверка чистого интерфейса:

~~~python
from todoc.application.documents import list_documents

def test_filter_before_limit():
    payload = {"dataset_id": "d", "corpus_digest": "sha256:fixture",
               "diagnostics": [], "documents": [
        {"document_id": "doc:a", "path": "ideas/a.md", "doc_type": "idea",
         "title": "Готово", "status": "ok", "lifecycle_status": "done"},
        {"document_id": "custom:b", "path": "ideas/b.md", "doc_type": "idea",
         "title": "Открыто", "status": "ok", "lifecycle_status": "captured"}]}
    page = list_documents(payload, doc_type="idea", statuses=("captured",), limit=1)
    assert page["total"] == 1
    assert page["items"][0]["id"] == "custom:b"
    assert page["items"][0]["status"] == "captured"
    assert page["items"][0]["parse_status"] == "ok"
    assert page["truncated"] is False
    assert page["next_cursor"] is None
~~~

- [ ] Добавить проверки null/OR/AND, пустой выборки, нескольких страниц,
  границы ideas vs ideas-old, одинаковых title, 51/501 элементов,
  повторного и подменённого cursor, смены snapshot/конфига.
- [ ] Реализовать filter → stable sort → paginate; данные и total до проекции.
- [ ] Run: .venv/bin/python -m pytest tests/unit/test_document_listing.py -q;
  ожидается PASS, обход страниц не теряет и не повторяет id.

### Задача 4: docs list, поля и совместимость чтения

**Файлы:** cli.py:до docs search, output/views.py, output/capabilities.py;
создать tests/cli/test_cli_docs_list.py.
**Consumes:** read_index и list_documents.
**Produces:** Click docs_list обработчик контракта §4.3; общая функция
project_fields(item: dict[str, Any], include: tuple[str, ...],
exclude: tuple[str, ...], *, allowed: frozenset[str],
structural: frozenset[str]) -> dict[str, Any] (сигнатура большого плана).

- [ ] Тест CliRunner и subprocess с fixture: одна команда даёт все 20;
  Counter(status) = captured:11, planned:2, done:6, None:1;
  каждый элемент содержит источник, нет snippet/text/lines.
- [ ] --fields id,path,title,status оставляет эти поля; все поля по умолчанию;
  структурные id/path не удаляются, неизвестный field и конфликт флагов — ошибка.
- [ ] --exclude-fields text у docs read --line-range 1-20 сохраняет lines;
  legacy read без проекции не теряет поля; docs list не вызывает docs_read.
- [ ] Обработать limit=0/-1, cursor не от этой команды, повтор root:
  если несколько root пока не поддержаны, отказ с guidance, не молча первый.
- [ ] Run: .venv/bin/python -m pytest tests/cli/test_cli_docs_list.py
  tests/cli/test_cli.py tests/cli/test_cli_status.py -q; ожидается PASS.
  Старый tree.status не менять на lifecycle в рамках аддитивного релиза;
  documented переход parse_status в целевом v2 остаётся большому плану.

### Задача 5: Конкретная guidance и контракт ошибок

**Файлы:** output/envelope.py:12–80, cli.py:_emit_error/main:2446,
output/guidance.py, resources/guidance/ru.json, pyproject.toml package-data;
tests/cli/test_overview_guidance.py.
**Consumes:** коды P15, Click UsageError.ctx, registry capabilities З4.
**Produces:** resolve_guidance(code: str, *, command: str,
params: dict[str, str], profile: str = "ru") -> dict[str, Any].
Envelope.guidance = {profile, mode, items}; компактный успех с items=[].

- [ ] Проверить наличие guidance на успехе/ошибке в json/markdown/table.
  При неверном --path у docs read — контекстная docs read --help,
  корректный argv для read предлагать только если id уже достоверно известен.
  Не выдумывать custom id по имени файла.
- [ ] Неизвестное поле/невалидный cursor/неполнота имеют стабильный code,
  текст и ссылки берутся из каталога; JSON stdout содержит один объект.
- [ ] Общий envelope получает компактное поле аддитивно; несовместимую миграцию
  всего data/schema_version не проводить. Полное покрытие всех кодов — владелец
  плана волн З2; для кодов этого инкремента покрытие обязательно.
- [ ] Проверить безопасные относительные ссылки каталога и отсутствие shell,
  наличие ru.json в собранном wheel; не ссылаться на ещё не существующий --mode.
- [ ] Run: .venv/bin/python -m pytest tests/cli/test_overview_guidance.py
  tests/cli/test_cli_contract.py -q; ожидается PASS.

### Задача 6: Короткий маршрут агента и честная проверка харнеса

**Файлы:** SKILL.md, src/todoc/data/agent-skill/todoc/SKILL.md;
через docs edit: demo/skills/docs/todoc-docs/SKILL.md,
demo/notes/agent-contract.md; tests/cli/test_metadata_overview_e2e.py,
tools/eval_metadata_overview.py.
**Consumes:** реальная команда З4 и ошибки З5.
**Produces:** маршрут «обзор метаданных → проверка полноты → ответ» и
scripted сценарии стенда; внешнюю платформу Codex скрипт не перенастраивает.

- [ ] Для задачи списка собственный скил сначала выбирает docs list; не требует
  HOME и N тел, если полная свежая проекция уже содержит запрошенные поля.
  Уже загруженный скил в сессии повторно не запрашивается.
- [ ] Развести проверку чтения (ok, complete, scope, cursor, источники)
  и обратное чтение после записи; предложить согласованное уточнение AGENTS
  при внедрении, а не обходить действующие правила в текущей сессии.
- [ ] Правило пакета: один проверочный вызов до тиражирования одинаковой формы;
  при ненулевом exit/ok=false зависимые вызовы прекращаются.
  Не объявлять, что CLI может отменить уже запущенные независимые процессы.
- [ ] В scripted пробе сначала неверный read: attempts=1, remaining_reads=0;
  после локальной справки один исправленный probe. Это тест runner policy,
  не доказательство поведения LLM.
- [ ] PowerShell/WSL: аргументы передавать массивом, не строить bash -lc строку;
  тесты с пробелами, кириллицей, скобками и пустым значением. Фиксировать версии
  PowerShell/WSL, smoke в доступной среде; недоступную платформу пометить not_run.
- [ ] Run: .venv/bin/python -m pytest tests/cli/test_metadata_overview_e2e.py -q.
  Проверка настоящей модели — минимум 3 повтора тем же промптом и корпусом;
  записать модель/инструкции/ошибки/вызовы/байты, tokens только при наличии usage.
  Если модель недоступна, scripted=pass, llm=not_run.

### Задача 7: Приёмка сценария и синхронизация документации

**Файлы:** tools/eval_metadata_overview.py, tests/cli/test_metadata_overview_e2e.py,
docs/state/03-cli-reference.md, README.md; через CLI
demo/references/state/03-cli-reference.md, demo/HOME.md и BUG-022.
**Consumes:** З1–З6; общие гейты §6.
**Produces:** отчёт с baseline/result/delta и матрица требований → проверок.

- [ ] Выполнить subprocess E2E на 20/100/500 fixture; измерить запросы данных,
  discovery отдельно, байты, cold/hot latency p50/p95 (не менее 10 повторов),
  полноту и отсутствие записей. Сравнение только на одинаковом корпусе/среде.
- [ ] Проверить один запрос для 20 с --limit 100; при большем корпусе
  ceil(total/limit) запросов, без чтения каждого тела. Не обещать один запрос
  для произвольного N с конечным лимитом.
- [ ] До реализации обзора baseline может требовать N read; не воспроизводить
  20 неверных команд ради замера. Исторические 54 — evidence эпизода, не
  целевая baseline-команда и не инструментально измеренный usage.
- [ ] Обновить справку, карту, BUG-022 и раздел 8 фактическими результатами;
  связать большой план (З3/З5/З9) и план волн (З2), не закрывая их целиком.
- [ ] Пройти гейты §6; до закрытия бага предоставить результат пользователю.

## 6. Definition of Done

- [ ] З1–З7 проверены; fixture, контракт, CLI, cursor, no-write и guidance покрыты.
- [ ] Полный пользовательский вопрос решается по актуальным fm метаданным,
  отсутствующий status виден отдельно; custom id и пути не потеряны.
- [ ] Нет второго views/guidance/storage pipeline и скрытых модификаций read.
- [ ] Отчёт различает measured/estimated/not_run, bytes/tokens, команды/tool calls,
  scripted/LLM; цель стоимости проверена без скрытия полей по умолчанию.
- [ ] Все кодовые изменения проходят:

~~~bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m coverage run --branch -m pytest
.venv/bin/python -m coverage report --fail-under=100
PYTHONPATH=src .venv/bin/python -m todoc validate --root demo --all
python3 tools/linkcheck.py
git diff --check
~~~

Ожидания: pytest PASS, coverage 100%, validate 0 диагностик, broken 0,
diff --check без ошибок. linkcheck сейчас возвращает 0 и при broken>0:
проверять текст отчёта. Существующие четыре broken в .doc/codexaudit не
замалчивать; сохранять baseline, исправить отдельным связанным исправлением
перед коммитом, если они остаются. demo отдельно должен иметь broken 0.

## 7. Риски и митигации

| Риск | Вероятность / влияние | Митигация | Владелец |
|---|---|---|---|
| Два значения status смешаются | высокая / высокая | lifecycle_status внутри, status/parse_status в новой форме; legacy tree не менять молча | исполнитель З2/З4 |
| Старый индекс потеряет fm | высокая / высокая | metadata schema version + in-memory rebuild; cold/stale тесты | исполнитель З2 |
| Cache/observe пишет из вложенного слоя | высокая / высокая | read_only до validator, перехват записи и файловые снимки | исполнитель З2 |
| Конфликт с большой миграцией CLI/P15 | высокая / средняя | reuse views/capabilities/guidance, таблица владельцев, сверка перед кодом | исполнитель |
| Бюрократия харнеса дороже данных | высокая / средняя | отдельно считать discovery, не перечитывать скил, остановка на полном ответе | владелец харнеса |
| Ошибка чтения выглядит пустой базой | средняя / высокая | complete=false + exit6, диагностики и тест исчезающего файла | исполнитель З2/З3 |
| Инструкции приняты за гарантию runtime | высокая / средняя | scripted и LLM отчёты раздельно, техническую отмену пакета не обещать | владелец оценки |
| План перегружен будущими идеями | средняя / средняя | жёсткий §2, один измеримый сценарий, связанные планы не закрывать целиком | исполнитель |

## 8. Прогресс и отклонения

- 2026-11-28: пользователь запросил исследованный план на основе BUG-022.
  Изучены связанные идеи, канонический контракт, два действующих плана и код
  models/service/validator/registry/CLI/envelope; новые внешние источники не нужны.
- План создан через docs new, заполнен review-first docs edit;
  реализация и создание task-записей не запускались.
- Самопроверка: BUG-022 → З1–З4/З7, BUG-021/P15 → З5,
  ошибки пакетного запуска/WSL → З6, no-write и свежесть → З2.
- Отличие от предложения в баге: не скрывать legacy lines/text по умолчанию,
  использовать явную проекцию; не подменять существующий tree.status.
  Причина — действующие решения идеи/плана единого CLI и совместимость.
- Широкие идеи остаются в своих статусах: данный план покрывает конкретный
  дефект, а не означает согласование SQLite/тегов/всей переделки CLI.
- Даты created/updated оставлены движку; дата исследования в журнале — 2026-11-28
  по пользовательскому контексту. Расхождение даты среды не исправлялось вручную.
