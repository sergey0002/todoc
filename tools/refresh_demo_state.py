#!/usr/bin/env python3
"""Refresh ``demo/references/state/*`` from ``docs/state/*``.

The demo dataset carries a copy of the state documentation inside itself, so an
agent working in the demo DATA_ROOT can read it without leaving the root. The
copy is derived, never edited by hand: this script rewrites the body from the
source, keeps each file's own front matter identity, and re-expresses the links
for the copy's location (``demo/references/state/`` instead of ``docs/state/``).

Links that have no counterpart inside the demo dataset are de-linked to plain
text rather than pointed at a file that does not exist.
"""

from __future__ import annotations

import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SRC = REPO / "docs" / "state"
DST = REPO / "demo" / "references" / "state"

#: Repo-relative link target -> the same target seen from demo/references/state/.
REMAP = {
    "../plan/audit-implementation.md": "../../plan/audit-implementation.md",
    "../plan/competitive-analysis.md": "../../plan/competitive-analysis.md",
    "../plan/constitution.md": "../../plan/constitution.md",
    "../plan/implementation-plan.md": "../../plan/implementation-plan.md",
    "../../SKILL.md": "../../skill/SKILL.md",
    "../../demo/README.md": "../../README.md",
    "../../demo/competitors/basic-memory.md": "../../competitors/basic-memory.md",
    "../../references/workflow.md": "../workflow.md",
}

#: AFTER-plans live one level deeper in the demo dataset.
AFTER = re.compile(r"^\.\./plan/(?P<name>[^/]+\.after\.md)$")

#: No counterpart inside the demo dataset: keep the text, drop the link.
DELINK = {
    "../../bench/criteria.md",
    "../../bench/results/benchmark.json",
    "../../bench/results/benchmark.md",
    # Repo-level docs index and installation guide: not copied into the demo.
    "../README.md",
    "../installation.md",
    # The history/changes plan is deliberately not mirrored into the demo dataset.
    "../plan/history-and-changes.md",
    # Repo source is not copied into the demo dataset either.
    "../../src/todoc/adapters/formats/jsonfmt.py",
}

LINK = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)(?P<rest>[^)]*)\)")


def remap_link(match: re.Match[str]) -> str:
    target = match.group("target")
    text = match.group("text")
    rest = match.group("rest")
    if target in DELINK:
        return text
    after = AFTER.match(target)
    if after:
        target = f"../../plan/after/{after.group('name')}"
    else:
        target = REMAP.get(target, target)
    return f"[{text}]({target}{rest})"


def main() -> int:
    missing = sorted(p.name for p in SRC.glob("*.md") if not (DST / p.name).is_file())
    if missing:
        print(f"no demo copy for: {missing}", file=sys.stderr)
        return 1

    changed: list[str] = []
    for source in sorted(SRC.glob("*.md")):
        target = DST / source.name
        body = source.read_text(encoding="utf-8")
        new_body = LINK.sub(remap_link, body)

        original = target.read_text(encoding="utf-8")
        if not original.startswith("---\n"):
            print(f"{target}: no front matter to preserve", file=sys.stderr)
            return 1
        head, _, _tail = original.partition("---\n---\n")
        fields: dict[str, str] = {}
        for line in head.splitlines()[1:]:
            key, sep, value = line.partition(":")
            if sep:
                fields[key.strip()] = value.strip()
        for key in ("id", "title"):
            if key not in fields:
                print(f"{target}: front matter has no {key!r}", file=sys.stderr)
                return 1

        front = "\n".join([
            "---",
            f"id: {fields['id']}",
            f"title: {fields['title']}",
            f"doc_type: {fields.get('doc_type', 'reference')}",
            f"lang: {fields.get('lang', 'ru')}",
            f"source: docs/state/{source.name}",
            "copied: true",
            "---",
        ])
        rendered = f"{front}\n{new_body}"
        if rendered != original:
            target.write_text(rendered, encoding="utf-8")
            changed.append(source.name)

    print(f"refreshed {len(changed)} of {len(list(SRC.glob('*.md')))}: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
