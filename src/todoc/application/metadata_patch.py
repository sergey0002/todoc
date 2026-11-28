"""Plan edits to stored document and record attributes without touching the source."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from todoc.adapters.filesystem.scanner import is_within_root
from todoc.adapters.formats.jsonfmt import parse_json
from todoc.adapters.formats.markdown import parse_markdown
from todoc.adapters.formats.metadata import get_attributes
from todoc.domain.models import WritePlan
from todoc.errors import ConflictError, ValidationError
from todoc.typing_system.document_metadata import metadata_errors, normalize_markdown_attributes

_PROTECTED = {"id", "doc_type", "record_id", "entity_type", "schema_version", "created", "updated", "path", "hash"}


def _invalid(message: str) -> ValidationError:
    return ValidationError(message, "metadata.invalid_patch")


def patch_attributes(original: dict[str, Any], operations: Any) -> dict[str, Any]:
    if not isinstance(operations, list) or not operations:
        raise _invalid("Expected a nonempty metadata operation list.")
    result = deepcopy(original)
    for operation in operations:
        if not isinstance(operation, dict):
            raise _invalid("Each metadata operation must be an object.")
        field = operation.get("field")
        op = operation.get("op")
        if not isinstance(field, str) or not field or field != field.strip() or field in _PROTECTED:
            raise _invalid(f"Metadata field is invalid or protected: {field!r}.")
        expected = {"op", "field"} if op == "remove" else {"op", "field", "value"}
        if set(operation) != expected:
            raise _invalid(f"Invalid keys for metadata operation {op!r}.")
        if op == "remove":
            result.pop(field, None)
        elif op == "set":
            result[field] = operation["value"]
        elif op in ("add_item", "remove_item"):
            values = result.get(field, [])
            if not isinstance(values, list):
                raise _invalid(f"Metadata field {field!r} is not an array.")
            item = operation["value"]
            if op == "add_item":
                if item not in values:
                    result[field] = [*values, item]
            elif field in result:
                result[field] = [value for value in values if value != item]
        else:
            raise _invalid(f"Unknown metadata operation: {op!r}.")
    return result


def rewrite_markdown_attributes(text: str, original: dict[str, Any], proposed: dict[str, Any]) -> str:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise _invalid("Markdown must have a front matter block.")
    end = next((index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        raise _invalid("Markdown front matter block is unclosed.")
    changed = {key for key in original.keys() | proposed.keys()
               if key not in original or key not in proposed or original[key] != proposed[key]}
    configured = []
    emitted = set()
    newline = "\r\n" if lines[0].endswith("\r\n") else "\n"
    for line in lines[1:end]:
        key, separator, _ = line.partition(":")
        key = key.strip()
        if not separator or key not in changed:
            configured.append(line)
        elif key in proposed and key not in emitted:
            configured.append(f"{key}: {json.dumps(proposed[key], ensure_ascii=False, allow_nan=False)}{newline}")
            emitted.add(key)
    for key in proposed:
        if key in changed and key not in emitted:
            configured.append(f"{key}: {json.dumps(proposed[key], ensure_ascii=False, allow_nan=False)}{newline}")
    return "".join([lines[0], *configured, *lines[end:]])


def _digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def plan_metadata_patch(
    root: Path, dataset_id: str, entry: dict[str, Any], fmt: str,
    operations: Any, schemas: list[tuple[dict[str, Any], str]], *, record: bool = False,
    allowed_statuses: list[str] | None = None,
) -> tuple[WritePlan, dict[str, Any], dict[str, Any]]:
    target = root / entry["path"]
    if not is_within_root(root, target):
        raise _invalid("The file is outside the dataset.")
    try:
        raw = target.read_bytes()
        before = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise _invalid(f"Could not read {entry['path']}: {exc}") from exc
    if _digest(raw) != entry["hash"]:
        raise ConflictError("The source changed before planning the metadata patch.", "write.hash_mismatch")
    if fmt == "markdown":
        original = normalize_markdown_attributes(parse_markdown(before).front_matter, schemas)
        proposed = patch_attributes(original, operations)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if (proposed != original and isinstance(proposed.get("updated"), str)
                and proposed["updated"] < stamp):
            proposed["updated"] = stamp
        content = rewrite_markdown_attributes(before, original, proposed)
        reread = normalize_markdown_attributes(parse_markdown(content).front_matter, schemas)
        if reread != proposed:
            raise _invalid("The patched values cannot be represented by the Markdown metadata adapter.")
        pointer = ""
    elif fmt == "json":
        value, errors = parse_json(before)
        if errors or not isinstance(value, dict):
            raise _invalid("JSON metadata requires a valid object.")
        if "record_id" in value and not record:
            raise _invalid("Use records edit for a typed record.")
        original, pointer, _ = get_attributes(fmt, value)
        if pointer and not isinstance(value["meta"], dict):
            raise _invalid("The JSON meta field must be an object.")
        proposed = patch_attributes(original, operations)
        if pointer and any(key in value and value[key] != proposed[key] for key in proposed):
            raise _invalid("The patch conflicts with a legacy top-level metadata key.")
        content = before
        if proposed != original:
            content = json.dumps({**value, "meta": proposed} if pointer else proposed,
                                 ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    else:
        raise _invalid("Metadata patches are supported for Markdown and JSON objects.")
    if allowed_statuses and proposed.get("status") not in allowed_statuses and "status" in proposed:
        raise _invalid(f"status must be one of {allowed_statuses}.")
    violations = [f"{location}: {message}" for schema, _ in schemas
                  for location, message in metadata_errors(proposed, schema, pointer)]
    if violations:
        raise ValidationError("; ".join(violations), "document.schema_violation")
    plan = WritePlan(
        dataset_id=dataset_id, target_path=entry["path"], new_content=content,
        expected_hash=entry["hash"], new_hash=_digest(content.encode("utf-8")),
        basis="Edit source metadata",
    )
    return plan, original, proposed
