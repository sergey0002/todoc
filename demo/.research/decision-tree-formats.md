---
id: doc:decision-tree-formats
title: "Ресёрч: машиночитаемые форматы деревьев решений и скриптов звонка (развилки с произвольными свойствами)"
doc_type: research-report
lang: ru
created: 2026-11-26
updated: 2026-11-26
tags: [research, research-report, decision-tree, форматы, dmn, asl, bpmn]
related: ["[[documentation-system]]", "[[теги-документов-как-aliases-поиска--tags-updated-related-в-front-matter]]"]
---

# Ресёрч: машиночитаемые форматы деревьев решений

**Вопрос:** какой существующий стандарт удобнее всего хранить скрипт-звонка/дерево
решений (флоу с развилками), если на каждой развилке нужны **произвольные свойства**
(«спросить у пользователя» / «действовать по умолчанию» / подсказка / timeout),
при этом формат должен быть **валидированным, машиночитаемым, удобно редактируемым**
и в перспективе — с **CLI-навигацией и чтением**.

**Контекст:** сейчас флоу в этом датасете — `flow-doc` (markdown: state machine +
таблица решений + mermaid flowchart + lineage, эталон в
[documentation-system](../ideas/documentation-system.md)); истина — таблица решений,
mermaid — проекция. Ресёрч отвечает на вопрос, чем дополнить/заменить markdown-таблицу
структурированным форматом.

## 1. Критерии

| # | Критерий | Пояснение |
|---|---|---|
| C1 | Произвольные свойства на развилке/ветке | `mode: ask-user \| auto` и любые свои поля, без правки стандарта |
| C2 | Стандарт/спека + схема валидации | валидация готовым валидатором, не самописным кодом |
| C3 | Текстовый, diff-friendly | редактирование в git-PR, осмысленные диффы, Obsidian |
| C4 | CLI-навигация/чтение реализуемо просто | обход узлов/ветвей командой, ответ «что делать на развилке N» |
| C5 | Семантика порядка правил | приоритет строк/ветвей (наш P1..Pn) без сюрпризов |
| C6 | Совместимость с todoc | файлы — истина; JSON Schema 2020-12 уже валидируется движком; без правок `src/` на уровне данных |

## 2. Кандидаты

### DMN (OMG Decision Model and Notation) — таблицы решений как стандарт
Децизионные таблицы — первоклассный артефакт: hit policies `UNIQUE/ANY/PRIORITY/FIRST/COLLECT`
точно формализуют наш порядок P1..Pn (`PRIORITY` — приоритет по списку выходов,
`FIRST` — первая совпавшая строка); FEEL — выражения условий; DRD — диаграмма требований.
Хранение — XML (XSD-валидация), расширения — `extensionElements`.
**+** C2/C5 идеально; **−** C1 (расширения многословны), C3 (XML-диффы тяжёлые),
«спросить пользователя» не в модели (DMN — про решения, не про процесс).

### BPMN 2.0 — процессы, где «спросить пользователя» встроено
`userTask` (человек) vs `serviceTask`/`scriptTask` (автоматика) + `exclusiveGateway`
с условиями и `default`-потоком — **родная семантика вопроса пользователя**:
движок на userTask создаёт задачу человеку, на serviceTask исполняет сам.
Хранение — XML, исполняемый стандарт (Camunda/Red Hat).
**+** C1/C5; **−** heavyweight для одного дерева: роли, пулы, события; C3 тяжёл.

### Amazon States Language (ASL) — JSON-дерево Choice
`Type: "Choice"` + `Choices: [{Condition, Next, Assign/Output}]` + `Default` —
машиночитаемое дерево с ветвями-правилами и веткой по умолчанию; есть JSON Schema;
интерпретаторы за пределами AWS (asls-сообщество).
**+** C2/C4/C5 (порядок Choices = порядок проверки); **−** C1 (свои поля — только в
`Comment`/`ResultPath`), «спросить пользователя» нет (модель автоматизации), AWS-центризм.

### CNCF Serverless Workflow — YAML/JSON со schema и metadata
Вендор-нейтральная спека: **YAML и JSON равноправны**, структура валидируется
официальной JSON Schema; у каждого state есть `metadata` (object) — произвольные
свойства уровня состояния; `switch`-состояния — ветвление по условиям.
**+** C1/C2/C3 (YAML читабелен); **−** оркестрация сервисов, а не диалоги; модель
богаче нужного; C4 требует своего обходчика.

### XState / Stately — JSON statecharts с `meta`
Каждый state node несёт `meta` (object) — штатное место произвольных данных
(в реальном проекте в `meta` жили endpoints, схемы, SLA-часы); guards/actions —
именованные ссылки; Stately editor/визуализатор; JSON Schema/TS-типы.
**+** C1/C2/C4 (граф читается tooling'ом); **−** формат компании, ломался между
v4/v5; оркестрационная семантика избыточна; JSON многословен (в спайке: ~2500 строк
JSON против ~600 YAML).

### Rasa CALM flows — YAML-флоу для диалогов
Флоу = YAML: шаги `collect` (спросить пользователя!), `action`, ветвление
по условиям, `call`/`link` между флоу; текстовые description управляют роутингом;
`rasa validate` — CLI-валидация.
**+** C1/C3/C4 (это буквально скрипты звонка с «спросить»); **−** привязка к Rasa
рантайму; стандарт де-факто одной платформы.

### Классика IVR: VoiceXML, SCXML, Twilio Studio, Dialogflow CX
VoiceXML (W3C) — исторический стандарт телефонных скриптов (формы, меню, DTMF) —
XML, но для новых проектов мёртв; SCXML (W3C) — statecharts в XML — валидируем,
но академичен; Twilio Studio Flow JSON / Dialogflow CX export — JSON-деревья
с ветвями и условиями — удобны, но проприетарные экспорты (vendor lock), схемы
нестабильны. Все — C3/C6 хуже облачных форматов.

### Mermaid flowchart (текущий статус-кво)
Текст, рендерится в Obsidian/GitHub; но нет схемы валидации семантики, произвольные
свойства — только комментарии, CLI-навигации нет. C1/C2/C4 — нет; служит проекцией.

## 3. Матрица

| Формат | C1 произв. свойства | C2 схема | C3 diff | C4 CLI | C5 порядок | Итог |
|---|---|---|---|---|---|---|
| DMN (XML) | ± extensionElements | ✅ XSD | ❌ | ± движки | ✅ P/F | сильный стандарт таблиц, тяжёлый носитель |
| BPMN (XML) | ✅ (task types) | ✅ XSD | ❌ | ± движки | ✅ default flow | избыточен для дерева |
| ASL (JSON) | ± (Assign/Output) | ✅ JSON Schema | ± | ✅ | ✅ Choices | близко, но без «user» |
| CNCF SW (YAML) | ✅ metadata | ✅ JSON Schema | ✅ | ± | ✅ switch | близко, оркестрационный |
| XState (JSON) | ✅ meta | ✅ schema/TS | ± | ✅ tooling | ✅ always[] | близко, многословен |
| Rasa CALM (YAML) | ✅ props шагов | ✅ rasa validate | ✅ | ✅ | ✅ if/else | диалоговый, платформенный |
| VoiceXML/SCXML (XML) | ± | ✅ XSD | ❌ | − | ✅ | устаревшее/академичное |
| Twilio/DfCX (JSON) | ✅ | ❌ проприетарно | ± | − | ✅ | vendor lock |
| Mermaid (текст) | ❌ | ❌ | ✅ | ❌ | вручную | только проекция |

## 4. Рекомендация

Ни один стандарт не закрывает весь набор C1–C6 одновременно: «спросить пользователя»
нативно есть только в BPMN/Rasa, произвольные свойства на узле — в XState (`meta`) и
CNCF SW (`metadata`), таблицная семантика порядка — в DMN, при этом diff-friendly
носитель + JSON Schema + Obsidian + существующий валидатор движка — только у
самописного минимализма на JSON Schema.

**Рекомендация (двухслойная, согласуется с планом softdoc):**

1. **Нативный слой todoc — структурированная запись дерева.** JSON-запись entity
   (`flow` из Задачи 2 плана softdoc расширяется полем `tree` либо отдельный
   `entity_type decision-tree`) со своей JSON Schema 2020-12:
   `nodes[{id, type: question|action|terminal|subflow, prompt?, actor?}]`,
   `edges[{from, when?, to, priority}]`,
   **`props` на развилке**: `{mode: ask-user|auto, default_branch?, timeout?, …}`
   — `additionalProperties: true` (произвольные свойства без правки стандарта).
   Валидация движком **сегодня** (`record.schema_violation` уже работает), рёбра
   `belongs_to` связывают дерево с правилами; семантика порядка рёбер —
   DMN-совместимая `FIRST/PRIORITY` (зафиксировать в schema-описании).
   Mermaid-проекция генерируется из записи (диаграмма остаётся производной —
   «не отдельная истина» сохраняется).
2. **CLI-навигация в перспективе** — отдельная подкоманда вида
   `docs flow walk --id flow:order-placement --at node:X` (ответ: вопрос/ветки/
   свойства развилки, путь до терминала) и `--render mermaid` — проекция в
   терминал/файл. Данные уже читаются существующими `records read/list` до её
   появления.
3. **Интероп-мосты по потребности:** исполняемый rule-движок → экспорт в DMN
   (таблица → таблица, hit policy `PRIORITY`); исполнение в облаке → экспорт
   Choice-фрагмента в ASL; диалоговый рантайм → Rasa flows. Экспорты — генерация
   из нативной записи, не ручной дубль (принцип «связки, не копии», D8 softdoc).

## 5. Источники (25.11–26.11.2026)

| Тема | Источник |
|---|---|
| DMN 1.5: hit policies U/A/P/F/C, FEEL, дефолтные выходы | https://www.omg.org/spec/DMN/1.5/Beta1/PDF |
| DMN: объяснение hit policy и таблиц | https://www.capitalone.com/tech/software-engineering/decision-model-and-notation/ |
| ASL: Choice state, Choices/Default/Assign | https://states-language.net/ |
| ASL: экзаменационный обзор state types | https://sailor.sh/blog/aws-developer-associate-step-functions-state-machines-asl-error-handling/ |
| XState v6: `meta`/`schemas` на state node | https://stately.ai/docs/xstate/v6/configuration |
| Спайк XState-формата: meta в бою, 2500 строк JSON vs 600 YAML | https://github.com/codeforamerica/safety-net-blueprint/issues/475 |
| BPMN 2.0: userTask/serviceTask, exclusiveGateway, default | https://www.omg.org/spec/BPMN/2.0/PDF/ |
| BPMN на практике: исполняемость, человек vs система | https://www.dokuflex.com/en/resources/bpmn-guide.html |
| Rasa CALM: YAML flows, collect/action, валидация | https://rasa.com/blog/what-our-own-rasa-skill-md-taught-me |
| Rasa CALM: архитектура флоу | https://ai.miraheze.org/wiki/RASA |
| CNCF Serverless Workflow: YAML/JSON + JSON Schema + metadata | https://github.com/open-workflow-specification/specification/blob/0.5.x/specification.md |
| SWS: YAML для LLM, switch-состояния | https://medium.com/@dixon.deng/rethinking-workflows-when-ai-needs-a-backbone-0d5764c10a24 |
