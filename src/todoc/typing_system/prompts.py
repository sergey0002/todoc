"""Starter templates and CRUD prompts shipped inside a type folder.

Every type may carry its own operating manual next to ``type.json``::

    .todoc/doc_types/<id>/type.json
    .todoc/doc_types/<id>/template.md          # starter document, with fill-in notes
    .todoc/doc_types/<id>/prompts/read.md      # how to read documents of this type
    .todoc/doc_types/<id>/prompts/create.md    # how to create one
    .todoc/doc_types/<id>/prompts/edit.md      # how to edit one (review-first)
    .todoc/doc_types/<id>/prompts/delete.md    # how to retire one safely

The four prompts mirror CRUD so an agent always gets the instruction that matches
the operation it is about to perform, instead of one generic block it has to
re-interpret per task.
"""

from __future__ import annotations

import json
from typing import Any

#: Placeholders a starter template may use (see ``descriptors.render_template``).
PLACEHOLDER_HELP = (
    "{title} — заголовок, {slug} — имя файла, {date} — дата UTC, "
    "{type_id} — тип, {id} — идентификатор документа, {format} — формат"
)


def _sections_block(descriptor: dict[str, Any]) -> str:
    required = descriptor.get("required_sections") or []
    rules = descriptor.get("section_rules") or []
    lines: list[str] = []
    if required:
        lines.append("Обязательные разделы: " + ", ".join(f"`{item}`" for item in required) + ".")
    for rule in rules:
        heading = rule.get("heading", "")
        lines.append(
            f"У каждого заголовка `{heading}` должно быть не меньше "
            f"{rule.get('min_children', 1)} подраздел(ов) уровня {rule.get('child_level', 'следующего')}."
        )
    return "\n".join(lines)


def _fields_block(descriptor: dict[str, Any]) -> str:
    required = descriptor.get("required_fields") or []
    if not required:
        return ""
    return "Обязательные поля: " + ", ".join(f"`{item}`" for item in required) + "."


def read_prompt(type_id: str, kind: str, description: str, descriptor: dict[str, Any]) -> str:
    """`prompts/read.md` — how to read one item of this type."""
    if kind == "doc_type":
        structure = _sections_block(descriptor)
        return f"""# Чтение: `{type_id}`

{description}

## Что делать

1. Найти документ: `todoc docs search --query "<суть>" --within <папка> --limit 3`.
2. Прочитать нужный раздел, а не весь файл:
   `todoc docs read --id doc:<путь> --section "<заголовок>"`.
3. Проверить происхождение: в ответе есть `hash`, `line_start`, `line_end` и
   `heading_path` — цитируйте по ним, не пересказывая по памяти.

## На что смотреть в первую очередь

- Заголовок и вводный абзац — о чём документ.
- Разделы по структуре типа: {structure or "структура не задана"}.
- Ссылки на другие документы: они проверены валидатором, битая ссылка — диагностика.

## Чего не делать

- Не читать файл целиком, если нужен один раздел: это дороже и шумнее.
- Не делать выводов по `docs tree` без `--within`: на большом корпусе он большой.
"""
    fields = _fields_block(descriptor)
    path_template = descriptor.get("path_template") or f"records/{type_id}/{{slug}}.json"
    return f"""# Чтение: `{type_id}`

{description}

## Что делать

1. Найти запись: `todoc records list --type {type_id} --limit 20`.
2. Прочитать: `todoc records read --id <record_id> --view summary`
   (или `--view full`, когда нужны все поля).
3. Посмотреть связи: `todoc relations graph --id <record_id>`.

## На что смотреть в первую очередь

- {fields or "Обязательные поля не заданы."}
- `relations` — на что запись ссылается; цели проверены валидатором.
- Путь записи определяется шаблоном `{path_template}`.

## Чего не делать

- Не угадывать `record_id`: сначала `records list`.
- Не менять запись вслепую без чтения текущих полей и связей (`records read`).
"""


def create_prompt(type_id: str, kind: str, description: str, descriptor: dict[str, Any]) -> str:
    """`prompts/create.md` — how to create one item of this type."""
    if kind == "doc_type":
        structure = _sections_block(descriptor)
        template = descriptor.get("template") or "template.md"
        return f"""# Создание: `{type_id}`

{description}

## Как создавать

1. Взять стартовый шаблон: он лежит в `.todoc/doc_types/{type_id}/{template}`.
2. Создать каркас документа одной командой (create-only, без перезаписи):
   `todoc docs new --type {type_id} --title "<Заголовок>" --path <папка>/<english-slug>.md`.
   Шаблоны подставляются как текст: {PLACEHOLDER_HELP}.
3. Наполнить разделы напрямую штатным редактором файлов, убрать подсказки в `<!-- ... -->`
   (не редактируя поля `created` и `updated` во front matter).
4. Завершить правку короткой командой `todoc sync --root KB <путь>` — она обновит индекс,
   историю и проверит валидность (`ok: true`, `diagnostics: []`).

## Структура, которую проверит валидатор

{structure or "Структурные правила для типа не заданы."}

## После создания

- `todoc sync --root KB <путь>` (или `todoc validate --all`) — должно быть 0 диагностик.
- Если шаблон нарушает структуру типа, `docs new` откажет с `types.template_invalid`
  и ничего не запишет: чините шаблон, а не обходите проверку.

## Чего не делать

- Не создавать файл руками в обход `docs new`: потеряете шаблон и стартовые метаданные.
- Не оставлять подсказки `<!-- ... -->` в готовом документе и не править руками `created`/`updated`.
"""
    fields = _fields_block(descriptor)
    path_template = descriptor.get("path_template") or f"records/{type_id}/{{slug}}.json"
    return f"""# Создание: `{type_id}`

{description}

## Как создавать

1. Взять стартовый шаблон: `.todoc/entity_types/{type_id}/template.json`.
2. Подготовить входной файл и создать запись (create-only):
   `todoc records create --type {type_id} --input-file <file.json> --preview`,
   затем то же с `--apply`.
3. Путь файла определит тип: `{path_template}`. Дальнейшие точечные правки созданного
   JSON-файла можно делать напрямую в файле с последующим `todoc sync --root KB <путь>`.

## Обязательные поля

{fields or f"Обязательные поля не заданы — сверьтесь со схемой `.todoc/entity_types/{type_id}/schema.json`."}

## После создания

- `todoc validate --all` — 0 диагностик.
- Отношения указывайте существующими `record_id`: иначе будет `relation.dangling_target`.

## Чего не делать

- Не рассчитывать на перезапись при `records create`: существующий `record_id` даёт `record.duplicate_id` и exit 5.
"""


def edit_prompt(type_id: str, kind: str, description: str, descriptor: dict[str, Any]) -> str:
    """`prompts/edit.md` — how to change one item directly and finalize with `todoc sync`."""
    if kind == "doc_type":
        structure = _sections_block(descriptor)
        return f"""# Правка: `{type_id}`

{description}

## Как править

1. Прочитать целевой раздел через `todoc docs read --id doc:<путь> --section "<заголовок>"`
   (если нужна сверка конкурентных правок — запомнить `hash`).
2. Внести изменения напрямую в файл штатным редактором (не трогая поля `created` и `updated`
   во front matter).
3. Сразу после прямой правки выполнить короткую команду финализации:
   `todoc sync --root KB <путь>` (при необходимости с `--if-hash <hash>`), убедившись,
   что `ok: true` и `diagnostics: []`.

## Что нельзя ломать

{structure or "Структурные правила для типа не заданы."}

- Заголовки, по которым документ ищется: меняя заголовок, меняйте и ссылки на него.
- Ссылки на другие документы: `todoc sync` проверит целостность и обновит `updated` и историю.

## Чего не делать

- Не забывать вызывать `todoc sync --root KB <путь>` после прямой правки файла.
- Не править вручную автособираемые витрины (`"generated": true`) — правьте их запись-источник.
"""
    fields = _fields_block(descriptor)
    return f"""# Правка: `{type_id}`

{description}

## Как править

1. `todoc records read --id <record_id> --view full` — прочитать текущее содержимое, схему и путь файла.
2. Отредактировать JSON-файл записи напрямую штатным редактором, сохранив `record_id` и `entity_type`.
3. Сразу после прямой правки выполнить короткую команду финализации:
   `todoc sync --root KB <путь-к-файлу.json>` — она обновит историю, индекс и проверит JSON Schema и связи.

## Что нельзя ломать

- {fields or "Обязательные поля не заданы."}
- `record_id`: на него ссылаются отношения других записей.
- Единицы измерений в числовых полях: смешение единиц ломает `records aggregate`.

## После правки

- `todoc sync --root KB <путь>` — `ok: true`, `diagnostics: []`.
- `todoc relations graph --id <record_id>` — связи не оборвались.
"""


def delete_prompt(type_id: str, kind: str, description: str, descriptor: dict[str, Any]) -> str:
    """`prompts/delete.md` — how to retire one item without breaking references."""
    subject = "документ" if kind == "doc_type" else "запись"
    lookup = (f"`todoc docs search --query \"<заголовок>\" --limit 5`"
              if kind == "doc_type" else "`todoc records list --type " + type_id + "`")
    graph = ("`todoc validate --all` — битые ссылки станут `markdown.link.target_missing`"
             if kind == "doc_type" else "`todoc relations graph --id <record_id>`")
    return f"""# Удаление: `{type_id}`

{description}

## Порядок действий

1. Найти {subject}: {lookup}.
2. Оценить последствия: {graph}.
3. Если на {subject} кто-то ссылается — сначала убрать или перевести ссылки,
   и только потом удалять файл.
4. Удаление делает оператор (или агент по явной команде): `todoc` сам файлы не удаляет.

## Вместо удаления

- Устарело — пометьте статусом и добавьте связь `supersedes` на замену.
- Переехало — обновите ссылки и оставьте короткую заглушку-указатель.

## После удаления

- `todoc validate --all` — не появилось `markdown.link.target_missing`
  или `relation.dangling_target`.
- `todoc index rebuild` — индекс пересобран, счётчики сошлись.

## Чего не делать

- Не удалять {subject}, не проверив входящие ссылки.
- Не удалять файл, чтобы «пересоздать заново»: история и хеши теряются.
"""


def build_prompts(type_id: str, kind: str, description: str,
                  descriptor: dict[str, Any]) -> dict[str, str]:
    """All four CRUD prompt texts for one type, keyed by operation."""
    return {
        "read": read_prompt(type_id, kind, description, descriptor),
        "create": create_prompt(type_id, kind, description, descriptor),
        "edit": edit_prompt(type_id, kind, description, descriptor),
        "delete": delete_prompt(type_id, kind, description, descriptor),
    }


def build_template(type_id: str, kind: str, description: str, descriptor: dict[str, Any]) -> str:
    """Starter file for a type: required sections present, fill-in notes inline.

    The result must satisfy the type's own structure rules, otherwise ``docs new``
    would refuse to create a document from the template its type ships.
    """
    from todoc.typing_system.descriptors import parse_heading_selector

    if kind == "doc_type":
        lines = ["# {title}", "", f"- Тип: `{type_id}`", "- Создан: {date}", "- Идентификатор: `{id}`", ""]
        selectors = list(descriptor.get("required_sections") or [])
        if not selectors:
            lines += ["## Суть", "", "<!-- ЗАПОЛНИ: одна-две фразы, о чём документ. -->", ""]
        for selector in selectors:
            level, title = parse_heading_selector(selector)
            lines += ["#" * (level or 2) + " " + title, "",
                      f"<!-- ЗАПОЛНИ: содержимое раздела «{title}». Подсказки в комментариях удалить. -->", ""]
        for rule in descriptor.get("section_rules") or []:
            selector = str(rule.get("heading", ""))
            level, title = parse_heading_selector(selector)
            child_level = rule.get("child_level") or (level + 1 if level else 3)
            example = title.rstrip(":") + ": <название>"
            lines += ["#" * (level or 3) + " " + example, "",
                      "<!-- ЗАПОЛНИ: нормативная формулировка (SHALL/MUST). -->", ""]
            for index in range(int(rule.get("min_children", 1))):
                suffix = "" if int(rule.get("min_children", 1)) == 1 else f" {index + 1}"
                lines += ["#" * int(child_level) + f" Scenario{suffix}: <имя сценария>", "",
                          "- **WHEN** <условие>", "- **THEN** <ожидаемый результат>", ""]
        return "\n".join(lines).rstrip() + "\n"

    required = list(descriptor.get("required_fields") or ["record_id", "entity_type"])
    record: dict[str, Any] = {"schema_version": 1}
    for field in required:
        if field == "record_id":
            record[field] = f"{type_id}:<slug>"
        elif field == "entity_type":
            record[field] = type_id
        else:
            record[field] = f"<{field}>"
    record["relations"] = []
    return json.dumps(record, indent=2, ensure_ascii=False) + "\n"
