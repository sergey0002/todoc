# tests/unit/test_status_validation.py — план «скилы-взаимодействия» З1:
# закрытые наборы статусов (allowed_statuses в doc_type) + валидация статуса.
# md-документ: docs.status_not_allowed; JSON-запись: enum схемы → record.schema_violation.
import json

from todoc.adapters.filesystem.scanner import scan_dataset
from todoc.application.validator import validate_dataset
from todoc.config import load_dataset, load_rules
from todoc.typing_system.descriptors import TypeRegistry

IDEA_STATUSES = ["captured", "planned", "in_progress", "done", "rejected", "superseded"]


def _validate(root):
    dataset = load_dataset(root)
    dir_rules, doc_rules = load_rules(root, dataset)
    registry = TypeRegistry()
    registry.load(root, dataset)
    _folders, files = scan_dataset(root)
    return validate_dataset(root, dataset, files, dir_rules, doc_rules, registry=registry)


def _write_idea_type(root: object, allowed: list[str] | None) -> None:
    d = root / ".todoc" / "doc_types" / "idea"
    d.mkdir(parents=True, exist_ok=True)
    descriptor = {"schema_version": 1, "type_id": "idea", "version": "0.1", "kind": "doc_type",
                  "description": "Идея.", "format": "markdown"}
    if allowed is not None:
        descriptor["allowed_statuses"] = allowed
    (d / "type.json").write_text(json.dumps(descriptor, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_idea_doc(root, status: str | None) -> None:
    fm = '---\nid: doc:idea-x\ntitle: "Идея"\ndoc_type: idea\nlang: ru\n'
    if status is not None:
        fm += f"status: {status}\n"
    fm += "---\n\n# Идея\n\nТекст.\n"
    path = root / "ideas" / "x.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fm, encoding="utf-8")


def test_status_outside_set_is_diagnostic(root):
    _write_idea_type(root, IDEA_STATUSES)
    _write_idea_doc(root, "acitve")  # опечатка — вне набора
    diags, _info = _validate(root)
    bad = [d for d in diags if d.code == "docs.status_not_allowed"]
    assert len(bad) == 1
    assert "acitve" in bad[0].message and "captured" in bad[0].evidence


def test_status_inside_set_is_clean(root):
    _write_idea_type(root, IDEA_STATUSES)
    _write_idea_doc(root, "captured")
    diags, _info = _validate(root)
    assert [d for d in diags if d.code == "docs.status_not_allowed"] == []


def test_doc_without_status_is_valid(root):
    _write_idea_type(root, IDEA_STATUSES)
    _write_idea_doc(root, None)
    diags, _info = _validate(root)
    assert [d for d in diags if d.code == "docs.status_not_allowed"] == []


def test_type_without_allowed_statuses_keeps_status_free(root):
    _write_idea_type(root, None)
    _write_idea_doc(root, "что-угодно")  # набор не объявлен — статус свободный
    diags, _info = _validate(root)
    assert [d for d in diags if d.code == "docs.status_not_allowed"] == []


def test_status_check_is_markdown_only(root):
    # JSON-файл (не запись) с doc_type из правила и чужим статусом — не md-документ,
    # проверка статуса его не касается (для записей правит enum схемы).
    _write_idea_type(root, IDEA_STATUSES)
    d = root / "ideas"
    d.mkdir(parents=True, exist_ok=True)
    (d / "x.json").write_text(json.dumps({"note": "не документ", "status": "acitve"},
                                         ensure_ascii=False) + "\n", encoding="utf-8")
    diags, _info = _validate(root)
    assert [d for d in diags if d.code == "docs.status_not_allowed"] == []


def test_task_enum_rejects_unknown_status(root):
    # JSON-запись: enum статуса покрывает существующая JSON Schema-проверка
    # (record.schema_violation) — отдельная ветка валидатору не нужна.
    d = root / ".todoc" / "entity_types" / "task"
    d.mkdir(parents=True, exist_ok=True)
    (d / "type.json").write_text(json.dumps(
        {"schema_version": 1, "type_id": "task", "version": "0.1", "kind": "entity_type",
         "description": "Задача.", "format": "json", "schema": "schema.json",
         "path_template": "tasks/{slug}.json",
         "required_fields": ["record_id", "entity_type", "title", "status"]},
        ensure_ascii=False) + "\n", encoding="utf-8")
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
              "required": ["schema_version", "record_id", "entity_type", "title", "status"],
              "properties": {"schema_version": {"const": 1},
                             "record_id": {"type": "string", "pattern": "^task:[a-z0-9][a-z0-9-]*$"},
                             "entity_type": {"const": "task"}, "title": {"type": "string"},
                             "status": {"enum": ["open", "in_progress", "done", "cancelled"]}}}
    (d / "schema.json").write_text(json.dumps(schema, ensure_ascii=False) + "\n", encoding="utf-8")
    rec = root / "tasks" / "t.json"
    rec.parent.mkdir(parents=True, exist_ok=True)
    rec.write_text(json.dumps({"schema_version": 1, "record_id": "task:demo-1",
                               "entity_type": "task", "title": "Дело", "status": "blah"},
                              ensure_ascii=False) + "\n", encoding="utf-8")
    diags, _info = _validate(root)
    bad = [d for d in diags if d.code == "record.schema_violation"]
    assert any(d.location.get("pointer") == "/status" for d in bad), bad


def test_allowed_statuses_bad_shape_is_config_diagnostic(root):
    # shape-валидация дескриптора: не-список / пустой / не-строки → config.invalid_schema
    import json as _json
    from todoc.typing_system.descriptors import descriptor_diagnostics
    descriptor = {"schema_version": 1, "type_id": "idea", "version": "0.1", "kind": "doc_type",
                  "description": "Идея.", "allowed_statuses": "captured"}
    diags = descriptor_diagnostics(root, {"dataset_id": "d"}, "doc_type", descriptor, "x/type.json")
    assert any(d["code"] == "config.invalid_schema" and "allowed_statuses" in d["message"] for d in diags)
    for bad in ([], ["captured", ""], [1, 2]):
        descriptor["allowed_statuses"] = bad
        diags = descriptor_diagnostics(root, {"dataset_id": "d"}, "doc_type", descriptor, "x/type.json")
        assert any(d["code"] == "config.invalid_schema" for d in diags), bad
    descriptor["allowed_statuses"] = ["captured", "planned"]
    diags = descriptor_diagnostics(root, {"dataset_id": "d"}, "doc_type", descriptor, "x/type.json")
    assert not any(d["code"] == "config.invalid_schema" for d in diags)
