# tests/cli/test_cli_state.py — Задача 2 плана agent-state: CLI-группа state
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


def _init(runner, tmp_path):
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path), "--no-input"]).exit_code == 0


def test_state_set_get_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    runner = CliRunner()
    _init(runner, tmp_path)
    r1 = _run(runner, ["--root", str(tmp_path), "state", "set", "--apply",
                       "context.current_project", "shop"])
    assert r1.exit_code == 0, r1.output
    data = _json(r1)["data"]["result"]
    assert data["key"] == "context.current_project" and data["value"] == "shop"
    assert data["updated_at"].startswith("20")
    r2 = _run(runner, ["--root", str(tmp_path), "state", "get", "context.current_project"])
    assert r2.exit_code == 0
    assert _json(r2)["data"]["result"]["value"] == "shop"


def test_state_get_missing_returns_null(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    runner = CliRunner()
    _init(runner, tmp_path)
    r = _run(runner, ["--root", str(tmp_path), "state", "get", "context.current_project"])
    assert r.exit_code == 0
    assert _json(r)["data"]["result"]["value"] is None


def test_state_unknown_key_json_diagnostic(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    runner = CliRunner()
    _init(runner, tmp_path)
    r = _run(runner, ["--root", str(tmp_path), "state", "set", "--apply", "foo.bar", "x"])
    assert r.exit_code != 0
    assert isinstance(r.exception, TodocError)
    assert r.exception.code == "state.unknown_key"
    # Контракт K48 (реальный процесс): ok:false конверт в stdout с кодом диагностики.
    import os
    import subprocess
    import sys
    proc = subprocess.run(
        [sys.executable, "-m", "todoc.cli", "--root", str(tmp_path), "state", "set", "--apply", "foo.bar", "x"],
        capture_output=True, text=True,
        env=dict(os.environ, XDG_STATE_HOME=str(tmp_path / "state")))
    assert proc.returncode == 3
    envelope = json.loads(proc.stdout)
    assert envelope["ok"] is False
    assert envelope["diagnostics"][0]["code"] == "state.unknown_key"


def test_state_invalid_value_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    runner = CliRunner()
    _init(runner, tmp_path)
    r = _run(runner, ["--root", str(tmp_path), "state", "set", "--apply", "context.current_project", ""])
    assert r.exit_code == 3
    assert isinstance(r.exception, TodocError)
    assert r.exception.code == "state.invalid_value"


def test_state_list_full_and_prefix(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("todoc.application.state.ALLOWED_KEYS_V1",
                        ("context.current_project", "context.branch"))
    runner = CliRunner()
    _init(runner, tmp_path)
    assert _run(runner, ["--root", str(tmp_path), "state", "set", "--apply", "context.current_project", "shop"]).exit_code == 0
    assert _run(runner, ["--root", str(tmp_path), "state", "set", "--apply", "context.branch", "main"]).exit_code == 0
    r = _run(runner, ["--root", str(tmp_path), "state", "list"])
    assert {row["key"]: row["value"] for row in _json(r)["data"]["result"]["items"]} == {"context.current_project": "shop", "context.branch": "main"}
    r = _run(runner, ["--root", str(tmp_path), "state", "list", "--prefix", "context.branch"])
    assert {row["key"]: row["value"] for row in _json(r)["data"]["result"]["items"]} == {"context.branch": "main"}


def test_state_unset_removed_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    runner = CliRunner()
    _init(runner, tmp_path)
    _run(runner, ["--root", str(tmp_path), "state", "set", "--apply", "context.current_project", "shop"])
    r = _run(runner, ["--root", str(tmp_path), "state", "unset", "--apply", "context.current_project"])
    assert _json(r)["data"]["result"]["removed"] is True
    r = _run(runner, ["--root", str(tmp_path), "state", "unset", "--apply", "context.current_project"])
    assert _json(r)["data"]["result"]["removed"] is False


def test_state_file_outside_dataset_root(tmp_path, monkeypatch):
    # XDG_STATE_HOME — сосед корня датасета, не внутри: state.json вне данных
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    runner = CliRunner()
    kb = tmp_path / "kb"
    _init(runner, kb)
    before = {p.relative_to(kb).as_posix() for p in kb.rglob("*")}
    assert _run(runner, ["--root", str(kb), "state", "set", "--apply",
                         "context.current_project", "shop"]).exit_code == 0
    after = {p.relative_to(kb).as_posix() for p in kb.rglob("*")}
    assert before == after  # датасет не тронут
    state_dir = tmp_path / "state" / "todoc"
    assert any(f.name.startswith("state-") for f in state_dir.iterdir())
