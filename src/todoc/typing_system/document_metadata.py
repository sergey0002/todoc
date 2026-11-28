"""Load the optional dataset-wide schema shared by Markdown and JSON documents."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, SchemaError
from referencing import Registry

from todoc.errors import ValidationError
from todoc.typing_system.descriptors import load_json_file

SCHEMA_PATH = ".todoc/document-metadata.schema.json"


def default_metadata_schema() -> dict[str, Any]:
    resource = files("todoc").joinpath("data", "metadata", "document-metadata.schema.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def load_metadata_schema(root: Path) -> dict[str, Any] | None:
    path = root / SCHEMA_PATH
    if not path.exists():
        return None
    data = load_json_file(path)
    if not isinstance(data, dict):
        raise ValidationError(f"{SCHEMA_PATH}: expected a schema object", "metadata.invalid_schema")
    try:
        Draft202012Validator.check_schema(data)
    except SchemaError as exc:
        raise ValidationError(f"{SCHEMA_PATH}: {exc.message}", "metadata.invalid_schema") from exc
    return data


def metadata_errors(data: dict[str, Any], schema: dict[str, Any], prefix: str) -> list[tuple[str, str]]:
    result = []
    validator = Draft202012Validator(schema, registry=Registry(), format_checker=FormatChecker())
    try:
        for error in validator.iter_errors(data):
            suffix = "/".join(str(token).replace("~", "~0").replace("/", "~1") for token in error.absolute_path)
            pointer = f"{prefix}/{suffix}" if suffix else (prefix or "/")
            result.append((pointer, error.message))
    except Exception as exc:
        # Unresolved refs use jsonschema's private wrapping exception. Depending
        # on the jsonschema version the original error is attached as ``__cause__``
        # or only as ``__context__``, so accept either link to the registry error.
        from referencing.exceptions import Unresolvable

        if not any(isinstance(cause, Unresolvable) for cause in (exc.__cause__, exc.__context__)):
            raise
        raise ValidationError(f"Metadata schema reference cannot be resolved: {exc}",
                              "metadata.invalid_schema") from exc
    return sorted(result)


def normalize_markdown_attributes(
    values: dict[str, Any], schemas: list[tuple[dict[str, Any], str]],
) -> dict[str, Any]:
    """Interpret YAML-lite scalar strings using declared metadata types."""
    properties = {}
    for schema, _source in schemas:
        properties.update(schema.get("properties", {}))
    result = dict(values)
    for key, value in values.items():
        spec = properties.get(key)
        if not isinstance(spec, dict) or not isinstance(value, str):
            continue
        if spec.get("type") not in ("integer", "number", "null"):
            continue
        try:
            decoded = json.loads(value)
        except (ValueError, RecursionError):
            continue
        if decoded is None or type(decoded) in (int, float):
            if json.dumps(decoded) not in ("NaN", "Infinity", "-Infinity"):
                result[key] = decoded
    return result
