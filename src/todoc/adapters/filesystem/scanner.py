"""Deterministic recursive scanning with containment and hard-excludes."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

HARD_EXCLUDE_DIRS = {".todoc", ".git", "__pycache__", "node_modules", ".obsidian", ".venv", "venv"}

FORMAT_BY_SUFFIX: dict[str, str] = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".csv": "csv",
    ".json": "json",
}


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def is_within_root(root: Path, candidate: Path) -> bool:
    root_resolved = root.resolve()
    try:
        candidate.resolve().relative_to(root_resolved)
    except ValueError:
        return False
    return True


def atomic_write(path: Path, content: str | bytes) -> None:
    """Write via temp file + atomic replace (E9)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8") if isinstance(content, str) else content
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".tmp.")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


class ScannedFile:
    def __init__(self, rel_path: str, abs_path: Path, format: str, size: int, hash: str, status: str = "ok") -> None:
        self.rel_path = rel_path
        self.abs_path = abs_path
        self.format = format
        self.size = size
        self.hash = hash
        self.status = status


class ScannedFolder:
    def __init__(self, rel_path: str, abs_path: Path) -> None:
        self.rel_path = rel_path
        self.abs_path = abs_path


def scan_dataset(root: Path, follow_symlinks: bool = False, max_file_bytes: int = 10485760) -> tuple[list[ScannedFolder], list[ScannedFile]]:
    """Walk root deterministically (sorted). Returns (folders, files).

    Hard-excludes apply before classification and cannot be lifted by config.
    Symlinks are not followed by default; symlink escapes are skipped.
    """
    root_resolved = root.resolve()
    folders: list[ScannedFolder] = [ScannedFolder(".", root_resolved)]
    files: list[ScannedFile] = []

    def walk(dir_path: Path, rel_dir: str) -> None:
        try:
            entries = sorted(os.scandir(dir_path), key=lambda e: e.name)
        except OSError:
            return
        for entry in entries:
            name = entry.name
            if name in HARD_EXCLUDE_DIRS:
                continue
            if name.startswith(".") and name in (".todoc.json",):
                continue
            rel = name if rel_dir == "." else f"{rel_dir}/{name}"
            entry_path = Path(entry.path)
            if entry.is_symlink():
                if not follow_symlinks:
                    continue
                if not is_within_root(root_resolved, entry_path):
                    continue
            if entry.is_dir(follow_symlinks=follow_symlinks):
                folders.append(ScannedFolder(rel, entry_path))
                walk(entry_path, rel)
            elif entry.is_file(follow_symlinks=follow_symlinks):
                try:
                    size = entry.stat(follow_symlinks=follow_symlinks).st_size
                except OSError:
                    files.append(ScannedFile(rel, entry_path, "opaque", 0, "sha256:", "permission_denied"))
                    continue
                fmt = FORMAT_BY_SUFFIX.get(Path(name).suffix.lower(), "opaque")
                if size > max_file_bytes:
                    files.append(ScannedFile(rel, entry_path, fmt, size, "sha256:", "unsupported"))
                    continue
                try:
                    digest = file_hash(entry_path)
                except OSError:
                    files.append(ScannedFile(rel, entry_path, fmt, size, "sha256:", "permission_denied"))
                    continue
                files.append(ScannedFile(rel, entry_path, fmt, size, digest))

    walk(root_resolved, ".")
    folders.sort(key=lambda f: f.rel_path)
    files.sort(key=lambda f: f.rel_path)
    return folders, files
