from pathlib import Path

from todoc.application.skills import effective_name, scan_skills


def _skill(root: Path, rel: str, name: str, desc: str = "Описание скила") -> None:
    d = root / "skills" / rel
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\n\n# {name}\n", encoding="utf-8")


def test_scan_detects_skill_and_sections(tmp_path):
    _skill(tmp_path, "coding/git/commit-message", "commit-message")
    _skill(tmp_path, "coding/git/!legacy-deploy", "legacy-deploy")
    (tmp_path / "skills/coding/git/release").mkdir(parents=True)  # раздел — не скил
    skills, diags = scan_skills(tmp_path / "skills")
    assert [s.name for s in skills] == ["commit-message", "legacy-deploy"]
    assert [s.section for s in skills] == ["coding/git", "coding/git"]
    assert [s.muted for s in skills] == [False, True]
    assert effective_name("!legacy-deploy") == "legacy-deploy"
    assert diags == []


def test_scan_counts_resources_and_top_level(tmp_path):
    _skill(tmp_path, "todoc-docs", "todoc-docs")
    d = tmp_path / "skills/todoc-docs"
    (d / "references").mkdir()
    (d / "references/cheatsheet.md").write_text("x\n", encoding="utf-8")
    (d / "scripts").mkdir()
    (d / "scripts/run.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    skills, diags = scan_skills(tmp_path / "skills")
    assert [s.section for s in skills] == [""]
    assert (skills[0].refs, skills[0].scripts, skills[0].assets) == (1, 1, 0)
    assert skills[0].muted is False
    assert diags == []


def test_scan_reports_front_matter_problems(tmp_path):
    d = tmp_path / "skills/docs/broken"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("# Нет front matter\n", encoding="utf-8")
    skills, diags = scan_skills(tmp_path / "skills")
    assert skills == []
    assert {x["code"] for x in diags} == {"skills.missing_front_matter"}
    assert diags[0]["path"].endswith("docs/broken/SKILL.md")
    assert "line" in diags[0]["location"]
    assert diags[0]["suggested_fixes"]
