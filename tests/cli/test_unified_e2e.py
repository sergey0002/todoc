"""Scripted conformance probes for the agent's bounded navigation workflow."""

import json
import sys

import click
import pytest
from click.testing import CliRunner

from todoc.cli import cli
from todoc.errors import TodocError


def _run(root, *args):
    return CliRunner().invoke(cli, ["--root", str(root), *args])


def _json(result):
    assert result.exit_code == 0, (result.output, result.exception)
    envelope = json.loads(result.output)
    assert envelope["ok"] and envelope["schema_version"] == 2 and "guidance" in envelope
    return envelope["data"]


def test_search_read_review_write_history_and_relations_in_one_workflow(root, sample_md, sample_record, tmp_path):
    search = _json(_run(root, "docs", "search", "--query", "refresh rotation", "--fields", "id,path,snippet"))
    hit = search["result"]["items"][0]
    assert hit["id"] == "doc:notes/design.md"
    assert hit["snippet"]["line_start"] > 0
    read = _json(_run(root, "docs", "read", "--id", hit["id"], "--section", "Decision",
                     "--fields", "text", "--budget", "20"))["result"]
    assert read["text"] == "## Decision\n\nWe use "
    assert read["truncated"]
    records = _json(_run(root, "records", "list", "--relation", "performed_by=person:sergei", "--limit", "1"))
    assert records["meta"]["total"] == 1
    record_id = records["result"]["items"][0]["record_id"]
    graph = _json(_run(root, "relations", "graph", "--from", record_id))
    assert graph["result"]["edges"][0]["to"] == "person:sergei"

    patch = tmp_path / "patch.json"
    patch.write_text('{"ops":[{"op":"insert_after","line":8,"text":"Новая строка"}]}', encoding="utf-8")
    before = sample_md.read_bytes()
    args = ("docs", "edit", "--id", hit["id"], "--patch-file", str(patch))
    preview = _json(_run(root, *args))["result"]
    assert preview["preview"] and sample_md.read_bytes() == before
    assert not (root / ".todoc/history/journal.jsonl").exists()
    applied = _json(_run(root, *args, "--if-hash", preview["expected_hash"], "--apply"))["result"]
    assert applied["applied"]
    after = _json(_run(root, "docs", "read", "--id", hit["id"], "--section", "Decision"))["result"]
    assert "Новая строка" in after["text"]
    history = _json(_run(root, "log", "--path", hit["path"], "--limit", "1"))["result"]["items"]
    assert history[0]["paths"][0]["after"] == after["hash"]


def test_scripted_recipe_stops_on_first_failed_probe(root, sample_md):
    commands = [
        ("docs", "list", "--fields", "unknown"),
        ("docs", "read", "--id", "doc:notes/design.md"),
    ]
    attempts = []
    for argv in commands:
        attempts.append(argv)
        result = _run(root, *argv)
        if result.exit_code != 0:
            assert isinstance(result.exception, (TodocError, SystemExit))
            break
    assert len(attempts) == 1


def test_each_group_level_inherits_and_overrides_common_options(root, sample_md, tmp_path):
    default = _run(root, "docs", "--output", "table", "read", "--id", "doc:notes/design.md")
    assert default.exit_code == 0 and "guidance:" in default.output
    explicit = _run(root, "docs", "--output", "table", "read", "--output", "json", "--id", "doc:notes/design.md")
    assert _json(explicit)["result"]["path"] == "notes/design.md"
    group = _run(tmp_path / "missing", "docs", "--root", str(root), "list")
    assert _json(group)["meta"]["scope"]["dataset_id"]
    discovery = _run(root, "docs", "--output", "markdown")
    assert discovery.exit_code == 0 and "executed: False" in discovery.output
    repeat = _run(root, "docs", "--root", str(root), "--root", str(root), "list")
    assert json.loads(repeat.output)["diagnostics"][0]["code"] == "docs.multiple_roots"


def test_projected_read_rejects_changed_or_unreadable_generation_metadata(root, sample_md):
    from todoc.service import DatasetContext

    ctx = DatasetContext(root)
    ctx.rebuild_index(observe=False)
    meta = ctx.store.current_dir / "meta.json"
    for bad in (b"{}", b"\xff"):
        meta.write_bytes(bad)
        payload = ctx.read_index(sections=())
        assert payload["documents"] and "generation_id" not in payload


def test_main_reports_click_errors_without_command_context(monkeypatch, capsys):
    import todoc.cli as entry

    def fail(*args, **kwargs):
        raise click.ClickException("Cannot process the command")

    monkeypatch.setattr(entry, "cli", fail)
    with pytest.raises(SystemExit) as error:
        entry.main()
    assert error.value.code == 2
    assert json.loads(capsys.readouterr().out)["diagnostics"][0]["code"] == "usage.error"


def test_main_uses_nearest_parsed_output_for_early_errors(monkeypatch, capsys):
    import todoc.cli as entry

    monkeypatch.setattr(sys, "argv", ["todoc", "--output", "table", "records", "--bogus"])
    with pytest.raises(SystemExit) as error:
        entry.main()
    assert error.value.code == 2
    out = capsys.readouterr().out
    assert out.startswith("ok: False") and "usage.error" in out


def test_main_does_not_leak_output_between_invocations(monkeypatch, capsys):
    import todoc.cli as entry

    monkeypatch.setattr(sys, "argv", ["todoc", "--output", "table", "records", "--bogus"])
    with pytest.raises(SystemExit):
        entry.main()
    capsys.readouterr()
    monkeypatch.setattr(sys, "argv", ["todoc", "records", "--bogus"])
    with pytest.raises(SystemExit):
        entry.main()
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["diagnostics"][0]["code"] == "usage.error"
    assert envelope["data"]["meta"]["command"] == "records"
    assert envelope["next_actions"][0]["argv"] == ["todoc", "records", "--help"]


def test_main_use_case_error_keeps_group_output(root, monkeypatch, capsys):
    import todoc.cli as entry

    monkeypatch.setattr(sys, "argv", ["todoc", "--output", "table", "--root", str(root),
                                      "docs", "read", "--id", "doc:absent"])
    with pytest.raises(SystemExit) as error:
        entry.main()
    assert error.value.code == 3
    out = capsys.readouterr().out
    assert out.startswith("ok: False") and "docs.not_found" in out


def test_main_use_case_error_honors_leaf_output_override(root, monkeypatch, capsys):
    import todoc.cli as entry

    monkeypatch.setattr(sys, "argv", ["todoc", "--output", "table", "--root", str(root),
                                      "docs", "read", "--id", "doc:absent", "--output", "json"])
    with pytest.raises(SystemExit) as error:
        entry.main()
    assert error.value.code == 3
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["diagnostics"][0]["code"] == "docs.not_found"


def test_read_and_preview_work_with_read_only_dataset_and_state(root, sample_md, tmp_path, monkeypatch):
    home = tmp_path / "home"
    state = tmp_path / "state"
    for directory in (home, state):
        directory.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    monkeypatch.setenv("TODOC_ROOT", str(root))
    patch = tmp_path / "edit.json"
    patch.write_text('{"ops":[{"line":5,"text":"# preview"}]}', encoding="utf-8")
    files = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    dirs = [root, home, state, *[p for p in root.rglob("*") if p.is_dir()]]
    for p in dirs:
        p.chmod(0o555)
    try:
        _json(_run(root, "docs", "list", "--within", "notes"))
        _json(_run(root, "docs", "search", "--query", "rotation"))
        _json(_run(root, "docs", "edit", "--id", "doc:notes/design.md", "--patch-file", str(patch), "--preview"))
        _json(_run(root, "records", "list"))
        _json(_run(root, "log"))
        assert not list(home.iterdir()) and not list(state.iterdir())
        assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == files
    finally:
        for p in dirs:
            p.chmod(0o755)
