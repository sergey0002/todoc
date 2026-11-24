"""Type descriptor loading and validation (all JSON, all versioned)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from todoc.errors import ValidationError


def load_json_file(path: Path) -> Any:
    """Load a JSON file, raising ValidationError on syntax errors."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationError(f"Cannot read {path}: {exc}", "config.unreadable") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON in {path}: {exc}", "config.invalid_json") from exc


def require_schema_version(data: Any, path: Path) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValidationError(f"{path}: top-level value must be an object", "config.invalid_schema")
    if data.get("schema_version") != 1:
        raise ValidationError(
            f"{path}: schema_version must be 1, got {data.get('schema_version')!r}",
            "config.unsupported_version",
        )
    return data


class TypeRegistry:
    """In-memory registry of dir/doc/entity/relation type descriptors."""

    def __init__(self) -> None:
        self.dir_types: dict[str, dict[str, Any]] = {}
        self.doc_types: dict[str, dict[str, Any]] = {}
        self.entity_types: dict[str, dict[str, Any]] = {}
        self.relation_types: dict[str, dict[str, Any]] = {}

    def _load_dir(self, base: Path, kind: str, store: dict[str, dict[str, Any]]) -> None:
        if not base.is_dir():
            return
        for type_dir in sorted(base.iterdir()):
            if not type_dir.is_dir():
                continue
            type_file = type_dir / "type.json"
            if not type_file.is_file():
                continue
            data = require_schema_version(load_json_file(type_file), type_file)
            type_id = data.get("type_id")
            if not isinstance(type_id, str) or not type_id:
                raise ValidationError(f"{type_file}: type_id is required", "config.invalid_schema")
            if type_id in store:
                raise ValidationError(f"Duplicate {kind} type_id: {type_id}", "config.duplicate_type")
            store[type_id] = data

    def load(self, root: Path, dataset: dict[str, Any]) -> None:
        todoc_dir = root / ".todoc"
        self._load_dir(todoc_dir / dataset.get("directory_types", "dir_types"), "dir_type", self.dir_types)
        self._load_dir(todoc_dir / dataset.get("document_types", "doc_types"), "doc_type", self.doc_types)
        self._load_dir(todoc_dir / dataset.get("entity_types", "entity_types"), "entity_type", self.entity_types)
        self._load_dir(todoc_dir / dataset.get("relation_types", "relation_types"), "relation_type", self.relation_types)

    def validate_references(self, dir_rules: list[dict[str, Any]], doc_rules: list[dict[str, Any]]) -> None:
        """Every assigned dir_type/doc_type must exist in the registry."""
        for rule in dir_rules:
            assigned = (rule.get("assign") or {}).get("dir_type")
            if assigned is not None and assigned not in self.dir_types:
                raise ValidationError(
                    f"Rule {rule.get('id')}: unknown dir_type {assigned!r}",
                    "config.unknown_type",
                )
        for rule in doc_rules:
            assigned = (rule.get("assign") or {}).get("doc_type")
            if assigned is not None and assigned not in self.doc_types:
                raise ValidationError(
                    f"Rule {rule.get('id')}: unknown doc_type {assigned!r}",
                    "config.unknown_type",
                )
