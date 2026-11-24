import json

import pytest

from todoc.adapters.filesystem.scanner import atomic_write, file_hash, is_within_root, scan_dataset
from todoc.application.registry import RegistryStore, parse_cache_key, read_parse_cache, write_parse_cache
from todoc.errors import IncompleteError


def test_scan_finds_files(root, sample_md, sample_csv):
    folders, files = scan_dataset(root)
    paths = [f.rel_path for f in files]
    assert "notes/design.md" in paths
    assert "data/runs.csv" in paths
    assert all(not p.startswith(".todoc/") for p in paths)
    assert all(f.hash.startswith("sha256:") for f in files)


def test_scan_skips_symlink_by_default(root, sample_md):
    link = root / "link.md"
    link.symlink_to(root / "notes" / "design.md")
    _folders, files = scan_dataset(root)
    assert "link.md" not in [f.rel_path for f in files]


def test_scan_follow_symlink_within(root, sample_md):
    link = root / "link.md"
    link.symlink_to(root / "notes" / "design.md")
    _folders, files = scan_dataset(root, follow_symlinks=True)
    assert "link.md" in [f.rel_path for f in files]


def test_is_within_root(root):
    assert is_within_root(root, root / "a" / "b.md")
    assert not is_within_root(root, root.parent / "outside.md")


def test_atomic_write(root):
    target = root / "out.txt"
    atomic_write(target, "hello")
    assert target.read_text() == "hello"
    atomic_write(target, b"bytes")
    assert target.read_bytes() == b"bytes"


def test_file_hash(root):
    path = root / "h.txt"
    path.write_text("abc")
    assert file_hash(path).startswith("sha256:")


def test_registry_publish_load(root):
    store = RegistryStore(root)
    gen = store.publish({"dataset_id": "ds"}, [{"path": "."}], [{"path": "a.md"}], [], [], [])
    assert store.current_generation_id() == gen
    payload = store.load_current()
    assert payload["documents"] == [{"path": "a.md"}]
    assert payload["generation_id"] == gen


def test_registry_require_current_missing(root):
    store = RegistryStore(root)
    with pytest.raises(IncompleteError):
        store.require_current()


def test_registry_corrupt_current(root):
    store = RegistryStore(root)
    store.publish({"dataset_id": "ds"}, [], [], [], [], [])
    (store.index_dir / "CURRENT.json").write_text("not json")
    assert store.current_generation_id() is None


def test_parse_cache_roundtrip(root):
    key = parse_cache_key("ds", "a.md", "sha256:x", "v1")
    write_parse_cache(root, key, {"path": "a.md"})
    assert read_parse_cache(root, key) == {"path": "a.md"}
    assert read_parse_cache(root, "missing") is None


def test_parse_cache_corrupt(root):
    key = "badkey"
    cache_dir = root / ".todoc" / "cache" / "parse"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key}.json").write_text("not json")
    assert read_parse_cache(root, key) is None
