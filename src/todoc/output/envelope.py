"""JSON envelope {schema_version, ok, data, diagnostics, next_actions}."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Envelope:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    next_actions: list[dict[str, Any]] = field(default_factory=list)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ok": self.ok,
            "data": self.data,
            "diagnostics": self.diagnostics,
            "next_actions": self.next_actions,
        }


def make_envelope(ok: bool, data: dict[str, Any] | None = None,
                  diagnostics: list[dict[str, Any]] | None = None,
                  next_actions: list[dict[str, Any]] | None = None) -> Envelope:
    return Envelope(ok=ok, data=data or {}, diagnostics=diagnostics or [], next_actions=next_actions or [])


def emit(envelope: Envelope, output: str, out_path: str | None = None) -> None:
    """Emit in json/table/markdown mode. JSON stdout is exactly one JSON text."""
    if output == "json":
        text = json.dumps(envelope.to_dict(), indent=2, ensure_ascii=False)
        if out_path:
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
        else:
            sys.stdout.write(text + "\n")
        return
    # Human modes: same machine facts, compact rendering.
    lines: list[str] = []
    lines.append(f"ok: {envelope.ok}")
    for key, value in envelope.data.items():
        lines.append(f"{key}: {value}")
    for diag in envelope.diagnostics:
        lines.append(f"[{diag.get('severity', 'error')}] {diag.get('code', '')} {diag.get('path', '')}: {diag.get('message', '')}")
    for action in envelope.next_actions:
        argv = " ".join(str(a) for a in action.get("argv", []))
        lines.append(f"next: {argv} ({action.get('purpose', '')})")
    text = "\n".join(lines) + "\n"
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
