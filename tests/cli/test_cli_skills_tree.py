# tests/cli/test_cli_skills_tree.py — house-паттерн tests/cli/test_cli.py
import json

import pytest
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
    _run(CliRunner(), ["init", "--apply", "--root", str(root)])  # house: команды идут через _contexts
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
    d = _json(_run(runner, ["skills", "tree", "--root", str(tmp_path), "--output", "json"]))["data"]["result"]
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
    assert lim["data"]["result"]["truncated"] is True and len(lim["data"]["result"]["skills"]) == 2


def test_read_by_dir_and_file(tmp_path):
    runner = CliRunner()
    _vault(tmp_path)
    d = _json(_run(runner, ["skills", "read", "--root", str(tmp_path),
                            "--path", "coding/review/adr"]))["data"]["result"]
    assert d["name"] == "adr" and "# adr" in d["content"]
    d2 = _json(_run(runner, ["skills", "read", "--root", str(tmp_path),
                             "--path", "skills/docs/jira-fetch/SKILL.md"]))["data"]["result"]
    assert d2["name"] == "jira-fetch"
    md = _run(runner, ["skills", "read", "--root", str(tmp_path),
                       "--path", "coding/review/adr", "--output", "markdown"])
    assert "# adr" in md.output
    rng = _json(_run(runner, ["skills", "read", "--root", str(tmp_path),
                              "--path", "coding/review/adr", "--line-range", "1-2"]))["data"]["result"]
    assert rng["content"].count("\n") <= 2
    bad = _run(runner, ["skills", "read", "--root", str(tmp_path), "--path", "../secrets.md"])
    assert bad.exit_code != 0
    assert isinstance(bad.exception, TodocError)
    assert bad.exception.code == "docs.invalid_scope"


def test_tree_sections_from_config_order_and_titles(tmp_path):
    """Задача 4: разделы описываются .config.json — title в table, section_meta в JSON, порядок order."""
    runner = CliRunner()
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path)]).exit_code == 0
    _skill(tmp_path, "coding/git/commit-message", "commit-message", "Пишет commit message.")
    _skill(tmp_path, "process/release-flow", "release-flow", "Проводит merge-forward релиза.")
    (tmp_path / "skills/coding/.config.json").write_text(
        '{"schema_version": 1, "title": "Скилы кодинга", "description": "git, ревью, окружение.", "order": 3}',
        encoding="utf-8")
    (tmp_path / "skills/process/.config.json").write_text(
        '{"schema_version": 1, "title": "Процессы", "order": 1}', encoding="utf-8")
    t = _run(runner, ["skills", "tree", "--root", str(tmp_path), "--output", "table"])
    assert "process/ — Процессы" in t.output and "coding/ — Скилы кодинга" in t.output
    assert t.output.index("Процессы") < t.output.index("Скилы кодинга")  # order 1 выше 3
    d = _json(_run(runner, ["skills", "tree", "--root", str(tmp_path)]))["data"]["result"]
    assert d["section_meta"]["coding"]["title"] == "Скилы кодинга"
    assert d["section_meta"]["process"]["order"] == 1


def test_tree_query_matches_section_config(tmp_path):
    """query по alias/тексту конфига раздела находит скилы внутри даже без совпадения в самом скиле."""
    runner = CliRunner()
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path)]).exit_code == 0
    _skill(tmp_path, "coding/git/commit-message", "commit-message", "Пишет commit message.")
    (tmp_path / "skills/coding/.config.json").write_text(
        '{"schema_version": 1, "title": "Скилы кодинга", "aliases": "кодинг|dev-work"}', encoding="utf-8")
    (tmp_path / "skills/other/skill-x/SKILL.md").parent.mkdir(parents=True)
    (tmp_path / "skills/other/skill-x/SKILL.md").write_text(
        "---\nname: skill-x\ndescription: Что-то постороннее.\n---\n\n# x\n", encoding="utf-8")
    q = _run(runner, ["skills", "tree", "--root", str(tmp_path), "--query", "кодинг"])
    assert "commit-message" in q.output and "skill-x" not in q.output
    q2 = _run(runner, ["skills", "tree", "--root", str(tmp_path), "--query", "dev-work"])
    assert "commit-message" in q2.output and "skill-x" not in q2.output


def test_tree_max_depth_cuts_recursion(tmp_path):
    """--max-depth отсекает рекурсию рендера: вложенный скил не печатается."""
    runner = CliRunner()
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path)]).exit_code == 0
    _skill(tmp_path, "coding/git/commit-message", "commit-message", "Пишет commit message.")
    t = _run(runner, ["skills", "tree", "--root", str(tmp_path), "--output", "table",
                      "--max-depth", "1"])
    assert t.exit_code == 0
    assert "commit-message" not in t.output


def test_skills_tree_pages_once_across_views_and_projections(tmp_path):
    _vault(tmp_path)
    args = ["skills", "tree", "--root", str(tmp_path), "--limit", "2"]
    first = _json(_run(CliRunner(), args + ["--view", "flat", "--fields", "name"]))["data"]
    assert first["meta"]["actual_view"] == "flat" and first["meta"]["total"] == 4
    assert len(first["result"]["items"]) == 2
    assert all(set(row) == {"id", "path", "name"} for row in first["result"]["items"])
    cursor = first["meta"]["next_cursor"]

    second = _json(_run(CliRunner(), args + ["--view", "tree", "--cursor", cursor,
                                            "--exclude-fields", "refs"]))["data"]
    paths = {row["path"] for row in second["result"]["skills"]}
    assert len(paths) == 2
    assert not paths & {row["path"] for row in first["result"]["items"]}
    assert all("refs" not in row for row in second["result"]["skills"])
    assert second["result"]["root"]["children"]
    assert second["meta"]["next_cursor"] is None

    _skill(tmp_path, "docs/extra", "extra")
    changed = _run(CliRunner(), args + ["--cursor", cursor])
    assert changed.exception.code == "cursor.invalid"


@pytest.mark.parametrize("output", ["json", "table", "markdown"])
def test_skills_tree_reports_view_fallback_in_each_format(tmp_path, output):
    _vault(tmp_path)
    result = _run(CliRunner(), ["skills", "tree", "--root", str(tmp_path), "--view", "graph",
                               "--output", output])
    assert result.exit_code == 0, result.exception
    assert "view.fallback" in result.output and "requested_view" in result.output
    assert "actual_view" in result.output and "commit-message" in result.output
    if output == "json":
        assert _json(result)["data"]["meta"]["actual_view"] == "tree"


def test_skills_tree_keeps_a_root_skill_and_inherits_muting(tmp_path):
    _vault(tmp_path)
    (tmp_path / "skills/SKILL.md").write_text("---\nname: skills\ndescription: Root skill\n---\n", encoding="utf-8")
    _skill(tmp_path, "!paused/child", "child")
    args = ["skills", "tree", "--root", str(tmp_path)]
    default = _json(_run(CliRunner(), args))
    assert default["data"]["result"]["root"]["path"] == "."
    assert "child" not in {row["name"] for row in default["data"]["result"]["skills"]}
    scoped = _json(_run(CliRunner(), args + ["--within", "!paused", "--all"]))
    row, = scoped["data"]["result"]["skills"]
    assert row["path"] == "!paused/child" and row["muted"]
    top = _run(CliRunner(), args + ["--depth", "0", "--output", "table"])
    assert top.exit_code == 0 and "Root skill" in top.output
    assert "commit-message" not in top.output


def test_skills_tree_surfaces_an_incomplete_scan_and_empty_scoped_query(tmp_path):
    _vault(tmp_path)
    base = ["skills", "tree", "--root", str(tmp_path)]
    empty = _json(_run(CliRunner(), base + ["--query", "no-match"]))
    assert empty["ok"] and empty["data"]["meta"]["returned"] == 0
    assert empty["next_actions"] == []
    (tmp_path / "skills/docs/note-search/SKILL.md").write_bytes(b"\xff")
    invalid = _run(CliRunner(), base)
    envelope = _json(invalid)
    assert invalid.exit_code == 6 and not envelope["data"]["meta"]["complete"]
    assert envelope["diagnostics"][0]["path"] == "docs/note-search/SKILL.md"
