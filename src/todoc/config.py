"""Dataset config loading and portable ``init``."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from todoc.errors import ValidationError
from todoc.typing_system.descriptors import load_json_file, require_schema_version

DEFAULT_LIMITS: dict[str, int] = {
    "max_file_bytes": 10485760,
    "max_json_depth": 128,
    "max_csv_rows": 1000000,
    "max_query_results": 200,
    "max_record_create_path": 512,
}


def default_dataset(dataset_id: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "dataset_id": dataset_id,
        "enabled_formats": ["csv", "json", "markdown"],
        "directory_rules": "rules/directory-rules.json",
        "document_rules": "rules/document-rules.json",
        "directory_types": "dir_types",
        "document_types": "doc_types",
        "entity_types": "entity_types",
        "relation_types": "relation_types",
        "queries": "queries",
        "templates": "templates",
        "trusted_workflows": {
            "record-capture-v1": {
                "kind": "external-skill",
                "workflow_id": "todoc-record-capture",
                "version": "0.1.0",
            }
        },
        "follow_symlinks": False,
        "limits": dict(DEFAULT_LIMITS),
    }


def default_directory_rules() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "rules": [
            {"id": "reserved-research", "match": {"kind": "directory", "basename": ".research"}, "assign": {"dir_type": "research"}, "priority": 100},
            {"id": "reserved-plan", "match": {"kind": "directory", "glob": "**/plan"}, "assign": {"dir_type": "plan"}, "priority": 100},
            {"id": "reserved-architecture", "match": {"kind": "directory", "basename": "architecture"}, "assign": {"dir_type": "architecture"}, "priority": 100},
            {"id": "reserved-constitution", "match": {"kind": "directory", "basename": "constitution"}, "assign": {"dir_type": "constitution"}, "priority": 100},
            {"id": "reserved-harness", "match": {"kind": "directory", "basename": "harness"}, "assign": {"dir_type": "harness"}, "priority": 100},
            {"id": "reserved-glossary", "match": {"kind": "directory", "basename": "glossary"}, "assign": {"dir_type": "glossary"}, "priority": 100},
        ],
    }


def default_document_rules() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "rules": [
            {"id": "adr-markdown", "match": {"kind": "file", "glob": "**/adr/*.md"}, "assign": {"doc_type": "adr"}, "priority": 50},
            {"id": "glossary-by-front-matter", "match": {"kind": "file", "front_matter": {"doc_type": "glossary-entry"}}, "assign": {"doc_type": "glossary-entry"}, "priority": 200},
        ],
    }


def _type_stub(type_id: str, description: str, kind: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {"schema_version": 1, "type_id": type_id, "version": "0.1", "kind": kind,
                            "description": description}
    if extra:
        data.update(extra)
    return data


#: Default document types of a fresh dataset: type_id -> required sections.
DEFAULT_DOC_TYPES: dict[str, list[str]] = {
    "adr": ["## Контекст", "## Решение", "## Последствия"],
    "glossary-entry": ["## Определение", "## Пример"],
    "research-note": ["## Вопрос", "## Источники", "## Вывод"],
    "note": ["## Суть"],
}

#: Default entity types of a fresh dataset: type_id -> required fields.
DEFAULT_ENTITY_TYPES: dict[str, list[str]] = {
    "note": ["record_id", "entity_type", "title"],
    "research": ["record_id", "entity_type", "topic"],
    "link": ["record_id", "entity_type", "url"],
    "plan": ["record_id", "entity_type", "title", "status"],
    "product": ["record_id", "entity_type", "name"],
    "person": ["record_id", "entity_type", "name"],
    "workout": ["record_id", "entity_type", "date"],
}


def _write_type_assets(type_dir: Path, kind: str, type_id: str, description: str,
                       descriptor: dict[str, Any]) -> None:
    """Write ``type.json`` + starter template + the four CRUD prompts of a type."""
    from todoc.typing_system.prompts import build_prompts, build_template

    (type_dir / "type.json").write_text(
        json.dumps(descriptor, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    extension = "md" if kind == "doc_type" else "json"
    (type_dir / f"template.{extension}").write_text(
        build_template(type_id, kind, description, descriptor), encoding="utf-8")
    prompts_dir = type_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    for operation, text in build_prompts(type_id, kind, description, descriptor).items():
        (prompts_dir / f"{operation}.md").write_text(text, encoding="utf-8")


def init_dataset(root: Path) -> dict[str, Any]:
    """Create .todoc/ control files. Never scans/moves user data."""
    todoc_dir = root / ".todoc"
    if (todoc_dir / "dataset.json").is_file():
        raise ValidationError(f"Dataset already initialized at {root}", "config.already_initialized")
    dataset_id = f"dataset-{uuid.uuid4().hex[:8]}"
    dataset = default_dataset(dataset_id)

    (todoc_dir / "rules").mkdir(parents=True, exist_ok=True)
    (todoc_dir / "dir_types").mkdir(parents=True, exist_ok=True)
    (todoc_dir / "doc_types").mkdir(parents=True, exist_ok=True)
    (todoc_dir / "entity_types").mkdir(parents=True, exist_ok=True)
    (todoc_dir / "relation_types").mkdir(parents=True, exist_ok=True)
    (todoc_dir / "templates" / "records").mkdir(parents=True, exist_ok=True)
    (todoc_dir / "schemas" / "records").mkdir(parents=True, exist_ok=True)
    (todoc_dir / "queries").mkdir(parents=True, exist_ok=True)
    (todoc_dir / "generated").mkdir(parents=True, exist_ok=True)

    (todoc_dir / "dataset.json").write_text(json.dumps(dataset, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (todoc_dir / "rules" / "directory-rules.json").write_text(
        json.dumps(default_directory_rules(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (todoc_dir / "rules" / "document-rules.json").write_text(
        json.dumps(default_document_rules(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    for type_id in ("research", "plan", "architecture", "constitution", "harness", "glossary"):
        d = todoc_dir / "dir_types" / type_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "type.json").write_text(
            json.dumps(_type_stub(type_id, f"Folder type {type_id}.", "dir_type"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    for type_id, sections in DEFAULT_DOC_TYPES.items():
        d = todoc_dir / "doc_types" / type_id
        d.mkdir(parents=True, exist_ok=True)
        descriptor = _type_stub(type_id, f"Document type {type_id}.", "doc_type",
                               {"format": "markdown", "template": "template.md",
                                "required_sections": sections})
        _write_type_assets(d, "doc_type", type_id, f"Document type {type_id}.", descriptor)
    for type_id, fields in DEFAULT_ENTITY_TYPES.items():
        d = todoc_dir / "entity_types" / type_id
        d.mkdir(parents=True, exist_ok=True)
        descriptor = _type_stub(type_id, f"Entity type {type_id}.", "entity_type",
                               {"format": "json", "template": "template.json",
                                "required_fields": fields,
                                "path_template": f"records/{type_id}/{{slug}}.json"})
        _write_type_assets(d, "entity_type", type_id, f"Entity type {type_id}.", descriptor)
    for type_id in ("performed_by", "derived_from", "supports", "contradicts"):
        d = todoc_dir / "relation_types" / type_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "type.json").write_text(
            json.dumps(_type_stub(type_id, f"Relation type {type_id}.", "relation_type"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    (todoc_dir / "templates" / "records" / "note.json").write_text(
        json.dumps({"schema_version": 1, "record_id": "note:example", "entity_type": "note", "title": ""}, indent=2) + "\n",
        encoding="utf-8",
    )
    return dataset


def load_dataset(root: Path) -> dict[str, Any]:
    dataset_file = root / ".todoc" / "dataset.json"
    if not dataset_file.is_file():
        raise ValidationError(f"No dataset at {root}: missing .todoc/dataset.json", "config.missing_dataset")
    dataset = require_schema_version(load_json_file(dataset_file), dataset_file)
    if not isinstance(dataset.get("dataset_id"), str) or not dataset["dataset_id"]:
        raise ValidationError(f"{dataset_file}: dataset_id is required", "config.invalid_schema")
    limits = dict(DEFAULT_LIMITS)
    limits.update(dataset.get("limits") or {})
    dataset["limits"] = limits
    return dataset


def load_rules(root: Path, dataset: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    todoc_dir = root / ".todoc"
    dir_file = todoc_dir / dataset.get("directory_rules", "rules/directory-rules.json")
    doc_file = todoc_dir / dataset.get("document_rules", "rules/document-rules.json")
    dir_rules: list[dict[str, Any]] = []
    doc_rules: list[dict[str, Any]] = []
    if dir_file.is_file():
        data = require_schema_version(load_json_file(dir_file), dir_file)
        dir_rules = list(data.get("rules") or [])
    if doc_file.is_file():
        data = require_schema_version(load_json_file(doc_file), doc_file)
        doc_rules = list(data.get("rules") or [])
    return dir_rules, doc_rules
