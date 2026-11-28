"""The JSON adapter and an independent in-memory implementation share the index contract."""

from copy import deepcopy

import pytest

from todoc.application.registry import RegistryStore
from todoc.application.storage import IndexStatus
from todoc.service import DatasetContext


class MemoryIndex:
    def __init__(self):
        self.snapshot = None
        self.stats = {}
        self.published = 0

    def inspect(self, dataset_id, fingerprint=None):
        meta = self.read_current_meta()
        if meta is None:
            return IndexStatus("missing")
        if meta["dataset_id"] != dataset_id:
            return IndexStatus("corrupt")
        if fingerprint is not None and fingerprint != meta["corpus_digest"]:
            return IndexStatus("stale", meta)
        return IndexStatus("valid", meta)

    def read_current_meta(self):
        if self.snapshot is None:
            return None
        keys = ("dataset_id", "generation_id", "corpus_digest")
        return {key: self.snapshot[key] for key in keys}

    def load_current(self):
        return deepcopy(self.snapshot)

    def read_stats(self):
        return self.stats

    def write_stats(self, files):
        self.stats = {file.rel_path: {"hash": file.hash} for file in files}

    def publish(self, dataset, folders, documents, records, relations, diagnostics, digest=None, mentions=None):
        self.published += 1
        generation_id = str(self.published)
        self.snapshot = deepcopy({
            "dataset_id": dataset["dataset_id"], "generation_id": generation_id,
            "corpus_digest": digest, "folders": folders, "documents": documents,
            "records": records, "relations": relations, "diagnostics": diagnostics, "mentions": mentions,
        })
        return generation_id


class MemoryParseCache:
    def __init__(self):
        self.entries = {}

    def read(self, path, content_hash):
        return deepcopy(self.entries.get((path, content_hash)))

    def write(self, path, content_hash, payload):
        self.entries[(path, content_hash)] = deepcopy(payload)

    def invalidate(self, path):
        matching = [key for key in self.entries if key[0] == path]
        for key in matching:
            del self.entries[key]
        return bool(matching)


@pytest.mark.parametrize("store_factory", [RegistryStore, lambda _root: MemoryIndex()])
def test_index_contract_reads_current_source_without_publishing(root, sample_md, store_factory):
    index = store_factory(root)
    cache = MemoryParseCache()
    ctx = DatasetContext(root, index_store=index, parse_cache=cache)
    assert ctx.index_status().state == "missing"
    cold = ctx.read_index(include_mentions=False)
    assert any(doc["path"] == "notes/design.md" for doc in cold["documents"])
    assert ctx.index_status().state == "missing" and not cache.entries

    published = ctx.rebuild_index(observe=False)
    assert cache.entries
    assert ctx.index_status().state == "valid"
    assert ctx.read_index()["generation_id"] == published["generation_id"]
    assert index.inspect("different-dataset").state == "corrupt"

    sample_md.write_text("# Updated title\n", encoding="utf-8")
    fresh = ctx.read_index(include_mentions=False)
    assert index.inspect(ctx.dataset_id, fresh["corpus_digest"]).state == "stale"
    assert fresh["documents"][0]["title"] == "Updated title"
    assert ctx.load_published_index()["generation_id"] == published["generation_id"]
    if isinstance(index, MemoryIndex):
        assert not (root / ".todoc/index").exists()
        assert not (root / ".todoc/cache").exists()


class MemoryHistory:
    def __init__(self):
        self.events = []
        self.objects = {}
        self.refs = {"head": None, "tags": {}}

    def read_refs(self):
        return deepcopy(self.refs)

    def write_refs(self, refs):
        self.refs = deepcopy(refs)

    def read_events(self, *, strict=False):
        return deepcopy(self.events)

    def append_event(self, event):
        rev = str(len(self.events) + 1)
        self.events.append(deepcopy({**event, "rev": rev}))
        return rev

    def event_bytes(self, event):
        import json
        return len(json.dumps(event).encode("utf-8")) + 1

    def replace_events(self, events):
        self.events = deepcopy(events)

    def list_snapshots(self):
        return list(self.objects)

    def remove_snapshot(self, digest):
        return self.objects.pop(digest, None) is not None

    def read_snapshot(self, digest):
        return self.objects.get(digest)

    def write_snapshot(self, content):
        from hashlib import sha256

        digest = "sha256:" + sha256(content).hexdigest()
        self.objects[digest] = content
        return digest


@pytest.mark.parametrize("kind", ["jsonl", "memory"])
def test_history_contract_reads_back_verified_before_image(root, kind):
    from todoc.adapters.history.store import FileHistoryStore

    store = FileHistoryStore(root) if kind == "jsonl" else MemoryHistory()
    ctx = DatasetContext(root, history_store=store)
    assert store.read_events(strict=True) == []
    ctx.history_recorder().record("notes/design.md", b"old", b"updated", "doc.edit")
    event, = store.read_events(strict=True)
    assert event["kind"] == "doc.edit"
    assert store.read_snapshot(event["paths"][0]["before"]) == b"old"
    if kind == "memory":
        assert not (root / ".todoc/history/journal.jsonl").exists()


def test_history_log_rejects_an_incomplete_journal(root):
    from click.testing import CliRunner
    import json
    from todoc.cli import cli

    path = root / ".todoc/history/journal.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"paths":[', encoding="utf-8")
    result = CliRunner().invoke(cli, ["log", "--root", str(root)])
    assert result.exit_code == 6
    data = json.loads(result.output)
    assert data["diagnostics"][0]["code"] == "history.journal_truncated_line"
    assert data["data"]["meta"]["complete"] is False
    assert path.read_bytes() == b'{"paths":['


@pytest.mark.parametrize(("kind", "payload", "diagnostic"), [
    ("journal", b"\xff\n", "history.journal_unreadable"),
    ("journal", b'{"paths":[],"paths":[]}\n', "history.journal_invalid"),
    ("journal", b'{"paths":[3]}\n', "history.journal_invalid"),
    ("refs", b'{"tags":[]}', "history.refs_invalid"),
    ("refs", b"\xff", "history.refs_unreadable"),
])
def test_history_adapter_reports_corrupt_sources(root, kind, payload, diagnostic):
    from todoc.adapters.history.store import FileHistoryStore
    from todoc.errors import IncompleteError

    history = root / ".todoc/history"
    history.mkdir(parents=True, exist_ok=True)
    file = history / ("journal.jsonl" if kind == "journal" else "refs.json")
    file.write_bytes(payload)
    store = FileHistoryStore(root)
    with pytest.raises(IncompleteError) as error:
        if kind == "journal":
            store.read_events(strict=True)
        else:
            store.read_refs()
    assert error.value.code == diagnostic
    assert file.read_bytes() == payload


@pytest.mark.parametrize("damage", ["unreadable_pointer", "missing_shard", "wrong_hash", "unexpected_counts"])
def test_index_status_distinguishes_corrupt_from_inaccessible(root, sample_md, monkeypatch, damage):
    import json
    from pathlib import Path

    ctx = DatasetContext(root)
    ctx.rebuild_index(observe=False)
    index = ctx.store
    pointer = index.index_dir / "CURRENT.json"
    shard = index.current_dir / "documents.json"
    expected = "corrupt"
    if damage == "unreadable_pointer":
        original = Path.read_bytes

        def unreadable(path):
            if path == pointer:
                raise PermissionError("simulated")
            return original(path)

        monkeypatch.setattr(Path, "read_bytes", unreadable)
        expected = "inaccessible"
    elif damage == "missing_shard":
        shard.unlink()
    elif damage == "wrong_hash":
        shard.write_text("[]", encoding="utf-8")
    else:
        data = json.loads(pointer.read_text(encoding="utf-8"))
        data["counts"]["documents"] = True
        edited = json.dumps(data)
        pointer.write_text(edited, encoding="utf-8")
        (index.current_dir / "meta.json").write_text(edited, encoding="utf-8")
    assert index.inspect(ctx.dataset_id).state == expected


def test_verified_range_source_read_rejects_stale_hash(root, sample_md):
    from todoc.adapters.filesystem.scanner import file_hash, read_verified_text
    from todoc.errors import IncompleteError

    digest = file_hash(sample_md)
    sample_md.write_text("# Changed\n", encoding="utf-8")
    with pytest.raises(IncompleteError) as error:
        read_verified_text(root, "notes/design.md", digest)
    assert error.value.code == "read.changed"



def test_sync_uses_injected_history_and_parse_cache(root, sample_md):
    from todoc.application.sync import sync_files

    index = MemoryIndex()
    cache = MemoryParseCache()
    history = MemoryHistory()
    ctx = DatasetContext(root, index_store=index, parse_cache=cache, history_store=history)
    ctx.rebuild_index(observe=False)
    sample_md.write_text("# Edited directly\n", encoding="utf-8")
    result = sync_files(ctx, ["notes/design.md"])
    assert result["ok"]
    assert result["synced"][0]["status"] == "synced"
    assert history.read_events(strict=True)[0]["kind"] == "doc.sync"
    assert not (root / ".todoc/history").exists()
    assert not (root / ".todoc/cache").exists()



@pytest.mark.parametrize("kind", ["jsonl", "memory"])
def test_history_cleanup_uses_store_and_only_removes_snapshots_after_apply(root, kind):
    from todoc.adapters.history.store import FileHistoryStore
    from todoc.application.history import gc

    store = FileHistoryStore(root) if kind == "jsonl" else MemoryHistory()
    ctx = DatasetContext(root, history_store=store)
    ctx.history_recorder().record("notes/design.md", b"old", b"updated", "doc.edit")
    orphan = store.write_snapshot(b"orphan")
    events = store.read_events(strict=True)
    preview = gc(root, dry_run=True, store=store)
    assert preview["orphans_removed"] == 1
    assert store.read_snapshot(orphan) == b"orphan"
    result = gc(root, store=store)
    assert result["orphans_removed"] == preview["orphans_removed"]
    assert store.read_events(strict=True) == events
    assert store.read_snapshot(orphan) is None
    if kind == "memory":
        assert not (root / ".todoc/history").exists()



def test_cli_context_uses_composed_history_store(root, monkeypatch):
    import json
    from click.testing import CliRunner
    import todoc.cli as entry

    history = MemoryHistory()
    ctx = DatasetContext(root, index_store=MemoryIndex(), parse_cache=MemoryParseCache(), history_store=history)
    ctx.history_recorder().record("notes/design.md", b"old", b"new", "doc.edit")
    revision = history.read_events(strict=True)[0]["rev"]
    history.write_refs({"head": revision, "tags": {"release": {"rev": revision}}})
    monkeypatch.setattr(entry, "DatasetContext", lambda resolved: ctx)
    result = CliRunner().invoke(entry.cli, ["context", "--root", str(root), "--tag", "release"])
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["data"]["result"]["events"][0]["rev"] == revision
    assert not (root / ".todoc/history").exists()



def test_atomic_write_plan_keeps_a_competing_creation(root, monkeypatch):
    import os
    from todoc.application.write import apply_write_plan
    from todoc.domain.models import WritePlan
    from todoc.errors import ConflictError

    target = root / "notes/new.md"
    real_link = os.link

    def competing_link(source, destination, *args, **kwargs):
        target.write_bytes(b"the other writer")
        return real_link(source, destination, *args, **kwargs)

    monkeypatch.setattr(os, "link", competing_link)
    plan = WritePlan(dataset_id="test", target_path="notes/new.md", new_content="# Mine\n",
                     expected_hash=None, new_hash="sha256:unused", basis="test publication")
    with pytest.raises(ConflictError, match="already exists"):
        apply_write_plan(root, plan)
    assert target.read_bytes() == b"the other writer"
    assert not list(target.parent.glob("*.tmp.*"))



def test_backup_rejects_missing_plan_sources_and_existing_destinations(root):
    from todoc.adapters.history.store import FileHistoryStore
    from todoc.errors import AccessError, ConflictError

    store = FileHistoryStore(root)
    assert store.write_backup(root / "backup", store.backup_manifest()) == 0
    assert not (root / "backup").exists()
    with pytest.raises(AccessError):
        store.write_backup(root / ".todoc/history/backup", {})
    store.append_event({"kind": "snapshot", "paths": []})
    manifest = store.backup_manifest()
    store.append_event({"kind": "doc.edit", "paths": []})
    with pytest.raises(ConflictError, match="changed before"):
        store.write_backup(root / "backup", manifest)
    backup = root / "backup"
    backup.mkdir()
    with pytest.raises(ConflictError, match="already exists"):
        store.write_backup(backup, store.backup_manifest())


@pytest.mark.parametrize("issue", ["unreadable", "changed"])
def test_backup_detects_source_change_or_io_failure_after_manifest(root, monkeypatch, issue):
    from pathlib import Path
    from todoc.adapters.history.store import FileHistoryStore
    from todoc.errors import ConflictError, IncompleteError

    store = FileHistoryStore(root)
    store.append_event({"kind": "snapshot", "paths": []})
    manifest = store.backup_manifest()
    monkeypatch.setattr(store, "backup_manifest", lambda: manifest)
    if issue == "changed":
        store.append_event({"kind": "doc.edit", "paths": []})
        with pytest.raises(ConflictError, match="changed during"):
            store.write_backup(root / "backup", manifest)
    else:
        original = Path.read_bytes

        def read_bytes(path):
            if path.name == "journal.jsonl":
                raise PermissionError("injected")
            return original(path)

        monkeypatch.setattr(Path, "read_bytes", read_bytes)
        with pytest.raises(IncompleteError, match="Backup may be incomplete"):
            store.write_backup(root / "backup", manifest)


def test_store_rejects_unreadable_journal_and_manifest(root, monkeypatch):
    from todoc.adapters.history.store import FileHistoryStore
    from todoc.errors import IncompleteError

    store = FileHistoryStore(root)
    journal = root / ".todoc/history/journal.jsonl"
    journal.mkdir(parents=True)
    with pytest.raises(IncompleteError) as unreadable:
        store.read_events(strict=True)
    assert unreadable.value.code == "history.journal_unreadable"
    journal.rmdir()
    store.append_event({"kind": "snapshot", "paths": []})

    def unreadable_file(path):
        raise PermissionError("injected")

    monkeypatch.setattr("todoc.adapters.history.store.file_hash", unreadable_file)
    with pytest.raises(IncompleteError) as unavailable:
        store.backup_manifest()
    assert unavailable.value.code == "history.backup_unreadable"



def test_cli_subprocess_reads_through_injected_drivers(root, sample_md, tmp_path):
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    project = Path(__file__).resolve().parents[2]
    script = tmp_path / "composed_todoc.py"
    script.write_text(
        """
from pathlib import Path
from test_storage_contracts import MemoryHistory, MemoryIndex, MemoryParseCache
from todoc.adapters.history.store import FileHistoryStore
import todoc.cli as entry
from todoc.service import DatasetContext

def forbidden(*args, **kwargs):
    raise AssertionError("The CLI fell back to the filesystem history adapter")

FileHistoryStore.read_events = forbidden
FileHistoryStore.read_refs = forbidden
FileHistoryStore.read_snapshot = forbidden
history = MemoryHistory()
revision = history.append_event({"kind": "doc.edit", "paths": [{"path": "notes/design.md"}]})
history.write_refs({"head": revision, "tags": {"release": {"rev": revision}}})
def compose(root: Path):
    return DatasetContext(root, index_store=MemoryIndex(), parse_cache=MemoryParseCache(), history_store=history)

entry.DatasetContext = compose
entry.main()
""",
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONPATH": os.pathsep.join([str(project / "src"), str(project / "tests/unit")])}
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    calls = [
        (["context", "--tag", "release"], lambda data: data["events"][0]["kind"] == "doc.edit"),
        (["docs", "list", "--within", "notes"], lambda data: data["items"][0]["path"] == "notes/design.md"),
    ]
    for args, check in calls:
        result = subprocess.run([sys.executable, str(script), "--root", str(root), *args],
                                env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, (result.stdout, result.stderr)
        envelope = json.loads(result.stdout)
        assert envelope["schema_version"] == 2
        assert check(envelope["data"]["result"])
    assert {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()} == before



def test_history_compaction_preserves_revision_of_imported_jsonl(root):
    from todoc.adapters.history.store import FileHistoryStore
    from todoc.application.history import gc

    store = FileHistoryStore(root)
    journal = root / ".todoc/history/journal.jsonl"
    journal.parent.mkdir(parents=True)
    journal.write_text('{ "paths": [], "kind": "snapshot" }\n', encoding="utf-8")
    event, = store.read_events(strict=True)
    store.write_refs({"head": event["rev"], "tags": {"imported": {"rev": event["rev"]}}})
    result = gc(root, store=store, refs=store.read_refs())
    assert result["kept_events"] == 1
    assert store.read_events(strict=True) == [event]
    assert store.read_refs()["tags"]["imported"]["rev"] == event["rev"]
    assert store.event_bytes(event) == journal.stat().st_size


@pytest.mark.parametrize("content", [b"invalid compressed content", b"different decoded content"])
def test_history_rejects_corrupt_snapshot(root, content):
    import zlib
    from todoc.adapters.history import objects
    from todoc.adapters.history.store import FileHistoryStore
    from todoc.errors import IncompleteError

    store = FileHistoryStore(root)
    digest = store.write_snapshot(b"original")
    path = objects.object_path(root, digest)
    path.write_bytes(zlib.compress(content) if content.startswith(b"different") else content)
    with pytest.raises(IncompleteError) as error:
        store.read_snapshot(digest)
    assert error.value.code == "history.object_corrupt"


def test_history_refuses_invalid_snapshot_identifier(root):
    from todoc.adapters.history.store import FileHistoryStore
    from todoc.errors import IncompleteError

    store = FileHistoryStore(root)
    with pytest.raises(IncompleteError) as error:
        store.read_snapshot("invalid-digest")
    assert error.value.code == "history.object_corrupt"


def test_history_refuses_symlinked_journal(root, tmp_path):
    from todoc.adapters.history.store import FileHistoryStore
    from todoc.errors import AccessError

    outside = tmp_path / "outside.jsonl"
    outside.write_text("{}\n", encoding="utf-8")
    journal = root / ".todoc/history/journal.jsonl"
    journal.parent.mkdir(parents=True)
    try:
        journal.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are unavailable")
    store = FileHistoryStore(root)
    with pytest.raises(AccessError):
        store.read_events(strict=True)
    with pytest.raises(AccessError):
        store.append_event({"kind": "snapshot", "paths": []})
    assert outside.read_text(encoding="utf-8") == "{}\n"



def test_verified_source_read_rejects_scope_and_encoding(tmp_path):
    from todoc.adapters.filesystem.scanner import file_hash, read_verified_text
    from todoc.errors import IncompleteError

    root = tmp_path / "dataset"
    root.mkdir()
    file = root / "bad.md"
    file.write_bytes(b"\xff")
    with pytest.raises(IncompleteError) as unreadable:
        read_verified_text(root, "bad.md", file_hash(file))
    assert unreadable.value.code == "file.unreadable"
    with pytest.raises(IncompleteError) as escaped:
        read_verified_text(root, "../outside.md", "sha256:irrelevant")
    assert escaped.value.code == "read.changed"



@pytest.mark.parametrize(("damage", "expected"), [
    ("pointer-schema", "corrupt"), ("missing-generation", "corrupt"), ("legacy-manifest", "stale"),
    ("wrong-manifest", "corrupt"), ("invalid-counts", "corrupt"), ("invalid-shard-type", "valid"),
    ("missing-shard", "corrupt"), ("invalid-shard-json", "valid"),
])
def test_published_index_failure_matrix(root, sample_md, damage, expected):
    import hashlib
    import json

    ctx = DatasetContext(root)
    ctx.rebuild_index(observe=False)
    index = ctx.store
    current = index.index_dir / "CURRENT.json"
    pointer = json.loads(current.read_text())
    docs = index.current_dir / "documents.json"
    if damage == "pointer-schema":
        pointer["schema_version"] = -1
    elif damage == "missing-generation":
        del pointer["generation_id"]
    elif damage == "legacy-manifest":
        del pointer["shards"]
    elif damage == "wrong-manifest":
        del pointer["shards"]["documents"]
    elif damage == "invalid-counts":
        pointer["counts"]["documents"] = -1
    elif damage == "missing-shard":
        docs.unlink()
    else:
        docs.write_text("{}" if damage == "invalid-shard-type" else "{", encoding="utf-8")
        pointer["shards"]["documents"] = "sha256:" + hashlib.sha256(docs.read_bytes()).hexdigest()
    serialized = json.dumps(pointer)
    current.write_text(serialized, encoding="utf-8")
    (index.current_dir / "meta.json").write_text(serialized, encoding="utf-8")
    assert index.inspect(ctx.dataset_id).state == expected
    payload = ctx.read_index(include_mentions=False)
    assert any(item["path"] == "notes/design.md" for item in payload["documents"])
    assert current.read_text() == serialized


@pytest.mark.parametrize("part", ["pointer", "shard"])
def test_index_distinguishes_unreadable_shards_from_corruption(root, sample_md, monkeypatch, part):
    from pathlib import Path
    from todoc.adapters.filesystem.scanner import file_hash

    ctx = DatasetContext(root)
    ctx.rebuild_index(observe=False)
    store = ctx.store
    if part == "pointer":
        pointer = store.index_dir / "CURRENT.json"
        original = Path.read_bytes

        def read(path):
            if path == pointer:
                raise PermissionError("injected pointer failure")
            return original(path)

        monkeypatch.setattr(Path, "read_bytes", read)
    else:
        shard = store.current_dir / "documents.json"

        def hash_shard(path):
            if path == shard:
                raise PermissionError("injected shard failure")
            return file_hash(path)

        monkeypatch.setattr("todoc.application.registry.file_hash", hash_shard)
    assert store.inspect(ctx.dataset_id).state == "inaccessible"
    assert any(item["path"] == "notes/design.md" for item in ctx.read_index()["documents"])


def test_index_notices_pointer_swap_during_verification(root, sample_md, monkeypatch):
    from pathlib import Path

    ctx = DatasetContext(root)
    ctx.rebuild_index(observe=False)
    store = ctx.store
    pointer = store.index_dir / "CURRENT.json"
    original = Path.read_bytes
    observations = 0

    def read(path):
        nonlocal observations
        data = original(path)
        if path == pointer:
            observations += 1
            if observations > 1:
                return data + b" "
        return data

    monkeypatch.setattr(Path, "read_bytes", read)
    assert store.inspect(ctx.dataset_id).state == "stale"
    assert observations == 2



@pytest.mark.parametrize("location", ["history", "entry"])
def test_backup_manifest_refuses_paths_that_resolve_outside_store(root, tmp_path, location):
    from todoc.adapters.history.store import FileHistoryStore
    from todoc.errors import AccessError

    outside = tmp_path / "external-history"
    outside.mkdir()
    (outside / "private").write_text("outside", encoding="utf-8")
    base = root / ".todoc/history"
    if location == "entry":
        base.mkdir()
    try:
        if location == "history":
            base.symlink_to(outside, target_is_directory=True)
        else:
            (base / "entry").symlink_to(outside / "private")
    except OSError:
        pytest.skip("symlinks are unavailable")
    with pytest.raises(AccessError):
        FileHistoryStore(root).backup_manifest()


def test_atomic_write_reports_unsupported_exclusive_publication(root, monkeypatch):
    import os
    from todoc.application.write import apply_write_plan
    from todoc.domain.models import WritePlan
    from todoc.errors import IncompleteError

    def disallow(*args, **kwargs):
        raise PermissionError("filesystem denied exclusive publish")

    monkeypatch.setattr(os, "link", disallow)
    plan = WritePlan(dataset_id="test", target_path="notes/new.md", new_content="# New\n",
                     expected_hash=None, new_hash="sha256:unused", basis="test publication")
    with pytest.raises(IncompleteError) as error:
        apply_write_plan(root, plan)
    assert error.value.code == "write.create_failed"
    assert not list((root / "notes").iterdir())
