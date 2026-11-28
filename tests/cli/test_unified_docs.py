"""Exercise metadata overview through the CLI, including cold and stale reads."""

from collections import Counter
from importlib.resources import files
import json
from pathlib import Path
from shutil import copytree, ignore_patterns
import subprocess
import sys

from click.testing import CliRunner
from jsonschema import Draft202012Validator
import pytest

from todoc.cli import cli, main
from todoc.service import DatasetContext

V2_SCHEMA = json.loads(files("todoc").joinpath("data", "output", "envelope-v2.json").read_text(encoding="utf-8"))


def _fixture(root: Path) -> None:
    config = Path(__file__).resolve().parents[2] / "demo" / ".todoc"
    copytree(config, root / ".todoc", dirs_exist_ok=True,
             ignore=ignore_patterns("history", "index", "cache"))
    folder = root / "ideas"
    folder.mkdir()
    statuses = ["captured"] * 11 + ["planned"] * 2 + ["done"] * 6 + [None]
    for index, status in enumerate(statuses):
        status_field = f"status: {status}\n" if status else ""
        (folder / f"idea-{index:02d}.md").write_text(
            f'---\nid: doc:fixture-{index}\ntitle: "Идея {index}"\ndoc_type: idea\n'
            f'{status_field}tags: [fixture]\n---\n\n# Идея {index}\n',
            encoding="utf-8",
        )


def _list(root: Path, *args: str):
    result = CliRunner().invoke(cli, ["docs", "list", "--root", str(root), *args])
    body = json.loads(result.stdout)
    Draft202012Validator(V2_SCHEMA).validate(body)
    return result.exit_code, body


def _snapshot(root: Path) -> dict[str, bytes]:
    return {file.relative_to(root).as_posix(): file.read_bytes()
            for file in root.rglob("*") if file.is_file()}


def _tree(root: Path, *args: str):
    return CliRunner().invoke(cli, ["docs", "tree", "--root", str(root), *args])


def test_tree_depth_and_scope(root, sample_md):
    nested = root / "notes" / "archive"
    nested.mkdir()
    (nested / "deep.md").write_text("# Deep\n", encoding="utf-8")
    (root / "notes-old").mkdir()
    (root / "notes-old" / "old.md").write_text("# Old\n", encoding="utf-8")
    for flag in ("--depth", "--max-depth"):
        result = _tree(root, "--within", "notes/", flag, "1")
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)["data"]
        assert data["meta"]["total"] == 3
        nodes = data["result"]["root"]["children"]
        assert [item["path"] for item in nodes] == ["notes/archive", "notes/design.md"]
    zero = json.loads(_tree(root, "--within", "notes", "--depth", "0").output)["data"]
    assert zero["meta"]["total"] == 1 and zero["result"]["root"]["children"] == []


def test_tree_cursor_traverses_every_row_and_rejects_scope_changes(root):
    folder = root / "empty"
    folder.mkdir()
    for count in range(53):
        (root / f"entry-{count:02d}.md").write_text("# Entry\n", encoding="utf-8")
    before = _snapshot(root)
    first = json.loads(_tree(root, "--view", "flat").output)["data"]
    meta = first["meta"]
    assert meta["total"] == 55 and meta["returned"] == 50 and meta["truncated"]
    cursor = meta["next_cursor"]
    last = json.loads(_tree(root, "--view", "flat", "--cursor", cursor).output)["data"]
    assert last["meta"]["returned"] == 5 and last["meta"]["next_cursor"] is None
    assert not last["meta"]["truncated"]
    rows = first["result"]["items"] + last["result"]["items"]
    assert len({item["path"] for item in rows if item["kind"] == "document"}) == 53
    changed_scope = _tree(root, "--depth", "1", "--cursor", cursor)
    assert json.loads(changed_scope.output)["diagnostics"][0]["code"] == "cursor.invalid"
    assert _snapshot(root) == before
    (folder / ".config.json").write_text('{"schema_version":1,"title":"Renamed folder"}', encoding="utf-8")
    changed_corpus = _tree(root, "--cursor", cursor)
    assert json.loads(changed_corpus.output)["diagnostics"][0]["code"] == "cursor.invalid"


def test_tree_rejects_multiple_roots(root):
    result = _tree(root, "--root", str(root))
    assert json.loads(result.output)["diagnostics"][0]["code"] == "docs.multiple_roots"


def test_read_projection_keeps_section_coordinates(root, sample_md):
    args = ["docs", "read", "--root", str(root), "--id", "doc:notes/design.md", "--section", "Decision"]
    response = CliRunner().invoke(cli, [*args, "--exclude-fields", "lines"])
    assert response.exit_code == 0, response.output
    data = json.loads(response.output)["data"]["result"]
    assert "lines" not in data and "refresh token" in data["text"]
    response = CliRunner().invoke(cli, [*args, "--fields", "text"])
    selected = json.loads(response.output)["data"]["result"]
    assert selected["line_start"] == data["line_start"]
    assert selected["line_end"] == data["line_end"]
    assert selected["truncated"] is False and selected["hash"] == data["hash"]
    assert "tags" not in selected


def test_ideas_overview_in_one_call(root):
    _fixture(root)
    before = _snapshot(root)
    code, result = _list(root, "--type", "idea", "--fields", "id,path,title,status", "--limit", "100")
    assert code == 0
    assert result["schema_version"] == 2
    assert result["guidance"]["items"] == []
    assert result["data"]["meta"]["complete"] is True
    assert result["data"]["meta"]["total"] == 20
    assert result["data"]["meta"]["next_cursor"] is None
    items = result["data"]["result"]["items"]
    assert set(items[0]) == {"id", "path", "title", "status"}
    assert items[0]["id"] == "doc:fixture-0"
    assert Counter(item["status"] for item in items) == {"captured": 11, "planned": 2, "done": 6, None: 1}
    assert len(json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")) < 12000
    assert _snapshot(root) == before


@pytest.mark.parametrize("args", [
    ("scan",), ("check",), ("validate", "--all"), ("docs", "tree"),
    ("docs", "search", "--query", "Design"), ("docs", "read", "--id", "doc:notes/design.md"),
    ("records", "list"), ("relations", "graph", "--from", "doc:notes/design.md"),
    ("log",), ("blame", "--path", "notes/design.md"), ("timeline",), ("stale",),
])
def test_existing_read_commands_leave_cold_dataset_unchanged(root, sample_md, args):
    before = _snapshot(root)
    result = CliRunner().invoke(cli, ["--root", str(root), *args])
    assert result.exit_code == 0, result.output
    assert _snapshot(root) == before


def test_record_filters_apply_before_limit(root, sample_record):
    template = json.loads(sample_record.read_text(encoding="utf-8"))
    for name, date, relations in [
        ("a", "2026-11-30", template["relations"]),
        ("b", "2026-11-20", []),
        ("c", "2026-11-20", template["relations"]),
        ("d", "2026-11-21", template["relations"]),
    ]:
        row = {**template, "record_id": f"workout:{name}", "date": date, "relations": relations}
        sample_record.with_name(f"{name}.json").write_text(json.dumps(row), encoding="utf-8")
    sample_record.unlink()
    response = CliRunner().invoke(cli, [
        "records", "list", "--root", str(root), "--type", "workout",
        "--since", "2026-11-20", "--until", "2026-11-21", "--limit", "1",
        "--relation", "performed_by=person:sergei",
    ])
    assert response.exit_code == 0, response.output
    data = json.loads(response.stdout)["data"]
    assert data["meta"]["total"] == 2 and data["meta"]["truncated"] is True
    assert [row["record_id"] for row in data["result"]["items"]] == ["workout:c"]


def test_cursor_binds_selection_and_revision(root):
    _fixture(root)
    flags = ("--type", "idea", "--status", "planned", "--status-missing", "--tag", "FIXTURE")
    code, result = _list(root, *flags, "--limit", "1")
    assert code == 0
    meta = result["data"]["meta"]
    assert meta["total"] == 3
    cursor = meta["next_cursor"]
    code, rest = _list(root, *flags, "--cursor", cursor, "--fields", "status")
    assert code == 0
    assert [item["status"] for item in rest["data"]["result"]["items"]] == ["planned", None]
    assert _list(root, "--cursor", cursor)[0] == 2
    (root / "ideas" / "idea-00.md").write_text("# Changed\n", encoding="utf-8")
    assert _list(root, *flags, "--cursor", cursor)[0] == 2


def test_read_index_falls_back_without_repairing_published_files(root):
    _fixture(root)
    ctx = DatasetContext(root)
    ctx.rebuild_index(observe=False)
    before = _snapshot(root)
    assert _list(root, "--type", "idea")[1]["data"]["meta"]["total"] == 20
    assert _snapshot(root) == before
    (ctx.store.current_dir / "documents.json").write_text("\"broken\"", encoding="utf-8")
    before = _snapshot(root)
    assert _list(root, "--type", "idea")[1]["data"]["meta"]["total"] == 20
    assert _snapshot(root) == before


def test_unreadable_document_does_not_become_a_complete_page(root):
    _fixture(root)
    (root / "ideas" / "unreadable.md").write_bytes(b"\xff")
    code, result = _list(root, "--within", "ideas")
    assert code == 6
    assert result["data"]["meta"]["complete"] is False
    assert result["data"]["meta"]["total"] is None
    assert result["diagnostics"][0]["path"] == "ideas/unreadable.md"


@pytest.mark.parametrize("args,expected", [
    (("--within", "../ideas"), "docs.invalid_scope"),
    (("--fields", "title", "--exclude-fields", "status"), "fields.conflict"),
    (("--fields", "unavailable"), "fields.unknown"),
    (("--limit", "0"), "usage.error"),
    (("--limit", "1001"), "usage.error"),
])
def test_subprocess_errors_keep_v2_and_original_exit_code(root, args, expected):
    proc = subprocess.run(
        [sys.executable, "-m", "todoc", "docs", "list", "--root", str(root), *args],
        capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 2
    result = json.loads(proc.stdout)
    assert result["schema_version"] == 2 and result["ok"] is False
    assert result["diagnostics"][0]["code"] == expected
    assert result["guidance"]["items"][0]["code"] == expected
    assert result["next_actions"][0]["argv"] == ["todoc", "docs", "list", "--help"]


def test_fields_discovery_without_root():
    result = CliRunner().invoke(cli, ["docs", "list", "--fields-help"])
    assert result.exit_code == 0
    data = json.loads(result.output)["data"]
    assert data["executed"] is False
    assert "parse_status" in data["result"]["fields"]


def test_fallback_preserves_items_and_scope(root):
    _fixture(root)
    code, result = _list(root, "--view", "graph", "--exclude-fields", "tags,hash")
    assert code == 0
    assert result["data"]["meta"]["requested_view"] == "graph"
    assert result["data"]["meta"]["actual_view"] == "flat"
    assert result["diagnostics"][0]["code"] == "view.fallback"
    assert len(result["data"]["result"]["items"]) == 20
    assert "tags" not in result["data"]["result"]["items"][0]


def test_multiple_roots_return_error(root):
    code, result = _list(root, "--root", str(root))
    assert code == 2
    assert result["diagnostics"][0]["code"] == "docs.multiple_roots"


def test_selections_do_not_cross_type_tag_or_directory_boundaries(root):
    _fixture(root)
    (root / "ideas-archive").mkdir()
    (root / "ideas-archive" / "extra.md").write_text(
        "---\ndoc_type: idea\ntags: [fixture]\n---\n# Extra\n", encoding="utf-8",
    )
    (root / "ideas" / "note.md").write_text("---\ndoc_type: note\ntags: [fixture]\n---\n# Note\n",
                                           encoding="utf-8")
    (root / "ideas" / "untagged.md").write_text("---\ndoc_type: idea\n---\n# Untagged\n", encoding="utf-8")
    code, result = _list(root, "--within", "ideas", "--type", "idea", "--tag", "fixture", "--limit", "1")
    assert code == 0
    meta = result["data"]["meta"]
    assert meta["total"] == 20
    replaced_offset = meta["next_cursor"].rsplit(":", 1)[0] + ":20"
    assert _list(root, "--within", "ideas", "--type", "idea", "--tag", "fixture",
                 "--cursor", replaced_offset)[0] == 2


def test_read_detects_late_corpus_change(root, sample_md, monkeypatch):
    original = DatasetContext.scan_and_validate

    def scan_and_change(ctx, *args, **kwargs):
        result = original(ctx, *args, **kwargs)
        sample_md.write_text("# changed during scan\n", encoding="utf-8")
        return result

    monkeypatch.setattr(DatasetContext, "scan_and_validate", scan_and_change)
    code, result = _list(root)
    assert code == 6
    assert result["diagnostics"][0]["code"] == "generation.incomplete"


def test_scan_failure_becomes_incomplete_result(root, monkeypatch):
    def blocked(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(DatasetContext, "scan", blocked)
    code, result = _list(root)
    assert code == 6
    assert result["data"]["meta"]["complete"] is False
    assert result["diagnostics"][0]["code"] == "generation.incomplete"


@pytest.mark.parametrize("args", [
    ("--limit", "0"), ("--fields", "bad"), ("--within", "../ideas"),
    ("--fields", "title", "--exclude-fields", "status"),
])
def test_main_returns_exit_status_for_invalid_list(root, monkeypatch, capsys, args):
    monkeypatch.setattr(sys, "argv", ["todoc", "docs", "list", "--root", str(root), *args])
    with pytest.raises(SystemExit) as result:
        main()
    assert result.value.code == 2
    assert json.loads(capsys.readouterr().out)["schema_version"] == 2


def test_common_metadata_selection_and_schema(root):
    schema = {
        "type": "object",
        "required": ["title", "priority"],
        "properties": {"priority": {"type": "integer", "minimum": 1}},
    }
    (root / ".todoc/document-metadata.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    sources = {
        "first.md": "---\nid: doc:first\ntitle: First\ndoc_type: idea\npriority: 2\ntags: [fast, cli]\n---\n",
        "second.json": json.dumps({"meta": {
            "id": "doc:second", "title": "Second", "doc_type": "plan",
            "priority": 2, "tags": ["fast"],
        }}),
        "third.md": "---\nid: doc:third\ntitle: Third\ndoc_type: agent-skill\npriority: 4\n---\n",
    }
    for name, text in sources.items():
        (root / name).write_text(text, encoding="utf-8")
    flags = ("--type", "idea|plan", "--attr-priority", "2",
             "--tag-in", "fast|shared", "--fields", "attributes")
    code, body = _list(root, *flags, "--limit", "1")
    assert code == 0, body
    assert body["data"]["meta"]["total"] == 2
    assert body["data"]["result"]["items"][0]["attributes"]["priority"] == 2
    cursor = body["data"]["meta"]["next_cursor"]
    code, body = _list(root, "--cursor", cursor, "--attr-priority=2", "--tag-in", "shared|fast",
                       "--type", "plan", "--type", "idea")
    assert code == 0
    assert body["data"]["result"]["items"][0]["id"] == "doc:second"
    assert _list(root, "--attr-missing", "value")[0] == 2
    assert _list(root, "--attr-priority", "high")[0] == 2
    code, body = _list(root, "--type", "plan", "--filter-fields")
    assert code == 0 and body["data"]["result"]["declared"]["priority"]["type"] == "integer"
    (root / "second.json").write_text('{"meta":{"doc_type":"plan"}}', encoding="utf-8")
    result = CliRunner().invoke(cli, ["validate", "--root", str(root), "--all"])
    assert result.exit_code == 3
    diagnostics = json.loads(result.output)["diagnostics"]
    assert any(item["code"] == "document.schema_violation"
               and item["location"]["pointer"] == "/meta"
               and "priority" in item["message"] for item in diagnostics)


def test_filter_file_distinguishes_null_from_absence_and_supports_dates(root, tmp_path):
    (root / "dated.json").write_text(
        '{"meta":{"title":"Dated","updated":"2026-11-27","status":null}}', encoding="utf-8",
    )
    (root / "previous.json").write_text(
        '{"meta":{"title":"Previous","updated":"2026-11-24"}}', encoding="utf-8",
    )
    path = tmp_path / "predicate.json"

    def write(value):
        path.write_text(json.dumps({"schema_version": 1, "conditions": [
            {"field": "status", "op": "eq", "value": None},
            {"field": "updated", "op": "gte", "value": value},
        ]}), encoding="utf-8")

    write("2026-11-25")
    code, body = _list(root, "--filter-file", str(path), "--file-format", "json")
    assert code == 0
    assert [item["path"] for item in body["data"]["result"]["items"]] == ["dated.json"]
    write("2026-02-30")
    assert _list(root, "--filter-file", str(path))[0] == 2


@pytest.mark.parametrize("extension", ["md", "json"])
def test_structured_metadata_edit_preserves_document_and_validates(root, tmp_path, extension):
    schema = {
        "required": ["title"],
        "properties": {"priority": {"type": "integer"}},
    }
    (root / ".todoc/document-metadata.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    target = root / f"document.{extension}"
    attributes = {"id": "doc:example", "title": "Example", "doc_type": "note", "unused": "retired"}
    if extension == "md":
        header = "\n".join(f"{key}: {value}" for key, value in attributes.items())
        target.write_bytes(f"---\r\n{header.replace(chr(10), chr(13) + chr(10))}\r\n---\r\n# Body\r\n".encode())
    else:
        target.write_text(json.dumps({"meta": attributes, "body": {"text": "# Body"}}), encoding="utf-8")
    patch = tmp_path / "metadata.json"
    patch.write_text(json.dumps({"metadata": [
        {"op": "set", "field": "priority", "value": 5},
        {"op": "remove", "field": "unused"},
        {"op": "add_item", "field": "tags", "value": "fast"},
    ]}), encoding="utf-8")
    args = ["docs", "edit", "--root", str(root), "--id", "doc:example", "--patch-file", str(patch)]
    runner = CliRunner()
    before = target.read_bytes()
    preview = runner.invoke(cli, [*args, "--preview"])
    assert preview.exit_code == 0, (preview.output, preview.exception)
    review = json.loads(preview.output)["data"]["result"]
    assert review["attributes"]["priority"] == 5
    assert "unused" not in review["attributes"] and review["diff"]
    assert target.read_bytes() == before
    updated = runner.invoke(cli, [*args, "--apply", "--if-hash", review["expected_hash"]])
    assert updated.exit_code == 0, (updated.output, updated.exception)
    assert _list(root, "--attr-priority", "5")[1]["data"]["meta"]["total"] == 1
    if extension == "md":
        assert target.read_bytes().endswith(b"---\r\n# Body\r\n")
    else:
        assert json.loads(target.read_text(encoding="utf-8"))["body"] == {"text": "# Body"}
    assert runner.invoke(cli, [*args, "--apply", "--if-hash", review["expected_hash"]]).exception.code == "write.hash_mismatch"
    after = target.read_bytes()
    patch.write_text('{"metadata":[{"op":"remove","field":"title"}]}', encoding="utf-8")
    rejected = runner.invoke(cli, [*args, "--preview"])
    assert rejected.exception.code == "document.schema_violation"
    assert target.read_bytes() == after


def test_search_metadata_and_unicode_budget(root, sample_md):
    base = ["docs", "search", "--root", str(root)]
    runner = CliRunner()
    discovery = runner.invoke(cli, ["docs", "search"])
    response = json.loads(discovery.output)
    Draft202012Validator(V2_SCHEMA).validate(response)
    assert response["data"]["executed"] is False
    result = runner.invoke(cli, [*base, "--file-format", "markdown", "--type", "note|unknown"])
    assert result.exit_code == 0
    assert any(item["path"] == "notes/design.md" for item in json.loads(result.output)["data"]["result"]["items"])
    (root / "unicode.md").write_text("# 🐍пример\n\nпример кириллицы и emoji 🐍\n", encoding="utf-8")
    search = runner.invoke(cli, [*base, "--query", "пример", "--budget", "4"])
    assert search.exit_code == 0
    snippet = json.loads(search.output)["data"]["result"]["items"][0]["snippet"]
    assert len(snippet["text"]) == 4 and snippet["snippet_truncated"]
    read = runner.invoke(cli, ["docs", "read", "--root", str(root), "--id", "doc:unicode.md",
                               "--line-range", "1-1", "--budget", "4"])
    assert read.exit_code == 0
    data = json.loads(read.output)["data"]["result"]
    assert data["text"] == "# 🐍п" and data["truncated"] is True


def test_document_schema_install_preview_and_create_in_both_formats(tmp_path):
    runner = CliRunner()
    args = ["--root", str(tmp_path)]
    initialized = runner.invoke(cli, ["init", "--apply", *args, "--document-metadata"])
    assert initialized.exit_code == 0, initialized.exception
    schema_path = tmp_path / ".todoc" / "document-metadata.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert set(schema["required"]) == {"id", "title", "lang", "created", "updated"}
    schema["required"].append("priority")
    schema["properties"]["priority"] = {"type": "integer"}
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    body = runner.invoke(cli, ["types", "show", "note", "--kind", "doc_type", *args])
    assert "priority" in json.loads(body.output)["data"]["result"]["document_metadata"]["required"]
    attributes = tmp_path / ".todoc" / "custom.json"
    attributes.write_text('{"priority":2}', encoding="utf-8")
    for extension in ("md", "json"):
        path = f"example.{extension}"
        command = ["docs", "new", *args, "--type", "note", "--title", "Example", "--path", path]
        assert runner.invoke(cli, command).exception.code == "document.schema_violation"
        command += ["--attributes-file", str(attributes)]
        preview = runner.invoke(cli, [*command, "--preview"])
        assert preview.exit_code == 0, preview.exception
        assert not (tmp_path / path).exists()
        assert json.loads(preview.output)["data"]["result"]["attributes"]["priority"] == 2
        created = runner.invoke(cli, [*command, "--apply"])
        assert created.exit_code == 0, created.exception
    report = runner.invoke(cli, ["types", "metadata", *args])
    assert report.exit_code == 0, report.exception
    assert json.loads(report.output)["data"]["result"]["items"] == []
    code, selected = _list(tmp_path, "--attr-priority", "2")
    assert code == 0 and selected["data"]["meta"]["total"] == 2


def test_records_metadata_filters_and_review_first_edit(root, sample_record):
    value = json.loads(sample_record.read_text(encoding="utf-8"))
    record_id = value["record_id"]
    value.update(details={"group": "morning"}, tags=["health", "running"])
    sample_record.write_text(json.dumps(value), encoding="utf-8")
    filters = root / ".todoc" / "record-filter.json"
    filters.write_text(json.dumps({"schema_version": 1, "conditions": [
        {"op": "eq", "field": "details.group", "value": "morning"},
    ]}), encoding="utf-8")
    runner = CliRunner()
    root_args = ["--root", str(root)]
    for cmd in ("list", "query"):
        result = runner.invoke(cli, ["records", cmd, *root_args, "--filter-file", str(filters),
                                      "--tag-all", "health|running"])
        assert result.exit_code == 0, result.exception
        assert [item["record_id"] for item in json.loads(result.output)["data"]["result"]["items"]] == [record_id]
    patch = root / ".todoc" / "patch.json"
    patch.write_text('{"metadata":[{"op":"remove_item","field":"tags","value":"running"}]}', encoding="utf-8")
    args = ["records", "edit", *root_args, "--id", record_id, "--patch-file", str(patch)]
    before = sample_record.read_bytes()
    preview = runner.invoke(cli, [*args, "--preview"])
    assert preview.exit_code == 0, preview.exception
    assert sample_record.read_bytes() == before
    review = json.loads(preview.output)["data"]["result"]
    assert review["attributes"]["tags"] == ["health"]
    applied = runner.invoke(cli, [*args, "--apply", "--if-hash", review["expected_hash"]])
    assert applied.exit_code == 0, applied.exception
    read = json.loads(sample_record.read_text(encoding="utf-8"))
    assert read["record_id"] == record_id and read["tags"] == ["health"]
