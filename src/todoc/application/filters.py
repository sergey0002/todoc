"""Declarative filters shared by document and record collections."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
import json
from pathlib import Path
import re
from typing import Any

from todoc.adapters.formats.jsonfmt import parse_json
from todoc.errors import EXIT_USAGE, TodocError

MISSING = object()
OPERATORS = ("eq", "in", "has_any", "has_all", "exists", "gte", "lte")
DATE_FIELDS = frozenset({"created", "updated", "date"})


def _invalid(message: str) -> TodocError:
    return TodocError(message, EXIT_USAGE, "filter.invalid")


def split_values(arguments: Iterable[str]) -> tuple[str, ...]:
    values = {part.strip() for arg in arguments for part in arg.split("|")}
    if "" in values:
        raise _invalid("A filter list contains an empty value.")
    return tuple(sorted(values))


def _field_tokens(field: str) -> list[str]:
    if field.startswith("/"):
        parts = field[1:].split("/")
        if any(re.search(r"~(?![01])", token) for token in parts):
            raise _invalid(f"Invalid JSON Pointer: {field!r}.")
        return [token.replace("~1", "/").replace("~0", "~") for token in parts]
    parts = field.split(".")
    if not all(parts):
        raise _invalid(f"Invalid attribute path: {field!r}.")
    return parts


def _pointer(parts: Iterable[str]) -> str:
    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)


def field_value(row: dict[str, Any], field: str) -> Any:
    value: Any = row
    for key in _field_tokens(field):
        if isinstance(value, dict) and key in value:
            value = value[key]
        elif (isinstance(value, list) and key.isascii() and key.isdecimal() and len(key) <= 9
              and int(key) < len(value)):
            value = value[int(key)]
        else:
            return MISSING
    return value


def _key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _scalar(value: Any) -> bool:
    return value is None or type(value) in (str, int, float, bool)


def _equal(left: Any, right: Any) -> bool:
    return type(left) is type(right) and left == right


def _matches(actual: Any, op: str, value: Any) -> bool:
    if op == "exists":
        return (actual is not MISSING) == value
    if actual is MISSING:
        return False
    if op == "eq":
        return _equal(actual, value)
    if op == "in":
        return any(_equal(actual, wanted) for wanted in value)
    if op in ("has_any", "has_all"):
        if not isinstance(actual, list):
            return False
        predicate = any if op == "has_any" else all
        return predicate(any(_equal(item, wanted) for item in actual) for wanted in value)
    if type(actual) is not type(value):
        return False
    return actual >= value if op == "gte" else actual <= value


def matches_conditions(row: dict[str, Any], conditions: tuple[tuple[str, str, Any], ...]) -> bool:
    return all(_matches(field_value(row, field), op, value) for field, op, value in conditions)


def schema_field(declared: Mapping[str, Any], field: str) -> Any:
    spec: Any = {"properties": declared}
    for key in _field_tokens(field):
        if not isinstance(spec, dict):
            return MISSING
        if spec.get("type") == "array" and key.isascii() and key.isdecimal():
            spec = spec.get("items", MISSING)
        else:
            spec = spec.get("properties", {}).get(key, MISSING)
    return spec


def _field_types(rows: list[dict[str, Any]], field: str, declared: Mapping[str, Any]) -> tuple[set[type], set[type]]:
    types: set[type] = set()
    items: set[type] = set()
    for row in rows:
        value = field_value(row, field)
        if value is MISSING or value is None:
            continue
        types.add(type(value))
        if isinstance(value, list):
            items.update(type(item) for item in value if item is not None)
    aliases = {"boolean": bool, "string": str, "integer": int, "number": float, "array": list, "object": dict}
    spec = schema_field(declared, field)
    if isinstance(spec, dict):
        # A declared number includes existing integer and floating values.
        declared_type = aliases.get(spec.get("type")) if isinstance(spec.get("type"), str) else None
        if not types and declared_type is not None:
            types.add(declared_type)
        item_spec = spec.get("items")
        if not items and isinstance(item_spec, dict) and isinstance(item_spec.get("type"), str):
            item_type = aliases.get(item_spec["type"])
            if item_type is not None:
                items.add(item_type)
    return types, items


def _coerce(value: str, target: type) -> Any:
    if target is str:
        return value
    try:
        parsed = json.loads(value)
    except (ValueError, RecursionError) as exc:
        raise _invalid(f"Invalid {target.__name__} operand: {value!r}.") from exc
    if target is float and type(parsed) is int:
        try:
            parsed = float(parsed)
        except OverflowError as exc:
            raise _invalid(f"Invalid numeric operand: {value!r}.") from exc
    if type(parsed) is not target:
        raise _invalid(f"Expected a {target.__name__} operand, got {value!r}.")
    return parsed


def _load_filter_file(path: Path) -> list[tuple[str, str, Any]]:
    try:
        data, errors = parse_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise _invalid(f"Cannot read filter file {path}: {exc}") from exc
    if (errors or not isinstance(data, dict) or type(data.get("schema_version")) is not int
            or data["schema_version"] != 1 or not isinstance(data.get("conditions"), list)):
        raise _invalid("Expected a version 1 filter file with a conditions array.")
    rules = []
    for rule in data["conditions"]:
        if not isinstance(rule, dict) or set(rule) != {"field", "op", "value"}:
            raise _invalid("Each filter condition requires field, op and value.")
        rules.append((rule["field"], rule["op"], rule["value"]))
    return rules


def compile_conditions(
    rows: list[dict[str, Any]], declared: Mapping[str, Any],
    attributes: tuple[tuple[str, str], ...] = (), filter_file: Path | None = None,
) -> tuple[tuple[str, str, Any], ...]:
    """Resolve operands once before matching, then canonicalize for the cursor."""
    raw = _load_filter_file(filter_file) if filter_file is not None else []
    groups: dict[str, list[str]] = {}
    for field, operand in attributes:
        groups.setdefault(_pointer([field]), []).append(operand)
    for field, operands in groups.items():
        types, items = _field_types(rows, field, declared)
        target_types = items if types == {list} else types
        if len(target_types) > 1 or any(kind in (dict, list) for kind in target_types):
            raise _invalid(f"Incompatible values for attribute {field!r}. Narrow the selection.")
        target = next(iter(target_types), str)
        values = [_coerce(value, target) for value in split_values(operands)]
        raw.append((field, "has_any" if types == {list} else "in", values))

    normalized = {}
    for field, op, value in raw:
        if not isinstance(field, str) or op not in OPERATORS:
            raise _invalid(f"Unknown field path or operator: {field!r} {op!r}.")
        parts = _field_tokens(field)
        field = _pointer(parts)
        spec = schema_field(declared, field)
        if spec is MISSING and not any(field_value(row, field) is not MISSING for row in rows):
            raise _invalid(f"Unknown attribute {field!r} in the selected scope.")
        types, items = _field_types(rows, field, declared)
        if len(types) > 1 and op != "exists":
            raise _invalid(f"Incompatible types for field {field!r}. Narrow the selection.")
        if op == "exists":
            if type(value) is not bool:
                raise _invalid("exists requires a Boolean operand.")
        elif op in ("in", "has_any", "has_all"):
            targets = types if op == "in" else items
            if (not isinstance(value, list) or not value
                    or not all(_scalar(item) and (item is None or not targets or type(item) in targets)
                               for item in value)):
                raise _invalid(f"{op} requires a nonempty array of compatible scalar operands for {field!r}.")
            if op != "in" and types and types != {list}:
                raise _invalid(f"{op} requires an array field, got {field!r}.")
        elif not _scalar(value) or (types and value is not None and type(value) not in types):
            raise _invalid(f"Incompatible operand for {field!r}.")
        if op in ("gte", "lte"):
            if type(value) not in (int, float, str):
                raise _invalid("A range endpoint must be a number or a date/string.")
            if parts[-1] in DATE_FIELDS or (
                isinstance(spec, dict) and spec.get("format") == "date"
            ):
                try:
                    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                        raise ValueError
                    date.fromisoformat(value)
                except ValueError as exc:
                    raise _invalid(f"Invalid calendar date for {field!r}: {value!r}.") from exc
        try:
            if isinstance(value, list):
                value = [json.loads(item) for item in sorted({_key(item) for item in value})]
            normalized[_key([field, op, value])] = (field, op, value)
        except ValueError as exc:
            raise _invalid(f"Non-finite numeric operand for {field!r}.") from exc
    return tuple(normalized[key] for key in sorted(normalized))


def tag_matches(tags: list[str], any_tags: tuple[str, ...], all_tags: tuple[str, ...]) -> bool:
    available = {tag.casefold() for tag in tags}
    return (not any_tags or not available.isdisjoint(any_tags)) and available.issuperset(all_tags)
