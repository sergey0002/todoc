"""Dataset-scoped JSONL journal and local object-store adapter."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, ContextManager

from todoc.adapters.filesystem.locks import directory_lock
from todoc.adapters.filesystem.scanner import atomic_write, file_hash, is_within_root
from todoc.adapters.formats.jsonfmt import parse_json
from todoc.adapters.history import journal, objects
from todoc.errors import AccessError, ConflictError, IncompleteError


class FileHistoryStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _checked_path(self, path: Path) -> Path:
        base = journal.history_dir(self.root)
        if path.is_symlink() or not is_within_root(self.root, path) or not is_within_root(base, path):
            raise AccessError(f"History path is outside the store: {path}", "access.outside_data_root")
        return path

    def transaction(self) -> ContextManager[None]:
        """Serialize cooperating writers across journal, refs and objects."""
        return directory_lock(self._checked_path(journal.history_dir(self.root) / ".write.lock"))

    def read_events(self, *, strict: bool = False) -> list[dict[str, Any]]:
        if not strict:
            return journal.read_events(self.root)
        path = self._checked_path(journal.journal_path(self.root))
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            return []
        except OSError as exc:
            raise IncompleteError(f"Could not read the history journal: {exc}", "history.journal_unreadable") from exc
        try:
            text = raw.decode("utf-8")
        except UnicodeError as exc:
            raise IncompleteError("History journal is not valid UTF-8.", "history.journal_unreadable") from exc
        if text and not text.endswith("\n"):
            raise IncompleteError("History journal has an incomplete final line.", "history.journal_truncated_line")
        events = []
        for number, line in enumerate(text.split("\n"), 1):
            line = line.strip()
            if not line:
                continue
            event, errors = parse_json(line)
            if errors or not isinstance(event, dict):
                raise IncompleteError(f"Invalid event on journal line {number}.", "history.journal_invalid")
            paths = event.get("paths", [])
            if not isinstance(paths, list) or any(not isinstance(item, dict) for item in paths):
                raise IncompleteError(f"Invalid event paths on line {number}.", "history.journal_invalid")
            event.setdefault("rev", journal.event_rev(line))
            events.append(event)
        return events

    def refs_path(self) -> Path:
        return journal.history_dir(self.root) / "refs.json"

    def read_legacy_refs(self) -> dict[str, Any]:
        try:
            return self.read_refs()
        except IncompleteError:
            return {"head": None, "tags": {}}

    def truncated_final_line(self) -> bool:
        return journal.truncated_last_line(self.root)

    def backup_to_existing_directory(self, destination: Path) -> int:
        source = journal.history_dir(self.root)
        if not source.is_dir():
            return 0
        destination.mkdir(parents=True, exist_ok=True)
        count = 0
        for path in source.rglob("*"):
            if not path.is_file():
                continue
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
            count += 1
        return count

    def read_refs(self) -> dict[str, Any]:
        path = self._checked_path(self.refs_path())
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"head": None, "tags": {}}
        except (OSError, UnicodeError) as exc:
            raise IncompleteError("Could not read history refs.", "history.refs_unreadable") from exc
        value, errors = parse_json(raw)
        if errors or not isinstance(value, dict) or not isinstance(value.get("tags", {}), dict):
            raise IncompleteError("History refs are not valid.", "history.refs_invalid")
        return {"head": None, "tags": {}, **value}

    def write_refs(self, refs: dict[str, Any]) -> None:
        atomic_write(self._checked_path(self.refs_path()), json.dumps(refs, indent=2, ensure_ascii=False) + "\n")

    def append_event(self, event: dict[str, Any]) -> str:
        # Atomic logical append: after a publication exception no event is visible.
        # Cooperating writers hold transaction(); preserve every old byte verbatim.
        path = self._checked_path(journal.journal_path(self.root))
        prefix = path.read_bytes() if path.exists() else b""
        payload = {k: v for k, v in event.items() if k != "rev"}
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        atomic_write(path, prefix + (line + "\n").encode("utf-8"))
        return journal.event_rev(line)

    def event_bytes(self, event: dict[str, Any]) -> int:
        return journal.events_bytes([event])

    def replace_events(self, events: list[dict[str, Any]]) -> None:
        self._checked_path(journal.journal_path(self.root))
        journal.rewrite(self.root, events)

    def list_snapshots(self) -> list[str]:
        """Return object digests ordered by age, with a stable tie-breaker."""
        source = self._checked_path(objects.objects_dir(self.root))
        files = [path for path in source.glob("[0-9a-f][0-9a-f]/*") if path.is_file()
                 and len(path.name) == 62 and all(char in "0123456789abcdef" for char in path.name)]
        files.sort(key=lambda path: (path.stat().st_mtime_ns, path.as_posix()))
        return ["sha256:" + path.parent.name + path.name for path in files]

    def _snapshot_path(self, digest: str) -> Path:
        if not isinstance(digest, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None:
            raise IncompleteError(f"Invalid history snapshot identifier: {digest!r}", "history.object_corrupt")
        path = self._checked_path(objects.object_path(self.root, digest))
        if not is_within_root(objects.objects_dir(self.root), path):
            raise AccessError(f"Snapshot is outside the object store: {path}", "access.outside_data_root")
        return path

    def remove_snapshot(self, digest: str) -> bool:
        self._snapshot_path(digest)
        return objects.remove_object(self.root, digest)

    def read_snapshot(self, digest: str) -> bytes | None:
        path = self._snapshot_path(digest)
        if not path.exists():
            return None
        content = objects.read_snapshot(self.root, digest)
        if content is None or objects.content_hash(content) != digest:
            raise IncompleteError(f"History snapshot {digest} is corrupt.", "history.object_corrupt")
        return content

    def write_snapshot(self, content: bytes) -> str:
        self._snapshot_path(objects.content_hash(content))
        return objects.write_snapshot(self.root, content)

    def backup_manifest(self) -> dict[str, str]:
        source = journal.history_dir(self.root)
        if not is_within_root(self.root, source):
            raise AccessError("History directory is outside the dataset.", "access.outside_data_root")
        manifest = {}
        try:
            for path in sorted(source.rglob("*")):
                if not is_within_root(source, path):
                    raise AccessError("History source is outside the history directory.", "access.outside_data_root")
                if path.is_file():
                    manifest[path.relative_to(source).as_posix()] = file_hash(path)
        except OSError as exc:
            raise IncompleteError(f"Could not enumerate history: {exc}", "history.backup_unreadable") from exc
        return manifest

    def check_backup_destination(self, destination: Path) -> None:
        if (not is_within_root(self.root, destination)
                or is_within_root(journal.history_dir(self.root), destination)):
            raise AccessError("Backup must be inside the dataset and outside history.", "access.outside_data_root")

    def write_backup(self, destination: Path, manifest: dict[str, str]) -> int:
        self.check_backup_destination(destination)
        source = journal.history_dir(self.root)
        if not manifest:
            return 0
        if manifest != self.backup_manifest():
            raise ConflictError("History changed before backup.", "write.hash_mismatch")
        try:
            destination.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise ConflictError(f"Backup already exists: {destination}", "write.target_exists") from exc
        try:
            for path, expected in manifest.items():
                original = source / path
                target = destination / path
                if not is_within_root(source, original) or not is_within_root(destination, target):
                    raise AccessError("Backup path is outside its directory.", "access.outside_data_root")
                content = original.read_bytes()
                if "sha256:" + hashlib.sha256(content).hexdigest() != expected:
                    raise ConflictError("History changed during backup.", "write.hash_mismatch")
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(content)
        except OSError as exc:
            raise IncompleteError(f"Backup may be incomplete at {destination}: {exc}",
                                  "history.backup_incomplete") from exc
        return len(manifest)
