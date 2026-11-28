"""Select a stable page of document metadata from one dataset snapshot."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from todoc.errors import TodocError, EXIT_USAGE
from todoc.application.paging import page
from todoc.application.filters import compile_conditions, matches_conditions, tag_matches


FIELDS = ("id", "path", "title", "doc_type", "status", "parse_status", "tags", "updated", "hash")


def normalize_scope(within: str) -> str:
    path = PurePosixPath(within)
    if path.is_absolute() or ".." in path.parts or "\\" in within or ":" in within:
        raise TodocError("Expected a path relative to DATA_ROOT.", EXIT_USAGE, "docs.invalid_scope")
    return path.as_posix()


def matching_documents(documents: list[dict[str, Any]], within: str, types: tuple[str, ...],
                       file_format: str | None) -> list[dict[str, Any]]:
    return [
        doc for doc in documents
        if (within == "." or doc["path"] == within or doc["path"].startswith(within + "/"))
        and (not types or doc["doc_type"] in types)
        and (file_format is None or doc["format"] == file_format)
    ]


def select_document_attributes(
    candidates: list[dict[str, Any]], declared: dict[str, Any], attributes: tuple[tuple[str, str], ...],
    filter_file: Path | None, tag: str | None, any_tags: tuple[str, ...], all_tags: tuple[str, ...],
) -> tuple[list[dict[str, Any]], tuple[tuple[str, str, Any], ...]]:
    conditions = compile_conditions([doc["attributes"] for doc in candidates], declared,
                                    attributes, filter_file)
    required_tags = (*all_tags, tag.casefold()) if tag is not None else all_tags
    return [
        doc for doc in candidates
        if tag_matches(doc.get("tags", []), any_tags, required_tags)
        and matches_conditions(doc["attributes"], conditions)
    ], conditions


def list_documents(payload: dict[str, Any], *, types: tuple[str, ...], within: str,
                   tag: str | None, any_tags: tuple[str, ...], all_tags: tuple[str, ...],
                   file_format: str | None, statuses: tuple[str, ...], status_missing: bool,
                   attributes: tuple[tuple[str, str], ...], filter_file: Path | None,
                   declared: dict[str, Any], limit: int, cursor: str | None
                   ) -> tuple[list[dict[str, Any]], int, str | None]:
    candidates = matching_documents(payload["documents"], within, types, file_format)
    candidates, conditions = select_document_attributes(
        candidates, declared, attributes, filter_file, tag, any_tags, all_tags,
    )
    selection = [2, "docs list", payload["dataset_id"], payload["corpus_digest"], within,
                 types, tag, any_tags, all_tags, file_format, sorted(set(statuses)), status_missing, conditions]
    items = []
    for doc in candidates:
        tags = doc.get("tags", [])
        status = doc.get("lifecycle_status")
        if (statuses or status_missing) and status not in statuses and not (status_missing and status is None):
            continue
        items.append({
            "id": doc["document_id"], "path": doc["path"], "title": doc["title"],
            "doc_type": doc["doc_type"], "status": status, "parse_status": doc["status"],
            "tags": tags, "updated": doc.get("updated"), "hash": doc["hash"],
            "attributes": doc["attributes"],
        })
    items.sort(key=lambda item: (item["path"], item["id"]))
    rows, next_cursor = page(items, selection, limit, cursor)
    return rows, len(items), next_cursor


def within_depth(path: str, scope: str, depth: int) -> bool:
    relative = PurePosixPath(path)
    base = PurePosixPath(scope)
    return relative.is_relative_to(base) and len(relative.relative_to(base).parts) <= depth


def folder_tree(scope: str, rows: list[dict[str, Any]], *,
                folder_metadata: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Attach page rows while restoring only the ancestors needed for navigation."""
    nodes = {row["path"]: {**row, "context_only": False, "children": []} for row in rows}

    def folder(path: str) -> dict[str, Any]:
        if path not in nodes:
            nodes[path] = {
                "id": f"folder:{path}", "path": path, "kind": "folder",
                "context_only": True, "children": [],
            }
            if folder_metadata is not None:
                nodes[path].update({"title": PurePosixPath(path).name or path, **folder_metadata.get(path, {})})
            if path != scope:
                folder(PurePosixPath(path).parent.as_posix())["children"].append(nodes[path])
        return nodes[path]

    root = folder(scope)
    for row in rows:
        path = row["path"]
        if path != scope:
            folder(PurePosixPath(path).parent.as_posix())["children"].append(nodes[path])
    return root
