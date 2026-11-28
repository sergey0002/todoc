"""Shared projection rules for CLI results."""

from __future__ import annotations

from typing import Any

from todoc.errors import TodocError, EXIT_USAGE


def selected_fields(allowed: tuple[str, ...], include: str | None, exclude: str | None,
                    *, structural: tuple[str, ...] = ()) -> tuple[str, ...]:
    if include is not None and exclude is not None:
        raise TodocError("Use either --fields or --exclude-fields.", EXIT_USAGE, "fields.conflict")
    if include is None and exclude is None:
        return allowed
    raw = include if include is not None else exclude
    names = {name.strip() for name in (raw or "").split(",")}
    unknown = names.difference(allowed)
    if unknown:
        raise TodocError(f"Unknown fields: {', '.join(sorted(unknown))}", EXIT_USAGE, "fields.unknown")
    if include is not None:
        return tuple(name for name in allowed if name in names or name in structural)
    return tuple(name for name in allowed if name not in names or name in structural)


def project_fields(item: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {name: item[name] for name in fields if name in item}


def mermaid_graph(nodes: list[str], edges: list[dict[str, Any]]) -> str:
    """Render graph labels as Mermaid text without allowing input to insert syntax."""
    def label(text: str) -> str:
        return "".join(character if character.isalnum() or character in " _-" else f"#{ord(character)};"
                       for character in text)

    identifiers = {node: f"n{index}" for index, node in enumerate(nodes)}
    lines = ["flowchart LR"]
    lines.extend(f'  {identifiers[node]}["{label(node)}"]' for node in nodes)
    lines.extend(
        f'  {identifiers[edge["from"]]} -->|"{label(edge["type_id"])}"| {identifiers[edge["to"]]}'
        for edge in edges
    )
    return "\n".join(lines)
