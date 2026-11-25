"""Type assets: starter templates, CRUD prompts, structure rules, config strictness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from todoc.adapters.formats.markdown import parse_markdown
from todoc.application.validator import _check_structure, _normalize_heading, validate_dataset
from todoc.application.write import create_document_plan, structure_violations
from todoc.config import DEFAULT_DOC_TYPES, DEFAULT_ENTITY_TYPES, _write_type_assets, init_dataset
from todoc.errors import ConflictError, ValidationError
from todoc.typing_system.descriptors import (
    KIND_FIELDS,
    PROMPT_OPERATIONS,
    descriptor_diagnostics,
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
    assert "docs edit" in build_prompts("spec", "doc_type", "d", SPEC)["edit"]
    assert "records read" in build_prompts("note", "entity_type", "d", {"type_id": "note"})["edit"]
    assert "supersedes" in build_prompts("spec", "doc_type", "d", SPEC)["delete"]


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
    assert plan.new_content == "# T\n"


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
    plan = create_document_plan(DATASET, {}, None, "Заголовок", "inbox/x.md")
    assert plan.new_content == "# Заголовок\n\n"
    assert plan.validations == ("template", "none", "no-overwrite")


def test_create_document_plan_renders_template_and_flags_structure():
    plan = create_document_plan(DATASET, {"note": {"required_sections": ["## Суть"]}}, "note", "T",
                                "inbox/x.md", "# {title}\n\n## Суть\n\n{date}\n",
                                {"title": "T", "date": "2026-11-25"})
    assert plan.new_content == "# T\n\n## Суть\n\n2026-11-25\n"
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
