#!/usr/bin/env python3
"""Markdown link checker: resolve every relative link against its own file.

Every relative target is resolved from the directory of the file that contains
it, so the same check works at any depth and after any move. External, mail and
pure-anchor links are skipped. Usage:

    python3 tools/linkcheck.py [PATH]     # default: the repository root

Exit code is 0 and the report lists every broken target, so a run before and
after a change can be compared line by line.

What counts as a link
---------------------
Only links a Markdown renderer would actually follow. Links inside fenced code
blocks (```` ``` ````/``~~~``) and inside inline code spans are documentation
*about* links — examples, templates, and diagnostic ``evidence`` payloads — and
are skipped, matching the parser's own behaviour documented in
``docs/state/05-formats.md`` ("ссылка внутри fenced-блока | нет").

Vendored snapshots of third-party repositories are skipped wholesale: their
links belong to the upstream projects, not to this one.

Known limitation: indented code blocks (four spaces) are not treated as code.
No such case exists in this repository today, and guessing list-continuation
indentation would risk hiding real links.
"""

from __future__ import annotations

import pathlib
import re
import sys

LINK = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<target>[^)]*)\)")

#: An opening or closing fence: three or more backticks or tildes.
FENCE = re.compile(r"^(?P<indent>\s{0,3})(?P<ticks>`{3,}|~{3,})(?P<info>.*)$")

#: An inline code span: a run of backticks, then text, then the same run.
INLINE_CODE = re.compile(r"(`+)(?s:.+?)\1")

#: Generated, non-source, or vendored trees: their links are not authored here.
SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".egg-info",
    "index",
    "cache",
    # Snapshots of third-party repositories kept as research material.
    "skills-audit",
}


def markdown_files(root: pathlib.Path):
    for path in sorted(root.rglob("*.md")):
        if SKIP_DIRS & set(path.relative_to(root).parts[:-1]):
            continue
        yield path


def prose_lines(text: str):
    """Yield ``(lineno, line)`` for lines outside fenced code blocks.

    Inline code spans are blanked out (spaces keep the columns intact) so that
    example links inside backticks are not reported.
    """
    fence_char = ""
    fence_len = 0
    fence_indent = 0
    for lineno, line in enumerate(text.splitlines(), start=1):
        match = FENCE.match(line)
        if match:
            ticks = match.group("ticks")
            if not fence_char:
                # An opening fence may carry an info string; a backtick fence may
                # not contain backticks in it.
                info = match.group("info").strip()
                if ticks[0] == "`" and "`" in info:
                    yield lineno, line
                    continue
                fence_char, fence_len = ticks[0], len(ticks)
                fence_indent = len(match.group("indent"))
                continue
            if (ticks[0] == fence_char
                    and len(ticks) >= fence_len
                    and not match.group("info").strip()
                    and len(match.group("indent")) <= fence_indent):
                fence_char = ""
                continue
        if fence_char:
            continue
        yield lineno, INLINE_CODE.sub(lambda m: " " * len(m.group(0)), line)


def main() -> int:
    root = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else (
        pathlib.Path(__file__).resolve().parents[1])
    total = 0
    broken: list[tuple[str, str]] = []
    for path in markdown_files(root):
        text = path.read_text(encoding="utf-8")
        for lineno, line in prose_lines(text):
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
