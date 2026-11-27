"""Type assets: starter templates, CRUD prompts, structure rules, config strictness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from todoc.adapters.formats.markdown import parse_markdown
from todoc.application.validator import (_check_structure, _entity_types_of, _load_schemas,
                                         _normalize_heading, validate_dataset)
from todoc.application.write import create_document_plan, structure_violations
from todoc.config import (DEFAULT_DOC_TYPES, DEFAULT_ENTITY_TYPES, _write_type_assets,
                          init_dataset, load_dataset, load_rules)
from todoc.errors import ConflictError, ValidationError
from todoc.typing_system.descriptors import (
    KIND_FIELDS,
    METRIC_FIELD_KEYS,
    TypeRegistry,
    load_json_file,
    PROMPT_OPERATIONS,
    descriptor_diagnostics,
    schema_file,
    parse_heading_selector,
    prompt_files,
    render_template,
    template_file,
    type_dir,
    type_kind_dir,
)
from todoc.typing_system.prompts import build_prompts, build_template

DATASET = {"dataset_id": "ds"}
SPEC = {
    "schema_version": 1, "type_id": "spec", "version": "0.1", "kind": "doc_type",
    "description": "Спецификация.", "format": "markdown", "template": "template.md",
    "required_sections": ["## Purpose", "## Requirements"],
    "section_rules": [{"heading": "### Requirement:", "min_children": 1, "child_level": 4}],
}


# ---------------------------------------------------------------------------
# selectors and paths
# ---------------------------------------------------------------------------

def test_parse_heading_selector_forms():
    assert parse_heading_selector("## Purpose") == (2, "Purpose")
    assert parse_heading_selector("Purpose") == (None, "Purpose")
    assert parse_heading_selector("### Requirement:") == (3, "Requirement:")
    assert parse_heading_selector("#  Spaced  ") == (1, "Spaced")


@pytest.mark.parametrize("kind,expected", (("dir_type", "dir_types"), ("doc_type", "doc_types"),
                                           ("entity_type", "entity_types"),
                                           ("relation_type", "relation_types")))
def test_type_kind_dir_defaults(kind, expected):
    assert type_kind_dir(DATASET, kind) == expected


def test_type_kind_dir_honours_dataset_override():
    assert type_kind_dir({"document_types": "docs"}, "doc_type") == "docs"


def test_type_dir_is_the_type_folder(tmp_path):
    assert type_dir(tmp_path, DATASET, "doc_type", "spec") == tmp_path / ".todoc" / "doc_types" / "spec"


def test_template_file_undeclared_and_malformed(tmp_path):
    assert template_file(tmp_path, DATASET, "doc_type", {"type_id": "spec"}) is None
    assert template_file(tmp_path, DATASET, "doc_type", {"type_id": "spec", "template": ""}) is None
    assert template_file(tmp_path, DATASET, "doc_type", {"type_id": "spec", "template": 7}) is None


def test_template_file_relative_and_absolute(tmp_path):
    relative = template_file(tmp_path, DATASET, "doc_type", SPEC)
    assert relative == tmp_path / ".todoc" / "doc_types" / "spec" / "template.md"
    absolute = template_file(tmp_path, DATASET, "doc_type", {"type_id": "spec", "template": "/abs/t.md"})
    assert absolute == Path("/abs/t.md")


def test_prompt_files_defaults_to_prompts_dir(tmp_path):
    paths = prompt_files(tmp_path, DATASET, "doc_type", {"type_id": "spec"})
    assert set(paths) == set(PROMPT_OPERATIONS)
    assert paths["read"] == tmp_path / ".todoc" / "doc_types" / "spec" / "prompts" / "read.md"


def test_prompt_files_declared_paths(tmp_path):
    descriptor = {"type_id": "spec", "prompts": {"read": "p/r.md", "create": "/abs/c.md", "edit": 5}}
    paths = prompt_files(tmp_path, DATASET, "doc_type", descriptor)
    assert paths["read"] == tmp_path / ".todoc" / "doc_types" / "spec" / "p" / "r.md"
    assert paths["create"] == Path("/abs/c.md")
    # a non-string declaration is ignored: the default path stays
    assert paths["edit"].name == "edit.md"
    assert paths["delete"].name == "delete.md"


def test_render_template_leaves_unknown_placeholders():
    out = render_template("# {title} | {date} | {nope}", {"title": "T", "date": "2026-11-25"})
    assert out == "# T | 2026-11-25 | {nope}"


# ---------------------------------------------------------------------------
# config strictness
# ---------------------------------------------------------------------------

def test_clean_descriptor_has_no_diagnostics(tmp_path):
    (tmp_path / ".todoc" / "doc_types" / "spec").mkdir(parents=True)
    (tmp_path / ".todoc" / "doc_types" / "spec" / "template.md").write_text("# {title}\n", encoding="utf-8")
    assert descriptor_diagnostics(tmp_path, DATASET, "doc_type", SPEC, ".todoc/doc_types/spec/type.json") == []


def test_unknown_field_is_reported_not_ignored(tmp_path):
    descriptor = dict(SPEC, required_headings=["Purpose"])
    found = descriptor_diagnostics(tmp_path, DATASET, "doc_type", descriptor, "c.json")
    unknown = [item for item in found if item["code"] == "config.unknown_field"]
    assert len(unknown) == 1
    assert "required_headings" in unknown[0]["message"]


def test_every_kind_has_an_allowlist():
    assert set(KIND_FIELDS) == {"dir_type", "doc_type", "entity_type", "relation_type"}
    assert "required_sections" in KIND_FIELDS["doc_type"]
    assert "required_sections" not in KIND_FIELDS["relation_type"]


def test_malformed_template_and_prompts_declarations(tmp_path):
    descriptor = {"type_id": "spec", "kind": "doc_type", "template": 7, "prompts": "read.md"}
    codes = [item["code"] for item in descriptor_diagnostics(tmp_path, DATASET, "doc_type", descriptor, "c.json")]
    assert codes == ["config.invalid_schema", "config.invalid_schema"]


def test_unknown_prompt_operation_and_bad_value(tmp_path):
    descriptor = {"type_id": "spec", "kind": "doc_type",
                  "prompts": {"review": "p/review.md", "read": ""}}
    found = descriptor_diagnostics(tmp_path, DATASET, "doc_type", descriptor, "c.json")
    messages = " ".join(item["message"] for item in found)
    assert "review" in messages and "read" in messages
    assert {"config.unknown_field", "config.invalid_schema"} <= {item["code"] for item in found}


def test_bad_required_sections_and_section_rules(tmp_path):
    descriptor = {"type_id": "spec", "kind": "doc_type", "required_sections": "Purpose",
                  "section_rules": {"heading": "## A"}}
    codes = [item["code"] for item in descriptor_diagnostics(tmp_path, DATASET, "doc_type", descriptor, "c.json")]
    assert codes == ["config.invalid_schema", "config.invalid_schema"]


def test_section_rule_field_checks(tmp_path):
    descriptor = {"type_id": "spec", "kind": "doc_type", "section_rules": [
        {"no_heading": True},
        {"heading": "## A", "weird": 1, "min_children": "2", "child_level": 1.5, "severity": "fatal"},
        "not-a-dict",
    ]}
    found = descriptor_diagnostics(tmp_path, DATASET, "doc_type", descriptor, "c.json")
    messages = " ".join(item["message"] for item in found)
    assert "needs a non-empty 'heading'" in messages
    assert "unknown field 'weird'" in messages
    assert "min_children must be an integer" in messages
    assert "child_level must be an integer" in messages
    assert "severity must be" in messages
    assert sum(1 for item in found if item["message"].startswith("section_rules[2]")) == 1


def test_declared_but_missing_template_and_prompt(tmp_path):
    descriptor = {"type_id": "spec", "kind": "doc_type", "template": "gone.md",
                  "prompts": {"read": "prompts/read.md"}}
    codes = sorted(item["code"] for item in descriptor_diagnostics(tmp_path, DATASET, "doc_type", descriptor, "c.json"))
    assert codes == ["config.prompt_missing", "config.template_missing"]


def test_undeclared_missing_prompt_is_not_an_error(tmp_path):
    """Only explicitly declared prompts must exist; defaults are optional."""
    descriptor = {"type_id": "spec", "kind": "doc_type"}
    assert descriptor_diagnostics(tmp_path, DATASET, "doc_type", descriptor, "c.json") == []


# ---------------------------------------------------------------------------
# structure validation
# ---------------------------------------------------------------------------

def test_normalize_heading_ignores_inline_markup():
    assert _normalize_heading("Пробел относительно `todoc`") == "Пробел относительно todoc"
    assert _normalize_heading("A **bold**  spaced") == "A bold spaced"


def _diags(text, descriptor):
    return _check_structure("ds", "a.md", parse_markdown(text).headings, descriptor)


def test_required_section_present_and_missing():
    ok = "# T\n\n## Purpose\n\nx\n\n## Requirements\n\ny\n"
    assert _diags(ok, SPEC) == []
    bad = "# T\n\n## Purpose\n\nx\n"
    found = _diags(bad, SPEC)
    assert [d.code for d in found] == ["markdown.section.missing"]
    assert found[0].location == {"line": 1, "column": 1}
    assert found[0].suggested_fixes[0].kind == "add_heading"
    assert found[0].suggested_fixes[0].autofixable is False


def test_required_section_without_level_matches_any_level():
    descriptor = {"type_id": "spec", "required_sections": ["Purpose"]}
    assert _diags("# T\n\n### Purpose\n\nx\n", descriptor) == []
    assert len(_diags("# T\n\n## Other\n\nx\n", descriptor)) == 1


def test_selector_matches_heading_with_inline_markup():
    descriptor = {"type_id": "c", "required_sections": ["## Пробел относительно `todoc`"]}
    assert _diags("# X\n\n## Пробел относительно todoc\n\ny\n", descriptor) == []


def test_section_rule_requires_children():
    rule_only = {"type_id": "spec", "section_rules": SPEC["section_rules"]}
    good = ("# T\n\n## Requirements\n\n### Requirement: A\n\nSHALL x\n\n"
            "#### Scenario: s\n\n- **WHEN** a\n- **THEN** b\n")
    assert _diags(good, rule_only) == []
    bad = "# T\n\n## Requirements\n\n### Requirement: A\n\nSHALL x\n"
    found = _diags(bad, rule_only)
    assert [d.code for d in found] == ["markdown.section.empty"]
    assert found[0].location == {"line": 5, "column": 1}
    assert "level-4" in found[0].message


def test_section_rule_default_child_level_and_severity():
    descriptor = {"type_id": "s", "section_rules": [
        {"heading": "## Group", "min_children": 2, "severity": "warning"}]}
    text = "# T\n\n## Group\n\n### one\n\nx\n"
    found = _diags(text, descriptor)
    assert found[0].severity == "warning"
    assert "level-3" in found[0].message
    assert _diags("# T\n\n## Group\n\n### one\n\n### two\n", descriptor) == []


def test_required_sections_skips_non_string_and_blank_entries():
    descriptor = {"type_id": "s", "required_sections": [7, "   ", "## Purpose"]}
    assert _diags("# T\n\n## Purpose\n\nx\n", descriptor) == []
    assert len(_diags("# T\n", descriptor)) == 1


def test_section_rule_skips_non_dict_and_blank_heading():
    descriptor = {"type_id": "s", "section_rules": ["x", {"heading": "  "}]}
    assert _diags("# T\n", descriptor) == []


def test_validate_dataset_accepts_registry_as_dict(root, sample_md):
    from todoc.adapters.filesystem.scanner import scan_dataset

    _folders, files = scan_dataset(root)
    registry = {"doc_types": {"unknown": {"required_sections": ["## Нечто"]}}}
    diags, _info = validate_dataset(root, {"dataset_id": "ds", "rules": []}, files, [], [], registry=registry)
    assert any(d.code == "markdown.section.missing" for d in diags)


def test_validate_dataset_without_registry_skips_structure(root, sample_md):
    from todoc.adapters.filesystem.scanner import scan_dataset

    _folders, files = scan_dataset(root)
    diags, _info = validate_dataset(root, {"dataset_id": "ds"}, files, [], [])
    assert not any(d.code.startswith("markdown.section") for d in diags)


# ---------------------------------------------------------------------------
# templates and prompts
# ---------------------------------------------------------------------------

def test_build_template_satisfies_its_own_structure_rules():
    text = build_template("spec", "doc_type", "Спецификация.", SPEC)
    assert structure_violations(text, SPEC) == []
    assert "## Purpose" in text and "#### Scenario" in text and "{title}" in text


def test_build_template_without_sections_uses_generic_skeleton():
    text = build_template("note", "doc_type", "Заметка.", {"type_id": "note", "kind": "doc_type"})
    assert "## Суть" in text
    assert "ЗАПОЛНИ" in text


def test_build_template_entity_is_valid_json_with_required_fields():
    descriptor = {"type_id": "metric", "kind": "entity_type",
                  "required_fields": ["record_id", "entity_type", "aspect"]}
    value = json.loads(build_template("metric", "entity_type", "Метрика.", descriptor))
    assert value["record_id"] == "metric:<slug>"
    assert value["entity_type"] == "metric"
    assert value["aspect"] == "<aspect>"
    assert value["relations"] == []


def test_build_prompts_covers_four_operations_for_both_kinds():
    for kind, descriptor in (("doc_type", SPEC),
                             ("entity_type", {"type_id": "note", "kind": "entity_type",
                                              "required_fields": ["record_id", "title"]})):
        prompts = build_prompts("note" if kind == "entity_type" else "spec", kind, "Описание.", descriptor)
        assert set(prompts) == set(PROMPT_OPERATIONS)
        for operation, text in prompts.items():
            assert text.startswith("# "), operation
            assert len(text) > 200, operation
    assert "docs read" in build_prompts("spec", "doc_type", "d", SPEC)["read"]
    assert "records create" in build_prompts("note", "entity_type", "d", {"type_id": "note"})["create"]
    assert "todoc sync" in build_prompts("spec", "doc_type", "d", SPEC)["edit"]
    assert "records read" in build_prompts("note", "entity_type", "d", {"type_id": "note"})["edit"]
    assert "supersedes" in build_prompts("spec", "doc_type", "d", SPEC)["delete"]


def test_build_prompts_uses_direct_edit_and_todoc_sync():
    doc_create = build_prompts("spec", "doc_type", "d", SPEC)["create"]
    assert "todoc sync" in doc_create

    doc_edit = build_prompts("spec", "doc_type", "d", SPEC)["edit"]
    assert "todoc sync" in doc_edit
    assert "--patch-file" not in doc_edit

    rec_edit = build_prompts("note", "entity_type", "d", {"type_id": "note"})["edit"]
    assert "todoc sync" in rec_edit
    assert "Удалить старый файл" not in rec_edit


def test_sections_block_without_required_sections_lists_rules_only():
    descriptor = {"type_id": "s", "section_rules": [{"heading": "### Requirement:", "min_children": 2}]}
    text = build_prompts("s", "doc_type", "d", descriptor)["create"]
    assert "Обязательные разделы" not in text
    assert "`### Requirement:`" in text and "2 подраздел" in text
    assert "уровня следующего" in text


def test_prompts_mention_declared_structure_and_fields():
    text = build_prompts("spec", "doc_type", "d", SPEC)["create"]
    assert "`## Purpose`" in text and "### Requirement:" in text
    fields = build_prompts("note", "entity_type", "d",
                           {"type_id": "note", "required_fields": ["record_id", "title"]})["create"]
    assert "`title`" in fields


# ---------------------------------------------------------------------------
# document creation plan
# ---------------------------------------------------------------------------

def test_create_document_plan_appends_a_final_newline():
    plan = create_document_plan(DATASET, {"note": {}}, "note", "T", "a/b.md", "# {title}",
                                {"title": "T"})
    # план doc-tags З3: fm-блок сверху, тело с финальным \n
    assert plan.new_content.endswith("\n# T\n")
    assert plan.new_content.startswith("---\n")


def test_create_document_plan_rejects_unknown_type_empty_title_and_bad_path():
    with pytest.raises(ValidationError) as exc:
        create_document_plan(DATASET, {}, "ghost", "T", "a/b.md")
    assert exc.value.code == "types.unknown"
    with pytest.raises(ValidationError) as exc:
        create_document_plan(DATASET, {"note": {}}, "note", "   ", "a/b.md")
    assert exc.value.code == "docs.empty_title"
    for bad in ("../escape.md", "a/../../escape.md", "/abs.md"):
        with pytest.raises(ValidationError) as exc:
            create_document_plan(DATASET, {"note": {}}, "note", "T", bad)
        assert exc.value.code == "docs.unsafe_path"


def test_create_document_plan_refuses_existing_target():
    with pytest.raises(ConflictError) as exc:
        create_document_plan(DATASET, {"note": {}}, "note", "T", "a/b.md",
                             existing_paths={"a/b.md"})
    assert exc.value.code == "docs.target_exists"


def test_create_document_plan_without_type_is_a_bare_title():
    """План doc-tags З3: docs new строит fm-блок сам (created/updated = сегодня)."""
    import re

    plan = create_document_plan(DATASET, {}, None, "Заголовок", "inbox/x.md")
    assert plan.new_content.endswith("# Заголовок\n\n")
    assert plan.new_content.startswith("---\n")
    assert 'title: "Заголовок"' in plan.new_content
    assert "lang: ru" in plan.new_content
    m = re.search(r"^created: (\d{4}-\d{2}-\d{2})$", plan.new_content, re.M)
    n = re.search(r"^updated: (\d{4}-\d{2}-\d{2})$", plan.new_content, re.M)
    assert m and n and m.group(1) == n.group(1)
    assert "doc_type:" not in plan.new_content  # тип не задан — строка опускается
    assert plan.validations == ("template", "none", "no-overwrite")


def test_create_document_plan_renders_template_and_flags_structure():
    plan = create_document_plan(DATASET, {"note": {"required_sections": ["## Суть"]}}, "note", "T",
                                "inbox/x.md", "# {title}\n\n## Суть\n\n{date}\n",
                                {"title": "T", "date": "2026-11-25"})
    assert plan.new_content.endswith("# T\n\n## Суть\n\n2026-11-25\n")
    assert plan.new_content.startswith("---\nid: doc:inbox/x.md\ntitle: \"T\"\ndoc_type: note\nlang: ru\n")
    assert "created: " in plan.new_content and "updated: " in plan.new_content
    assert "structure" in plan.validations


def test_create_document_plan_refuses_template_that_breaks_the_type():
    with pytest.raises(ValidationError) as exc:
        create_document_plan(DATASET, {"spec": SPEC}, "spec", "T", "specs/x.md", "# {title}\n")
    assert exc.value.code == "types.template_invalid"
    assert "Purpose" in str(exc.value)


def test_structure_violations_is_empty_without_rules():
    assert structure_violations("anything", {"type_id": "note"}) == []


# ---------------------------------------------------------------------------
# init_dataset ships the assets
# ---------------------------------------------------------------------------

def test_init_dataset_ships_template_and_four_prompts_per_type(tmp_path):
    data_root = tmp_path / "kb"
    data_root.mkdir()
    init_dataset(data_root)
    for type_id in DEFAULT_DOC_TYPES:
        base = data_root / ".todoc" / "doc_types" / type_id
        assert (base / "template.md").is_file(), type_id
        for operation in PROMPT_OPERATIONS:
            assert (base / "prompts" / f"{operation}.md").is_file(), (type_id, operation)
        descriptor = json.loads((base / "type.json").read_text(encoding="utf-8"))
        assert descriptor["template"] == "template.md"
        assert descriptor["required_sections"] == DEFAULT_DOC_TYPES[type_id]
    for type_id in DEFAULT_ENTITY_TYPES:
        base = data_root / ".todoc" / "entity_types" / type_id
        assert (base / "template.json").is_file(), type_id
        assert json.loads((base / "template.json").read_text(encoding="utf-8"))["entity_type"] == type_id
        descriptor = json.loads((base / "type.json").read_text(encoding="utf-8"))
        assert descriptor["required_fields"] == DEFAULT_ENTITY_TYPES[type_id]
        assert descriptor["path_template"] == f"records/{type_id}/{{slug}}.json"


def test_write_type_assets_is_idempotent(tmp_path):
    base = tmp_path / "spec"
    base.mkdir()
    for _ in range(2):
        _write_type_assets(base, "doc_type", "spec", "Спецификация.", SPEC)
    files = sorted(p.name for p in base.rglob("*") if p.is_file())
    assert files == ["create.md", "delete.md", "edit.md", "read.md", "template.md", "type.json"]


# ---------------------------------------------------------------------------
# Раскладка: всё, что относится к типу, лежит в его папке
# ---------------------------------------------------------------------------

def test_schema_of_a_type_lives_beside_its_descriptor(tmp_path):
    """`entity_types/<id>/schema.json` is the primary home of a record schema."""
    root = tmp_path
    (root / ".todoc" / "entity_types" / "metric").mkdir(parents=True)
    descriptor = {"schema_version": 1, "type_id": "metric", "version": "0.1", "kind": "entity_type"}
    assert schema_file(root, DATASET, "entity_type", descriptor) is None
    (root / ".todoc" / "entity_types" / "metric" / "schema.json").write_text("{}", encoding="utf-8")
    resolved = schema_file(root, DATASET, "entity_type", descriptor)
    assert resolved == root / ".todoc" / "entity_types" / "metric" / "schema.json"
    # Only entity types have a record schema.
    assert schema_file(root, DATASET, "doc_type", descriptor) is None


def test_schema_declaration_may_point_elsewhere_inside_data_root(tmp_path):
    descriptor = {"type_id": "metric", "kind": "entity_type", "schema": "schemas/metric.v2.json"}
    resolved = schema_file(tmp_path, DATASET, "entity_type", descriptor)
    assert resolved == tmp_path / ".todoc" / "entity_types" / "metric" / "schemas" / "metric.v2.json"


def test_a_schema_outside_the_type_folder_is_not_read(tmp_path):
    """The type folder is the only home of a schema: a top-level catalog is dead."""
    descriptor = {"type_id": "metric", "kind": "entity_type"}
    catalog = tmp_path / ".todoc" / "schemas" / "records"
    catalog.mkdir(parents=True)
    (catalog / "metric.json").write_text("{}", encoding="utf-8")
    assert schema_file(tmp_path, DATASET, "entity_type", descriptor) is None
    base = tmp_path / ".todoc" / "entity_types" / "metric"
    base.mkdir(parents=True)
    (base / "schema.json").write_text("{}", encoding="utf-8")
    assert schema_file(tmp_path, DATASET, "entity_type", descriptor) == base / "schema.json"


def test_template_is_resolved_only_inside_the_type_folder(tmp_path):
    """A template lives beside its type.json; a top-level catalog is not consulted."""
    descriptor = {"type_id": "metric", "kind": "entity_type", "template": "template.json"}
    base = tmp_path / ".todoc" / "entity_types" / "metric"
    assert template_file(tmp_path, DATASET, "entity_type", descriptor) == base / "template.json"
    catalog = tmp_path / ".todoc" / "templates" / "records"
    catalog.mkdir(parents=True)
    (catalog / "metric.json").write_text("{}", encoding="utf-8")
    assert template_file(tmp_path, DATASET, "entity_type", descriptor) == base / "template.json"
    assert template_file(tmp_path, DATASET, "entity_type", {"type_id": "x", "kind": "entity_type"}) is None


def test_config_rejects_a_malformed_schema_field(tmp_path):
    descriptor = {"type_id": "metric", "kind": "entity_type", "schema": ""}
    codes = [item["code"] for item in descriptor_diagnostics(tmp_path, DATASET, "entity_type", descriptor, "x")]
    assert "config.invalid_schema" in codes


def test_config_reports_a_schema_declared_twice(tmp_path):
    """Two files claiming to be the schema of one type is an error, not a guess."""
    base = tmp_path / ".todoc" / "entity_types" / "metric"
    base.mkdir(parents=True)
    (base / "schema.json").write_text("{}", encoding="utf-8")
    (base / "metric.v2.json").write_text("{}", encoding="utf-8")
    descriptor = {"type_id": "metric", "kind": "entity_type", "schema": "metric.v2.json"}
    items = descriptor_diagnostics(tmp_path, DATASET, "entity_type", descriptor, "x")
    assert [item["code"] for item in items] == ["config.duplicate_asset"]


def test_config_reports_a_declared_schema_that_is_missing(tmp_path):
    """A dead pointer is reported instead of silently validating nothing."""
    descriptor = {"type_id": "metric", "kind": "entity_type", "schema": "metric.json"}
    items = descriptor_diagnostics(tmp_path, DATASET, "entity_type", descriptor, "x")
    assert [item["code"] for item in items] == ["config.schema_missing"]


def test_init_keeps_type_assets_in_one_place(tmp_path):
    """A fresh dataset has no parallel templates/ or schemas/ catalog to drift from."""
    root = tmp_path / "kb"
    root.mkdir()
    init_dataset(root)
    todoc = root / ".todoc"
    assert not (todoc / "templates").exists()
    assert not (todoc / "schemas").exists()
    assert "templates" not in json.loads((todoc / "dataset.json").read_text(encoding="utf-8"))
    for type_id in DEFAULT_ENTITY_TYPES:
        base = todoc / "entity_types" / type_id
        assert (base / "type.json").is_file()
        assert (base / "template.json").is_file()
        assert sorted(p.name for p in (base / "prompts").iterdir()) == sorted(f"{op}.md" for op in PROMPT_OPERATIONS)


def test_record_schemas_come_from_the_type_folder_and_skip_broken_ones(tmp_path):
    """The loader reads each type's own schema; an unreadable one is skipped, not fatal."""

    for type_id, body in (("good", '{"type": "object"}'), ("broken", "{not json")):
        base = tmp_path / ".todoc" / "entity_types" / type_id
        base.mkdir(parents=True)
        (base / "schema.json").write_text(body, encoding="utf-8")
    # Valid JSON that is not an object is not a schema either.
    listed = tmp_path / ".todoc" / "entity_types" / "listed"
    listed.mkdir(parents=True)
    (listed / "schema.json").write_text("[]", encoding="utf-8")
    registry = {"entity_types": {"good": {"type_id": "good"}, "broken": {"type_id": "broken"},
                                 "plain": {"type_id": "plain"}, "listed": {"type_id": "listed"}}}
    assert list(_load_schemas(tmp_path, registry, {}, "entity_type", _entity_types_of)) == ["good"]


def test_a_schema_violation_names_the_schema_that_was_applied(tmp_path):
    """The evidence is the path the schema was loaded from, recorded at load time."""
    root = tmp_path / "root"
    base = root / ".todoc" / "entity_types" / "metric"
    base.mkdir(parents=True)
    (base / "schema.json").write_text("{}", encoding="utf-8")
    registry = {"entity_types": {"metric": {"type_id": "metric"}}}
    assert _load_schemas(root, registry, {}, "entity_type", _entity_types_of)["metric"][1] == (
        "schema: .todoc/entity_types/metric/schema.json")

    # A type with no schema loads nothing: no path is invented for it.
    (base / "schema.json").unlink()
    assert _load_schemas(root, registry, {}, "entity_type", _entity_types_of) == {}

    # A schema declared outside DATA_ROOT is reported as-is rather than crashing.
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    declared = {"entity_types": {"metric": {"type_id": "metric", "schema": str(outside)}}}
    assert _load_schemas(root, declared, {}, "entity_type", _entity_types_of)["metric"][1] == f"schema: {outside}"


# --- Фаза 2: any_of_sections и схема front matter документов -----------------

ANY_OF = {"any_of_sections": ["## ADDED:", "## MODIFIED:", "## REMOVED:"]}


def test_any_of_sections_accepts_single_alternative():
    """Дельте достаточно одной операции: required_sections здесь не подходит."""
    for selector in ("## ADDED: ## Новое", "## MODIFIED: ## Цель", "## REMOVED: ## Старое"):
        text = f"# Д\n\n{selector}\n\nтело\n"
        assert _diags(text, ANY_OF) == [], selector


def test_any_of_sections_reports_when_none_present():
    found = _diags("# Д\n\n## Просто раздел\n\nтекст\n", ANY_OF)
    assert [d.code for d in found] == ["markdown.section.missing"]
    assert found[0].location == {"line": 1, "column": 1}
    assert found[0].evidence.startswith("doc_type declares any_of_sections")
    assert found[0].suggested_fixes[0].replacement == "## ADDED:"


def test_any_of_sections_ignores_blank_selectors():
    assert _diags("# Д\n\n## ADDED: ## Новое\n\nт\n", {"any_of_sections": ["", "   ", 5]}) == []


def test_doc_type_schema_is_optional(root):
    """Тип без schema ведёт себя как раньше — ни одна проверка не должна сломаться."""
    descriptor = load_json_file(root / ".todoc" / "doc_types" / "note" / "type.json")
    assert "schema" not in descriptor
    assert schema_file(root, {}, "doc_type", descriptor) is None


def test_delta_doc_type_declares_schema_and_any_of(root):
    descriptor = load_json_file(root / ".todoc" / "doc_types" / "delta" / "type.json")
    assert descriptor["any_of_sections"] == ["## ADDED:", "## MODIFIED:", "## REMOVED:"]
    path = schema_file(root, {}, "doc_type", descriptor)
    assert path is not None and path.is_file()
    schema = load_json_file(path)
    assert schema["required"] == ["target"]


def test_document_schema_violation_is_reported(root):
    """Front matter документов проверяется схемой doc_type (план §19, вариант (a))."""
    deltas = root / "changes" / "x" / "deltas"
    deltas.mkdir(parents=True)
    (deltas / "d.md").write_text("---\ndoc_type: delta\n---\n\n## ADDED: ## Новое\n\nт\n",
                                 encoding="utf-8")
    from todoc.adapters.filesystem.scanner import scan_dataset

    dataset = load_dataset(root)
    dir_rules, doc_rules = load_rules(root, dataset)
    registry = TypeRegistry()
    registry.load(root, dataset)
    scanned = scan_dataset(root)
    _diags_found, _info = validate_dataset(root, dataset, scanned[1], dir_rules, doc_rules,
                                           registry=registry)
    codes = [d.code for d in _diags_found]
    assert "document.schema_violation" in codes
    violation = next(d for d in _diags_found if d.code == "document.schema_violation")
    # Отсутствие обязательного свойства — ошибка корня, поэтому указатель "/",
    # а имя свойства остаётся в сообщении (так и требует семантика JSON Schema).
    assert violation.location["pointer"] == "/"
    assert violation.location["doc_type"] == "delta"
    assert "target" in violation.message
    assert "schema:" in violation.evidence


def test_document_schema_accepts_valid_front_matter(root):
    deltas = root / "changes" / "x" / "deltas"
    deltas.mkdir(parents=True)
    (deltas / "d.md").write_text(
        "---\ntarget: notes/a.md\ndoc_type: delta\n---\n\n## ADDED: ## Новое\n\nт\n",
        encoding="utf-8")
    from todoc.adapters.filesystem.scanner import scan_dataset

    dataset = load_dataset(root)
    dir_rules, doc_rules = load_rules(root, dataset)
    registry = TypeRegistry()
    registry.load(root, dataset)
    scanned = scan_dataset(root)
    found, _info = validate_dataset(root, dataset, scanned[1], dir_rules, doc_rules,
                                    registry=registry)
    assert [d.code for d in found] == []


# ---------------------------------------------------------------------------
# metric_fields: объявляется промпт, а не формула (P1-11)
# ---------------------------------------------------------------------------

ENTITY = {"schema_version": 1, "type_id": "metric", "version": "0.1", "kind": "entity_type",
          "description": "Показатель.", "format": "json"}


def test_metric_fields_accepts_unit_and_prompt(tmp_path):
    descriptor = dict(ENTITY, metric_fields={"value": {"unit": "count", "prompt": "Целое число."}})
    assert descriptor_diagnostics(tmp_path, DATASET, "entity_type", descriptor, "c.json") == []


def test_metric_fields_formula_is_an_unknown_field(tmp_path):
    """Формула в типе — мёртвая конфигурация: ядро её никогда не вычисляло."""
    descriptor = dict(ENTITY, metric_fields={"value": {"unit": "count", "formula": "sum(value)"}})
    found = descriptor_diagnostics(tmp_path, DATASET, "entity_type", descriptor, "c.json")
    unknown = [item for item in found if item["code"] == "config.unknown_field"]
    assert len(unknown) == 1
    assert "formula" in unknown[0]["message"]
    assert "prompt" in unknown[0]["message"]


def test_metric_fields_shapes_are_checked(tmp_path):
    descriptor = dict(ENTITY, metric_fields={"a": "не объект", "b": {"unit": 7}, "c": {"prompt": "  "}})
    codes = [item["code"] for item in descriptor_diagnostics(tmp_path, DATASET, "entity_type", descriptor, "c.json")]
    assert codes == ["config.invalid_schema", "config.invalid_schema", "config.invalid_schema"]


def test_metric_fields_must_be_an_object(tmp_path):
    descriptor = dict(ENTITY, metric_fields=["value"])
    codes = [item["code"] for item in descriptor_diagnostics(tmp_path, DATASET, "entity_type", descriptor, "c.json")]
    assert codes == ["config.invalid_schema"]


def test_metric_field_keys_are_fixed():
    assert METRIC_FIELD_KEYS == {"unit", "prompt"}
