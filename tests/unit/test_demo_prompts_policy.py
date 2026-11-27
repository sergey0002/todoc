from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_all_56_demo_types_have_edit_prompt_without_mandatory_patch_file() -> None:
    type_dirs = sorted((REPO_ROOT / "demo" / ".todoc" / "doc_types").iterdir()) + sorted(
        (REPO_ROOT / "demo" / ".todoc" / "entity_types").iterdir()
    )
    type_dirs = [d for d in type_dirs if d.is_dir()]
    assert len(type_dirs) == 56

    offenders: list[str] = []
    for tdir in type_dirs:
        edit_md = tdir / "prompts" / "edit.md"
        assert edit_md.is_file(), f"Missing edit.md in {tdir}"
        text = edit_md.read_text(encoding="utf-8")
        if "--patch-file" in text:
            offenders.append(str(edit_md.relative_to(REPO_ROOT)))
        if tdir.name not in {"export", "flow-doc"}:
            assert "todoc sync" in text, f"{edit_md} must instruct running todoc sync"
    assert offenders == [], f"Prompts still mandating --patch-file: {offenders}"


def test_rules_contracts_and_skills_reference_todoc_sync_without_patch_file_mandate() -> None:
    for rel in (
        "AGENTS.md",
        "SKILL.md",
        "demo/skill/SKILL.md",
        "demo/notes/agent-contract.md",
        "demo/skills/docs/todoc-docs/SKILL.md",
        "demo/skills/process/todoc-capture/SKILL.md",
        "demo/skills/process/todoc-plan/SKILL.md",
        "demo/skills/process/todoc-execute/SKILL.md",
        "demo/skill/doc-flow-capture/SKILL.md",
        "demo/skill/doc-spec-write/SKILL.md",
    ):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "todoc sync" in text, f"{rel} must document todoc sync"
