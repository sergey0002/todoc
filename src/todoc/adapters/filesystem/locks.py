"""Exclusive write staging on filesystems that support atomic directory creation."""

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from todoc.errors import ConflictError


@contextmanager
def directory_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.mkdir()
    except FileExistsError as exc:
        raise ConflictError(f"Write lock already exists: {path}", "write.busy") from exc
    try:
        yield
    finally:
        path.rmdir()
