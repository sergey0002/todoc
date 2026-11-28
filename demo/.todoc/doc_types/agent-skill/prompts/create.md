# Создание: `agent-skill`

Скил агента по стандарту Agent Skills: папка `skill/<имя>/SKILL.md`, front matter
`name` (= имени папки, lowercase-дефисы, ≤64) + `description` ≤1024 «что + когда»
с ключевыми словами поиска; тело < 5000 токенов. Скил — процесс над типовыми
промптами (`todoc types prompt`), не копия инструкций.

## Как создавать

1. Дедуп: `todoc docs search --root KB --query "<тема>"` — нет ли скила на эту работу.
2. Создать папку и файл:

   ```bash
   mkdir -p KB/skill/<имя-скила>
   # SKILL.md по шаблону .todoc/doc_types/agent-skill/template.md
   todoc validate --root KB --all   # 0 диагностик
   ```

3. `name` во front matter = имени папки (фм-правило `fm-agent-skill` назначает тип).

## Правила качества

- `description` — «что делает + когда применять», с ключевыми словами, по которым
  скил найдёт `docs search`.
- Шаги с точными CLI-командами; ссылки на `todoc types prompt <T> --op create`,
  не копии промптов.
- Стоп-условия: «данных нет — уточни, не выдумывай»; progressive disclosure —
  подробности в references/, не в теле.

## Запрещённые заглушки

- Скил без работающего шага-команды; описание без «когда применять».

## Самопроверка

- `todoc docs search --root KB --query "<слова из description>"` находит скил.
- `todoc explain-path --root KB skill/<имя>/SKILL.md` — `doc_type: agent-skill`.

> **Метаданные:** `created` и `updated` во front matter ставит движок (`docs new`) — руками не заполнять. Заполни `tags` (2–8 kebab-тегов: папка + тип + тематические) и, если есть явные связи, `related`-wikilinks (`[[имя-без-.md]]`).
