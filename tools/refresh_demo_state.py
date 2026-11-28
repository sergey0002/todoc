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

#: Docs reference demo assets as ``../../demo/...``; from the demo copy the same
#: file is one level shallower (``../../plan/…``, ``../../bugs/…``, …).
DEMO_ASSET = re.compile(r"^\.\./\.\./demo/(?P<rest>.+)$")

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
    # Guides are repo-only.
    "../guides/python-api-for-agents.md",
    # The generated Click reference is not mirrored into the demo dataset.
    "cli.md",
    # Config lives under .todoc, which is not part of the document index.
    "../../demo/.todoc/document-metadata.schema.json",
    # The history/changes plan is deliberately not mirrored into the demo dataset.
    "../plan/history-and-changes.md",
    # Repo source is not copied into the demo dataset either.
    "../../src/todoc/adapters/formats/jsonfmt.py",
}

#: Prefixes whose targets never exist inside the demo dataset.
DELINK_PREFIXES = ("../../src/", "../guides/")

LINK = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)(?P<rest>[^)]*)\)")

#: Generated sources that deliberately have no demo mirror: ``cli.md`` is rendered
#: from the Click tree by ``tools/render_cli_reference.py``, so requiring a copy
#: here would block every refresh.
EXCLUDE = {"cli.md"}


def sources() -> list[pathlib.Path]:
    return sorted(p for p in SRC.glob("*.md") if p.name not in EXCLUDE)


def remap_link(match: re.Match[str]) -> str:
    target = match.group("target")
    text = match.group("text")
    rest = match.group("rest")
    if target in DELINK or target.startswith(DELINK_PREFIXES):
        return text
    after = AFTER.match(target)
    demo_asset = DEMO_ASSET.match(target)
    if after:
        target = f"../../plan/after/{after.group('name')}"
    elif demo_asset:
        rest_path = demo_asset.group("rest")
        if (DST.parents[1] / rest_path).is_dir():
            # The validator resolves links to documents; a folder has no document
            # counterpart in the copy, so keep the text and drop the link.
            return text
        target = f"../../{rest_path}"
    else:
        target = REMAP.get(target, target)
    return f"[{text}]({target}{rest})"


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="report drift without writing; exit 1 when a copy is stale")
    args = parser.parse_args(argv)
    mirrored = sources()
    missing = sorted(p.name for p in mirrored if not (DST / p.name).is_file())
    if missing:
        print(f"no demo copy for: {missing}", file=sys.stderr)
        return 1

    changed: list[str] = []
    for source in mirrored:
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

        # Dates belong to the copy: keep them so a refresh is not a history event.
        front_lines = ["---"]
        for key in ("created", "updated"):
            if key in fields:
                front_lines.append(f"{key}: {fields[key]}")
        front_lines.extend([
            f"id: {fields['id']}",
            f"title: {fields['title']}",
            f"doc_type: {fields.get('doc_type', 'reference')}",
            f"lang: {fields.get('lang', 'ru')}",
            f"source: docs/state/{source.name}",
            "copied: true",
            "---",
        ])
        rendered = "\n".join(front_lines) + "\n\n" + new_body.lstrip("\n")
        if rendered != original:
            changed.append(source.name)
            if not args.check:
                target.write_text(rendered, encoding="utf-8")

    if args.check:
        state = "up to date" if not changed else f"stale: {changed}"
        print(f"checked {len(mirrored)} copies: {state}")
        return 0 if not changed else 1
    print(f"refreshed {len(changed)} of {len(mirrored)}: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
