"""Targeted tests for edge branches (full coverage)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from todoc.adapters.filesystem.scanner import ScannedFile, atomic_write, scan_dataset
from todoc.adapters.formats.csvfmt import parse_csv
from todoc.adapters.formats.jsonfmt import resolve_pointer
from todoc.adapters.formats.markdown import parse_markdown
from todoc.application import registry as registry_mod
from todoc.application.query import graph_neighbors, query_records
from todoc.application.registry import RegistryStore
from todoc.application.search import _snippet, search_documents
from todoc.application.validator import _check_markdown_links, validate_dataset, validate_relations
from todoc.application.write import apply_edit_ops, apply_write_plan, load_input_record
from todoc.config import load_dataset, load_rules
from todoc.domain.models import Record, Relation, ValidationReport
from todoc.errors import AccessError, ConflictError, ValidationError
from todoc.output.envelope import emit, make_envelope
from todoc.service import DatasetContext, resolve_roots
from todoc.typing_system.descriptors import TypeRegistry, load_json_file
from todoc.typing_system.resolver import glob_match, resolve_type


# --- scanner ---------------------------------------------------------------

def test_atomic_write_failure_cleans_tmp(root, monkeypatch):
    target = root / "out.txt"

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        atomic_write(target, "data")
    assert list(root.glob("out.txt.tmp.*")) == []


def test_scan_skips_todoc_json(root, sample_md):
    (root / ".todoc.json").write_text("{}")
    _folders, files = scan_dataset(root)
    assert ".todoc.json" not in [f.rel_path for f in files]


def test_scan_fifo_neither_dir_nor_file(root):
    os.mkfifo(root / "pipe")
    _folders, files = scan_dataset(root)
    assert "pipe" not in [f.rel_path for f in files]


def test_scan_symlink_escape_skipped(root, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside\n")
    link = root / "escape.md"
    link.symlink_to(outside)
    _folders, files = scan_dataset(root, follow_symlinks=True)
    # is_within_root resolves the link target: escape outside root is skipped.
    assert "escape.md" not in [f.rel_path for f in files]


def test_scan_symlinked_dir_escape(root, tmp_path):
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    (outside_dir / "secret.md").write_text("# Secret\n")
    link = root / "linkdir"
    link.symlink_to(outside_dir, target_is_directory=True)
    _folders, files = scan_dataset(root, follow_symlinks=True)
    paths = [f.rel_path for f in files]
    assert not any("secret.md" in p for p in paths)


def test_scan_oversize_file_unsupported(root):
    big = root / "big.md"
    big.write_text("# Big\n" + "x" * 100)
    _folders, files = scan_dataset(root, max_file_bytes=10)
    big_file = next(f for f in files if f.rel_path == "big.md")
    assert big_file.status == "unsupported"


def test_scan_stat_error_permission_denied(root, sample_md, monkeypatch):
    real_scandir = os.scandir

    class FakeEntry:
        def __init__(self, real):
            self._real = real
            self.name = real.name
            self.path = real.path

        def is_symlink(self):
            return False

        def is_dir(self, follow_symlinks=True):
            return False

        def is_file(self, follow_symlinks=True):
            return True

        def stat(self, follow_symlinks=True):
            raise OSError("nope")

    def fake_scandir(path):
        return [FakeEntry(e) for e in real_scandir(path)]

    monkeypatch.setattr(os, "scandir", fake_scandir)
    _folders, files = scan_dataset(root)
    denied = [f for f in files if f.status == "permission_denied"]
    assert denied, "expected permission_denied entries"


def test_scan_hash_error_permission_denied(root, sample_md, monkeypatch):
    import todoc.adapters.filesystem.scanner as scanner_mod

    def boom(path):
        raise OSError("nope")

    monkeypatch.setattr(scanner_mod, "file_hash", boom)
    _folders, files = scan_dataset(root)
    assert any(f.status == "permission_denied" for f in files)


def test_scan_unreadable_dir(root, monkeypatch):
    real_scandir = os.scandir

    def fake_scandir(path):
        if str(path).endswith("blocked"):
            raise OSError("blocked")
        return real_scandir(path)

    (root / "blocked").mkdir()
    monkeypatch.setattr(os, "scandir", fake_scandir)
    folders, _files = scan_dataset(root)
    assert any(f.rel_path == "blocked" for f in folders)


# --- formats ---------------------------------------------------------------

def test_csv_parse_error_huge_field():
    doc = parse_csv("a\n" + "x" * 200000 + "\n")
    assert any("parse_error" in e for e in doc.errors)


def test_pointer_into_scalar():
    with pytest.raises(KeyError):
        resolve_pointer({"a": 5}, "/a/b")


def test_front_matter_line_without_colon():
    doc = parse_markdown("---\nno colon here\ntitle: X\n---\n\n# Hi\n")
    assert doc.front_matter == {"title": "X"}


def test_empty_heading():
    doc = parse_markdown("#\n")
    assert doc.headings[0].title == ""


# --- query -----------------------------------------------------------------

def test_query_in_filter_excludes():
    records = [
        {"record_id": "w:1", "entity_type": "workout", "data": {"muscle": "triceps"}},
        {"record_id": "w:2", "entity_type": "workout", "data": {"muscle": "biceps"}},
    ]
    items, total, _ = query_records(records, "workout", {"muscle": {"$in": ["triceps"]}})
    assert total == 1
    assert items[0]["record_id"] == "w:1"


def test_graph_limit():
    relations = [
        {"type_id": "t", "source_id": "a", "target_id": "b"},
        {"type_id": "t", "source_id": "a", "target_id": "c"},
        {"type_id": "t", "source_id": "a", "target_id": "d"},
    ]
    edges = graph_neighbors(relations, "a", "t", depth=1, limit=1)
    assert len(edges) == 1


def test_graph_depth_exhaustion():
    relations = [{"type_id": "t", "source_id": "a", "target_id": "b"}]
    edges = graph_neighbors(relations, "a", "t", depth=5, limit=10)
    assert len(edges) == 1


# --- registry --------------------------------------------------------------

def test_config_digest_no_todoc_dir(tmp_path):
    store = RegistryStore(tmp_path)
    gen = store.publish({"dataset_id": "ds"}, [], [], [], [], [])
    assert store.current_generation_id() == gen


def test_config_digest_unreadable_file(root):
    broken = root / ".todoc" / "broken.json"
    broken.symlink_to(root / ".todoc" / "nonexistent.json")
    store = RegistryStore(root)
    gen = store.publish({"dataset_id": "ds"}, [], [], [], [], [])
    assert gen


def test_load_current_missing_gen_dir(root):
    store = RegistryStore(root)
    gen = store.publish({"dataset_id": "ds"}, [], [], [], [], [])
    shutil.rmtree(store.generations_dir / gen)
    assert store.load_current() is None


def test_load_current_missing_file(root):
    store = RegistryStore(root)
    gen = store.publish({"dataset_id": "ds"}, [], [], [], [], [])
    (store.generations_dir / gen / "folders.json").unlink()
    assert store.load_current() is None


def test_load_current_corrupt_file(root):
    store = RegistryStore(root)
    gen = store.publish({"dataset_id": "ds"}, [], [], [], [], [])
    (store.generations_dir / gen / "folders.json").write_text("not json")
    assert store.load_current() is None


def test_publish_gen_collision(root, monkeypatch):
    store = RegistryStore(root)
    fixed = type("U", (), {"hex": "abc123abc123"})()
    monkeypatch.setattr(registry_mod.uuid, "uuid4", lambda: fixed)
    gen1 = store.publish({"dataset_id": "ds"}, [], [], [], [], [])
    gen2 = store.publish({"dataset_id": "ds"}, [], [], [], [], [])
    assert gen1 == gen2 == "abc123abc123"


def test_publish_failure_cleans_tmp(root, monkeypatch):
    store = RegistryStore(root)

    def bad_loads(text, *args, **kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(registry_mod.json, "loads", bad_loads)
    with pytest.raises(ValueError):
        store.publish({"dataset_id": "ds"}, [], [], [], [], [])
    assert list(store.generations_dir.glob(".tmp-*")) == []


# --- search ----------------------------------------------------------------

def test_document_text_missing_file(root):
    documents = [{"document_id": "doc:gone.md", "path": "gone.md", "format": "markdown",
                  "doc_type": "note", "title": "", "status": "ok"}]
    hits, total, _ = search_documents(root, documents, "refresh")
    assert total == 0
    assert hits == []


def test_snippet_no_term_in_text():
    snippet, line_start, line_end, truncated = _snippet("hello world", ["absent"])
    assert snippet == "hello world"
    assert line_start == 1
    assert line_end == 1
    assert truncated is False


def test_search_status_filter(root, sample_md):
    documents = [{"document_id": "doc:notes/design.md", "path": "notes/design.md", "format": "markdown",
                  "doc_type": "note", "title": "Design", "status": "unsupported"}]
    hits, total, _ = search_documents(root, documents, "refresh")
    assert total == 0


def test_search_budget_break(root, tmp_path):
    root2 = tmp_path / "kb"
    root2.mkdir()
    from todoc.config import init_dataset
    init_dataset(root2)
    for name in ("a.md", "b.md"):
        (root2 / name).write_text(f"# {name}\n\nrefresh token content here for {name}.\n")
    documents = [
        {"document_id": f"doc:{n}", "path": n, "format": "markdown", "doc_type": "note", "title": n, "status": "ok"}
        for n in ("a.md", "b.md")
    ]
    hits, total, _ = search_documents(root2, documents, "refresh", limit=10, budget=5)
    assert total == 2
    assert len(hits) == 1


def test_search_heading_oserror(root, sample_md, monkeypatch):
    import todoc.application.search as search_mod

    real_parse = search_mod.parse_markdown
    calls = {"n": 0}

    def flaky(text):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("gone")
        return real_parse(text)

    monkeypatch.setattr(search_mod, "parse_markdown", flaky)
    documents = [{"document_id": "doc:notes/design.md", "path": "notes/design.md", "format": "markdown",
                  "doc_type": "note", "title": "Design", "status": "ok"}]
    hits, total, _ = search_documents(root, documents, "refresh")
    assert total == 1
    assert hits[0].heading_path == ()


def test_search_markdown_without_headings(root, tmp_path):
    root2 = tmp_path / "kb"
    root2.mkdir()
    from todoc.config import init_dataset
    init_dataset(root2)
    (root2 / "plain.md").write_text("just some refresh token text without headings\n")
    documents = [{"document_id": "doc:plain.md", "path": "plain.md", "format": "markdown",
                  "doc_type": "note", "title": "", "status": "ok"}]
    hits, total, _ = search_documents(root2, documents, "refresh")
    assert total == 1
    assert hits[0].heading_path == ()


# --- validator -------------------------------------------------------------

def test_check_markdown_links_unreadable(root):
    scanned = ScannedFile("gone.md", root / "gone.md", "markdown", 0, "sha256:")
    diags = _check_markdown_links("ds", scanned, root, {"gone.md"})
    assert diags[0].code == "markdown.unreadable"


def test_check_markdown_links_external_skipped(root):
    path = root / "ext.md"
    path.write_text("# Ext\n\n[a](https://example.com) [b](#anchor) [c](mailto:x@y.z) [d](http://x.y)\n")
    scanned = ScannedFile("ext.md", path, "markdown", path.stat().st_size, "sha256:")
    diags = _check_markdown_links("ds", scanned, root, {"ext.md"})
    assert diags == []


def test_check_markdown_links_empty_href(root):
    path = root / "empty.md"
    path.write_text("# Empty\n\n[x]()\n")
    scanned = ScannedFile("empty.md", path, "markdown", path.stat().st_size, "sha256:")
    diags = _check_markdown_links("ds", scanned, root, {"empty.md"})
    assert diags == []


def test_check_markdown_links_dotdot_at_root(root):
    path = root / "top.md"
    path.write_text("# Top\n\n[x](../../outside.md)\n")
    scanned = ScannedFile("top.md", path, "markdown", path.stat().st_size, "sha256:")
    diags = _check_markdown_links("ds", scanned, root, {"top.md"})
    assert len(diags) == 1
    assert diags[0].code == "markdown.link.target_missing"


def _validate(root: Path):
    dataset = load_dataset(root)
    dir_rules, doc_rules = load_rules(root, dataset)
    _folders, files = scan_dataset(root)
    return validate_dataset(root, dataset, files, dir_rules, doc_rules)


def test_validate_unsupported_status(root):
    dataset = load_dataset(root)
    dir_rules, doc_rules = load_rules(root, dataset)
    scanned = ScannedFile("big.md", root / "big.md", "markdown", 99999999, "sha256:", "unsupported")
    diags, _info = validate_dataset(root, dataset, [scanned], dir_rules, doc_rules)
    assert any(d.code == "file.unsupported" for d in diags)


def test_validate_permission_denied_status(root):
    dataset = load_dataset(root)
    dir_rules, doc_rules = load_rules(root, dataset)
    scanned = ScannedFile("secret.md", root / "secret.md", "markdown", 10, "sha256:", "permission_denied")
    diags, _info = validate_dataset(root, dataset, [scanned], dir_rules, doc_rules)
    assert any(d.code == "file.permission_denied" for d in diags)


def test_validate_invalid_utf8(root):
    path = root / "bad.md"
    path.write_bytes(b"\xff\xfe\x00bad")
    diags, _info = _validate(root)
    assert any(d.code == "file.unreadable" for d in diags)


def test_validate_ambiguous_doc_rule(root):
    rules_file = root / ".todoc" / "rules" / "document-rules.json"
    data = json.loads(rules_file.read_text())
    data["rules"] = [
        {"id": "a", "match": {"kind": "file", "glob": "**/*.md"}, "assign": {"doc_type": "note"}, "priority": 10},
        {"id": "b", "match": {"kind": "file", "glob": "**/*.md"}, "assign": {"doc_type": "adr"}, "priority": 10},
    ]
    rules_file.write_text(json.dumps(data))
    (root / "x.md").write_text("# X\n")
    diags, _info = _validate(root)
    assert any(d.code == "config.ambiguous_rule" for d in diags)


def test_validate_records_unreadable(root):
    from todoc.application.validator import _validate_records
    # abs_path is a directory: read_text raises IsADirectoryError (OSError).
    scanned = ScannedFile("dir.json", root, "json", 10, "sha256:", "ok")
    diags, records = _validate_records("ds", root, [scanned], {})
    assert diags == []
    assert records == []


def test_validate_relations_non_dict():
    records = [{"record_id": "w:1", "path": "w.json", "data": {"relations": ["notadict", 42]}}]
    assert validate_relations("ds", records) == []


# --- write -----------------------------------------------------------------

def test_apply_write_plan_caller_hash_mismatch(root):
    from todoc.adapters.filesystem.scanner import file_hash
    from todoc.domain.models import WritePlan
    (root / "records").mkdir(exist_ok=True)
    target = root / "records" / "x.json"
    target.write_text("old")
    plan = WritePlan("ds", "records/x.json", "new", file_hash(target), "sha256:x", "test")
    with pytest.raises(ConflictError):
        apply_write_plan(root, plan, expected_hash="sha256:other")


def test_apply_edit_ops_file_missing(root):
    with pytest.raises(ValidationError):
        apply_edit_ops(root, "missing.md", [{"line": 1, "text": "x"}])


def test_load_input_record_missing(tmp_path):
    with pytest.raises(ValidationError):
        load_input_record(tmp_path / "missing.json")


# --- config / models / errors / envelope -----------------------------------

def test_load_rules_missing_files(root):
    rules_dir = root / ".todoc" / "rules"
    for f in rules_dir.glob("*.json"):
        f.unlink()
    dataset = load_dataset(root)
    dir_rules, doc_rules = load_rules(root, dataset)
    assert dir_rules == []
    assert doc_rules == []


def test_model_to_dicts():
    record = Record("w:1", "workout", "ds", "w.json", "sha256:x", {"a": 1})
    assert record.to_dict()["record_id"] == "w:1"
    relation = Relation("t", "a", "b", "ds")
    assert relation.to_dict() == {"type_id": "t", "source_id": "a", "target_id": "b", "dataset_id": "ds"}
    report = ValidationReport("ds", "valid", "x.md", ())
    assert report.to_dict() == {"dataset_id": "ds", "status": "valid", "path": "x.md", "issues": []}


def test_access_error_exit_code():
    err = AccessError("denied")
    assert err.exit_code == 4
    assert err.code == "access.denied"


def test_envelope_table_with_diagnostics(capsys):
    envelope = make_envelope(True, {"a": 1}, [{"severity": "error", "code": "c", "path": "p", "message": "m"}])
    emit(envelope, "table")
    out = capsys.readouterr().out
    assert "[error] c p: m" in out


# --- service ---------------------------------------------------------------

def test_service_ambiguous_folder_rule(root, sample_md):
    rules_file = root / ".todoc" / "rules" / "directory-rules.json"
    data = json.loads(rules_file.read_text())
    data["rules"] = [
        {"id": "a", "match": {"kind": "directory", "basename": "notes"}, "assign": {"dir_type": "research"}, "priority": 10},
        {"id": "b", "match": {"kind": "directory", "basename": "notes"}, "assign": {"dir_type": "plan"}, "priority": 10},
    ]
    rules_file.write_text(json.dumps(data))
    ctx = DatasetContext(root)
    _f, _d, _r, _rel, diagnostics = ctx.scan_and_validate()
    assert any(d["code"] == "config.ambiguous_rule" for d in diagnostics)


def test_service_invalid_json_skipped(root):
    (root / "bad.json").write_text("{bad json")
    ctx = DatasetContext(root)
    _f, _d, records, _rel, _diag = ctx.scan_and_validate()
    assert all(r["path"] != "bad.json" for r in records)


def test_service_json_list_skipped(root):
    (root / "list.json").write_text("[1, 2, 3]")
    ctx = DatasetContext(root)
    _f, _d, records, _rel, _diag = ctx.scan_and_validate()
    assert all(r["path"] != "list.json" for r in records)


def test_service_relation_without_target_id(root):
    path = root / "records" / "w.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"record_id": "w:1", "entity_type": "workout", "relations": [{"type_id": "t"}]}))
    ctx = DatasetContext(root)
    _f, _d, _records, relations, _diag = ctx.scan_and_validate()
    assert relations == []


def test_service_front_matter_id(root):
    path = root / "notes" / "custom.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\nid: custom-id\n---\n\n# Custom\n")
    ctx = DatasetContext(root)
    _f, documents, _r, _rel, _d = ctx.scan_and_validate()
    custom = next(d for d in documents if d["path"] == "notes/custom.md")
    assert custom["document_id"] == "custom-id"


def test_resolve_roots_env(root, monkeypatch):
    monkeypatch.setenv("TODOC_ROOT", str(root))
    assert resolve_roots(()) == [root.resolve()]


# --- descriptors / resolver ------------------------------------------------

def test_load_json_file_missing(tmp_path):
    with pytest.raises(ValidationError):
        load_json_file(tmp_path / "missing.json")


def test_registry_load_dir_missing_base(root):
    registry = TypeRegistry()
    registry._load_dir(root / "nonexistent", "entity_type", registry.entity_types)
    assert registry.entity_types == {}


def test_registry_load_dir_stray_file_and_empty_dir(root):
    (root / ".todoc" / "entity_types" / "stray.txt").write_text("x")
    (root / ".todoc" / "entity_types" / "empty").mkdir()
    dataset = load_dataset(root)
    registry = TypeRegistry()
    registry.load(root, dataset)
    assert "workout" in registry.entity_types


def test_registry_unknown_doc_type_ref(root):
    dataset = load_dataset(root)
    registry = TypeRegistry()
    registry.load(root, dataset)
    with pytest.raises(ValidationError):
        registry.validate_references([], [{"id": "r", "assign": {"doc_type": "ghost"}}])


def test_glob_double_star_without_slash():
    assert glob_match("a**b", "axxb")
    assert glob_match("**", "a/b/c")
    assert glob_match("a**", "axyz")


def test_resolve_directory_rule_no_matchers():
    rules = [{"id": "x", "match": {"kind": "directory"}, "assign": {"dir_type": "note"}, "priority": 1}]
    dir_type, source, _ = resolve_type(rules, "a", "a", None, "dir_type", {}, "unknown")
    assert dir_type == "unknown"
    assert source == "default"


def test_resolve_file_rule_front_matter_not_dict():
    rules = [{"id": "x", "match": {"kind": "file", "front_matter": "bad"}, "assign": {"doc_type": "note"}, "priority": 1}]
    doc_type, source, _ = resolve_type(rules, "x.md", "x.md", {"a": 1}, "doc_type", {}, "unknown")
    assert doc_type == "unknown"
    assert source == "default"


def test_resolve_file_rule_no_matchers():
    rules = [{"id": "x", "match": {"kind": "file"}, "assign": {"doc_type": "note"}, "priority": 1}]
    doc_type, source, _ = resolve_type(rules, "x.md", "x.md", None, "doc_type", {}, "unknown")
    assert doc_type == "unknown"
    assert source == "default"
