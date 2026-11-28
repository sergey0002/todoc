# tests/cli/test_cli_skills_import.py — house-паттерн (Задача 6)
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


def _mk_skill(base: Path, rel: str, name: str, desc: str = "Скил из источника.") -> None:
    d = base / rel
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\n\n# {name}\n",
                                encoding="utf-8")


def _repo_with_wrapper(base: Path) -> Path:
    """Источник-пакет: 3 скила + плагинная обвязка (структура obra/superpowers)."""
    src = base / "src-repo"
    _mk_skill(src, "skills/alpha", "alpha")
    _mk_skill(src, "skills/beta", "beta")
    _mk_skill(src, "skills/gamma", "gamma")
    (src / "hooks").mkdir()
    (src / "hooks" / "session-start.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (src / "commands").mkdir()
    (src / "commands" / "do.md").write_text("# cmd\n", encoding="utf-8")
    (src / "package.json").write_text('{"name": "wrapper"}\n', encoding="utf-8")
    return src


def _demo(tmp_path: Path) -> Path:
    runner = CliRunner()
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path)]).exit_code == 0
    return tmp_path


def test_import_whole_package_copies_only_skills(tmp_path):
    runner = CliRunner()
    demo = _demo(tmp_path)
    src = _repo_with_wrapper(tmp_path)
    r = _run(runner, ["skills", "import", "--apply", "--root", str(demo), "--src", str(src),
                      "--into", "coding/imported"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)["data"]["result"]
    assert [s["name"] for s in data["imported"]] == ["alpha", "beta", "gamma"]
    assert data["audit_note"]
    vault = demo / "skills/coding/imported"
    assert sorted(p.name for p in vault.iterdir()) == ["alpha", "beta", "gamma"]  # обвязка не перенеслась
    assert not (demo / "skills/coding/imported/hooks").exists()
    # виден в дереве сразу (live-scan)
    t = _run(runner, ["skills", "tree", "--root", str(demo), "--query", "alpha"])
    assert "alpha" in t.output


def test_import_no_overwrite_and_skill_filter_and_dry_run(tmp_path):
    runner = CliRunner()
    demo = _demo(tmp_path)
    src = _repo_with_wrapper(tmp_path)
    args = ["skills", "import", "--apply", "--root", str(demo), "--src", str(src), "--into", "coding/imported"]
    assert _run(runner, args).exit_code == 0
    again = _run(runner, args)
    assert again.exit_code != 0
    assert again.exception.code == "skills.path_exists"
    # выборочный
    demo2 = _demo(tmp_path / "d2")
    one = _run(runner, ["skills", "import", "--apply", "--root", str(demo2), "--src", str(src),
                        "--skill", "beta", "--into", "process/x"])
    assert one.exit_code == 0
    assert [s["name"] for s in json.loads(one.output)["data"]["result"]["imported"]] == ["beta"]
    # dry-run ничего не пишет
    demo3 = _demo(tmp_path / "d3")
    dry = _run(runner, ["skills", "import", "--root", str(demo3), "--src", str(src),
                        "--into", "coding/x", "--dry-run"])
    assert dry.exit_code == 0
    assert not (demo3 / "skills/coding/x").exists()


def test_import_reports_invalid_front_matter(tmp_path):
    runner = CliRunner()
    demo = _demo(tmp_path)
    src = tmp_path / "bad-repo"
    _mk_skill(src, "skills/good", "good")
    bad = src / "skills/bad"
    bad.mkdir(parents=True)
    (bad / "SKILL.md").write_text("---\nname: Wrong_Name\ndescription: x\n---\n", encoding="utf-8")
    r = _run(runner, ["skills", "import", "--apply", "--root", str(demo), "--src", str(src),
                      "--into", "coding/review"])
    assert r.exit_code == 0  # файлы — истина: импорт состоялся
    data = json.loads(r.output)["data"]["result"]
    codes = {d["code"] for d in data["diagnostics"]}
    assert {"skills.bad_name", "skills.name_mismatch"} <= codes
    assert (demo / "skills/coding/review/bad/SKILL.md").exists()


def test_adopt_validates_existing_folder(tmp_path):
    runner = CliRunner()
    demo = _demo(tmp_path)
    _mk_skill(demo / "skills", "coding/review/manual", "manual")  # скопировали руками
    r = _run(runner, ["skills", "import", "--root", str(demo), "--src", str(demo / "skills"),
                      "--skill", "manual", "--adopt", "--into", "coding/review"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)["data"]["result"]
    assert data["adopted"] == ["manual"] and data["imported"] == []
    miss = _run(runner, ["skills", "import", "--root", str(demo), "--src", str(demo / "skills"),
                         "--skill", "absent", "--adopt", "--into", "coding/review"])
    assert miss.exit_code != 0
    assert miss.exception.code == "skills.not_found"
