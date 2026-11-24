"""Markdown adapter: headings/links/front matter from tokens, never regex.

Uses markdown-it-py (CommonMark) token stream. Front matter is a separate
YAML-lite layer (simple ``key: value`` pairs) validated independently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from markdown_it import MarkdownIt

_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


@dataclass
class Heading:
    title: str
    level: int
    line: int
    anchor: str
    parent_index: int | None = None
    children: list[Heading] = field(default_factory=list)


@dataclass
class Link:
    text: str
    target: str
    line: int
    column: int
    is_wikilink: bool = False


@dataclass
class MarkdownDoc:
    title: str
    front_matter: dict[str, Any]
    headings: list[Heading]
    links: list[Link]
    text: str
    errors: list[str] = field(default_factory=list)


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9\u0400-\u04ff]+", "-", title.lower()).strip("-")
    return slug or "section"


def _parse_front_matter(text: str) -> tuple[dict[str, Any], str, int]:
    """Return (front_matter, body, body_start_line_1based)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, 1
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text, 1
    fm: dict[str, Any] = {}
    for raw in lines[1:end]:
        if ":" not in raw:
            continue
        key, _, value = raw.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value in ("true", "false"):
            fm[key] = value == "true"
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            fm[key] = [v.strip().strip('"').strip("'") for v in inner.split(",") if v.strip()] if inner else []
        else:
            fm[key] = value
    body = "\n".join(lines[end + 1 :])
    return fm, body, end + 2


def parse_markdown(text: str) -> MarkdownDoc:
    front_matter, body, body_start = _parse_front_matter(text)
    md = MarkdownIt("commonmark")
    tokens = md.parse(body)
    headings: list[Heading] = []
    stack: list[tuple[int, int]] = []  # (level, index)
    seen_anchors: dict[str, int] = {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            level = int(tok.tag[1])
            line = (tok.map[0] + body_start) if tok.map else body_start
            # markdown-it always emits an inline token after heading_open.
            title = (tokens[i + 1].content or "").strip() if i + 1 < len(tokens) else ""
            base = _slugify(title)
            count = seen_anchors.get(base, 0)
            anchor = base if count == 0 else f"{base}-{count}"
            seen_anchors[base] = count + 1
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent = stack[-1][1] if stack else None
            headings.append(Heading(title=title, level=level, line=line, anchor=anchor, parent_index=parent))
            stack.append((level, len(headings) - 1))
        i += 1
    # Build tree children.
    for idx, h in enumerate(headings):
        if h.parent_index is not None:
            headings[h.parent_index].children.append(h)

    links: list[Link] = []
    for lineno, raw_line in enumerate(body.splitlines(), start=body_start):
        for m in _LINK_RE.finditer(raw_line):
            links.append(Link(text=m.group(1), target=m.group(2), line=lineno, column=m.start() + 1))
        for m in _WIKILINK_RE.finditer(raw_line):
            links.append(Link(text=m.group(1).strip(), target=m.group(1).strip(), line=lineno, column=m.start() + 1, is_wikilink=True))

    title = ""
    if front_matter.get("title"):
        title = str(front_matter["title"])
    elif headings:
        title = headings[0].title
    return MarkdownDoc(title=title, front_matter=front_matter, headings=headings, links=links, text=text)


def heading_path_for(headings: list[Heading], index: int) -> list[str]:
    path: list[str] = []
    cur: Heading | None = headings[index]
    while cur is not None:
        path.append(cur.title)
        cur = headings[cur.parent_index] if cur.parent_index is not None else None
    path.reverse()
    return path
