#!/usr/bin/env python3
"""Markdown link checker: resolve every relative link against its own file.

Every relative target is resolved from the directory of the file that contains
it, so the same check works at any depth and after any move. External, mail and
pure-anchor links are skipped. Usage:

    python3 tools/linkcheck.py [PATH]     # default: the repository root

Exit code is 0 and the report lists every broken target, so a run before and
after a change can be compared line by line.
"""

from __future__ import annotations

import pathlib
import re
import sys

LINK = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<target>[^)]*)\)")

#: Generated or non-source trees: their links are produced, not authored.
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".egg-info", "index", "cache"}


def markdown_files(root: pathlib.Path):
    for path in sorted(root.rglob("*.md")):
        if SKIP_DIRS & set(path.relative_to(root).parts[:-1]):
            continue
        yield path


def main() -> int:
    root = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else (
        pathlib.Path(__file__).resolve().parents[1])
    total = 0
    broken: list[tuple[str, str]] = []
    for path in markdown_files(root):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in LINK.finditer(line):
                target = match.group("target").strip()
                if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                target = target.split()[0].strip("<>")
                if not target or target.startswith("#"):
                    continue
                total += 1
                resolved = (path.parent / target.split("#")[0]).resolve()
                if not resolved.exists():
                    broken.append((str(path.relative_to(root)), f"{lineno}: {target}"))
    print(f"scanned {total} relative links, broken {len(broken)}")
    for owner, where in broken:
        print(f"  {owner}  {where}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
