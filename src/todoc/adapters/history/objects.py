"""Снимки «до»: ``.todoc/history/objects/<2hex>/<rest>``.

Имя объекта — SHA-256 несжатого содержимого, тот же формат ``sha256:``, что уже возвращает
``file_hash``. Содержимое сжимается zlib: текстовые документы сжимаются хорошо, а история
хранит много близких версий одного файла.

**Хранится только образ «до».** Образ «после» уже лежит на диске, поэтому содержимое файла
на ревизии R восстанавливается как образ «до» первого изменения после R. Это вдвое
уменьшает объём без потери возможности отката.
"""

from __future__ import annotations

import hashlib
import zlib
from pathlib import Path

from todoc.adapters.filesystem.scanner import atomic_write


def objects_dir(root: Path) -> Path:
    return root / ".todoc" / "history" / "objects"


def content_hash(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def object_path(root: Path, digest: str) -> Path:
    hexpart = digest.split(":", 1)[-1]
    return objects_dir(root) / hexpart[:2] / hexpart[2:]


def write_snapshot(root: Path, data: bytes) -> str:
    """Кладёт образ и возвращает его ``sha256:``. Повторная запись того же содержимого — no-op."""
    digest = content_hash(data)
    path = object_path(root, digest)
    if path.is_file():
        return digest
    atomic_write(path, zlib.compress(data, 6))
    return digest


def read_snapshot(root: Path, digest: str) -> bytes | None:
    path = object_path(root, digest)
    if not path.is_file():
        return None
    try:
        return zlib.decompress(path.read_bytes())
    except (OSError, zlib.error):
        return None


def count_objects(root: Path) -> int:
    base = objects_dir(root)
    if not base.is_dir():
        return 0
    return sum(1 for _ in base.rglob("*") if _.is_file())


def objects_bytes(root: Path) -> int:
    base = objects_dir(root)
    if not base.is_dir():
        return 0
    return sum(p.stat().st_size for p in base.rglob("*") if p.is_file())


def remove_object(root: Path, digest: str) -> bool:
    path = object_path(root, digest)
    if not path.is_file():
        return False
    try:
        path.unlink()
        parent = path.parent
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
    except OSError:
        return False
    return True
