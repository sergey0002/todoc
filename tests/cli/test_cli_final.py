"""Final CLI edge-branch tests."""

import json
import os
import subprocess
import sys
from pathlib import Path

from click.testing import CliRunner

from todoc.cli import cli
from todoc.errors import TodocError
from todoc.service import DatasetContext


def _run(runner, args):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


def _json(result):
    return json.loads(result.output)


def test_docs_read_markdown_full(root, sample_md):
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "docs", "read", "--id", "doc:notes/design.md", "--output", "json"])
    assert result.exit_code == 0, result.output
    data = _json(result)["data"]["result"]
    assert data["title"] == "Design"
    assert data["headings"][0]["title"] == "Design"
    assert "refresh token" in data["text"]


def test_docs_read_json_no_pointer(root, sample_record):
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "docs", "read", "--id", "doc:records/workouts/w1.json", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert _json(result)["data"]["result"]["value"]["record_id"] == "workout:2026-11-24-sergei-01"


def test_records_read_unknown_view(root, sample_record):
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "records", "read", "--id", "workout:2026-11-24-sergei-01", "--view", "ghost", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert "date" in _json(result)["data"]["result"]["data"]


def test_fix_cannot_apply(root, monkeypatch):
    real = DatasetContext.scan_and_validate

    def fake(self, **kwargs):
        _f, _d, _r, _rel, diagnostics = real(self, **kwargs)
        diagnostics.append({
            "dataset_id": self.dataset_id, "id": "diag_crafted", "code": "markdown.link.target_missing",
            "severity": "error", "path": "notes/x.md", "location": {}, "evidence": "no link here",
            "message": "crafted", "suggested_fixes": [{"kind": "replace_link_target", "replacement": "y.md"}],
        })
        return _f, _d, _r, _rel, diagnostics

    monkeypatch.setattr(DatasetContext, "scan_and_validate", fake)
    runner = CliRunner()
    result = _run(runner, ["--root", str(root), "fix", "--diagnostic", "diag_crafted", "--apply", "--output", "json"])
    assert result.exit_code == 3


def test_cli_module_run_as_main(root, monkeypatch):
    import runpy
    script = Path(__file__).resolve().parents[2] / "src" / "todoc" / "cli.py"
    monkeypatch.setattr(sys, "argv", ["cli.py", "--root", str(root), "check", "--output", "json"])
    runpy.run_path(str(script), run_name="__main__")  # covers the __main__ guard in cli.py


def test_cli_script_as_main(root):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    script = Path(__file__).resolve().parents[2] / "src" / "todoc" / "cli.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--root", str(root), "check", "--output", "json"],
        capture_output=True, text=True, env=env, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["ok"] is True
