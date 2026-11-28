"""Resolve progressive help from the bundled catalog."""

from functools import lru_cache
from importlib.resources import files
import json
from typing import Any


@lru_cache(maxsize=1)
def _catalog() -> dict[str, str | dict[str, Any]]:
    source = files("todoc").joinpath("data", "guidance", "ru.json")
    return json.loads(source.read_text(encoding="utf-8"))


def guidance_for(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    errors = list(dict.fromkeys(d["code"] for d in diagnostics if d["severity"] == "error"))
    if not errors:
        return {"profile": "ru", "mode": "compact", "items": []}
    catalog = _catalog()
    items = []
    for code in errors:
        guidance = catalog.get(code, catalog["usage.error"])
        if isinstance(guidance, str):
            guidance = {"hint": guidance, "skills": [], "docs": []}
        items.append({"code": code, **guidance})
    return {"profile": "ru", "mode": "on_error", "items": items}
