import json

import pytest

from todoc.adapters.filesystem.scanner import file_hash
from todoc.application.search import search_documents, tokenize
from todoc.application.write import apply_edit_ops, apply_fix, apply_write_plan, create_record_plan, load_input_record
from todoc.errors import ConflictError, ValidationError


def test_tokenize():
    assert tokenize("Refresh TOKEN") == ["refresh", "token"]


def test_search_finds(root, sample_md):
    documents = [{"document_id": "doc:notes/design.md", "path": "notes/design.md", "format": "markdown",
                  "doc_type": "note", "title": "Design", "status": "ok"}]
    hits, total, truncated = search_documents(root, documents, "refresh token", limit=10)
    assert total == 1
    assert list(hits[0].matched_terms) == ["refresh", "token"]
    assert hits[0].heading_path
    assert hits[0].snippet_text


def test_search_no_match(root, sample_md):
    documents = [{"document_id": "doc:notes/design.md", "path": "notes/design.md", "format": "markdown",
                  "doc_type": "note", "title": "Design", "status": "ok"}]
    hits, total, _ = search_documents(root, documents, "nonexistentterm")
    assert total == 0
    assert hits == []


def test_search_empty_query(root, sample_md):
    hits, total, _ = search_documents(root, [], "   ")
    assert hits == []
    assert total == 0


def test_search_type_filter(root, sample_md):
    documents = [{"document_id": "doc:notes/design.md", "path": "notes/design.md", "format": "markdown",
                  "doc_type": "note", "title": "Design", "status": "ok"}]
    hits, total, _ = search_documents(root, documents, "refresh", doc_type="adr")
    assert total == 0


def test_search_within(root, sample_md):
    documents = [{"document_id": "doc:notes/design.md", "path": "notes/design.md", "format": "markdown",
                  "doc_type": "note", "title": "Design", "status": "ok"}]
    hits, total, _ = search_documents(root, documents, "refresh", within="other")
    assert total == 0
    hits2, total2, _ = search_documents(root, documents, "refresh", within="notes")
    assert total2 == 1


def test_search_budget(root, sample_md):
    documents = [{"document_id": "doc:notes/design.md", "path": "notes/design.md", "format": "markdown",
                  "doc_type": "note", "title": "Design", "status": "ok"}]
    hits, total, truncated = search_documents(root, documents, "refresh", limit=10, budget=10)
    assert total == 1
    assert len(hits) == 1


def test_create_record_plan(root):
    dataset = {"dataset_id": "ds"}
    entity_types = {"workout": {"required_fields": ["date"], "path_template": "records/workouts/{slug}.json"}}
    record = {"record_id": "workout:2026-11-24-01", "entity_type": "workout", "date": "2026-11-24"}
    plan = create_record_plan(dataset, entity_types, record, set(), set())
    assert plan.target_path == "records/workouts/2026-11-24-01.json"
    assert plan.expected_hash is None


def test_create_record_plan_rejects_schema_violation():
    schema = {"type": "object", "properties": {"mood": {"enum": ["calm", "focused"]}}}
    record = {"record_id": "note:1", "entity_type": "note", "mood": "angry"}
    with pytest.raises(ValidationError) as exc:
        create_record_plan({"dataset_id": "ds"}, {"note": {}}, record, set(), set(), schema)
    assert exc.value.code == "record.schema_violation"
    assert "/mood" in exc.value.message


def test_create_record_plan_accepts_schema_conformant_record():
    schema = {"type": "object", "properties": {"mood": {"enum": ["calm", "focused"]}}}
    record = {"record_id": "note:2", "entity_type": "note", "mood": "calm"}
    plan = create_record_plan({"dataset_id": "ds"}, {"note": {}}, record, set(), set(), schema)
    assert plan.target_path == "records/note/note:2.json"


def test_create_record_plan_unknown_type():
    with pytest.raises(ValidationError):
        create_record_plan({"dataset_id": "ds"}, {}, {"record_id": "x:1", "entity_type": "ghost"}, set(), set())


def test_create_record_plan_missing_id():
    with pytest.raises(ValidationError):
        create_record_plan({"dataset_id": "ds"}, {"workout": {}}, {"entity_type": "workout"}, set(), set())


def test_create_record_plan_duplicate_id():
    with pytest.raises(ConflictError):
        create_record_plan({"dataset_id": "ds"}, {"workout": {}}, {"record_id": "w:1", "entity_type": "workout"}, {"w:1"}, set())


def test_create_record_plan_missing_field():
    with pytest.raises(ValidationError):
        create_record_plan({"dataset_id": "ds"}, {"workout": {"required_fields": ["date"]}},
                           {"record_id": "w:1", "entity_type": "workout"}, set(), set())


def test_create_record_plan_target_exists():
    with pytest.raises(ConflictError):
        create_record_plan({"dataset_id": "ds"}, {"workout": {"path_template": "records/{slug}.json"}},
                           {"record_id": "w:1", "entity_type": "workout"}, set(), {"records/1.json"})


def test_create_record_plan_unsafe_path():
    with pytest.raises(ValidationError):
        create_record_plan({"dataset_id": "ds"}, {"workout": {"path_template": "../{slug}.json"}},
                           {"record_id": "w:1", "entity_type": "workout"}, set(), set())


def test_apply_write_plan_new(root):
    from todoc.domain.models import WritePlan
    plan = WritePlan("ds", "records/x.json", '{"a": 1}\n', None, "sha256:x", "test")
    new_hash = apply_write_plan(root, plan)
    assert new_hash == "sha256:x"
    assert (root / "records" / "x.json").exists()


def test_apply_write_plan_overwrite_conflict(root):
    from todoc.domain.models import WritePlan
    (root / "records").mkdir(exist_ok=True)
    (root / "records" / "x.json").write_text("old")
    plan = WritePlan("ds", "records/x.json", "new", None, "sha256:x", "test")
    with pytest.raises(ConflictError):
        apply_write_plan(root, plan)


def test_apply_write_plan_hash_mismatch(root):
    from todoc.domain.models import WritePlan
    (root / "records").mkdir(exist_ok=True)
    (root / "records" / "x.json").write_text("old")
    plan = WritePlan("ds", "records/x.json", "new", "sha256:wrong", "sha256:x", "test")
    with pytest.raises(ConflictError):
        apply_write_plan(root, plan)


def test_apply_write_plan_update_ok(root):
    from todoc.domain.models import WritePlan
    (root / "records").mkdir(exist_ok=True)
    target = root / "records" / "x.json"
    target.write_text("old")
    plan = WritePlan("ds", "records/x.json", "new", file_hash(target), "sha256:x", "test")
    assert apply_write_plan(root, plan) == "sha256:x"
    assert target.read_text() == "new"


def test_apply_write_plan_missing_target(root):
    from todoc.domain.models import WritePlan
    plan = WritePlan("ds", "records/missing.json", "new", "sha256:x", "sha256:y", "test")
    with pytest.raises(ConflictError):
        apply_write_plan(root, plan)


def test_apply_fix(root, sample_md):
    new_hash = apply_fix(root, "notes/design.md", "../ops/runbook.md", "../ops/runbook.md")
    assert new_hash.startswith("sha256:")


def test_apply_fix_hash_mismatch(root, sample_md):
    with pytest.raises(ConflictError):
        apply_fix(root, "notes/design.md", "../ops/runbook.md", "x.md", expected_hash="sha256:wrong")


def test_apply_fix_target_not_found(root, sample_md):
    with pytest.raises(ValidationError):
        apply_fix(root, "notes/design.md", "missing.md", "x.md")


def test_apply_fix_file_missing(root):
    with pytest.raises(ValidationError):
        apply_fix(root, "missing.md", "a", "b")


def test_apply_edit_ops(root, sample_md):
    new_hash = apply_edit_ops(root, "notes/design.md", [{"line": 1, "text": "# Changed"}])
    assert new_hash.startswith("sha256:")
    assert (root / "notes" / "design.md").read_text().splitlines()[0] == "# Changed"


def test_apply_edit_ops_out_of_range(root, sample_md):
    with pytest.raises(ValidationError):
        apply_edit_ops(root, "notes/design.md", [{"line": 9999, "text": "x"}])


def test_apply_edit_ops_hash_mismatch(root, sample_md):
    with pytest.raises(ConflictError):
        apply_edit_ops(root, "notes/design.md", [{"line": 1, "text": "x"}], expected_hash="sha256:wrong")


def test_load_input_record(tmp_path):
    path = tmp_path / "in.json"
    path.write_text('{"record_id": "w:1", "entity_type": "workout"}')
    assert load_input_record(path)["record_id"] == "w:1"


def test_load_input_record_invalid(tmp_path):
    path = tmp_path / "in.json"
    path.write_text("{bad")
    with pytest.raises(ValidationError):
        load_input_record(path)
    path.write_text("[1, 2]")
    with pytest.raises(ValidationError):
        load_input_record(path)
