"""Source-format adapters for the common document metadata model."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def _markdown_attributes(source: Any) -> tuple[dict[str, Any], str, bool]:
    return source.front_matter, "", True


def _json_attributes(source: Any) -> tuple[dict[str, Any], str, bool]:
    if not isinstance(source, dict):
        return {}, "", False
    if "record_id" not in source and "meta" in source:
        metadata = source["meta"]
        return (metadata if isinstance(metadata, dict) else {}), "/meta", True
    return source, "", "record_id" not in source


_ADAPTERS: dict[str, Callable[[Any], tuple[dict[str, Any], str, bool]]] = {
    "markdown": _markdown_attributes,
    "json": _json_attributes,
}


def get_attributes(file_format: str, source: Any) -> tuple[dict[str, Any], str, bool]:
    """Return metadata, its source pointer prefix and document-profile eligibility."""
    return _ADAPTERS[file_format](source)
