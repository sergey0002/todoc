from __future__ import annotations

import subprocess
from pathlib import Path

from todoc.adapters.history.backends import GitBackend
from todoc.application.registry import RegistryStore
from todoc.application.write import bump_front_matter_updated
from todoc.typing_system.descriptors import descriptor_diagnostics


def test_git_backend_read_at_resolves_dataset_inside_repo_subdir(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    kb = tmp_path / "demo"
    (kb / "ideas").mkdir(parents=True)
    doc = kb / "ideas" / "sample.md"
    doc.write_text("# v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
    doc.write_text("# v2\n", encoding="utf-8")

    backend = GitBackend(kb)
    head = backend.head()
    assert head is not None
    assert backend.read_at(head, "ideas/sample.md") == b"# v1\n"
    assert backend.read_at(head, "./ideas/sample.md") == b"# v1\n"


def test_config_digest_ignores_history_refs_json(tmp_path: Path) -> None:
    (tmp_path / ".todoc").mkdir()
    (tmp_path / ".todoc" / "dataset.json").write_text('{"schema_version": 1}\n', encoding="utf-8")
    store = RegistryStore(tmp_path)
    before = store.config_digest()
    refs = tmp_path / ".todoc" / "history" / "refs.json"
    refs.parent.mkdir(parents=True)
    refs.write_text('{"head": "rev-1", "tags": {}}\n', encoding="utf-8")
    assert store.config_digest() == before


def test_doc_type_generated_field_accepts_bool_and_rejects_non_bool(tmp_path: Path) -> None:
    dataset = {"document_types": "doc_types"}
    type_dir = tmp_path / ".todoc" / "doc_types" / "export"
    type_dir.mkdir(parents=True)
    for op in ("read", "create", "edit", "delete"):
        p = type_dir / "prompts" / f"{op}.md"
        p.parent.mkdir(exist_ok=True)
        p.write_text(f"# {op}\n", encoding="utf-8")

    ok_diags = descriptor_diagnostics(
        tmp_path, dataset, "doc_type",
        {"schema_version": 1, "type_id": "export", "version": "1.0", "kind": "doc_type",
         "description": "d", "format": "markdown", "generated": True},
        ".todoc/doc_types/export/type.json",
    )
    assert ok_diags == []

    bad_diags = descriptor_diagnostics(
        tmp_path, dataset, "doc_type",
        {"schema_version": 1, "type_id": "export", "version": "1.0", "kind": "doc_type",
         "description": "d", "format": "markdown", "generated": "yes"},
        ".todoc/doc_types/export/type.json",
    )
    assert any(d["code"] == "config.invalid_schema" and "generated" in d["message"] for d in bad_diags)


def test_bump_front_matter_updated_handles_present_same_unclosed_and_absent_fm() -> None:
    src = "---\nid: doc:a\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n\n# A\n"
    new_text, bumped = bump_front_matter_updated(src, today="2026-11-27")
    assert bumped is True
    assert "updated: 2026-11-27\n" in new_text

    same_text, bumped_again = bump_front_matter_updated(new_text, today="2026-11-27")
    assert bumped_again is False
    assert same_text == new_text

    # Default UTC today branch
    _, _ = bump_front_matter_updated(src)

    no_updated_key = "---\nid: doc:b\n---\n\n# B\n"
    unchanged_fm, bumped_no_key = bump_front_matter_updated(no_updated_key, today="2026-11-27")
    assert bumped_no_key is False
    assert unchanged_fm == no_updated_key

    unclosed_fm = "---\nid: doc:c\n# no closing fence\n"
    unchanged_unclosed, bumped_unclosed = bump_front_matter_updated(unclosed_fm, today="2026-11-27")
    assert bumped_unclosed is False
    assert unchanged_unclosed == unclosed_fm

    no_fm, bumped_no_fm = bump_front_matter_updated("# Plain\n", today="2026-11-27")
    assert bumped_no_fm is False
    assert no_fm == "# Plain\n"
