# tests/cli/test_cli_skills_tree.py — house-паттерн tests/cli/test_cli.py
import json
from pathlib import Path

from click.testing import CliRunner

from todoc.cli import cli
from todoc.errors import TodocError


def _skill(root: Path, rel: str, name: str, desc: str = "Описание скила") -> None:
    d = root / "skills" / rel
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\n\n# {name}\n", encoding="utf-8")


def _vault(root: Path) -> None:
    _run(CliRunner(), ["init", "--root", str(root)])  # house: команды идут через _contexts
    _skill(root, "coding/git/commit-message", "commit-message", "Пишет commit message.")
    _skill(root, "coding/review/adr", "adr", "Пишет ADR: контекст, решение, последствия.")
    _skill(root, "docs/jira-fetch", "jira-fetch", "Тянет задачу Jira в снимок.")
    _skill(root, "coding/git/!legacy-deploy", "legacy-deploy", "Мьютнутый: деплой legacy.")
    _skill(root, "docs/note-search", "note-search", "Ищет заметки по кириллическому запросу.")


def _run(runner, args):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


def _json(result):
    return json.loads(result.output)


def test_tree_json_bounded(tmp_path):
    runner = CliRunner()
    _vault(tmp_path)
    d = _json(_run(runner, ["skills", "tree", "--root", str(tmp_path), "--output", "json"]))["data"]
    assert d["counts"]["skills"] == 5 and d["counts"]["muted"] == 1
    assert d["truncated"] is False
    assert all("description" in s for s in d["skills"])
    assert d["counts"]["sections"] == 2  # coding/git, coding/review, docs → top sections


def test_tree_table_query_within_all(tmp_path):
    runner = CliRunner()
    _vault(tmp_path)
    t = _run(runner, ["skills", "tree", "--root", str(tmp_path), "--output", "table"])
    assert "commit-message" in t.output and "[!]" not in t.output  # мьют скрыт
    q = _run(runner, ["skills", "tree", "--root", str(tmp_path), "--query", "commit"])
    assert "commit-message" in q.output and "jira-fetch" not in q.output
    w = _run(runner, ["skills", "tree", "--root", str(tmp_path), "--within", "coding"])
    assert "jira-fetch" not in w.output
    cyr = _run(runner, ["skills", "tree", "--root", str(tmp_path), "--query", "кириллическ"])
    assert "note-search" in cyr.output               # кириллица в --query работает (§4, §7)
    a = _run(runner, ["skills", "tree", "--root", str(tmp_path), "--all", "--output", "table"])
    assert "[!]" in a.output and "legacy-deploy" in a.output
    d1 = _run(runner, ["skills", "tree", "--root", str(tmp_path), "--max-depth", "1"])
    assert "commit-message" not in d1.output         # глубина ограничивает выдачу
    lim = _json(_run(runner, ["skills", "tree", "--root", str(tmp_path),
                              "--output", "json", "--limit", "2"]))
    assert lim["data"]["truncated"] is True and len(lim["data"]["skills"]) == 2


def test_read_by_dir_and_file(tmp_path):
    runner = CliRunner()
    _vault(tmp_path)
    d = _json(_run(runner, ["skills", "read", "--root", str(tmp_path),
                            "--path", "coding/review/adr"]))["data"]
    assert d["name"] == "adr" and "# adr" in d["content"]
    d2 = _json(_run(runner, ["skills", "read", "--root", str(tmp_path),
                             "--path", "skills/docs/jira-fetch/SKILL.md"]))["data"]
    assert d2["name"] == "jira-fetch"
    md = _run(runner, ["skills", "read", "--root", str(tmp_path),
                       "--path", "coding/review/adr", "--output", "markdown"])
    assert "# adr" in md.output
    rng = _json(_run(runner, ["skills", "read", "--root", str(tmp_path),
                              "--path", "coding/review/adr", "--line-range", "1-2"]))["data"]
    assert rng["content"].count("\n") <= 2
    bad = _run(runner, ["skills", "read", "--root", str(tmp_path), "--path", "../secrets.md"])
    assert bad.exit_code != 0
    assert isinstance(bad.exception, TodocError)
    assert bad.exception.code == "skills.not_found"
