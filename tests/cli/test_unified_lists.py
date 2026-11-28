"""Collection contracts shared by typed records, history, and catalogs."""

import json

import pytest
from click.testing import CliRunner

from todoc.cli import cli
from todoc.service import DatasetContext


def invoke(runner, root, *args):
    result = runner.invoke(cli, ["--root", str(root), *args])
    assert result.exit_code == 0, (args, result.exception, result.output)
    return result


@pytest.fixture()
def collections(root, sample_md, sample_record, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("todoc.application.state.ALLOWED_KEYS_V1", ("context.current_project", "context.branch"))
    runner = CliRunner()
    for key in ("context.current_project", "context.branch"):
        invoke(runner, root, "state", "set", key, "sample", "--apply")
    for title in ("Alpha", "Beta"):
        invoke(runner, root, "change", "open", "--title", title, "--apply")
    recorder = DatasetContext(root).history_recorder()
    recorder.record("notes/design.md", b"first", b"second", "doc.edit")
    recorder.record("notes/design.md", b"second", b"third", "doc.edit")
    data = json.loads(sample_record.read_text())
    data.update(record_id="workout:another", date="2026-11-25")
    sample_record.with_name("another.json").write_text(json.dumps(data) + "\n", encoding="utf-8")
    query = tmp_path / "query.json"
    query.write_text('{"entity_type":"workout","limit":1}', encoding="utf-8")
    return runner, root, query


@pytest.mark.parametrize(("base", "field", "structural", "query_spec"), [
    (("records", "list", "--type", "workout"), "data", {"record_id", "path"}, False),
    (("records", "query"), "data", {"record_id", "path"}, True),
    (("types", "list"), "description", {"kind", "type_id"}, False),
    (("state", "list"), "value", {"key"}, False),
    (("change", "list"), "title", {"record_id", "path"}, False),
    (("log", "--path", "notes/design.md"), "kind", {"rev"}, False),
    (("timeline", "--path", "notes/design.md"), "kind", {"entry", "path"}, False),
    (("blame", "--path", "notes/design.md"), "kind", {"rev"}, False),
    (("records", "aggregate", "--type", "workout", "--metric", "volume", "--group-by", "date"),
     "value", {"group"}, False),
])
def test_projection_preserves_selection_and_cursor(collections, base, field, structural, query_spec):
    runner, root, query = collections
    args = [*base, "--query-file", str(query)] if query_spec else [*base, "--limit", "1"]
    unprojected = json.loads(invoke(runner, root, *args).output)["data"]
    assert field in unprojected["result"]["items"][0]
    expected_cursor = unprojected["meta"]["next_cursor"]
    assert expected_cursor
    included = json.loads(invoke(runner, root, *args, "--fields", field).output)["data"]
    assert structural | {field} == set(included["result"]["items"][0])
    assert included["meta"]["next_cursor"] == expected_cursor
    excluded = json.loads(invoke(runner, root, *args, "--exclude-fields", field).output)["data"]
    assert field not in excluded["result"]["items"][0]
    assert excluded["meta"]["next_cursor"] == expected_cursor
    other = json.loads(invoke(runner, root, *args, "--fields", field, "--cursor", expected_cursor).output)["data"]
    assert other["meta"]["total"] == unprojected["meta"]["total"]
    assert other["meta"]["next_cursor"] != expected_cursor


@pytest.mark.parametrize("formatter", ["json", "table", "markdown"])
def test_flat_collection_fallback_reports_effective_view(collections, formatter):
    runner, root, _ = collections
    result = invoke(runner, root, "change", "list", "--view", "graph", "--output", formatter)
    if formatter == "json":
        envelope = json.loads(result.output)
        assert envelope["data"]["meta"]["actual_view"] == "flat"
        assert envelope["diagnostics"][0]["code"] == "view.fallback"
        assert envelope["data"]["result"]["items"]
    else:
        assert "view.fallback" in result.output and "Alpha" in result.output



@pytest.mark.parametrize("base", [
    ("records", "list", "--type", "workout"),
    ("records", "query"),
    ("types", "list"),
    ("state", "list"),
    ("log", "--path", "notes/design.md"),
    ("timeline", "--path", "notes/design.md"),
    ("blame", "--path", "notes/design.md"),
    ("records", "aggregate", "--type", "workout", "--metric", "volume", "--group-by", "date"),
])
def test_unavailable_collection_view_keeps_rows_and_explains_fallback(collections, base):
    runner, root, query = collections
    argv = [*base, "--query-file", str(query)] if base == ("records", "query") else list(base)
    flat = json.loads(invoke(runner, root, *argv).output)["data"]
    alternate = json.loads(invoke(runner, root, *argv, "--view", "unsupported").output)
    assert alternate["data"]["result"]["items"] == flat["result"]["items"]
    assert alternate["data"]["meta"]["requested_view"] == "unsupported"
    assert alternate["data"]["meta"]["actual_view"] == "flat"
    assert any(issue["code"] == "view.fallback" for issue in alternate["diagnostics"])


def test_timeline_count_only_rejects_cursor(collections):
    runner, root, _ = collections
    args = ["--root", str(root), "timeline", "--path", "notes/design.md"]
    first = json.loads(invoke(runner, root, "timeline", "--path", "notes/design.md", "--limit", "1").output)
    cursor = first["data"]["meta"]["next_cursor"]
    assert cursor
    result = runner.invoke(cli, [*args, "--limit", "0", "--cursor", cursor])
    assert result.exception.code == "cursor.invalid"
