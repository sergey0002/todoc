from todoc.application.skills import scan_skills, validate_skills


def _skill(root, rel, name, desc="Описание скила"):
    d = root / "skills" / rel
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\n\n# {name}\n", encoding="utf-8")


def test_all_skill_codes(tmp_path):
    _skill(tmp_path, "coding/a", "a", "x" * 1100)            # long_description
    b = tmp_path / "skills/coding/b"                          # bad_name + name_mismatch
    b.mkdir(parents=True)
    (b / "SKILL.md").write_text("---\nname: Wrong_Name\ndescription: ok\n---\n", encoding="utf-8")
    _skill(tmp_path, "coding/silent", "silent", "")           # empty_description
    _skill(tmp_path, "coding/p/c", "c", "первый")             # duplicate_name (две папки,
    _skill(tmp_path, "coding/q/c", "c", "второй")             # одно имя)
    skills, diags = scan_skills(tmp_path / "skills")
    codes = {d["code"] for d in diags + validate_skills(tmp_path / "skills", skills)}
    assert {"skills.long_description", "skills.bad_name", "skills.name_mismatch",
            "skills.empty_description", "skills.duplicate_name"} <= codes
    loc = [d for d in diags if d["code"] == "skills.bad_name"][0]
    assert loc["path"].endswith("coding/b/SKILL.md") and "line" in loc["location"]
    assert loc["suggested_fixes"]


def test_valid_vault_has_no_diagnostics(tmp_path):
    _skill(tmp_path, "coding/git/commit-message", "commit-message", "Пишет commit message.")
    _skill(tmp_path, "coding/git/!legacy-deploy", "legacy-deploy", "Мьютнутый, но валидный.")
    skills, diags = scan_skills(tmp_path / "skills")
    assert diags == []
    assert validate_skills(tmp_path / "skills", skills) == []


def test_muted_folder_validates_by_effective_name(tmp_path):
    _skill(tmp_path, "docs/!jira-fetch", "jira-fetch", "Тянет задачу.")
    skills, diags = scan_skills(tmp_path / "skills")
    assert skills[0].muted is True and skills[0].name == "jira-fetch"
    assert diags == []
    assert validate_skills(tmp_path / "skills", skills) == []


def test_validate_dataset_merges_skills_vault(tmp_path):
    """Шаг 6: валидатор датасета подхватывает <root>/skills; без vault — ничего."""
    import json
    from todoc.application.validator import validate_dataset

    (tmp_path / ".todoc").mkdir()
    (tmp_path / ".todoc" / "dataset.json").write_text(
        json.dumps({"dataset_id": "ds-skills-test"}), encoding="utf-8")
    dataset = {"dataset_id": "ds-skills-test"}
    _skill(tmp_path, "coding/b", "Wrong_Name", "ok")
    b = tmp_path / "skills/coding/b/SKILL.md"
    diags, _ = validate_dataset(tmp_path, dataset, [], [], [], None)
    assert {d.code for d in diags} == {"skills.bad_name", "skills.name_mismatch"}
    assert all(d.dataset_id == "ds-skills-test" for d in diags)
    assert all(d.path.startswith("skills/") for d in diags)
    assert b.exists()
    # Без vault — ноль новых диагностик
    import shutil
    shutil.rmtree(tmp_path / "skills")
    diags2, _ = validate_dataset(tmp_path, dataset, [], [], [], None)
    assert diags2 == []
