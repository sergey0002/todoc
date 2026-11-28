"""Fingerprint the source corpus and its configuration independently of the index."""

import hashlib
from pathlib import Path
from typing import Any

def _config_digest(root: Path, *, strict: bool = False) -> str:
    h = hashlib.sha256()
    todoc_dir = root / ".todoc"
    if todoc_dir.is_dir():
        for path in sorted(todoc_dir.rglob("*.json")):
            relative = path.relative_to(todoc_dir)
            if relative.parts[0] in {"index", "cache", "generated", "history"}:
                continue
            try:
                data = path.read_bytes()
            except OSError:
                if strict:
                    raise
                continue
            h.update(path.relative_to(root).as_posix().encode("utf-8"))
            h.update(b"\0")
            h.update(hashlib.sha256(data).digest())
    return "sha256:" + h.hexdigest()


def corpus_digest(files: list[Any], config_digest: str) -> str:
    """SHA-256 over sorted (rel_path, content_hash) pairs plus the config digest.

    Two scans of an unchanged corpus produce the same digest, which is what lets a
    read command reuse the published index instead of republishing it. ``created_at``
    is deliberately not an input: metadata must not invalidate the index.
    """
    h = hashlib.sha256()
    for path, digest in sorted((f.rel_path, f.hash) for f in files):
        h.update(path.encode("utf-8"))
        h.update(b"\0")
        h.update(digest.encode("utf-8"))
        h.update(b"\n")
    h.update(config_digest.encode("utf-8"))
    return "sha256:" + h.hexdigest()




def source_fingerprint(root: Path, folders: list[Any], files: list[Any]) -> str:
    """Bind the snapshot to the file contents, folder inventory and local configuration."""
    # Parser semantics are part of the projection basis too: old published
    # mentions must not survive a decoder change with unchanged source bytes.
    from todoc.adapters.formats.markdown import PARSER_VERSION
    basis = hashlib.sha256((_config_digest(root, strict=True) + PARSER_VERSION).encode())
    for folder in sorted(folders, key=lambda item: item.rel_path):
        basis.update(folder.rel_path.encode("utf-8") + b"\0")
        config = folder.abs_path / ".config.json"
        if config.is_file():
            basis.update(hashlib.sha256(config.read_bytes()).digest())
        basis.update(b"\n")
    return corpus_digest(files, basis.hexdigest())
