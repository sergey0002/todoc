"""Snapshot-bound cursors for ordered result sets."""

import hashlib
import json
from typing import TypeVar

from todoc.errors import EXIT_USAGE, TodocError

T = TypeVar("T")


def selection_key(selection: list) -> str:
    return hashlib.sha256(json.dumps(selection, sort_keys=True).encode()).hexdigest()


def cursor_offset(cursor: str | None, fingerprint: str) -> int:
    if cursor is None:
        return 0
    digest, _, offset = cursor.partition(":")
    if digest != fingerprint or not offset.isascii() or not offset.isdecimal() or len(offset) > 12:
        raise TodocError("Cursor does not match this selection.", EXIT_USAGE, "cursor.invalid")
    start = int(offset)
    if start == 0:
        raise TodocError("Cursor is outside this selection.", EXIT_USAGE, "cursor.invalid")
    return start


def next_page_cursor(fingerprint: str, end: int, total: int) -> str | None:
    return f"{fingerprint}:{end}" if end < total else None


def page(items: list[T], selection: list, limit: int, cursor: str | None) -> tuple[list[T], str | None]:
    if cursor is None and len(items) <= limit:
        return items, None
    fingerprint = selection_key(selection)
    start = cursor_offset(cursor, fingerprint)
    if start >= len(items):
        raise TodocError("Cursor is outside this selection.", EXIT_USAGE, "cursor.invalid")
    end = start + limit
    return items[start:end], next_page_cursor(fingerprint, end, len(items))
