"""JSON adapter: strict parsing, duplicate-key rejection, JSON Pointer."""

from __future__ import annotations

import json
from typing import Any


class DuplicateKeyError(ValueError):
    pass


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise DuplicateKeyError(f"duplicate key: {key}")
        obj[key] = value
    return obj


def _depth(value: Any) -> int:
    if isinstance(value, dict):
        return 1 + max((_depth(v) for v in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_depth(v) for v in value), default=0)
    return 0


def parse_json(text: str, max_depth: int = 128) -> tuple[Any, list[str]]:
    """Return (value, errors). Duplicate keys and depth overflow are errors."""
    try:
        value = json.loads(text, object_pairs_hook=_no_duplicates)
    except DuplicateKeyError as exc:
        return None, [f"json.duplicate_key: {exc}"]
    except json.JSONDecodeError as exc:
        return None, [f"json.syntax_error: {exc}"]
    if _depth(value) > max_depth:
        return None, ["json.too_deep"]
    return value, []


def resolve_pointer(value: Any, pointer: str) -> Any:
    """Resolve RFC 6901 JSON Pointer. Raises KeyError/IndexError on miss."""
    if pointer in ("", "/"):
        return value
    if not pointer.startswith("/"):
        raise KeyError(f"Invalid JSON Pointer: {pointer}")
    current = value
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if part not in current:
                raise KeyError(part)
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:
            raise KeyError(part)
    return current
