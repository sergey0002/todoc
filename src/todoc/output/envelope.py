"""JSON envelope {schema_version, ok, data, diagnostics, next_actions}."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any

from todoc.output.guidance import guidance_for


@dataclass
class Envelope:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    next_actions: list[dict[str, Any]] = field(default_factory=list)
    schema_version: int = 1
    guidance: dict[str, Any] | None = None
    include_guidance: bool = False

    @classmethod
    def collection(cls, meta: dict[str, Any], items: list[dict[str, Any]], *,
                   diagnostics: list[dict[str, Any]] | None = None) -> Envelope:
        return cls.result(meta, {"items": items}, diagnostics=diagnostics)

    @classmethod
    def result(cls, meta: dict[str, Any], result: dict[str, Any], *,
               diagnostics: list[dict[str, Any]] | None = None) -> Envelope:
        findings = diagnostics or []
        return cls(
            not any(item["severity"] == "error" for item in findings),
            {"meta": meta, "result": result}, findings,
            schema_version=2, guidance=guidance_for(findings),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "ok": self.ok,
            "data": self.data,
            "diagnostics": self.diagnostics,
            "next_actions": self.next_actions,
        }
        if self.include_guidance or self.guidance is not None:
            payload["guidance"] = self.guidance
        return payload


def make_envelope(ok: bool, data: dict[str, Any] | None = None,
                  diagnostics: list[dict[str, Any]] | None = None,
                  next_actions: list[dict[str, Any]] | None = None,
                  guidance: dict[str, Any] | None = None,
                  include_guidance: bool = False) -> Envelope:
    return Envelope(ok=ok, data=data or {}, diagnostics=diagnostics or [],
                    next_actions=next_actions or [], guidance=guidance,
                    include_guidance=include_guidance)


def _table(items: list[dict[str, Any]]) -> list[str]:
    fields = tuple(dict.fromkeys(key for item in items for key in item))
    if not fields:
        return ["items: []"]

    def cell(value: Any) -> str:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        return text.replace("|", "\\|").replace("\r", "\\r").replace("\n", "\\n")

    def row(values) -> str:
        return "| " + " | ".join(cell(value) for value in values) + " |"

    return [row(fields), row(["---"] * len(fields)),
            *(row(item.get(field, "") for field in fields) for item in items)]


def render(envelope: Envelope, output: str) -> str:
    """Serialize an envelope without touching stdout or the filesystem."""
    if output == "json":
        return json.dumps(envelope.to_dict(), indent=2, ensure_ascii=False) + "\n"
    # Human modes: same machine facts, compact rendering.
    lines: list[str] = []
    lines.append(f"ok: {envelope.ok}")
    for key, value in envelope.data.items():
        if output == "markdown" and key == "result" and isinstance(value, dict) and "mermaid" in value:
            diagram = value["mermaid"]
            details = {name: field for name, field in value.items() if name != "mermaid"}
            fence = chr(96) * 3
            lines.extend((f"{key}: {details}", "", f"{fence}mermaid", diagram, fence))
        elif key == "result" and isinstance(value, dict) and "tree_text" in value:
            lines.extend(("result:", str(value["tree_text"]), "", *_table(value["skills"])))
            lines.extend(f"{name}: {field}" for name, field in value.items()
                         if name not in ("tree_text", "skills", "root"))
        elif envelope.schema_version == 2 and key == "result" and isinstance(value, dict) and "items" in value:
            lines.extend(("result:", "", *_table(value["items"])))
            lines.extend(f"{name}: {field}" for name, field in value.items() if name != "items")
        else:
            lines.append(f"{key}: {value}")
    for diag in envelope.diagnostics:
        lines.append(f"[{diag.get('severity', 'error')}] {diag.get('code', '')} {diag.get('path', '')}: {diag.get('message', '')}")
    if envelope.guidance is not None:
        lines.append(f"guidance: {envelope.guidance}")
    for action in envelope.next_actions:
        argv = " ".join(str(a) for a in action.get("argv", []))
        lines.append(f"next: {argv} ({action.get('purpose', '')})")
    return "\n".join(lines) + "\n"


def write(text: str, out_path: str | None = None) -> None:
    """Transport only: send rendered text to a file or stdout."""
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)


def emit(envelope: Envelope, output: str, out_path: str | None = None) -> None:
    """Render in json/table/markdown mode, then write to stdout or ``out_path``."""
    write(render(envelope, output), out_path)
