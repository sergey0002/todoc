"""End-to-end: init -> docs -> check -> search -> read -> records -> aggregate."""

import json

from click.testing import CliRunner

from todoc.cli import cli
from todoc.errors import TodocError


def _invoke(runner, args):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


def test_full_flow(root, sample_md, sample_csv, sample_record):
    runner = CliRunner()
    # Check is clean.
    result = _invoke(runner, ["--root", str(root), "check", "--output", "json"])
    assert result.exit_code == 0, result.output
    # Search finds the design doc.
    result = _invoke(runner, ["--root", str(root), "docs", "search", "--query", "refresh token", "--output", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["data"]["meta"]["total"] >= 1
    # Read bounded section.
    result = _invoke(runner, ["--root", str(root), "docs", "read", "--id", "doc:notes/design.md", "--section", "Decision", "--output", "json"])
    assert result.exit_code == 0
    assert "refresh token" in json.loads(result.output)["data"]["result"]["text"]
    # Aggregate with provenance.
    result = _invoke(runner, ["--root", str(root), "records", "aggregate", "--metric", "volume", "--type", "workout", "--output", "json"])
    assert result.exit_code == 0
    agg = json.loads(result.output)["data"]["result"]
    assert agg["units"] == "kg"
    assert agg["formula"] == "sum(volume)"
    assert agg["items"][0]["incoming_ids"] == ["workout:2026-11-24-sergei-01"]
    # Reads leave a cold dataset untouched. After explicit publication the
    # index is still rebuildable from sources.
    import shutil
    index = root / ".todoc" / "index"
    assert not index.exists()
    result = _invoke(runner, ["--root", str(root), "index", "rebuild", "--apply", "--output", "json"])
    assert result.exit_code == 0, result.output
    shutil.rmtree(index)
    result = _invoke(runner, ["--root", str(root), "index", "rebuild", "--apply", "--output", "json"])
    assert result.exit_code == 0
    result = _invoke(runner, ["--root", str(root), "index", "status", "--output", "json"])
    assert json.loads(result.output)["data"]["result"]["datasets"][0]["current"] is True


def test_relocation(root, sample_md, tmp_path):
    """DATA_ROOT moves to another absolute path and reopens without fixes."""
    import shutil
    moved = tmp_path / "moved" / "knowledge"
    moved.parent.mkdir(parents=True)
    shutil.copytree(root, moved)
    runner = CliRunner()
    result = _invoke(runner, ["--root", str(moved), "check", "--output", "json"])
    assert result.exit_code == 0, result.output
    result = _invoke(runner, ["--root", str(moved), "docs", "search", "--query", "refresh", "--output", "json"])
    assert result.exit_code == 0
    assert json.loads(result.output)["data"]["meta"]["total"] >= 1
