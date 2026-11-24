"""Review-first writes: WritePlan, create record, fix, edit (E9)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from todoc.adapters.filesystem.scanner import atomic_write, file_hash
from todoc.adapters.formats.jsonfmt import parse_json
from todoc.domain.models import WritePlan
from todoc.errors import ConflictError, ValidationError


def _sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def create_record_plan(dataset: dict[str, Any], entity_types: dict[str, Any], record: dict[str, Any],
                       existing_ids: set[str], existing_paths: set[str]) -> WritePlan:
    """Build a WritePlan for a new JSON record (create-only, no-overwrite)."""
    dataset_id = dataset["dataset_id"]
    entity_type = str(record.get("entity_type", ""))
    record_id = str(record.get("record_id", ""))
    if entity_type not in entity_types:
        raise ValidationError(f"Unknown entity_type: {entity_type!r}", "record.unknown_entity_type")
    if not record_id:
        raise ValidationError("Record has no record_id", "record.missing_id")
    if record_id in existing_ids:
        raise ConflictError(f"record_id already exists: {record_id}", "record.duplicate_id")
    descriptor = entity_types[entity_type]
    required = descriptor.get("required_fields") or []
    for field_name in required:
        if field_name not in record:
            raise ValidationError(f"Missing required field: {field_name}", "record.missing_field")
    path_template = str(descriptor.get("path_template") or f"records/{entity_type}/{{record_id}}.json")
    slug = record_id.split(":")[-1]
    target = path_template.replace("{record_id}", record_id).replace("{slug}", slug)
    if target in existing_paths:
        raise ConflictError(f"Target already exists: {target}", "record.target_exists")
    if target.startswith("../") or "/../" in target or target.startswith("/"):
        raise ValidationError(f"Unsafe path_template result: {target}", "record.unsafe_path")
    content = json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    return WritePlan(
        dataset_id=dataset_id,
        target_path=target,
        new_content=content,
        expected_hash=None,
        new_hash=_sha(content),
        basis=f"Create {entity_type} record {record_id}",
        validations=("schema", "relations", "no-overwrite"),
    )


def apply_write_plan(root: Path, plan: WritePlan, expected_hash: str | None = None) -> str:
    """Apply a WritePlan atomically. Returns new hash."""
    target = root / plan.target_path
    if plan.expected_hash is None:
        if target.exists():
            raise ConflictError(f"Target already exists: {plan.target_path}", "write.target_exists")
    else:
        if not target.is_file():
            raise ConflictError(f"Target does not exist: {plan.target_path}", "write.target_missing")
        current = file_hash(target)
        if current != plan.expected_hash:
            raise ConflictError(f"Hash mismatch for {plan.target_path}: expected {plan.expected_hash}, got {current}",
                                "write.hash_mismatch")
        if expected_hash is not None and expected_hash != plan.expected_hash:
            raise ConflictError("Caller expected_hash does not match plan", "write.hash_mismatch")
    atomic_write(target, plan.new_content)
    return plan.new_hash


def apply_fix(root: Path, rel_path: str, old_target: str, new_target: str, expected_hash: str | None = None) -> str:
    """Replace one link target in a Markdown file (review-first fix)."""
    target = root / rel_path
    if not target.is_file():
        raise ValidationError(f"File not found: {rel_path}", "fix.file_missing")
    current_hash = file_hash(target)
    if expected_hash is not None and current_hash != expected_hash:
        raise ConflictError(f"Hash mismatch for {rel_path}", "write.hash_mismatch")
    text = target.read_text(encoding="utf-8")
    if old_target not in text:
        raise ValidationError(f"Target {old_target!r} not found in {rel_path}", "fix.target_not_found")
    new_text = text.replace(old_target, new_target, 1)
    atomic_write(target, new_text)
    return _sha(new_text)


def apply_edit_ops(root: Path, rel_path: str, ops: list[dict[str, Any]], expected_hash: str | None = None) -> str:
    """Apply line-based edit ops: [{line: 1-based, text: new line}]."""
    target = root / rel_path
    if not target.is_file():
        raise ValidationError(f"File not found: {rel_path}", "edit.file_missing")
    current_hash = file_hash(target)
    if expected_hash is not None and current_hash != expected_hash:
        raise ConflictError(f"Hash mismatch for {rel_path}", "write.hash_mismatch")
    lines = target.read_text(encoding="utf-8").splitlines()
    for op in ops:
        line_no = int(op.get("line", 0))
        if line_no < 1 or line_no > len(lines):
            raise ValidationError(f"Line out of range: {line_no}", "edit.line_out_of_range")
        lines[line_no - 1] = str(op.get("text", ""))
    new_text = "\n".join(lines) + "\n"
    atomic_write(target, new_text)
    return _sha(new_text)


def load_input_record(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationError(f"Cannot read input file: {exc}", "record.unreadable_input") from exc
    value, errors = parse_json(text)
    if errors:
        raise ValidationError(f"Invalid JSON in input file: {errors[0]}", "record.invalid_json")
    if not isinstance(value, dict):
        raise ValidationError("Input record must be a JSON object", "record.invalid_input")
    return value
