"""Сквозной контракт CLI: K47 и K48 по всему перечню команд.

План (docs/plan/history-and-changes.md, §20) требует: «K47 и K48 должны быть
параметризованы по перечню команд, а не написаны на одну: иначе команда, добавленная
позже, пройдёт мимо проверки». Поэтому список команд здесь не зашит literально, а
вычитывается из самого CLI — новая команда попадает в проверку автоматически.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from todoc.cli import cli
from todoc.output.capabilities import UnifiedCommand, command_inventory

SRC = str(Path(__file__).resolve().parents[2] / "src")


INVENTORY = {entry.path: entry for entry in command_inventory(cli)}
LEAVES = [path for path, entry in INVENTORY.items() if not entry.group]


def _run_no_input(root: Path, argv: tuple[str, ...]) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = SRC
    return subprocess.run(
        [sys.executable, "-m", "todoc", "--root", str(root), "--output", "json",
         "--no-input", *argv],
        capture_output=True, text=True, env=env, timeout=120,
        stdin=subprocess.DEVNULL,  # K47: TTY нет вовсе
    )


def test_every_leaf_command_is_covered():
    """Страховка от молчаливого сужения списка: команд не меньше, чем в CLI."""
    assert INVENTORY[("docs", "flow")].group
    assert ("docs", "flow", "render") in LEAVES
    assert ("docs", "flow") not in LEAVES
    assert len(LEAVES) >= 45, f"слишком мало команд: {len(LEAVES)}"


def test_all_leaf_commands_use_the_common_handler():
    for path in LEAVES:
        command = cli
        for part in path:
            command = command.commands[part]
        assert isinstance(command, UnifiedCommand), path


@pytest.mark.parametrize("output", ["json", "table", "markdown"])
def test_missing_required_input_returns_discovery_without_writes(tmp_path, output):
    result = CliRunner().invoke(cli, ["--output", output, "init"])
    assert result.exit_code == 0, result.output
    if output == "json":
        envelope = json.loads(result.output)
        assert envelope["data"]["executed"] is False
        assert envelope["data"]["meta"]["command"] == "init"
        assert any("--root" in item["spellings"] and item["required"]
                   for item in envelope["data"]["result"]["parameters"])
    else:
        assert "guidance:" in result.output and "--root" in result.output
    assert not list(tmp_path.iterdir())


def test_inventory_preserves_public_option_grammar():
    params = {p.name: p for p in INVENTORY[("docs", "search")].parameters}
    assert params["query"].required is False
    assert params["query"].spellings == ("--query",)
    assert params["roots"].multiple
    assert params["output"].default == "json"


@pytest.mark.parametrize("path", [path for path, entry in INVENTORY.items() if entry.group])
def test_groups_return_read_only_discovery(root, path):
    before = {file.relative_to(root): file.read_bytes() for file in root.rglob("*") if file.is_file()}
    response = _run_no_input(root, path)
    assert response.returncode == 0, response.stderr
    envelope = json.loads(response.stdout)
    assert envelope["schema_version"] == 2
    assert envelope["data"]["executed"] is False
    assert envelope["data"]["meta"]["command"] == (" ".join(path) or "todoc")
    assert envelope["guidance"]["items"] == []
    group = cli
    for part in path:
        group = group.commands[part]
    children = {name for name, command in group.commands.items() if not command.hidden}
    assert {command["name"] for command in envelope["data"]["result"]["commands"]} == children
    assert {file.relative_to(root): file.read_bytes() for file in root.rglob("*") if file.is_file()} == before


def test_discovery_keeps_selected_output_without_a_root(monkeypatch):
    monkeypatch.delenv("TODOC_ROOT", raising=False)
    root = CliRunner().invoke(cli, [])
    assert root.exit_code == 0
    assert json.loads(root.output)["data"]["meta"]["command"] == "todoc"
    nested = CliRunner().invoke(cli, ["--output", "markdown", "docs", "flow"])
    assert nested.exit_code == 0
    assert "guidance:" in nested.output
    assert "docs flow" in nested.output


@pytest.mark.parametrize("argv", LEAVES)
def test_k47_no_command_needs_a_tty(root, argv):
    """K47: при --no-input и закрытом stdin команда завершается, а не ждёт ввода."""
    result = _run_no_input(root, argv)
    # Главное — процесс вернулся (timeout убил бы его) и не оставил трейсбек ожидания.
    assert result.returncode is not None
    assert "Traceback (most recent call last)" not in result.stderr, result.stderr[-800:]


@pytest.mark.parametrize("argv", LEAVES)
def test_k48_failure_is_an_envelope(root, argv):
    """K48: неуспех — это конверт ok:false в stdout и ненулевой exit code."""
    result = _run_no_input(root, (*argv, "--todoc-contract-invalid-option"))
    assert result.returncode == 2
    assert result.stdout.strip(), f"при ошибке stdout пуст: stderr={result.stderr[-400:]}"
    envelope = json.loads(result.stdout)
    assert envelope["schema_version"] == 2
    assert envelope["ok"] is False
    # Контракт конверта: код и сообщение живут в диагностике, а не на верхнем уровне.
    diags = envelope["diagnostics"]
    assert diags, "ok:false без диагностики необъясним для агента"
    assert diags[0]["code"] and diags[0]["message"]
    assert diags[0]["severity"] == "error"
    assert "Traceback (most recent call last)" not in result.stderr, result.stderr[-800:]



def test_init_and_index_rebuild_preview_leave_sources_untouched(tmp_path):
    runner = CliRunner()
    root = tmp_path / "new-dataset"
    args = ["init", "--root", str(root)]
    preview = runner.invoke(cli, args)
    assert preview.exit_code == 0, preview.output
    result = json.loads(preview.output)["data"]["result"]
    assert result["applied"] is False and not root.exists()
    applied = runner.invoke(cli, [*args, "--apply", "--if-plan-hash", result["plan_hash"]])
    assert applied.exit_code == 0, applied.output

    args = ["index", "rebuild", "--root", str(root)]
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    check = runner.invoke(cli, args)
    assert check.exit_code == 0, check.output
    assert not json.loads(check.output)["data"]["result"]["datasets"][0]["applied"]
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    applied = runner.invoke(cli, [*args, "--apply"])
    assert applied.exit_code == 0, applied.output
    assert (root / ".todoc/index/CURRENT.json").is_file()



def test_actions_reject_conflicting_modes_before_opening_a_dataset(tmp_path):
    runner = CliRunner()
    root = tmp_path / "absent"
    actions = [
        ("init", "--root", str(root)),
        ("index", "rebuild"),
        ("docs", "new", "--title", "Review"),
        ("sync",),
        ("state", "set", "context.current_project", "demo"),
        ("state", "unset", "context.current_project"),
        ("change", "open", "--title", "Review"),
        ("change", "archive", "change:review"),
        ("change", "apply", "change:review"),
        ("change", "revert", "change:review"),
        ("types", "guide", "--out", "guide.md"),
        ("docs", "flow", "render", "--id", "flow:review", "--write", "flow.md"),
        ("interop", "export", "--kind", "rasa", "--write", "exports/glossary.md"),
        ("fix", "--diagnostic", "diagnostic-review"),
        ("docs", "status", "--id", "doc:review.md", "--set", "active"),
        ("records", "status", "--id", "note:review", "--set", "active"),
        ("records", "undo-relation", "--id", "note:review", "--pointer", "/relations/0"),
        ("skills", "attach", "--to", str(tmp_path / "skills")),
        ("skills", "import", "--src", str(tmp_path / "skills"), "--into", "process"),
        ("stale", "--ack", "review.md", "--reason", "reviewed"),
    ]
    for argv in actions:
        result = runner.invoke(cli, ["--root", str(root), *argv, "--apply", "--preview"])
        assert getattr(result.exception, "code", None) == "usage.error", (argv, result.exception, result.output)
    assert not list(tmp_path.iterdir())


def test_stale_plan_hashes_never_write(root, sample_md, tmp_path, monkeypatch):
    runner = CliRunner()
    state = tmp_path / "session-state"
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    actions = [
        ("docs", "new", "--title", "Review"),
        ("change", "open", "--title", "Review", "--artifact", "notes/design.md"),
        ("types", "guide", "--out", "guide.md"),
        ("state", "set", "context.current_project", "demo"),
        ("state", "unset", "context.current_project"),
        ("history", "adopt"),
        ("history", "export", "--to", "backup"),
        ("history", "gc"),
        ("skills", "attach", "--to", str(tmp_path / "agent-skills")),
    ]
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    for argv in actions:
        result = runner.invoke(cli, ["--root", str(root), *argv, "--apply", "--if-plan-hash", "stale"])
        assert getattr(result.exception, "code", None) == "write.hash_mismatch", (argv, result.exception)
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    assert not state.exists()
    assert not (tmp_path / "agent-skills").exists()
