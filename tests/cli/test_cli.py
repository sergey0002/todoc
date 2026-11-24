import json

from click.testing import CliRunner

from todoc.cli import cli
from todoc.errors import TodocError


def _run(runner, args):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


def _json(result):
    return json.loads(result.output)


def test_help_and_version():
    runner = CliRunner()
    assert _run(runner, ["--help"]).exit_code == 0
    assert _run(runner, ["--version"]).exit_code == 0


def test_no_args_discovery():
    runner = CliRunner()
    result = _run(runner, [])
    assert result.exit_code == 0
    assert "todoc" in result.output


def test_init_check_scan(root):
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "check", "--output", "json"])
    assert result.exit_code == 0, result.output
    data = _json(result)
    assert data["ok"] is True
    result = _run(runner, ["--root", str(root), "scan", "--output", "json"])
    assert result.exit_code == 0
    result = _run(runner, ["--root", str(root), "check-config", "--output", "json"])
    assert result.exit_code == 0


def test_validate(root, sample_md):
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "validate", "--all", "--output", "json"])
    assert result.exit_code == 0, result.output


def test_index_status_rebuild(root, sample_md):
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "index", "rebuild", "--output", "json"])
    assert result.exit_code == 0, result.output
    result = _run(runner, ["--root", str(root), "index", "status", "--output", "json"])
    assert result.exit_code == 0
    assert _json(result)["data"]["datasets"][0]["current"] is True


def test_explain_path(root, sample_md):
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "explain-path", "notes/design.md", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert _json(result)["data"]["path"] == "notes/design.md"


def test_explain_path_missing(root):
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "explain-path", "missing.md", "--output", "json"])
    assert result.exit_code == 3


def test_docs_new_search_read(root, sample_md):
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "docs", "new", "--title", "Release decision", "--dir", "inbox", "--template", "note", "--output", "json"])
    assert result.exit_code == 0, result.output
    result = _run(runner, ["--root", str(root), "docs", "search", "--query", "refresh token", "--limit", "10", "--output", "json"])
    assert result.exit_code == 0, result.output
    data = _json(result)
    assert data["data"]["total"] >= 1
    doc_id = data["data"]["items"][0]["id"]
    result = _run(runner, ["--root", str(root), "docs", "read", "--id", doc_id, "--section", "Decision", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert "refresh token" in _json(result)["data"]["text"]


def test_docs_read_pointer_and_columns(root, sample_record, sample_csv):
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "docs", "search", "--query", "workout", "--output", "json"])
    assert result.exit_code == 0
    # Read JSON record via docs read pointer.
    result = _run(runner, ["--root", str(root), "docs", "read", "--id", "doc:records/workouts/w1.json", "--pointer", "/date", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert _json(result)["data"]["value"] == "2026-11-24"
    # Read CSV columns.
    result = _run(runner, ["--root", str(root), "docs", "read", "--id", "doc:data/runs.csv", "--columns", "run_id,status", "--rows", "1", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert _json(result)["data"]["rows"] == [{"run_id": "r1", "status": "ok"}]


def test_docs_read_missing(root):
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "docs", "read", "--id", "doc:missing.md", "--output", "json"])
    assert result.exit_code == 3


def test_docs_tree(root, sample_md):
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "docs", "tree", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert _json(result)["data"]["total_documents"] >= 1


def test_docs_edit_preview_apply(root, sample_md, tmp_path):
    runner = CliRunner()
    patch = tmp_path / "patch.json"
    patch.write_text(json.dumps({"ops": [{"line": 1, "text": "# Changed"}]}))
    result = _run(runner, ["--root", str(root), "docs", "edit", "--id", "doc:notes/design.md", "--patch-file", str(patch), "--output", "json"])
    assert result.exit_code == 0, result.output
    assert _json(result)["data"]["preview"] is True
    result = _run(runner, ["--root", str(root), "docs", "edit", "--id", "doc:notes/design.md", "--patch-file", str(patch), "--apply", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert (root / "notes" / "design.md").read_text().splitlines()[0] == "# Changed"


def test_records_create_preview_apply(root, tmp_path):
    runner = CliRunner()
    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps({"record_id": "workout:2026-11-25-01", "entity_type": "workout", "date": "2026-11-25"}))
    result = _run(runner, ["--root", str(root), "records", "create", "--type", "workout", "--input-file", str(draft), "--preview", "--output", "json"])
    assert result.exit_code == 0, result.output
    result = _run(runner, ["--root", str(root), "records", "create", "--type", "workout", "--input-file", str(draft), "--apply", "--output", "json"])
    assert result.exit_code == 0, result.output


def test_records_list_query_aggregate_read(root, sample_record):
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "records", "list", "--type", "workout", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert _json(result)["data"]["total"] == 1
    query_file = root / ".todoc" / "queries" / "q.json"
    query_file.write_text(json.dumps({"entity_type": "workout", "limit": 10}))
    result = _run(runner, ["--root", str(root), "records", "query", "--query-file", str(query_file), "--output", "json"])
    assert result.exit_code == 0, result.output
    result = _run(runner, ["--root", str(root), "records", "aggregate", "--metric", "volume", "--type", "workout", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert _json(result)["data"]["groups"]["all"] == 100.0
    result = _run(runner, ["--root", str(root), "records", "read", "--id", "workout:2026-11-24-sergei-01", "--output", "json"])
    assert result.exit_code == 0, result.output


def test_records_read_missing(root):
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "records", "read", "--id", "workout:missing", "--output", "json"])
    assert result.exit_code == 3


def test_relations_graph(root, sample_record):
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "relations", "graph", "--from", "person:sergei", "--type", "performed_by", "--depth", "2", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert _json(result)["data"]["total"] >= 1


def test_types_list_show_guide(root):
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "types", "list", "--output", "json"])
    assert result.exit_code == 0
    assert "workout" in _json(result)["data"]["entity_types"]
    result = _run(runner, ["--root", str(root), "types", "show", "workout", "--output", "json"])
    assert result.exit_code == 0
    result = _run(runner, ["--root", str(root), "types", "show", "ghost", "--output", "json"])
    assert result.exit_code == 3
    result = _run(runner, ["--root", str(root), "types", "guide", "--format", "markdown", "--output", "json"])
    assert result.exit_code == 0
    result = _run(runner, ["--root", str(root), "types", "guide", "--format", "json", "--out", ".todoc/generated/types-reference.md", "--output", "json"])
    assert result.exit_code == 0
    assert (root / ".todoc" / "generated" / "types-reference.md").is_file()


def test_fix_preview_apply(root):
    (root / "ops").mkdir(parents=True, exist_ok=True)
    (root / "ops" / "runbook.md").write_text("# Runbook\n", encoding="utf-8")
    (root / "notes").mkdir(parents=True, exist_ok=True)
    (root / "notes" / "broken.md").write_text("# Broken\n\nSee [runbook](../ops/runbok.md).\n", encoding="utf-8")
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "check", "--output", "json"])
    assert result.exit_code == 3  # issues_found -> validation error exit
    # Find diagnostic id via validate.
    result = _run(runner, ["--root", str(root), "validate", "--all", "--output", "json"])
    diags = _json(result)["data"]["datasets"][0]["diagnostics"]
    target = next(d for d in diags if d["code"] == "markdown.link.target_missing")
    result = _run(runner, ["--root", str(root), "fix", "--diagnostic", target["id"], "--preview", "--output", "json"])
    assert result.exit_code == 0, result.output
    result = _run(runner, ["--root", str(root), "fix", "--diagnostic", target["id"], "--apply", "--output", "json"])
    assert result.exit_code == 0, result.output


def test_fix_missing_diagnostic(root):
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "fix", "--diagnostic", "diag_missing", "--preview", "--output", "json"])
    assert result.exit_code == 3


def test_doctor_status(root, sample_md):
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "doctor", "--output", "json"])
    assert result.exit_code == 0, result.output
    result = _run(runner, ["--root", str(root), "doctor", "--check", "config", "--output", "json"])
    assert result.exit_code == 0
    result = _run(runner, ["--root", str(root), "status", "--output", "json"])
    assert result.exit_code == 0


def test_multi_root(root, tmp_path):
    from todoc.config import init_dataset
    root2 = tmp_path / "research"
    root2.mkdir()
    init_dataset(root2)
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "--root", str(root2), "check", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert len(_json(result)["data"]["datasets"]) == 2


def test_missing_root():
    runner = CliRunner()
    result = _run(runner, ["check", "--output", "json"])
    assert result.exit_code == 3
