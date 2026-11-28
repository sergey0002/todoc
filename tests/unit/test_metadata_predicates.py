"""Predicate and schema tests for typed and source-defined metadata."""

import json

import pytest

from todoc.application.filters import compile_conditions, matches_conditions
from todoc.application.metadata_patch import patch_attributes
from todoc.errors import TodocError, ValidationError
from todoc.typing_system.document_metadata import load_metadata_schema, metadata_errors


def _filter(tmp_path, field, op, value):
    path = tmp_path / "selection.json"
    path.write_text(json.dumps({
        "schema_version": 1, "conditions": [{"field": field, "op": op, "value": value}],
    }), encoding="utf-8")
    return path


@pytest.mark.parametrize(("field", "op", "value", "matches"), [
    ("created", "lte", "2026-01-01", False),
    ("created", "gte", "2026-01-01", True),
    ("tags", "has_all", ["work", "cli"], True),
    ("tags", "has_all", ["work", "other"], False),
    ("tags", "has_any", ["other", "cli"], True),
    ("tags", "has_any", ["other"], False),
    ("status", "exists", True, True),
    ("status", "exists", False, False),
    ("status", "eq", None, True),
    ("/вес.команды", "eq", 2, True),
    ("priority", "gte", 2, True),
    ("/nested/0/type", "eq", "example", True),
])
def test_predicates_distinguish_source_values(tmp_path, field, op, value, matches):
    row = {"created": "2026-11-28", "tags": ["work", "cli"], "status": None, "вес.команды": 2,
           "priority": 4, "nested": [{"type": "example"}]}
    rules = compile_conditions([row], {}, filter_file=_filter(tmp_path, field, op, value))
    assert matches_conditions(row, rules) is matches


@pytest.mark.parametrize(("field", "op", "value"), [
    ("path", "unknown", "text"),
    ("unknown", "eq", "text"),
    ("/path~2", "eq", "text"),
    ("nested..type", "eq", "text"),
    ("tags", "has_any", []),
    ("rating", "has_all", ["1"]),
    ("status", "exists", "true"),
    ("rating", "gte", None),
    ("created", "gte", "2026-09-31"),
])
def test_bad_predicates_report_usage_error(tmp_path, field, op, value):
    row = {"status": None, "rating": 2, "tags": ["work"], "created": "2026-01-31"}
    with pytest.raises(TodocError) as exc:
        compile_conditions([row], {}, filter_file=_filter(tmp_path, field, op, value))
    assert exc.value.code == "filter.invalid"


def test_unicode_key_and_equivalent_predicate_normalize(tmp_path):
    row = {"вес.команды": 2}
    remote = _filter(tmp_path, "/вес.команды", "in", [4, 2, 2])
    direct = compile_conditions([row], {}, (("вес.команды", "2|4"),))
    declared = {"later": {"type": "array", "items": {"type": "integer"}}}
    assert direct == compile_conditions([row], {}, filter_file=remote)
    invisible = compile_conditions([], declared, (("later", "4"),))
    assert invisible == (("/later", "has_any", [4]),)


@pytest.mark.parametrize("operations", [
    None, [], ["wrong"], [{"op": "remove", "field": "id"}],
    [{"op": "set", "field": "x"}], [{"op": "unknown", "field": "x", "value": 2}],
    [{"op": "add_item", "field": "existing", "value": 2}],
])
def test_metadata_patch_rejects_invalid_operations(operations):
    with pytest.raises(ValidationError) as exc:
        patch_attributes({"existing": "text"}, operations)
    assert exc.value.code == "metadata.invalid_patch"


def test_common_schema_reports_invalid_definition_and_disables_remote_references(root):
    path = root / ".todoc" / "document-metadata.schema.json"
    path.write_text('{"required": true}', encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        load_metadata_schema(root)
    assert exc.value.code == "metadata.invalid_schema"
    path.write_text('{"properties":{"value":{"$ref":"https://example.invalid/schema"}}}', encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        metadata_errors({"value": 1}, load_metadata_schema(root), "/meta")
    assert exc.value.code == "metadata.invalid_schema"


def test_outline_matches_full_markdown_provenance():
    from todoc.adapters.formats.markdown import parse_markdown

    source = (
        "---\ntitle: Sample\n---\n\n"
        "# *Styled* [link][reference]\n\n"
        "[reference]: foo.md\n\n"
        "## `Code`\n\n[body](other.md)\n"
        "\n~~~markdown\n# Not a heading\n~~~\n"
    )
    complete = parse_markdown(source)
    outline = parse_markdown(source, include_links=False)
    assert outline.title == complete.title and outline.front_matter == complete.front_matter
    assert outline.headings == complete.headings
    assert complete.links and not outline.links



@pytest.mark.parametrize("payload", [b"{", b"[]", b'{"schema_version":true,"conditions":[]}',
                                     b'{"schema_version":1,"conditions":[{}]}', b"\xff"])
def test_filter_rejects_unreadable_or_invalid_files(tmp_path, payload):
    path = tmp_path / "broken-filter.json"
    path.write_bytes(payload)
    with pytest.raises(TodocError, match="filter file|condition"):
        compile_conditions([], {}, filter_file=path)


@pytest.mark.parametrize(("rows", "declared", "operand"), [
    ([{"value": 1}, {"value": False}], {}, "1"),
    ([{"value": [{}]}], {}, "anything"),
    ([{"value": 2}], {}, "not-a-number"),
    ([{"value": 2}], {}, "true"),
    ([], {"value": {"type": "number"}}, "1" + "0" * 400),
    ([], {"value": {"type": "number"}}, "NaN"),
    ([{"value": 2}], {}, "2|"),
])
def test_attribute_argument_rejects_ambiguous_values_and_invalid_coercions(rows, declared, operand):
    with pytest.raises(TodocError) as failure:
        compile_conditions(rows, declared, (("value", operand),))
    assert failure.value.code == "filter.invalid"


def test_filter_can_query_declared_array_elements_and_unset_tags(tmp_path):
    declared = {"nested": {"type": "array", "items": {"type": "integer"}},
                "value": {"type": "number"}, "tags": {"type": "array", "items": {"type": "string"}}}
    assert compile_conditions([], declared, filter_file=_filter(tmp_path, "/nested/0", "eq", 2)) == (
        ("/nested/0", "eq", 2),)
    assert compile_conditions([], declared, (("value", "1"),)) == (("/value", "in", [1.0]),)
    rules = compile_conditions([], declared, filter_file=_filter(tmp_path, "tags", "has_any", ["demo"]))
    assert not matches_conditions({"tags": "text"}, rules)
    rules = compile_conditions([], declared, filter_file=_filter(tmp_path, "value", "gte", 2.0))
    assert not matches_conditions({}, rules)
    assert not matches_conditions({"value": "2"}, rules)


@pytest.mark.parametrize(("fmt", "content", "operations"), [
    ("markdown", "# Without metadata\n", [{"op": "set", "field": "status", "value": "active"}]),
    ("markdown", "---\ntitle: Old\n", [{"op": "set", "field": "status", "value": "active"}]),
    ("json", "[]\n", [{"op": "set", "field": "status", "value": "active"}]),
    ("json", '{"record_id":"note:legacy"}\n', [{"op": "set", "field": "status", "value": "active"}]),
    ("json", '{"meta":42}\n', [{"op": "set", "field": "status", "value": "active"}]),
    ("json", '{"title":"a","meta":{"title":"a"}}\n', [{"op": "set", "field": "title", "value": "b"}]),
    ("csv", "name\ndemo\n", [{"op": "set", "field": "status", "value": "active"}]),
    ("json", '{"meta":{"status":"old"}}\n', [{"op": "set", "field": "status", "value": "other"}]),
])
def test_metadata_plan_rejects_invalid_sources_without_changing_bytes(tmp_path, fmt, content, operations):
    from todoc.adapters.filesystem.scanner import file_hash
    from todoc.application.metadata_patch import plan_metadata_patch

    path = tmp_path / "source"
    path.write_text(content, encoding="utf-8")
    before = path.read_bytes()
    entry = {"path": "source", "hash": file_hash(path)}
    with pytest.raises(ValidationError) as error:
        plan_metadata_patch(tmp_path, "test", entry, fmt, operations, [], allowed_statuses=["active"])
    assert error.value.code == "metadata.invalid_patch"
    assert path.read_bytes() == before


def test_metadata_noop_array_operations_preserve_original_order():
    original = {"tags": ["b", "a"]}
    operations = [{"op": "add_item", "field": "tags", "value": "a"},
                  {"op": "remove_item", "field": "unused", "value": "x"}]
    assert patch_attributes(original, operations) == original



def test_markdown_declared_scalars_reject_nonfinite_literals_and_preserve_text():
    from todoc.typing_system.document_metadata import normalize_markdown_attributes

    values = {"bad": "not-json", "bool": "true", "finite": "6", "nan": "NaN",
              "none": "null", "string": "12", "number": 4}
    kinds = {"bad": "number", "bool": "number", "finite": "integer", "nan": "number",
             "none": "null", "string": "string", "number": "integer"}
    schema = {"properties": {key: {"type": kind} for key, kind in kinds.items()}}
    assert normalize_markdown_attributes(values, [(schema, "schema")]) == {
        **values, "finite": 6, "none": None,
    }


def test_metadata_schema_requires_object_and_reports_escaped_nested_pointer(root):
    path = root / ".todoc/document-metadata.schema.json"
    path.write_text("false", encoding="utf-8")
    with pytest.raises(ValidationError) as error:
        load_metadata_schema(root)
    assert error.value.code == "metadata.invalid_schema"
    schema = {"properties": {"a~/": {"type": "array", "items": {"type": "integer"}}}}
    findings = metadata_errors({"a~/": ["invalid"]}, schema, "/meta")
    assert findings[0][0] == "/meta/a~0~1/0"


def test_metadata_preview_refuses_stale_content_and_unreadable_sources(tmp_path):
    from todoc.adapters.filesystem.scanner import file_hash
    from todoc.application.metadata_patch import plan_metadata_patch
    from todoc.errors import ConflictError

    target = tmp_path / "document.md"
    target.write_text("---\ntitle: Sample\n---\n", encoding="utf-8")
    entry = {"path": "document.md", "hash": file_hash(target)}
    ops = [{"field": "status", "op": "set", "value": "active"}]
    target.write_text("---\ntitle: Changed\n---\n", encoding="utf-8")
    with pytest.raises(ConflictError) as conflict:
        plan_metadata_patch(tmp_path, "demo", entry, "markdown", ops, [])
    assert conflict.value.code == "write.hash_mismatch"
    for invalid in ("missing.md", "../outside.md"):
        with pytest.raises(ValidationError) as problem:
            plan_metadata_patch(tmp_path, "demo", {**entry, "path": invalid}, "markdown", ops, [])
        assert problem.value.code == "metadata.invalid_patch"


def test_metadata_rewrite_preserves_crlf_and_removes_all_duplicate_assignments():
    from todoc.application.metadata_patch import rewrite_markdown_attributes

    original = "---\r\n# Comment\r\nstatus: open\r\nstatus: open\r\n---\r\n# Body\r\n"
    actual = rewrite_markdown_attributes(original, {"status": "open"}, {"status": "closed"})
    assert actual == '---\r\n# Comment\r\nstatus: "closed"\r\n---\r\n# Body\r\n'



def test_markdown_front_matter_parses_json_values_and_preserves_legacy_literals():
    from todoc.adapters.formats.markdown import parse_markdown

    text = "\n".join((
        "---", 'caption: "line\\nend"', 'legacy: "unknown\\q"',
        'inline: {"mode":"strict"}', 'unsupported: {"reading":NaN}',
        'list: [NaN, example]', "---", "# Intent", "",
    ))
    attrs = parse_markdown(text).front_matter
    assert attrs["caption"] == "line\nend"
    assert attrs["legacy"] == "unknown\\q"
    assert attrs["inline"] == {"mode": "strict"}
    assert attrs["unsupported"] == '{"reading":NaN}'
    assert attrs["list"] == ["NaN", "example"]



@pytest.mark.parametrize(("values", "field", "operator", "operand"), [
    ([{"score": 1}, {"score": "mixed"}], "score", "eq", 1),
    ([{"score": 1}], "score", "eq", {"value": 1}),
    ([{"created": "2026-01-01"}], "created", "lte", "January"),
])
def test_filter_file_refuses_incompatible_operand_types_and_calendar_spellings(
    tmp_path, values, field, operator, operand
):
    with pytest.raises(TodocError) as error:
        compile_conditions(values, {}, filter_file=_filter(tmp_path, field, operator, operand))
    assert error.value.code == "filter.invalid"


def test_unknown_array_item_types_defer_to_observed_text():
    schema = {"array": {"type": "array", "items": {"type": "custom"}}}
    assert compile_conditions([], schema, (("array", "demo"),)) == (("/array", "has_any", ["demo"]),)
