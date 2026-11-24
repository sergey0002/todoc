"""Deterministic lexical search over registry documents (E4/E5, offline)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from todoc.adapters.formats.markdown import parse_markdown
from todoc.domain.models import SearchHit

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_\u0400-\u04ff]+")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _terms(query: str) -> list[str]:
    return tokenize(query)


def _document_text(root: Path, rel_path: str, fmt: str) -> str:
    try:
        text = (root / rel_path).read_text(encoding="utf-8")
    except OSError:
        return ""
    if fmt == "markdown":
        doc = parse_markdown(text)
        headings = " ".join(h.title for h in doc.headings)
        return f"{doc.title}\n{headings}\n{text}"
    return text


def _snippet(text: str, terms: list[str], max_chars: int = 240) -> tuple[str, int, int, bool]:
    lowered = text.lower()
    best_pos = -1
    for term in terms:
        pos = lowered.find(term)
        if pos != -1 and (best_pos == -1 or pos < best_pos):
            best_pos = pos
    if best_pos == -1:
        return text[:max_chars], 1, 1, len(text) > max_chars
    start = max(0, best_pos - 80)
    end = min(len(text), best_pos + 160)
    snippet = text[start:end].replace("\n", " ").strip()
    truncated = end < len(text) or start > 0
    line_start = text.count("\n", 0, start) + 1
    line_end = text.count("\n", 0, end) + 1
    return snippet, line_start, line_end, truncated


def search_documents(
    root: Path,
    documents: list[dict[str, Any]],
    query: str,
    doc_type: str | None = None,
    within: str | None = None,
    limit: int = 10,
    budget: int | None = None,
) -> tuple[list[SearchHit], int, bool]:
    """Return (hits, total, truncated). Deterministic rank, tie-break by id."""
    terms = _terms(query)
    if not terms:
        return [], 0, False
    candidates: list[tuple[int, dict[str, Any], str, list[str]]] = []
    for doc in documents:
        if doc.get("status") not in ("ok", None):
            continue
        if doc_type is not None and doc.get("doc_type") != doc_type:
            continue
        if within is not None:
            path = str(doc.get("path", ""))
            if path != within and not path.startswith(within.rstrip("/") + "/"):
                continue
        text = _document_text(root, str(doc.get("path", "")), str(doc.get("format", "")))
        lowered = text.lower()
        matched = [t for t in terms if t in lowered]
        if not matched:
            continue
        title = str(doc.get("title", ""))
        title_hits = sum(1 for t in matched if t in title.lower())
        score = title_hits * 10 + len(matched)
        candidates.append((score, doc, text, matched))
    candidates.sort(key=lambda c: (-c[0], str(c[1].get("document_id", ""))))
    total = len(candidates)
    hits: list[SearchHit] = []
    used_bytes = 0
    for rank, (_score, doc, text, matched) in enumerate(candidates[:limit], start=1):
        snippet, line_start, line_end, snippet_trunc = _snippet(text, matched)
        if budget is not None:
            cost = len(snippet.encode("utf-8"))
            if used_bytes + cost > budget and hits:
                break
            used_bytes += cost
        heading_path: tuple[str, ...] = ()
        if doc.get("format") == "markdown":
            try:
                md = parse_markdown((root / str(doc.get("path", ""))).read_text(encoding="utf-8"))
                if md.headings:
                    heading_path = tuple(h.title for h in md.headings[:3])
            except OSError:
                heading_path = ()
        hits.append(SearchHit(
            id=str(doc.get("document_id", "")),
            path=str(doc.get("path", "")),
            title=str(doc.get("title", "")),
            heading_path=heading_path,
            rank=rank,
            relevance_method="lexical",
            matched_terms=tuple(matched),
            snippet_text=snippet,
            line_start=line_start,
            line_end=line_end,
            snippet_truncated=snippet_trunc,
        ))
    truncated = total > len(hits)
    return hits, total, truncated
