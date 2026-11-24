"""Filesystem adapter: scanning, containment, atomic writes."""

from todoc.adapters.filesystem.scanner import (
    atomic_write,
    file_hash,
    is_within_root,
    scan_dataset,
)

__all__ = ["atomic_write", "file_hash", "is_within_root", "scan_dataset"]
