"""Задача 3 плана skills-vault: мьют !-папки исключён из docs search."""
import json
from pathlib import Path

from click.testing import CliRunner

from todoc.cli import cli
from todoc.errors import TodocError


def _run(runner, args):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


def _mk_skill(root: Path, rel: str, name: str, body: str) -> None:
    d = root / "skills" / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {name} скил.\n---\n\n{body}\n", encoding="utf-8")


def test_muted_skill_excluded_from_docs_search(tmp_path):
    runner = CliRunner()
    assert _run(runner, ["init", "--root", str(tmp_path)]).exit_code == 0
    _mk_skill(tmp_path, "deploy/active-deploy", "active-deploy", "# Деплой\nСлово deploy в живом скиле.")
    _mk_skill(tmp_path, "deploy/!legacy-deploy", "legacy-deploy", "# Legacy\nСлово deploy в мьюте.")
    assert _run(runner, ["index", "rebuild", "--root", str(tmp_path)]).exit_code == 0
    r = _run(runner, ["docs", "search", "--root", str(tmp_path), "--query", "deploy"])
    assert r.exit_code == 0, r.output
    hits = json.loads(r.output)["data"]["items"]
    paths = [h["path"] for h in hits]
    assert any("active" in p for p in paths), paths
    assert not any("!legacy-deploy" in p for p in paths), paths
    # мьют не ломает validate
    v = _run(runner, ["validate", "--root", str(tmp_path), "--all"])
    assert v.exit_code == 0
    assert json.loads(v.output)["diagnostics"] == []
