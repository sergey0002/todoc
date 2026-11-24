"""Final edge-branch tests to reach 100% coverage."""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

import pytest

from todoc.adapters.filesystem.scanner import ScannedFile, atomic_write
from todoc.application.query import graph_neighbors, query_records
from todoc.application.registry import RegistryStore, _config_digest
from todoc.application.validator import _check_markdown_links, validate_dataset
from todoc.config import load_dataset, load_rules


def test_main_module_entry(root, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["todoc", "--root", str(root), "check", "--output", "json"])
    runpy.run_module("todoc", run_name="__main__")  # must not raise


def test_main_module_imported():
    import todoc.__main__  # noqa: F401  (covers the __name__ guard False branch)


def test_atomic_write_unlink_failure(root, monkeypatch):
    target = root / "out.txt"

    def boom_replace(src, dst):
        raise OSError("disk full")

    def boom_unlink(path):
        raise OSError("cannot unlink")

    monkeypatch.setattr(os, "replace", boom_replace)
    monkeypatch.setattr(os, "unlink", boom_unlink)
    with pytest.raises(OSError):
        atomic_write(target, "data")


def test_query_lte_filter():
    records = [
        {"record_id": "w:1", "entity_type": "workout", "data": {"date": "2026-11-01"}},
        {"record_id": "w:2", "entity_type": "workout", "data": {"date": "2026-11-20"}},
    ]
    items, total, _ = query_records(records, "workout", {"date": {"$lte": "2026-11-10"}})
    assert total == 1
    assert items[0]["record_id"] == "w:1"


def test_graph_type_mismatch_skipped():
    relations = [
        {"type_id": "t1", "source_id": "a", "target_id": "b"},
        {"type_id": "t2", "source_id": "a", "target_id": "c"},
    ]
    edges = graph_neighbors(relations, "a", "t1", depth=1, limit=10)
    assert edges == [{"type_id": "t1", "from": "a", "to": "b"}]


def test_config_digest_without_todoc(tmp_path):
    digest = _config_digest(tmp_path)
    assert digest.startswith("sha256:")


def test_publish_tmp_missing_on_failure(root, monkeypatch):
    store = RegistryStore(root)
    real_rename = Path.rename

    def bad_rename(self, target):
        # Simulate tmp dir vanishing before rename completes.
        import shutil
        shutil.rmtree(self, ignore_errors=True)
        raise OSError("rename failed")

    monkeypatch.setattr(Path, "rename", bad_rename)
    with pytest.raises(OSError):
        store.publish({"dataset_id": "ds"}, [], [], [], [], [])


def test_check_markdown_links_empty_wikilink(root):
    path = root / "wiki.md"
    path.write_text("# Wiki\n\n[[ ]]\n")
    scanned = ScannedFile("wiki.md", path, "markdown", path.stat().st_size, "sha256:")
    diags = _check_markdown_links("ds", scanned, root, {"wiki.md"})
    assert diags == []


def test_check_markdown_links_absolute_target(root):
    (root / "notes").mkdir(parents=True, exist_ok=True)
    (root / "notes" / "design.md").write_text("# Design\n")
    path = root / "abs.md"
    path.write_text("# Abs\n\n[x](/notes/design.md)\n")
    scanned = ScannedFile("abs.md", path, "markdown", path.stat().st_size, "sha256:")
    diags = _check_markdown_links("ds", scanned, root, {"abs.md", "notes/design.md"})
    assert diags == []


def test_validate_unknown_format_falls_through(root):
    dataset = load_dataset(root)
    dir_rules, doc_rules = load_rules(root, dataset)
    scanned = ScannedFile("x.yaml", root / "x.yaml", "yaml", 10, "sha256:", "ok")
    (root / "x.yaml").write_text("a: 1\n")
    diags, info = validate_dataset(root, dataset, [scanned], dir_rules, doc_rules)
    assert info["x.yaml"]["format"] == "yaml"
    assert diags == []
