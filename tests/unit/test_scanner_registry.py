import json

import pytest

from todoc.adapters.filesystem.scanner import atomic_write, file_hash, is_within_root, scan_dataset
from todoc.application.registry import (RegistryStore, corpus_digest, parse_cache_key,
                                          read_parse_cache, write_parse_cache)
from todoc.service import DatasetContext
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


# --- Фаза 0: один снимок и инвалидация по дайджесту (K31, K32) --------------


def test_corpus_digest_stable_on_unchanged_corpus(root, sample_md):
    _f, files = scan_dataset(root)
    first = corpus_digest(files, "sha256:cfg")
    _f2, files2 = scan_dataset(root)
    assert corpus_digest(files2, "sha256:cfg") == first


def test_corpus_digest_changes_on_edit(root, sample_md):
    _f, files = scan_dataset(root)
    before = corpus_digest(files, "sha256:cfg")
    sample_md.write_text(sample_md.read_text(encoding="utf-8") + "\nправка\n", encoding="utf-8")
    _f2, files2 = scan_dataset(root)
    assert corpus_digest(files2, "sha256:cfg") != before


def test_corpus_digest_depends_on_config(root, sample_md):
    _f, files = scan_dataset(root)
    assert corpus_digest(files, "sha256:a") != corpus_digest(files, "sha256:b")


def test_publish_keeps_single_snapshot(root):
    """K32: повторная публикация перезаписывает снимок, а не добавляет новый."""
    store = RegistryStore(root)
    store.publish({"dataset_id": "ds"}, [{"path": "."}], [], [], [], [], "sha256:d1")
    first = store.publish({"dataset_id": "ds"}, [{"path": "."}], [], [], [], [], "sha256:d2")
    assert list(store.index_dir.iterdir()) and store.current_dir.is_dir()
    assert store.current_generation_id() == first
    # ни одного каталога-поколения: только current/, CURRENT.json и, возможно, stats
    assert not (store.index_dir / "generations").exists()


def test_publish_records_digest_and_created_at(root):
    store = RegistryStore(root)
    store.publish({"dataset_id": "ds"}, [], [], [], [], [], "sha256:abc")
    meta = store.read_current_meta()
    assert meta["corpus_digest"] == "sha256:abc"
    assert meta["created_at"].endswith("Z")


def test_publish_removes_legacy_generations(root):
    store = RegistryStore(root)
    legacy = store.index_dir / "generations" / "deadbeef0000"
    legacy.mkdir(parents=True)
    (legacy / "meta.json").write_text("{}", encoding="utf-8")
    store.publish({"dataset_id": "ds"}, [], [], [], [], [], None)
    assert not store.legacy_generations_dir.exists()


def test_hash_cache_reuses_stored_digest(root, sample_md):
    _f, files = scan_dataset(root)
    target = next(f for f in files if f.rel_path == "notes/design.md")
    cache = {target.rel_path: {"hash": "sha256:cached", "mtime": target.abs_path.stat().st_mtime_ns,
                               "size": target.size}}
    _f2, files2 = scan_dataset(root, hash_cache=cache)
    reused = next(f for f in files2 if f.rel_path == "notes/design.md")
    assert reused.hash == "sha256:cached"


def test_hash_cache_ignored_when_mtime_changed(root, sample_md):
    _f, files = scan_dataset(root)
    target = next(f for f in files if f.rel_path == "notes/design.md")
    cache = {target.rel_path: {"hash": "sha256:stale", "mtime": target.abs_path.stat().st_mtime_ns - 1,
                               "size": target.size}}
    _f2, files2 = scan_dataset(root, hash_cache=cache)
    reused = next(f for f in files2 if f.rel_path == "notes/design.md")
    assert reused.hash == target.hash


def test_ensure_index_does_not_republish(root, sample_md):
    """K31: команда чтения на неизменном корпусе не издаёт новый снимок."""
    ctx = DatasetContext(root)
    first = ctx.ensure_index()
    for _ in range(4):
        again = ctx.ensure_index()
        assert again["generation_id"] == first["generation_id"]


def test_ensure_index_republishes_after_edit(root, sample_md):
    ctx = DatasetContext(root)
    first = ctx.ensure_index()
    sample_md.write_text(sample_md.read_text(encoding="utf-8") + "\nещё\n", encoding="utf-8")
    second = ctx.ensure_index()
    assert second["generation_id"] != first["generation_id"]


def test_rebuild_index_force_vs_reuse(root, sample_md):
    ctx = DatasetContext(root)
    first = ctx.rebuild_index()
    assert first["reused"] is False
    soft = ctx.rebuild_index(force=False)
    assert soft["reused"] is True and soft["generation_id"] == first["generation_id"]
    hard = ctx.rebuild_index(force=True)
    assert hard["reused"] is False and hard["generation_id"] != first["generation_id"]


def test_stats_written_and_reusable(root, sample_md):
    ctx = DatasetContext(root)
    ctx.ensure_index()
    stats = ctx.store.read_stats()
    assert "notes/design.md" in stats
    entry = stats["notes/design.md"]
    assert entry["hash"].startswith("sha256:") and entry["size"] > 0 and entry["mtime"] > 0


def test_read_stats_tolerates_corrupt_file(root):
    store = RegistryStore(root)
    store.stats_path.parent.mkdir(parents=True, exist_ok=True)
    store.stats_path.write_text("не json", encoding="utf-8")
    assert store.read_stats() == {}
    store.stats_path.write_text('{"files": "не словарь"}', encoding="utf-8")
    assert store.read_stats() == {}


def test_publish_clears_stale_tmp_dir(root):
    store = RegistryStore(root)
    leftover = store.index_dir / ".tmp-current"
    leftover.mkdir(parents=True)
    (leftover / "junk.json").write_text("{}", encoding="utf-8")
    store.publish({"dataset_id": "ds"}, [], [], [], [], [], None)
    assert not leftover.exists()
    assert store.current_dir.is_dir()


def test_require_current_returns_payload(root):
    store = RegistryStore(root)
    store.publish({"dataset_id": "ds"}, [{"path": "."}], [{"path": "a.md"}], [], [], [], "sha256:d")
    payload = store.require_current()
    assert payload["documents"] == [{"path": "a.md"}]


def test_mtime_ns_of_unreadable_path_is_zero(root):
    from todoc.application.registry import _mtime_ns
    assert _mtime_ns(root / "нет" / "такого.json") == 0


def test_hash_cache_with_invalid_digest_is_ignored(root, sample_md):
    """Битый хеш в кеше не принимается на веру — файл перечитывается."""
    _f, files = scan_dataset(root)
    target = next(f for f in files if f.rel_path == "notes/design.md")
    cache = {target.rel_path: {"hash": "не-хеш", "mtime": target.abs_path.stat().st_mtime_ns,
                               "size": target.size}}
    _f2, files2 = scan_dataset(root, hash_cache=cache)
    assert next(f for f in files2 if f.rel_path == "notes/design.md").hash == target.hash


def test_ensure_index_raises_when_publish_unreadable(root, sample_md, monkeypatch):
    """Защитная ветка: публикация прошла, но снимок не читается."""
    ctx = DatasetContext(root)
    monkeypatch.setattr(ctx.store, "load_current", lambda: None)
    with pytest.raises(IncompleteError):
        ctx.ensure_index()


def test_rebuild_index_soft_falls_back_when_snapshot_unreadable(root, sample_md, monkeypatch):
    """Дайджест совпал, но снимок пропал — soft-режим обязан пересобрать, а не упасть."""
    ctx = DatasetContext(root)
    ctx.rebuild_index()
    real_load = ctx.store.load_current
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        return None if calls["n"] == 1 else real_load()

    monkeypatch.setattr(ctx.store, "load_current", flaky)
    result = ctx.rebuild_index(force=False)
    assert result["reused"] is False


def test_ensure_index_rebuilds_when_snapshot_vanished(root, sample_md, monkeypatch):
    """Дайджест совпал, но current/ пропал — ensure_index обязан пересобрать."""
    ctx = DatasetContext(root)
    ctx.ensure_index()
    real_load = ctx.store.load_current
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        return None if calls["n"] == 1 else real_load()

    monkeypatch.setattr(ctx.store, "load_current", flaky)
    payload = ctx.ensure_index()
    assert payload["documents"]
