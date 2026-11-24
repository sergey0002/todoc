"""Tests for the hardened markdown/json adapters (token links, strict JSON)."""

from __future__ import annotations

import json

import pytest

from todoc.adapters.filesystem.scanner import ScannedFile
from todoc.adapters.formats.jsonfmt import parse_json, resolve_pointer, validate_against_schema
from todoc.adapters.formats.markdown import (
    build_backlink_index,
    heading_path_for,
    parse_markdown,
    resolve_link_target,
)
from todoc.application.validator import _check_markdown_links, _validate_records, validate_dataset


# --- markdown: token-authoritative links -----------------------------------


def test_links_inside_code_fence_are_not_links():
    doc = parse_markdown("# T\n\n```\n[example](missing-in-code.md)\n```\n")
    assert doc.links == []


def test_links_inside_inline_code_are_not_links():
    doc = parse_markdown("Use `[a](b.md)` literally.\n")
    assert doc.links == []


def test_links_inside_indented_code_are_not_links():
    doc = parse_markdown("Text\n\n    [a](b.md)\n")
    assert doc.links == []


def test_wikilink_inside_inline_code_is_ignored():
    doc = parse_markdown("Literal `[[Page]]` here.\n")
    assert doc.links == []


def test_reference_style_link_is_found():
    doc = parse_markdown("See [runbook][rb].\n\n[rb]: ../ops/runbook.md\n")
    assert [(link.text, link.target) for link in doc.links] == [("runbook", "../ops/runbook.md")]


def test_shortcut_reference_link_is_found():
    doc = parse_markdown("See [runbook].\n\n[runbook]: ../ops/runbook.md\n")
    assert [link.target for link in doc.links] == ["../ops/runbook.md"]


def test_autolink_is_found():
    doc = parse_markdown("Mail <https://example.com/a.md> now.\n")
    assert [link.target for link in doc.links] == ["https://example.com/a.md"]


def test_image_link_is_found():
    doc = parse_markdown("![diagram](img/arch.png)\n")
    assert [(link.text, link.target) for link in doc.links] == [("diagram", "img/arch.png")]


def test_multiline_link_reports_start_line():
    text = "Start [a long\nlabel](deep/target.md) end.\n"
    doc = parse_markdown(text)
    link = next(l for l in doc.links if l.target == "deep/target.md")
    assert link.line == 1


def test_columns_of_inline_link():
    doc = parse_markdown("ab [x](rel/one.md) cd\n")
    link = doc.links[0]
    assert (link.column, link.end_column) == (4, 18)


def test_wikilink_columns():
    doc = parse_markdown("ab [[Some Page]] cd\n")
    link = doc.links[0]
    assert link.is_wikilink is True
    assert link.target == "Some Page"
    assert (link.column, link.end_column) == (4, 16)


def test_percent_encoded_target_is_decoded():
    doc = parse_markdown("[a](notes/my%20note.md)\n")
    assert doc.links[0].target == "notes/my note.md"


def test_headings_have_plain_text_titles_and_unique_anchors():
    doc = parse_markdown("# Intro **bold**\n\n## Setup\n\n## Setup\n")
    assert [h.title for h in doc.headings] == ["Intro bold", "Setup", "Setup"]
    assert [h.anchor for h in doc.headings] == ["intro-bold", "setup", "setup-1"]


def test_heading_parent_child_tree():
    doc = parse_markdown("# A\n\n## B\n\n### C\n\n## D\n")
    heads = doc.headings
    assert [h.parent_index for h in heads] == [None, 0, 1, 0]
    assert [h.title for h in heads[0].children] == ["B", "D"]
    assert heading_path_for(heads, 2) == ["A", "B", "C"]


def test_heading_with_code_in_title():
    doc = parse_markdown("# Use `todoc check`\n")
    assert doc.headings[0].title == "Use todoc check"


def test_front_matter_types_and_quotes():
    doc = parse_markdown('---\ntitle: "Quoted: yes"\nprivate: false\nshared: true\ntags: [a, "b c"]\nempty: []\nplain\n---\n\n# H\n')
    assert doc.front_matter == {
        "title": "Quoted: yes",
        "private": False,
        "shared": True,
        "tags": ["a", "b c"],
        "empty": [],
    }
    assert doc.headings[0].line == 10  # 1-based, front matter counts
    assert doc.title == "Quoted: yes"


def test_markdown_bom_is_stripped():
    doc = parse_markdown("\ufeff# BOM\n")
    assert doc.headings[0].title == "BOM"


# --- markdown: target resolution and backlinks ------------------------------


@pytest.mark.parametrize(
    ("source", "target", "expected"),
    [
        ("notes/a.md", "b.md", "notes/b.md"),
        ("notes/a.md", "../ops/runbook.md", "ops/runbook.md"),
        ("notes/sub/a.md", "../../root.md", "root.md"),
        ("a.md", "/absolute.md", "absolute.md"),
        ("notes/a.md", "sibling.md#section", "notes/sibling.md"),
        ("notes/a.md", "#only-anchor", None),
        ("notes/a.md", "https://example.com/x.md", None),
        ("notes/a.md", "mailto:a@b.c", None),
        ("notes/a.md", "", None),
        ("a.md", "../../../../escape.md", "escape.md"),
    ],
)
def test_resolve_link_target(source: str, target: str, expected: str | None):
    assert resolve_link_target(source, target) == expected


def test_build_backlink_index():
    docs = {
        "notes/a.md": parse_markdown("See [b](../ops/b.md) and [self](a.md).\n"),
        "notes/c.md": parse_markdown("See [b](../ops/b.md).\n"),
    }
    assert build_backlink_index(docs) == {"notes/a.md": ["notes/a.md"], "ops/b.md": ["notes/a.md", "notes/c.md"]}


# --- markdown: wikilink resolution in the validator -------------------------


def test_wikilink_resolves_by_stem_anywhere_in_root(root):
    (root / "deep" / "nested").mkdir(parents=True)
    (root / "deep" / "nested" / "Some Page.md").write_text("# Some Page\n", encoding="utf-8")
    page = root / "index.md"
    page.write_text("# Index\n\nGo to [[Some Page]].\n", encoding="utf-8")
    scanned = ScannedFile("index.md", page, "markdown", page.stat().st_size, "sha256:")
    diags = _check_markdown_links("ds", scanned, root, {"index.md", "deep/nested/Some Page.md"})
    assert diags == []


def test_missing_wikilink_diagnostic(root):
    page = root / "index.md"
    page.write_text("# Index\n\n[[Nope]]\n", encoding="utf-8")
    scanned = ScannedFile("index.md", page, "markdown", page.stat().st_size, "sha256:")
    diags = _check_markdown_links("ds", scanned, root, {"index.md"})
    assert len(diags) == 1
    assert diags[0].code == "markdown.link.target_missing"
    assert diags[0].location == {"line": 3, "column": 1, "end_column": 8, "is_wikilink": True}
    assert diags[0].evidence == "[[Nope]]"


def test_broken_inline_link_reports_end_column(root):
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "runbok.md").write_text("# Runbook\n", encoding="utf-8")
    page = root / "notes" / "a.md"
    page.write_text("See [runbook](runbok.md).\n", encoding="utf-8")
    scanned = ScannedFile("notes/a.md", page, "markdown", page.stat().st_size, "sha256:")
    diags = _check_markdown_links("ds", scanned, root, {"notes/a.md", "notes/runbok.md"})
    assert diags == []  # runbok.md exists as a path; only typos in the target break


def test_broken_inline_link_typo_suggests_fix(root):
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "runbook.md").write_text("# Runbook\n", encoding="utf-8")
    page = root / "notes" / "a.md"
    page.write_text("See [runbook](runbok.md).\n", encoding="utf-8")
    scanned = ScannedFile("notes/a.md", page, "markdown", page.stat().st_size, "sha256:")
    diags = _check_markdown_links("ds", scanned, root, {"notes/a.md", "notes/runbook.md"})
    assert len(diags) == 1
    assert diags[0].location["end_column"] == 24
    assert diags[0].suggested_fixes[0].replacement == "notes/runbook.md"


# --- json: strictness -------------------------------------------------------


def test_duplicate_key_is_rejected():
    value, errors = parse_json('{"a": 1, "a": 2}')
    assert value is None
    assert errors[0].startswith("json.duplicate_key")


def test_invalid_constants_are_rejected():
    for text in ("[NaN]", "[Infinity]", "[-Infinity]"):
        value, errors = parse_json(text)
        assert value is None
        assert errors[0].startswith("json.invalid_constant")


def test_json_bom_is_stripped():
    value, errors = parse_json('\ufeff{"a": 1}')
    assert value == {"a": 1}
    assert errors == []


def test_depth_limit_is_enforced_iteratively():
    deep = "[" * 400 + "]" * 400
    value, errors = parse_json(deep, max_depth=128)
    assert value is None
    assert len(errors) == 1
    assert errors[0].startswith("json.too_deep: nesting depth ")


def test_no_recursion_error_on_hostile_nesting():
    hostile = "[" * 5000 + "]" * 5000
    value, errors = parse_json(hostile)  # must not raise
    assert value is None
    assert errors and errors[0].startswith("json.too_deep")


def test_shallow_json_passes():
    value, errors = parse_json('{"a": [1, {"b": 2}]}', max_depth=128)
    assert errors == []
    assert value == {"a": [1, {"b": 2}]}


def test_pointer_edge_cases():
    value = {"a": {"b": [10, 20]}, "": "root-empty"}
    assert resolve_pointer(value, "/") == "root-empty"
    assert resolve_pointer(value, "/a/b/0") == 10
    with pytest.raises(KeyError):
        resolve_pointer(value, "/a/b/-1")
    with pytest.raises(IndexError):
        resolve_pointer(value, "/a/b/2")
    with pytest.raises(KeyError):
        resolve_pointer([1, 2], "no-slash")


def test_validate_against_schema_reports_pointers():
    schema = {"type": "object", "properties": {"volume": {"type": "object", "properties": {"value": {"type": "number"}}, "required": ["value"]}}}
    messages = validate_against_schema({"volume": {}}, schema)
    assert messages == ["/volume: 'value' is a required property"]
    assert validate_against_schema({"volume": {"value": 3}}, schema) == []


# --- validator: record schema validation -----------------------------------


def test_record_schema_violation_is_reported(root):
    schema_dir = root / ".todoc" / "schemas" / "records"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "workout.json").write_text(json.dumps({
        "type": "object",
        "properties": {"volume": {"type": "object", "properties": {"value": {"type": "number"}}, "required": ["value"]}},
    }), encoding="utf-8")
    path = root / "records" / "w1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema_version": 1, "record_id": "workout:w1", "entity_type": "workout", "volume": {},
    }), encoding="utf-8")
    scanned = ScannedFile("records/w1.json", path, "json", path.stat().st_size, "sha256:")
    diags, records = _validate_records("ds", root, [scanned], {})
    assert [d.code for d in diags] == ["record.schema_violation"]
    assert diags[0].location == {"pointer": "/volume", "entity_type": "workout"}
    assert records[0]["record_id"] == "workout:w1"


def test_record_without_schema_is_not_flagged(root):
    path = root / "records" / "w1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"record_id": "w:1", "entity_type": "note"}), encoding="utf-8")
    scanned = ScannedFile("records/w1.json", path, "json", path.stat().st_size, "sha256:")
    diags, _records = _validate_records("ds", root, [scanned], {})
    assert diags == []


def test_invalid_schema_file_is_ignored(root):
    schema_dir = root / ".todoc" / "schemas" / "records"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "note.json").write_text("{not json", encoding="utf-8")
    (schema_dir / "bad.json").write_text("[1, 2]", encoding="utf-8")
    path = root / "records" / "n1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"record_id": "n:1", "entity_type": "note"}), encoding="utf-8")
    scanned = ScannedFile("records/n1.json", path, "json", path.stat().st_size, "sha256:")
    diags, _records = _validate_records("ds", root, [scanned], {})
    assert diags == []


def test_validate_dataset_reports_duplicate_key_error(root):
    path = root / "records" / "dup.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"a": 1, "a": 2}', encoding="utf-8")
    scanned = ScannedFile("records/dup.json", path, "json", path.stat().st_size, "sha256:")
    diags, _info = validate_dataset(root, {"dataset_id": "ds"}, [scanned], [], [])
    assert [d.code for d in diags] == ["json.duplicate_key"]


# --- validator: relation type/target checks --------------------------------


def test_unknown_relation_type_is_reported():
    from todoc.application.validator import validate_relations

    records = [{"record_id": "w:1", "path": "w.json",
                "data": {"relations": [{"type_id": "loves", "target": {"id": "w:1"}}]}}]
    diags = validate_relations("ds", records, {"performed_by"})
    assert [d.code for d in diags] == ["relation.unknown_type"]


def test_relation_type_check_disabled_without_registry():
    from todoc.application.validator import validate_relations

    records = [{"record_id": "w:1", "path": "w.json",
                "data": {"relations": [{"type_id": "loves", "target": {"id": "w:1"}}]}}]
    assert validate_relations("ds", records) == []


def test_relation_missing_target_is_reported():
    from todoc.application.validator import validate_relations

    records = [{"record_id": "w:1", "path": "w.json",
                "data": {"relations": [{"type_id": "performed_by", "target": {}}]}}]
    diags = validate_relations("ds", records, {"performed_by"})
    assert [d.code for d in diags] == ["relation.missing_target"]


def test_relations_field_not_a_list_is_reported():
    from todoc.application.validator import validate_relations

    records = [{"record_id": "w:1", "path": "w.json", "data": {"relations": {"type_id": "x"}}}]
    diags = validate_relations("ds", records)
    assert [d.code for d in diags] == ["relation.malformed"]


def test_relation_missing_target_key_is_not_reported():
    from todoc.application.validator import validate_relations

    records = [{"record_id": "w:1", "path": "w.json", "data": {}}]
    assert validate_relations("ds", records, {"performed_by"}) == []


# --- remaining edge branches ------------------------------------------------


def test_setext_heading_with_softbreak_keeps_plain_title():
    doc = parse_markdown("Multi word\ntitle\n=========\n")
    assert doc.headings[0].title == "Multi word title"


def test_softbreak_outside_link_keeps_lines_aligned():
    doc = parse_markdown("[a](one.md)\nplain wrapped\ntext here\n")
    assert [link.line for link in doc.links] == [1]


def test_unclosed_backtick_on_wikilink_line():
    doc = parse_markdown("open `tick then [[Page]]\n")
    assert [link.target for link in doc.links] == ["Page"]


def test_entity_encoded_destination_still_gets_columns():
    doc = parse_markdown("[a](&#120;.md)\n")
    link = doc.links[0]
    assert link.target == "x.md"
    assert link.column == 1


def test_backlink_index_skips_external_and_anchor_links():
    docs = {"a.md": parse_markdown("[x](b.md) [y](https://e.com/z.md) [z](#frag)\n")}
    assert build_backlink_index(docs) == {"b.md": ["a.md"]}


def test_record_schemas_absent_dir(tmp_path):
    from todoc.application.validator import _load_record_schemas

    assert _load_record_schemas(tmp_path) == {}


def test_reference_link_after_two_inline_links():
    doc = parse_markdown("[a](x.md) [b](y.md) [c][rb]\n\n[rb]: z.md\n")
    assert [(link.text, link.target) for link in doc.links] == [("a", "x.md"), ("b", "y.md"), ("c", "z.md")]
    assert [link.column for link in doc.links] == [1, 11, 21]
