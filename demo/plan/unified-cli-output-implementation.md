---
id: doc:plan/unified-cli-output-implementation.md
title: "Единый самодокументируемый CLI: план реализации"
doc_type: plan
lang: ru
created: 2026-11-26
updated: 2026-11-27
---

# Единый самодокументируемый CLI — план реализации

> **Исполнителю:** реализация только после прямого указания и подтверждения
> пользователя. Работай по задачам сверху вниз; отмечай завершённые чекбоксы и
> фиксируй отклонения в разделе 8. Коммиты, ветки и PR — только по отдельному
> разрешению пользователя и правилам текущей среды.

**Цель:** масштабно переделать весь публичный todoc CLI в один предсказуемый,
самодокументируемый интерфейс для LLM: одинаковые слова, расположение опций,
семантика, структура ответов и безопасность во всех применимых командах. Агент
осваивает одни правила, а не запоминает исключения каждого обработчика. Виды
`flat`, `tree`, `graph` и форматы независимы. Переделка — не цель сама по себе:
единый наблюдаемый контракт и доказуемая работа всего CLI — цель.

**Спека:** [идея единого CLI](../ideas/unified-cli-output.md). **Стек:** Python
3.11+, Click, jsonschema, markdown-it-py, pytest и coverage; новые runtime-зависимости
не добавлять. **Архитектура:** данные собирают существующие application-сервисы;
общий реестр описывает возможности команд, общий слой применяет проекции и
представления, а один сериализатор выдаёт результат и сообщения.

> **Маршрут для новой сессии:** пользователь выбрал чистый master и перенос
> только четырёх документов, без наших тестов, кода и баг-репортов. При
> расхождении с историческими инструкциями о переносе/слиянии ниже применять
> маршрут B §0.11 и мастер-план `docs/plan/todoc-master-refactoring-plan.md`.
> Текущие изменения в старой сессии не удалять; их резервная копия желательна,
> но для нового чистого checkout не требуется переносить эти изменения.
> Указанные в §0.6 тесты и репорты — исторические ссылки; недостающие тесты
> нужно заново написать по инвариантам, а не считать их имеющимися в master.

## 0. Подготовка: правила, сохранность и база master

**Статус:** это условия будущей реализации, а не уже изменённые правила и не
разрешение на merge. Текущая задача — только аудит и правка этого плана; до нового
прямого поручения не менять код, правила, данные, критерии, состояние ветки или PR.
Исторические разрешения на реализацию в разделе 8 относятся к прошлому поручению.

### 0.1. Временные правила на время реализации

- [ ] Перед стартом согласовать и затем отдельным разрешённым изменением уточнить
  соответствующие источники правил: `AGENTS.md` (включая локальное приоритетное
  правило о прямом поручении), канон `demo/notes/agent-contract.md` и другие
  реально распространяющие их инструкции/промпты, если аудит выявит расхождение.
  Сохранить остальное, зафиксировать область, начало и окончание исключения.
- [ ] Во время **тестирования и разработки CLI** не создавать баг-репорты по
  найденным тестами проблемам: фиксировать их в тестах/результатах и разделе 8,
  исправлять ошибки реализации в рамках разрешённой задачи. При **использовании
  todoc как продукта** правило фиксации баг-репортов с поиском дублей сохраняется.
  Пользователь употребил «багфиксы»: здесь это предварительно трактуется как
  баг-репорты по контексту действующих правил, а не запрет исправлять код;
  до изменения правил уточнить у пользователя, если он имел в виду другое.
- [ ] При доработке CLI разрешить чтение и запись файлов удобными инструментами,
  а не только через todoc, включая код, тестовые фикстуры и необходимые документы;
  это не разрешение на несанкционированные изменения, потерю пользовательских
  данных или нарушение ограничений песочницы. Разделить разработку/тестирование
  и использование продукта; после согласованного срока вернуть обычные правила.
- [ ] После каждой правки запускать относящиеся к ней тесты и проверки; полный
  набор и 100% branch coverage — по завершении каждого **этапа**, не каждой
  правки. На этапе интеграции, З1, З2, З3, З4–З7 по законченным группам, З8 и
  З9 отдельно записывать входной снимок, команды, результат и пропуски. Ошибка
  точечного теста блокирует соответствующую работу, полный гейт — закрытие этапа.

### 0.2. Безопасное начало с учётом актуального master

- [ ] Перед началом повторно проверить удалённый master, текущую ветку и общий
  предок; учесть изменения после зафиксированного аудита. Интеграция master →
  текущая ветка возможна только по отдельному разрешению пользователя, не
  выполнять её в рамках настоящей правки плана и не создавать другую ветку.
- [ ] До любых интеграционных действий сделать проверяемую резервную копию всех
  tracked staged/unstaged и non-ignored untracked файлов, в том числе идеи, плана,
  тестов, данных, `demo/.todoc/history/{journal.jsonl,objects/}` и результатов
  benchmark. Сохранить статусы, хэши, базу, список путей и историю; проверить
  восстановление в отдельной временной копии. Игнорируемые, но значимые данные
  также отдельно инвентаризовать и сохранить при необходимости. Резервная копия
  должна переживать окончание сессии: `.venv` и другие исключённые из снимков
  каталоги для этого не подходят; выбрать сохраняемое место и проверить доступный
  объём, не добавляя архив автоматически в Git. Если сохранение или восстановление
  нельзя гарантировать — остановиться и согласовать с пользователем. Не использовать
  `reset --hard`, `clean`, стирание или переименование пользовательских файлов.
- [ ] Сравнить в изолированной копии **полный рабочий снимок**, а не только HEAD,
  с master и общей базой; пробно интегрировать там, классифицировать конфликты
  и сохранить результаты проверки вне целевого дерева. Только после разрешения
  интегрировать в текущую ветку, разрешая конфликты по смыслу обеих сторон и
  перепроверяя сохранность относительно исходного манифеста. Если безопасное
  сочетание спорно — остановиться и запросить решение, а не выбирать сторону.
- [ ] Сохранить оба независимых набора BUG-011–016 и журнал/объекты: имена BUG
  совпадают, содержание отличается, document ID различны. Составить таблицу
  совпадений, ссылок и истории; согласовать с пользователем способ устранения
  неоднозначности без удаления/переименования репортов и без переписывания
  истории; до этого не переиспользовать неоднозначные номера. Проверить ссылки
  и поиск по обеим версиям. Не дополнять demo тестовыми баг-репортами.
- [ ] После интеграции классифицировать частичную реализацию по матрице и
  регрессионным тестам: сохранить работающие правки и новые возможности master,
  исправить несовместимости. Не начинать «с чистого master» поверх рабочего
  дерева и не считать автослияние или зелёную валидацию доказательством интеграции.

### 0.3. Фактический аудит и задачи по расхождениям

Аудирован master `c9256c2f5401e4f4be400382a9773f6f39f3d4d1`, общая база и
HEAD `7b8adedf3c1a08375b7e681628a6171cf54a8f32`; состояние нашего дерева —
незакоммиченные правки поверх HEAD. Это снимок на момент аудита, не обещание,
что master не изменится. Архив master изучен отдельно, рабочая ветка не слита.

| Область и свидетельство в коде | Работа и приёмка после интеграции |
|---|---|
| В master 63 Click leaf и 359 параметров leaf; наш частичный реестр содержит 60 имён/476 параметров leaf. Нет `docs status`, `records status`, `interop export`. Количество параметров не является матрицей поведения. | З1: получить новую точную инвентаризацию объединённого дерева; сравнить Click и реестр по всем опциям/позициям/алиасам/типам и сценариям, включая три новых листа. Тест не проходит только потому, что совпало число имён. |
| Master: `cli.py` и `output/envelope.py` используют v1; `_emit_ok`, прямой `click.echo` и отдельно `main` для ошибок. У нас v2 частичный, есть прежние ветки. | З2/З7/З8: трассировать root/group/leaf, `main` и CliRunner, JSON/table/markdown, парсинг ошибок и raw-ветки; schema и контракт-тесты успешных и ошибочных форм, включая downstream. |
| В master `service.py:ensure_index` на изменившемся корпусе вызывает publish, stats и observe, хотя вызывается чтениями; `scan_and_validate` также использует кэш. Наш `read_index` и строгие чтения охватывают не всё. | З3: инвентаризировать фактические вызовы и запись на всех ветвях, включая новые команды master, холодный/битый индекс, внешние правки и history; не полагаться на имя read-only. Явно решить recovery повреждённого опубликованного индекса, не выдавать устаревшие данные за актуальные. |
| Master `records list` применяет `until/relation` после limit; `docs tree` возвращает `max_depth`, но фактически не обрезает документы. Частичные исправления в нашем дереве ещё нужно проверить в интеграции. | З3/З5: регрессии на результат после первого лимита, общие счётчики и глубину; тесты на нескольких страницах и изменившейся конфигурации. |
| Master status GET/SET (`cli.py:1617,1823`) выбирает `_contexts(roots)[0]`, SET сразу вызывает `apply_write_plan`, проверяет `allowed_statuses`/schema enum, сохраняет body/updated и историю. | Для обеих команд: GET чистый, SET → preview по умолчанию и явный apply с CAS; не терять ограничения статусов, отсутствие поля, одновременные правки и history. Определить поддержку многокорневого чтения и однозначное разрешение корня записи без тихого выбора первого; проверить в subprocess, JSON и человеческих форматах. |
| Master `interop export` поддерживает ASL/DMN/Rasa, stdout и `--write` в `exports/`, защищает не-derived цель, записывает derived_from и историю; `--write` сейчас пишет сразу и выбирает первый root. | Сохранить семантику видов/источников и защиты ручных файлов, containment и stale; `--write` сам по себе не применяет запись, preview → явный apply с CAS, гонками и корректным root. Проверить отсутствие записи в index/history/цель при preview, отказ при изменении файлов, derived и validation после apply. |
| `history gc` в нашем дереве ещё v1, выбирает первый root; его preview может не совпадать с реальным удалением, операция может завершиться частично. | Отдельно проектировать безопасную область действия, точный план, проверку актуальности плана и сообщение о частичном выполнении/восстановлении; не обещать атомарность без механизма. Тестировать защиту объектов и journal на временном root, без настоящего demo. |
| При локальном тесте примера З4 вызов `project_fields` без keyword-only `allowed` даёт `TypeError`; текущие структурные поля зависят от аргумента `structural`. | Исправленный ниже пример описывает текущий интерфейс, но не доказывает З4: проверить идентичность и допустимые поля по каждой форме и согласовать единый адаптер. |
| В master новые процессные навыки `todoc-capture`, `todoc-plan`, `todoc-execute`, `todoc-transitions` используют старые status-вызовы, output и validation. | З8: мигрировать эти и остальные потребители вместе с примерами, встроенными `src/todoc/data/agent-skill`, `typing_system/prompts.py`, `demo/.todoc/{entity_types,doc_types}/*/prompts`, README, SKILL, `docs/state` и `demo/references/state`; выполнять реальные сценарии, не только текстовый поиск. |
| Наши `bench/criteria.md` и проверки K14/K19/K30 уже изменены; 30/30 измерены до последнего adopt и не являются независимым гейтом. K30 offline проверял лишь один вызов/Python socket, не firewall. | З8/З9: сверить с master все K1–K30, сохранить K1/K2/K4–K30 как baseline; изменение любого, кроме K3, только с причиной и предварительным согласием пользователя; особенно K19 и K30. До решения не считать 30/30 доказательством. Изолировать результаты и фиксированные `/tmp/todoc-bench-*`; воспроизвести после интеграции и последней правки с точной методикой. |

**Диагностическая проверка, не итог интеграции.** В изолированном пробном
автослиянии было 13 файлов с текстовыми конфликтами (в основном `demo/HOME.md`,
`demo/README.md`, `demo/references/state/*`, `docs/state/*`); `cli.py` и
`validator.py` слились текстово, но требуют семантической проверки. Прогон с
конфликт-маркерами: 1737 passed, 60 skipped, 39 failed; validate и linkcheck были
зелёными, но не выявили маркеры. После экспериментальной поправки только части
фикстур init/rebuild: 33 passed, 6 failed — `skills read` truncation, root и
`skills attach`, строгий `docs links`, `docs flow render`, запись interop. Это
потенциальные различия контракта/фикстур или дефекты, не доказательство 39 либо
6 производственных багов; каждый классифицировать и проверить отдельно.
Контроль точного master: `tests/cli/test_cli_status.py`, `test_cli_interop.py`,
`tests/unit/test_status_validation.py` — 35 passed в изолированной копии.
Наш последний полный прогон **до master**: 1691 passed, 57 skipped, 100% branch
coverage; это не результат объединённого дерева. З1–З9 остаются незакрытыми.

### 0.4. Реальный маршрут запуска и контрольные точки

Ниже — последовательность **после нового поручения и отдельных разрешений**;
план не гарантирует отсутствие неизвестных дефектов. Не переносить статус
«завершено» из исторического журнала в объединённое дерево без проверки.
Для маршрута B (§0.11) P0 и P2 применяются к чистому master и переданным
артефактам, а P1 с интеграцией двух снимков неприменим: фиксируется как N/A.
Если перенесённые тесты целевого контракта закономерно падают на чистом master,
зафиксировать baseline и причины, отделить их от неожиданных проблем baseline;
они могут оставаться красными до своих задач, но не закрывают З0-S, соответствующий
этап или итоговый DoD без прохождения. Не требовать зелёного будущего поведения
как условия начала его реализации.

1. **P0 — решение о правилах и базе.** Уточнить значение «багфиксы» и срок
   исключения из §0.1; согласовать и изменить только разрешённые правила. Повторно
   сверить master и рабочий снимок. Явно согласовать способ переноса истории Git:
   dirty tracked/untracked файлы могут блокировать `git merge`, поэтому иметь
   проверенный внешний backup и пробу в изоляции. Если способ требует коммита,
   заранее получить отдельное разрешение; если пользователь не разрешает коммит
   или merge, остановиться, не выдавать копирование файлов за merge/master-базу.
   Не перезаписывать конфликтующие untracked файлы при восстановлении. Записать
   манифест hashes, режимы файлов, symlink targets, tracked/staged/unstaged и
   untracked, сравнить содержимое и историю обеих сторон после восстановления.
2. **P1 — интеграция.** Пробное трёхстороннее объединение в отдельной копии;
   фактическое master → текущая ветка только по разрешению. Разрешать 13 ранее
   обнаруженных конфликтов и заново проверить 25 общих путей по §0.5. Согласовать
   коллизию номеров BUG, не стирать журнал. Сохранить документы master и наши
   правки; отдельно сверить `cli.py`/`validator.py`, которые могут слиться без
   маркеров, но не по семантике. На чистой копии собрать baseline как есть.
3. **P2 — интеграционный гейт.** Первыми проверить фикстуры init/rebuild,
   новые `test_cli_status.py`, `test_cli_interop.py`, `test_cli_coverage_gaps.py`,
   `test_status_validation.py`, `test_interop.py` и регрессии §0.6. Адаптация
   assertions — только вслед за доказанным целевым контрактом и без удаления
   смысловых проверок. Классифицировать каждое падение: контракт/фикстура,
   реальная ошибка, среда, неопределённое решение; для каждой — репродукция,
   владелец/следующий шаг. Затем полный pytest и coverage 100%; провал блокирует
   закрытие интеграционного этапа, но не запрещает продолжить точечную починку.
4. **P2-S — граница storage (З0-S, §0.10).** Адаптировать JSON/JSONL,
   сохранив независимый HistoryBackend; перевести существующие обращения к
   storage на seam, проверить fake и регрессии. После гейта переносить остальные
   команды на единый CLI-контракт, используя seam, а не обходя его.
5. **P3 — инвентарь и контракт (З1–З2).** Собрать по фактическому Click каждую
   группу/лист/все параметры и клиентов, для каждого leaf — позитивный, негативный,
   no-input и side-effect сценарии. Написать schema, golden fixtures для текущего
   master и целевого v2, матрицу legacy → v2. Разрешить явные конфликты опций,
   root, ошибок, обязательных входов, action и форматов. Гейт — проверки схемы,
   dispatcher и запись матрицы, затем полный набор этапа; не объявлять работу
   готовой на основании одного сравнения имён реестра.
6. **P4 — данные и безопасность (З3, З4–З7).** Сначала инфраструктура чистого
   чтения/проверок корня и history, затем общие виды/пагинация, после — семейства
   команд по матрице. Для каждого семейства единый вертикальный срез: тест →
   обработчик → schema → CLI subprocess и форматы → потребители → связанные
   регрессии. Не создавать вторую несовместимую v2-форму между этапами. Точечные
   тесты после правки; полный набор и 100% в конце каждой законченной группы.
7. **P5 — миграция и выпуск (З8–З9).** Прогнать сквозные сценарии master,
   полную матрицу листьев, тесты обеих сторон, разрешённые benchmark-критерии,
   CLI-примеры, docs и контроль сохранности. CI запускает Python 3.11 и 3.12;
   локально повторить обе версии при наличии, иначе честно отметить непроверенную
   версию и дождаться CI при разрешённой публикации. Отдельно показать пропуски
   pytest и не объявлять пропущенное проверенным. Приложить команды и фактические
   результаты, ограничения snapshot/TOCTOU; только затем предлагать завершение.

**Разбор шести остаточных падений диагностической копии:**
`skills_read_budget_truncates` — перенести проверку truncation в v2 без потери
метаданных и реального бюджетирования; `skills_attach_requires_root` — утвердить
различие отсутствующего и явно неверного root; `skills_attach_copies_subdirs…` —
инициализация и attach с явным apply плюс вложенные файлы и безопасность; `docs_links_edge_cases`
— проверить строгую ошибку на битый источник и отдельный валидный кейс ссылок,
не просто вернуть прежнее неполное поведение; `flow_render_overwrite_and_missing_pointer`
— v2 preview/apply, derived_from и защита ручной цели; `written_export_is_valid_doc…`
— применить запись явно, затем проверять реальный файл и тип валидацией. Сначала
подтвердить причину каждого на разрешённом объединённом дереве: прежний эксперимент
с конфликт-маркерами сам по себе не доказывает defect или решение.

### 0.5. Полный манифест изменений master и стратегия сохранения

На аудированном master от базы: **114 путей (58 M, 56 A)**; 25 общих путей с
рабочим снимком; 13 текстовых конфликтов. Реестр ниже покрывает *все* пути данного
снимка master; категория задаёт обязательную проверку, а не утверждение, что
каждый файл уже проверен построчно. A — добавлен, M — изменён относительно базы.
Между выполнением этого плана и аудитом master может измениться: при старте
перестроить манифест и сравнить дополнения. Не считать 56 отсутствующих у нас
master-файлов намеренно удалёнными.

- **A — код:** `interop.py`, `validator.py`, `cli.py`, `descriptors.py`: сохранить
  обе ветки логики; status allowed_statuses, формы/диагностики схем, interop и
  частичные v2/read-only. Проверить именно вызовы/ошибки/побочные эффекты.
- **B — тесты:** сохранить тесты master и наши; исходную цель assertions
  сопоставить с v2, не отключать тесты и не заменять безопасность пустой проверкой.
- **C — типы, схемы и правила датасета:** экспортный тип и document rule,
  allowed_statuses идеи/плана, enum task, `implements` и `subtask_of`. Проверить
  загрузку, validate и образцы статусов/связей, в том числе неверные значения.
- **D — четыре process-skill:** вместе с `README/SKILL` и промптами перейти на
  актуальные результаты и preview/apply; не нарушить требование явного
  подтверждения конечного статуса. Проверить сценарий idea → plan → task →
  transitions на изолированном dataset, не закрывая реальные задачи.
- **E — существующие баги/design и document records:** сохранить весь текст,
  front matter, статус, пути и связи; номинальные совпадения наших BUG-011–016
  решить отдельно по §0.2. Триаж master-багов и design — §0.7, а не молчаливая
  отметка их выполненными.
- **F — экспорты, tasks и document record плана:** сохранить содержимое, источники,
  `derived_from`, статусы и связи, проверить ASL/DMN/Rasa, fresh → source edit →
  stale, regenerate preview/apply и validation. Не перегенерировать рабочие
  экспортные документы во время теста, использовать копии.
- **G — идеи/планы/исследования:** сохранить все новые и изменения статусов,
  HOME-ссылки и `derived_from`; они не автоматически становятся требованиями
  реализации единого CLI. Отдельные архитектурные предложения — вне скоупа до
  согласования; при конфликте с новым контрактом зафиксировать миграцию/решение.
- **H — зеркала справки:** сверить `docs/state` и `demo/references/state` по
  каждому пути, 17–19 включительно; слить знания обеих сторон, затем актуализировать
  фактические вызовы, ссылки, счётчики и примеры. Validate/linkcheck не заменяют
  обнаружение маркеров и смысловую проверку. Не стирать дополнения master.
- **I — карты и README:** свести навигацию, счётчики и списки двух сторон по
  реальному объединённому содержимому; не переписывать HOME одной стороной.
- **J — генератор:** `tools/refresh_demo_state.py` учитывать как источник
  воспроизведения справок; перед запуском выяснить, что он перезаписывает,
  сравнить в копии и не перезатирать пользовательские исправления.

| Путь master относительно базы | Изменение | Проверка |
|---|---|---|
| `README.md` | M | I |
| `demo/.research/agent-brainstorming-and-research-packs.md` | A | G |
| `demo/.research/bm25-ranking-python-libs.md` | A | G |
| `demo/.todoc/doc_types/export/type.json` | A | C |
| `demo/.todoc/doc_types/idea/type.json` | M | C |
| `demo/.todoc/doc_types/plan/type.json` | M | C |
| `demo/.todoc/entity_types/task/schema.json` | M | C |
| `demo/.todoc/relation_types/implements/type.json` | A | C |
| `demo/.todoc/relation_types/subtask_of/type.json` | A | C |
| `demo/.todoc/rules/document-rules.json` | M | C |
| `demo/HOME.md` | M | I |
| `demo/README.md` | M | I |
| `demo/bugs/bug-003--счётчики-демо-в-readme-разошлись-с-фактом.md` | M | E |
| `demo/bugs/bug-004--docs-edit-не-умеет-вставку-и-удаление-строк.md` | M | E |
| `demo/bugs/bug-011-dreyf-derived-from-pri-smene-statusa-tela-ishodnika-trebuet-ruchnogo-re-ankoringa.md` | A | E |
| `demo/bugs/bug-012-history-revizii-mutiruyuschih-komand-zagryaznyayut-git-status.md` | A | E |
| `demo/bugs/bug-013-neodnorodnye-id-i-output-kontrakty-rezolv-identifikatora-trebuet-ruchnogo-grep.md` | A | E |
| `demo/bugs/bug-014-docs-edit-preview-ne-pokazyvaet-numeraciyu-rezultata.md` | A | E |
| `demo/bugs/bug-015-yaml-lite-front-matter-ne-obrabatyvaet-backslash-escape-kavychek.md` | A | E |
| `demo/bugs/bug-016-filtry-records-query-ne-dokumentirovany-v-spravkah.md` | A | E |
| `demo/bugs/design-q01-terminalnyy-status-zapisi-guard-procedurnyy-dvizhok-molchit.md` | A | E |
| `demo/bugs/design-q02-review-first-dvoynoy-vyzov-stoimost-dlya-agenta-protiv-kontrolya.md` | A | E |
| `demo/exports/asl-order-placement.md` | A | F |
| `demo/exports/dmn-account-blocked-v1.md` | A | F |
| `demo/exports/dmn-gateway-down-v1.md` | A | F |
| `demo/exports/dmn-no-funds-v1.md` | A | F |
| `demo/exports/rasa-glossary.md` | A | F |
| `demo/ideas/action-logging.md` | A | G |
| `demo/ideas/agent-state.md` | M | G |
| `demo/ideas/bitemporal-clocks.md` | A | G |
| `demo/ideas/docs-move.md` | A | G |
| `demo/ideas/documentation-system.md` | M | G |
| `demo/ideas/entity-catalog.md` | M | G |
| `demo/ideas/entity-to-folder.md` | A | G |
| `demo/ideas/folder-config.md` | M | G |
| `demo/ideas/interop-exports.md` | A | G |
| `demo/ideas/skills-engine.md` | M | G |
| `demo/ideas/sqlite-storage-drivers.md` | A | G |
| `demo/ideas/todocignore.md` | A | G |
| `demo/ideas/type-naming-and-state-dir.md` | A | G |
| `demo/ideas/typed-tree-projection.md` | A | G |
| `demo/ideas/unified-tags-and-tag-graph.md` | A | G |
| `demo/plan/folder-config-implementation.md` | M | G |
| `demo/plan/interop-exports-dmn-asl-rasa.md` | A | G |
| `demo/plan/skills-vault-implementation.md` | M | G |
| `demo/plan/агентский-стейт--state-json-в-движке--v1---текущий-проект.md` | M | G |
| `demo/plan/документирование-софта--типовой-профиль---типы--стартовые-промпты--скилы.md` | M | G |
| `demo/plan/скилы-взаимодействия--захват--план--исполнение--переходы--жизненный-цикл.md` | M | G |
| `demo/records/documents/bug-011-derived-from-drift-reanchoring.json` | A | E |
| `demo/records/documents/bug-012-history-journal-git-pollution.json` | A | E |
| `demo/records/documents/bug-013-id-resolve-output-contracts.json` | A | E |
| `demo/records/documents/bug-014-edit-preview-no-line-numbers.json` | A | E |
| `demo/records/documents/bug-015-yaml-lite-quote-escape.json` | A | E |
| `demo/records/documents/bug-016-query-filters-undocumented.json` | A | E |
| `demo/records/documents/design-q01-terminal-status-guard.json` | A | E |
| `demo/records/documents/design-q02-review-first-cost.json` | A | E |
| `demo/records/documents/plan-interop-exports.json` | A | F |
| `demo/references/state/01-overview.md` | M | H |
| `demo/references/state/02-architecture.md` | M | H |
| `demo/references/state/03-cli-reference.md` | M | H |
| `demo/references/state/04-config-and-types.md` | M | H |
| `demo/references/state/05-formats.md` | M | H |
| `demo/references/state/06-validation-and-diagnostics.md` | M | H |
| `demo/references/state/07-search-and-read.md` | M | H |
| `demo/references/state/08-records-and-relations.md` | M | H |
| `demo/references/state/09-storage-and-index.md` | M | H |
| `demo/references/state/10-testing-and-quality.md` | M | H |
| `demo/references/state/11-known-issues.md` | M | H |
| `demo/references/state/12-agent-operations.md` | M | H |
| `demo/references/state/13-demo-dataset.md` | M | H |
| `demo/references/state/14-glossary.md` | M | H |
| `demo/references/state/15-benchmark.md` | M | H |
| `demo/references/state/16-leftovers-report.md` | M | H |
| `demo/references/state/17-skills-and-vault.md` | A | H |
| `demo/references/state/18-agent-state-and-context.md` | A | H |
| `demo/references/state/19-interop-exports.md` | A | H |
| `demo/references/state/README.md` | M | H |
| `demo/skills/process/todoc-capture/SKILL.md` | A | D |
| `demo/skills/process/todoc-execute/SKILL.md` | A | D |
| `demo/skills/process/todoc-plan/SKILL.md` | A | D |
| `demo/skills/process/todoc-transitions/SKILL.md` | A | D |
| `demo/tasks/interop-converters-cli.json` | A | F |
| `demo/tasks/interop-formats-revision.json` | A | F |
| `docs/state/01-overview.md` | M | H |
| `docs/state/02-architecture.md` | M | H |
| `docs/state/03-cli-reference.md` | M | H |
| `docs/state/04-config-and-types.md` | M | H |
| `docs/state/05-formats.md` | M | H |
| `docs/state/06-validation-and-diagnostics.md` | M | H |
| `docs/state/07-search-and-read.md` | M | H |
| `docs/state/08-records-and-relations.md` | M | H |
| `docs/state/09-storage-and-index.md` | M | H |
| `docs/state/10-testing-and-quality.md` | M | H |
| `docs/state/11-known-issues.md` | M | H |
| `docs/state/12-agent-operations.md` | M | H |
| `docs/state/13-demo-dataset.md` | M | H |
| `docs/state/14-glossary.md` | M | H |
| `docs/state/15-benchmark.md` | M | H |
| `docs/state/16-leftovers-report.md` | M | H |
| `docs/state/17-skills-and-vault.md` | A | H |
| `docs/state/18-agent-state-and-context.md` | A | H |
| `docs/state/19-interop-exports.md` | A | H |
| `docs/state/README.md` | M | H |
| `src/todoc/application/interop.py` | A | A |
| `src/todoc/application/validator.py` | M | A |
| `src/todoc/cli.py` | M | A |
| `src/todoc/typing_system/descriptors.py` | M | A |
| `tests/cli/test_cli_coverage_gaps.py` | A | B |
| `tests/cli/test_cli_interop.py` | A | B |
| `tests/cli/test_cli_status.py` | A | B |
| `tests/unit/test_interop.py` | A | B |
| `tests/unit/test_skills_scan.py` | M | B |
| `tests/unit/test_status_validation.py` | A | B |
| `tools/refresh_demo_state.py` | M | J |

**Пересечение 25 путей:** `README.md`, `demo/HOME.md`, `demo/README.md`,
`demo/references/state/{03-cli-reference,04-config-and-types,07-search-and-read,08-records-and-relations,10-testing-and-quality,11-known-issues,12-agent-operations,13-demo-dataset,15-benchmark,16-leftovers-report}.md`,
`docs/state/{03-cli-reference,04-config-and-types,07-search-and-read,08-records-and-relations,10-testing-and-quality,11-known-issues,12-agent-operations,13-demo-dataset,15-benchmark,16-leftovers-report}.md`,
`src/todoc/application/validator.py`, `src/todoc/cli.py`. Из них маркеры были в
`demo/HOME.md`, `demo/README.md`, demo-справках 03, 04, 07, 08, 11, 12, 13,
15, 16 и docs-справках 03, 13. Маркеры — не исчерпывающий список проблем.

### 0.6. Матрица регрессий нашей реализации

Обозначение в первом столбце — историческое **имя файла**, а не один лишь
BUG-NNN: номера 011–016 есть и у master с другим содержанием. Наши репорты и
тесты **не переносятся**; имена и selectors ниже — сведения прежнего рабочего
снимка, не рабочие ссылки или доказательство наличия файлов на master.
Новая сессия для каждой инварианты пишет собственный воспроизводимый тест на
временных данных, учитывая полный контекст плана; там, где описание недостаточно,
помечает сценарий непроверенным и уточняет его, а не выдумывает совпадение со
старым тестом. Старые 28 адресов прошли на прежнем рабочем снимке; статус на
чистом master неизвестен. Не менять статусы багов и не утверждать прохождение
на основании прошлого прогона. Сохранять негативные случаи и проверки гонок.

| Историческое имя репорта | Задача и проверяемая инварианта | Исторический test selector (может отсутствовать) |
|---|---|---|
| `bug-011-fix-wrong-occurrence.md` | З2/З7: только диагностированная ссылка; неоднозначность/гонка → отказ без записи | `tests/cli/test_unified_fix.py::test_fix_apply_does_not_replace_an_unrelated_earlier_occurrence` |
| `bug-012-undo-skips-missing-history.md` | З2/З7: отсутствующий последний snapshot → ошибка без отката к старому | `tests/unit/test_records_undo.py::test_undo_refuses_missing_latest_history_snapshot_instead_of_older_version` |
| `bug-013-gc-corrupt-journal.md` | З2/З3: битый журнал → не переписывать/не удалять объекты | `tests/cli/test_unified_gc_safety.py::test_gc_refuses_corrupt_journal_without_deleting_objects` |
| `bug-014-change-list-silently-skips.md` | З3/З7: ошибка change.json → отказ, не неполный успех | `tests/cli/test_unified_change_list.py::test_change_list_refuses_corrupt_or_unreadable_change_file` |
| `bug-015-change-list-escapes-root.md` | З3/З7: symlink наружу → отказ до чтения | `tests/cli/test_unified_change_list.py::test_change_list_refuses_external_symlink` |
| `bug-016-aggregate-invalid-number.md` | З7: нечисловое/NaN/overflow → структурированная ошибка, валидный JSON | `tests/cli/test_unified_record_aggregate.py::test_non_numeric_measurement_reports_query_error` |
| `bug-017-check-config-invalid-fix-action.md` | З2/З7: только реальная применимая и root-bound next_action | `tests/cli/test_unified_check_config.py::test_config_check_does_not_recommend_unrelated_fix` |
| `bug-018-scan-incomplete-success.md` | З3: неполный обход/чтение или ошибка второго root → не успех | `tests/cli/test_unified_validation_scan_safety.py` |
| `bug-019-strict-check-status.md` | З2/З7: check --strict warning: статус, ok и exit согласованы | `tests/cli/test_unified_check_validate.py::test_check_strict_keeps_warning_exit_semantics` |
| `bug-020-search-silent-read-failure.md` | З3/З5: поздняя ошибка чтения не скрывается | `tests/cli/test_unified_docs_search.py::test_late_read_failure_does_not_silently_omit_match` |
| `bug-021-search-budget-overrun.md` | З5/З8: бюджет первого фрагмента и продолжение; не путать с K19 | `tests/unit/test_search_write.py::test_search_budget` |
| `bug-022-search-duplicate-id-action.md` | З2/З5: одинаковый id не ведёт к ошибочному документу | `tests/cli/test_unified_docs_search.py::test_duplicate_document_id_does_not_offer_read_for_wrong_path` |
| `bug-023-read-stale-source.md` | З3/З7: источник после scan изменён → отказ, не устаревший hash | `tests/cli/test_unified_docs_read.py::test_read_rejects_source_change_after_index` |
| `bug-024-read-silent-parser-errors.md` | З3/З7: битый JSON/CSV → ошибка, не молчаливый успех | `tests/cli/test_unified_docs_read.py::test_invalid_json_and_csv_are_not_silent_success` |
| `bug-025-links-incomplete-success.md` | З3/З5: links при неполном чтении → отказ, не ложная полнота | `tests/cli/test_unified_docs_navigation.py::test_links_late_unreadable_source_is_not_success` |
| `bug-026-suggest-incomplete-config.md` | З3/З5: битый/недоступный folder config не отбрасывается молча | `tests/cli/test_unified_docs_navigation.py::test_suggest_does_not_silently_discard_invalid_folder_config` |
| `bug-027-folder-config-invalid-severity.md` | З2/З5: severity и suggested_fixes корректны для конфигов | `tests/cli/test_unified_docs_navigation.py::test_invalid_folder_config_diagnostic_has_valid_severity` |
| `bug-028-links-record-targets.md` | З5: record wikilink разрешается по идентичности, не только basename | `tests/cli/test_unified_docs_navigation.py::test_record_wikilink_is_not_reported_broken` |
| `bug-029-log-corrupt-journal.md` | З3/З7: битый журнал log не пропускает события | `tests/cli/test_unified_log.py::test_corrupt_journal_does_not_report_success` |
| `bug-030-log-unsafe-section-source.md` | З3/З7: раздел log не выходит за root; ошибка чтения не скрывается | `tests/cli/test_unified_log.py::test_section_access_containment_and_cursor` |
| `bug-031-skills-read-inconsistent.md` | З3/З7: skills read метаданные и текст из согласованных байтов | `tests/cli/test_unified_skills_read.py::test_read_change_and_late_access` |
| `bug-032-skills-read-invalid-range.md` | З2/З7: диапазон и UTF-8 budget валидируются, truncation честен | `tests/cli/test_unified_skills_read.py::test_skills_confinement_and_validation` |
| `bug-033-index-corruption-hidden.md` | З3/З7: битый опубликованный индекс ≠ отсутствующий, не утверждать свежесть | `tests/cli/test_unified_index_status.py::test_status_does_not_call_corrupt_index_unbuilt` |
| `bug-034-index-rebuild-incomplete-snapshot.md` | З3/З7: ошибка обхода/изменение источника не публикует неполный индекс | `tests/cli/test_unified_index_rebuild.py::test_rebuild_rejects_scanner_failure_without_publication` |
| `bug-035-doctor-unknown-check-index-current.md` | З2/З7: неизвестная проверка doctor → ошибка, наличие указателя ≠ свежесть | `tests/cli/test_unified_doctor.py::test_doctor_rejects_unknown_and_empty_check` |
| `bug-036-benchmark-k14-legacy-plan.md` | З8/З9: K14 читает v2 план и реально проверяет отсутствие записи | `tests/unit/test_benchmark_unified.py::test_k14_reads_v2_and_still_checks_execution_and_writes` |
| `bug-037-benchmark-k30-portability-proxy.md` | З8/З9: K30 проверяет заявленное, документирует предел offline и согласование | `tests/unit/test_benchmark_unified.py::test_portability_requires_text_sources_and_actual_ignore_rules` |
| `bug-038-history-adopt-partial-baseline.md` | З2/З3/З7: adopt: исчезнувший файл/битая история → нет частичного baseline | `tests/cli/test_unified_history_adopt.py::test_adopt_rejects_vanished_file_instead_of_partial_baseline` |

После каждого затронутого семейства: точечный тест/файл таблицы, проверка
сохранности данных и форматов; после соответствующего этапа — полный набор.
Кроме 28 репортов сохранять регрессии на все ранее обнаруженные проблемы, даже
если по ним нет документа: depth/filter-before-limit/graph cycles, cold cache,
raw stdout, конфликт алиасов, path/symlink, cursor, history, полная матрица действий.
См. также `tests/cli/test_unified_*.py`, `tests/unit/test_records_undo.py`,
`tests/unit/test_query.py` и тесты master. Тесты могут пропускаться по среде;
учесть причины, а не засчитывать пропуск как прохождение.

### 0.7. Баги и открытые решения master — без расширения скоупа молча

Ниже — **репорты из master**, не совпадающие по смыслу с одноимёнными нашими;
идентифицировать по полному пути из §0.5. Включение в план не означает, что
каждый старый баг решён или что его полное исправление автоматически входит
в задачу единого CLI. Для каждого при интеграции сохранить открытый статус,
зафиксировать воспроизведение в изолированной фикстуре и принять нижеуказанное
решение; если требуется новая продуктовая функциональность вне контракта —
согласовать её с пользователем либо отметить отдельным открытым блокером/долгом.

| Master | Связь с планом и обязательная проверка |
|---|---|
| BUG-011 derived_from drift | З3/З8: изменение источника действительно делает владельца stale; не прятать диагностику и не менять якорь автоматически. Потребность в новом безопасном re-anchor отдельно согласовать; проверить статусы и interop fresh → stale. |
| BUG-012 history и git | З2/З3: preview/read не пишет; apply видимо сообщает о ревизии там, где это реализуемо. Конвенцию хранения/коммита журнала согласовать отдельно; существующую историю не удалять и не игнорировать как способ «очистки». |
| BUG-013 неоднородные ID и envelopes | З1/З2/З8: вернуть реальные ID/пути где известны, ошибки всегда распознаются по `ok`/exit, тестировать неоднозначные ID. Автоматический cross-namespace resolver не предполагать без решения о неоднозначности. |
| BUG-014 docs edit preview/нумерация | З2/З8: сохранить правильность последовательных op и CAS, проверить диагностический контекст и preview. Нумерованный preview / дополнительные guards — отдельное решение, если не покрыты согласованной schema. |
| BUG-015 YAML-lite escape | З3/З8: не потерять существующий контракт парсера; отдельно проверить ошибочный escape и документировать/согласовать диагностику либо поддержку. Не считать это исправленным из-за v2 envelope. |
| BUG-016 records query filters | З7/З8: сохранить и описать фактические операторы/вложенные значения, добавить запускаемые примеры и тесты; не расширять семантику `$in`/`$gte` по предположению. |
| DESIGN-Q01 guard терминальных статусов | Открытое архитектурное решение: сохранять процедурное требование подтверждения в навыках; не внедрять и не убирать движковый guard без решения пользователя. |
| DESIGN-Q02 стоимость review-first | Измерить стоимость в usability gate З9, сохранить согласованный preview/apply. План-файл и изменение схемы подтверждения — отдельное решение, не превращать `--write` в неявный apply. |

### 0.8. Benchmark и невыполненные решения перед выпуском

- **K19 — обнаруженное расхождение:** master `bench/criteria.md` требует
  «объём ответа не превышает бюджет»; в рабочем дереве критерий заменён на
  «UTF-8 байты возвращённого текста Markdown, не размер конверта». Проверка
  benchmark также считает лишь `data.result.text`. Разница существенна: метаданные,
  diagnostics и envelope могут превышать budget. До согласования пользователя
  считать изменение K19 **неутверждённым**, не выдавать прохождение проверки текста
  за выполнение исходного критерия. Проверить согласуемость полного JSON-envelope
  с малым бюджетом, обнаружить минимальные размеры/ошибки; предложить точное
  решение пользователю, либо обеспечить исходный критерий без его ослабления.
- **K30** переформулирован и проверяется ограниченными прокси; согласование
  обязательно. K14/K16 и другие проверки мигрировать на v2, сохраняя исходные
  смысл и пороги; ослабление или пересмотр любого K1/K2/K4–K30 не разрешён без
  отдельного согласия. При неоднозначности K29 «0 пропущенных» явно различать
  непокрытые ветви и pytest skips: coverage 100% обязателен, количество/причины
  skips отчитываются, трактовку исходного текста не изменять молча.
- Текущий `bench/run_benchmark.py` задаёт `RESULTS = REPO / "bench" / "results"`:
  одна установка переменной окружения `RESULTS` сама по себе не изолирует файл.
  Выполнять в защищённой копии репозитория с проверенным результатом/перенаправлением
  в коде тестового harness; сам script использует фиксированные `/tmp/todoc-bench-*`
  и может их удалять. До запуска проверить изоляцию **и** отсутствие чужих файлов,
  конкурирующих запусков; при невозможности — не запускать, сообщить блокер.
- В итоговом отчёте отдельно: версии master/снимка и окружения, каждый критерий
  с неизменённым порогом или согласованным решением, переданные тесты и skips,
  производительность p50/p95, целостность backup, истинные ограничения K30,
  результаты всех проверок. Число `30/30` старого запуска до BUG-038 не доказывает
  выполнение новых условий и не заменяет финального прогона.

### 0.9. Сверка с идеями и незавершёнными планами master

**Граница сверки.** Проверен master `c9256c2f5401e4f4be400382a9773f6f39f3d4d1`:
в `demo/ideas/` 15 документов (9 `captured`, 6 `done`); из документов
`doc_type: plan` в `demo/` один `active`, семь `done`; дополнительно шесть
`demo/plan/after/*.after.md` имеют статус FUTURE и соответствующие оригиналы в
`docs/plan/`. Исторические `implementation-plan`, `constitution`, `audit` и
`competitive-analysis` без front-matter status не следует автоматически считать
незавершёнными фичами. `docs/plan/history-and-changes.md` помечен реализованным,
но важен как источник инвариантов истории. Перед началом реализации перепроверить
master, статусы и реально доступные планы: документы могут измениться.

**Приоритет и scope:** идеи `captured` и AFTER — архитектурные ориентиры и
открытые решения, не разрешение внедрять команды, БД, плагины, сеть, telemetry,
ML, новые типы или менять данные. Учитывать их совместимость там, где это не
требует преждевременного кода. При конфликте фиксировать текущий согласованный
контракт и решение пользователя; не выдавать черновой пример в идее за факт.
Нормативные `demo/plan/constitution.md` и `docs/plan/constitution.md` и исторический
MVP-план описывают v1-примеры и прежние критерии: целевой v2 и discovery —
намеренный breaking change по поручению пользователя, а не доказанная обратная
совместимость. На этапе З8 согласованно привести нормативные тексты, зеркала и
примеры в соответствие; не править их в ходе текущего аудита. Для конкретных
наблюдений источник истины — код, тесты и фактически проверенные данные.

#### 0.9.1. Все идеи master → архитектура единого CLI

| Идея master и её статус | Что учесть сейчас и где | Что остаётся будущим/решением |
|---|---|---|
| `demo/ideas/action-logging.md` — captured | З1–З3/З8: сохранить чистый stdout, отдельно держать результаты и операционные события; возможный инъецируемый **no-op** observer/метрики без записи и без исполнения недоверенных данных. `log` уже история содержимого. | Идея предлагает в режиме `all` писать каждый read в XDG, а `notice` — preview: это прямо противоречит запрету **любых** записей при read/preview, в том числе в XDG. До отдельного решения дефолт — без трассировки; не создавать `trace` и не писать логи. Будущая opt-in трассировка потребует явно пересмотреть область чистоты/consent, privacy/redaction, retention и поведение при отказе логгера. |
| `demo/ideas/bitemporal-clocks.md` — captured | З1/З3/З6/З7: отдельно сохранять valid-time, knowledge-time и историю revisions; реальные временные поля и параметры входят в scope, fingerprint и курсор; результаты не называть полным би-темпоральным снимком без доказательства. Проверки и решение — §0.9.4. | Два новых clock-флага, новый default скрытия и валидация knowledge-интервала меняют семантику; не реализовывать неявно как часть форматирования, нужны решение пользователя и собственные регрессии. |
| `demo/ideas/docs-move.md` — captured | З1/З2/З5/З6: реальные `id`, исходный путь, связь, секция и provenance остаются независимыми; preview/action допускает перечень затронутых путей, old/new hash, ограничения и отдельные diagnostics, не жёстко один файл. Не терять возможность описать конфликт/частичное выполнение. | `docs move`, переписывание ссылок и whole-file re-anchor вне скоупа. В идее есть гипотеза многофайловой атомарности через rollback — `os.replace` по отдельности не доказывает crash-atomicity; понадобятся журнал, восстановление и отдельный acceptance. Поведение путевых ID, вложений, папок и отката не решено. |
| `demo/ideas/entity-to-folder.md` — captured | З4/З5: сохранять идентичность сущности, реальный path и разделять дерево файлов/логический объект; `--within` нормализуется по сегментам и scope, config метаданные не теряются; не предполагать одинаковый носитель у record и doc. | `folderize`, созданные подпапки и move-engine не реализовывать; сохранение basename само по себе не исключает неоднозначных wikilinks, это надо проверять в будущем. Возможность `records --within` не обещать до фактической поддержки. |
| `demo/ideas/sqlite-storage-drivers.md` — captured | З3: отделить интерфейс чтения индексного снимка от **явной** публикации, а историю — от пересобираемого индекса; не зашивать JSON-структуру хранения в рендер/cursor/сервисы. Граница может быть малым внутренним адаптером существующего кода, без будущего plugin framework. Общие contract-тесты read-only и истории. | SQLite/FTS5, плагины и независимое переключение не вводятся. Идея `IndexCoordinator.sync` на каждом read конфликтует с чистым read; менять backend можно только сохранив этот инвариант или после отдельного согласования. `mtime+size` не доказывают равенство содержимого, O(Δ) и цифры скорости идеи не считать гарантией. История — не удаляемый derived cache. |
| `demo/ideas/todocignore.md` — captured | З3/З5: выделить единую границу обхода/области и счётчиков, не плодить жёстко зашитые разрозненные правила в новом view; учитывать конфиги как часть fingerprint. Различать «файл физически существует», «включён в выборку» и «разрешён как цель ссылки». | Сам matcher, `pathspec`, скрытие путей, новый init-файл и proposed правила symlink/negation не реализовывать без разрешения; не объявлять файлы ignored на основании идеи. В будущем hash/изменения ignore должны инвалидировать выборку/cursor, не порождая запись на read. `.gitignore` и `.todocignore` — не одно и то же. |
| `demo/ideas/type-naming-and-state-dir.md` — captured | З1/З4/З7: считать `type_id` непрозрачным значением с существующей политикой, поддерживать реальные `bug-report` и `derived_from`; различать `dir_type`, `doc_type`, `entity_type`, `relation_type` и формат. `todoc state`/XDG state не отождествлять с файловой папкой `state/`. | Ренейм типов и новый `state_doc`/`dir_type: state` не делать. Будущая миграция всех схем, ID и потребителей — отдельное согласование; не проверять type ID по гипотетическому snake_case regex. |
| `demo/ideas/typed-tree-projection.md` — captured | З4/З5: разделить физическое дерево и проекции; сохранить полный path и настоящие parent/child даже при страницах/фильтрах; сделать отдельное место для контекстных/проектированных родителей, не строить связи по basename. Проверки конфликта глубины — §0.9.3. | `todoc tree`, `--dir-type`, lineage, contraction и `--keep-empty` пока не реализуются и не рекламируются; не добавлять текущему `--depth` вторую семантику. Пример v1 JSON — эскиз, не новая схема v2. |
| `demo/ideas/unified-tags-and-tag-graph.md` — captured | З1/З5/З6/З7: существующий doc-tag, tags папки, `labels` записи и **метка истории** — разные носители и пространства имён. Рёбра должны хранить направление и provenance и не предполагать, что любой тег — графовая связь. Учитывать будущие OR/AND и условные обязательные аргументы, не меняя нынешние фильтры. | `tags` group, `tag:<name>`, `has_tag`, `--tag-in`/`--tag-all`, `labels` migration, 200-теговый порог и поиск без query — предложения, не заявленные возможности. Наследование папочных тегов и миграция labels открыты. Бюджет/пагинация даже при ≤200 должны оставаться честными; решение «отдавать все» не отменяет limits и DoD. |
| `demo/ideas/agent-state.md` — done | З2/З7: сохранять существующее dataset-scoped XDG-состояние и ключи, атомарность текущих writes где доказана, изоляцию root, preview/apply; state не смешивать с history/log. | Фазы автоматического project scope, новые ключи и project commands отдельно за gate; не подставлять state молча в фильтрацию. |
| `demo/ideas/documentation-system.md` — done в объёме типового профиля | З1/З8: сохранить типы/схемы/стартовые промпты и навыки, bounded search/read, provenance, offline и review-first; настоящий интерфейс записи и подсказки обновить по матрице. | Jira/git интеграции, синтез и дальнейшие фазы идеи не объявлять выполненными и не создавать. |
| `demo/ideas/entity-catalog.md` — done | З5/З6/З7: сохранять term/flow/правила, `mentions` vs явные relations, реальные источники/направления/параллельные рёбра, `undo-relation`, семантику flow render/walk и защиты derived витрин. | Не добавлять в граф виртуальные теги из другой идеи и не терять доступ к старым источникам при перестройке вида. |
| `demo/ideas/folder-config.md` — done | З3–З5: `.config.json` опционален, не документ, настраивает title/description/aliases/order/tags и search boost; учесть muted paths и конфиг в fingerprint, строгие ошибки и отсутствие скрытой записи. | BM25/стемминг Phase B за отдельным gate; не менять фактический ranking ради унификации. |
| `demo/ideas/interop-exports.md` — done | З1/З2/З8: сохранить существующие ASL/DMN/Rasa конвертеры, data источники и anchors, защиту цели, `stale`; тесты master и новый v2 preview/apply из §0.3. | Обратные конвертеры/runtime и расширение скоупа форматов не делать. FM `status: done`, текстовые старые пометки/open questions не доказывают неготовность существующего кода. |
| `demo/ideas/skills-engine.md` — done | З2/З4/З8: реальный vault, наследуемый mute, optional section config, ограниченное read, trusted dispatcher/ресурсы, внешний attach/import и защита путей. | Не превращать файл датасета в исполняемый код или доверенный промпт; не путать дерево навыков с будущим типизированным сжатым деревом. |

#### 0.9.2. План тегов, реализованные контракты и AFTER

`demo/plan/теги-документов-как-aliases-поиска--tags-updated-related-в-front-matter.md`
имеет `status: active`, но в §8 сообщает задачи 1–5 выполненными; в DoD не
отмечен визуальный **Obsidian-чек** пользователя. Не перезапускать массовую
миграцию и не переводить статус без разрешения. Не путать этот остаток с новым
предложением unified tags. Зафиксировать и протестировать на объединённом дереве:

- [ ] В З3/З5: поиск сохраняет фильтр существующего front-matter `--tag` с
  регистронезависимым точным совпадением и реальное ранжирование master:
  title×10 + совпадения + tag exact×8/часть×3 + буст config предков; без тегов
  прежняя формула. Фильтровать **до** пагинации/лимита и не смешивать scoring с
  filter. Фикстуры со связанной и несвязанной папкой, кириллическим тегом,
  одинаковым рангом и изменившимся `tags`/config; сравнить оба снимка, не
  воспринимать исторические числа corpus как актуальные.
- [ ] В З2/З5/З8: `docs new` формирует fm/dates, `docs edit --apply` обновляет
  `updated` вместе с итоговым hash; preview не пишет и показывает итог. `docs read`
  не теряет `tags`, `updated`, `related`, validator принимает отсутствие optional
  полей и проверяет заданные. Существующий `related` — wikilink-метаданные;
  наличие `related` не доказывает, что он является резолвленным ребром графа.
  Проверять `tests/unit/test_meta_tags.py`, `test_search_folder_boost.py`,
  `tests/cli/test_cli_folder_meta.py` и фактические потребители после интеграции.
- [ ] Проверить `.obsidian/` и структурную часть на изолированной копии; визуальную
  работу Obsidian не объявлять прошедшей без фактического пользовательского smoke.

Шесть future-планов (`demo/plan/after/` и соответствующие `docs/plan/`):

| AFTER-план | Совместимый задел в З1–З9, не реализация будущей функции |
|---|---|
| `mcp-adapter.after.md` | Семантика поиска, ошибок, прав, preview и apply живёт в application, CLI — тонкий адаптер; машиночитаемые схемы и примеры пригодны для будущего transport mapping. MCP в будущем не обязан буквально повторять CLI envelope/`argv`; auth, доверие, input_required и protocol cursor — отдельная работа. Не реализовывать MCP. |
| `web-ui.after.md` | Формы/tree/graph, идентичность, scope, диагностики и видимое усечение не зависят от текстового рендера; подтверждение записи и CAS — не функция UI. Не создавать API/web и не обещать атомарный опубликованный snapshot, пока код его не обеспечивает. |
| `memory-llm-wiki.after.md` | Сохранять generic записи/relations/QuerySpec, provenance и отделять transient state от данных и трёх хронологий; никаких скрытых LLM/auto-save. Future task/idea workflow или bundle не становятся обязанностью ядра автоматически. |
| `plugins-formats-import.after.md` | Формат носителя, предметный тип и output-формат — независимы; оставлять существующие format-adapters и validation boundaries, не исполнять код из DATA_ROOT. Plugin loader, watch, новые форматы и сетевой импорт — не сейчас. |
| `search-embeddings-vector.after.md` | В З3/З5 не смешивать filter/scope, candidate retrieval, ranking и presentation; сохранять offline deterministic lexical default и объяснимые факты/сортировку. Embeddings, fusion и rerank требуют отдельного quality/privacy gate и opt-in. |
| `sync-collab-export.after.md` | Явные hashes, конфликты, root-relative пути, provenance и реальные гарантии записи; файлы и необратимая история сохраняются отдельно от пересобираемых индексов. Никакой sync, ACL, SARIF или backend-бэкапа как фичи сейчас. |

`docs/plan/history-and-changes.md` имеет статус реализованного плана: при
миграции не сливать file revisions, причинные `change` и valid/knowledge time в
одну хронологию; тестировать `embedded` и доступный `git` backend, gap-filling,
corrupt/missing snapshots, `change verify`, `stale`, `timeline` и recovery.
Историческое условие «read создаёт один snapshot» конфликтует с новым запретом
побочных записей: при отсутствии индекса read строит in-memory, публикация только
явным действием; этот **breaking change** нужно отразить в миграции, не считать
исторический тест на публикацию по чтению неизменным требованием. Не переосмыслять
уже записанные исторические события и не обещать восполнение промежуточных правок.

#### 0.9.3. Явные разрешения конфликтов механик и имён

1. **Две глубины дерева.** Сейчас `--depth` в docs/skills = число физических
   уровней выбранной области; graph — расстояние в рёбрах, см. §4. Будущее
   сжатое дерево идеи считает глубину по *проектированным* узлам. В З1/З4/З5
   документировать единицу для каждого адаптера и сохранить физическую глубину
   нынешних команд; не создавать contraction и не переводить старый `--max-depth`
   на сжатую глубину. При будущей реализации новой проекции — отдельная явно
   объявленная политика глубины/режима и версия контракта. Проверить фикстуру
   `A(type1)/B(type2)/C(type2)/D(type1)`, физический path D, фильтры/счётчики и
   все страницы без схлопывания сейчас; в будущих contract-файлах отдельно
   описать, что будет с `skipped_dirs`, пустыми папками и корнем, не объявляя их
   реализованными. Корень с неустановленным типом не считать совпавшим по догадке.
2. **`--format`.** В `types guide` это формат содержимого экспорта; идея дерева
   использует его для формата входных файлов. Не подменять `--output` и не
   переносить значение с одной команды на другую под видом общего флага. В З1
   зафиксировать существующий смысл; до будущей tree-команды выбрать отдельное
   имя фильтра (например `--file-format`) после согласования и миграцию алиасов.
3. **`--tag` и `tag`/`tags`.** В `docs search --tag` — метаданные документа;
   в `log --tag`, `change archive --tag` и `change revert --tag` — метка истории,
   у `change archive` ещё и действие записи. Не утверждать общий смысл без
   разрешения коллизии и не превращать флаг действия в фильтр. В З1/З8 выбрать
   каноническое различение (например `--history-tag` для history с локальным
   однозначным legacy-алиасом), описать команды/aliases, риск коллизий и
   contract-тесты. Не занимать множественную группу `tags` под историю.
4. **Условный ввод.** В текущем `docs search` отсутствие query → discovery;
   идея `--tag-in` допускает поиск без query **при наличии будущего фильтра**.
   Реестр в З1 описывает правила вида «A или B» без специальных скрытых default,
   но не объявляет B поддержанным до реализации. Неполный вызов, некорректный
   явно указанный фильтр и ошибка чтения обрабатываются отдельно.
5. **Все поля vs ограничение.** Все поля *выбранной поддерживаемой формы* не
   означают полный файл или всю коллекцию; `limit`, budget, cursor и explicit
   `truncated` продолжают действовать. Метрики токенов не выводятся из байтов.
   Размер ответа, текстовый byte budget и гипотетический 200-tag default не
   смешивать, конфликт K19 остаётся блокирующим решением §0.8.
6. **Курсор/происхождение.** Новые виды, фильтры, ranking, тип и версия scope,
   конфиги, будущий ignore/драйвер/часы по мере появления входят в версионированный
   fingerprint выборки. Здесь cursor не обещан криптографически подписанным;
   scope и все параметры проверяются повторно. Не создавать
   стабильность identity из basename, display-позиции или версии storage.

#### 0.9.4. Проверенный конфликт текущей темпоральной семантики

Изолированный master: `application/temporal.py:145–171`: `visible_at` не
учитывает левую границу `observed_at`, а `records_as_of(..., None)` и
`relations_as_of(..., None)` возвращают исходные списки до проверки закрытия.
`interval_defect` проверяет `valid_from/valid_to`, но не `observed_at`.
Воспроизведение без записи на master: факт `valid_from=2026-05-01`,
`observed_at=2026-06-10` виден на `2026-05-15`; закрытая запись и ребро остаются
в списке при `None`; ошибочный `observed_at` не даёт interval defect. При этом
`tests/unit/test_temporal.py`, `tests/cli/test_cli_temporal.py`,
`tests/unit/test_meta_tags.py`, `tests/unit/test_search_folder_boost.py`,
`tests/cli/test_cli_folder_meta.py` вместе дали **67 passed** на точном master.
Тест `test_records_query_without_as_of_hides_closed_records` не засевает закрытие
на самой записи; зелёный тест не доказывает отсутствие проблемы.

- [ ] В З1 до принятия output schema классифицировать все `as_of`/timeline/graph
  и описания: зафиксировать фактический смысл и ограничения, не называть текущий
  результат «что система знала на дату» если учёт `observed_at` не реализован.
  Обсудить с пользователем: отдельная реализация двух часов из идеи либо сохранение
  текущей семантики с явным, не вводящим в заблуждение ограничением. Если нельзя
  обеспечить честный публичный контракт без изменения данных/поведения — стоп,
  не маскировать это успехом. Не менять defaults и K40/K41 молча.
- [ ] Добавить изолированные регрессии на позднюю загрузку, закрытую **запись и
  ребро**, граничные моменты, неверные обе оси и cursor со сменой временного
  среза; текущую и желаемую семантику тестировать отдельно, не считать тесты
  предложения доказательством уже имеющихся возможностей. При решении о двух
  часах включить конфликт `--as-of` с новыми аргументами, half-open интервалы,
  старые записи без полей, единые правила для records/relations/timeline и
  миграционное описание. Прежде чем добавлять `--valid-at`/`--known-at`,
  согласовать область работ и влияние на клиентов.

#### 0.9.5. Архитектурные гейты реализации, а не заготовки будущих фич

- [ ] **Слои и один источник поведения:** реальные операции фильтрации,
  валидации, plan/apply и ошибки доступны без разбора/сериализации Click stdout;
  обработчики преобразуют аргументы и вызывают application, renderer не ходит в
  ФС/историю и не исполняет `next_actions`. Выделять минимально необходимое,
  не обещать, что уже существующие порты E1–E10 реализованы полностью.
- [ ] **Эволюция capability/schema:** реестр различает реально поддержанные
  команды, наборы и комбинации аргументов, conditional requirements, типы,
  defaults, семантику идентичности/scope, режимы действия и side effects.
  Тест с локальным fake-адаптером проверяет добавление нового листа и источника
  без копирования сериализатора, но не рекламирует вымышленные `tree/tags/trace`.
  Различать версии schema ответа, индексного снапшота и данных пользователя.
- [ ] **Query pipeline:** предметный scope/filter до ranking/страницы, порядок с
  реальным tie-break, проверяемое усечение, provenance от источника. Cursor
  зависит от полного запроса и версии алгоритма, а не от выбранного renderer;
  не отбрасывать future temporal fields, folder metadata или graph edge kinds.
  Поддержка новых операторов QuerySpec — только через версионирование и тесты,
  без произвольного Python/SQL и без изменения типов на основе имени файла.
- [ ] **Action pipeline:** план — данные с явно перечисленной областью,
  входными предпосылками/hashes и ожидаемым эффектом; preview не пишет; apply
  перепроверяет полномочия и предпосылки. Не закодировать в базовой схеме, что
  действие всегда трогает один файл, но не реализовывать bundle/rollback ради
  будущего. Для уже существующих частичных действий честно показывать результат
  и recovery, не заявлять all-or-nothing без crash/concurrency tests.
- [ ] **Изоляция:** явные `dataset_id`, root, ограничения и конфигурация на
  каждый вызов, без протекания `_group_roots`/`_group_output` между CliRunner
  или последовательными вызовами; одинаковые ID в разных root не смешивать.
  Для read/preview перехватить попытки записи в source/cache/index/history/XDG,
  в том числе инструмента логирования; в subprocess проверить stdout/exit.
- [ ] **Будущие источники и доверие:** файлы/поля конфигурации — данные, а не
  исполняемый код или разрешения; содержимое может содержать враждебные команды.
  Сохранять escape Markdown/Mermaid, JSON, пути, next_actions как данные;
  закрытые источники или будущий сетевой/плагинный backend не внедрять по умолчанию.
- [ ] **Матрица приёмки:** для каждого из четырёх пересечений (темпоральность,
  теги, дерево, backend/read-only) сопоставить fixture → тест → реализуемая
  инварианта → связанная строка З1–З9 → фактический результат. Тесты на будущие
  идеи без их реализации — только на отсутствие архитектурного запрета и
  сохранение текущих данных, не ложные acceptance tests будущей функции.
  Отдельно проверять старые навыки/промпты и examples после изменения синтаксиса.

### 0.10. Обязательный задел: граница хранения до переделки CLI

**Область поручения:** в реализации этого плана создать и использовать реальные
внутренние границы хранения и адаптировать существующие JSON/JSONL реализации;
это не реализация SQLite и не решение о его включении. Новый frontend CLI не
должен знать, где и в каком формате лежат индекс и история. Это уменьшает объём
будущей переделки, но не гарантирует, что при появлении SQLite вообще не придётся
менять контракты. Новые публичные команды `storage`, настройки драйверов, плагины,
BM25/FTS5, SQL и миграцию производственной истории в этой работе не добавлять.

#### 0.10.1. Выводы аудита реального кода

| Срез | Факт на master и/или в текущем дереве | Необходимая граница |
|---|---|---|
| Индекс | Master `DatasetContext` создаёт `RegistryStore`, `scan()` читает `stats.json`; `ensure_index()` может publish, писать stats и observe даже при чтении. Рабочий `read_index()` строит in-memory, но CLI `index status/rebuild/status` всё ещё обращается к `index_dir`, `current_dir`, `.tmp-current`, JSON shards и `store.publish` напрямую. | Доставать состояние и публиковать только через внутренний сервис/порт; read и rebuild разнести. Путь файлового layout использовать только внутри файлового адаптера, safety-проверки перенести вместе с ним. |
| Parse cache | `validator.py` импортирует `read_parse_cache`/`write_parse_cache`; `write.py` и `changes.py` — `invalidate_parse_cache` из `application/registry.py`. Кэш живёт отдельно от RegistryStore и не охвачен одним портом. | Явная политика no-write; чтение/инвалидация разбора проходят через тот же индексный контур или его дочерний узкий порт; не потерять ограничения `content_hash` и `parser_version`. |
| История и `HistoryBackend` | `src/todoc/ports/history.py` описывает `available/head/read_at/needs_snapshot` для источника образа (`embedded`/`git`); он **не** абстрагирует журнал, refs, GC или экспорт. `application/history.py` напрямую вызывает `journal`/`objects`, читает и пишет `refs.json`; `temporal.py`, `context.py`, `changes.py` читают события напрямую, CLI тоже импортирует `read_events` и в рабочем снимке проверяет пути журнала. | Источник образа и хранилище событий — независимые роли: сохранить работающий `HistoryBackend` и gap-filling; добавить отдельную границу журнала/refs/объектов, а не переименовать существующий backend в якобы полный `HistoryDriver`. Перенести проверки безопасности и строгие ошибки в адаптер. |
| Целостность | `journal.iter_events` master пропускает повреждённые строки; наши `_strict_relation_events` и `read_refs_strict` защищают только часть путей. В master `RegistryStore.publish` удаляет старый `current/` до rename; по одному docstring нельзя обещать crash-atomic snapshot. Запись файла в `application/write.py` предшествует `history.record`: отказ истории возможен после изменения файла. | Определить явные состояния повреждения и частичного применения, failure-injection и recovery; не заверять пользователя в транзакции между файлами, индексом и журналом, которую код не обеспечивает. |
| GC/экспорт | Текущий `history gc` отдельно переписывает события и удаляет объекты; режим `keep_objects` способен удалять даже referenced снимки. `history export` копирует layout каталога; общий интерфейс пока отсутствует. | План GC обязан честно перечислять потерю восстанавливаемости и защищённые/удаляемые элементы до apply. Перенести логику за границу и не представлять JSONL-копирование как универсальный экспорт SQLite. Политика retention и необратимых удалений — отдельное явное решение пользователя. |

#### 0.10.2. Минимальные контракты портов и правила

Конкретные имена и Python-типы могут быть уточнены в З0-S, но **семантика этих
операций обязательна**, покрывается контрактными тестами и не выражается как пути
к `.json` или таблицам SQL. Перед кодом сравнить с существующим `WritePlan`,
`HistoryBackend`, `RegistryStore` и данными обоих снимков, не писать параллельные
реализации одной логики.

**Индекс и кэш (`IndexRead` / `IndexWrite`, возможны имена `IndexDriver` и
`ParseCache`):**

- [ ] Read-only метод возвращает статус `missing | valid | stale | corrupt |
  inaccessible` и, только если доступен, проверенный снимок с `dataset_id`,
  версией, fingerprint входов, структурами folders/documents/records/relations/
  mentions/diagnostics и неизменёнными предметными полями. `missing` ≠ `corrupt`
  ≠ ошибка доступа. Вычисление fingerprint источников/конфигураций — отдельная
  обязанность сервисного слоя, не деталь JSON-path или конкретного БД-драйвера.
- [ ] Явно отделить `read_published` (без записи), строгое построение in-memory
  и `publish`/обновление stats/cache (только подтверждённое действие). Холодный,
  повреждённый, чужой dataset/version или устаревший cache не выдавать за
  актуальную истину. Ошибки чтения исходников и конфигов не превращать в miss;
  политика использования битого кэша и восстановление индекса — явная.
- [ ] Не требовать материализации всей базы как условия работы порта: отделить
  логический снимок и минимальные возможности запроса/итерации от конкретного
  JSON-представления. Определить порядок, стабильность identity, области фильтров,
  курсор и признак полноты/диагностик; существующий JSON может материализовать
  данные целиком. Не добавлять сейчас спекулятивный API FTS или обещание скорости.
- [ ] Parse-cache: ключ dataset/root + нормализованный путь + content hash +
  parser/schema version; hit допустим только при проверке всех влияющих входов.
  При несовпадении — miss, при ошибке источника — диагностика. Явные методы
  чтения, записи и инвалидирования; read/preview никогда не записывают и не
  инвалидацируют. Хеш-кэш `(mtime,size)` — только оптимизация, не доказательство
  неизменности содержимого. In-memory и JSON должны возвращать эквивалентные
  данные/ошибки при одинаковом входном снимке.
- [ ] Публикация с предусловием fingerprint/generation и определённым порядком
  обновления индекса, stats и history. При сбое любой стадии сообщать реальные
  результаты и возможную частичность. Если обещается «старый индекс остаётся
  читаем», это должно быть обеспечено и проверено отдельной реализацией с
  инъекцией отказа и конкурентным чтением, а не названием `atomic`.

**Хранилище истории (`HistoryStore` / предполагаемый `HistoryDriver`):**

- [ ] Независимо от `HistoryBackend` предоставлять операции: строгое чтение и
  последовательность событий с полноценными полями/неизвестными атрибутами;
  чтение и проверка целостности объектов по digest; чтение refs/head/tags;
  дописка события, запись снимка и изменение refs с проверкой предусловий;
  построение плана GC, применение подтверждённого плана, экспорт и диагностика.
  API может быть разделён на узкие read/write-порты. Read не создаёт файлы,
  connection state или служебные каталоги. Поддержать dataset scope, порядок и
  повторяющиеся события; отличать пустую историю от corrupt/inaccessible и
  найденной ревизии с недоступным before-image.
- [ ] Не менять существующие event fields/`change_id`, `rev`, refs и hashes при
  адаптации; writer master вычисляет `rev` как первые 12 hex SHA-256 от
  канонической сериализации события без `rev`, но не записывает `rev` в строку;
  reader добавляет его из исходной обрезанной строки только при отсутствии поля.
  Одинаковые события и коллизии усечённого hash **теоретически возможны**. Не строить алгоритм на
  предположении глобальной уникальности `rev`, строкового порядка или выдуманного
  идентификатора SQLite. Пустая история, duplicate/ambiguous rev, битый UTF-8,
  оборванная строка, дубликат JSON-ключа, неизвестные поля и недостающий объект
  должны иметь детерминированную политику; не пропускать повреждение там, где
  операция утверждает полноту или собирается менять историю.
- [ ] `embedded` и `git` — независимая политика источника содержимого поверх
  хранилища; сохранить настройку и деградацию, gap-filling между коммитами и
  диагностику, не требовать git для embedded. Использовать порт для `log`,
  `show/diff/blame`, `timeline`, `context`, `records undo-relation`, `change`,
  `tag`, `revert`, `stale`, `adopt/gc/export`, а не только новых CLI-обёрток.
- [ ] Публикация исходного файла и запись history могут завершиться частично:
  общий результат обязан различать «не выполнено», «файл изменён, history не
  записана» и успех. Для `adopt`, `gc` и `export` также моделировать стадии,
  hash/токен предусловий, конкуренцию и отказ; предлагаемый recovery должен
  опираться на фактически сохранённые данные, без автоматического повтора опасной
  операции. SQLite-транзакция сама по себе не атомарна с операцией файловой системы.

**Общие границы:** scoped composition per dataset; выбор источника образов не
подменяет выбор хранилища, и наоборот. Разделить version схемы пользователя,
индекса, истории и output; payload с неизвестными полями не обрезать. Не
объявлять универсальным raw JSON layout, bytes compressed blob или абсолютный
путь. История и её backup — невосстановимые данные, cache/index — производные.
В `status`/`doctor` говорить о проверенном состоянии, не о свежести только по
наличию указателя. Для SQLite позже отдельно проверить `mode=ro`, WAL/SHM,
подключение, блокировки и файловые side effects: одно слово «read-only» не
доказывает отсутствие записи в sandbox/XDG или рядом с БД.

#### 0.10.3. З0-S — реализация границы и гейт против двойной работы

**Порядок:** после P0–P2 и до окончательной миграции З1–З8. Интеграционный
этап сначала сохраняет обе стороны, адаптирует несовместимые фикстуры и получает
базовый full-test результат. Затем З0-S строит границы на фактическом объединённом
срезе; З3 и обработчики З5–З8 вызывают их, а не копируют JSON/JSONL-логику.
На маршруте B интеграции нет: З0-S строится на чистом master с переданными
артефактами (§0.11); регрессии будущего CLI, не затронутые З0-S, могут оставаться
классифицированно красными до своей задачи (§0.4). При интеграции старые частичные
фиксы и регрессии сохраняются; не переписывать всё заранее под предположительный SQL.

- [ ] **S1 — инвентаризация и карта:** перечислить все вызовы и прямые импорты
  index/parse-cache/history на данном снимке (включая `service.py`, `cli.py`,
  `validator.py`, `write.py`, `changes.py`, `temporal.py`, `context.py`,
  `history.py`). Для каждого указать read/preview/apply, side effects, проверку
  path, семантического владельца и новый интерфейс. Перед выносом зафиксировать
  поведение/fixtures и подтвердить, что все 63+ leaf покрыты матрицей. Вносить
  один общий порт, не копировать обход для каждого нового семейства.
- [ ] **S2 — индекс/кэш:** определить typed result/state и реальные ограниченные
  `IndexRead`/`IndexWrite` интерфейсы; завернуть существующие JSON `RegistryStore`
  и parse cache, выделить no-write строителя. Перенести `index status/rebuild`,
  `status`, `doctor` и потребителей read на общий сервис. Включить строгий hash
  источников и config без смешивания schema и сериализации. JSON JSONL хранятся
  в прежнем layout, если нет отдельно согласованной миграции.
- [ ] **S3 — история:** обернуть текущие journal, refs и object store за
  `HistoryStore`, внедрить в `HistoryRecorder` и прочие потребители, сохранив
  `HistoryBackend` embedded/git как независимый источник образов. Перенести
  строгий parser и containment без ослабления существующих BUG-012/013/029/038;
  объединять проверки по фактическому общему назначению, не заменять на
  терпимое `journal.read_events`. `history gc` и `export` различают план,
  применение, потери снимков и повреждённую историю.
- [ ] **S4 — доказательство сменяемости, не SQLite:** параметризовать один набор
  contract-тестов на настоящий JSON/JSONL и независимый минимальный in-memory
  fake (fixture только для тестов, с проверкой вызовов и ошибок). JSON+embedded,
  JSON+git где доступен, а также два независимых fake index/history и их
  комбинации; на fake запускать те же application use cases и несколько
  CLI/subprocess сценариев через разрешённый composition seam. Проверить, что
  при fake обращения к файловым индексным/историческим адаптерам перехватываются
  и запрещены. Это доказывает границу на данном наборе операций, **не** готовность
  SQLite. Для CLI subprocess описать реалистичный способ инъекции (тестовый
  composition harness, без нового публичного флага), без побочных runtime API.
- [ ] **S5 — error/failure matrix:** cold/warm/stale/corrupt/inaccessible,
  второй dataset, duplicate revision, missing/corrupt snapshot, неизвестные
  event fields, конкурентное изменение при preview/apply, публикация и запись
  по стадиям с injected failure, read-only root + XDG, безопасный recovery,
  git absent/gap-filling. Проверить Unicode, нулевые/большие данные, порядок и
  cursor; ошибки fake и JSON логически совпадают, не теряются коды и полнота.
- [ ] **S6 — seam-gate:** `cli.py` и application use cases за исключением
  composition/adapters не импортируют файловый `journal`, `objects`, файловые
  cache helpers и не обращаются к `index_dir/current_dir` или hardcoded shards.
  Известные исключения (например, чтение **исходных** файлов датасета для
  validation/search) не запрещать: речь о storage-деталях, а не об отказе от
  filesystem как источника истины. Дополнить проверку архитектуры анализом
  импортов **и** подменой fake: одного `rg` недостаточно. Существующие JSONL
  низкоуровневые тесты остаются тестами адаптера, а не обязательным API ядра.
- [ ] Запускать связанные тесты после каждой правки. После З0-S выполнить полный
  pytest, branch coverage 100% и остальные этапные проверки §6; на маршруте B
  отдельно классифицировать заранее известные несвязанные FAIL из baseline:
  storage-контракты и затронутые регрессии обязаны проходить, а общий гейт остаётся
  открытым до реализации остальных функций. Новые падения/потерю покрытия не
  маскировать baseline; итоговый DoD требует полного зелёного набора и 100%.
  Тесты хранить в репозитории как `tests/unit/test_storage_contracts.py` и требуемые CLI tests,
  реальные имена утвердить до реализации. Проверить как минимум существующие
  `tests/unit/test_history.py`, `test_strict_relation_history.py`,
  `test_scanner_registry.py`, `tests/cli/test_unified_{gc_safety,history_export,history_adopt,index_rebuild,index_status,log}.py`
  и добавленные master status/interop. Не удалять failing проверки ради гейта.

**Текущее доказательство:** на рабочем незакоммиченном дереве выборка из семи
существующих storage/history/index тестовых файлов (history, strict relation
history, scanner registry, gc safety, history export/adopt и index rebuild) —
**200 passed** в изолированных pytest fixtures. Это не объединённый master, не
доказательство существования границы и не проверка SQLite.

#### 0.10.4. Будущая SQLite-итерация — контракт handoff, не реализация сейчас

Когда пользователь отдельно утвердит идею SQLite, команда, сохраняя порт, отдельно
разрабатывает и сравнивает **четыре сочетания** index JSON/SQLite × history
JSONL/SQLite с источником образов embedded/git; не фиксировать в текущем плане
размеры и скорости как уже доказанные. Сначала согласовать FTS/BM25 и различия
rank, поскольку строгая идентичность поиска несовместима с незаявленной сменой
ранжирования. Не обещать O(Δ): full scan, config/ignore, парсинг и пересчёт
зависящих ссылок должны учитываться в измерениях.

Для будущей миграции history предусмотреть: неизменяемый backup и проверку его
восстановления; сохранение последовательности, original event/refs, неизвестных
полей и byte-exact образов; `rev`/digest/порядок, duplicate и усечённые коллизии;
read-only подготовку и preview плана; согласованный apply и отказ при изменении
исходника; инъекции сбоя до/во время/после переключения; проверку SQLite WAL/SHM,
checksums, `show/revert/undo/tag/log` и обратного round-trip. Если rev вычислен
из исходной строки, простая повторная сериализация JSON может поменять rev:
сохранить необходимые исходные байты/алгоритм и проверить до переключения.
Никакого удаления JSONL-источника или переключения config до проверенного
экспорта/восстановления и согласования. Определить взаимосогласованность файла
данных и журнала, и не обещать всеобщую атомарность через отдельные БД.

### 0.11. Выбранный маршрут: чистый master, только документы

Пользователь выбрал старт в новой сессии от актуального чистого master и
публикацию только четырёх документов: мастер-плана, архитектурного предложения,
этого плана и идеи unified CLI. Старые tests, производственный код, репорты и
историю не переносить. Предыдущие обсуждения объединения и backup относятся к
альтернативному маршруту и не являются требованиями для выбранного старта.
Нынешние пользовательские файлы при публикации не удалять, не сбрасывать и не
переименовывать; при будущей работе с реальными данными отдельно обеспечить
backup и восстановление до потенциально опасных изменений.

- [ ] В новой сессии проверить актуальный master/HEAD, правила ветки и наличие
  четырёх документов. Учитывать свои ограничения среды; не менять ветку или
  выполнять merge вне разрешённых операций. Исторические 13 конфликтов и 39
  падений пробного слияния не являются baseline чистого master.
- [ ] Проверить и записать baseline тестов **самого master**. Таблица §0.6 —
  список 28 инвариантов и исторических selectors, а не набор переданных тестов.
  До реализации создать новые тесты по соответствующим сценариям на временных
  datasets, включая негативные случаи; если описание недостаточно для проверки
  — зафиксировать `не проверено`, запросить уточнение и не закрывать регрессию.
  Не требовать доставить отсутствующие старые тесты при достаточном описании.
- [ ] Отдельно классифицировать известные ожидаемые FAIL новых целевых тестов
  до реализации. Тесты и исходники master не перезаписывать молча, не засчитывать
  старые результаты как новый PASS, полный гейт закрыть после реализации всех
  обязательных сценариев. Не переносить тестовую активность в реальный demo.
- [ ] Повторить полный inventory идей, зависимостей и потребителей по актуальному
  master. Подготовка плана не является разрешением на реализацию; точечные тесты
  запускать после правки, полный этапный набор — по согласованным правилам.

## 1. Критерии успеха

Целевой результат — **один новый контракт по умолчанию для всех команд**, без
постоянного v1/v2-переключателя, без старого default и без двух вариантов бизнес-
логики или ответа. Эта масштабная переделка прямо следует уточнённой цели пользователя.
Проверять старые вызовы и обновлять потребителей обязательно, но полная обратная
совместимость с меняющимся JSON/exit code технически не обещается. Выполнение плана
по-прежнему только после отдельного прямого разрешения пользователя.

1. Для каждой листовой команды реестр задаёт возможности и безопасный ответ при
   отсутствии аргументов; прогон всех команд без параметров даёт успешную
   подсказку или результат и не производит запись без явного `--apply`/другого
   подтверждённого действия. Исключение — реальные ошибки окружения/доступа,
   которые не маскируются успехом.
2. `skills tree` и `docs tree` показывают настоящую иерархию, имена папок и пути;
   `flat`, `tree`, `graph` доступны по применимости, JSON и Markdown несут одни
   сведения, совместимый `--output table` остаётся. Неизвестный/неприменимый
   вид → успешный фактический вид с диагностикой и без потери данных.
3. Фильтры применяются до ограничения; `total`, `returned`, `truncated` и курсор
   не утверждают ложную полноту. Пустой или устаревший индекс не приводит к
   записи при чтении: актуальные данные вычисляются в памяти.
4. Все листы, группы и корневой вызов подчиняются единой грамматике раздела 4;
   функциональные различия объявлены в реестре, а не создают произвольные CLI-
   диалекты. Матрица проверяет не только наличие имён, но и фактическое поведение.
5. Один целевой контракт включён по умолчанию; матрица старых потребителей,
   миграция, E2E и гейты раздела 6 проверены. Метрики baseline и результата на
   одинаковых данных приложены без недоказанных заявлений об экономии.

## 2. Вне скоупа

- Создание UI, MCP-сервера, сетевых интеграций, LLM-ранжирования и новых типов
  датасета; реализация `project`/`context.current_project` как фильтра.
- Массовое переименование документов, автоматическое исправление датасета и
  мьют/редактирование сторонних скилов.
- Добавление `table` как четвёртого вида или графовых связей там, где их нет.
- Выполнение этого плана, коммит или публикация без отдельного разрешения.

## 3. Глобальные ограничения

- `--view`: только `flat`, `tree`, `graph`; `--output` по умолчанию `json`,
  также `markdown` и поддерживаемый совместимый `table`.
- Все предусмотренные поля выдаются по умолчанию; проекции задаёт пользователь.
- Вызов без опций не выдумывает обязательные входы и не запускает мутации;
  в `data` указывать `executed: false` при информационном ответе вместо действия.
- Корректные результат и fallback вида: `ok: true`, exit 0; настоящая ошибка
  данных/доступа/фильтра: `ok: false`, ненулевой exit. `diagnostics` с
  `severity: info` и `next_actions` видны во всех форматах.
- JSON stdout — ровно один JSON; `next_actions[].argv` — массив аргументов,
  никогда не исполняется автоматически. Не ломать mute, безопасность путей,
  корректность связей, `--preview`/`--apply` и проверки хешей.
- Только запрошенная выборка: фильтрация до лимита, явное усечение и отсутствие
  скрытого расширения области из-за игнорирования фильтра.
- Проходят полный `pytest`, 100% branch coverage, `todoc validate --root demo --all`
  без диагностик и `tools/linkcheck.py` без битых ссылок.

## 4. Архитектура и файловая карта

### Базовые контракты

- `src/todoc/output/capabilities.py`: `CommandCapabilities` — имя команды,
  поддерживаемые виды/поля/фильтры, дефолты и подсказки; `get_capabilities(name:
  str) -> CommandCapabilities`. Реестр строится один раз, покрытие всех листьев
  проверяется интроспекцией Click. Для результата не-выборки явно объявить
  `views=()` и не навязывать ему дерево.
- `src/todoc/output/views.py`: единый pipeline проверки вида, фильтров, проекции,
  стабильной сортировки, ограничений и сериализации. Адаптеры предоставляют
  типизированные элементы и, где применимо, дерево или рёбра; набор структурных
  ключей определяется формой и источником, а не выдумывается для всех команд.
  У файлов есть реальный `path`, у записи/типа/события — её реальная идентичность;
  у переменной state — ключ. Не требовать `path` у событий и строк, не терять
  идентичные параллельные рёбра. Контракт и список структурных полей каждой формы
  фиксируются примерами и schema-тестами до подключения обработчиков. Реестр
  задаёт допустимые поля, виды и фильтры; все поля предусмотренной формы по умолчанию
  включены. Сигнатуры и внутренние структуры исполнитель определяет по fixtures,
  не закрепляя прежнюю ошибочную универсальную модель `id + path`.

- `src/todoc/output/envelope.py`: единый `emit` для JSON, Markdown и table;
  нормализовать успехи, ошибки и discovery, включая Click parse errors. Версия
  конверта явно задаёт новый единый опубликованный контракт; сохранить верхние
  ключи `schema_version`, `ok`, `data`, `diagnostics`, `next_actions`, присвоить
  новой несовместимой схеме `schema_version: 2`. Это версия схемы, не параметр
  выбора старого контракта. Схемы и политика их будущего изменения документируются.
- `src/todoc/service.py`, `application/validator.py`, `application/registry.py`,
  scanner/search/history: чистый сбор без записи parse-cache, индекса, статистики,
  истории и state. Передавать разобранные документы между validation и mentions в
  памяти либо измерить стоимость повторного разбора. Переиспользовать снимок только
  при проверяемой актуальности всех влияющих входов. Политика состояния, ошибок и
  согласованности — в разделе «Снимок и история» ниже. Явная публикация/observe —
  отдельное разрешённое действие, а не скрытый побочный эффект чтения.

- `src/todoc/cli.py`, `src/todoc/application/query.py`: подключение реестра,
  корректные фильтры, структура данных и адаптеры совместимости. Список листовых
  команд и фактических потребителей берётся из интроспекции и поиска в З1.
- `tests/unit/test_output_views.py`, `tests/cli/test_unified_output.py`,
  `tests/cli/test_unified_read_only.py`, существующие `tests/cli/test_cli*.py`,
  `tests/unit/test_query.py` и `tests/unit/test_scanner_registry.py`: контракт,
  регрессии, миграция и безопасность.
- `docs/state/03-cli-reference.md`, `README.md`, `SKILL.md`,
  `demo/references/state/03-cli-reference.md`: документировать единый контракт,
  сохранить ссылочную целостность. Запись изменений — в существующий релизный
  процесс проекта, не создавать отдельный релиз автоматически.

### Решения для реализации и проверки

- `--fields` и `--exclude-fields` взаимоисключающие; неизвестное поле или
  неподдерживаемый фильтр — `usage.error`, без частичного успешного результата.
  Структурные поля конкретной формы (реальные идентификаторы и пути при наличии,
  родители дерева, концы рёбер, `truncated` и cursor) не отбрасываются проекцией;
  требовать их только там, где они определены схемой этой формы.
- `--within` — нормализованный путь относительно выбранной области: для docs —
  DATA_ROOT, для skills — vault внутри DATA_ROOT (совместимость с текущим
  `--within coding/git`). В ответе/справке указывать область; `..`, абсолютные
  пути и выход через symlink за пределы соответствующей области отклоняются.
  Отбор по границе сегментов (`a` не включает `ab`), а не по простому префиксу.
  Фильтр результата не обещает ограничить физический scan: отдельно измерить и
  задокументировать фактическую область сканирования. Все фильтры — до лимита.
- `--depth`: 0 = только корень, 1 = ближайшие потомки/соседи. Для graph множество
  достижимых узлов определяется кратчайшим расстоянием по выбранному направлению
  после фильтра типа; graph содержит все исходные рёбра между достигнутыми узлами,
  включая параллельные рёбра и self-loop на глубине 0. `tree` — дерево обхода с
  явными ссылками на повтор/цикл, а не полный набор рёбер. Исходное направление
  сохраняется отдельно от направления обхода; для relations определить единый
  документированный дефолт направления при инвентаризации.
- `--limit` считает элементы flat/tree и рёбра graph, контекстные родители/узлы
  не входят в `returned`. На каждой странице повторять минимальные корни и пути,
  нужные для самостоятельной интерпретации; помечать их как контекст, не считать
  результатами и не обрывать графовые концы. `total` — совпадения до страницы,
  `returned` — результаты на странице, `truncated` и cursor показывают наличие
  продолжения. `--limit 0` отклонять как usage error, чтобы не создать cursor без
  прогресса; отрицательные лимиты тоже отклонять. Зафиксировать детерминированный
  порядок и tie-breaker по реальной identity, включая разные датасеты и повторные
  рёбра. Без стабильной идентичности не обещать переход по cursor.
- Cursor непрозрачен, versioned, ограничен размером и привязан к dataset/root,
  контракту, query, виду, сортировке, фильтрам, направлению и полному fingerprint
  входов; любые несовпадения → явная ошибка без выдачи ложной полноты. Подмена
  курсора не должна обходить валидацию, ограничения или containment; секретность и
  криптографическая защита не предполагаются без отдельной реализации подписи.
- `records read --record-view` — именованная проекция записи, `--view` — всегда
  форма `flat/tree/graph`. Старые `--view summary/full` могут переводиться в
  `--record-view` только для однозначно распознанных имён, с диагностикой; имена,
  совпадающие с видами, в `--view` всегда значат вид. Любое другое неизвестное
  значение вида получает согласованный fallback, а не интерпретацию как проекция.
  Конфликт двух проекций — ошибка. Устаревшие `--max-depth` и другие синтаксические
  алиасы допустимы лишь когда однозначно переводятся в один целевой контракт,
  сообщают о замене и имеют задокументированную политику удаления; не воспроизводить
  старые дефекты. Согласовать и указать несовместимые случаи в миграции.
- Один контракт с `schema_version: 2` по умолчанию; не вводить `--contract-version`
  и не поддерживать параллельные v1-ответы. Golden fixtures старого CLI служат
  анализу миграции, а не требованию byte-for-byte совместимости. Проверить и обновить
  встроенные/демо-промпты, docs, benchmark и тесты; неизвестных внешних клиентов
  предупредить в миграционном руководстве. Совместимость означает исправные ясные
  переходы, поддерживаемые однозначные синтаксические алиасы и перенесённых клиентов,
  но не сохранение всех старых форм, ошибочных результатов и exit code.

- Подсказки по умолчанию: одна короткая информационная запись с поддерживаемыми
  видами и именами опций проекции; `next_actions` — не более двух релевантных
  действий, кроме уже существующих обязательных по смыслу. Полный список полей
  доступен через `--fields-help` в том же конверте, в том числе без обязательных
  аргументов и без чтения датасета, если известен статически. Режим обнаружения
  указывает недостающие входы и `executed: false`; если root и входы достаточны,
  безопасная команда действительно выполняется и возвращает данные, а не
  `executed: false`. Синтаксические ошибки и ошибки доступа остаются ошибками.

### Единая грамматика CLI — обязательная спецификация

Инвентаризация: на 26.11.2026 Click обнаруживает 60 листовых команд, 38 имеют
обязательный аргумент или параметр. Это baseline, а не фиксированное число на
будущее: генерация матрицы идёт из актуального дерева команд. Кроме листьев,
покрыть корень и все промежуточные группы (`docs`, `records`, `relations`,
`skills`, `types`, `state`, `index`, `history`, `change`, `docs flow`).

| Повторяемое правило | Единый смысл и проверка |
|---|---|
| Адресация | `--root` повторяем там, где поддерживаются несколько датасетов; `TODOC_ROOT` — только явный документированный fallback. В каждом ответе указать фактический dataset и область. Где несколько root недопустимы — отказ, а не молча первый. В матрице раскрыть исключения до миграции. |
| Расположение опций | Глобальные `--root`, `--output`, `--no-input` работают до и после групп/листа одинаково; явное значение листа сильнее явного группового, последнее на одном уровне — по документированному правилу; повторяемые roots не теряются. Конфликты без однозначного смысла — ошибка. Тестировать цепочки `todoc --output table skills tree`, `todoc skills tree --output table` и обе вместе. |
| Формы и форматы | `--view flat/tree/graph` обозначает только представление; `--output json/markdown/table` — только формат. По умолчанию JSON и типичный для команды вид из идеи. `table` — формат, не вид. Недоступный/неизвестный вид даёт успех и реально доступный fallback с `requested_view` и `actual_view` в структурированных метаданных и `view.fallback` в diagnostics. Иные ошибки не маскируются. |
| Поля | `--fields a,b`, `--exclude-fields a,b` — одинаковые правила, без них все поля выбранной формы. Структура, identity и метаданные страницы сохраняются; неизвестное поле/конфликт опций — ошибка. Для вложенных полей заранее задать синтаксис, допустимые значения и что происходит с отсутствующими необязательными полями. Discovery предоставляет точный список для каждой формы. |
| Отбор | `--within`, `--type`, `--tag`, `--query`, `--section`, `--relation` применяются по И до сортировки/страницы; предметные пространства имён, особенно `--tag` документа и метки истории, разделяются по §0.9.3 и не притворяются одинаковыми; неприменимый фильтр — явная ошибка с подсказкой, не игнорирование. Повторения каждого фильтра и сравнение регистра описать в реестре и тестах; не вводить фиктивные фильтры для действий. |
| Пределы | Общие `--limit`, `--depth`, `--cursor`, `--budget` работают одинаково по объявленной единице: бюджет не объявлять токенами, если он в символах или байтах. Таблица возможностей сообщает единицу, допустимый диапазон и какой объект отсекается. Один cursor не принимается другой командой или query. |
| Discovery | Корень, группы и листы без аргументов используют тот же конверт, короткие применимые опции/следующие шаги; безопасный вызов с достаточными входами выполняется, недостаточный — `executed: false`, `ok: true`, exit 0, с конкретными недостающими входами. Ошибочный явно указанный ввод и ошибка доступа → ошибка. `--fields-help` доступен без данных. Исключения Click `--help` и `--version` документировать отдельно как справочный протокол, не прятать расхождения. |
| Действия | Все изменения — единый review-first: `--preview`/отсутствие `--apply` показывают план, `--apply` разрешает только указанное действие; `--preview` и `--apply` вместе — ошибка. Preview не пишет в root, кэш, историю, XDG, git и внешнюю цель. `--force`, `--write`, `--fix`, `--dry-run`, `--adopt`, `--out` не подменяют `--apply`; старые формы классифицировать и мигрировать. Это изменение опасных старых вызовов. |
| Ответы и ошибки | Во всех форматах сохраняются `ok`, результат, информационные/ошибочные diagnostics, `next_actions`, `executed` для discovery/действий и метаданные выборки. JSON stdout — один объект даже при ошибках разбора; stderr не участвует в JSON. `severity: info` добавить в доменные модели и потребителей, а не только рендерер. `next_actions[].argv` — реальные argv без подстановок; шаблон с незаполненным значением обозначать отдельно, не как исполняемую команду. |

`--output markdown` для графа = Mermaid плюс текст/структурированные сведения,
которые Mermaid не умеет кодировать: метаданные, все поля и диагностики; table
сохраняет тот же смысл, при необходимости отдельные секции, а не обрезку. Проверить
экранирование Markdown, Mermaid, переводов строк и hostile label. Не заставлять
одиночный объект или результат действия притворяться деревом: общие envelope,
ошибки и discovery действуют везде, возможности представления — по данным.
Переход с raw `skills read --output markdown` и `types guide --format/--out`
проверить отдельно: pipe-потребители изменятся; обновить их, а не оставить второй
особый формат под тем же флагом. Для файлового экспорта разделить явное действие
записи и формат вывода команды.

**Единая форма результата:** до реализации зафиксировать примеры JSON и JSON Schema
для коллекции, дерева, графа, одиночного объекта, диагностики, preview/apply и
корня/групп. У всех один envelope и общая секция метаданных внутри `data` с
`command`, фактической областью, `requested_view`/`actual_view` где применимо,
а также едиными `total`, `returned`, `truncated`, `next_cursor` для страниц;
для непагинируемой операции — явное documented отсутствие, не выдуманные значения.
Имена предметных полей остаются значимыми; атомарные строки, key/value и события
адаптируются без фиктивного файлового path. На примерах показать JSON и все поля,
соответствующий Markdown и table. Политика null/отсутствия, имена корней дерева,
identity и границы выбранной области должны быть одинаковы во всех адаптерах.

### Карта охвата всех семейств команд

| Семейство | Общий контракт и специфичная семантика |
|---|---|
| Корень и группы | Один информационный envelope; список команд и применимые опции по реестру. `--help`/`--version` — справочные исключения, не результат данных. |
| `check-config`, `check`, `scan`, `validate`, `doctor`, `status`, `index status` | Одиночный отчёт или коллекция диагностик; выборки получают единые фильтры/пределы по применимости. Режим исправления `doctor` и `index rebuild` — действие с preview/apply. |
| `skills tree/read/attach/import` | Tree/flat и реальный vault; `read` — одиночное ограниченное содержимое, attach/import — действия с явной внешней целью и preview/apply. |
| `docs search/read/suggest/links/tree/flow/new/edit` | Поиск и ссылки — flat, tree — иерархия, read — ограниченный одиночный объект; flow отдельно учитывает семантику walk/render и возможную запись. New/edit — действия. |
| `records list/query/aggregate/read/create/undo-relation` | Выборки и агрегаты — flat, read — объект с именованной проекцией; create/undo — действия. Query-файл и `--as-of` не теряются при переносе. |
| `relations graph/tree` | graph содержит реальные рёбра, tree — обход; исходное направление и повторные рёбра не теряются. |
| `types list/show/prompt/guide` | Каталог — flat, show/prompt/guide — содержательный объект; отдельное файловое сохранение — действие, raw stdout мигрирует в один формат. |
| `state get/list/set/unset`, `context`, `explain-path` | Чтение — объект/список; set/unset — preview/apply с изоляцией XDG, не придумывать file path для ключа state. |
| `log/show/diff/blame/timeline`, `history gc/adopt/export`, `revert`, `tag`, `stale` | История/различия — объект или flat-события, наблюдение внешних изменений явно; gc/adopt/export/revert/tag и ack — действия, включая побочные эффекты history backend. |
| `change list/open/show/validate/verify/apply/archive/revert`, `fix`, `init`, `index rebuild` | Отчёты и списки отдельно от мутаций; open/apply/archive/revert, fix и init — действия с preview/apply, включая проверку хеша и all-or-nothing, где она уже гарантирована. |

Матрица З1 сверяет каждую команду с этой картой по фактическому Click; изменение
наименования или набора команд фиксируется и проверяется, не оставляет непокрытый
лист. У разных предметных операций могут быть разные входы и наборы данных, но
один и тот же флаг нигде не получает другой смысл. Сохранить функциональные
селекторы `--section`, `--line-range`, JSON Pointer, CSV columns/rows и лимиты
progressive disclosure; «все поля ответа» не означает «выдать весь файл».

**Нормативный каркас JSON:** один объект с верхними ключами, фиксированными выше;
в `data` у всех результаты представлены как `result`, а общие метаданные — как
`meta`. Для списка `result.items`, для дерева `result.root`, для графа
`result.nodes`/`result.edges`, для объекта/отчёта `result` содержит собственные
поля; действие дополнительно имеет `data.executed` и план либо результат.
`data.meta.command` и `data.meta.scope` присутствуют всегда (`scope: null`, если
датасет не выбран); у выборок добавляются `requested_view`, `actual_view`,
`total`, `returned`, `truncated`, `next_cursor` с одним смыслом из раздела 4.
Для discovery задать `data.executed: false` и `result` с недостающими входами;
для ошибки `ok: false`, `executed: false` если действие не выполнено и диагностика
с кодом. `null` и отсутствие других optional-полей определить в Schema до кода.
Пример ниже иллюстрирует форму, а не полный набор полей документа или дерева:

```json
{"schema_version":2,"ok":true,"data":{"meta":{"command":"docs search",
"scope":{"dataset_id":"dataset-example","within":"."},"requested_view":"flat",
"actual_view":"flat","total":1,"returned":1,"truncated":false,
"next_cursor":null},"result":{"items":[{"id":"doc:a","path":"a.md"}]}},
"diagnostics":[],"next_actions":[]}
```

Полная schema/fixtures каждого типа фиксируются в З1 на основе реальных данных;
у не-выборок поля вида/пагинации отсутствуют, а не выдумываются. Примеры для
fallback, ошибки, списка, двух страниц дерева/графа, discovery и preview должны
однозначно описывать контракт до написания адаптеров. `total` допускается только
при фактическом подсчёте; если производитель не может знать полноту, требуется
честная типизированная отметка об этом, не фиктивное точное число.

### Снимок, история и границы достоверности

- `validate_dataset` на cache miss вызывает `write_parse_cache`; явный no-write
  флаг/контекст обязателен для всех read и preview, включая `scan` и `validate`.
  Проверить холодный/битый cache, свежий/битый индекс и запрет записи; не считать
  отсутствие ошибок записи доказательством отсутствия попытки записи.
- Чистое чтение не вызывает `observe_history`. Явная запись/`index rebuild`
  может наблюдать внешние изменения; `log`/`blame` до наблюдения показывают только
  реально зафиксированное и уведомляют о возможной незафиксированной внешней
  правке, если это определено безопасным сравнением. Изменения между наблюдениями
  нельзя восстановить задним числом; не обещать полный журнал внешних изменений.
  Зафиксировать и протестировать политику для обоих history backends и отказов.
- Текущий `corpus_digest` не включает обычные `.config.json` папок и пустые папки,
  хотя они влияют на названия/поиск. Fingerprint курсора учитывает все релевантные
  входы, настройки, порядок, идентичность датасета и версию алгоритма. Тесты меняют
  только folder config, структуру, типы, ranking и правила при неизменных файлах.
- Текущий сканер может переиспользовать хеш по mtime+size и проглатывать ошибки
  обхода, а содержимое читается позднее: один физический проход не гарантирует
  атомарный snapshot. Не утверждать абсолютную актуальность и неизменность при
  параллельной записи. Выбрать реализуемую проверку: snapshot входных байтов или
  повторная проверка fingerprints до ответа; при обнаруженном конфликте — retry с
  ограничением либо ошибка, не успех с ложной полнотой. Разрешить дополнительный
  проход; описать оставшуюся модель согласованности. Ошибка доступа/неполный обход
  → диагностированный неполный/ошибочный ответ, а не полная выборка.

### Проверки повышенного риска

1. Одинаковые имена скилов в разных папках; mute на предке `!section/skill`, а
   не только в имени самого skill; конфиг title, fallback basename и безопасный vault.
2. A→B, B→A, параллельные одинаковые/разнотипные рёбра, mention и self-loop;
   graph хранит рёбра/направления/происхождение, tree отмечает циклы.
3. Совпадение за первым лимитом, полный проход многими страницами без пропусков,
   повторяющийся контекст страниц дерева, старый cursor при изменении конфигурации.
4. Неполные вводы действий и root/group/leaf: успех discovery без побочных записей;
   явные неверные значения, ошибки доступа и конфликт флагов не маскируются.
5. Холодные кэш и индекс, preview всех типов мутаций и внешняя правка: ни попыток
   записи ни изменения root/XDG/git/внешней цели, история не обновляется скрыто.
6. Паритет форматов и парсинг ошибок Click: отсутствие raw stdout и неожиданных
   исключений, существующие K17–K21/K24 и shell-контракты явно учтены.

## 5. Задачи

Все тесты запускаются из корня: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src
.venv/bin/python -m pytest ...`. Для каждой ещё не покрытой части задачи сначала добавить регрессионные тесты и
проверить ожидаемую причину падения там, где дефект воспроизводится; уже
работающие тесты и исправления сохранять, не ломать их ради искусственного FAIL.
Затем реализовать недостающий контракт и повторить относящиеся к правке тесты.
Команды FAIL → PASS ниже описывают сценарий отсутствующей функциональности, а
не требование заново воспроизвести исправленные дефекты. До тестов установить
зависимости проекта в `.venv` по правилам репозитория; никогда не писать
тестовые данные в реальный `demo` — использовать `tmp_path`.

### З1. Инвентаризация и единый реестр возможностей

**Файлы:** создать `src/todoc/output/capabilities.py`,
`tests/unit/test_output_capabilities.py`; изменить `src/todoc/cli.py` и
`docs/state/03-cli-reference.md`.

**Consumes:** Click `cli`; текущие форматы и параметры обработчиков.
**Produces:** `CommandCapabilities` и `get_capabilities(name: str)` из раздела 4;
матрица всех полных имён листовых команд и потребителей старого JSON.

- [ ] Написать тест: рекурсивный обход Click выявляет каждый лист, а множество
  имён точно равно ключам реестра; `skills tree` имеет `tree/flat`, `relations
  graph` — `graph`, `docs read` не заявляет граф.
- [ ] Выполнить `.venv/bin/python -m pytest tests/unit/test_output_capabilities.py -q`
  с `PYTHONPATH=src`; проверить фактические пробелы реестра на интегрированном
  дереве (текущий реестр уже существует), затем закрыть их.
- [ ] Создать реестр, сверить `rg` потребителей и построить матрицу: команда,
  старый JSON, поддерживаемые виды/фильтры/поля, обязательные параметры,
  безопасный сценарий без них, целевой вид и совместимый адаптер. Проверить
  не только README/SKILL, но и встроенные промпты в `src/todoc/data` и
  `demo/.todoc/entity_types/*/prompts`, включая `--view summary/full`; записать
  места в матрицу. До изменения кода снять v1 JSON golden fixtures для З8.
  Для каждой команды определить применимость по данным, не обещая все фильтры.
- [ ] Матрица для каждого листа и группы содержит назначение, canonical синтаксис,
  старые псевдонимы, входы, все поддержанные форматы/виды/поля/фильтры, область,
  счётчики, исполнение/побочные эффекты, все места raw stdout и затронутых клиентов.
  Автопроверка сравнивает реестр и Click по именам, типам, default, aliases и
  поведению, а не только по числу команд. Выявить пересечения смысла флагов
  `--format`, `--output`, `--view`, `--write`, `--fix`, `--force`, `--dry-run`,
  а также документных и исторических `--tag` по §0.9.3.
- [ ] До кода утвердить JSON Schema и минимальные примеры для всех форм из
  раздела 4; примеры проходят одинаковые contract-тесты. Зафиксировать различия
  и обновление K3 без отмены требований пользователя о безопасных пустых вызовах.
- [ ] Повторить тест: PASS; в матрице нет пропущенных листьев. Зафиксировать
  baseline файловых/байтовых размеров и при доступном токенизаторе число токенов
  на одинаковых fixtures с описанием метода, не устанавливая runtime-зависимость.

### З2. Конверт, самоописание и безопасные пустые вызовы

**Файлы:** изменить `src/todoc/output/envelope.py`, `src/todoc/cli.py`;
создать `tests/cli/test_unified_discovery.py`.

**Consumes:** реестр З1. **Produces:** единые сообщения и подсказки для всех
форматов, отсутствие действия при неполном вызове.

- [ ] Тест: каждый лист без опций и аргументов с изолированным root выдаёт exit 0
  и `ok: true`: при недостающем вводе или для опасного вызова — `executed: false`
  и подсказку, иначе безопасный результат. Снимки root, state, git и внешней
  области назначения до/после совпадают; XDG и HOME направить в `tmp_path`.
  Отдельно проверить `init`, `state set`, `docs new`, `fix`, `index rebuild`,
  `history adopt/gc/export`, `skills attach/import`, `tag`, `change apply`.
  Тестировать через `python -m todoc` без TTY, как и CI, а не только CliRunner.
- [ ] Тест: `docs search` без `--query`, `relations graph` без `--from`,
  `records read` без `--id`, отсутствующий `--root` → информация, не traceback;
  невалидный указанный root или ошибка доступа → ошибка, а не успех.
- [ ] Тесты в subprocess для корня, групп и листьев, отсутствующего параметра,
  пустого/неверного явного значения, неизвестного фильтра, ошибок Click, root и
  вывода до/после группы. На каждом результате проверять один envelope и exit;
  проверить что отсутствие `--apply` всегда безопасно даже с другими флагами.
- [ ] Для всех mutating leaf покрыть preview/apply, конфликты, метаданные и
  разрешённые области, включая `history gc`, `init`, `tag`, `state`, `types guide
  --out`, `docs flow render --write`, `skills import/attach`, `doctor --fix`.
- [ ] Тест: JSON/Markdown/table показывают одинаковый смысл `diagnostics` и
  `next_actions`, JSON parseable и stdout содержит ровно один объект; подсказки
  не содержат команд автоматического применения.
- [ ] Запустить `.venv/bin/python -m pytest tests/cli/test_unified_discovery.py -q`
  с `PYTHONPATH=src`; FAIL → реализовать единый диспетчер без избыточной справки
  в каждом ответе → PASS. Сохранить действующие ошибки при действительно неверных
  значениях и требования безопасности операций записи.

### З3. Чистое чтение и фильтрация до лимита

**Файлы:** изменить `src/todoc/service.py`, `src/todoc/application/query.py`,
`src/todoc/cli.py`; создать `tests/cli/test_unified_read_only.py`, дополнить
`tests/unit/test_query.py` и `tests/unit/test_scanner_registry.py`.

**Consumes:** storage seam З0-S (§0.10), `DatasetContext.scan_and_validate` и
`build_mentions`. **Produces:** `DatasetContext.read_index() -> dict[str, Any]`
или эквивалентный сервис поверх порта; корректный
`query_records` с полным набором фильтров до сортировки/лимита.

- [ ] Тест с тремя записями: совпадает только последняя после первых двух;
  `records list --limit 1 --relation ...` и `--until ...` находят её; два
  совпадения при limit 1 → `total: 2`, `returned: 1`, `truncated: true`.
- [ ] Тест: при пустом индексе и после внешнего изменения данных `docs search`,
  `docs read`, `docs tree`, `records list`, `relations graph` видят актуальные
  результаты, а побайтовые снимки root, index, history и state не меняются;
  свежий снимок переиспользуется без публикации. Проверить идентичные ключи
  payload при актуальном, отсутствующем и битом снимке, изменения конфигурации,
  недоступный файл и изменение корпуса во время scan. В fixture отключить
  bytecode (`PYTHONDONTWRITEBYTECODE=1`), XDG state перенести в `tmp_path`.
- [ ] Запустить `.venv/bin/python -m pytest tests/unit/test_query.py
  tests/unit/test_scanner_registry.py tests/cli/test_unified_read_only.py -q`;
  FAIL → создать in-memory payload, перенести соответствующие read-пути на
  `read_index`, оставить явную публикацию в операциях записи → PASS.
- [ ] Перенести в память parsed-doc cache и явно запретить вызовы записи в
  validator/registry даже при cold cache; проверять перехват попыток записи и
  снимки реальных файлов. Добавить тесты для `scan`, `validate`, всех read и
  preview, а также запрета записи/ошибок доступа и большого корпуса.
- [ ] Реализовать явную политику history/observe и безопасной согласованности из
  раздела 4; тесты внешней правки до/после observe, смены конфига и ошибочного
  обхода. Сравнить baseline и новый hot/cold p50/p95 без генерации в рабочем demo.
- [ ] Проверить те же гарантии для preview-веток команд изменения и обхода
  истории; при настоящей ошибке чтения возвращать диагностику, не старый
  результат, представленный как актуальный.

### З4. Поля и дерево папок

**Файлы:** создать `src/todoc/output/views.py`,
`tests/unit/test_output_views.py`; изменить `src/todoc/cli.py`,
`tests/cli/test_cli_skills_tree.py`.

**Consumes:** `get_capabilities`, результаты `scan_skills`/`load_folder_configs`.
**Produces:** `project_fields` и `render_view` из раздела 4.

- [ ] Тесты: include `name,path` оставляет эти поля и обязательный `id`;
  exclude `refs` убирает только его; без проекции возвращаются все поля.
  Одновременные include/exclude и неизвестное поле → ошибка; структурный `path`
  не теряется. Минимальный воспроизводимый тест интерфейса:

```python
from todoc.output.views import project_fields

def test_project_fields_preserves_identity():
    item = {"id": "s:1", "name": "a", "path": "x/a", "refs": 2}
    allowed = frozenset(item)
    structural = frozenset({"id", "path"})
    assert project_fields(item, ("name",), (), allowed=allowed, structural=structural) == {
        "id": "s:1", "path": "x/a", "name": "a"
    }
    assert project_fields(item, (), (), allowed=allowed, structural=structural) == item
```

- [ ] Тест: `coding/git/a` и `process/git/a` сохраняют разные пути, имя папки
  берётся из `title` или basename; мутированный `!` скрыт без `--all` и помечен
  при `--all`, в том числе у потомков muted-предка; глубины 0/1/2 применяются
  одинаково в JSON/Markdown/table. Проверить пути vault, `..` и symlink наружу.
- [ ] Запустить `.venv/bin/python -m pytest tests/unit/test_output_views.py
  tests/cli/test_cli_skills_tree.py -q`; FAIL → реализовать общее дерево и
  адаптировать `skills tree`, включая `--within`, `--query`, `--limit` → PASS.
- [ ] Тест: `--view graph` и `--view typo` у `skills tree` → `ok: true`,
  фактический `tree`, `view.fallback` с обоими значениями, все данные доступны;
  проверить ту же диагностику во всех трёх форматах.

### З5. Навигация по документам и пагинация

**Файлы:** изменить `src/todoc/cli.py`, `src/todoc/application/search.py`,
`src/todoc/output/views.py`; создать `tests/cli/test_unified_docs.py`.

**Consumes:** З1–З4. **Produces:** общие виды и проекции для `docs tree`,
`search`, `suggest`, `links`; честная пагинация и применение глубины.

- [ ] Тест: в дереве корень, папка и вложенный документ; `--depth 1` не
  содержит документ глубины 2, `--within` не включает соседний одноимённый
  префикс; 51+ документов → корректный `truncated` и следующий курсор. Для
  `skills tree --within coding/git` путь разрешается относительно vault;
  для `docs tree --within coding/git` — относительно DATA_ROOT. Проверить
  `..`, абсолютный путь, symlink наружу и старый `--max-depth` отдельно.
- [ ] Тест: `--query`, `--within`, `--type`, `--tag` вместе = пересечение;
  соответствующая запись после первого лимита найдена; возвращённый cursor
  проходит все элементы без дубликатов; изменённые фильтры/снимок → ошибка.
  Отдельно проверить `--limit 0`, пустую последнюю страницу, одинаковые ключи,
  изменение folder config/пустого каталога и повтор контекста родителей на странице.
- [ ] Запустить `.venv/bin/python -m pytest tests/cli/test_unified_docs.py -q`;
  FAIL → заменить плоские массивы `docs tree` общим рендером, применить
  фильтры до среза и подключить реестр → PASS. Проверить пути за пределы root.

### З6. Граф и дерево связей

**Файлы:** изменить `src/todoc/application/query.py`,
`src/todoc/output/views.py`, `src/todoc/cli.py`; создать
`tests/cli/test_unified_relations.py`.

**Consumes:** типизированные `relations` и `mentions`; интерфейс З4.
**Produces:** направленный граф и дерево обхода, без потери циклов и рёбер.

- [ ] Тест на A→B, B→A и A→B другого типа: `graph` сохраняет все три
  типизированных ребра и направление; дерево помечает цикл и не зацикливается.
- [ ] Тест: фильтр типа, глубина 0/1/2 и лимит рёбер дают правильные счётчики;
  JSON и Mermaid представляют одни узлы/рёбра, идентификаторы и подписи с
  кавычками/переносами безопасно экранированы.
- [ ] Запустить `.venv/bin/python -m pytest tests/cli/test_unified_relations.py -q`;
  FAIL → отделить обработку уже посещённых узлов от сохранения рёбер, подключить
  единый рендер и сообщения → PASS. Проверить mention и self-loop, параллельные
  одинаковые рёбра, пагинацию и достижимость каждой страницы; не выдумывать ID.
  До подключения зафиксировать identity/происхождение рёбер и порядок с дубликатами.

### З7. Остальные выборки и представления

**Файлы:** изменить `src/todoc/cli.py`, `src/todoc/output/views.py`;
создать `tests/cli/test_unified_lists.py`.

**Consumes:** реестр З1 и render/project З4. **Produces:** единообразные
поддерживаемые поля и фильтры для `records list/query`, `types list`, `state list`,
`change list`, `log`, `timeline`, `blame`; собственные формы остальных ответов.

- [ ] Параметризованный тест для каждой перечисленной команды: вызов по
  умолчанию возвращает все предусмотренные поля, `--fields` и
  `--exclude-fields` меняют только проекцию, а диагностики и cursor остаются.
- [ ] Тест: неподдерживаемый `--within`, `--tag` или `--relation` возвращает
  ошибку и подсказку; `--view graph` при отсутствии рёбер даёт корректный
  fallback, не пустой граф вместо данных.
- [ ] Выполнить `.venv/bin/python -m pytest tests/cli/test_unified_lists.py -q`;
  FAIL → подключить общие адаптеры, не меняя смысла команд → PASS. Проверить
  каждую строку матрицы З1 и отдельно документировать неприменимые фильтры.
- [ ] Перенести также singleton и action-команды, не ограничиваясь указанными
  выборками: common envelope, discovery, опции, безопасность и форматы по матрице.
  Нет команды с прежним специальным парсером/сырой веткой под общим флагом.

### З8. Совместимость и миграция на один контракт

**Файлы:** `src/todoc/cli.py`, `src/todoc/output/`, существующие тесты и
потребители, `tests/cli/test_output_migration.py`, `README.md`, `SKILL.md`,
справочники, встроенные и демо-промпты, benchmark и критерии.

**Consumes:** единый результат З2–З7, baseline и матрица З1. **Produces:**
один новый контракт по умолчанию, однозначные синтаксические алиасы и руководство
миграции с перечнем несовместимостей; переключателя старого JSON нет.

- [ ] Тест: примеры v1 из З1 показывают ожидаемые различия и миграционные инструкции;
  новые вызовы без переключателя возвращают единую `schema_version: 2`. Старые
  безопасные и однозначные имена принимаются лишь как алиасы в новый результат;
  неизбежный breaking change JSON/exit/действий перечислен. Старые дефекты и
  скрытые записи не воспроизводятся.
- [ ] Тест: `records read --record-view summary`, старый `--view summary` и
  коллизии имён по правилам раздела 4; исходные промпты и обновлённые промпты
  проверяются соответственно на результат алиаса и на новый синтаксис.
- [ ] Тест: `table`, `--max-depth`, повтор `--root`, глобальные и локальные опции,
  обработка конфликтов и все три формата. Убрать raw-ветки, обновить вызовы pipe.
- [ ] Запустить `.venv/bin/python -m pytest tests/cli/test_output_migration.py -q`;
  FAIL → реализовать миграцию без v1-режима → PASS. Протестировать все известные
  потребители из матрицы. Явно обновить K3 под согласованный exit 0 при недостающем
  входе; отдельно сохранить exit 2 для ошибочного указанного значения. Все прочие
  критерии K1–K30 не менять ради прохождения без указания причины и согласования.

### З9. Итоговый сценарий, размеры и выпускной гейт

**Файлы:** создать `tests/cli/test_unified_e2e.py`; изменить справочники и
`SKILL.md` из раздела 4; при необходимости скорректировать тесты З1–З8.

**Consumes:** все предыдущие задачи. **Produces:** проверенный общий контракт и
отчёт сравнения на исходных fixtures.

- [ ] E2E в `tmp_path`: создать fixture датасета; вызвать `skills tree` без
  опций вывода; повторить с `flat` и полями, `tree` с глубиной, `graph` у
  relations, Markdown и ошибочным видом. Проверить `ok`, подсказки, реальные
  пути, фильтры, отсутствие повторного запроса и побочных записей при чтении.
- [ ] Выполнить `.venv/bin/python -m pytest tests/cli/test_unified_e2e.py -q`;
  ожидается PASS. Сравнить размеры и, если доступен согласованный токенизатор,
  токены с baseline З1; записать метод и значения без заявлений о выигрыше,
  если он не измерен. Все поля по умолчанию не убирать ради метрики. Измерить
  25/100/500+ элементов, байты и токены одним указанным токенизатором; отметить
  fixture и hot/cold p50/p95. Не считать разницу bytes доказательством токенов.
- [ ] LLM usability gate: на заранее подготовленных сценариях поиск/навигация,
  связи, чтение и preview с минимумом вводной документации измерить число разных
  правил/флагов, успешность, вызовы, ошибки, токены подсказок и общее число токенов;
  сравнить старый и новый CLI на одинаковых задачах, фиксировать модель, промпт,
  повторения и отклонения. При недоступности LLM — воспроизводимые scripted
  conformance-пробы и честная пометка, что поведение LLM не проверено.
- [ ] Выполнить полный набор проверок раздела 6; записать точные результаты в
  раздел 8. Для E2E dataset использовать `tmp_path`, не модифицировать `demo`
  дополнительными командами записи.

## 6. Definition of Done

- [ ] Реализован и проверен З0-S: рабочие JSON/JSONL адаптеры и независимый
  fake проходят общие storage-контракты, CLI/use cases не обходят seam (§0.10);
  никаких заявлений о готовности SQLite без отдельной реализации и тестов.
- [ ] Выполнены архитектурные проверки §0.9.2–§0.9.5; конфликт времени
  и будущего logging не скрыт, зафиксированы согласованные решения и незавершённые
  возможности. Массовые миграции чужих планов без отдельного поручения не запускались.
- [ ] Каждое требование идеи сопоставлено задаче З0-S или З1–З9; матрица охватывает все
  листовые команды, fallback и discovery проверены во всех форматах.
- [ ] В виртуальном окружении установлены зависимости `[dev]`; команды:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m coverage run --branch --source=src/todoc -m pytest -q
.venv/bin/python -m coverage report --fail-under=100
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m todoc validate --root demo --all
PYTHONDONTWRITEBYTECODE=1 python3 tools/linkcheck.py
git diff --check
```

  Ожидание: все тесты проходят; coverage ≥ 100%; validate — 0 диагностик;
  linkcheck — `broken 0`; `git diff --check` не выводит ошибок.
- [ ] На всех листах, группах и корне действуют общие грамматика, единый конверт,
  форматы и семантика по матрице; единый контракт по умолчанию. Старые потребители
  обновлены или документированы как несовместимые; проверены только однозначные
  синтаксические алиасы. Отдельного режима/параллельной v1-схемы нет.
- [ ] Подтверждены отсутствие записи в read/preview, политика observe, честная
  согласованность, конфиг-fingerprint и полный проход страниц; K3 адаптирован к
  согласованному discovery, K1/K2/K4–K30 проверены по исходным критериям либо их изменения предварительно согласованы; K19/K30 разобраны по §0.8.

- [ ] Проверка linkcheck включает анализ строки `broken 0`, а не только код
  возврата: `tools/linkcheck.py` в текущем коде возвращает 0 даже при битых ссылках.
- [ ] Ревью изменений и подтверждение пользователя получены до коммита или
  последующих изменений состояния. Выполнение плана не является таким согласием.

- [ ] Проверить отсутствие неразрешённых конфликт-маркеров в интегрированных
  текстовых файлах отдельно от validate/linkcheck, ревьюить ложные совпадения;
  проверить исходные и добавленные master-тесты и пользователей по матрице.
- [ ] Перед benchmark согласовать любые изменения критериев кроме K3 и избежать
  перезаписи пользовательских результатов и конфликтующих фиксированных `/tmp`
  путей; измерить на финальном состоянии, записать версии, среду и результаты.
- [ ] Изоляция: `tmp_path` для датасетов и целей, отдельные HOME/XDG/TODOC_ROOT,
  coverage-файл и результаты benchmark; проверить отсутствие изменений реального
  demo, history, git и внешних файлов на read/preview. Тесты init/rebuild и
  фикстуры master адаптировать к явному apply, не ослабляя проверки безопасности.

## 7. Риски и митигации

| Риск | Вероятность / влияние | Митигация | Владелец |
|---|---|---|---|
| Поломка внешнего клиента из-за структуры `data` | высокая / высокая | Матрица потребителей, однозначные алиасы, fixtures и руководство миграции; единственный новый контракт З1/З8 | исполнитель |
| Тихая потеря данных из-за лимита, глубины или курсора | высокая / высокая | Фильтры до среза, стабильные счётчики, тесты страниц и изменившегося снимка З3/З5/З6 | исполнитель |
| Неточные связи или незавершённый обход графа | средняя / высокая | Сохранять все рёбра, отдельно отслеживать посещённые узлы, тесты циклов и нескольких типов З6 | исполнитель |
| Побочные записи при чтении или пустом вызове | высокая / высокая | In-memory индекс, побайтовые снимки, тесты destructive-команд З0-S/З2/З3 | исполнитель |
| Частичная запись файла и истории или GC, потеря ревизий | высокая / высокая | Явный результат стадий, fake/failure-injection, безопасный recovery без обещания cross-store атомарности (§0.10) | исполнитель |
| Утечка JSON-layout или связанного источника blob в CLI | высокая / высокая | Независимые порты, две реализации и seam-gate, matrix комбинаций (§0.10) | исполнитель |
| Самоописание само расходует контекст | средняя / средняя | Компактная подсказка, полный список по запросу, измерения З1/З9 | исполнитель |
| Флаг `--view` конфликтует со старой проекцией | высокая / средняя | `--record-view`, детерминированный алиас и тест коллизии З8 | исполнитель |

## 8. Прогресс и отклонения

- Реализация начата по прямому поручению пользователя; З0-S и З1–З9 в целом ещё не завершены.
- Аудит границ storage выполнен на master `c9256c2` и текущем дереве; §0.10–0.11
  добавлены в план, но сами порты, адаптеры и будущие SQLite-драйверы не реализованы.
  Целевой storage-прогон: 200 passed на текущем дереве до интеграции; clean master
  и совместимость двух реальных драйверов этим прогоном не проверены.
- Для аудита выполнены изолированные проверки с подменённым in-memory payload:
  `records list` пропускает совпадение за лимитом и сообщает `truncated=false`;
  `docs tree --max-depth 1` возвращает глубокий документ; `graph_neighbors`
  из трёх рёбер между A и B возвращает одно. Это воспроизведения текущих
  дефектов, не тестирование новой реализации и не прогон полного pytest.
- Уточнение пользователя 26.11.2026: цель — именно масштабная переделка ради
  единообразия всего CLI для LLM; предложение оставить v1 default/v2 opt-in снято.
  В плане — один новый контракт без постоянного параллельного интерфейса.
- Повторный аудит: инвентаризация 60 листьев/38 с обязательными входами на текущем
  checkout, parse-cache write при cold miss воспроизведён с перехватом записи;
  определены риски истории, курсора, консистентности, графов и raw-вывода. Метрики
  `skills tree`: 25 видимых скилов, JSON pretty 11 469 и compact 8 786 байт,
  текущий текст table 4 986 байт; полнота форматов различается, токены не измерены.
  Полный pytest и benchmark при аудите не запускались.
- Ранее пользователь разрешал исполнение; актуальное поручение ограничено
  аудитом и правкой плана. Для возобновления нужен новый прямой запрос; merge,
  коммит, push и PR также требуют отдельных разрешений.
- Реализация 26.11.2026, незавершённая: создан target-реестр всех листов Click
  и тест покрытия имён; общая схема, поля, discovery и подключение команд ещё не готовы.
- Исправлены фильтры `records list` до limit; добавлены безопасный preview по
  умолчанию для `history gc`, наследование `--output`, containment vault и mute
  предка. Изменение `history gc`: фактическое удаление теперь требует `--apply`.
- `check`, `scan`, `validate` не пишут parse-cache; для части read/preview создан
  `read_index` без публикации, кэша и истории. Он перечитывает корпус дважды и
  отказывает при обнаруженном изменении; это не атомарный snapshot и не покрывает
  все остальные read/preview. `log`, `blame` и `timeline` больше не наблюдают внешние правки; наблюдение выполняется при `index rebuild --apply`. З3 не завершена.
- Следующие шаги: завершить З1 (матрица возможностей и schema), единый конверт
  и безопасный discovery З2, затем выполнить остальные задачи плана; не считать
  частичные изменения завершением единого интерфейса.
- Дополнительно: `skills tree` частично переведён на v2 с видами `tree`/`flat`,
  проекциями, cursor и fallback; discovery корня, групп и пустых листьев частично
  реализован. `init`, `index rebuild`, `history adopt` требуют `--apply` для записи.
  Это не единый контракт: большинство остальных ответов остаётся v1, многие
  команды записи не переведены на безопасный preview, З1–З9 не завершены.
- Полный pytest на промежуточном состоянии прошёл с пропусками; branch coverage
  100%, гейт пройден. Схема, общий dispatcher, граф, потребители и
  выпускные проверки ещё требуют реализации и повторного тестирования.
- Следующий частичный шаг З5: `docs tree` переведён на v2 tree/flat, поля,
  фильтры, глубину и cursor. Папки и документы — отдельные результаты;
  пустые папки сохраняются, контекстные предки повторяются без учёта в returned.
  Cursor учитывает fingerprint корпуса и конфигов. Обновлены тесты и справочник.
  Конфиги для `docs tree` загружаются между двумя проверочными сканами; ошибки
  доступа и обнаруженное изменение дают отказ; атомарный snapshot не обещается.
  `docs search`, `suggest`, `links` и остальные семейства ещё не унифицированы.
- Частичный шаг З6: `relations graph/tree` переведены на v2 с видами graph, tree
  и flat, проекциями и курсорами. Обход BFS и сохранение рёбер разделены:
  результат — индуцированный направленный мультиграф, включая петли и дубликаты;
  tree повторяет контекстные рёбра и помечает повторные посещения. Источники
  записей снабжены реальными path/pointer и исходным data, упоминания — строкой.
  Markdown graph выводит Mermaid и данные; тесты и справочник обновлены.
  З6 целиком не закрыта: требуется дополнительный аудит потребителей, а все
  прочие задачи плана и общий единый контракт по-прежнему не завершены.
- Для графа исправлены встроенный генератор типовых промптов и 36 промптов demo:
  вместо ошибочного `relations graph --id` используется `--from`. CLI не умеет
  править файлы типовых промптов, поэтому они изменены напрямую и перечитаны.
  При обратном чтении обнаружена коллизия `types prompt` для `guide`, `note`,
  `plan`: одинаковое имя doc_type и entity_type выбирает doc_type без выбора вида;
  9 промптов entity_type пришлось перепроверить непосредственно по файлам.
  Коллизия устранена: `types show/prompt --kind` выбирает точный вид, при неоднозначном ID без вида — `types.ambiguous`; все 18 промптов этих пар перечитаны через CLI. Потребители `records read` мигрированы ниже.
- Частично З3/З8: `docs new` по умолчанию и с `--preview` возвращает v2-план
  с полным содержимым без записи, `--apply` создаёт документ, конфликт флагов и
  несколько roots отклоняются. Действие preview содержит `--if-plan-hash`,
  при изменении шаблона или даты план повторно проверяется и создание отклоняется;
  прямой `--apply` без hash пересчитывает план. Create-only публикация через
  hard link атомарно отказывает при занятой цели (включая гонку и висячий
  symlink); неподдерживаемые файловые системы дают отказ без unsafe fallback.
  Замена родительских каталогов и CAS существующих файлов остаются рисками.
  Генератор и 29 create-промптов обновлены, исходящие действия и форматы проверены.
- `records read` частично переведён на v2: именованная проекция — `--record-view`,
  `--view summary/full` распознаётся как устаревший alias с info, форма `graph`
  никогда не перехватывается одноимённой проекцией; несуществующий view даёт
  fallback с диагностикой, недоступный summary возвращает full с диагностикой.
  Мигрированы генератор и 36 промптов, справочники и тесты. Общий контракт и
  полный аудит потребителей по-прежнему не завершены.
- Полный pytest прошёл с пропусками, branch coverage 100%; план З1–З9 не завершён.
- Частично З7: `types list` и `state list` используют общий flat-адаптер:
  реальные `{kind,type_id}` и `{key,value}`, фильтры до ограничения, проекции
  без потери identity, курсор с проверкой selection и info-fallback в JSON,
  Markdown и table. Несколько roots отклоняются, поля доступны без root.
  Общий адаптер пока не подключён ко всем спискам и не заменяет З7 целиком.
- Команды `next_actions` в текстовых форматах экранируются с сохранением argv.
  Тесты на гонку, висячую ссылку, неподдерживаемую ФС, фильтры и cursor добавлены;
  полный pytest прошёл с пропусками, branch coverage 100%.
  Аудит новых записей, конкурентная безопасность и общий dispatcher остаются открыты.
  Виды и миграция большинства команд по-прежнему не завершены.
- Дополнительно частично З2/З7/З8: `records list/query` используют flat v2 с проекциями,
  фильтрами до страницы и cursor; некорректный QuerySpec явно отклоняется.
  Неполный вызов с частично указанными аргументами даёт discovery без записи;
  K3 benchmark обновлён: недостающий вход → exit 0, неверное значение → exit 2.
  `types show/prompt`, `state get/set/unset` используют v2; state-мутаторы
  требуют `--apply`, preview не пишет XDG и предлагает проверку `--if-hash`.
  Проверка стейта не атомарный CAS. Раннее прекращение чтения файла при сборке
  индекса теперь не выдаётся за полный результат; ABA и другие гонки остаются.
  Ошибки через main возвращают v2, но большинство успешных команд остаётся v1;
  план целиком не завершён, schema/dispatcher и полный benchmark ещё впереди.
- Частично З2: `change open` теперь по умолчанию показывает v2 preview и требует
  `--apply`; `--if-plan-hash` проверяет план, шаблоны и базовую линию перед записью.
  Это не атомарный CAS; создание каталога, файлов и истории не транзакционно,
  при ошибке возможен частичный результат. Гонки родительских каталогов остаются.
  Запись и шаблоны создаются create-only; существующие шаблоны сохраняются.
- Частично З2: `skills import` выдаёт v2 preview с manifest размеров, hash и
  прав файлов; `--apply` создаёт новые каталоги без перезаписи, `--dry-run` —
  псевдоним preview, `--adopt` только читает. `--if-plan-hash` привязан к
  снимку файлов и плану; next action не включает `--apply`. Путь раздела
  ограничен vault, симлинки и специальные файлы в копируемых скилах запрещены.
  Импорт многофайловый, не транзакционный, снимок не атомарен, при ошибках
  возможен частичный результат; гонки родительских каталогов не устранены.
  Для безопасного чтения нужны O_NOFOLLOW и fchmod; файлы снимка хранятся в памяти.
- Частично З2: `skills attach` выдаёт v2 preview внешней цели и требует `--apply`;
  `--force` сам по себе не пишет. План показывает hash и права создаваемых или
  заменяемых файлов; `--if-plan-hash` проверяет их перед записью, подсказка не
  включает `--apply`. Файлы создаются create-only или заменяются поштучно;
  лишние существующие файлы сохраняются. Дескрипторы каталогов препятствуют
  перенаправлению через замену симлинка после открытия целевой директории, но
  проверка hash не CAS, операции не транзакционны, возможны частичные результаты
  и гонки до открытия родительского каталога/при перемещении директорий.
  Для установки нужны dir_fd, O_NOFOLLOW и hard links; на неподдерживаемой
  платформе или ФС запись отклоняется. DATA_ROOT с пробелами shell-экранирован.
- Частично З2/З7/З8: `types guide` выдаёт единый v2-конверт для JSON/table/
  markdown, `--format` задаёт формат содержимого. `--out` без `--apply` —
  preview с хешами и содержимым, подсказка не включает `--apply`. Создание
  защищено атомарной create-only публикацией, обновление — не CAS; гонки
  родительских каталогов остаются. Потребитель K5 benchmark мигрирован.
  `tag` теперь preview по умолчанию и v2: план включает ревизию и hash refs;
  `--apply` пишет, `--if-plan-hash` проверяется до записи, но это не CAS.
  Битые/нечитаемые refs и несуществующие ревизии отклоняются вместо перезаписи.
  Другие обращения к истории и гонки parent dirs ещё нуждаются в аудите.
- Частично З2: `history export` показывает v2-план со снимком и не пишет без
  `--apply`. `--if-plan-hash` привязан к источнику, цели и метаданным файлов.
  Папка бэкапа создаётся create-only, пересечение с историей и симлинки
  источника запрещены. Несколько файлов не транзакционны, снимок не атомарен,
  гонки до открытия родительского каталога и перемещение каталогов остаются;
  на неподдерживаемой ФС публикация отклоняется. Содержимое снимка в памяти.
- Частично З2/З7: `docs flow render` использует v2 для чтения и действий;
  `--write` без `--apply` показывает полное содержимое и hash плана; подсказка
  не содержит `--apply`. `--section` и `--write` несовместимы; ручные файлы и
  симлинки не перезаписываются. `--if-plan-hash` не является атомарным CAS;
  возможны гонки родителей и сбой индекса/истории после публикации файла.
- Исправлены подсказки `docs new`, `change open`, `state set/unset`: argv
  предварительной проверки не содержит `--apply`; его нужно добавить явно.
  Генератор и 29 create-промптов, документы и тесты мигрированы. Полный аудит
  `next_actions` остальных команд и единый контракт остаются незавершёнными.
- Частично З2: `change archive` выдаёт v2-план без записи; `--apply`
  архивирует после проверки `--if-plan-hash` по дереву, журналу и refs.
  Симлинки и занятая цель отклоняются. Проверка не CAS; возможны гонки путей
  и неполные изменения при сбое статуса, переноса, истории или метки.
  Снимок не атомарен, содержимое файлов читается в память; timestamp при apply.
- Безопасность до дальнейшей миграции: `docs edit`, `records create` и `fix`
  отклоняют совместные `--preview --apply` до чтения и записи;
  их v2-реализация и остающиеся ограничения описаны ниже.
- Частично З2: `records create` показывает v2-план с полным содержимым,
  проверяет `--if-plan-hash`, отклоняет выход за DATA_ROOT и публикует новый
  файл create-only. Сравнение плана не CAS, гонки родителей остаются; сбой
  истории или индекса после создания может оставить частичный результат.
- Частично З2: `docs edit` возвращает v2 и предварительно вычисляет точное
  содержимое, валидацию патча, дату updated и хеши; `--if-plan-hash` связывает
  патч и состояние документа. Сравнение не CAS, возможны гонки путей и
  частичная запись при сбое истории или индекса после публикации документа.
- Частично З2: `fix` показывает v2-план с точным содержимым и проверкой
  `--if-plan-hash`. Замена ограничена evidence на строке диагностики;
  неоднозначное совпадение отклоняется (BUG-011). Проверка не атомарный CAS,
  возможны гонки и сбои истории/индекса после публикации.
- Частично З2/З3: `records undo-relation` использует v2-план с итоговым JSON,
  хешами и `--if-plan-hash`; при недоступном снимке и повреждённом журнале
  отказывает вместо выбора более старой версии (BUG-012). `before: null`
  прекращает поиск: creation, baseline или backend без embedded-снимка не
  дают надёжного предшественника. CAS и атомарный снимок не гарантируются;
  возможны гонки путей и ошибки истории/индекса после публикации.
- Частично З2/З3: `history gc` до удаления строго проверяет журнал и ссылки
  на объекты, отклоняет симлинки и специальные файлы хранилища (BUG-013).
  Гонки при замене каталогов остаются; v2, hash-план и полный аудит GC ещё
  не выполнены. Явный лимит может удалять снимки с активными ссылками.
- Частично З7: `status` теперь возвращает v2-отчёт с фактическими root и dataset,
  честной отметкой о возможном устаревании опубликованного индекса и безопасным
  следующим действием. Снимок не пересобирается автоматически.
- Частично З3/З7/З8: `change list` выдаёт flat v2, проекции, фильтрацию
  до страницы и cursor по полным прочитанным записям и их путям; `baseline`
  не раскрывается. Ошибки чтения и отсутствующий ID отклоняются (BUG-014),
  симлинки в сканируемых путях запрещены (BUG-015). Дополнительные поля
  доступны только если встречаются в источнике. Сканирование не атомарно,
  гонки замены путей остаются; отсутствие файла в папке считается нормой.
  Дубли record_id команда не различает по пути в выводе; нужен отдельный аудит.
- Частично З7/З8: `records aggregate` показывает flat v2-группы с единицами
  и происхождением каждой группы, проекциями, страницей и cursor по данным и
  описателю метрики. `completeness` относится к обработке входов, не страницы;
  список ID внутри группы не ограничен лимитом. Multi-root отклоняется.
  Невалидные и неконечные числа и переполнение суммы приводят к
  структурированной ошибке вместо исключения или некорректного JSON (BUG-016).
- Частично З2/З7: `check-config` возвращает v2-отчёты по всем roots,
  включая их фактические пути в результатах и диагностиках, и безопасную
  исполнимую подсказку `types show` для первого затронутого типа (BUG-017).
- Частично З3/З7: `scan` возвращает v2 с root и диагностиками, без публикации
  индекса, с безопасной подсказкой `validate --all`. Статус scan отражает
  завершение обхода, а не успешность валидации; объём диагностик не ограничен.
  Полная проверка надёжности обхода, включая ошибки scanner, остаётся в З3.

- Частично З3, BUG-018: `scan`, `check`, `validate` используют строгий обход без хеш-кэша; ошибки доступа к каталогам, stat и хеширования прерывают вывод. Для нескольких roots частичный успех не выдаётся. Позднее нечитаемое содержимое даёт ошибку. Есть CLI/subprocess и read-only регрессии. Согласованность при конкурентной записи и остальные read/preview остаются открытыми; З3 не закрыта.

- Частично З2/З7/З8: `check` и `validate` используют v2 и указывают root в каждой диагностике, без дублирования списка; обновлены потребители benchmark, тесты и справочники. Подсказки больше не предлагают непроверенный `fix` без root (см. BUG-017); статус warning в `check --strict` исправлен (BUG-019). Диагностики по-прежнему не ограничены и не пагинируются; единого контракта на всех командах ещё нет.

- Частично З3/З5/З8: `docs search` перешёл на v2, flat-проекции и cursor, связанный со снимком и параметрами; `--within`, фильтры и бюджет фрагментов проверяются до вывода. Поздняя ошибка чтения и заметное изменение во время поиска дают отказ (BUG-020); байтовый бюджет первого фрагмента ограничен (BUG-021). K1–K5 и K22–K24 проверены на изолированной копии demo. Снимок не атомарен, полный З5 и benchmark K1–K30 остаются открыты. Для дублирующегося id подсказка чтения отключена (BUG-022); ручной `docs read` по такому id возвращает ошибку.
  Изолированная копия demo, 7 последовательных запусков поиска `план --limit 3`: 1637–1825 мс, медиана 1677 мс (только эта среда; не полный p50/p95-gate и не сопоставленный baseline).

- Частично З3/З7/З8: `docs read` использует v2, один root, строгий обход и проверку хеша повторного чтения (BUG-023); ошибки разбора JSON/CSV больше не скрываются (BUG-024). Бюджет ограничивает UTF-8 байты текста, а не весь конверт; JSON/CSV этот флаг отклоняют. Невалидные селекторы отклоняются. Обновлены тесты и потребители K17–K21. Снимок и проверка пути не атомарны; ABA и гонки остаются. Полный план и K1–K30 не закрыты. Изолированная копия demo: K17–K21 по тогдашней реализации benchmark pass (K19: 500 UTF-8 байт текста, не полного ответа; исходное требование K19 не доказано, см. §0.8); это не полный K1–K30. Полный прогон тестов и branch coverage на этом этапе: 1602 passed, 57 skipped, 100%.

- Частично З3/З5/З8: `docs suggest` и `docs links` выдают flat v2 с проекциями, счётчиками и cursor по проверенному снимку. Suggest не скрывает недоступные/битые конфиги (BUG-026); исправлен тип severity некоторых диагностик (BUG-027). Links не скрывает ошибки чтения (BUG-025), учитывает record_id (BUG-028), отклоняет невалидные JSON и неподдерживаемые Markdown/JSON. Cursor и чтение не атомарны, ABA и гонки остаются; остальные задачи плана не закрыты. Полный прогон: 1621 passed, 57 skipped, branch coverage 100%; demo validate без диагностик, linkcheck broken 0 (806 ссылок). Повторный итоговый прогон после дополнительных проверок: 1622 passed, 57 skipped, branch coverage 100%.

- Частично З3/З7/З8: `log` использует v2, строгий журнал, проверки пути и актуальных границ раздела, проекции, фильтрацию до limit и cursor по журналу/refs/файлу (BUG-029, BUG-030). Повреждённая последняя строка теперь ошибка; наблюдение внешних изменений не выполняется. Сравнение снимков не атомарно, ABA и гонки путей остаются; другие команды истории не мигрированы.

- Частично З3/З7/З8: `skills read` перешёл на v2 для всех форматов без сырого Markdown, проверяет область vault, диапазоны и положительный UTF-8 бюджет, по умолчанию 4000 байт. Метаданные и текст берутся из одних байтов, повторное чтение обнаруживает заметное изменение (BUG-031, BUG-032); при усечении предлагается исполнимое дочитывание. Проверка пути не атомарна, ABA остаётся.

- Частично З3/З7/З8: `index status` теперь в v2, явно отличает отсутствие метаданных от повреждения и не заявляет свежесть. `status` проверяет опубликованные шарды, их типы и метаданные и повторно считывает снимок; ошибки и заметные изменения не маскируются отсутствующим индексом (BUG-033). Снимок не атомарен, повторное чтение не защищает от ABA.

- Частично З3/З7/З8: `index rebuild` переведён на v2, preview с `plan_hash`, строгий обход без кэша хешей и сверку published payload перед reuse. BUG-034: ранее неполный обход или hash-cache могли привести к неполному/устаревшему индексу. Проверки и публикация не атомарны; ABA и ошибка истории после публикации остаются. Это не завершает З3/З7/З8.

- Частично З3/З7/З8: `doctor` возвращает v2, отклоняет неизвестные проверки и честно сообщает, что наличие метаданных не доказывает свежести индекса (BUG-035). `--fix` не выполняет ремонт. Это не завершает задачи.

- Частично З3/З7/З8: `history adopt` v2, один root, preview/plan_hash и повторная проверка хешей всех файлов, журнала и refs; больше не публикует индекс (BUG-038). Проверки не атомарны, журнал и refs могут разойтись после частичной ошибки. Это не завершает задачи.

- Промежуточный K1–K30 в изолированной копии без конкурентов: 28.5/30, K14 ошибочно провален из-за старого пути `data.plan` (BUG-036), K27 partial: search 4020 мс, K30 partial и измеряет неверные прокси (BUG-037). После исправления K14 отдельный K14–K16 pass; после повторного использования разбора и строгой контрольной fingerprint-проверки отдельный K27 pass (медиана search 1547 мс на том же корпусе). K30 после исправления прокси отдельно pass 8/8 (проверка офлайна ограничена одним вызовом и Python socket API; BUG-037). Это не полный повторный gate и не закрывает З9: usability и оставшиеся команды ещё не завершены; ABA остаётся.

- Повторный полный K1–K30 после исправлений: 30/30, без конкурентов, отдельная копия demo с искусственными дефектами; результаты `bench/results/unified-cli-benchmark.json` и `.md`. Поиск 1487 мс (медиана 3 запусков), K28 1680 passed, K29 100%. Метка времени в артефакте — часы контейнера. Это проверка существующего benchmark, а не завершение плана: его пробы не исчерпывают всех команд и требований; K30 offline ограничен одним вызовом и Python socket API, usability gate и остальная матрица не доказаны.
