# tests/cli/test_cli_skills_attach.py — house-паттерн
from click.testing import CliRunner

from todoc.cli import cli
from todoc.errors import TodocError


def _run(runner, args):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


def test_attach_copies_and_embeds_root(tmp_path):
    runner = CliRunner()
    proj = tmp_path / "proj"; (proj / ".agents" / "skills").mkdir(parents=True)
    demo = tmp_path / "demo"; demo.mkdir()
    args = ["skills", "attach", "--apply", "--to", str(proj / ".agents/skills"), "--root", str(demo)]
    r = _run(runner, args)
    assert r.exit_code == 0, r.output
    sk = proj / ".agents" / "skills" / "todoc" / "SKILL.md"
    assert sk.exists() and str(demo) in sk.read_text(encoding="utf-8")
    r2 = _run(runner, args)
    assert r2.exit_code != 0
    assert r2.exception.code == "attach.exists"
    r3 = _run(runner, args + ["--force"])
    assert r3.exit_code == 0
    # {ROOT} заменён: плейсхолдера больше нет
    assert "{ROOT}" not in sk.read_text(encoding="utf-8")
