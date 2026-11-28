---
id: doc:plan/unified-cli-output-implementation.md
title: "Единый самодокументируемый CLI: план реализации"
doc_type: plan
lang: ru
status: active
created: 2026-11-26
updated: 2026-11-28
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

> **Точка входа.** §0.12 задаёт исходный снимок и первый проверяемый результат.
> §4 задаёт контракт, §5 — задачи, §6 — условия выпуска. Материалы прежнего
> переноса в §0.2–§0.8 и журнал §8 служат источниками регрессий.

## 0. Подготовка: правила, сохранность и база master

Для реализации действуют инструкции выбранного checkout и маршрут §0.11–§0.12.
Исторические указания на ветки и перенос описывают прежние попытки.

### 0.1. Временные правила на время реализации

- [ ] На старте прочитать инструкции выбранной базы. Для датасета применять
  предусмотренный ими workflow, для разработки использовать временные фикстуры.
- [ ] Дефекты эксплуатации фиксировать с дедупликацией. Регрессию разработки
  подтверждать целевым тестом, результаты сохранять в журнале этапа.
- [ ] Проверять изменённые контракты точечными тестами. На завершении этапа
  записывать SHA, команды, результат и skips. На выпуске применить §6.

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

- **K19, решение пользователя от 2026-11-28.** `--budget N` для
  текстового содержимого задаётся в символах Unicode, как `len(text)`.
  Считаются фактически возвращённые символы полезного содержимого, включая
  переводы строк. Заголовки конверта, координаты, хеши, диагностика, guidance,
  JSON-экранирование и форматирование в бюджет не входят. Для нескольких
  текстовых фрагментов считать сумму их длин. Альтернативные представления
  одного фрагмента считать один раз и строить из одного ограниченного окна.
  Размер полного stdout в байтах и число токенов измерять отдельно.
- До приёмки З5/З8/З9 синхронизировать `bench/criteria.md`, проверку K19,
  help, справочники и клиентов применимых `--budget`. Тест должен
  различать символы и байты на кириллице и emoji. Проверить длинную строку
  без переносов, секцию, диапазон, точную границу и явный признак усечения.
  Пределы массива записей, CSV-строк и графа задаются их селекторами.
  Для нетекстовой формы без определённой семантики `--budget` вернуть
  диагностированный отказ. Порог K19 — 500 символов полезного текста.
- **K30** сохраняет восемь исходных требований. З9 заменяет прокси
  доказательствами для каждого пункта. Отсутствие сетевых вызовов проверять
  на репрезентативных командах в изолированной среде; недоступная изоляция
  означает `not_run`. Наличие индекса не доказывает правила Git, обязательна
  проверка фактического игнорирования производных путей. Если исходный
  критерий потребуется изменить, вынести конкретное решение пользователю.
- K14/K16 мигрировать на v2 с прежними смыслом и порогами. Для K29 ветви
  и инструкции должны быть покрыты на 100%. Pytest skips и причины
  пропуска указываются отдельно.
- В ветке bigplan `bench/run_benchmark.py` использует временную директорию
  на прогон и принимает `--results-dir`. Указывать отдельный каталог для
  отчёта, чтобы сохранить прежние артефакты. Сверять запуск и семантику
  критериев с выбранным коммитом.
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
| `demo/ideas/unified-tags-and-tag-graph.md` — captured | З1/З5/З7: реализовать `--tag-in`/`--tag-all` для документов и записей с известным носителем тегов; см. §4. Теги документа, `labels` записи, теги папок и метки истории сохраняют происхождение и отдельные области. | Группа `tags`, узлы `tag:<name>`, рёбра `has_tag`, наследование папочных тегов, миграция `labels` и поддержка фильтров в `skills tree`/`context` остаются задачами идеи. Пагинация и лимиты обязательны. |
| `demo/ideas/agent-state.md` — done | З2/З7: сохранять существующее dataset-scoped XDG-состояние и ключи, атомарность текущих writes где доказана, изоляцию root, preview/apply; state не смешивать с history/log. | Фазы автоматического project scope, новые ключи и project commands отдельно за gate; не подставлять state молча в фильтрацию. |
| `demo/ideas/documentation-system.md` — done в объёме типового профиля | З1/З8: сохранить типы/схемы/стартовые промпты и навыки, bounded search/read, provenance, offline и review-first; настоящий интерфейс записи и подсказки обновить по матрице. | Jira/git интеграции, синтез и дальнейшие фазы идеи не объявлять выполненными и не создавать. |
| `demo/ideas/entity-catalog.md` — done | З5/З6/З7: сохранять term/flow/правила, `mentions` vs явные relations, реальные источники/направления/параллельные рёбра, `undo-relation`, семантику flow render/walk и защиты derived витрин. | Не добавлять в граф виртуальные теги из другой идеи и не терять доступ к старым источникам при перестройке вида. |
| `demo/ideas/folder-config.md` — done | З3–З5: `.config.json` опционален, не документ, настраивает title/description/aliases/order/tags и search boost; учесть muted paths и конфиг в fingerprint, строгие ошибки и отсутствие скрытой записи. | BM25/стемминг Phase B за отдельным gate; не менять фактический ranking ради унификации. |
| `demo/ideas/interop-exports.md` — done | З1/З2/З8: сохранить существующие ASL/DMN/Rasa конвертеры, data источники и anchors, защиту цели, `stale`; тесты master и новый v2 preview/apply из §0.3. | Обратные конвертеры/runtime и расширение скоупа форматов не делать. FM `status: done`, текстовые старые пометки/open questions не доказывают неготовность существующего кода. |
| `demo/ideas/skills-engine.md` — done | З2/З4/З8: реальный vault, наследуемый mute, optional section config, ограниченное read, trusted dispatcher/ресурсы, внешний attach/import и защита путей. | Не превращать файл датасета в исполняемый код или доверенный промпт; не путать дерево навыков с будущим типизированным сжатым деревом. |

#### 0.9.1а. Повторная сверка bigplan на 2026-11-28

Срез `docs list` на базе `bigplan`: 23 идеи, 16 без статуса done.
Разбивка: 13 captured, 2 planned, 1 null. В `plan/` 12 документов типа
plan: 3 active, 8 done и 1 superseded. JSON-зеркала из records/documents
не считаются рабочими планами. §0.9.1 выше сохраняет исходную сверку
по 15 идеям. Таблица ниже добавляет семь недостающих идей и фиксирует
зависимости с текущими планами.

| Идея или соседний план | Что входит в текущий CLI и чем проверяется | Где проходит граница |
|---|---|---|
| [Единый CLI](../ideas/unified-cli-output.md) | Это спека данного плана. З1/З5/З8/З9 подтверждают реестр, одну схему v2, фильтры, честные страницы и миграцию клиентов. Статус идеи null сохраняется до решения по её жизненному циклу. | Автоматическая смена статуса источника не является частью выбора интерфейса. |
| [Guidance и каталог](../ideas/cli-model-guidance-and-hint-catalog.md), [BMAD З2](bmad-wave-planning-skills.md) | З2 владеет схемой конверта, формами ошибок и общей интеграцией каталога. BMAD расширяет существующий каталог кодами волн и добавляет маршруты guided. Проверить один и тот же код во всех форматах и исполнимость argv. | Не создавать второй загрузчик или параллельные схемы подсказок. Полный guided-режим и его сессионные настройки принадлежат задаче BMAD. |
| [CLI-помощники волн](../ideas/wave-planning-cli-helpers.md), [BMAD З2–З3](bmad-wave-planning-skills.md) | З2/З3/З8 оставляют совместимые формы для `stale`, `docs status`, секционного патча и диагностики частичного применения. Входы и выходы новых команд BMAD описываются тем же реестром и конвертом. | `plan bind/portfolio`, якоря и множественные ID входят в BMAD. Его старые примеры с результатами на верхнем уровне data при реализации переносить в data.result/meta. Предварительная валидация пакета не обещает атомарность нескольких записей. |
| [Agent flows](../ideas/agent-flows.md) | З1/З2/З6 оставляют расширяемые коды, ссылки на скил и provenance рёбер. Проверить, что чтение диаграммы не исполняет действие, а next_actions остаётся данными. | Тип agent_flow, исполнение узлов, сохранение курсора и квиз принадлежат будущему движку флоу. `flows step` не является алиасом текущего `docs flow walk`. |
| [Флоу разработки](../ideas/dev-lifecycle-flow.md) | З5–З9 дают обзор статусов, источники, связь план–задача и проверку полноты. Приёмка проверяет цепочку с реальными ID и сохраняет этап ручного подтверждения закрытия. | Запуск конвейера, folderize и автоматическое создание задач остаются в идее флоу. Нужны отдельные реализации agent_flow и folderize. |
| [Мультипроектность](../ideas/multi-project-workspace.md) | З1/З3/З5 фиксируют явный DATA_ROOT, границы within, идентичность датасета в курсоре. Проверить одинаковые имена папок в двух корнях и отклонение курсора с другой областью. | Один dataset с несколькими projects и несколько datasets по `--root` различны. Фильтр project, подмешивание core и применение состояния к выборке остаются будущей работой. |
| [Отключаемые правила](../ideas/toggleable-rules.md) | З1/З4/З5 сохраняют существующие правила mute для скилов, явно показывают scope и допускают расширение фильтров после появления данных. | Новое enabled, универсальные enable/disable и скрытие правил/флоу принадлежат идее. Булев флаг, mute по пути и lifecycle status имеют разные значения. |
| [Теги документов v1](теги-документов-как-aliases-поиска--tags-updated-related-в-front-matter.md) | Сохранить точный `--tag` без учёта регистра, буст, `related` и `updated` после doc edit и sync. Сценарий З8 сравнивает до/после. | План active с оставшимся Obsidian-чеком. Проверка CLI его не заменяет. Сквозные теги и tag graph остаются отдельной идеей. |
| [Прямое редактирование и sync](direct-edit-and-sync.md) | Существующая команда финализирует правки и защищает витрины. З2/З3/З8 сохраняют защиту generated, область, `--if-hash`, историю и явное отсутствие сетевых действий. | Политика подтверждения явного файла и пакетного sync — решение в З2. Другие задачи можно исполнять независимо. |
| [Обзор метаданных](metadata-overview-and-harness-efficiency.md) | Приёмка BUG-022 находится в З5/З9 данного плана. | Документ superseded сохраняется для истории. |

Матрица включает шесть отдельных AFTER-планов из §0.9.2. Storage seam
З0-S относится к текущему выпуску, SQLite/FTS5 и смена драйвера относятся
к отдельной идее. Явно хранить направление связей и provenance уже сейчас.
З6 не создаёт tag graph, запуск произвольных действий из DATA_ROOT или
автоматическую терминализацию жизненного цикла.

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
   отбор по метаданным (§4) допускает поиск без query при наличии фильтра.
   Реестр в З1 описывает правила вида «A или B» без специальных скрытых default,
   но не объявляет B поддержанным до реализации. Неполный вызов, некорректный
   явно указанный фильтр и ошибка чтения обрабатываются отдельно.
5. **Все поля vs ограничение.** Все поля *выбранной поддерживаемой формы* не
   означают полный файл или всю коллекцию; `limit`, budget, cursor и explicit
   `truncated` продолжают действовать. Метрики токенов не выводятся из байтов.
   Бюджет содержимого в символах, размер всего ответа в байтах и
   токенный замер измерять отдельно по решению §0.8.
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

**Границы ответственности.** Исходные Markdown, JSON, CSV и дескрипторы
остаются каноническими. Application владеет правилами отбора, полноты,
порядка и определения свежести. Адаптер реализует хранение и может
выполнить фильтрацию на своей стороне по тому же контракту. Индекс
и кэш пересобираются, журнал и снимки истории восстанавливаются из
проверенного экспорта/backup. `HistoryBackend` отвечает только за источник
образа ревизии (Git или embedded). Чтение тела документа, структуры vault
и правил остаётся чтением источника, если операция требует актуальных
байтов. Тонкий слой CLI не должен знать layout индекса и журнала.

Первый этап поддерживает встроенные JSON/JSONL и подменяемые зависимости
для тестов. Публичный реестр сторонних плагинов, универсальный SQL/FTS API
и конфигурация выбора ещё отсутствующего драйвера входят только в Э10,
когда появится второй реальный адаптер и будут известны его требования.
Ошибочный или неподдерживаемый выбор драйвера в будущем диагностируется
явно. Для истории особенно важно исключить тихую запись в другой backend.

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
- [ ] Разделить состояние опубликованного индекса и полноту ответа на
  запрос. Отсутствующий или устаревший индекс допускает строгое чтение
  источника и построение временной проекции для одного вызова. Потеря
  доступа к источнику даёт ошибку или неполный результат. Если используется
  опубликованный снимок, метаданные и данные должны принадлежать одному
  поколению. Проверить конкурентную публикацию, включая чтение указателя
  между сменой поколений. Нельзя переиспользовать смесь shard-файлов.
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

**Приоритет для bigplan.** Первый рабочий срез уже добавил `read_index()`,
но его результат всё ещё зависит от `RegistryStore.load_current()`,
материализации JSON и повторного строгого обхода. Продолжить S1/S2 на
двух потребителях с разной нагрузкой: `status/index status` проверяет
доступность снимка без загрузки строк, `docs list/search` получает
ограниченную проекцию через семантический запрос. Не размножать прямые
вызовы RegistryStore при миграции З4–З8. Затем S3 на `sync` и `log/show`
проверяет границу журнала, чтение образа и доступ к истории при нездоровом
индексе. Дальнейшие семьи подключаются к этим путям.

Зафиксировать baseline производительности отдельно по проходам:
обход/хеширование, чтение снимка, разбор/валидация, выборка/рендер.
Проверить опубликованный свежий снимок, холодный индекс и изменение файла
вне CLI. Для K27 приводить end-to-end p50/p95 и режим снимка. Ускорение
не может опираться на молча устаревший индекс или сравнение только mtime/size.

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

Рекомендуемый порядок проверки: SQLite-индекс с прежним ранжированием →
отдельный эксперимент FTS5 → SQLite-история при доказанной пользе.
Индекс можно отдельно включить и отдельно откатить, пересобрав из
источников. Паритет фильтров, объёма страниц, полноты и диагностик
проверяется на одинаковом снимке. Паритет сортировки требуется для
одного и того же алгоритма; новый rank имеет отдельный quality gate и
версию fingerprint. SQL, tokenizer и схема таблиц остаются деталями
адаптера. Числа микробенчмарков идеи не сравнивать напрямую с полным
вызовом CLI. Пересчёт Δ и зависящих объектов измерять отдельно от
обнаружения правок, полного обхода и сортировки.

Обычный read/preview не вызывает refresh, публикацию или PRAGMA с
побочными эффектами. Для SQLite проверять read-only соединение на
каталоге без прав записи, со служебными файлами WAL/SHM и без них.
Для недоступного кэша разрешён временный снимок из источников, а для
недоступной истории требуется явная диагностика. Живая БД не открывается
как immutable для обхода этого ограничения.

Для будущей миграции history предусмотреть: неизменяемый backup и проверку его
восстановления; сохранение последовательности, original event/refs, неизвестных
полей и byte-exact образов; `rev`/digest/порядок, duplicate и усечённые коллизии;
read-only подготовку и preview плана; согласованный apply и отказ при изменении
исходника; инъекции сбоя до/во время/после переключения; проверку SQLite WAL/SHM,
checksums, `show/revert/undo/tag/log` и обратного round-trip. Если rev вычислен
из исходной строки, простая повторная сериализация JSON может поменять rev:
сохранить необходимые исходные байты/алгоритм и проверить до переключения.
Порядок хранится отдельным ключом события. Внутренний seq не заменяет
публичный rev, а rev не получает ограничение UNIQUE. Повторяющиеся rev
сохраняются, при неоднозначном обращении по rev возвращается диагностика.
Верификация экспортирует и сравнивает порядок, ревизии, неизвестные поля,
refs и точные байты исторических снимков. Для backup активной WAL-БД
нужен согласованный снимок БД, а не копирование только файла .sqlite.
Успех экспорта подтверждается восстановлением в изолированный dataset.
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

### 0.12. Старт выполнения и подтверждённое состояние

Аудит 2026-11-28 проверен в рабочем дереве `5e86eb7`. Сохранённый
`origin/master` — `7db08c7`, он содержит `sync` и новый workflow прямой
правки. Перед реализацией определить рабочий SHA заново. Оба проверенных
коммита содержат v1 Envelope. В рабочем дереве docs tree выдаёт v1 и
технический status="ok". Docs list пока отсутствует.

| Этап | Подтверждено на аудите | Первый результат |
|---|---|---|
| З0-S | Действующий JSON-индекс и история | Общие проверки чтения и отказов на адаптере и fake |
| З1 | Есть test_cli_contract, целевой реестр не найден | Инвентарь Click и schema с примерами §4 |
| З2 | v1 без guidance в проверенной пробе | Success, usage error и discovery в subprocess |
| З3 | Целевой read_index на проверенных коммитах не найден | Fresh/cold/stale/corrupt и no-write |
| З4–З5 | Legacy-дерево доступно | Проекция и один вызов docs list для 20 идей |
| З6–З7 | Доступны граф и выборки записей | Проверенные порядок, рёбра и предметная семантика |
| З8 | Потребители v1 и новый sync в сохранённом upstream | Миграция промптов и оба маршрута записи |
| З9 | Исторический K1–K30, артефактов в чекауте нет | Новый прогон на одном SHA с сохранёнными результатами |

- [ ] Проверить SHA, Python, состояние дерева и правила базы. Начать в
  чистом рабочем дереве с актуальной согласованной базой и этим планом.
  Сохранить пользовательские правки текущего checkout.
- [ ] Снять baseline командами
  `PYTHONPATH=src .venv/bin/python -m pytest tests/cli/test_cli_contract.py -q`
  и `PYTHONPATH=src .venv/bin/python -m pytest`. Зафиксировать stdout, exit
  и skips. Исторические 30/30 из §8 учитывать как справочный результат.
- [ ] Начать с инвентаризации З1 и З0-S. Подключить конверт З2 и read-only
  снимок З3. Первый сквозной результат — З4–З5. Затем мигрировать оставшиеся
  семейства по З6–З8 и провести приёмку З9. K19/K30 — условия выпуска.
- [ ] Связать реализацию с идеей и
  [отчётом об обзоре](../bugs/bug-022-no-type-overview-query.md) по полному
  doc ID. Для машинной цепочки сверить существующую модель зеркала document,
  record_id задачи и ребро implements. Проверить связь в CLI. Порядок
  исполнения задаёт §5.

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
  ключи `schema_version`, `ok`, `data`, `diagnostics`, `next_actions`, добавить обязательный `guidance` по §4 и присвоить
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
| Отбор | `--within`, `--type`, `--tag`, `--query`, `--attr-<поле>`, `--filter-file`, `--section`, `--relation` применяются по правилам §4 до сортировки/страницы; предметные пространства имён, особенно `--tag` документа и метки истории, разделяются по §0.9.3 и не притворяются одинаковыми; неприменимый фильтр — явная ошибка с подсказкой, не игнорирование. Повторения, сравнение регистра и укороченный синтаксис описать в реестре и тестах; не вводить фиктивные фильтры для действий. |
| Пределы | `--limit` и `--depth` считают элементы и уровни по контракту команды. Текстовый `--budget` считает символы Unicode полезного содержимого, метаданные вне бюджета. `--cursor` связывает страницу с командой, отбором и снимком. |
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
| `docs list/search/read/suggest/links/tree/flow/new/edit/status` | List — flat-метаданные, search — ранжирование, tree — иерархия, read — ограниченный объект. Flow сохраняет walk/render. New/edit и смена статуса — действия. |
| `records list/query/aggregate/read/create/undo-relation/status` | Коллекции — flat, read — именованная проекция. Create/undo и смена статуса — действия. QuerySpec и `--as-of` сохраняют семантику. |
| `relations graph/tree` | graph содержит реальные рёбра, tree — обход; исходное направление и повторные рёбра не теряются. |
| `types list/show/prompt/guide` | Каталог — flat, show/prompt/guide — содержательный объект; отдельное файловое сохранение — действие, raw stdout мигрирует в один формат. |
| `state get/list/set/unset`, `context`, `explain-path` | Чтение — объект/список; set/unset — preview/apply с изоляцией XDG, не придумывать file path для ключа state. |
| `log/show/diff/blame/timeline`, `history gc/adopt/export`, `revert`, `tag`, `stale` | История/различия — объект или flat-события, наблюдение внешних изменений явно; gc/adopt/export/revert/tag и ack — действия, включая побочные эффекты history backend. |
| `change list/open/show/validate/verify/apply/archive/revert`, `fix`, `init`, `index rebuild` | Отчёты и списки отдельно от мутаций; open/apply/archive/revert, fix и init — действия с preview/apply, включая проверку хеша и all-or-nothing, где она уже гарантирована. |
| `interop export` | DMN/ASL/Rasa — форматы содержимого. stdout — чтение, сохранение в файл — действие. |
| `sync` на базе с этой командой | Финализация уже сохранённых правок. Различать состояние источника, обновление метаданных, индекса и истории. З2, З3, З8. |

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
"diagnostics":[],"next_actions":[],"guidance":{"profile":"ru","mode":"compact","items":[]}}
```

Полная schema/fixtures каждого типа фиксируются в З1 на основе реальных данных;
у не-выборок поля вида/пагинации отсутствуют, а не выдумываются. Примеры для
fallback, ошибки, списка, двух страниц дерева/графа, discovery и preview должны
однозначно описывать контракт до написания адаптеров. `total` допускается только
при фактическом подсчёте; если производитель не может знать полноту, требуется
честная типизированная отметка об этом, не фиктивное точное число.

**P15.** Конверт содержит обязательный `guidance: {profile, mode, items}`
с теми же сведениями в Markdown и table. Обычный успех даёт mode=compact,
items=[]. На ошибке каталог предоставляет code, hint, skills, docs.
Next actions содержат проверяемые argv. З2 владеет схемой и интеграцией,
[план волн](bmad-wave-planning-skills.md) добавляет коды и скилы в общий
каталог. Печатать приглашение к guided после появления проверенного argv.

**Обзор метаданных.** Канонический вызов З5:

~~~bash
todoc docs list --root demo --type idea --fields id,path,title,status --limit 100
~~~

Единая flat-форма использует data.result.items и data.meta. Поля элемента
по умолчанию — id, path, title, doc_type, status, parse_status, tags,
updated, hash. Id сохраняется из источника. Status берётся из front matter,
отсутствующее значение — JSON null. Parse_status описывает состояние файла.
Повторяемый --status образует ИЛИ, --status-missing добавляет null. Другие
фильтры (тип, область по сегментам пути, точный тег) соединяются по И до
сортировки и лимита. Порядок (path,id), limit 1–1000, default 50.
Курсор привязан к команде, датасету, снимку, отбору и порядку. Проекцию и
формат можно менять между страницами. Несколько roots отклоняются явно.

Data.meta.complete отражает полноту источника, truncated — остаток страниц.
Полный пустой результат имеет total=0. При неполном обходе или невозможности
прочитать нужные метаданные — ok=false, exit 6, complete=false, total=null,
диагностика и next_cursor=null.

### Поиск и правка метаданных

**Охват.** `docs list/search` отбирают документы любых зарегистрированных
типов и обычные файлы в области сканирования. Канонические атрибуты читает
профиль формата (§4 ниже). CSV
поддерживает метаданные файла, доступные через профиль; значения колонок строк
фильтруются в `docs read --where`. `records list/query` отбирают типизированные
JSON-записи по полям самой записи, в том числе вложенным. `doc_type`, формат
файла и `entity_type` остаются независимыми. При наличии одной сущности в двух
представлениях её данные и происхождение видны в каждом представлении.

**Короткие фильтры.** `--type 'plan|idea|agent-skill'` отбирает по одному
из эффективных `doc_type` в `docs list/search`. Одинарный `--type plan`
сохраняет поведение; повторы `--type` объединяют набор. `agent-skill` —
фактическое имя типа в demo. Правила датасета могут вывести `doc_type` из
пути или атрибутов файла. Явное значение из самого файла доступно через
`--attr-doc_type`, даже когда классификатор выбрал другое значение.
`--file-format markdown` при добавлении фильтра формата проверяет носитель,
а `records --type` сохраняет значение `entity_type`.

```bash
todoc docs list --root demo --type 'plan|idea|agent-skill'
todoc docs list --root demo --type 'plan|idea' --attr-status 'active|draft'
todoc docs list --root demo --type bug-report --attr-severity 'high|medium'
```

`--attr-<имя> 'значение1|значение 2'` отбирает по записанному атрибуту
независимо от его расположения в Markdown или JSON. Именем служит точный
ключ из discovery (`--attr-agent_impact` для `agent_impact`). Для скаляра
это равенство одному из значений, для массива скаляров — наличие любого.
Операнды переводятся в тип поля и проверяются по контракту. Повторы одного
поля образуют объединение, разные поля и ограничения области соединяются
по И. Пробелы вокруг `|` удаляются, пробелы внутри значения сохраняются,
пустые варианты отклоняются. Весь аргумент со знаком `|` заключать в
кавычки. Для буквального `|` внутри значения, вложенных путей, диапазонов,
явного `null` и проверки наличия использовать `--filter-file`.

Реестр передаёт распознанные `--attr-*` в общий предикат. Справка показывает
правило, выбранный тип показывает допустимые ключи, а неизвестные поля и
опечатки получают диагностику. Последовательность аргументов и дубликаты
в наборах ИЛИ не меняют fingerprint курсора. Быстрые флаги и эквивалентный
предикат дают одинаковый отбор.

**Отбор.** З1 публикует доступные поля, типы, операторы и источники в discovery.
З5 и З7 дают общий `--filter-file` с версионированным JSON-предикатом и явным
путём поля. Поддержать равенство, набор допустимых значений, принадлежность
любого или всех значений массиву, наличие поля и включительные границы
диапазона. Отсутствующее поле, явный `null` и пустой массив различаются.
Неизвестное для области поле, неверный тип операнда или несовместимые типы
поля в разных профилях дают диагностику с предложением сузить область или
исправить предикат. Список полей включает объявленные схемой и фактически
доступные пользовательские метаданные, например `severity` и `agent_impact`
у баг-репортов. Добавление поля в разрешающий его тип не требует правки Python.
`--fields` меняет только вывод. Условия применяются до ранжирования, лимита
и курсора. Фильтры объединяются по И, существующие повторяемые статусы
сохраняют ИЛИ. Запрос с условиями по метаданным работает без полнотекстового
`--query`. Формат и проекция не меняют выборку. Нормализованный предикат
учитывается в fingerprint курсора. `QuerySpec` и старые флаги сохраняют
семантику и используют совместимые части общего предиката.

**Даты и теги.** Дата выбирается по имени поля. У Markdown это, например,
`created` или `updated`, у записи — `date` или поле даты её типа.
Проверять календарные даты и границы диапазона. `records list --since/--until`
сохраняет привязку к `date`; `--as-of` сохраняет семантику времени правды.
`--tag-in 'тег1|тег2|тег-3'` — краткая форма ИЛИ по массиву тегов;
`--tag-all` — И по тому же массиву. Старый `--tag` сохраняет точное сравнение
без учёта регистра. Разбирать `|`, обрезать пробелы вокруг элементов,
отклонять пустые элементы, ошибки формата указывать явно. Для Markdown
действует существующий формат kebab-case: `тег-3` допустим, `тег 3` для
хранения недопустим. Для записи использовать её `tags` либо явное
сопоставление поля из профиля (например `task.labels` при совпадающей
семантике); без такого поля запись не совпадает, без носителя во всей
выбранной области выдавать диагностику. Теги папок, скилов и история
сохраняют собственные области. Граф, каталог и миграция тегов описаны
[в отдельной идее](../ideas/unified-tags-and-tag-graph.md).

**Правка.** З8 добавляет одну структурированную грамматику patch для
`docs edit` и редактора типизированных записей: установка нового или
замена существующего значения, явное удаление ключа и изменение элементов
массива. Обычный объект JSON редактируется в документном профиле, если он
разрешает запись. Просмотр показывает дифф, результирующие метаданные,
валидацию и hash, применение повторно проверяет hash и тип. Сохранять
Markdown-тело и остальные поля, использовать штатные границы записи,
историю и обновление индекса по §0.10. Запрещать удаление обязательного
поля и правку идентификаторов и производных полей через обычный patch;
`created` и `updated` Markdown ведёт движок. Отклонённая операция не
меняет файл. Существующий линейный MD patch сохраняется. CSV-колонки,
файлы конфигурации и миграции схем имеют отдельные процессы.

**Единая схема документов Markdown и JSON.** Один контракт метаданных в
`.todoc/document-metadata.schema.json` задаёт ключи, типы и общие обязательные
поля. Для новых управляемых документов общий минимум в источнике — `id`,
`title`, `lang`, `created`, `updated`; `tags` и `related` одинаково
типизированы и необязательны. Профиль `doc_type` добавляет обязательность,
enum и пользовательские поля (например, `status` или `agent_impact`).
Правила выбора профиля и ограничения типа одинаковы для Markdown и JSON.
Встроенные значения `doc_type` проверяются при наличии; эффективный
`doc_type` обязателен в нормализованной модели. Формат, путь и hash относятся
к вычисляемым полям. Обязательные разделы Markdown и структура JSON-тела
проверяются в профилях формата. CSV остаётся на своём профиле.

- Markdown хранит атрибуты во front matter; управляемый JSON-документ — в
  объекте `meta` рядом с содержимым. Адаптеры переводят оба формата в одну
  модель до разрешения типа и общей проверки. В диагностике сохраняется
  позиция исходного YAML или JSON Pointer (`/meta/status`).
- Базовая схема и схема типа имеют один источник в реестре, с локальными
  ссылками и без сетевого разрешения. Шаблоны создания, `types show`,
  discovery, `validate` и preview/apply используют одну эффективную схему.
  Проверку выполнять и для пустых метаданных, чтобы `required` срабатывал.
  Индекс хранит производную проекцию и версию контракта. Смена схемы
  инвалидирует проекцию и курсоры по §0.10.
- Существующий плоский JSON читается через профиль совместимости. Для
  документов со старым расположением ключей профиль явно определяет карту.
  При конфликте значения в старом источнике и `meta` выдаётся диагностика.
  Типизированные JSON-записи сохраняют `record_id`, `entity_type` и поля
  своей схемы. Если запись используется как документ, её документные
  атрибуты проецируются через профиль, например `record_id → id` при
  совпадающей семантике. Версия контракта источника отделена от версии
  конверта CLI.
- Новые управляемые документы проходят строгую проверку при создании.
  Для существующих файлов собрать отчёт о недостающих полях и переносе
  плоского JSON, дать явный preview миграции и включать строгий режим для
  профиля после подтверждённой чистой проверки. При миграции сохранять
  идентичность, тело и ссылки. Недостоверные даты не заполнять.
- Новое необязательное поле можно добавить через patch, если его допускает
  профиль. Обязательность, тип и enum меняются в схеме с проверкой
  существующих данных. Фильтрация, валидация и правка подхватывают изменения
  из реестра без появления новых флагов в исходном коде.


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

- [ ] Описать единую схему документов, сопоставления форматов и каталог
  доступных `--attr-*` по типу. Проверить составление схемы с профилем и
  диагностику конфигурации до чтения корпуса.

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
- [ ] Включить новый docs list, docs/records status, interop export и sync,
  если он присутствует в базе, в матрицу Click. Снять types list, scan и
  records list для выбранной базы. Различить Markdown-план, зеркало document,
  запись plan и их ID. Для незаполненных типов покрыть фикстурами отличающуюся
  семантику, общие случаи проверить общим контрактом.

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
- [ ] В test_unified_discovery.py проверить P15 для JSON/Markdown/table.
  Ошибка флага docs read предлагает локальную справку. Исполнимый read
  требует известного ID, в том числе для файла со своим custom id.
- [ ] На базе с sync добавить review-first финализацию. Preview показывает
  область и план, apply выполняет финализацию. Проверить explicit paths,
  --dirty, --out, generated guard, hash и --no-history. Preview не пишет в
  источник, индекс, историю и файл вывода. Диагностика при сбое apply
  перечисляет завершённые этапы и условия повтора.

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
- [ ] Для docs list проверить fresh/cold/stale/corrupt. Старый снимок без
  полей статуса пересчитать в памяти. Перехватить попытки записи и сравнить
  байты индекса, кэша, истории и XDG. Проверить исчезновение или отказ чтения
  файла во время обхода по контракту incomplete из §4.

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

- [ ] Выполнить документную часть контракта метаданных §4: discovery, поиск
  без текста, OR/AND по тегам, диапазоны `created`/`updated`, статусы и
  пользовательские поля. Проверить планы, идеи, баг-репорты и JSON-документы,
  пограничные даты, отсутствующее поле, неверное условие и смену курсора.

- [ ] Проверить союз типов `plan|idea|agent-skill`, повторы и совпадение за
  первым лимитом. Отдельно проверить эффективный и объявленный `doc_type`,
  разные значения одного атрибута через ИЛИ, пересечение разных полей,
  неизвестное имя, пробелы и одинаковый курсор у эквивалентных условий.

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

- [ ] В test_unified_docs.py проверить docs list на общем снимке и курсоре.
  Покрыть custom id, null, parse_status, OR/AND фильтров, --status-missing,
  совпадение за лимитом, смену снимка и 51+ строк без пропусков.
  Явная проекция docs read исключает text или lines, сохраняя provenance
  и признак усечения.
- [ ] Реализовать согласованный K19 для применимых текстовых форм чтения.
  Сохранять происхождение, координаты и признак усечения вне лимита.
  Логический текст проекции ограничивать по символам до рендера.
  Случаи проверки и единицы измерения заданы в §0.8.
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

- [ ] Подключить общий предикат метаданных §4 к `records list/query`.
  Проверить вложенное поле, массив, `null` и отсутствие, несовместимые типы
  и поля тегов у разных записей. Сохранить QuerySpec, `--since/--until` и
  `--as-of`. Проверить одинаковую выборку для всех форматов вывода.

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

- [ ] Реализовать структурированную правку метаданных §4. Проверить
  добавление, замену и удаление необязательного поля, операции с массивом,
  обязательность, сохранение Markdown-тела и остальных полей JSON, параллельную
  правку, историю и отсутствие побочных эффектов preview и отказов.
  Добавить необязательное поле к профилю фикстуры и пройти поиск/правку через
  штатный CLI без изменения исходного кода.

- [ ] Проверить одни и те же метаданные в front matter и JSON `meta`:
  одинаковые projected fields, совпадения фильтров и смысл диагностик,
  обязательное поле в пустом объекте, неверный enum и расхождение старого
  плоского ключа с `meta`. Подготовить отчёт и preview совместимой миграции
  до включения строгой проверки существующего датасета.

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

- [ ] Обновить потребителей штатного edit и прямой правки с sync на базе,
  где они предусмотрены. Проверить updated, историю, повторное чтение и
  диагностики. В собственных скилах использовать обзор метаданных и проверять
  один вызов перед тиражированием.
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

- [ ] Сценарии test_unified_e2e.py: обзор идей, поиск с ограниченной секцией
  и источником, запись с ребром и фильтром до лимита, граф плана и задачи,
  правка с историей и повторным чтением. На 20 идеях один запрос данных даёт
  11 captured, 2 planned, 6 done, 1 null. Компактный stdout ≤12000 UTF-8 байт,
  ≤2000 токенов при названном токенизаторе. Отдельно считать discovery.
- [ ] Проверить остановку зависимого пакета после первого ошибочного probe.
  Результаты scripted и реального LLM-прогона хранить отдельно. Для
  PowerShell/WSL проверить аргументы с пробелами и кириллицей, недоступный
  runtime пометить not_run.
## 6. Definition of Done

- [ ] Реализован и проверен З0-S: рабочие JSON/JSONL адаптеры и независимый
  fake проходят общие storage-контракты, CLI/use cases не обходят seam (§0.10);
  никаких заявлений о готовности SQLite без отдельной реализации и тестов.
- [ ] Контракт метаданных §4 принят по З5/З7/З8. Один набор приёмочных
  фикстур проверяет отбор по тегам, датам, статусам и пользовательскому
  полю, а также проверяемую правку Markdown и типизированного JSON.
- [ ] Выполнены архитектурные проверки §0.9.2–§0.9.5; конфликт времени
  и будущего logging не скрыт, зафиксированы согласованные решения и незавершённые
  возможности. Массовые миграции чужих планов без отдельного поручения не запускались.
- [ ] Каждое требование идеи сопоставлено задаче З0-S или З1–З9; матрица охватывает все
  листовые команды, fallback и discovery проверены во всех форматах.
- [ ] `doc:bugs/bug-022-no-type-overview-query.md` принят по З5/З9. Исторический
  дефект повторных ID проверен как самостоятельный сценарий.
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
- [ ] Перед benchmark согласовать любое отклонение от исходных критериев и
  решений по K3 и K19. Использовать отдельный каталог результатов.
  Измерить на финальном состоянии и записать версии, среду и результаты.
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

- Частично З3/З5/З8: `docs search` перешёл на v2, flat-проекции и cursor, связанный со снимком и параметрами; `--within`, фильтры и бюджет фрагментов проверяются до вывода. Поздняя ошибка чтения и заметное изменение во время поиска дают отказ (BUG-020); байтовый бюджет первого фрагмента ограничен (BUG-021). K1–K5 и K22–K24 проверены на изолированной копии demo. Снимок не атомарен, полный З5 и benchmark K1–K30 остаются открыты. Для дублирующегося id подсказка чтения отключена (исторический BUG-022 о повторяющемся ID); ручной `docs read` по такому id возвращает ошибку.
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

### Уточнение 2026-11-28: BUG-022 исполняется в этом плане

По запросу пользователя устранено дублирование планирования. Единственный
исполняемый план по BUG-022 — данный документ; [отдельный разбор](metadata-overview-and-harness-efficiency.md)
сохранён как исторический материал. Его З1–З7 не являются параллельным backlog.
Покрытие ниже — требования к существующим З1–З9, не новая очередь задач.
[Баг](../bugs/bug-022-no-type-overview-query.md) остаётся open до реализации и приёмки.

| Требование BUG-022 | Владелец здесь | Обязательное дополнение |
|---|---|---|
| Обзор документов типа без чтения N тел | З1, З5 | Каноническая metadata-выборка без обязательного текстового query |
| Статусы идеи и состояния файла различаются | З1, З3, З5, З8 | Явные lifecycle status и parse_status, отсутствующее значение null |
| Полнота, отбор до лимита и cursor | З3–З5 | Отдельно полнота источника и усечение страницы, связанные с query/snapshot курсоры |
| Дублирование вывода | З4, З5, З8 | Проекция метаданных/полей; предусмотренные поля по умолчанию не скрывать |
| Конкретная guidance вместо корневого help | З2; общий P15 — план волн З2 | Один каталог и envelope, готовые безопасные argv |
| Избыточные действия модели/ошибочный пакет | З8, З9 | Собственные скилы и сценарная проверка, не обещание контроля внешнего runtime |
| Стоимость пользовательского ответа | З1, З9 | baseline/result, вызовы данных отдельно от discovery, bytes отдельно от tokens |

#### Дополнение к З1 и З5: канонический обзор метаданных

- [ ] Канонический обзор — docs list по §4. Реестр, снимок, проекции и
  курсоры общие, проверки находятся в З1 и З5.
- [ ] Выборка отдаёт как минимум id, path, title, doc_type, статус жизненного
  цикла, parse_status и данные полноты/страницы; идентификатор — реальный, включая
  custom id. Метаданные берутся из единого актуального снимка с уже разобранным fm.
  Старое Document.status="ok" нельзя молча выдавать за статус идеи.
- [ ] Общие фильтры типа/статуса/области/тега работают до сортировки и страницы;
  тип задаёт допустимые статусы, core не зашивает idea/captured/done.
  Отсутствующий статус виден как null и не превращается в captured.
  Политика OR повторов одного фильтра и AND разных закрепляется в реестре.
- [ ] Null, parse error и пустая полная выборка различаются. Неполный обход
  не заявляет total как достоверный полный итог; параметры полноты и диагностики
  согласованы с общим v2-контрактом. Page truncation не равна ошибке источника.
- [ ] Единый механизм --fields/--exclude-fields позволяет не получать тело,
  lines и text одновременно, если нужна одна форма. Не вводить второй
  compact/legacy режим и не переопределять общий schema_version локально.

#### Дополнение к З2 и З8: инструкция и восстановление после ошибки

- [ ] Guidance ошибки docs read указывает на локальную справку/правильные флаги;
  исполняемый read предлагается только при известном реальном id, не по догадке
  из path. Поле guidance и тексты каталога P15 согласовать с
  [планом волн, З2](bmad-wave-planning-skills.md); второй каталог не создавать.
- [ ] В собственных скилах закрепить проверку существующего плана до создания
  нового, маршрут metadata → полнота → ответ, повторное использование загруженного
  скила и правило «один probe перед тиражированием формы команды».
- [ ] При ошибке зависимый пакет не запускается. Это правило для агента/runner,
  CLI не может отменить уже запущенные внешней платформой независимые процессы.
  PowerShell/WSL smoke использует argv и проверяет кириллицу/пробелы/скобки;
  внешний runtime не перенастраивается без отдельной задачи.

#### Дополнение к З9: обязательный сценарий BUG-022

- [ ] Fixture из 20 идей: 11 captured, 2 planned, 6 done, 1 без fm status,
  с русскими title и custom id; это контрольные данные, не вечный счётчик demo.
  Один запрос данных с limit=100 выдаёт полный обзор без N отдельных docs read.
  Ответ агента выделяет 14 незавершённых/несогласованных с оговоркой про null.
- [ ] Для 100/500 идей страницы обходятся без потерь/дубликатов; число запросов
  соответствует страницам, а не числу документов. Проверить изменение snapshot,
  неизвестное поле, limit=0, совпадение после лимита и within ideas vs ideas-old.
- [ ] Проверить no-write fresh/cold/stale/corrupt путей, включая parse cache,
  index, history и XDG; использовать общие тесты З3, не дублирующий read_index.
- [ ] Стенд намеренно ошибается на первом probe: до исправления attempts=1,
  remaining_reads=0. Scripted conformance и настоящий LLM-прогон различаются;
  недоступный LLM явно not_run. Инструкция не считается доказанной гарантией.
- [ ] Цель выбранной проекции 20 идей — ≤12000 UTF-8 байт; ≤2000 токенов —
  только при названном токенизаторе. Без него tokens=null, не оценка из bytes.
  Отдельно фиксировать discovery/data calls, успешные/ошибочные запуски,
  cold/hot latency и среду. Исторические 54 запуска — evidence, не API usage.
- [ ] BUG-022 закрывать только после этого сценария, общих гейтов и подтверждения.
  Исторический отдельный документ не запускать и не трактовать как второй контракт.

### Аудит готовности 2026-11-28

- §0.12 задаёт рабочую базу, порядок запуска и границы доказательств.
- Обзор, P15, статусы, sync и сквозные сценарии внесены в §4 и задачи
  владельцев. Дополнение §8 сохраняет историю переноса BUG-022.

- Начато исполнение в ветке `bigplan` от `origin/master` (`7db08c7`).
  Перенесены актуальный план и источники, на которые он ссылается.
  Подготовлена локальная .venv через uv из-за отсутствующего ensurepip.
  З1: добавлена рекурсивная инвентаризация Click, включая вложенные команды.
  З2–З5: первый срез v2 и guidance применены к docs list. Добавлены общий
  интерфейс проекции и непубликующий путь сборки снимка с проверкой
  содержимого. Тест на корпусе из 20 идей подтверждает один вызов, разделение
  статусов, бюджет ответа, курсор и отсутствие изменений файлов.
  З0-S, общая миграция команд и выпускная приёмка остаются открыты.
- З1–З2: v2 discovery работает в корневой и вложенных группах. Схема
  конверта хранится в `src/todoc/data/output/envelope-v2.json`. В CLI-тестах
  проверяются каталог команд, форма результата и отсутствие записей.
- З3: чтение документов, записей, отношений, timeline и stale использует
  непубликующий снимок. Log и blame читают уже записанные события. Явный
  index rebuild по-прежнему наблюдает внешние правки. На холодном датасете
  проверены 12 команд с побайтовым сравнением файлов до и после вызова.
  Фильтры records list по датам и связи применяются до limit.
- Ручная проверка на демо этой ветки: 23 идеи одним запросом, complete=true,
  8680 байт в замере через PowerShell. Данные демо отличаются от фикстуры из
  20 идей. Замер не заменяет выпускной бенчмарк.
- З2: `history gc` по умолчанию возвращает preview. Для удаления нужен
  `--apply`. CLI-тест проверяет сохранность журнала при просмотре,
  конфликт preview/apply и фактическое применение.
- З9: стенд бенчмарка получил отдельные временные каталоги и явный
  каталог результатов. Пороги K1–K30 сохранены. K19 измеряет весь JSON
  в UTF-8. Точечный прогон K19 получил 16679 байт при пороге 500, этап
  остаётся открытым. Полный pytest: 1344 passed, 22 skipped. Branch coverage
  100%, validate без диагностик, linkcheck и git diff --check прошли.
- Изолированный quick benchmark первой версии дал 28.4/30.
  K8 выявил неэкранированные кавычки в YAML-описаниях трёх процессных
  скилов. Описания исправлены, независимая повторная проверка PyYAML
  разобрала 248 документов без ошибок. Исторический quick-отчёт проверял
  у K19 только поле text, отдельный исправленный замер указан выше.
  K27 и K30 в quick-отчёте частичные. Для поиска и чтения исключено
  построение неиспользуемого графа упоминаний на холодном снимке.
  Повтор K27 из трёх запусков без параллельного pytest на отдельном
  корпусе с заданными дефектами остаётся частичным. Медианы docs search
  4098 мс и records list 4001 мс выше порога 2500 мс. Актуальный полный
  pytest прошёл с 1344 passed и 22 skips, branch coverage 100%.
- Продолжение З4–З5: `docs tree` учитывает физическую глубину относительно
  `--within`, сохраняет алиас `--max-depth` и возвращает явное усечение с
  `next_cursor`. `docs list` и `docs tree` используют одну реализацию
  страниц. Проверены 55 строк, отсутствие пропусков, смена глубины и
  конфигурации папки. Раздельные массивы v1 пока сохраняются для клиентов.
  `docs read` поддерживает явную проекцию полей с сохранением хеша и
  координат секции. Бюджет полного конверта K19 остаётся открытым.
  Проверки этого шага: 1348 тестов прошли, 22 пропущены, покрытие ветвей
  100%, validate и linkcheck без ошибок.

- §0.12 задаёт рабочую базу, порядок запуска и границы доказательств.
- Обзор, P15, статусы, sync и сквозные сценарии внесены в §4 и задачи
  владельцев. Дополнение §8 сохраняет историю переноса BUG-022.

### Повторный аудит согласованности 2026-11-28

- §0.9.1а сверяет идеи и планы ветки, указывает владельцев контрактов и
  будущих функций. Дополнительного плана исполнения для BUG-022 нет.
- Уточнение пользователя по K19 заменило прежний вывод о бюджете целого
  конверта. Исторический замер 16679 байт сохраняется как измерение
  полного вывода. До закрытия K19 нужны согласованная правка стенда,
  справки и прохождение критериев §0.8.
- Приостановленная миграция docs tree на v2 остаётся изменением рабочего
  дерева. Повторный аудит относится к плану и не засчитывает эту миграцию
  без проверки потребителей и полного прогона.

### Выполнение в bigplan 2026-11-28

- З5/З7: `docs list/search` поддерживают объединение типов, `--attr-*`,
  `--tag-in`/`--tag-all`, `--filter-file` и `--file-format`. Отбор по
  метаданным проходит без полнотекстового запроса. `records list/query`
  используют тот же предикат и сохраняют QuerySpec и `--as-of`. `docs
  list/search/tree/read` и обе выборки записей выдают v2.
- З8: управляемые Markdown и JSON-документы используют общий файл схемы.
  `init --document-metadata` ставит пакетный шаблон, `types metadata`
  показывает результаты перед подключением к существующему датасету.
  `docs new` принимает JSON-атрибуты, `docs edit` и `records edit` умеют
  структурированную правку с хешем preview, проверкой схемы и историей.
  Общая схема в demo включена после миграции 27 Markdown-документов.
  Для 22 файлов `created` восстановлен из первого добавления в Git,
  `updated` — из последнего Git-изменения. Остальные пропуски заполнены
  из существующей идентичности, заголовков и языка источника. Тела и ID
  проверены чтением до и после. Строгий контракт проверил 197 управляемых документов.
- З5: ограничение K19 проверено на 500 символах. Кириллица, emoji, длинные
  фрагменты и ограничение секций проверяются в CLI-тестах. Измерение
  UTF-8 размера конверта осталось отдельным.
- З6: граф сохраняет направление, параллельные рёбра, self-loop и источник;
  в Markdown доступен Mermaid. Граф и дерево связей имеют привязанный к
  снимку курсор, дерево повторяет контекст предков на следующих страницах.
- З0-S: введены порты индекса, parse-cache и истории. Проверяется манифест
  шардов JSON-индекса; есть сценарии с in-memory адаптерами и инъекцией
  сбоя публикации. `log` читает JSONL строго и выдаёт v2. Часть команд
  истории и записи ещё требуют перехода на порт.
- З9: K30 проверяет восемь критериев по наблюдаемым данным, включая
  `git check-ignore`, текстовый Git diff и CLI в сетевом namespace WSL.
  Отдельная проверка K30 на demo прошла 8/8.
- В общем конверте также работают `scan`, `check`, `validate`, `check-config`,
  `status`, `doctor`, `index status/rebuild`, `types list`, `state list`,
  `docs links/suggest`, `skills read` и линейный `docs edit` с точным diff.
- В предыдущем полном замере K27 все шесть команд уложились в пороги.
  Медиана `docs search` составила 2267 мс, `records list` — 2088 мс.
  Для этого повторный разбор источников заменён использованием проверенной
  проекции с сохранением проверки хеша перед выдачей текста.
- Повторный полный benchmark со строгой схемой demo: 1402 теста прошли,
  27 пропущено. K19, K22, K27 и K30 прошли. Медианы K27 для `docs search`,
  `docs read` и `records list` составили 1635, 1593 и 1550 мс; p95 — 1680,
  1743 и 1639 мс. В проверяемых выборках Markdown-метаданные и оглавление
  читаются без разбора ссылок. Полная проверка по-прежнему разбирает связи.
- K29 остаётся открытым: 97% покрытия, 187 непокрытых инструкций и 115
  частично покрытых ветвей. `coverage report --fail-under=100` завершился
  с кодом 2. Общий выпускной гейт остаётся открытым.

План остаётся active. Для Done обязательны полный аудит листовых команд,
оставшиеся review-first операции, сквозной seam-гейт, полный benchmark
и branch coverage 100%. Результаты частичных прогонов не закрывают эти пункты.

### Миграция команд истории и создания записей 2026-11-28

- `show`, `diff`, `blame`, `timeline`, `revert`, `tag`, `history adopt`,
  `history export`, `history gc` и `records create` выдают v2. `diff`
  ограничивает содержимое в символах, включая переводы строк, и сообщает
  об обрезке. `revert` проверяет исходный хеш при записи.
- `tag`, `history adopt`, `history export` и `history gc` по умолчанию
  возвращают план. Запись требует `--apply`, `--if-plan-hash` проверяет
  актуальность плана. Очистка отклоняется при оборванном журнале и когда
  удаляемое событие используется меткой. Справка CLI обновлена.
- Полный pytest в итоговом benchmark: 1409 прошло, 27 пропущено. Строгая
  проверка demo: 469 документов, 0 диагностик. Linkcheck: 1170 ссылок, 0 битых.
- K29 открыт: 97%, 215 непокрытых инструкций, 143 частично покрытые ветви.
  Наибольшие группы пропусков в `cli.py`, фильтрах, патчах метаданных,
  файловом хранилище истории и проверке манифеста индекса.
- Индикатор миграции: `UnifiedCommand` используется в 35 из 67 листовых
  команд. До закрытия З1–З3 остаются fallback, discovery, возможности
  команд и проверка всех форматов вывода. Приоритет оставшихся операций
  записи: `docs new`, `sync`, `change`, `skills attach/import`, `fix`,
  экспорт и состояние агента.
- `sync` использует порты истории и parse-cache. Предыдущие хеши путей
  выбираются за один проход журнала. `history gc` использует порт для
  инвентаризации и удаления снимков, замены журнала и расчёта его размера.
  Прошло 180 целевых тестов, включая сценарии с адаптерами в памяти.
- До S6 остаются прямые обращения к журналу в `changes` и `context`,
  часть внутренних операций чтения истории и общий сквозной тест
  с подменой адаптеров в CLI и матрицей отказов из §0.10.
- Итоговый benchmark: K1–K28 и K30 прошли, K29 частичный. Лимит K19
  вернул 500 символов текста, все 6 команд K27 уложились в пороги.

### Выпуск CLI 2026-11-28

- Полный pytest прошёл: 1660 тестов. `coverage report --fail-under=100`
  подтвердил 8573 покрытые инструкции и 3204 покрытые ветви, пропусков нет.
- Все критерии K1–K30 получили `pass`, суммарная оценка 29,9 из 30.
  K19 ограничил текст 500 символами, K27 выдержал все шесть порогов.
- Проверены отказы на повреждённых источниках, устаревших курсорах и
  планах записи, дубликатах идентификаторов и изменениях во время чтения.
- За индекс и историю отвечают внедряемые порты. Для полного закрытия
  §0.10 ещё нужны ограниченное чтение снимка через порт и архитектурная
  проверка всех потребителей. Драйвер SQLite относится к следующей
  итерации по §0.10.4.
