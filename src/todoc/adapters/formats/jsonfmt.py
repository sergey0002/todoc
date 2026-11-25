"""JSON adapter: strict parsing, duplicate-key rejection, JSON Pointer, schema check.

Error contract: ``parse_json`` returns ``(value, errors)`` where each error is
a ``"code: message"`` string (callers split on the first ``": "``). Codes:
``json.syntax_error``, ``json.duplicate_key``, ``json.invalid_constant``,
``json.too_deep``. Strict mode: ``NaN``/``Infinity`` are rejected (not valid
JSON), a leading BOM is stripped, and nesting depth is checked iteratively
so hostile input cannot crash the process with ``RecursionError``.
"""

from __future__ import annotations

import json
import re
from typing import Any

from jsonschema import Draft202012Validator


class DuplicateKeyError(ValueError):
    pass


class _InvalidConstant(ValueError):
    pass


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise DuplicateKeyError(f"duplicate key: {key}")
        obj[key] = value
    return obj


def _reject_constant(value: str) -> Any:
    raise _InvalidConstant(f"invalid constant: {value}")


def _depth(value: Any) -> int:
    """Iterative nesting depth (no recursion limit issues)."""
    max_depth = 0
    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > max_depth:
            max_depth = depth
        if isinstance(current, dict):
            stack.extend((v, depth + 1) for v in current.values())
        elif isinstance(current, list):
            stack.extend((v, depth + 1) for v in current)
    return max_depth


class JsonError(str):
    """Parse error that also carries a source position.

    Subclasses ``str`` so every existing consumer (``"code" in err``,
    ``err.partition(": ")``, equality against literals) keeps working, while
    callers that can report locations get ``line``/``column`` for free.
    """

    code: str
    message: str
    line: int | None
    column: int | None

    def __new__(cls, code: str, message: str, line: int | None = None, column: int | None = None) -> "JsonError":
        self = super().__new__(cls, f"{code}: {message}")
        self.code = code
        self.message = message
        self.line = line
        self.column = column
        return self


def parse_json(text: str, max_depth: int = 128) -> tuple[Any, list[JsonError]]:
    """Return (value, errors). Duplicate keys, invalid constants and depth
    overflow are errors; the value is None whenever errors is non-empty."""
    if text.startswith("\ufeff"):
        text = text[1:]
    try:
        value = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_reject_constant)
    except DuplicateKeyError as exc:
        return None, [JsonError("json.duplicate_key", str(exc))]
    except _InvalidConstant as exc:
        return None, [JsonError("json.invalid_constant", str(exc))]
    except json.JSONDecodeError as exc:
        # exc.msg alone: the full str(exc) repeats "line N column M (char K)",
        # which would duplicate the structured location.
        return None, [JsonError("json.syntax_error", exc.msg, exc.lineno, exc.colno)]
    except RecursionError:
        return None, [JsonError("json.too_deep", "parser recursion limit exceeded")]
    depth = _depth(value)  # iterative: cannot RecursionError on hostile nesting
    if depth > max_depth:
        return None, [JsonError("json.too_deep", f"nesting depth {depth} exceeds limit {max_depth}")]
    return value, []


_ARRAY_INDEX_RE = re.compile(r"^(0|[1-9][0-9]*)$")


def resolve_pointer(value: Any, pointer: str) -> Any:
    """Resolve an RFC 6901 JSON Pointer. Raises KeyError/IndexError on miss.

    ``""`` refers to the whole document; ``"/"`` refers to the member with
    the empty-string key. Array indices must be canonical (no leading zeros,
    no negatives); ``"-"`` (past-the-end) is a miss.
    """
    if pointer == "":
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
            if not _ARRAY_INDEX_RE.match(part):
                raise KeyError(part)
            index = int(part)
            if index >= len(current):
                raise IndexError(part)
            current = current[index]
        else:
            raise KeyError(part)
    return current


def validate_against_schema(instance: Any, schema: dict[str, Any]) -> list[str]:
    """Validate instance against a JSON Schema (2020-12). Returns messages."""
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    messages: list[str] = []
    for error in errors:
        path = "/".join(str(p) for p in error.absolute_path)
        messages.append(f"/{path}: {error.message}" if path else f"/: {error.message}")
    return messages
