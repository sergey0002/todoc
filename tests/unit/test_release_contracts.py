"""Regression cases for the release contract's failure paths."""

import json
from pathlib import Path

import pytest

from todoc.adapters.filesystem.scanner import file_hash
from todoc.adapters.history.store import FileHistoryStore
from todoc.application.changes import list_change_entries, open_change, revert_change
from todoc.application.history import adopt, content_at, gc
from todoc.application.metadata_patch import plan_metadata_patch
from todoc.application.paging import cursor_offset
from todoc.config import init_dataset
from todoc.errors import AccessError, ConflictError, IncompleteError, TodocError, ValidationError
from todoc.service import DatasetContext


def symlink(path, destination, directory=False):
    try:
        path.symlink_to(destination, target_is_directory=directory)
    except OSError:
        pytest.skip("symlinks unavailable")


@pytest.mark.parametrize("part", ["parent", "folder", "file"])
def test_change_listing_refuses_symbolic_links(root, tmp_path, part):
    outside = tmp_path / "external"
    outside.mkdir()
    (outside / "change.json").write_text('{"record_id":"change:external"}', encoding="utf-8")
    base = root / "changes"
    if part == "parent":
        symlink(base, outside, True)
    else:
        base.mkdir()
        if part == "folder":
            symlink(base / "external", outside, True)
        else:
            folder = base / "local"
            folder.mkdir()
            symlink(folder / "change.json", outside / "change.json")
    with pytest.raises(IncompleteError, match="symlink"):
        list_change_entries(root)


def test_change_listing_refuses_unreadable_source(root):
    path = root / "changes/unreadable/change.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff")
    with pytest.raises(IncompleteError, match="Could not read changes"):
        list_change_entries(root)


def test_reverting_change_refuses_outside_artifacts(root):
    record = open_change(root, "Example", status="applied", artifacts=("../outside",))
    with pytest.raises(ValidationError) as failure:
        revert_change(root, record["record_id"], apply=True)
    assert failure.value.code == "change.target_outside_root"


def test_history_rejects_invalid_backup_paths_even_with_precomputed_manifest(root, monkeypatch):
    store = FileHistoryStore(root)
    manifest = {"../outside": "sha256:fixture"}
    monkeypatch.setattr(store, "backup_manifest", lambda: manifest)
    with pytest.raises(AccessError):
        store.write_backup(root / "backup", manifest)


def test_snapshot_cannot_follow_prefix_directory_to_another_history_location(root):
    store = FileHistoryStore(root)
    digest = store.write_snapshot(b"source")
    folder = root / ".todoc/history/objects" / digest[7:9]
    moved = folder.parents[1] / "elsewhere"
    folder.rename(moved)
    symlink(folder, moved, True)
    with pytest.raises(AccessError):
        store.read_snapshot(digest)


def test_history_cleanup_reports_partial_removal(root, monkeypatch):
    store = FileHistoryStore(root)
    digest = store.write_snapshot(b"orphan")
    monkeypatch.setattr(store, "remove_snapshot", lambda key: False)
    with pytest.raises(IncompleteError) as failure:
        gc(root, store=store)
    assert failure.value.code == "history.cleanup_incomplete"
    assert store.read_snapshot(digest) == b"orphan"


def test_adopt_rechecks_each_source_at_application_time(root, sample_md):
    store = FileHistoryStore(root)
    with pytest.raises(AccessError):
        adopt(root, [{"path": "../outside.md"}], store=store)
    with pytest.raises(ConflictError):
        adopt(root, [{"path": "notes/design.md", "hash": "sha256:stale"}], store=store)
    assert store.read_events(strict=True) == []


def test_history_ignores_unrelated_paths_in_later_journal_events(root, sample_md):
    store = FileHistoryStore(root)
    rev = store.append_event({"paths": [{"path": "notes/design.md"}]})
    store.append_event({"paths": [{"path": "elsewhere.md"}]})
    assert content_at(root, rev, "notes/design.md", store=store)[0] == sample_md.read_bytes()


def test_missing_folder_rows_are_synthesized_as_context():
    from todoc.application.documents import folder_tree

    tree = folder_tree(".", [{"id": "doc:example", "path": "nested/deeper/note.md"}])
    parent = tree["children"][0]
    assert tree["context_only"] is True
    assert parent["path"] == "nested" and parent["context_only"] is True
    assert parent["children"][0]["children"][0]["id"] == "doc:example"


def test_cursor_refuses_zero_offset():
    with pytest.raises(TodocError, match="outside"):
        cursor_offset("matching:0", "matching")


def test_metadata_update_advances_old_date_and_refuses_unrepresentable_values(root):
    target = root / "sample.md"
    target.write_text("---\nupdated: 2001-01-01\n---\n# Sample\n", encoding="utf-8")
    entry = {"path": target.name, "hash": file_hash(target)}
    ops = [{"field": "title", "op": "set", "value": "Changed"}]
    plan, _, _ = plan_metadata_patch(root, "demo", entry, "markdown", ops, [])
    assert "2001-01-01" not in plan.new_content
    bad_ops = [{"field": "priority", "op": "set", "value": 5}]
    with pytest.raises(ValidationError, match="cannot be represented"):
        plan_metadata_patch(root, "demo", entry, "markdown", bad_ops, [])


def test_registry_rejects_pointer_replaced_after_loading(root, sample_md, monkeypatch):
    ctx = DatasetContext(root)
    ctx.rebuild_index(observe=False)
    store = ctx.store
    initial = store.read_current_meta()
    reports = iter((initial, {**initial, "generation_id": "another"}))
    monkeypatch.setattr(store, "read_current_meta", lambda: next(reports))
    assert store.load_current() is None


def test_strict_config_fingerprint_reports_failed_source_read(root, monkeypatch):
    from todoc.application.registry import _config_digest

    original = Path.read_bytes
    target = root / ".todoc/dataset.json"

    def read(path):
        if path == target:
            raise PermissionError("configuration is unreadable")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    with pytest.raises(PermissionError):
        _config_digest(root, strict=True)


def test_write_and_line_edit_refuse_targets_outside_dataset(root, sample_md):
    from todoc.application.write import apply_write_plan, plan_edit_ops
    from todoc.domain.models import WritePlan

    plan = WritePlan(dataset_id="demo", target_path="../outside.md", new_content="# Plan",
                     expected_hash=None, new_hash="unused", basis="test")
    with pytest.raises(AccessError):
        apply_write_plan(root, plan)
    with pytest.raises(ValidationError, match="Unsafe target path"):
        plan_edit_ops(root, plan.target_path, [])
    for op in ({"line": "invalid"}, {"op": "insert_after", "line": 1, "text": 23}):
        with pytest.raises(ValidationError):
            plan_edit_ops(root, "notes/design.md", [op])


def test_legacy_link_fix_records_event_when_recorder_is_supplied(root, sample_md):
    from todoc.application.write import apply_fix

    ctx = DatasetContext(root)
    apply_fix(root, "notes/design.md", "runbook.md", "new.md", history=ctx.history_recorder())
    assert ctx.history_store.read_events(strict=True)[-1]["kind"] == "doc.fix"


def test_record_relation_undo_refuses_stale_hash(root, sample_record):
    from todoc.application.write import apply_undo_relation

    with pytest.raises(ConflictError):
        apply_undo_relation(root, "records/workouts/w1.json", "/relations/0", None, expected_hash="stale")


def test_init_cannot_overwrite_existing_shared_schema(tmp_path):
    schema = tmp_path / ".todoc/document-metadata.schema.json"
    schema.parent.mkdir()
    schema.write_text("{}", encoding="utf-8")
    with pytest.raises(ValidationError) as error:
        init_dataset(tmp_path, document_metadata=True)
    assert error.value.code == "metadata.schema_exists"


def test_typed_record_without_relation_array_is_still_returned(root, sample_record):
    record = json.loads(sample_record.read_text())
    record["relations"] = "invalid"
    sample_record.write_text(json.dumps(record), encoding="utf-8")
    payload = DatasetContext(root).read_index()
    assert any(row["record_id"] == record["record_id"] for row in payload["records"])
    assert not payload["relations"]



def test_search_filters_tags_and_accounts_for_a_complete_snippet(root, sample_md):
    from todoc.application.search import search_documents

    documents = DatasetContext(root).read_index(include_mentions=False)["documents"]
    rows, total, _ = search_documents(root, documents, "rotation", tag="absent")
    assert rows == [] and total == 0
    rows, total, _ = search_documents(root, documents, "rotation", budget=4000)
    assert total == 1 and "rotation" in rows[0].snippet_text


def test_skills_omit_symbolic_sources_outside_the_vault(root, tmp_path):
    from todoc.application.skills import scan_skills

    outside = tmp_path / "SKILL.md"
    outside.write_text("# External", encoding="utf-8")
    folder = root / "skills/entry"
    folder.mkdir(parents=True)
    symlink(folder / "SKILL.md", outside)
    skills, issues = scan_skills(root / "skills")
    assert skills == [] and issues[0]["code"] == "access.outside_data_root"


def test_state_preview_does_not_create_session_file(root, tmp_path, monkeypatch):
    from todoc.application.state import set_var

    base = tmp_path / "state"
    monkeypatch.setenv("XDG_STATE_HOME", str(base))
    result = set_var("demo", "context.current_project", "demo", apply=False)
    assert result["vars"]["context.current_project"] == "demo"
    assert not base.exists()


def test_sync_no_write_preview_accepts_events_without_an_after_hash(root, sample_md):
    from todoc.application.sync import sync_files

    ctx = DatasetContext(root)
    ctx.history_store.append_event({"paths": [{"path": "notes/design.md", "before": None}]})
    sample_md.unlink()
    result = sync_files(ctx, ["notes/design.md"], apply=False, record_history=True)
    assert result["synced"][0]["status"] == "deleted"
    assert len(ctx.history_store.read_events(strict=True)) == 1


@pytest.mark.parametrize(("content", "code"), [
    ({"meta": []}, "document.metadata_type"),
    ({"meta": {"title": "central"}, "title": "other"}, "document.metadata_conflict"),
    ({"meta": {"title": "central"}, "title": "central"}, None),
])
def test_json_metadata_reports_legacy_conflict_and_preserves_equal_duplicates(root, content, code):
    path = root / "metadata.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    payload = DatasetContext(root).read_index(include_mentions=False)
    codes = {issue["code"] for issue in payload["diagnostics"]}
    if code is not None:
        assert code in codes
    else:
        assert "document.metadata_conflict" not in codes


def test_metadata_validation_propagates_unexpected_engine_failure(monkeypatch):
    from todoc.typing_system import document_metadata

    def failed(*args, **kwargs):
        raise RuntimeError("validator failed")

    monkeypatch.setattr(document_metadata.Draft202012Validator, "iter_errors", failed)
    with pytest.raises(RuntimeError, match="validator failed"):
        document_metadata.metadata_errors({}, {}, "")


def test_optional_output_inheritance_allows_a_parent_without_output_option():
    import click
    from click.testing import CliRunner
    from todoc.output.capabilities import UnifiedCommand

    @click.group()
    def root_group():
        pass

    @root_group.command(cls=UnifiedCommand)
    @click.option("--output", default="json")
    def read(output):
        click.echo(output)

    command = CliRunner().invoke(root_group, ["read"])
    assert command.exit_code == 0 and command.output == "json\n"


def test_empty_projected_rows_render_without_a_malformed_table():
    from click.testing import CliRunner
    import click
    from todoc.output.envelope import Envelope, emit

    @click.command()
    def read():
        emit(Envelope.collection({"command": "test"}, [{}]), "table")

    result = CliRunner().invoke(read)
    assert result.exit_code == 0 and "items: []" in result.output
